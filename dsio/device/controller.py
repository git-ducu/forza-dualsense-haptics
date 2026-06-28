# -*- coding: utf-8 -*-
# DualSense HID output-report writer with auto-reconnect.

from __future__ import annotations
from dataclasses import dataclass
import logging
import struct
import sys
import threading
import time
import zlib

if sys.platform.startswith("linux"):
    from . import _hidraw as hid
else:
    import hid

from . import hidhide
from dsio.trigger import clearEffect, buildSimpleResistance, Mode

log = logging.getLogger("dhe.ds")

# ── Hardware identifiers ──────────────────────────────────────────────────────

SONY_VENDOR = 0x054C
PRODUCT_IDS = (0x0CE6, 0x0DF2)      # DualSense, DualSense Edge

# Output report flag bits (byte at flagsOff)
FLAG_MOTOR_R    = 0x01
FLAG_MOTOR_L    = 0x02
FLAG_MOTORS     = FLAG_MOTOR_R | FLAG_MOTOR_L
FLAG_TRIGGERS   = 0x04 | 0x08

# ── Report layout ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ReportLayout:
    """Byte offsets for USB vs BT output reports."""
    reportId: int
    flagsOff: int
    vf1Off: int
    powerOff: int
    rightTrigOff: int
    leftTrigOff: int
    reportLen: int
    isBT: bool

USB_TRANSPORT = ReportLayout(
    reportId=0x02, flagsOff=1, vf1Off=2, powerOff=10,
    rightTrigOff=11, leftTrigOff=22, reportLen=64, isBT=False)
BT_TRANSPORT = ReportLayout(
    reportId=0x31, flagsOff=2, vf1Off=3, powerOff=11,
    rightTrigOff=12, leftTrigOff=23, reportLen=78, isBT=True)

_BT_REPORT_CRC_INIT = zlib.crc32(b"\xA2")

_macCache: dict[bytes, str] = {}
_macCacheLock = threading.Lock()


# ── Device discovery ─────────────────────────────────────────────────────────

def enumerateControllers() -> list[dict]:
    """Return hidapi entries for DualSense gamepads (filter to gamepad HID interface).
    When a pad appears on both USB and BT simultaneously, keeps USB only."""
    rawDevices = [d for d in hid.enumerate(SONY_VENDOR, 0)
                  if d.get("product_id") in PRODUCT_IDS
                  and d.get("usage_page", 1) == 1
                  and d.get("usage", 5) == 5]
    # resolve MAC via feature report when serial is absent (USB on Windows)
    for d in rawDevices:
        if d.get("serial_number"):
            continue
        path = d["path"]
        with _macCacheLock:
            cached = _macCache.get(path)
            if cached is None:
                dev = hid.device()
                try:
                    dev.open_path(path)
                    feat = dev.get_feature_report(0x09, 64)
                except (OSError, IOError) as e:
                    log.warning("feature report 0x09 failed on %r: %s", path, e)
                    dev.close()
                    continue
                dev.close()
                if len(feat) < 7:
                    continue
                # MAC bytes in feature report are little-endian
                cached = "".join(f"{b:02x}" for b in feat[6:0:-1])
                _macCache[path] = cached
        d["serial_number"] = cached
    # deduplicate: keep wired when both transports show same pad
    wiredSerials = {d["serial_number"] for d in rawDevices
                    if d.get("serial_number") and not _isBtTransport(d)}
    return [d for d in rawDevices
            if not (_isBtTransport(d) and d.get("serial_number") in wiredSerials)]


def _isBtTransport(info: dict) -> bool:
    """Heuristic BT detection across hidapi backends."""
    busType = info.get("bus_type")
    if busType in (2, 5):                    # Windows=2, Linux hidraw=5
        return True
    if busType in (1, 3):                    # USB variants
        return False
    path = info.get("path", b"")
    if isinstance(path, str):
        path = path.encode()
    return b"BTHENUM" in path.upper() or b"BLUETOOTH" in path.upper()


def _logOpenFailure(err) -> None:
    if sys.platform.startswith("linux"):
        log.error("Cannot open controller (%s). Add the udev rule:\n"
                  "  sudo cp packaging/linux/70-dualsense.rules /etc/udev/rules.d/\n"
                  "  sudo udevadm control --reload-rules && sudo udevadm trigger", err)
    else:
        log.warning("Cannot open controller (%s) — exclusive access held elsewhere.", err)



def pulseIdentifyDevice(info: dict, force: int = 180, durationSec: float = 0.2) -> bool:
    """Briefly pulse both triggers on a controller from enumeration info.
    Returns False on failure. Does not require a DualSenseWriter instance."""
    layout = BT_TRANSPORT if _isBtTransport(info) else USB_TRANSPORT
    dev = hid.device()
    try:
        dev.open_path(info["path"])
    except (OSError, IOError) as e:
        log.warning("identifyPulse open failed: %s", e)
        return False
    try:
        pulseEffect = buildSimpleResistance(0, force)
        dev.write(_assembleRawReport(layout, pulseEffect, pulseEffect))
        time.sleep(durationSec)
        resetEffect = clearEffect()
        dev.write(_assembleRawReport(layout, resetEffect, resetEffect))
        return True
    except (OSError, IOError) as e:
        log.warning("identifyPulse write failed: %s", e)
        return False
    finally:
        dev.close()


def _assembleRawReport(layout: ReportLayout, leftEffect, rightEffect,
                       motorL: int = 0, motorR: int = 0, writeMotors: bool = False) -> bytearray:
    """Build a complete HID output report from trigger effects + optional motors."""
    buf = bytearray(layout.reportLen)
    buf[0] = layout.reportId
    if layout.isBT:
        buf[1] = 0x02
    flags = FLAG_TRIGGERS
    if writeMotors:
        flags |= FLAG_MOTORS
        buf[layout.flagsOff + 2] = max(0, min(255, int(motorR)))
        buf[layout.flagsOff + 3] = max(0, min(255, int(motorL)))
    buf[layout.flagsOff] = flags
    # write trigger sections
    leftPacked = leftEffect.pack()
    rightPacked = rightEffect.pack()
    rOff = layout.rightTrigOff
    lOff = layout.leftTrigOff
    buf[rOff:rOff + 11] = rightPacked
    buf[lOff:lOff + 11] = leftPacked
    if layout.isBT:
        crc = zlib.crc32(memoryview(buf)[:74], _BT_REPORT_CRC_INIT)
        struct.pack_into("<I", buf, 74, crc)
    return buf



# ── DualSenseWriter — main controller interface ─────────────────────────────────────

class DualSenseWriter:
    """Background HID output writer for DualSense controllers.

    Operates independently of controller presence — silently queues
    frames and writes them when a device becomes available."""

    def __init__(self, *,
                 startupPulseForce: int = 180,
                 enableStartupPulse: bool = True,
                 reconnectIntervalSec: float = 5.0,
                 enableReconnect: bool = False,
                 lockedSerial: str = ""):
        self._hidDev = None
        self._devPath = None
        self._devSerial: str = ""
        self._layout = USB_TRANSPORT
        self._ioLock = threading.Lock()

        # queued frame state
        self._leftEffect = clearEffect()
        self._rightEffect = clearEffect()
        self._motorL = 0
        self._motorR = 0
        self._writeMotors = False
        self._bodyRumbleOwned = False
        self._frameDirty = False

        # lifecycle
        self._running = False
        self._ioThread: threading.Thread | None = None
        self._wakeSignal = threading.Event()

        # config
        self._pulseForce = startupPulseForce
        self._enableStartupPulse = enableStartupPulse
        self._reconnectInterval = reconnectIntervalSec
        self._enableReconnect = enableReconnect
        self._lockedSerial = lockedSerial

        # state tracking
        self._everConnected = False
        self._openHinted = False
        self._waitHinted = False
        self._lastAttemptTime = -1e9
        self._lastInputTime = 0.0
        self._lastEnumCount = -1

        # idle timeouts for watchdog (BT needs longer due to power saving)
        self._idleTimeoutUsb = 3.0
        self._idleTimeoutBt = 6.0

    # ── Public properties ─────────────────────────────────────────────────────

    @property
    def isOpen(self) -> bool:
        return self._hidDev is not None

    connected = isOpen

    @property
    def isLatched(self) -> bool:
        """Handle stays open after connect (HidHide active or reconnect off)."""
        return (self._everConnected
                and (hidhide.is_detected() or not self._enableReconnect))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Launch the I/O thread. Safe to call before any controller is plugged in."""
        if self._running:
            return
        log.info("HidHide: %s", "detected" if hidhide.is_detected() else "not detected")
        self._logReconnectMode()
        self._running = True
        self._ioThread = threading.Thread(target=self._ioLoop, daemon=True)
        self._ioThread.start()

    def close(self) -> None:
        """Shut down I/O thread and release HID handle."""
        if not self._running and self._ioThread is None:
            return
        self._running = False
        self._wakeSignal.set()
        if self._ioThread:
            self._ioThread.join(timeout=2.0)
            self._ioThread = None
        self._releaseDevice()

    def __enter__(self) -> "DualSenseWriter":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ── Frame submission ──────────────────────────────────────────────────────

    def submitFrame(self, leftEffect, rightEffect,
                    motorL: int = 0, motorR: int = 0,
                    bodyRumbleEnabled: bool = False) -> None:
        """Queue trigger effects + optional body rumble for next write cycle."""
        motorL = max(0, min(255, int(motorL)))
        motorR = max(0, min(255, int(motorR)))
        wantMotors = bool(bodyRumbleEnabled)
        with self._ioLock:
            if wantMotors:
                self._bodyRumbleOwned = True
            elif self._bodyRumbleOwned:
                # release frame: zero motors with flags set, then stop owning
                wantMotors = True
                motorL = motorR = 0
                self._bodyRumbleOwned = False
            self._leftEffect = leftEffect
            self._rightEffect = rightEffect
            self._motorL = motorL
            self._motorR = motorR
            self._writeMotors = wantMotors
            self._frameDirty = True
        self._wakeSignal.set()

    def set(self, left, right, motor_left: int = 0, motor_right: int = 0, body_rumble_enabled: bool = False):
        self.submitFrame(left, right, motor_left, motor_right, body_rumble_enabled)

    # ── Runtime config ────────────────────────────────────────────────────────

    def setReconnectEnabled(self, enabled: bool) -> None:
        val = bool(enabled)
        if val == self._enableReconnect:
            return
        self._enableReconnect = val
        self._wakeSignal.set()
        if val:
            log.info("Auto-reconnect enabled -- retries every %.0fs.", self._reconnectInterval)
        else:
            log.info("Auto-reconnect disabled%s.",
                     " (latched -- HidHide detected)" if hidhide.is_detected() else "")

    set_reconnect_enabled = setReconnectEnabled

    def setReconnectInterval(self, intervalSec: float) -> None:
        self._reconnectInterval = float(intervalSec)
        self._wakeSignal.set()

    set_reconnect_interval = setReconnectInterval

    def setLockedSerial(self, serial: str) -> None:
        self._lockedSerial = serial

    def forceReconnect(self) -> None:
        """Drop current handle and immediately try a fresh connection."""
        self._everConnected = False
        self._lastAttemptTime = -1e9
        self._releaseDevice("user-initiated switch")
        self._wakeSignal.set()

    # ── Internal: connect / disconnect ────────────────────────────────────────

    def _tryConnect(self) -> bool:
        devices = enumerateControllers()
        n = len(devices)
        if n != self._lastEnumCount:
            self._lastEnumCount = n
            if n == 0:
                log.info("HID: 0 DualSense interfaces visible "
                         "(controller off, cable loose, or cloaked by HidHide/Steam)")
            else:
                desc = ", ".join(
                    f"[pid=0x{d.get('product_id',0):04x} bus={d.get('bus_type')}]"
                    for d in devices)
                log.info("HID: %d DualSense interface(s): %s", n, desc)
        if not devices:
            if not self._waitHinted:
                log.info("Scanning for DualSense -- poll interval %.0fs", self._reconnectInterval)
                self._waitHinted = True
            return False
        # pick target: locked serial first, otherwise first found
        target = None
        if self._lockedSerial:
            target = next((d for d in devices if d.get("serial_number") == self._lockedSerial), None)
        if target is None:
            target = devices[0]
        try:
            dev = hid.device()
            dev.open_path(target["path"])
            dev.set_nonblocking(True)
        except (OSError, IOError) as e:
            if not self._openHinted:
                _logOpenFailure(e)
                self._openHinted = True
            return False
        self._hidDev = dev
        self._devPath = target.get("path")
        self._devSerial = target.get("serial_number") or ""
        self._layout = BT_TRANSPORT if _isBtTransport(target) else USB_TRANSPORT
        self._openHinted = self._waitHinted = False
        self._everConnected = True
        self._lastInputTime = time.monotonic()
        bus = "BT" if self._layout.isBT else "USB"
        log.info("DualSense connected (%s)%s", bus, " -- latched" if self.isLatched else "")
        # startup pulse
        if self._enableStartupPulse:
            pulseEff = buildSimpleResistance(0, self._pulseForce)
            self._safeWrite(self._buildReport(pulseEff, pulseEff))
            time.sleep(0.2)
            resetEff = clearEffect()
            self._safeWrite(self._buildReport(resetEff, resetEff, 0, 0, self._bodyRumbleOwned))
        return True

    def _releaseDevice(self, reason: str = "") -> None:
        if self.isLatched and self._running:
            return
        wasOpen = self._hidDev is not None
        if wasOpen:
            resetEff = clearEffect()
            self._safeWrite(self._buildReport(resetEff, resetEff, 0, 0, self._bodyRumbleOwned))
            try:
                self._hidDev.close()
            except Exception:
                pass
        self._hidDev = None
        self._devPath = None
        self._devSerial = ""
        self._bodyRumbleOwned = False
        if wasOpen and self._running:
            suffix = f" ({reason})" if reason else ""
            if self._enableReconnect:
                log.warning("DualSense disconnected%s -- retrying every %.0fs",
                            suffix, self._reconnectInterval)
            else:
                log.warning("DualSense disconnected%s -- auto-reconnect disabled.", suffix)

    # ── Internal: I/O loop ───────────────────────────────────────────────────

    def _ioLoop(self) -> None:
        while self._running:
            now = time.monotonic()
            # -- not connected: try reconnect on interval
            if not self.isOpen:
                if self._enableReconnect or not self._everConnected:
                    if now - self._lastAttemptTime >= self._reconnectInterval:
                        self._lastAttemptTime = now
                        self._tryConnect()
                self._wakeSignal.wait(0.5)
                self._wakeSignal.clear()
                continue
            latched = self.isLatched
            # -- drain one input report for liveness watchdog
            try:
                inputData = self._hidDev.read(self._layout.reportLen, timeout_ms=0)
            except OSError as e:
                if not latched:
                    self._releaseDevice(f"read error: {e}")
                    continue
                inputData = None
            if inputData:
                self._lastInputTime = now
            elif not latched:
                timeout = self._idleTimeoutBt if self._layout.isBT else self._idleTimeoutUsb
                if now - self._lastInputTime >= timeout:
                    self._releaseDevice(f"no input for {timeout:.0f}s")
                    continue
            # -- flush queued frame
            with self._ioLock:
                dirty = self._frameDirty
                leftEff = self._leftEffect
                rightEff = self._rightEffect
                mL = self._motorL
                mR = self._motorR
                wm = self._writeMotors
                self._frameDirty = False
            if dirty:
                try:
                    written = self._hidDev.write(self._buildReport(leftEff, rightEff, mL, mR, wm))
                except Exception as e:
                    if not latched:
                        self._releaseDevice(f"write error: {e}")
                        continue
                    written = None
                if not latched and written is not None and written <= 0:
                    self._releaseDevice(f"write returned {written}")
                    continue
            # sleep until next frame or watchdog tick
            self._wakeSignal.wait(0.5)
            self._wakeSignal.clear()

    # ── Internal: report building ─────────────────────────────────────────────

    def _buildReport(self, leftEffect, rightEffect,
                     motorL: int = 0, motorR: int = 0, writeMotors: bool = False) -> bytearray:
        return _assembleRawReport(self._layout, leftEffect, rightEffect, motorL, motorR, writeMotors)

    def _safeWrite(self, buf: bytearray) -> None:
        try:
            self._hidDev.write(buf)
        except (OSError, IOError):
            pass

    def _logReconnectMode(self) -> None:
        if hidhide.is_detected() or not self._enableReconnect:
            log.info("Controller handle will stay open after connection")
        else:
            log.info("Controller retry interval: %.0fs", self._reconnectInterval)
