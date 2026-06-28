# ── Shared trigger constants and gain math ──────────────────────────────────
#
# Forza-specific helpers used by triggerMap.py and roadTexture.py.
# Factored out to avoid circular imports between the two.

from __future__ import annotations

# Below this speed, tyre slip_ratio degenerates; fall back to wheel angular velocity
SLIP_TRUST_SPEED_KMH = 5.0
# Wheel angular velocity (rad/s) that qualifies as standing-start wheelspin
STANDSTILL_SPIN_THRESHOLD = 30.0
# Forza drive_train enum → powered axle wheel positions
DRIVETRAIN_WHEEL_MAP = {0: ("fl", "fr"), 1: ("rl", "rr"), 2: ("fl", "fr", "rl", "rr")}

# Internal trigger amplitude multiplier (compensates DS hardware attenuation)
_TRIGGER_BASE_AMP = 1.3


def ampToZoneStrength(ampByte: int) -> int:
    # Map raw 0..255 vibration amplitude to DualSense zone strength 1..8
    return max(1, min(8, (max(0, int(ampByte)) // 18) + 1))


def computeTriggerGain(settings, role: str = "master", side: str = "") -> float:
    # Unified trigger gain: master × side × role sub-gain × base amp
    try:
        master = float(getattr(settings, "trigger_master_gain", 1.0))
    except (TypeError, ValueError):
        master = 1.0
    if master <= 0.0:
        return 0.0
    # per-trigger individual gain
    if side == "l2":
        l2 = float(getattr(settings, "trigger_l2_gain", 1.0))
        if l2 <= 0.0:
            return 0.0
        master *= min(2.0, l2)
    elif side == "r2":
        r2 = float(getattr(settings, "trigger_r2_gain", 1.0))
        if r2 <= 0.0:
            return 0.0
        master *= min(2.0, r2)
    if role == "shift":
        sub = float(getattr(settings, "trigger_shift_kick_gain", 1.0))
        if sub <= 0.0:
            return 0.0
        master *= sub
    elif role == "abs":
        sub = float(getattr(settings, "trigger_abs_gain", 1.0))
        if sub <= 0.0:
            return 0.0
        master *= sub
        master *= float(getattr(settings, "trigger_grip_chatter_gain", 1.0))
    elif role in {"wheelspin", "grip"}:
        sub = float(getattr(settings, "trigger_wheelspin_gain", 1.0))
        if sub <= 0.0:
            return 0.0
        master *= sub
        master *= float(getattr(settings, "trigger_grip_chatter_gain", 1.0))
    return min(3.25, master * _TRIGGER_BASE_AMP)


def scaleAmplitude(settings, amp: int, role: str = "master", side: str = "") -> int:
    # Apply gain chain to raw amplitude byte
    gain = computeTriggerGain(settings, role, side)
    if gain <= 0.0:
        return 0
    return max(1, min(255, int(max(0, int(amp)) * gain)))
