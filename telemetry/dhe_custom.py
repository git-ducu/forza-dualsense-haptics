# ── Forza road-texture + wheelspin trigger effects ──────────────────────────
#
# Converts surface telemetry into DualSense trigger vibration descriptors.
# Called by the runtime engine alongside computeTriggerFrame() to overlay
# road feel onto the L2/R2 resistance baseline.
#
# Returns TriggerEffect | None per function.

from __future__ import annotations

from dsio.trigger.effects import (
    TriggerEffect, clearEffect,
    buildZoneVibration, buildZoneVibrationFromPosition,
    buildSoftZoneVibration, buildSoftZoneVibrationFromPosition,
)
from .triggerHelpers import (
    SLIP_TRUST_SPEED_KMH, STANDSTILL_SPIN_THRESHOLD, DRIVETRAIN_WHEEL_MAP,
    ampToZoneStrength, computeTriggerGain, scaleAmplitude,
)

# ── Local aliases matching internal call conventions ─────────────────────────
_amp_to_strength = ampToZoneStrength
_trigger_gain = computeTriggerGain
_scaled_amp = scaleAmplitude
_TRIGGER_BASE_AMP = 1.3


# Road texture tuning.
ROAD_MIN_SPEED_KMH = 8.0
ROAD_SOFT_THRESHOLD = 0.025
ROAD_TEXTURE_THRESHOLD_ON = 0.055
ROAD_TEXTURE_THRESHOLD_OFF = 0.040
ROAD_LOOSE_THRESHOLD_ON = 0.100
ROAD_LOOSE_THRESHOLD_OFF = 0.075
ROAD_CHUNKY_THRESHOLD_ON = 0.300
ROAD_CHUNKY_THRESHOLD_OFF = 0.220
ROAD_SMOOTH_ATTACK = 0.55
ROAD_SMOOTH_RELEASE = 0.25

# L2 is brake, so keep it weaker than R2.
# V2: raised from 0.48/0.72 -- road texture was barely perceptible at those levels.
LEFT_ROAD_SCALE = 0.62
RIGHT_ROAD_SCALE = 0.85

# Wheelspin tuning. Prefer longitudinal slip_ratio; use combined_slip only as a fallback
# when slip_ratio is also non-trivial, so lateral drift does not constantly masquerade
# as throttle wheelspin.
WHEELSPIN_RATIO_THRESHOLD = 1.0
WHEELSPIN_COMBINED_THRESHOLD = 1.35
WHEELSPIN_RATIO_FALLBACK_THRESHOLD = 0.35
WHEELSPIN_SMOOTH_ATTACK = 0.60
WHEELSPIN_SMOOTH_RELEASE = 0.28
WHEELSPIN_THRESHOLD_ON = 0.080
WHEELSPIN_THRESHOLD_OFF = 0.030
WHEELSPIN_HOLD_S = 0.070

# Tire scrub is lateral tire scrub / understeer-ish texture, not longitudinal
# throttle wheelspin. Keep it weak and optional.
SCRUB_MIN_SPEED_KMH = 25.0
SCRUB_ANGLE_ON = 0.120
SCRUB_ANGLE_OFF = 0.075
SCRUB_SIGNAL_ON = 0.080
SCRUB_SIGNAL_OFF = 0.030
SCRUB_COMBINED_MIN = 0.80
SCRUB_SMOOTH_ATTACK = 0.50
SCRUB_SMOOTH_RELEASE = 0.22
SCRUB_HOLD_S = 0.060

# Road speed scaling. Only amplitude changes; frequency stages stay stable.
ROAD_SPEED_SCALE_LOW = 0.65
ROAD_SPEED_SCALE_MID = 1.00
ROAD_SPEED_SCALE_HIGH = 1.18

# Road smoothing state: (channel, side) -> {"rumble": float, "stage": int}
# Channels are split so trigger-road and body-road calls in the same frame do not
# double-apply smoothing to one shared state.
_road_state = {}
_wheelspin_state = {}
_scrub_state = {"signal": 0.0, "active": False, "until": 0.0}
_r2_pos_state = {"pos": 0.0}
_bump_state = {
    "left": {"signal": 0.0, "active": False, "until": 0.0, "last": 0.0},
    "right": {"signal": 0.0, "active": False, "until": 0.0, "last": 0.0},
}


def reset_custom_state() -> None:
    """Clear trigger effect smoothing state on car/profile change."""
    _road_state.clear()
    _wheelspin_state.clear()
    _scrub_state.update(signal=0.0, active=False, until=0.0)
    _r2_pos_state.update(pos=0.0)
    for side in _bump_state.values():
        side.update(signal=0.0, active=False, until=0.0, last=0.0)


def _tg(t, key: str, default=0):
    """Telemetry getter. Works with current dict-like telemetry."""
    try:
        return t.get(key, default)
    except AttributeError:
        try:
            return t[key]
        except Exception:
            return default


def _enabled(settings, name: str, default: bool = False) -> bool:
    """Feature-flag getter.

    Custom effects default to False if a setting is missing.
    Original DHE flags should pass default=True explicitly.
    """
    return bool(getattr(settings, name, default))


def _scale(s, name: str, default: float = 1.0, lo: float = 0.1, hi: float = 3.0) -> float:
    try:
        v = float(getattr(s, name, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _trigger_vibrate(freq: int, amp: int, wall_zones: int = 2, settings=None, role: str = "master", side: str = ""):
    # Buzz with firm end-wall: lower zones vibrate, top zones stay rigid
    if settings is not None:
        amp = _scaled_amp(settings, amp, role, side)
    if amp <= 0:
        return clearEffect()
    strength = _amp_to_strength(amp)
    w = max(1, min(9, int(wall_zones)))
    zones = [strength] * (10 - w) + [8] * w
    return buildZoneVibration(zones, freq)


def _lerp(a: float, b: float, r: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, float(r)))


def _road_speed_factor(speed_kmh: float) -> float:
    """Mild amplitude scaling: low speed quieter, high speed a bit more present."""
    speed = max(0.0, float(speed_kmh))
    if speed <= 8.0:
        return ROAD_SPEED_SCALE_LOW
    if speed < 45.0:
        return _lerp(ROAD_SPEED_SCALE_LOW, ROAD_SPEED_SCALE_MID, (speed - 8.0) / 37.0)
    if speed < 130.0:
        return _lerp(ROAD_SPEED_SCALE_MID, ROAD_SPEED_SCALE_HIGH, (speed - 45.0) / 85.0)
    return ROAD_SPEED_SCALE_HIGH


def _gear_position_zone(t, s) -> int:
    """Subtle gear/load position for R2 buzz.

    The first positioned build pushed the active zone too far down the trigger,
    which could feel like full throttle before the static wall. Keep the range
    shallow and let gear/load add character instead of moving the buzz too deep.
    """
    accel = int(_tg(t, "accel", 0))
    deadzone = max(1, int(getattr(s, "accel_deadzone", 50)))
    gear = max(1, int(_tg(t, "gear", 1)))
    load = max(0.0, min(1.0, (accel - deadzone) / max(1, 255 - deadzone)))
    gear_bias = 0.0 if gear <= 2 else (0.55 if gear <= 4 else 1.10)
    depth = _scale(s, "adaptive_acceleration_depth", 0.30, 0.0, 1.5)
    # depth=0 keeps the active zone near the top; higher depth lets gear/load move it deeper.
    target_zone = max(0, min(4, int(round((load * 2.2 + gear_bias) * depth))))

    prev = float(_r2_pos_state.get("pos_zone", 0.0))
    alpha = 0.34 if target_zone >= prev else 0.20
    pos_zone = prev + (target_zone - prev) * alpha
    _r2_pos_state["pos_zone"] = pos_zone
    return max(0, min(4, int(round(pos_zone))))


def _r2_throttle_min_strength(t, s) -> int:
    """Throttle-position-based minimum zone strength for R2 vibration effects.

    When R2 vibration (road texture, wheelspin, scrub) replaces the throttle
    rigid ramp, the trigger can feel limp because vibration zone strengths are
    often only 2-3/8.  This adds a floor: the deeper the throttle is pressed,
    the stronger the minimum buzz so the pedal always has resistance feel.
    """
    if not _enabled(s, "enable_throttle_resistance", True):
        return 0
    # If R2 trigger gain is 0, no minimum strength
    r2_gain = float(getattr(s, "trigger_r2_gain", 1.0))
    master_gain = float(getattr(s, "trigger_master_gain", 1.0))
    if r2_gain <= 0.0 or master_gain <= 0.0:
        return 0
    accel = int(_tg(t, "accel", 0))
    deadzone = max(1, int(getattr(s, "accel_deadzone", 50)))
    if accel < deadzone:
        return 0
    throttle_pct = min(1.0, (accel - deadzone) / max(1, 255 - deadzone))
    # Aggressive floor: R2 always feels resistive when pressed.
    # 0% → 3, 33% → 4, 66% → 5, 100% → 6
    return max(3, min(6, int(3 + throttle_pct * 3)))


def _r2_vibrate(t, s, freq: int, amp: int):
    # R2 buzz: gear/load-positioned soft zone or standard zone vibration
    wall_zones = int(getattr(s, "wall_zones", 2))
    throttle_min = _r2_throttle_min_strength(t, s)
    if _enabled(s, "enable_trigger_positioned_vibration", False):
        start_zone = _gear_position_zone(t, s)
        amp = _scaled_amp(s, amp, side="r2")
        strength = max(throttle_min, _amp_to_strength(amp))
        return buildSoftZoneVibrationFromPosition(start_zone, strength, freq, topBoost=1)
    amp_s = _scaled_amp(s, amp, side="r2")
    strength = max(throttle_min, _amp_to_strength(amp_s))
    w = max(1, min(9, int(wall_zones)))
    zones = [strength] * (10 - w) + [8] * w
    return buildZoneVibration(zones, freq)


def _r2_texture_vibrate(t, s, freq: int, amp: int):
    """Softer R2 buzz for informational textures that must not feel like a lockout.

    Uses throttle minimum so even soft textures have base pedal resistance.
    """
    throttle_min = _r2_throttle_min_strength(t, s)
    if _enabled(s, "enable_trigger_positioned_vibration", False):
        amp = _scaled_amp(s, amp, side="r2")
        strength = max(throttle_min, _amp_to_strength(amp))
        return buildSoftZoneVibrationFromPosition(_gear_position_zone(t, s), strength, freq, topBoost=0)
    amp = _scaled_amp(s, amp, side="r2")
    strength = max(throttle_min, _amp_to_strength(amp))
    return buildSoftZoneVibration(strength, freq, topBoost=0)


def _l2_vibrate(s, freq: int, amp: int):
    # L2 buzz with end-wall preserved for brake feel
    return _trigger_vibrate(freq, amp, int(getattr(s, "wall_zones", 2)), settings=s, side="l2")



def _side_wheels(side: str):
    return ("fl", "rl") if side == "left" else ("fr", "rr")


def _driven_wheels(t):
    return DRIVETRAIN_WHEEL_MAP.get(int(_tg(t, "drive_train", 2)), ("fl", "fr", "rl", "rr"))


def _side_surface_rumble(t, side: str) -> float:
    return max(abs(float(_tg(t, f"surface_rumble_{w}", 0.0))) for w in _side_wheels(side))


def _side_on_kerb(t, side: str) -> bool:
    return any(_tg(t, f"wheel_on_rumble_strip_{w}", 0) > 0 for w in _side_wheels(side))


def _side_in_puddle(t, side: str) -> bool:
    return any(_tg(t, f"wheel_in_puddle_{w}", 0) > 0 for w in _side_wheels(side))


def _road_stage(smoothed: float, prev_stage: int, on_kerb: bool) -> int:
    """Return road intensity stage with hysteresis.

    0 = none, 1 = asphalt texture, 2 = dirt/loose, 3 = kerb/gravel/chunky.
    """
    if on_kerb:
        return 3
    if smoothed >= ROAD_CHUNKY_THRESHOLD_ON or (prev_stage >= 3 and smoothed >= ROAD_CHUNKY_THRESHOLD_OFF):
        return 3
    if smoothed >= ROAD_LOOSE_THRESHOLD_ON or (prev_stage >= 2 and smoothed >= ROAD_LOOSE_THRESHOLD_OFF):
        return 2
    if smoothed >= ROAD_TEXTURE_THRESHOLD_ON or (prev_stage >= 1 and smoothed >= ROAD_TEXTURE_THRESHOLD_OFF):
        return 1
    return 0


def _smooth_road(channel: str, side: str, raw: float, on_kerb: bool) -> tuple[float, int]:
    key = (channel, side)
    st = _road_state.setdefault(key, {"rumble": 0.0, "stage": 0})
    prev = float(st.get("rumble", 0.0))
    alpha = ROAD_SMOOTH_ATTACK if raw >= prev else ROAD_SMOOTH_RELEASE
    smoothed = prev + (raw - prev) * alpha
    stage = _road_stage(smoothed, int(st.get("stage", 0)), on_kerb)
    st["rumble"] = smoothed
    st["stage"] = stage
    return smoothed, stage


def _reset_road(channel: str, side: str) -> None:
    st = _road_state.setdefault((channel, side), {"rumble": 0.0, "stage": 0})
    st["rumble"] = 0.0
    st["stage"] = 0


def _road_buzz_values(
    t,
    s,
    side: str,
    scale: float,
    require_trigger_enabled: bool = True,
    channel: str = "trigger",
    now: float | None = None,
):
    if require_trigger_enabled:
        if side == "left" and not _enabled(s, "enable_left_road_texture", False):
            return None
        if side == "right" and not _enabled(s, "enable_right_road_texture", False):
            return None

    speed_kmh = float(_tg(t, "speed", 0.0))
    if speed_kmh < ROAD_MIN_SPEED_KMH:
        _reset_road(channel, side)
        return None

    strength_scale = _scale(s, "road_texture_strength", 1.0, 0.25, 2.5)
    if channel == "trigger":
        side_attr = "left_road_strength" if side == "left" else "right_road_strength"
        strength_scale *= _scale(s, side_attr, 1.0 if side == "right" else 0.75, 0.0, 2.0)
    speed_scale = _road_speed_factor(speed_kmh)

    # Large road impact / landing is now fused into road texture instead of being
    # a separate trigger toggle. It only runs when the corresponding road texture
    # path is active, so it behaves like a rare impact spice on top of road feel.
    if channel == "trigger" and now is not None:
        bump = _suspension_bump_values(t, s, side, now)
        if bump is not None:
            b_freq, b_amp = bump
            # Keep it under the road texture strength sliders.
            b_amp = int(b_amp * strength_scale * speed_scale)
            if b_amp > 0:
                return b_freq, min(255, max(1, b_amp))

    raw_rumble = _side_surface_rumble(t, side)
    on_kerb = _side_on_kerb(t, side)
    in_puddle = _side_in_puddle(t, side)

    # Puddles are sharp one-off texture, not a low mud rumble.
    if in_puddle:
        _smooth_road(channel, side, max(raw_rumble, ROAD_TEXTURE_THRESHOLD_ON), on_kerb)
        amp = max(8, int(34 * scale * speed_scale * strength_scale))
        return 150, min(255, amp)

    if not on_kerb and raw_rumble < ROAD_SOFT_THRESHOLD:
        smoothed, stage = _smooth_road(channel, side, 0.0, False)
    else:
        smoothed, stage = _smooth_road(channel, side, raw_rumble, on_kerb)

    if stage <= 0:
        return None

    # Rumble strip / kerb: keep it chunky and slightly patterned instead of a flat buzz.
    if on_kerb:
        # Speed-based kerb pulse: slow kerb = thump-thump, fast kerb = rapid rattle.
        period = _lerp(0.105, 0.035, min(1.0, speed_kmh / 160.0))
        phase = ((now or 0.0) / period) % 1.0
        gate = 1.00 if phase < 0.58 else 0.50
        freq = int(_lerp(30, 50, min(1.0, speed_kmh / 160.0)))
        amp = int((100 + min(1.0, smoothed) * 145) * scale * speed_scale * strength_scale * gate)
        return freq, min(160, max(1, amp))

    # Kerb / gravel / rocks: chunky thump.
    # L2 offroad freq raised from 18→55Hz so it feels like vibration, not a lock.
    if stage >= 3:
        amp = int((90 + min(1.0, smoothed) * 145) * scale * speed_scale * strength_scale)
        amp = min(180, max(1, amp))  # cap to prevent rigid-like lock on L2
        return 55, amp

    # Dirt / loose surface: low rumble.
    # L2 offroad freq raised from 38→65Hz -- same reason as above.
    if stage == 2:
        amp = int((62 + smoothed * 160) * scale * speed_scale * strength_scale)
        amp = min(160, max(1, amp))
        return 65, amp

    # Low asphalt texture: thin, weaker high-frequency texture.
    # V2: raised base from 24 to 36 so asphalt is actually perceptible.
    amp = int((36 + smoothed * 130) * scale * speed_scale * strength_scale)
    return 88, min(255, max(1, amp))

def _wheelspin_signal_mode(t, wheels, s=None):
    """Return (normalized wheelspin signal 0..1, mode) or (None, None)."""
    sens = _scale(s, "wheelspin_sensitivity", 1.0, 0.35, 2.5) if s is not None else 1.0
    ratio_threshold = WHEELSPIN_RATIO_THRESHOLD / sens
    combined_threshold = WHEELSPIN_COMBINED_THRESHOLD / max(0.65, sens)
    fallback_threshold = WHEELSPIN_RATIO_FALLBACK_THRESHOLD / max(0.65, sens)
    speed = float(_tg(t, "speed", 0.0))
    if speed < SLIP_TRUST_SPEED_KMH:
        spin = max(abs(float(_tg(t, f"wheel_rotation_speed_{w}", 0.0))) for w in wheels)
        if spin < STANDSTILL_SPIN_THRESHOLD:
            return None, None
        return min(1.0, spin / max(STANDSTILL_SPIN_THRESHOLD * 3.0, 1.0)), "burnout"

    ratio = max(abs(float(_tg(t, f"tire_slip_ratio_{w}", 0.0))) for w in wheels)
    if ratio >= ratio_threshold:
        return min(1.0, (ratio - ratio_threshold) / max(0.35, 2.5 / sens)), "ratio"

    combined = max(abs(float(_tg(t, f"tire_combined_slip_{w}", 0.0))) for w in wheels)
    if ratio >= fallback_threshold and combined >= combined_threshold:
        return min(1.0, (combined - combined_threshold) / max(0.35, 2.5 / sens)), "combined"

    return None, None


def _wheelspin_signal(t, wheels, s=None):
    signal, _mode = _wheelspin_signal_mode(t, wheels, s)
    return signal


def _reset_gate(state: dict) -> None:
    state["signal"] = 0.0
    state["active"] = False
    state["until"] = 0.0


def _gate_signal(
    state: dict,
    raw_signal,
    now: float,
    attack: float,
    release: float,
    on_threshold: float,
    off_threshold: float,
    hold_s: float,
):
    """Common attack/release + hysteresis + short hold gate for noisy telemetry."""
    raw = 0.0 if raw_signal is None else max(0.0, min(1.0, float(raw_signal)))
    prev = float(state.get("signal", 0.0))
    alpha = attack if raw >= prev else release
    signal = prev + (raw - prev) * alpha

    was_active = bool(state.get("active", False))
    active = signal >= on_threshold or (was_active and signal >= off_threshold)

    if raw_signal is not None and signal >= on_threshold:
        state["until"] = now + hold_s
    if was_active and now < float(state.get("until", 0.0)):
        active = True

    state["signal"] = signal
    state["active"] = active
    if not active:
        return None
    return max(signal, on_threshold)


def _reset_wheelspin(channel: str) -> None:
    st = _wheelspin_state.setdefault(channel, {"signal": 0.0, "active": False, "until": 0.0})
    _reset_gate(st)


def _smooth_wheelspin(channel: str, raw_signal, now: float, s=None):
    st = _wheelspin_state.setdefault(channel, {"signal": 0.0, "active": False, "until": 0.0})
    hold_s = max(0.0, min(0.250, float(getattr(s, "wheelspin_hold_ms", WHEELSPIN_HOLD_S * 1000.0))) / 1000.0) if s is not None else WHEELSPIN_HOLD_S
    return _gate_signal(
        st, raw_signal, now,
        WHEELSPIN_SMOOTH_ATTACK, WHEELSPIN_SMOOTH_RELEASE,
        WHEELSPIN_THRESHOLD_ON, WHEELSPIN_THRESHOLD_OFF,
        hold_s,
    )


def _wheelspin_values(t, s, wheels=None, now: float | None = None, channel: str = "r2"):
    if not _enabled(s, "enable_wheelspin_buzz", True):
        _reset_wheelspin(channel)
        return None
    if int(_tg(t, "accel", 0)) < int(getattr(s, "accel_deadzone", 50)):
        _reset_wheelspin(channel)
        return None

    wheels = tuple(wheels or _driven_wheels(t))
    if not wheels:
        _reset_wheelspin(channel)
        return None

    raw_signal, mode = _wheelspin_signal_mode(t, wheels, s)
    if now is None:
        signal = raw_signal
    else:
        signal = _smooth_wheelspin(channel, raw_signal, now, s)
    if signal is None:
        return None

    base = max(1, int(getattr(s, "wheelspin_amp", 15)))
    speed = float(_tg(t, "speed", 0.0))
    drivetrain = int(_tg(t, "drive_train", 2))

    # Low-speed burnout/start wheelspin gets its own lower, thicker pattern.
    if mode == "burnout" or speed < SLIP_TRUST_SPEED_KMH:
        freq = int(42 + signal * 22)
        amp = int(base * (3.5 + signal * 5.0))
    else:
        # Drivetrain character: FWD = thin/high, RWD = chunky/low, AWD = middle.
        # V2: raised multipliers so amp reaches 48+ (strength 3+) during normal wheelspin.
        # Old AWD: 8*(1.15+0.5*1.85)=16 → strength 1. New: 15*(1.6+0.5*2.4)=42 → strength 2-3.
        if drivetrain == 0:      # FWD
            freq = int(138 + signal * 20)
            amp = int(base * (1.3 + signal * 2.0))
        elif drivetrain == 1:    # RWD
            freq = int(82 + signal * 34)
            amp = int(base * (1.8 + signal * 2.8))
        else:                    # AWD / unknown
            freq = int(112 + signal * 30)
            amp = int(base * (1.6 + signal * 2.4))

        # High-speed wheelspin gets a little sharper; do not overdo amplitude.
        if speed > 120.0:
            freq = min(170, int(freq + min(20, (speed - 120.0) / 5.0)))

    # Engine load makes throttle slip feel more convincing, but keep it mild
    # so wild car telemetry does not dominate the tire signal.
    torque = abs(float(_tg(t, "torque", 0.0)))
    power = abs(float(_tg(t, "power", 0.0)))
    load_boost = min(0.25, min(1.0, torque / 850.0) * 0.14 + min(1.0, power / 420000.0) * 0.11)
    amp = int(amp * (1.0 + load_boost))

    # Water: sharp but weaker, like traction suddenly washing away.
    if any(_tg(t, f"wheel_in_puddle_{w}", 0) > 0 for w in wheels):
        return 132, max(1, int(amp * 0.55 * _trigger_gain(s, "wheelspin", "r2")))

    rumble = max(abs(float(_tg(t, f"surface_rumble_{w}", 0.0))) for w in wheels)
    if rumble > 0.30:
        # Offroad high rumble -- DualSense vibrate below ~80Hz creates audible
        # mechanical clatter. Solution:
        # 1. Raise freq to 100-130Hz range (smooth texture feel)
        # 2. Cap amplitude much lower (max 110) to prevent hardware banging
        # 3. Apply throttle-proportional damping: full throttle gets LESS amp
        #    because 100% accel + high rumble = worst clatter scenario.
        smooth_rumble = min(1.0, (rumble - 0.30) / 0.50)
        freq_off = int(100 + smooth_rumble * 30)   # 100-130Hz: smooth, no bang
        # Throttle damping: higher throttle = lower amp (prevents full-accel clatter)
        accel_byte = int(_tg(t, "accel", 0))
        throttle_damp = 1.0 - min(0.40, max(0.0, (accel_byte - 128) / 127.0) * 0.40)
        amp_off = int(amp * (0.8 + smooth_rumble * 0.20) * throttle_damp)
        amp_off = min(110, int(amp_off * _trigger_gain(s, "wheelspin", "r2")))  # hard cap 110
        return freq_off, max(1, amp_off)
    if rumble > 0.10:
        # Moderate rumble: textured but not clattery. Freq 90-105Hz.
        smooth_rumble = min(1.0, (rumble - 0.10) / 0.20)
        freq_off = int(90 + smooth_rumble * 15)  # 90-105Hz
        amp_off = int(amp * (0.85 + smooth_rumble * 0.15))
        amp_off = min(130, int(amp_off * _trigger_gain(s, "wheelspin", "r2")))
        return freq_off, max(1, amp_off)

    return max(1, min(180, freq)), min(255, max(1, int(amp * _trigger_gain(s, "wheelspin", "r2"))))


def _r2_road_allowed(t, s) -> bool:
    accel = int(_tg(t, "accel", 0))
    deadzone = max(1, int(getattr(s, "accel_deadzone", 50)))
    return accel >= max(1, int(deadzone * 0.50))


def _r2_road_accel_scale(t, s) -> float:
    accel = int(_tg(t, "accel", 0))
    deadzone = max(1, int(getattr(s, "accel_deadzone", 50)))
    start = max(1, int(deadzone * 0.50))
    if accel <= start:
        return 0.0
    if accel < deadzone:
        return 0.45
    return _lerp(0.65, 1.0, (accel - deadzone) / max(1, 170 - deadzone))

def left_road_buzz(t, s, now):
    """L2 left-side road texture.

    This intentionally does nothing while braking, so it does not mask ABS,
    brake wall, or brake stiffness.
    """
    if not _enabled(s, "enable_left_road_texture", False):
        return None

    if int(_tg(t, "brake", 0)) >= max(1, int(getattr(s, "brake_deadzone", 50))):
        return None

    road = _road_buzz_values(t, s, "left", LEFT_ROAD_SCALE, channel="trigger", now=now)
    if road is None:
        return None

    freq, amp = road
    return _l2_vibrate(s, freq, amp)


def right_wheelspin_buzz(t, s, now):
    """R2 wheelspin-only buzz using guarded slip_ratio-first detection."""
    spin = _wheelspin_values(t, s, now=now, channel="r2")
    if spin is None:
        return None
    freq, amp = spin
    # Offroad surfaces use soft vibration (texture_vibrate) to avoid
    # mechanical clatter. Lower threshold (0.08) catches more offroad.
    wheels = tuple(_driven_wheels(t))
    rumble = max(abs(float(_tg(t, f"surface_rumble_{w}", 0.0))) for w in wheels) if wheels else 0.0
    if rumble > 0.08:
        return _r2_texture_vibrate(t, s, freq, amp)
    return _r2_vibrate(t, s, freq, amp)


def right_wheelspin_road_buzz(t, s, now):
    """R2 wheelspin + right-side road texture mixer.

    - Wheelspin wins and keeps its drivetrain-specific pattern.
    - R2 road requires at least a light accelerator press, so the throttle trigger
      does not buzz while completely off-throttle.
    - Road texture is mixed as small amplitude spice under wheelspin.
    """
    if not _enabled(s, "enable_right_road_texture", False):
        return None

    spin = _wheelspin_values(t, s, now=now, channel="r2")
    road = None
    if _r2_road_allowed(t, s):
        road = _road_buzz_values(t, s, "right", RIGHT_ROAD_SCALE, channel="trigger", now=now)
        if road is not None:
            r_freq, r_amp = road
            road_scale = _r2_road_accel_scale(t, s)
            road = (r_freq, max(1, int(r_amp * road_scale))) if road_scale > 0.0 else None

    if spin is None and road is None:
        return None

    if spin is not None:
        freq, amp = spin
        if road is not None:
            amp = min(255, int(amp + road[1] * 0.30))
        return _r2_vibrate(t, s, freq, amp)

    freq, amp = road
    return _r2_vibrate(t, s, freq, amp)


def right_road_buzz(t, s, now, amp_scale: float = 1.0):
    """R2 right-side road texture only, used by priority modes."""
    if not _enabled(s, "enable_right_road_texture", False):
        return None
    if not _r2_road_allowed(t, s):
        return None
    road = _road_buzz_values(t, s, "right", RIGHT_ROAD_SCALE, channel="trigger", now=now)
    if road is None:
        return None
    freq, amp = road
    road_scale = _r2_road_accel_scale(t, s) * max(0.0, float(amp_scale))
    amp = max(1, int(amp * road_scale)) if road_scale > 0.0 else 0
    if amp <= 0:
        return None
    return _r2_vibrate(t, s, freq, amp)

def _scrub_signal(t, s=None):
    """Return (signal, kind) for lateral tire scrub: under/over/neutral."""
    sens = _scale(s, "tire_scrub_sensitivity", 1.0, 0.35, 2.5) if s is not None else 1.0
    angle_on = SCRUB_ANGLE_ON / sens
    combined_min = SCRUB_COMBINED_MIN / max(0.65, sens)
    speed = float(_tg(t, "speed", 0.0))
    if speed < SCRUB_MIN_SPEED_KMH:
        return None, None

    wheels = ("fl", "fr", "rl", "rr")
    # Wheelspin owns longitudinal slip. Scrub only handles lateral/combined slide.
    ratio = max(abs(float(_tg(t, f"tire_slip_ratio_{w}", 0.0))) for w in wheels)
    if ratio >= WHEELSPIN_RATIO_THRESHOLD:
        return None, None

    front_angle = max(abs(float(_tg(t, f"tire_slip_angle_{w}", 0.0))) for w in ("fl", "fr"))
    rear_angle = max(abs(float(_tg(t, f"tire_slip_angle_{w}", 0.0))) for w in ("rl", "rr"))
    front_combined = max(abs(float(_tg(t, f"tire_combined_slip_{w}", 0.0))) for w in ("fl", "fr"))
    rear_combined = max(abs(float(_tg(t, f"tire_combined_slip_{w}", 0.0))) for w in ("rl", "rr"))

    front_signal = max(
        max(0.0, (front_angle - angle_on) / max(0.18, 0.55 / sens)),
        max(0.0, (front_combined - combined_min) / max(0.45, 2.0 / sens)) * 0.70,
    )
    rear_signal = max(
        max(0.0, (rear_angle - angle_on) / max(0.18, 0.55 / sens)),
        max(0.0, (rear_combined - combined_min) / max(0.45, 2.0 / sens)) * 0.70,
    )

    signal = min(1.0, max(front_signal, rear_signal))
    if signal <= 0.0:
        return None, None

    if front_signal > rear_signal * 1.18:
        kind = "under"
    elif rear_signal > front_signal * 1.18:
        kind = "over"
    else:
        kind = "neutral"
    return signal, kind


def _smooth_scrub(raw_signal, kind, now: float, s=None):
    hold_s = max(0.0, min(0.250, float(getattr(s, "tire_scrub_hold_ms", SCRUB_HOLD_S * 1000.0))) / 1000.0) if s is not None else SCRUB_HOLD_S
    signal = _gate_signal(
        _scrub_state, raw_signal, now,
        SCRUB_SMOOTH_ATTACK, SCRUB_SMOOTH_RELEASE,
        SCRUB_SIGNAL_ON, SCRUB_SIGNAL_OFF,
        hold_s,
    )
    if kind is not None:
        _scrub_state["kind"] = kind
    if signal is None:
        return None, None
    return signal, _scrub_state.get("kind", "neutral")


def right_tire_scrub_buzz(t, s, now):
    """Optional R2 lateral tire scrub with understeer/oversteer split."""
    if not _enabled(s, "enable_tire_scrub_buzz", False):
        _reset_gate(_scrub_state)
        _scrub_state["kind"] = "neutral"
        return None
    if int(_tg(t, "accel", 0)) < int(getattr(s, "accel_deadzone", 50)):
        return None

    raw_signal, raw_kind = _scrub_signal(t, s)
    signal, kind = _smooth_scrub(raw_signal, raw_kind, now, s)
    if signal is None:
        return None

    base = max(1, int(getattr(s, "wheelspin_amp", 15)))

    # Scrub is an advisory texture, not a throttle lockout. The first deep build
    # made heavy off-road oversteer feel like a hard "do not press" latch.
    # Keep tarmac scrub readable, but heavily soften rough/off-road scrub.
    wheels = ("fl", "fr", "rl", "rr")
    rough = max(abs(float(_tg(t, f"surface_rumble_{w}", 0.0))) for w in wheels)
    on_rough = rough > 0.10 or any(_tg(t, f"wheel_on_rumble_strip_{w}", 0) > 0 for w in wheels)
    in_puddle = any(_tg(t, f"wheel_in_puddle_{w}", 0) > 0 for w in wheels)
    road_strength = _scale(s, "tire_scrub_road_strength", 1.0, 0.0, 2.0)
    offroad_strength = _scale(s, "tire_scrub_offroad_strength", 0.35, 0.0, 2.0)
    terrain_scale = road_strength
    if in_puddle:
        terrain_scale = offroad_strength * 0.55
    elif rough > 0.30:
        terrain_scale = offroad_strength * 0.70
    elif on_rough:
        terrain_scale = offroad_strength

    if on_rough or in_puddle:
        signal = min(signal, 0.55)

    if kind == "under":
        freq = int(120 + signal * 24)   # front push: thin/high
        amp_scale = 0.48 + signal * 0.62
    elif kind == "over":
        freq = int(64 + signal * 22)    # rear slide: lower/chunkier
        amp_scale = 0.58 + signal * 0.82
    else:
        freq = int(92 + signal * 22)
        amp_scale = 0.52 + signal * 0.70

    amp = max(1, int(base * amp_scale * terrain_scale))
    # Hard cap because scrub should never feel like the trigger is locking.
    max_force = _scale(s, "tire_scrub_max_force", 0.60, 0.10, 1.0)
    cap = int(160 * max_force)
    if on_rough or in_puddle:
        cap = min(cap, int(120 * max_force))
    amp = min(max(1, cap), amp)
    return _r2_texture_vibrate(t, s, freq, amp)


def _suspension_bump_values(t, s, side: str, now: float):
    """Short trigger buzz for large suspension compression / landing events."""
    speed = float(_tg(t, "speed", 0.0))
    if speed < 12.0:
        return None

    wheels = _side_wheels(side)
    # Prefer normalized suspension travel when available; fallback to meters.
    vals = [abs(float(_tg(t, f"norm_suspension_travel_{w}", 0.0))) for w in wheels]
    if max(vals) <= 0.0:
        vals = [min(1.0, abs(float(_tg(t, f"suspension_travel_meters_{w}", 0.0))) / 0.20) for w in wheels]
    current = max(vals)
    st = _bump_state[side]
    last = float(st.get("last", current))
    delta = abs(current - last)
    st["last"] = current

    sens = _scale(s, "suspension_bump_sensitivity", 1.0, 0.35, 2.5)
    raw = 0.0
    compression_threshold = 0.92 / min(1.35, max(0.75, sens))
    delta_threshold = 0.18 / min(1.45, max(0.70, sens))
    if current >= compression_threshold:
        raw = max(raw, (current - compression_threshold) / max(0.12, 0.20 / sens))
    if delta >= delta_threshold:
        raw = max(raw, (delta - delta_threshold) / max(0.20, 0.42 / sens))
    raw = min(1.0, raw * sens)

    # Avoid double-hitting ordinary rough terrain: bump is for large compression/landing only.
    rough = max(abs(float(_tg(t, f"surface_rumble_{w}", 0.0))) for w in wheels)
    if rough > 0.30 and raw < 0.45:
        raw *= 0.35
    elif rough > 0.10 and raw < 0.30:
        raw *= 0.60

    signal = _gate_signal(st, raw if raw > 0 else None, now, 0.72, 0.30, 0.10, 0.035, 0.055)
    if signal is None:
        return None

    strength = _scale(s, "suspension_bump_strength", 0.80, 0.0, 2.0)
    freq = int(50 + min(1.0, speed / 160.0) * 20)
    amp = min(180, int((32 + signal * 110) * strength))
    return freq, max(1, amp)


def left_suspension_bump_buzz(t, s, now):
    bump = _suspension_bump_values(t, s, "left", now)
    if bump is None:
        return None
    return _l2_vibrate(s, *bump)


def right_suspension_bump_buzz(t, s, now):
    bump = _suspension_bump_values(t, s, "right", now)
    if bump is None:
        return None
    return _r2_vibrate(t, s, *bump)
