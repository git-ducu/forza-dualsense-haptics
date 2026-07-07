# -*- coding: utf-8 -*-
"""DHE self-test: verifies controller, HID output, triggers, and UDP port."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

from config import paths
from config.settings import Settings
from config import profile_store as preferences


# ── Output helpers ──────────────────────────────────────────────────────────

class TestResult:
    """Collects test output lines and tracks pass/warn/fail counts."""

    def __init__(self):
        self.lines: list[str] = []
        self.ok = 0
        self.warn = 0
        self.fail = 0

    def _emit(self, tag: str, msg: str):
        line = f"[{tag}] {msg}"
        self.lines.append(line)
        print(line)

    def passed(self, msg: str):
        self.ok += 1
        self._emit("OK", msg)

    def warning(self, msg: str):
        self.warn += 1
        self._emit("WARN", msg)

    def failed(self, msg: str):
        self.fail += 1
        self._emit("FAIL", msg)

    def info(self, msg: str):
        line = f"      {msg}"
        self.lines.append(line)
        print(line)

    @property
    def exit_code(self) -> int:
        return 1 if self.fail > 0 else 0

    def summary(self) -> str:
        return f"Results: {self.ok} OK, {self.warn} WARN, {self.fail} FAIL"


# ── RAII guard for controller reset ────────────────────────────────────────

@contextmanager
def _neutral_guard(dev, layout):
    """Ensures controller triggers/motors are reset to neutral on exit."""
    try:
        yield
    finally:
        try:
            from dsio.trigger import clearEffect
            from dsio.device.controller import _assembleRawReport
            reset = clearEffect()
            buf = _assembleRawReport(layout, reset, reset)
            dev.write(buf)
        except Exception:
            pass


# ── Self-test implementation ───────────────────────────────────────────────

def run_self_test(settings: Settings | None = None) -> int:
    """Execute self-test sequence. Returns process exit code (0=ok/warn, 1=fail)."""
    print("\n=== DHE Self-Test ===\n")
    result = TestResult()

    if settings is None:
        settings = Settings()
        try:
            preferences.load(settings)
        except Exception:
            pass

    # 1. Controller detection
    _test_controller(result)

    # 2. UDP port bind test
    _test_udp(result, settings)

    # Summary
    print(f"\n{result.summary()}")
    result.info("Forza telemetry is not required for self-test")

    # Write results to file for GUI-subsystem case
    _write_result_file(result)

    return result.exit_code


def _test_controller(result: TestResult):
    """Detect DualSense and run trigger tests."""
    try:
        from dsio.device.controller import (
            enumerateControllers, _isBtTransport, _assembleRawReport,
            USB_TRANSPORT, BT_TRANSPORT,
        )
        from dsio.trigger import clearEffect, buildSimpleResistance, buildSimpleVibration
        import hid
    except ImportError as e:
        result.failed(f"Cannot import HID modules: {e}")
        return

    devices = enumerateControllers()
    if not devices:
        result.failed("No DualSense controller detected")
        result.info("Ensure controller is connected via USB or Bluetooth")
        result.info("If HID access fails, check tools that may capture the controller")
        result.info("(Steam Input, DS4Windows, DSX, reWASD, or HidHide)")
        return

    target = devices[0]
    is_bt = _isBtTransport(target)
    transport = "Bluetooth" if is_bt else "USB"
    layout = BT_TRANSPORT if is_bt else USB_TRANSPORT
    serial = target.get("serial_number", "") or ""
    masked_serial = (serial[:4] + "****") if len(serial) > 4 else "unknown"
    result.passed(f"DualSense detected via {transport} (serial: {masked_serial})")

    # Open HID device
    dev = hid.device()
    try:
        dev.open_path(target["path"])
    except (OSError, IOError) as e:
        result.failed(f"Cannot open HID device: {e}")
        result.info("Another application may have exclusive access")
        return

    result.passed("HID output available")

    # Use RAII guard to ensure neutral reset
    with _neutral_guard(dev, layout):
        # L2 trigger test (light resistance)
        try:
            eff = buildSimpleResistance(0, 120)
            buf = _assembleRawReport(layout, eff, clearEffect())
            written = dev.write(buf)
            if written and written > 0:
                time.sleep(0.3)
                result.passed("L2 trigger test completed")
            else:
                result.warning("L2 trigger write returned 0")
        except (OSError, IOError) as e:
            result.failed(f"L2 trigger test failed: {e}")

        # R2 trigger test (light resistance)
        try:
            eff = buildSimpleResistance(0, 120)
            buf = _assembleRawReport(layout, clearEffect(), eff)
            written = dev.write(buf)
            if written and written > 0:
                time.sleep(0.3)
                result.passed("R2 trigger test completed")
            else:
                result.warning("R2 trigger write returned 0")
        except (OSError, IOError) as e:
            result.failed(f"R2 trigger test failed: {e}")

        # Brief vibration test
        try:
            vib = buildSimpleVibration(50, 30, 200)
            buf = _assembleRawReport(layout, vib, vib)
            written = dev.write(buf)
            if written and written > 0:
                time.sleep(0.25)
                result.passed("Haptic vibration test completed")
            else:
                result.warning("Haptic vibration write returned 0")
        except (OSError, IOError) as e:
            result.warning(f"Haptic vibration test skipped: {e}")

    # Guard ensures neutral is already sent, close device
    dev.close()


def _test_udp(result: TestResult, settings: Settings):
    """Test UDP port binding."""
    from telemetry.receiver import TelemetryReceiver

    host = settings.udp_host
    port = settings.udp_port

    ok, msg = TelemetryReceiver.testBind(host, port)
    if ok:
        result.passed(f"UDP port {port} bind test passed")
    else:
        result.failed(msg)
        result.info("Ensure no other DHE instance or telemetry app is using the port")

    result.warning("Forza telemetry is not required for self-test")


def _write_result_file(result: TestResult):
    """Write test results to a file for GUI-subsystem accessibility."""
    try:
        out_dir = paths.DATA / "diagnostics"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "self_test_result.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("DHE Self-Test Results\n")
            f.write("=" * 40 + "\n\n")
            for line in result.lines:
                f.write(line + "\n")
            f.write(f"\n{result.summary()}\n")
        print(f"\nResults saved to: {out_path}")
    except OSError:
        pass
