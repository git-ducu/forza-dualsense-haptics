"""Factory for DualSense backend — isolated to avoid double-import of app.py."""
from config.settings import Settings
from dsio.device import DualSenseWriter


def make_backend(s: Settings, enable_startup_pulse: bool | None = None) -> DualSenseWriter:
    """Build the DualSense HID backend from settings."""
    if enable_startup_pulse is None:
        enable_startup_pulse = s.enable_startup_pulse
    return DualSenseWriter(
        startupPulseForce=s.startup_pulse_force,
        enableStartupPulse=enable_startup_pulse,
        reconnectIntervalSec=s.reconnect_interval_s,
        enableReconnect=s.enable_reconnect,
        lockedSerial=s.controller_lock_serial,
    )
