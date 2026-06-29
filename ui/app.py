"""PySide6 GUI — Single-page Instrument Panel.

Layout:
  +──[ status bar: pills + version ]───────────────────────────+
  │  LIVE PANEL  │  TUNING (accordion sections, scrollable)    │
  │  trigger     │  ┌─ Brake ────────────────────────────────┐ │
  │  gauges,     │  │ sliders ...                            │ │
  │  vehicle     │  └────────────────────────────────────────┘ │
  │  info,       │  ┌─ Throttle ─────────────────────────────┐ │
  │  bus levels  │  │ sliders ...                            │ │
  │              │  └────────────────────────────────────────┘ │
  ├──────────────┴─────────────────────────────────────────────┤
  │  ▾ Log (collapsible drawer)                                │
  +────────────────────────────────────────────────────────────+

No sidebar navigation. No tabs. Everything visible at once.
"""
import json
import logging
import os
import queue
import re
import sys
import threading
import time

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame,
    QHBoxLayout, QVBoxLayout, QLabel,
    QSystemTrayIcon, QMenu, QPlainTextEdit,
)
from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtGui import QAction

from runtime import loop, diagnostics
from config import profile_store as preferences, paths

VERSION = "1.0.1"
def t(s: str) -> str: return s
from dsio.trigger.effects import clearEffect, buildSimpleVibration
from runtime.factory import make_backend

from . import style as T
from . import components as W
from .pages.tuningPage import SettingsTab
from .pages.logPage import LogsTab

log = logging.getLogger("dhe")

# legacy aliases for trigger effect functions
def vibrate(frequency: int, amplitude: int, position: int = 0):
    """Wrapper: vibrate(freq, amp) → buildSimpleVibration(position, amp, freq)"""
    return buildSimpleVibration(position, amplitude, frequency)
off = clearEffect

HAPTIC_FREQ_HZ = 40
HAPTIC_AMP_ON = 200
HAPTIC_AMP_OFF = 120
HAPTIC_DURATION_S = 0.10


class _QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self._q = q

    def emit(self, record):
        try:
            self._q.put_nowait((record.levelname, self.format(record)))
        except queue.Full:
            pass


class TriggerGUI:
    def __init__(self, settings):
        self.settings = settings
        # language setting removed — UI is bilingual inline

        # Runtime state
        self._stop = threading.Event()
        self._thread = None
        self._ds = None
        self._listener_cm = None
        self._listener = None
        self._tearing_down = False
        self._refreshing = False
        self._live_telemetry: dict | None = None  # shared with loop thread
        self._refresh_callbacks: list = []
        self._log_queue: queue.Queue = queue.Queue(maxsize=4000)
        self._startup_t0 = time.perf_counter()
        self._startup_profile: dict[str, float | str] = {"app_version": VERSION}
        self.diagnostic_status = "idle"
        self.last_diagnostic_path = ""
        self._diagnostic_cancel_event = None

        # Qt Application
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication(sys.argv)
        self._app.setStyleSheet(T.build_stylesheet())

        self.scale = 1.0

        # Main window
        self.root = QMainWindow()
        self.root.setWindowTitle("DHE")
        self.root.resize(1100, 720)
        self.root.setMinimumSize(QSize(900, 560))
        self._center_window()

        # Tray
        self._tray = None
        self._setup_tray()

        # Build single-page layout
        central = QWidget()
        self.root.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_status_bar(main_layout)
        self._build_main_panels(main_layout)
        self._build_log_drawer(main_layout)

        # LogsTab (hidden log sink — required by _drain_logs)
        self.logs_tab = LogsTab(self)

        # Timers
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(1000)

        self._log_timer = QTimer()
        self._log_timer.timeout.connect(self._drain_logs)
        self._log_timer.start(250)

        self._live_timer = QTimer()
        self._live_timer.timeout.connect(self._refresh_live)
        self._live_timer.start(100)

        self._install_log_handler()
        self._refresh_status()

    # MARK: window ----------------------------------------------------------

    def _center_window(self):
        screen = self._app.primaryScreen().geometry()
        size = self.root.size()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2 - int(screen.height() * 0.04)
        self.root.move(max(0, x), max(0, y))

    # MARK: tray ------------------------------------------------------------

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self.root)
        self._tray.setToolTip("DHE")

        menu = QMenu()
        show_action = QAction("Show", self.root)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        quit_action = QAction("Quit", self.root)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    # MARK: layout — status bar ---------------------------------------------

    def _build_status_bar(self, parent_layout: QVBoxLayout):
        bar = QFrame()
        bar.setObjectName("header")
        bar.setFixedHeight(T.TOOLBAR_HEIGHT)
        h = QHBoxLayout(bar)
        h.setContentsMargins(T.GAP_MD, 0, T.GAP_MD, 0)
        h.setSpacing(T.GAP_SM)

        title = QLabel("DHE")
        title.setProperty("class", "h2")
        h.addWidget(title)

        h.addSpacing(T.GAP_LG)

        self.status_pill = W.Pill(label=t("Pad disconnected"), dot_color=T.RED)
        h.addWidget(self.status_pill)

        self.telemetry_pill = W.Pill(label=t("Awaiting signal"), dot_color=T.YELLOW)
        h.addWidget(self.telemetry_pill)

        h.addStretch()

        self.lbl_version = QLabel(f"v{VERSION}")
        self.lbl_version.setProperty("class", "faint")
        h.addWidget(self.lbl_version)

        parent_layout.addWidget(bar)

    # MARK: layout — main panels (live + tuning) ----------------------------

    def _build_main_panels(self, parent_layout: QVBoxLayout):
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left: Live Monitor Panel
        live_panel = QFrame()
        live_panel.setObjectName("live_panel")
        live_panel.setFixedWidth(T.LIVE_PANEL_WIDTH)
        lp_layout = QVBoxLayout(live_panel)
        lp_layout.setContentsMargins(T.GAP_MD, T.GAP_MD, T.GAP_MD, T.GAP_MD)
        lp_layout.setSpacing(T.GAP_SM)

        lp_layout.addWidget(W.H2("Live"))
        lp_layout.addSpacing(T.GAP_XS)

        # Trigger gauges
        self._gauge_l2 = W.TriggerGauge("L2")
        self._gauge_r2 = W.TriggerGauge("R2")
        lp_layout.addWidget(self._gauge_l2)
        lp_layout.addWidget(self._gauge_r2)

        lp_layout.addSpacing(T.GAP_SM)

        # Vehicle info
        self._info_speed = W.InfoRow("Speed")
        self._info_gear = W.InfoRow("Gear")
        self._info_rpm = W.InfoRow("RPM")
        self._info_surface = W.InfoRow("Surface")
        lp_layout.addWidget(self._info_speed)
        lp_layout.addWidget(self._info_gear)
        lp_layout.addWidget(self._info_rpm)
        lp_layout.addWidget(self._info_surface)

        lp_layout.addSpacing(T.GAP_SM)

        # Haptic bus levels
        lp_layout.addWidget(W.Hint("Haptic Bus"))
        self._bus_surface = W.BusLevel("Surface")
        self._bus_vehicle = W.BusLevel("Vehicle")
        self._bus_engine = W.BusLevel("Engine")
        self._bus_event = W.BusLevel("Event")
        lp_layout.addWidget(self._bus_surface)
        lp_layout.addWidget(self._bus_vehicle)
        lp_layout.addWidget(self._bus_engine)
        lp_layout.addWidget(self._bus_event)

        lp_layout.addStretch()
        body_layout.addWidget(live_panel)

        # Right column: System (top) + Tuning (bottom)
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(T.GAP_MD, T.GAP_MD, T.GAP_MD, 0)
        right_layout.setSpacing(T.GAP_SM)

        # ── System settings (top) ──
        right_layout.addWidget(W.H2("System"))

        from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox

        # Haptic audio device
        right_layout.addWidget(W.Hint("Haptic Device"))
        dev_row = QWidget()
        dr_layout = QHBoxLayout(dev_row)
        dr_layout.setContentsMargins(0, 0, 0, 0)
        dr_layout.setSpacing(6)
        self._haptic_combo = QComboBox()
        self._haptic_combo.setMinimumWidth(200)
        self._haptic_combo.addItem("(loading...)")
        self._haptic_combo.currentTextChanged.connect(self._on_haptic_device_changed)
        dr_layout.addWidget(self._haptic_combo, 1)
        refresh_btn = W.SecondaryButton("Refresh")
        refresh_btn.clicked.connect(self._populate_haptic_combo)
        dr_layout.addWidget(refresh_btn)
        right_layout.addWidget(dev_row)

        # Channel scan / test + L/R assignment (same row)
        ch_row = QWidget()
        ch_layout = QHBoxLayout(ch_row)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        ch_layout.setSpacing(4)
        scan_btn = W.SecondaryButton("Scan ch1-4")
        scan_btn.clicked.connect(self._scan_haptic_channels)
        ch_layout.addWidget(scan_btn)
        for ch in (1, 2, 3, 4):
            btn = W.SecondaryButton(f"ch{ch}")
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda checked=False, c=ch: self._test_haptic_channel(c))
            ch_layout.addWidget(btn)
        ch_layout.addSpacing(12)
        ch_layout.addWidget(QLabel("L:"))
        self._ch_l_combo = QComboBox()
        self._ch_l_combo.addItems(["1", "2", "3", "4"])
        self._ch_l_combo.setCurrentText(str(getattr(self.settings, "haptic_left_channel", 3)))
        self._ch_l_combo.currentTextChanged.connect(lambda v: self._set_channel("haptic_left_channel", v))
        ch_layout.addWidget(self._ch_l_combo)
        ch_layout.addWidget(QLabel("R:"))
        self._ch_r_combo = QComboBox()
        self._ch_r_combo.addItems(["1", "2", "3", "4"])
        self._ch_r_combo.setCurrentText(str(getattr(self.settings, "haptic_right_channel", 4)))
        self._ch_r_combo.currentTextChanged.connect(lambda v: self._set_channel("haptic_right_channel", v))
        ch_layout.addWidget(self._ch_r_combo)
        ch_layout.addStretch()
        right_layout.addWidget(ch_row)

        # Texture test row
        tex_row = QWidget()
        tex_layout = QHBoxLayout(tex_row)
        tex_layout.setContentsMargins(0, 0, 0, 0)
        tex_layout.setSpacing(4)
        tex_layout.addWidget(QLabel("Texture:"))
        for kind, label in (("kerb", "Kerb"), ("thump", "Thump"), ("shift", "Shift")):
            btn = W.SecondaryButton(label)
            btn.clicked.connect(lambda checked=False, k=kind: self._test_haptic_texture(k))
            tex_layout.addWidget(btn)
        # Trigger test (same row)
        tex_layout.addSpacing(12)
        self._test_btn = W.SecondaryButton("Test Triggers")
        self._test_btn.clicked.connect(self._on_test_triggers)
        tex_layout.addWidget(self._test_btn)
        tex_layout.addWidget(QLabel("  L→R vibration check"))
        tex_layout.addStretch()
        right_layout.addWidget(tex_row)

        # Telemetry connection
        right_layout.addWidget(W.Hint("Telemetry Connection"))
        conn_row = QWidget()
        cr_layout = QHBoxLayout(conn_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(8)
        cr_layout.addWidget(QLabel("Host"))
        self._udp_host_edit = QLineEdit(str(getattr(self.settings, "udp_host", "127.0.0.1")))
        self._udp_host_edit.setFixedWidth(110)
        self._udp_host_edit.editingFinished.connect(self._on_udp_host_changed)
        cr_layout.addWidget(self._udp_host_edit)
        cr_layout.addWidget(QLabel("Port"))
        self._udp_port_spin = QSpinBox()
        self._udp_port_spin.setRange(1, 65535)
        self._udp_port_spin.setValue(int(getattr(self.settings, "udp_port", 5300)))
        self._udp_port_spin.setFixedWidth(90)
        self._udp_port_spin.editingFinished.connect(self._on_udp_port_changed)
        cr_layout.addWidget(self._udp_port_spin)
        self._reconnect_btn = W.SecondaryButton("Reconnect")
        self._reconnect_btn.clicked.connect(self._on_reconnect)
        cr_layout.addWidget(self._reconnect_btn)
        cr_layout.addStretch()
        right_layout.addWidget(conn_row)

        # ── Tuning (bottom, takes remaining space) ──
        self.settings_tab = SettingsTab(self)
        right_layout.addWidget(self.settings_tab, 1)

        body_layout.addWidget(right_col, 1)

        parent_layout.addWidget(body, 1)

    # MARK: layout — log drawer ---------------------------------------------

    def _build_log_drawer(self, parent_layout: QVBoxLayout):
        drawer = QFrame()
        drawer.setObjectName("log_drawer")
        drawer_layout = QVBoxLayout(drawer)
        drawer_layout.setContentsMargins(0, 0, 0, 0)
        drawer_layout.setSpacing(0)

        # Toggle button
        self._log_toggle = W.GhostButton(f"\u25BE Log")
        self._log_toggle.setFixedHeight(24)
        self._log_toggle.clicked.connect(self._toggle_log_drawer)
        drawer_layout.addWidget(self._log_toggle)

        # Log text area
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        self._log_text.setFixedHeight(T.LOG_DRAWER_HEIGHT)
        self._log_text.setVisible(False)
        drawer_layout.addWidget(self._log_text)

        self._log_expanded = False
        parent_layout.addWidget(drawer)

    def _toggle_log_drawer(self):
        self._log_expanded = not self._log_expanded
        self._log_text.setVisible(self._log_expanded)
        arrow = "\u25BE" if self._log_expanded else "\u25B8"
        self._log_toggle.setText(f"{arrow} Log")

    # MARK: live panel update -----------------------------------------------

    def update_live_panel(self, telemetry: dict):
        """Called from the main thread (via QTimer) to refresh live gauges."""
        if not telemetry:
            return
        self._gauge_l2.set_value(int(telemetry.get("brake", 0)))
        self._gauge_r2.set_value(int(telemetry.get("accel", 0)))
        speed_kmh = float(telemetry.get("speed", 0))
        self._info_speed.set_value(f"{speed_kmh:.0f} km/h")
        self._info_gear.set_value(str(int(telemetry.get("gear", 0))))
        rpm = float(telemetry.get("rpm", 0))
        max_rpm = float(telemetry.get("max_rpm", 1))
        self._info_rpm.set_value(f"{rpm:.0f} / {max_rpm:.0f}")
        # Surface detection from rumble
        rumble = max(
            abs(float(telemetry.get("surface_rumble_fl", 0))),
            abs(float(telemetry.get("surface_rumble_fr", 0))),
            abs(float(telemetry.get("surface_rumble_rl", 0))),
            abs(float(telemetry.get("surface_rumble_rr", 0))),
        )
        if rumble > 0.30:
            surface = "Gravel"
        elif rumble > 0.10:
            surface = "Dirt"
        elif rumble > 0.0:
            surface = "Kerb"
        else:
            surface = "Tarmac"
        self._info_surface.set_value(surface)

    def update_bus_levels(self, levels: dict):
        """Update haptic bus level indicators. levels: {bus_name: 0..1}."""
        self._bus_surface.set_level(levels.get("surface", 0))
        self._bus_vehicle.set_level(levels.get("vehicle", 0))
        self._bus_engine.set_level(levels.get("engine", 0))
        self._bus_event.set_level(levels.get("event", 0))

    def _refresh_live(self):
        """Called every 100ms by timer — push latest telemetry to Live panel."""
        t = self._live_telemetry
        if t is None:
            return
        self.update_live_panel(t)
        self.update_bus_levels({
            "surface": t.get("_bus_surface", 0),
            "vehicle": t.get("_bus_vehicle", 0),
            "engine": t.get("_bus_engine", 0),
            "event": t.get("_bus_event", 0),
        })

    # MARK: connection settings ---------------------------------------------

    def _on_udp_host_changed(self):
        new_host = self._udp_host_edit.text().strip()
        if new_host and new_host != getattr(self.settings, "udp_host", ""):
            self.settings.udp_host = new_host
            preferences.save_debounced(self.settings)
            log.info("UDP host changed to %s (restart required)", new_host)

    def _on_udp_port_changed(self):
        new_port = self._udp_port_spin.value()
        if new_port != int(getattr(self.settings, "udp_port", 5300)):
            self.settings.udp_port = new_port
            preferences.save_debounced(self.settings)
            log.info("UDP port changed to %d (restart required)", new_port)

    def _on_reconnect(self):
        """Force reconnect DualSense + restart UDP receiver."""
        log.info("Manual reconnect triggered")
        self.status_pill.set_label("Reconnecting...")
        if self._ds:
            self._ds.forceReconnect()
        self._restart_backend()

    # MARK: haptic device ---------------------------------------------------

    def _populate_haptic_combo(self):
        """Fill haptic device combo from available audio outputs."""
        try:
            labels = self.get_haptic_device_labels()
        except Exception:
            labels = []
        self._haptic_combo.blockSignals(True)
        self._haptic_combo.clear()
        if not labels:
            self._haptic_combo.addItem("(no device)")
        else:
            self._haptic_combo.addItems(labels)
            # restore saved selection
            saved = getattr(self.settings, "haptic_device_name", "")
            if saved in labels:
                self._haptic_combo.setCurrentText(saved)
        self._haptic_combo.blockSignals(False)

    def _on_haptic_device_changed(self, text: str):
        if text and not text.startswith("("):
            self.settings.haptic_device_name = text
            preferences.save_debounced(self.settings)
            log.info("Haptic device → %s", text)

    def _scan_haptic_channels(self):
        """Play sequential channel scan on selected haptic device."""
        threading.Thread(target=self.haptic_channel_scan, daemon=True).start()

    def _test_haptic_channel(self, ch: int):
        """Test a single haptic channel."""
        threading.Thread(target=self.haptic_channel_test, args=(ch,), daemon=True).start()

    def _set_channel(self, attr: str, value: str):
        """Set L/R channel assignment."""
        try:
            ch = int(value)
        except ValueError:
            return
        setattr(self.settings, attr, ch)
        preferences.save_debounced(self.settings)
        log.info("%s = %d", attr, ch)

    def _test_haptic_texture(self, kind: str):
        """Test a haptic texture (kerb/thump/shift)."""
        def run():
            try:
                self.haptic_texture_test(kind)
            except Exception as e:
                log.warning("Texture test %s failed: %s", kind, e)
        threading.Thread(target=run, daemon=True).start()

    def _on_test_triggers(self):
        """Run trigger test and show result feedback."""
        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing...")

        # Quick check — no DS connected
        try:
            ds_ready = self._ds and self._ds.connected
        except Exception:
            ds_ready = False

        if not ds_ready:
            self._test_btn.setText("Pad not connected")
            self._test_btn.setEnabled(True)
            QTimer.singleShot(3000, lambda: self._test_btn.setText("Test Triggers"))
            return

        self._trigger_test_result = None

        def run():
            msg = "Triggers OK \u2713"
            try:
                l = vibrate(34, 210)
                r = vibrate(34, 210)
                self._ds.set(l, off())
                time.sleep(0.22)
                self._ds.set(off(), off())
                time.sleep(0.10)
                self._ds.set(off(), r)
                time.sleep(0.22)
                self._ds.set(off(), off())
                time.sleep(0.10)
                self._ds.set(l, r)
                time.sleep(0.35)
                self._ds.set(off(), off())
            except Exception as e:
                msg = "Trigger test failed"
                log.warning("trigger test failed: %s", e)
            self._trigger_test_result = msg

        threading.Thread(target=run, daemon=True).start()
        # Poll from main thread until result is ready
        self._poll_trigger_result()

    def _poll_trigger_result(self):
        if self._trigger_test_result is not None:
            self._test_btn.setText(self._trigger_test_result)
            self._test_btn.setEnabled(True)
            QTimer.singleShot(3000, lambda: self._test_btn.setText("Test Triggers"))
        else:
            QTimer.singleShot(50, self._poll_trigger_result)

    def _finish_trigger_test(self, message: str):
        self._test_btn.setText(message)
        self._test_btn.setEnabled(True)
        QTimer.singleShot(3000, lambda: self._test_btn.setText("Test Triggers"))

    # MARK: lifecycle -------------------------------------------------------

    def run(self):
        QTimer.singleShot(0, self._start_backend)
        QTimer.singleShot(100, self._populate_haptic_combo)
        self.root.show()
        try:
            self._app.exec()
        finally:
            self._teardown()

    def _show_window(self):
        self.root.showNormal()
        self.root.activateWindow()
        self.root.raise_()

    def _quit(self):
        self._teardown()
        self._app.quit()

    def _teardown(self):
        if self._tearing_down:
            return
        self._tearing_down = True
        if self._tray:
            self._tray.hide()
        try:
            preferences.flush_debounced(self.settings)
        except Exception:
            pass
        root_logger = logging.getLogger()
        for h in list(root_logger.handlers):
            if isinstance(h, _QueueLogHandler):
                root_logger.removeHandler(h)
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._listener_cm:
            try:
                self._listener_cm.__exit__(None, None, None)
            except Exception:
                pass
        if self._ds:
            try:
                self._ds.close()
            except Exception:
                pass

    def _install_log_handler(self):
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        from .pages.logPage import DEFAULT_LOG_LEVEL
        h = _QueueLogHandler(self._log_queue)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        root_logger.addHandler(h)
        root_logger.setLevel(getattr(logging, DEFAULT_LOG_LEVEL))

    def _drain_logs(self):
        if self._tearing_down:
            return
        for _ in range(200):
            try:
                level, msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self.logs_tab.write(level, msg)
            # Also append to the log drawer
            self._log_text.appendPlainText(msg)
            try:
                diagnostics.RAW_LOGGER.write({"type": "app_log", "level": level, "message": msg, "t": time.time()})
            except Exception:
                pass

    def _start_backend(self):
        from telemetry.receiver import TelemetryReceiver
        s = self.settings
        try:
            preferences.load(s)
            self._ds = make_backend(s, s.enable_startup_pulse)
            self._ds.open()
            self._listener_cm = TelemetryReceiver(
                s.udp_host, s.udp_port, s.udp_timeout, s.udp_forward_to, s.udp_forward)
            self._listener = self._listener_cm.__enter__()
            log.info("Listening on %s:%d", s.udp_host, s.udp_port)
            log.info("In game: HUD & Gameplay -> Data Out: ON, IP %s, Port %d", s.udp_host, s.udp_port)
            t_backend = time.perf_counter()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._startup_profile["backend_start_ms"] = round((time.perf_counter() - t_backend) * 1000, 2)
            self._startup_profile["total_to_ready_ms"] = round((time.perf_counter() - self._startup_t0) * 1000, 2)
            self._write_startup_profile()
        except OSError:
            log.exception("UDP bind failed on %s:%d", s.udp_host, s.udp_port)
            self.status_pill.set_label(t("UDP port {port} in use").format(port=s.udp_port))
        except Exception as exc:
            log.exception("Backend startup failed")
            self.status_pill.set_label(t("Backend failed: {error}").format(error=exc))

    def _run_loop(self):
        try:
            loop.run(self._ds, self._listener, self.settings,
                     stop_event=self._stop,
                     telemetry_sink=self._on_telemetry)
        except Exception:
            log.exception("Telemetry loop crashed")
        finally:
            if not self._stop.is_set():
                QTimer.singleShot(0, self._quit)

    def _on_telemetry(self, t: dict):
        """Called from loop thread — just store latest dict for timer to pick up."""
        self._live_telemetry = t

    def _restart_backend(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._ds:
            self._ds.close()
        self._stop.clear()
        s = self.settings
        try:
            self._ds = make_backend(s, False)
            self._ds.open()
            log.info("HID mode: writing direct to DualSense")
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        except Exception as exc:
            log.exception("Backend restart failed")
            QTimer.singleShot(0, lambda: self.status_pill.set_label(
                t("Backend failed: {error}").format(error=exc)))

    def _write_startup_profile(self):
        try:
            paths.DATA.mkdir(parents=True, exist_ok=True)
            data = dict(self._startup_profile)
            data["written_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            (paths.DATA / "startup_profile.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug("write startup profile failed: %s", e)

    # MARK: status ----------------------------------------------------------

    def _refresh_status(self):
        if self._tearing_down:
            return
        connected = bool(self._ds and self._ds.connected)
        if connected:
            self.status_pill.set(t("Pad connected"), dot_color=T.GREEN)
        else:
            self.status_pill.set(t("Pad disconnected"), dot_color=T.RED)

        tel_label, tel_color = self.telemetry_status_text_color()
        self.telemetry_pill.set(tel_label, dot_color=tel_color)

    def telemetry_status_text_color(self):
        listener = self._listener
        if listener is None:
            return t("Awaiting signal"), T.YELLOW
        if int(getattr(listener, "badPacketCount", 0) or 0) > 0 and int(getattr(listener, "packetCount", 0) or 0) == int(getattr(listener, "badPacketCount", 0) or 0):
            return t("UDP port error"), T.RED
        last = float(getattr(listener, "lastPacketTime", 0.0) or 0.0)
        if last <= 0.0:
            return t("Awaiting signal"), T.YELLOW
        if time.time() - last > 5.0 or getattr(listener, "lost", False):
            return t("Signal lost"), T.YELLOW
        if bool(getattr(self.settings, "udp_forward", False)):
            return t("Forwarding"), T.GREEN
        return t("Receiving"), T.GREEN

    refresh_status = _refresh_status

    def refresh_global_state(self):
        self._refresh_status()
        self.refresh_setting_widgets()

    # MARK: shared helpers --------------------------------------------------

    def register_refresh(self, fn):
        self._refresh_callbacks.append(fn)

    def refresh_setting_widgets(self):
        self._refreshing = True
        try:
            for fn in self._refresh_callbacks:
                try:
                    fn()
                except Exception:
                    log.exception("refresh callback failed")
        finally:
            self._refreshing = False

    def haptic(self, on_state: bool):
        if self._ds and self._ds.connected:
            threading.Thread(target=self._do_haptic, args=(on_state,), daemon=True).start()

    def _do_haptic(self, on_state: bool):
        amp = HAPTIC_AMP_ON if on_state else HAPTIC_AMP_OFF
        try:
            self._ds.set(vibrate(HAPTIC_FREQ_HZ, amp), off())
            time.sleep(HAPTIC_DURATION_S)
            self._ds.set(off(), off())
        except Exception:
            pass

    def trigger_output_check(self, callback=None):
        try:
            ds_ok = self._ds and self._ds.connected
        except Exception:
            ds_ok = False
        if not ds_ok:
            if callback:
                QTimer.singleShot(0, lambda: callback(False, "Pad not connected"))
            return

        def run():
            ok = True
            message = "Triggers OK"
            try:
                l = vibrate(34, 210)
                r = vibrate(34, 210)
                self._ds.set(l, off())
                time.sleep(0.22)
                self._ds.set(off(), off())
                time.sleep(0.10)
                self._ds.set(off(), r)
                time.sleep(0.22)
                self._ds.set(off(), off())
                time.sleep(0.10)
                self._ds.set(l, r)
                time.sleep(0.35)
                self._ds.set(off(), off())
            except Exception as e:
                ok = False
                message = "Trigger check failed"
                log.warning("trigger output check failed: %s", e)
            finally:
                if callback:
                    QTimer.singleShot(0, lambda: callback(ok, message))
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Haptic device helpers — called by pages (no direct forza import needed)

    def get_haptic_device_labels(self) -> list[str]:
        from telemetry.haptics import audioEngine
        return audioEngine.candidate_device_labels()

    def haptic_channel_scan(self) -> None:
        from telemetry.haptics import audioEngine
        audioEngine.play_channel_scan(self.settings)

    def haptic_channel_test(self, channel: int) -> None:
        from telemetry.haptics import audioEngine
        audioEngine.play_channel_test(self.settings, channel)

    def haptic_texture_test(self, kind: str) -> None:
        from telemetry.haptics import audioEngine
        audioEngine.play_texture_test(self.settings, kind)

    # ------------------------------------------------------------------
    # Setting change feedback - context-aware preview
    # Routes based on option_registry.spec.affects field:
    #   "trigger" - trigger motor vibration
    #   "haptic"  - haptic audio speaker

    _feedback_lock = threading.Lock()
    _feedback_pending = False

    # Frequency hints for haptic preview by key (Hz)
    _HAPTIC_FREQ_HINTS = {
        # Core balance
        "haptic_master_gain": 75.0,
        "haptic_bass_foundation_gain": 45.0,
        "haptic_sub_bass_boost": 35.0,
        "haptic_mid_texture_balance": 120.0,
        "haptic_high_edge_gain": 220.0,
        "haptic_high_shimmer_ratio": 280.0,
        "haptic_high_shimmer_cap": 280.0,
        "haptic_spectrum_glue_gain": 100.0,
        "haptic_mid_min_gain": 120.0,
        "haptic_fatigue_control": 100.0,
        "haptic_mastering_sidechain_strength": 100.0,
        "haptic_mastering_soft_saturation": 100.0,
        # Road / tire
        "haptic_road_gain": 85.0,
        "haptic_texture_palette_strength": 95.0,
        "haptic_gravel_gain": 58.0,
        "haptic_tire_scrub_texture_strength": 200.0,
        "haptic_grip_edge_high_strength": 300.0,
        "haptic_slip_sizzle_strength": 320.0,
        "haptic_drift_breakaway_strength": 50.0,
        # Shift
        "haptic_shift_master_gain": 150.0,
        "haptic_shift_impact_gain": 150.0,
        "haptic_shift_body_gain": 60.0,
        # Spatial
        "haptic_steer_width_gain": 100.0,
        "haptic_front_rear_contrast": 100.0,
        "haptic_final_side_boost": 100.0,
        # Extended telemetry
        "haptic_rpm_texture_gain": 90.0,
        "haptic_body_motion_gain": 50.0,
        "haptic_traction_pulse_gain": 70.0,
        # Engine
        "haptic_rpm_harmonics_strength": 140.0,
        "haptic_redline_warning_strength": 200.0,
        "haptic_turbo_spool_strength": 160.0,
        "haptic_engine_braking_strength": 60.0,
        "haptic_corner_exit_strength": 55.0,
        "haptic_engine_start_strength": 45.0,
        "haptic_idle_strength": 40.0,
        "haptic_punch_sustain_blend": 50.0,
    }
    # Texture kind hints (default "tone" if not listed)
    _HAPTIC_KIND_HINTS = {
        "haptic_gravel_gain": "gravel",
        "haptic_tire_scrub_texture_strength": "noise",
        "haptic_slip_sizzle_strength": "noise",
        "haptic_grip_edge_high_strength": "noise",
        "haptic_drift_breakaway_strength": "thump",
        "haptic_road_gain": "kerb",
        "haptic_texture_palette_strength": "kerb",
        "haptic_shift_master_gain": "shift",
        "haptic_shift_impact_gain": "shift",
        "haptic_shift_body_gain": "thump",
        "haptic_corner_exit_strength": "thump",
        "haptic_engine_start_strength": "thump",
        "haptic_punch_sustain_blend": "thump",
    }

    def setting_feedback(self, attr: str = ""):
        """Play a context-aware preview of the changed setting."""
        if self._feedback_pending:
            return
        self._feedback_pending = True
        threading.Thread(target=self._do_setting_feedback, args=(attr,), daemon=True).start()

    def _do_setting_feedback(self, attr: str):
        from config import option_registry
        try:
            with self._feedback_lock:
                spec = option_registry.spec_for(attr)
                affects = spec.affects if spec else ""
                if affects == "trigger":
                    self._preview_trigger(attr)
                elif affects == "haptic":
                    self._preview_haptic(attr)
                else:
                    # Unknown or system --silent
                    pass
        except Exception:
            pass
        finally:
            self._feedback_pending = False

    def _preview_trigger(self, attr: str):
        """Trigger vibration scaled proportionally, respecting master gain."""
        if not (self._ds and self._ds.connected):
            return
        from config import option_registry

        # Trigger master --if at minimum, no preview for sub-settings
        trigger_master = float(getattr(self.settings, "trigger_master_gain", 1.0))
        if attr != "trigger_master_gain" and trigger_master < 0.3:
            return

        val = getattr(self.settings, attr, 1.0)
        if isinstance(val, bool):
            amp = 220 if val else 0
            if amp == 0:
                return
        else:
            pct = option_registry.percent_from_raw(attr, val)
            if pct is not None:
                amp = int(min(255, max(0, float(pct) / 300.0 * 255)))
            else:
                amp = int(min(255, max(0, float(val) * 160)))
            if amp < 20:
                return

        # Apply trigger master scaling for sub-settings
        if attr != "trigger_master_gain":
            amp = int(min(255, amp * min(1.5, trigger_master)))

        freq = 34 + int(min(20, amp / 12))
        pulse = vibrate(freq, amp)
        self._ds.set(pulse, off())
        time.sleep(0.18)
        self._ds.set(off(), off())

    def _preview_haptic(self, attr: str):
        """Play haptic texture through speaker, respecting full gain chain."""
        try:
            from telemetry.haptics import audioEngine as haptics_audio
            from dsio.haptics.waveform import make_test_texture
            from config import option_registry
            import numpy as np
            import sounddevice as sd

            # Master gain --if 0, no haptic preview at all
            master = float(getattr(self.settings, "haptic_master_gain", 1.0))
            if master < 0.01:
                return

            # Determine which bus this setting belongs to and get bus gain
            bus_gain = self._resolve_bus_gain(attr)

            dev = haptics_audio._device_or_raise(self.settings)
            sr = int(getattr(self.settings, "haptic_sample_rate", 48000) or 48000)

            val = getattr(self.settings, attr, 1.0)
            if isinstance(val, bool):
                source_gain = 0.5 if val else 0.0
            else:
                pct = option_registry.percent_from_raw(attr, val)
                if pct is not None:
                    source_gain = min(1.0, max(0.0, float(pct) / 300.0))
                else:
                    source_gain = min(1.0, max(0.0, float(val)))

            # Final gain = master × bus × source (same as engine)
            gain = min(0.9, master * bus_gain * source_gain * 1.2)
            if gain < 0.01:
                return

            freq = self._HAPTIC_FREQ_HINTS.get(attr, 100.0)
            kind = self._HAPTIC_KIND_HINTS.get(attr, "tone")

            sig = make_test_texture(kind, sr, 0.18, gain, freq=freq)
            data = np.zeros((len(sig), 4), dtype=np.float32)
            li = max(0, min(3, int(getattr(self.settings, "haptic_left_channel", 3)) - 1))
            ri = max(0, min(3, int(getattr(self.settings, "haptic_right_channel", 4)) - 1))
            data[:, li] = sig
            data[:, ri] = sig
            sd.play(data, samplerate=sr, device=dev.index, blocking=True)
            sd.stop()
        except Exception:
            pass

    def _resolve_bus_gain(self, attr: str) -> float:
        """Get the bus gain multiplier for a setting based on which bus it belongs to."""
        # Surface bus keys
        _SURFACE = {"haptic_road_gain", "haptic_gravel_gain", "haptic_texture_palette_strength",
                    "haptic_surface_texture_enabled", "haptic_surface_bus_gain"}
        # Engine bus keys
        _ENGINE = {"haptic_rpm_texture_gain", "haptic_rpm_harmonics_strength", "haptic_idle_strength",
                   "haptic_turbo_spool_strength", "haptic_engine_braking_strength",
                   "haptic_corner_exit_strength", "haptic_engine_start_strength",
                   "haptic_rpm_texture_enabled", "haptic_idle_haptics_enabled", "haptic_engine_bus_gain"}
        # Vehicle bus keys
        _VEHICLE = {"haptic_drift_breakaway_strength", "haptic_tire_scrub_texture_strength",
                    "haptic_grip_edge_high_strength", "haptic_slip_sizzle_strength",
                    "haptic_body_motion_gain", "haptic_traction_pulse_gain",
                    "haptic_body_motion_enabled", "haptic_traction_pulse_enabled",
                    "haptic_vehicle_flavor_enabled", "haptic_vehicle_bus_gain"}
        # Event bus keys
        _EVENT = {"haptic_shift_master_gain", "haptic_shift_click_strength",
                  "haptic_shift_clunk_strength", "haptic_shift_engagement_strength",
                  "haptic_accel_onset_strength", "haptic_decel_onset_strength",
                  "haptic_impact_master_gain", "haptic_impact_sub_strength",
                  "haptic_impact_crack_high_strength", "haptic_special_events_enabled",
                  "haptic_event_bus_gain"}

        if attr in _SURFACE:
            return float(getattr(self.settings, "haptic_surface_bus_gain", 0.52))
        elif attr in _ENGINE:
            return float(getattr(self.settings, "haptic_engine_bus_gain", 0.65))
        elif attr in _VEHICLE:
            return float(getattr(self.settings, "haptic_vehicle_bus_gain", 0.72))
        elif attr in _EVENT:
            return float(getattr(self.settings, "haptic_event_bus_gain", 0.84))
        else:
            return 1.0  # Master-level or unclassified

    def toast(self, message: str, ms: int = 2500):
        """Show a brief status message."""
        # Use status bar or temporary label overlay
        log.info("[TOAST] %s", message)

    def px(self, n: int) -> int:
        return max(1, int(round(n * self.scale)))

    def font_size(self, base: int) -> int:
        return max(8, int(round(base * self.scale)))
