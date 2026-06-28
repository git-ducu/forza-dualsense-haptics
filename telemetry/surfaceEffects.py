"""Forza telemetry -> DualSense audio-haptic texture state.

Improved haptic mapping:
- stronger Forza output scale so master gain can stay around 0.35..0.45
- floor values for detected kerb/gravel/collision so telemetry does not log silently
- wheel-specific spatial events for L/R and front/rear frequency shaping
- short event envelopes for collision, bump and puddle
- tunable hold/decay, trigger-haptic ducking, and stronger spatial shaping
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .haptics.audioEngine import HapticState

WHEELS = ("fl", "fr", "rl", "rr")
SIDES = {
    "left": ("fl", "rl"),
    "right": ("fr", "rr"),
}
DRIVEN = {
    0: ("fl", "fr"),
    1: ("rl", "rr"),
    2: ("fl", "fr", "rl", "rr"),
}


@dataclass
class SurfaceContext:
    left_label: str = "unknown"
    right_label: str = "unknown"
    dominant: str = "unknown"
    confidence: float = 0.0
    transition: str = ""
    ice_l: float = 0.0
    ice_r: float = 0.0
    packed_snow_l: float = 0.0
    packed_snow_r: float = 0.0
    loose_snow_l: float = 0.0
    loose_snow_r: float = 0.0
    slush_l: float = 0.0
    slush_r: float = 0.0
    sand_l: float = 0.0
    sand_r: float = 0.0
    thin_water_l: float = 0.0
    thin_water_r: float = 0.0
    deep_water_l: float = 0.0
    deep_water_r: float = 0.0
    wet_tail_l: float = 0.0
    wet_tail_r: float = 0.0
    transition_l: float = 0.0
    transition_r: float = 0.0


@dataclass
class VehicleContext:
    understeer_l: float = 0.0
    understeer_r: float = 0.0
    oversteer_l: float = 0.0
    oversteer_r: float = 0.0
    four_wheel_slide: float = 0.0
    slide_chaos_l: float = 0.0
    slide_chaos_r: float = 0.0
    rear_breakaway_l: float = 0.0
    rear_breakaway_r: float = 0.0
    side_scrub_edge_l: float = 0.0
    side_scrub_edge_r: float = 0.0
    tire_scrub_l: float = 0.0
    tire_scrub_r: float = 0.0
    tire_smear_l: float = 0.0
    tire_smear_r: float = 0.0
    slip_sizzle_l: float = 0.0
    slip_sizzle_r: float = 0.0
    asphalt_drift_l: float = 0.0
    asphalt_drift_r: float = 0.0
    offroad_drift_l: float = 0.0
    offroad_drift_r: float = 0.0
    drift_confidence: float = 0.0
    airborne: float = 0.0
    landing: float = 0.0
    bottom_out: float = 0.0
    tire_temp_grip: float = 1.0
    class_character: float = 0.0


@dataclass
class EventContext:
    event_l: float = 0.0
    event_r: float = 0.0
    continuous_duck_l: float = 1.0
    continuous_duck_r: float = 1.0
    vehicle_duck_l: float = 1.0
    vehicle_duck_r: float = 1.0


def reset_haptic_state(reason: str = "manual") -> None:
    """Clear haptic classifier memory without touching trigger code.

    This is intentionally local to audio haptics. It prevents stale wetness,
    rear echoes, launch/shift envelopes or surface memory from leaking across
    car changes, menu pauses, profile swaps or telemetry loss.
    """
    keep = {"last_now", "dt"}
    for k in list(_state.keys()):
        if k in keep:
            continue
        v = _state[k]
        if isinstance(v, (int, float)) or v is None:
            _state[k] = None if k.startswith("last_susp_") else 0.0
        elif isinstance(v, str):
            _state[k] = ""
    _state["last_reset_reason"] = str(reason)
    # Also clear trigger-side smoothing state (road/wheelspin/bump/scrub)
    from . import dhe_custom
    dhe_custom.reset_custom_state()


_state = {
    "road_l": 0.0, "road_r": 0.0,
    "gravel_l": 0.0, "gravel_r": 0.0,
    "wheel_l": 0.0, "wheel_r": 0.0,
    "scrub_l": 0.0, "scrub_r": 0.0,
    "last_susp_fl": None, "last_susp_fr": None, "last_susp_rl": None, "last_susp_rr": None,
    "collision_until": 0.0, "collision_amp": 0.0, "collision_pan": 0.0,
    "weight_l": 0.0, "weight_r": 0.0,
    "last_lat_g": 0.0, "weight_pulse_until": 0.0, "weight_pulse_side": 0.0, "weight_pulse_amp": 0.0,
    "asphalt_grip_l": 0.0, "asphalt_grip_r": 0.0,
    "slide_l": 0.0, "slide_r": 0.0,
    "last_slide_sign": 0.0, "slide_pulse_until": 0.0, "slide_pulse_side": 0.0, "slide_pulse_amp": 0.0,
    "slide_chaos_l": 0.0, "slide_chaos_r": 0.0,
    "rear_breakaway_l": 0.0, "rear_breakaway_r": 0.0,
    "side_scrub_edge_l": 0.0, "side_scrub_edge_r": 0.0,
    "tire_scrub_l": 0.0, "tire_scrub_r": 0.0,
    "tire_smear_l": 0.0, "tire_smear_r": 0.0,
    "slip_sizzle_l": 0.0, "slip_sizzle_r": 0.0,
    "asphalt_drift_l": 0.0, "asphalt_drift_r": 0.0,
    "offroad_drift_l": 0.0, "offroad_drift_r": 0.0,
    "drift_confidence": 0.0,
    "shift_click_until": 0.0, "shift_click_amp": 0.0,
    "shift_clunk_until": 0.0, "shift_clunk_amp": 0.0,
    "shift_rattle_until": 0.0, "shift_rattle_amp": 0.0,
    "shift_tail_until": 0.0, "shift_tail_amp": 0.0,
    "shift_torque_cut_until": 0.0, "shift_torque_cut_amp": 0.0,
    "shift_character": "street_sport",
    "shift_dir": 0.0,
    "idle_engine": 0.0,
    "launch_load": 0.0, "launch_active_prev": 0.0, "launch_release_until": 0.0, "launch_release_amp": 0.0,
    "rough_asphalt_l": 0.0, "rough_asphalt_r": 0.0,
    "dirt_l": 0.0, "dirt_r": 0.0, "grass_l": 0.0, "grass_r": 0.0,
    "rear_echo_l_until": 0.0, "rear_echo_r_until": 0.0, "rear_echo_l_amp": 0.0, "rear_echo_r_amp": 0.0,
    "scrape_l": 0.0, "scrape_r": 0.0, "collision_crack": 0.0,
    "last_torque_norm": 0.0, "torque_surge": 0.0, "boost_build": 0.0,
    "last_gear": None, "shift_kick_until": 0.0, "shift_kick_amp": 0.0,
    "last_now": None, "dt": 1.0 / 60.0,
    "weather_wetness": 0.0, "wetness_from_puddle": 0.0, "low_grip_memory": 0.0,
    "ice_memory": 0.0, "snow_memory": 0.0, "slush_memory": 0.0, "sand_memory": 0.0,
    "wet_asphalt_l": 0.0, "wet_asphalt_r": 0.0,
    "mud_l": 0.0, "mud_r": 0.0, "spray_l": 0.0, "spray_r": 0.0,
    "ice_l": 0.0, "ice_r": 0.0,
    "packed_snow_l": 0.0, "packed_snow_r": 0.0,
    "loose_snow_l": 0.0, "loose_snow_r": 0.0,
    "slush_l": 0.0, "slush_r": 0.0,
    "sand_l": 0.0, "sand_r": 0.0,
    "thin_water_l": 0.0, "thin_water_r": 0.0,
    "deep_water_l": 0.0, "deep_water_r": 0.0,
    "wet_tire_tail_l": 0.0, "wet_tire_tail_r": 0.0,
    "surface_transition_l": 0.0, "surface_transition_r": 0.0,
    "surface_transition_until": 0.0, "surface_transition_label": "",
    "surface_candidate_label": "unknown", "surface_candidate_since": 0.0,
    "last_surface_transition_time": 0.0,
    "last_surface_label": "unknown", "last_car_ordinal": None,
    "airborne_memory": 0.0, "landing_until": 0.0, "landing_amp": 0.0,
    "bottom_out_until": 0.0, "bottom_out_amp": 0.0,
    "brake_body_l": 0.0, "brake_body_r": 0.0,
    "abs_body_l": 0.0, "abs_body_r": 0.0,
    "rear_echo_l_due": 0.0, "rear_echo_r_due": 0.0,
    "rear_echo_l_tone": 0.0, "rear_echo_r_tone": 0.0,
    "shift_surface_duck_until": 0.0,
    # extended telemetry tracking
    "last_steer": 0.0,
    "last_rpm": 0.0,
    "susp_vel_fl": 0.0, "susp_vel_fr": 0.0, "susp_vel_rl": 0.0, "susp_vel_rr": 0.0,
    "last_accel_y": 0.0,
}

# Per-wheel event envelopes.
for _w in WHEELS:
    _state[f"kerb_{_w}_until"] = 0.0
    _state[f"puddle_{_w}_until"] = 0.0
    _state[f"puddle_{_w}_amp"] = 0.0
    _state[f"bump_{_w}_until"] = 0.0
    _state[f"bump_{_w}_amp"] = 0.0


def _tg(t, key, default=0.0):
    try:
        return t.get(key, default)
    except AttributeError:
        try:
            return t[key]
        except Exception:
            return default


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _gain(s, name: str, default: float = 1.0) -> float:
    try:
        return float(getattr(s, name, default))
    except Exception:
        return default


def _hold_s(s, name: str, default_ms: float, lo_ms: float = 0.0, hi_ms: float = 1000.0) -> float:
    ms = _gain(s, name, default_ms)
    return max(lo_ms, min(hi_ms, ms)) / 1000.0


def _release_alpha_from_ms(s, name: str, default_ms: float, lo: float = 0.06, hi: float = 0.55) -> float:
    # The telemetry loop is roughly frame-rate driven, not fixed. This alpha is
    # intentionally approximate; it gives users a predictable shorter/longer tail.
    ms = max(20.0, _gain(s, name, default_ms))
    return _clamp(45.0 / ms, lo, hi)


def _speed_norm(speed_kmh: float, start: float, full: float) -> float:
    if speed_kmh <= start:
        return 0.0
    return _clamp((speed_kmh - start) / max(1.0, full - start))


def _lateral_g(t, s=None) -> float:
    # Default remains accel_x, but logs accel_x/y/z and supports a hidden
    # source selector so road-test logs can prove whether the lateral axis/sign is right.
    src = str(getattr(s, "haptic_lateral_g_source", "accel_x") or "accel_x").lower() if s is not None else "accel_x"
    if src not in {"accel_x", "accel_y", "accel_z"}:
        src = "accel_x"
    g = float(_tg(t, src, 0.0)) / 9.80665
    if bool(getattr(s, "haptic_lateral_g_invert", False)):
        g = -g
    return max(-2.5, min(2.5, g))


def _torque_norm(t) -> float:
    return _clamp(abs(float(_tg(t, "torque", 0.0))) / 850.0)


def _power_norm(t) -> float:
    return _clamp(abs(float(_tg(t, "power", 0.0))) / 420000.0)


def _boost_norm(t) -> float:
    return _clamp(abs(float(_tg(t, "boost", 0.0))) / 1.5)


def _side_avg(t, prefix: str, side: str) -> float:
    vals = [abs(float(_tg(t, f"{prefix}_{w}", 0.0))) for w in SIDES[side]]
    return sum(vals) / max(1, len(vals))


def _rough_context(gravel_l: float, gravel_r: float, kerb: dict, puddle: dict | None = None) -> float:
    p = 0.0
    if puddle is not None:
        p = max(float(v) for v in puddle.values())
    return _clamp(max(gravel_l, gravel_r, max(float(v) for v in kerb.values()), p))


def _coordination(s) -> float:
    return _clamp(_gain(s, "haptic_trigger_haptic_coordination_strength", 0.70), 0.0, 1.0)


def _trigger_duck(s, layer: str, side: str | None = None) -> float:
    """Reduce haptic layers that duplicate an enabled trigger layer.

    Triggers own pedal/traction/ABS. Audio haptics own body, surface space,
    weather and collision. The coordinator keeps both systems from describing
    the exact same signal at the same time.
    """
    duck = _clamp(_gain(s, "haptic_trigger_ducking", 0.55), 0.0, 1.0) * _coordination(s)
    if duck <= 0.0:
        return 1.0
    if layer == "wheelspin" and bool(getattr(s, "enable_wheelspin_buzz", True)):
        return 1.0 - 0.68 * duck
    if layer == "scrub" and bool(getattr(s, "enable_tire_scrub_buzz", False)):
        return 1.0 - 0.66 * duck
    if layer == "asphalt_grip" and bool(getattr(s, "enable_tire_scrub_buzz", False)):
        return 1.0 - 0.30 * duck
    if layer == "slide" and bool(getattr(s, "enable_tire_scrub_buzz", False)):
        return 1.0 - 0.18 * duck
    if layer == "brake_abs" and bool(getattr(s, "enable_abs", True)):
        return 1.0 - 0.45 * duck
    if layer == "road":
        if side == "left" and bool(getattr(s, "enable_left_road_texture", False)):
            return 1.0 - 0.52 * duck
        if side == "right" and bool(getattr(s, "enable_right_road_texture", False)):
            return 1.0 - 0.52 * duck
    return 1.0


def _dt_alpha(alpha: float) -> float:
    """Frame-rate independent equivalent of the old per-frame smoothing alpha."""
    a = _clamp(alpha, 0.0, 0.98)
    dt = max(0.001, min(0.100, float(_state.get("dt", 1.0 / 60.0))))
    ref = 1.0 / 60.0
    return _clamp(1.0 - ((1.0 - a) ** (dt / ref)), 0.0, 0.98)


def _smooth(name: str, raw: float, attack: float = 0.50, release: float = 0.16) -> float:
    prev = float(_state.get(name, 0.0))
    alpha = _dt_alpha(attack if raw >= prev else release)
    v = prev + (raw - prev) * alpha
    _state[name] = v
    return v


def _transient_scale(s) -> float:
    return _clamp(_gain(s, "haptic_event_transient_strength", 1.0), 0.0, 1.5)


def _scale_event(v: float, s, minimum: float = 0.0) -> float:
    # 1.0 keeps current feel. Lower values quiet one-shot events; higher values
    # make kerb/puddle/bump/crack stand out without raising background buzz.
    return _clamp(float(v) * _transient_scale(s), minimum, 1.5)


def _side_max(t, prefix: str, side: str) -> float:
    return max(abs(float(_tg(t, f"{prefix}_{w}", 0.0))) for w in SIDES[side])


def _side_driven_max(t, prefix: str, side: str) -> float:
    wheels = set(DRIVEN.get(int(_tg(t, "drive_train", 2)), WHEELS))
    side_wheels = [w for w in SIDES[side] if w in wheels]
    if not side_wheels:
        side_wheels = list(SIDES[side])
    return max(abs(float(_tg(t, f"{prefix}_{w}", 0.0))) for w in side_wheels)


def _floor(v: float, floor: float) -> float:
    v = _clamp(v)
    if 0.0 < v < floor:
        return floor
    return v


def _event(name: str, raw: float, now: float, floor: float, hold_s: float, release_s: float = 0.10) -> float:
    """Small held envelope for short telemetry events.

    raw: normalized event intensity. If raw > 0, it arms/refreshes a hold.
    release_s controls linear fade after the hold expires.
    """
    raw = _clamp(raw)
    until_k = f"{name}_until"
    amp_k = f"{name}_amp"
    if raw > 0.0:
        amp = max(float(_state.get(amp_k, 0.0)) * 0.85, _floor(raw, floor))
        _state[amp_k] = _clamp(amp)
        _state[until_k] = now + hold_s
    until = float(_state.get(until_k, 0.0))
    amp = float(_state.get(amp_k, 0.0))
    if now <= until:
        return amp
    if release_s > 0.0 and now <= until + release_s:
        return _clamp(amp * (1.0 - ((now - until) / release_s)))
    _state[amp_k] = 0.0
    return 0.0


def _bool_event(name: str, active: bool, now: float, amp: float = 1.0, hold_s: float = 0.055) -> float:
    until_k = f"{name}_until"
    if active:
        _state[until_k] = now + hold_s
    return amp if now <= float(_state.get(until_k, 0.0)) else 0.0


def _rear_delay(speed_kmh: float) -> float:
    # Approx wheelbase delay. Too much feels late, so clamp hard for haptics.
    mps = max(1.0, float(speed_kmh) / 3.6)
    return max(0.018, min(0.115, 2.7 / mps))


def _schedule_rear_echo(side: str, amp: float, now: float, speed_kmh: float, s, tone: float = 0.0) -> None:
    if not bool(getattr(s, "haptic_front_rear_event_queue_enabled", True)):
        return
    a = _scale_event(amp, s)
    if a <= 0.0 or speed_kmh < 12.0:
        return
    due = now + _rear_delay(speed_kmh)
    key_due = f"rear_echo_{side}_due"
    key_until = f"rear_echo_{side}_until"
    key_amp = f"rear_echo_{side}_amp"
    key_tone = f"rear_echo_{side}_tone"
    hold = 0.050 + 0.030 * _clamp(_gain(s, "haptic_rear_echo_strength", 0.65), 0.0, 1.0)
    # Avoid rescheduling the same front wheel hold every frame; refresh when stronger
    # or when the pending echo is nearly complete. Due is stored separately so the
    # rear hit does not fire immediately after scheduling.
    if due > float(_state.get(key_until, 0.0)) - 0.025 or a > float(_state.get(key_amp, 0.0)):
        _state[key_due] = due
        _state[key_until] = due + hold
        _state[key_amp] = max(float(_state.get(key_amp, 0.0)) * 0.72, a)
        _state[key_tone] = _clamp(tone, -1.0, 1.0)


def _rear_echo(side: str, now: float) -> float:
    due = float(_state.get(f"rear_echo_{side}_due", 0.0))
    until = float(_state.get(f"rear_echo_{side}_until", 0.0))
    amp = float(_state.get(f"rear_echo_{side}_amp", 0.0))
    if amp <= 0.0:
        return 0.0
    if now < due:
        return 0.0
    if now <= until:
        return _clamp(amp)
    if now <= until + 0.075:
        return _clamp(amp * (1.0 - ((now - until) / 0.075)))
    _state[f"rear_echo_{side}_amp"] = 0.0
    _state[f"rear_echo_{side}_tone"] = 0.0
    return 0.0


def _one_pole(name: str, raw: float, attack_tau: float = 0.25, release_tau: float = 2.0) -> float:
    prev = float(_state.get(name, 0.0) or 0.0)
    dt = max(0.001, min(0.100, float(_state.get("dt", 1.0 / 60.0))))
    tau = attack_tau if raw >= prev else release_tau
    alpha = 1.0 - math.exp(-dt / max(0.025, tau))
    v = _clamp(prev + (raw - prev) * alpha)
    _state[name] = v
    return v


def _side_bool(t, prefix: str, side: str) -> bool:
    return any(int(_tg(t, f"{prefix}_{w}", 0)) > 0 for w in SIDES[side])


def _side_susp_current(t, side: str) -> float:
    vals = [abs(float(_tg(t, f"norm_suspension_travel_{w}", 0.0))) for w in SIDES[side]]
    return sum(vals) / max(1, len(vals))


def _tire_temp_context(t) -> float:
    temps = [float(_tg(t, f"tire_temp_{w}", 80.0)) for w in WHEELS]
    avg = sum(temps) / max(1, len(temps))
    # Conservative generic grip window. It is not a real tire model; it only
    # shifts haptic warning slightly so cold/overheated tires do not feel identical.
    cold_penalty = _clamp((70.0 - avg) / 45.0)
    hot_penalty = _clamp((118.0 - avg) / -45.0)
    return _clamp(1.0 - 0.18 * cold_penalty - 0.16 * hot_penalty, 0.72, 1.04)


def _vehicle_class_character(t) -> float:
    # Positive = high-PI/hypercar sharpness, negative = low/offroad/classic softness.
    pi = float(_tg(t, "car_performance_index", 650.0))
    power = abs(float(_tg(t, "power", 0.0)))
    torque = abs(float(_tg(t, "torque", 0.0)))
    drivetrain = int(_tg(t, "drive_train", 2))
    sharp = _clamp((pi - 750.0) / 250.0) * 0.65 + _clamp(power / 520000.0) * 0.25
    heavy_torque = _clamp((torque - 550.0) / 650.0) * 0.25
    rwd_bias = 0.10 if drivetrain == 1 else 0.0
    return _clamp(sharp + heavy_torque + rwd_bias, 0.0, 1.0)


def _vehicle_shift_character(t, surface_label: str = "dry_asphalt") -> str:
    """Telemetry-derived shift feel class.

    This deliberately avoids brand lookups. The haptic goal is not to know the
    car name; it is to infer whether the drivetrain should feel loose, sharp,
    torquey, rally-rough, smooth, or EV-direct from telemetry that is already
    available in Forza Data Out.
    """
    pi = float(_tg(t, "car_performance_index", 650.0))
    power = abs(float(_tg(t, "power", 0.0)))
    torque = abs(float(_tg(t, "torque", 0.0)))
    max_rpm = max(1.0, float(_tg(t, "max_rpm", 7000.0)))
    cylinders = int(_tg(t, "num_cylinders", 4))
    drivetrain = int(_tg(t, "drive_train", 2))
    offroadish = surface_label in {"gravel", "dirt", "grass", "sand", "mud", "slush", "loose_snow", "packed_snow"}
    if cylinders <= 0:
        return "ev_direct"
    if offroadish and drivetrain == 2 and pi >= 500:
        return "rally_rough"
    if drivetrain == 1 and torque > 650.0 and power > 260000.0:
        return "muscle_torque"
    if pi >= 900 or power > 650000.0 or max_rpm > 8800.0:
        return "race_sharp"
    if pi >= 760 or power > 360000.0 or max_rpm > 7600.0:
        return "street_sport"
    if pi < 450 or (power < 145000.0 and max_rpm < 6500.0):
        return "beater_loose"
    if pi < 610 and max_rpm < 7200.0:
        return "classic_manual"
    if pi >= 700 and torque > 520.0 and power > 260000.0:
        return "luxury_smooth"
    return "street_sport"


# --- REFACTORED: Early surface category detection for lazy layer selection ---
# Surface categories for skipping expensive calculations:
#   ASPHALT = dry/wet pavement, low roughness
#   OFFROAD = dirt, gravel, grass, sand, mud
#   SNOW_ICE = ice, packed/loose snow, slush
#   WATER = puddles, deep water crossings
_SURFACE_CATEGORIES = {
    "asphalt": {"dry_asphalt", "rough_asphalt", "wet_asphalt", "road"},
    "offroad": {"dirt", "gravel", "grass", "sand", "mud"},
    "snow_ice": {"ice", "packed_snow", "loose_snow", "slush"},
    "water": {"thin_water", "deep_water", "wet_tire_tail", "spray"},
}


def _quick_surface_category(t) -> str:
    """Fast surface category probe using raw telemetry only.
    
    Called once at the start of build_state() to determine which layer
    calculations can be skipped. Returns: "asphalt", "offroad", "snow_ice", or "water".
    """
    # Get raw telemetry values (no smoothing)
    rough_l = max(float(_tg(t, "surface_rumble_fl", 0.0)), float(_tg(t, "surface_rumble_rl", 0.0)))
    rough_r = max(float(_tg(t, "surface_rumble_fr", 0.0)), float(_tg(t, "surface_rumble_rr", 0.0)))
    rough = max(rough_l, rough_r)
    
    slip_l = max(float(_tg(t, "tire_combined_slip_fl", 0.0)), float(_tg(t, "tire_combined_slip_rl", 0.0)))
    slip_r = max(float(_tg(t, "tire_combined_slip_fr", 0.0)), float(_tg(t, "tire_combined_slip_rr", 0.0)))
    slip = max(slip_l, slip_r)
    
    puddle = any(int(_tg(t, f"wheel_in_puddle_{w}", 0)) > 0 for w in WHEELS)
    
    # Decision tree based on empirical telemetry ranges:
    # Water: explicit puddle contact
    if puddle:
        return "water"
    # Snow/Ice: low roughness + high slip (slippery smooth surface)
    if rough < 0.12 and slip > 0.45:
        return "snow_ice"
    # Offroad: high roughness
    if rough > 0.10:
        return "offroad"
    # Default: asphalt
    return "asphalt"


def _dominant_surface(candidates: dict[str, float]) -> tuple[str, float]:
    name, val = max(candidates.items(), key=lambda kv: kv[1])
    if val < 0.12:
        return "dry_asphalt", max(0.0, val)
    return name, _clamp(val)


def _raw_susp_delta(t, w: str) -> float:
    key = f"norm_suspension_travel_{w}"
    cur = abs(float(_tg(t, key, 0.0)))
    prev_key = f"last_susp_{w}"
    prev = _state.get(prev_key)
    _state[prev_key] = cur
    if prev is None:
        return 0.0
    return max(0.0, cur - float(prev))


def _collision_pan(t, s=None) -> float:
    """Best-effort L/R collision bias.

    Forza smashable telemetry gives strength, not side. Lateral acceleration is used
    only as a mild panning hint; if absent, keep centered.
    """
    ax = float(_tg(t, "accel_x", 0.0))
    steer = float(_tg(t, "steer", 0.0)) / 127.0
    strength = _clamp(_gain(s, "haptic_collision_direction_strength", 0.65) if s is not None else 0.65, 0.0, 1.0)
    if abs(ax) < 0.20 and abs(steer) < 0.10:
        return 0.0
    # Unknown sign in some telemetry versions; keep it subtle and fall back toward center.
    pan = (ax / 10.0) * 0.85 + steer * 0.15
    return _clamp(pan * strength, -0.75, 0.75)


def build_state(t, s, now: float | None = None) -> HapticState:
    if now is None:
        import time
        now = time.monotonic()

    last_now = _state.get("last_now")
    if last_now is None:
        _state["dt"] = 1.0 / 60.0
    else:
        _state["dt"] = max(0.001, min(0.100, float(now) - float(last_now)))
    _state["last_now"] = float(now)

    speed = max(0.0, float(_tg(t, "speed", 0.0)))
    if not bool(_tg(t, "on", False)):
        reset_haptic_state("telemetry_off")
        _state["last_now"] = float(now)
        return HapticState(speed_kmh=speed)

    car_now = int(_tg(t, "car_ordinal", 0) or 0)
    last_car = _state.get("last_car_ordinal")
    if car_now and last_car not in (None, 0, car_now):
        reset_haptic_state("car_changed")
        _state["last_now"] = float(now)
    _state["last_car_ordinal"] = car_now

    surface_texture_enabled = bool(getattr(s, "haptic_surface_texture_enabled", True))
    special_events_enabled = bool(getattr(s, "haptic_special_events_enabled", True))
    vehicle_flavor_enabled = bool(getattr(s, "haptic_vehicle_flavor_enabled", True))
    spatial_haptics_enabled = bool(getattr(s, "haptic_spatial_haptics_enabled", True))

    # --- REFACTORED: Early surface category for lazy layer selection ---
    # This determines which expensive layer calculations can be skipped.
    _surface_cat = _quick_surface_category(t)
    _state["surface_category"] = _surface_cat

    # 6.2 Forza speed-gate: 40~90km/h is still low-speed in Horizon.
    # Keep high-speed detail, but remove slow cart-like pulses below ~90km/h.
    low_start = _clamp(_gain(s, "haptic_low_speed_surface_start_kmh", 10.0), 0.0, 30.0)
    low_full = max(low_start + 20.0, _clamp(_gain(s, "haptic_low_speed_surface_full_kmh", 115.0), 55.0, 190.0))
    surface_motion_gate = _speed_norm(speed, low_start, low_full) ** 1.18
    road_motion_gate = max(surface_motion_gate, 0.30 * (_speed_norm(speed, 18.0, 80.0) ** 1.10))
    if speed < 2.0:
        surface_motion_gate = 0.0
        road_motion_gate = 0.0
    if not surface_texture_enabled:
        surface_motion_gate = 0.0
        road_motion_gate = 0.0
    offroad_bias = _clamp(_gain(s, "haptic_low_speed_offroad_bias", 0.82), 0.0, 1.0)
    offroad_low_speed_gate = (1.0 - offroad_bias) + offroad_bias * (_speed_norm(speed, 45.0, 145.0) ** 1.35)
    # Low-speed vehicle/body limiter: idle/collision stay alive, but fake body chatter does not.
    low_speed_body_gate = 0.22 + 0.78 * (_speed_norm(speed, 35.0, 125.0) ** 1.10)

    # Lateral-G / speed context. These drive asphalt texture and body-load space.
    lat_g = _lateral_g(t, s)
    abs_lat = abs(lat_g)
    lat_thr = _clamp(_gain(s, "haptic_lateral_g_threshold", 0.22), 0.02, 1.50)
    lat_sharp = max(0.35, _gain(s, "haptic_lateral_g_sharpness", 1.20))
    lat_signal = _clamp((abs_lat - lat_thr) / max(0.10, 1.20 - lat_thr)) ** lat_sharp
    speed_for_asphalt = _speed_norm(speed, 35.0, 170.0)
    speed_scale = _clamp(_gain(s, "haptic_asphalt_speed_scale", 1.0), 0.0, 2.0)

    # ----- extended telemetry extraction -----
    # These tap into previously unused Forza Data Out fields to create richer
    # mid-range texture and spatial feel without changing trigger feedback.
    dt = max(0.001, min(0.100, float(_state.get("dt", 1.0 / 60.0))))

    # RPM normalisation (idle..max → 0..1). Used for engine body texture later.
    rpm = max(0.0, float(_tg(t, "rpm", 0.0)))
    idle_rpm = max(100.0, float(_tg(t, "idle_rpm", 800.0)))
    max_rpm = max(idle_rpm + 500.0, float(_tg(t, "max_rpm", 7000.0)))
    rpm_norm = _clamp((rpm - idle_rpm) / max(1.0, max_rpm - idle_rpm))

    # Angular velocity: pitch (dive/squat) and roll (cornering lean).
    # Forza angular_velocity: x=pitch, y=yaw, z=roll (rad/s).
    # These were unused beyond yaw for drift; now we derive body motion cues.
    pitch_rate_raw = float(_tg(t, "angular_velocity_x", 0.0))
    roll_rate_raw = float(_tg(t, "angular_velocity_z", 0.0))
    yaw_rate_raw = float(_tg(t, "angular_velocity_y", 0.0))
    # Smooth to avoid per-frame jitter in haptics (these change fast in Forza)
    pitch_rate = _smooth("pitch_rate", _clamp(abs(pitch_rate_raw) / 3.0), 0.38, 0.14)
    roll_rate = _smooth("roll_rate", _clamp(abs(roll_rate_raw) / 3.5), 0.38, 0.14)
    yaw_rate = _smooth("yaw_rate", _clamp(abs(yaw_rate_raw) / 4.0), 0.38, 0.14)

    # Steering velocity: how fast the player turns in. Quick turn-in sharpens
    # texture response; gradual turn feels smoother. Derived from steer delta.
    steer_now = float(_tg(t, "steer", 0.0)) / 127.0
    last_steer = float(_state.get("last_steer", 0.0))
    steer_delta = abs(steer_now - last_steer) / max(0.001, dt)
    _state["last_steer"] = steer_now
    steer_velocity = _smooth("steer_velocity", _clamp(steer_delta / 12.0), 0.45, 0.12)

    # Suspension velocity per side (how fast the car compresses/extends).
    # Higher velocity = bumpier road = sharper texture attack.
    susp_vel_sides = {}
    for _sw in WHEELS:
        cur_s = abs(float(_tg(t, f"norm_suspension_travel_{_sw}", 0.0)))
        prev_s = float(_state.get(f"susp_vel_{_sw}", cur_s))
        sv = abs(cur_s - prev_s) / max(0.001, dt)
        _state[f"susp_vel_{_sw}"] = cur_s
        susp_vel_sides[_sw] = sv
    susp_velocity_l = _smooth("susp_vel_smooth_l",
                               _clamp(max(susp_vel_sides["fl"], susp_vel_sides["rl"]) / 6.0),
                               0.35, 0.14)
    susp_velocity_r = _smooth("susp_vel_smooth_r",
                               _clamp(max(susp_vel_sides["fr"], susp_vel_sides["rr"]) / 6.0),
                               0.35, 0.14)

    # Tire temperature: extend beyond simple gain to frequency modulation.
    # Cold tires feel "slippery sharp", hot tires feel "sluggish muted".
    tire_temp_grip = _tire_temp_context(t)
    temps = [float(_tg(t, f"tire_temp_{_tw}", 80.0)) for _tw in WHEELS]
    avg_temp = sum(temps) / max(1, len(temps))
    # Cold (<65°C): shift freq up +15%. Optimal (80-100°C): no shift. Hot (>120°C): shift down -10%
    cold_shift = _clamp((65.0 - avg_temp) / 40.0) * 0.15
    hot_shift = _clamp((avg_temp - 120.0) / 45.0) * -0.10
    tire_temp_freq_mod = 1.0 + cold_shift + hot_shift

    # Longitudinal acceleration: brake dive vs throttle squat feel.
    accel_y = float(_tg(t, "accel_y", 0.0))
    accel_longitudinal = _smooth("accel_long",
                                  _clamp(abs(accel_y) / 15.0),
                                  0.30, 0.12)

    # Front-rear wheel speed difference: traction control / power delivery signal.
    # AWD/RWD torque split creates a speed difference that's not captured elsewhere.
    ws_fl = abs(float(_tg(t, "wheel_rotation_speed_fl", 0.0)))
    ws_fr = abs(float(_tg(t, "wheel_rotation_speed_fr", 0.0)))
    ws_rl = abs(float(_tg(t, "wheel_rotation_speed_rl", 0.0)))
    ws_rr = abs(float(_tg(t, "wheel_rotation_speed_rr", 0.0)))
    front_avg = (ws_fl + ws_fr) / 2.0
    rear_avg = (ws_rl + ws_rr) / 2.0
    max_ws = max(front_avg, rear_avg, 1.0)
    wheel_speed_diff = _clamp(abs(front_avg - rear_avg) / max_ws / 0.25)

    # ----- engine enhancement telemetry -----
    # 1. Engine braking: RPM 높고 스로틀 0일 때 (엔진 저항 느낌)
    accel_raw = float(_tg(t, "accel", 0)) / 255.0
    engine_braking = 0.0
    if speed > 20.0 and accel_raw < 0.05 and rpm_norm > 0.25:
        engine_braking = _clamp(rpm_norm * 0.8 * _speed_norm(speed, 30.0, 200.0))
    engine_braking = _smooth("engine_braking", engine_braking, 0.30, 0.20)

    # 2. Corner exit torque: 스티어링이 복귀 중 + 가속 중
    steer_returning = max(0.0, float(_state.get("last_abs_steer", 0.0)) - abs(steer_now))
    _state["last_abs_steer"] = abs(steer_now)
    corner_exit_torque = 0.0
    if steer_returning > 0.01 and accel_raw > 0.5 and speed > 40.0:
        corner_exit_torque = _clamp(steer_returning * 8.0 * accel_raw * rpm_norm)
    corner_exit_torque = _smooth("corner_exit_torque", corner_exit_torque, 0.08, 0.25)

    # 3. Turbo spool: boost 증가 속도
    prev_boost = float(_state.get("prev_boost_build", 0.0))
    boost_now = _boost_norm(t)
    boost_delta = max(0.0, boost_now - prev_boost)
    _state["prev_boost_build"] = boost_now
    turbo_spool = _smooth("turbo_spool", _clamp(boost_delta * 5.0), 0.25, 0.15)

    # 4. Engine start: 속도 0에서 RPM이 갑자기 올라갈 때 (리스폰/시동)
    prev_rpm_norm = float(_state.get("prev_rpm_norm", 0.0))
    _state["prev_rpm_norm"] = rpm_norm
    engine_start = 0.0
    engine_start_cooldown = float(_state.get("engine_start_cooldown", 0.0))
    if engine_start_cooldown > 0.0:
        _state["engine_start_cooldown"] = max(0.0, engine_start_cooldown - dt)
    elif speed < 2.0 and prev_rpm_norm < 0.05 and rpm_norm > 0.15:
        engine_start = _clamp((rpm_norm - prev_rpm_norm) * 3.0)
        _state["engine_start_cooldown"] = 3.0  # 3초 쿨다운
    engine_start = _smooth("engine_start", engine_start, 0.10, 0.30)

    # 5. Cylinder count estimation: peak power 캐시 기반 (매 프레임 변동 방지)
    current_power = max(0.0, float(_tg(t, "power", 0.0)))
    peak_power = max(current_power, float(_state.get("peak_power", 0.0)))
    _state["peak_power"] = peak_power
    # peak power 기반 추정 (히스테리시스: 한번 결정되면 유지)
    prev_cyl = int(_state.get("cylinder_count", 0))
    if peak_power > 550:
        cylinder_count = 10
    elif peak_power > 380:
        cylinder_count = 8
    elif peak_power > 220:
        cylinder_count = 6
    else:
        cylinder_count = 4
    # 히스테리시스: 이미 결정된 값은 쉽게 바뀌지 않음
    if prev_cyl > 0 and abs(cylinder_count - prev_cyl) <= 2:
        cylinder_count = prev_cyl  # 유지
    _state["cylinder_count"] = cylinder_count

    # 6. Redline warning: rpm_norm이 이미 있으므로 추가 계산 불필요
    #    (렌더러가 rpm_norm > 0.9을 직접 확인)
    # ----- end extended telemetry -----

    # Weather/wetness and low-grip context. Forza telemetry available here does
    # not carry direct weather/material names. V3 deliberately splits true water
    # memory from generic low-grip memory so ice/snow do not collapse into
    # "wet asphalt" just because slip is high on a smooth surface.
    puddle_active_any = any(int(_tg(t, f"wheel_in_puddle_{w}", 0)) > 0 for w in WHEELS)
    puddle_l_contact = _side_bool(t, "wheel_in_puddle", "left")
    puddle_r_contact = _side_bool(t, "wheel_in_puddle", "right")
    rough_hint = max(_side_max(t, "surface_rumble", "left"), _side_max(t, "surface_rumble", "right"))
    slip_hint = max(
        _side_max(t, "tire_combined_slip", "left"), _side_max(t, "tire_combined_slip", "right"),
        _side_max(t, "tire_slip_angle", "left"), _side_max(t, "tire_slip_angle", "right"),
    )
    low_grip_hint = (
        _clamp((slip_hint - 0.34) / 0.95)
        * _speed_norm(speed, 24.0, 120.0)
    )
    water_target = 1.0 if puddle_active_any else 0.0
    water_memory = _one_pole("wetness_from_puddle", water_target, 0.20, 14.0) if bool(getattr(s, "haptic_weather_wetness_enabled", True)) else 0.0
    low_grip_memory = _one_pole("low_grip_memory", low_grip_hint, 0.32, 4.8)
    # Only a small amount of low-grip contributes to wetness without puddles; the
    # rest competes as ice/snow/slush below.
    wet_target = max(water_memory, low_grip_memory * _clamp((0.18 - rough_hint) / 0.18) * 0.20)
    wetness = _clamp(wet_target * _clamp(_gain(s, "haptic_weather_wetness_strength", 0.75), 0.0, 1.5))
    _state["weather_wetness"] = wetness

    # Road/asphalt: speed + lateral load gives clean tarmac a subtle body texture.
    # Keep this lower than events; grip layers below carry the stronger tire-limit feel.
    surface_l = _clamp((_side_max(t, "surface_rumble", "left") - 0.010) / 0.22) * 0.72
    surface_r = _clamp((_side_max(t, "surface_rumble", "right") - 0.010) / 0.22) * 0.72
    asphalt_base = _clamp(speed_for_asphalt * (0.13 + 0.22 * speed_scale))
    # Outside tire load gets more texture in corners.
    load_l = lat_signal if lat_g < 0.0 else 0.0
    load_r = lat_signal if lat_g > 0.0 else 0.0
    road_l_raw = _clamp((surface_l + asphalt_base * (1.0 + load_l * 1.20)) * 0.58)
    road_r_raw = _clamp((surface_r + asphalt_base * (1.0 + load_r * 1.20)) * 0.58)
    # Off-line bonus: normalized_driving_line (0=on-line, ±127=far off) adds
    # subtle extra texture when driving off the racing line. Free telemetry data.
    ndl = abs(float(_tg(t, "normalized_driving_line", 0)))
    off_line_boost = 1.0 + _clamp(ndl / 127.0) * 0.25  # up to +25% texture
    road_l = _smooth("road_l", road_l_raw, 0.40, 0.18) * (1.0 - wetness * 0.22) * off_line_boost
    road_r = _smooth("road_r", road_r_raw, 0.40, 0.18) * (1.0 - wetness * 0.22) * off_line_boost

    # Surface classifier / texture palette. This splits the previous generic road/gravel
    # signal into smoother asphalt, rough asphalt, dirt and grass-like low texture.
    # It is heuristic because Forza Data Out does not expose surface names directly.
    classifier_strength = _clamp(_gain(s, "haptic_surface_classifier_strength", 1.0), 0.0, 1.5)
    side_rough_l = _side_max(t, "surface_rumble", "left")
    side_rough_r = _side_max(t, "surface_rumble", "right")
    _susp_delta = {w: _raw_susp_delta(t, w) for w in WHEELS}
    susp_l = max(_susp_delta["fl"], _susp_delta["rl"])
    susp_r = max(_susp_delta["fr"], _susp_delta["rr"])
    # Put the deltas back for bump logic below by caching them per wheel.
    for _w, _d in _susp_delta.items():
        _state[f"cached_susp_delta_{_w}"] = max(float(_state.get(f"cached_susp_delta_{_w}", 0.0)), float(_d))
    rough_asphalt_l_raw = _clamp((side_rough_l - 0.025) / 0.16) * speed_for_asphalt * (1.0 - _clamp((side_rough_l - 0.18) / 0.22)) * classifier_strength
    rough_asphalt_r_raw = _clamp((side_rough_r - 0.025) / 0.16) * speed_for_asphalt * (1.0 - _clamp((side_rough_r - 0.18) / 0.22)) * classifier_strength
    # Dirt: rough but not sharp/chattery. Grass-like: smoother low rumble with slip but not much suspension spike.
    dirt_l_raw = _clamp((side_rough_l - 0.11) / 0.30) * (1.0 - _clamp(susp_l / 0.13)) * classifier_strength
    dirt_r_raw = _clamp((side_rough_r - 0.11) / 0.30) * (1.0 - _clamp(susp_r / 0.13)) * classifier_strength
    side_slip_l = max(_side_max(t, "tire_combined_slip", "left"), _side_max(t, "tire_slip_angle", "left"))
    side_slip_r = max(_side_max(t, "tire_combined_slip", "right"), _side_max(t, "tire_slip_angle", "right"))

    # Expanded low-grip surface classifier. These categories compete with wetness
    # instead of being folded into it. The aim is not perfect material detection;
    # it is enough separation that asphalt, ice, snow, slush and sand do not all
    # render as the same buzz.
    low_rough_l = _clamp((0.105 - side_rough_l) / 0.105)
    low_rough_r = _clamp((0.105 - side_rough_r) / 0.105)
    mid_rough_l = _clamp((side_rough_l - 0.045) / 0.22) * _clamp((0.34 - side_rough_l) / 0.34)
    mid_rough_r = _clamp((side_rough_r - 0.045) / 0.22) * _clamp((0.34 - side_rough_r) / 0.34)
    high_slip_l = _clamp((side_slip_l - 0.32) / 1.05) * _speed_norm(speed, 18.0, 95.0)
    high_slip_r = _clamp((side_slip_r - 0.32) / 1.05) * _speed_norm(speed, 18.0, 95.0)
    wet_side_l = max(wetness, 1.0 if puddle_l_contact else 0.0)
    wet_side_r = max(wetness, 1.0 if puddle_r_contact else 0.0)

    # --- LAZY LAYER SELECTION: Skip calculations based on surface category ---
    # This reduces CPU load and prevents irrelevant surfaces from contributing
    # "noise" that muddies the dominant texture. Only compute layers for the
    # current surface category.
    _skip_snow_ice = _state.get("surface_category") == "asphalt"
    _skip_sand = _state.get("surface_category") in ("asphalt", "snow_ice", "water")
    _skip_offroad_detail = _state.get("surface_category") in ("asphalt", "snow_ice")

    # ice must be conservative. Previous logs showed dry asphalt slides were
    # too often classified as ice because low roughness + high slip is common when
    # the player intentionally drifts. Require higher slip, more speed, slower
    # attack memory, and reduce confidence during strong dry lateral loading.
    ice_cls = _clamp(_gain(s, "haptic_ice_classifier_strength", 0.62), 0.0, 1.2) if not _skip_snow_ice else 0.0
    ice_min_speed = _clamp(_gain(s, "haptic_ice_min_speed_kmh", 40.0), 10.0, 90.0)
    ice_slip_l = _clamp((side_slip_l - 0.58) / 1.15) * _speed_norm(speed, ice_min_speed, 130.0)
    ice_slip_r = _clamp((side_slip_r - 0.58) / 1.15) * _speed_norm(speed, ice_min_speed, 130.0)
    dry_drift_guard_l = _clamp((abs_lat - 0.45) / 1.15) * low_rough_l * (1.0 - wet_side_l)
    dry_drift_guard_r = _clamp((abs_lat - 0.45) / 1.15) * low_rough_r * (1.0 - wet_side_r)
    ice_candidate_l = ice_slip_l * low_rough_l * (1.0 - wet_side_l * 0.92) * classifier_strength * ice_cls * (1.0 - 0.50 * dry_drift_guard_l)
    ice_candidate_r = ice_slip_r * low_rough_r * (1.0 - wet_side_r * 0.92) * classifier_strength * ice_cls * (1.0 - 0.50 * dry_drift_guard_r)
    ice_l_raw = _one_pole("ice_candidate_l", ice_candidate_l, 0.55, 1.55)
    ice_r_raw = _one_pole("ice_candidate_r", ice_candidate_r, 0.55, 1.55)
    # Snow calculations — skip when on asphalt to reduce noise
    if _skip_snow_ice:
        packed_snow_l_raw = packed_snow_r_raw = 0.0
        loose_snow_l_raw = loose_snow_r_raw = 0.0
        slush_l_raw = slush_r_raw = 0.0
    else:
        packed_snow_l_raw = high_slip_l * mid_rough_l * (1.0 - wet_side_l * 0.70) * (1.0 - _clamp(susp_l / 0.20) * 0.35) * classifier_strength
        packed_snow_r_raw = high_slip_r * mid_rough_r * (1.0 - wet_side_r * 0.70) * (1.0 - _clamp(susp_r / 0.20) * 0.35) * classifier_strength
        loose_snow_l_raw = high_slip_l * mid_rough_l * _clamp(susp_l / 0.22) * (1.0 - wet_side_l * 0.55) * classifier_strength
        loose_snow_r_raw = high_slip_r * mid_rough_r * _clamp(susp_r / 0.22) * (1.0 - wet_side_r * 0.55) * classifier_strength
        slush_l_raw = high_slip_l * wet_side_l * (0.35 + 0.65 * mid_rough_l) * classifier_strength
        slush_r_raw = high_slip_r * wet_side_r * (0.35 + 0.65 * mid_rough_r) * classifier_strength
    # Sand calculations — skip on asphalt/snow/water
    if _skip_sand:
        sand_l_raw = sand_r_raw = 0.0
    else:
        sand_l_raw = _clamp((side_slip_l - 0.24) / 0.76) * mid_rough_l * (1.0 - max(wet_side_l, ice_l_raw, packed_snow_l_raw) * 0.70) * _speed_norm(speed, 22.0, 125.0) * classifier_strength * 1.45
        sand_r_raw = _clamp((side_slip_r - 0.24) / 0.76) * mid_rough_r * (1.0 - max(wet_side_r, ice_r_raw, packed_snow_r_raw) * 0.70) * _speed_norm(speed, 22.0, 125.0) * classifier_strength * 1.45

    # Water sub-classes: film, puddle/deep crossing and wet tire tail. Duration
    # makes a stream/river crossing feel different from a one-frame puddle tick.
    for side, active in (("l", puddle_l_contact), ("r", puddle_r_contact)):
        dur_k = f"water_duration_{side}"
        tail_k = f"wet_tire_tail_{side}"
        if active:
            _state[dur_k] = float(_state.get(dur_k, 0.0)) + float(_state.get("dt", 1.0 / 60.0))
            _state[tail_k] = 1.0
        else:
            _state[dur_k] = max(0.0, float(_state.get(dur_k, 0.0)) - float(_state.get("dt", 1.0 / 60.0)) * 1.8)
            _state[tail_k] = max(0.0, float(_state.get(tail_k, 0.0)) - float(_state.get("dt", 1.0 / 60.0)) / 3.5)
    thin_water_l_raw = wetness * low_rough_l * _speed_norm(speed, 18.0, 110.0) * (1.0 - _clamp(float(_state.get("water_duration_l", 0.0)) / 0.65) * 0.45)
    thin_water_r_raw = wetness * low_rough_r * _speed_norm(speed, 18.0, 110.0) * (1.0 - _clamp(float(_state.get("water_duration_r", 0.0)) / 0.65) * 0.45)
    deep_water_l_raw = (1.0 if puddle_l_contact else 0.0) * _clamp(float(_state.get("water_duration_l", 0.0)) / 0.85) * (0.45 + 0.35 * _speed_norm(speed, 10.0, 75.0))
    deep_water_r_raw = (1.0 if puddle_r_contact else 0.0) * _clamp(float(_state.get("water_duration_r", 0.0)) / 0.85) * (0.45 + 0.35 * _speed_norm(speed, 10.0, 75.0))
    wet_tire_tail_l_raw = float(_state.get("wet_tire_tail_l", 0.0)) * _speed_norm(speed, 15.0, 120.0) * (0.28 + 0.32 * wetness)
    wet_tire_tail_r_raw = float(_state.get("wet_tire_tail_r", 0.0)) * _speed_norm(speed, 15.0, 120.0) * (0.28 + 0.32 * wetness)

    ice_l = _smooth("ice_l", ice_l_raw, 0.48, 0.10)
    ice_r = _smooth("ice_r", ice_r_raw, 0.48, 0.10)
    packed_snow_l = _smooth("packed_snow_l", packed_snow_l_raw, 0.36, 0.11)
    packed_snow_r = _smooth("packed_snow_r", packed_snow_r_raw, 0.36, 0.11)
    loose_snow_l = _smooth("loose_snow_l", loose_snow_l_raw, 0.34, 0.10)
    loose_snow_r = _smooth("loose_snow_r", loose_snow_r_raw, 0.34, 0.10)
    slush_l = _smooth("slush_l", slush_l_raw, 0.36, 0.10)
    slush_r = _smooth("slush_r", slush_r_raw, 0.36, 0.10)
    sand_l = _smooth("sand_l", sand_l_raw, 0.30, 0.12)
    sand_r = _smooth("sand_r", sand_r_raw, 0.30, 0.12)
    thin_water_l = _smooth("thin_water_l", thin_water_l_raw, 0.32, 0.12)
    thin_water_r = _smooth("thin_water_r", thin_water_r_raw, 0.32, 0.12)
    deep_water_l = _smooth("deep_water_l", deep_water_l_raw, 0.46, 0.12)
    deep_water_r = _smooth("deep_water_r", deep_water_r_raw, 0.46, 0.12)
    wet_tire_tail_l = _smooth("wet_tire_tail_l", wet_tire_tail_l_raw, 0.25, 0.08)
    wet_tire_tail_r = _smooth("wet_tire_tail_r", wet_tire_tail_r_raw, 0.25, 0.08)

    if not bool(getattr(s, "haptic_low_grip_surfaces_enabled", True)):
        ice_l = ice_r = packed_snow_l = packed_snow_r = loose_snow_l = loose_snow_r = slush_l = slush_r = sand_l = sand_r = 0.0
    if not bool(getattr(s, "haptic_water_detail_enabled", True)):
        thin_water_l = thin_water_r = deep_water_l = deep_water_r = wet_tire_tail_l = wet_tire_tail_r = 0.0

    # 6.2 guard: asphalt cornering/sliding used to be misread as grass because
    # low roughness + slip looked like a low-grip surface. Grass now needs real
    # rough/suspension evidence; slip alone is handled by asphalt grip/slide/drift.
    grass_rough_l = _clamp((side_rough_l - 0.030) / 0.130) * _clamp((0.24 - side_rough_l) / 0.24)
    grass_rough_r = _clamp((side_rough_r - 0.030) / 0.130) * _clamp((0.24 - side_rough_r) / 0.24)
    grass_susp_l = _clamp(susp_l / 0.18)
    grass_susp_r = _clamp(susp_r / 0.18)
    grass_evidence_l = max(grass_rough_l, grass_susp_l * 0.55)
    grass_evidence_r = max(grass_rough_r, grass_susp_r * 0.55)
    asphalt_slide_guard_l = low_rough_l * _clamp((abs_lat - 0.35) / 1.10) * (1.0 - wet_side_l)
    asphalt_slide_guard_r = low_rough_r * _clamp((abs_lat - 0.35) / 1.10) * (1.0 - wet_side_r)
    grass_l_raw = _clamp((side_slip_l - 0.45) / 1.10) * grass_evidence_l * _speed_norm(speed, 38.0, 130.0) * classifier_strength * (1.0 - max(ice_l, packed_snow_l, slush_l) * 0.75) * (1.0 - asphalt_slide_guard_l * 0.75)
    grass_r_raw = _clamp((side_slip_r - 0.45) / 1.10) * grass_evidence_r * _speed_norm(speed, 38.0, 130.0) * classifier_strength * (1.0 - max(ice_r, packed_snow_r, slush_r) * 0.75) * (1.0 - asphalt_slide_guard_r * 0.75)
    rough_asphalt_l = _smooth("rough_asphalt_l", rough_asphalt_l_raw * (1.0 - wetness * 0.18), 0.40, 0.14)
    rough_asphalt_r = _smooth("rough_asphalt_r", rough_asphalt_r_raw * (1.0 - wetness * 0.18), 0.40, 0.14)
    dirt_l = _smooth("dirt_l", dirt_l_raw, 0.35, 0.10)
    dirt_r = _smooth("dirt_r", dirt_r_raw, 0.35, 0.10)
    grass_l = _smooth("grass_l", grass_l_raw, 0.32, 0.12)
    grass_r = _smooth("grass_r", grass_r_raw, 0.32, 0.12)
    # --- LAZY SKIP: Zero out offroad detail when on asphalt/snow ---
    if _skip_offroad_detail:
        dirt_l = dirt_r = grass_l = grass_r = 0.0

    # Wet palette: clean wet asphalt should feel slick/shimmery; wet rough/offroad
    # becomes mud; high-speed wet asphalt gets a thin spray layer.
    wet_asphalt_l_raw = wetness * _speed_norm(speed, 24.0, 130.0) * _clamp((0.20 - side_rough_l) / 0.20) * (0.38 + 0.45 * lat_signal + 0.25 * _clamp((side_slip_l - 0.20) / 0.70))
    wet_asphalt_r_raw = wetness * _speed_norm(speed, 24.0, 130.0) * _clamp((0.20 - side_rough_r) / 0.20) * (0.38 + 0.45 * lat_signal + 0.25 * _clamp((side_slip_r - 0.20) / 0.70))
    mud_l_raw = wetness * _clamp((side_rough_l - 0.10) / 0.36) * (0.45 + 0.35 * _clamp(side_slip_l / 1.4))
    mud_r_raw = wetness * _clamp((side_rough_r - 0.10) / 0.36) * (0.45 + 0.35 * _clamp(side_slip_r / 1.4))
    spray_l_raw = wetness * _speed_norm(speed, 65.0, 180.0) * _clamp((0.22 - side_rough_l) / 0.22)
    spray_r_raw = wetness * _speed_norm(speed, 65.0, 180.0) * _clamp((0.22 - side_rough_r) / 0.22)
    wet_asphalt_l = _smooth("wet_asphalt_l", wet_asphalt_l_raw, 0.38, 0.10)
    wet_asphalt_r = _smooth("wet_asphalt_r", wet_asphalt_r_raw, 0.38, 0.10)
    mud_l = _smooth("mud_l", mud_l_raw, 0.35, 0.09)
    mud_r = _smooth("mud_r", mud_r_raw, 0.35, 0.09)
    spray_l = _smooth("spray_l", spray_l_raw, 0.36, 0.12)
    spray_r = _smooth("spray_r", spray_r_raw, 0.36, 0.12)

    # Surface dominance and transition event. This gives logs a clear answer to
    # "what did the classifier think this was?" and makes asphalt->snow/ice/water
    # changes tactile instead of just smoothed.
    surface_candidates_l = {
        "ice": ice_l,
        "packed_snow": packed_snow_l,
        "loose_snow": loose_snow_l,
        "slush": slush_l,
        "sand": max(sand_l, sand_l_raw * 5.0),
        "deep_water": deep_water_l,
        "wet_asphalt": wet_asphalt_l,
        "mud": mud_l,
        "dirt": dirt_l_raw * (1.0 - _clamp((side_slip_l - 0.36) / 0.70) * 0.75),
        "gravel": _clamp((side_rough_l - 0.13) / 0.28) * (1.0 - _clamp((side_slip_l - 0.36) / 0.70) * 0.75),
        "rough_asphalt": rough_asphalt_l_raw,
        "grass": grass_l_raw,
        "dry_asphalt": asphalt_base * (1.0 - max(wetness, ice_l, packed_snow_l, slush_l) * 0.55),
    }
    surface_candidates_r = {
        "ice": ice_r,
        "packed_snow": packed_snow_r,
        "loose_snow": loose_snow_r,
        "slush": slush_r,
        "sand": max(sand_r, sand_r_raw * 5.0),
        "deep_water": deep_water_r,
        "wet_asphalt": wet_asphalt_r,
        "mud": mud_r,
        "dirt": dirt_r_raw * (1.0 - _clamp((side_slip_r - 0.36) / 0.70) * 0.75),
        "gravel": _clamp((side_rough_r - 0.13) / 0.28) * (1.0 - _clamp((side_slip_r - 0.36) / 0.70) * 0.75),
        "rough_asphalt": rough_asphalt_r_raw,
        "grass": grass_r_raw,
        "dry_asphalt": asphalt_base * (1.0 - max(wetness, ice_r, packed_snow_r, slush_r) * 0.55),
    }
    label_l, conf_l = _dominant_surface(surface_candidates_l)
    label_r, conf_r = _dominant_surface(surface_candidates_r)
    dominant_label, dominant_conf = (label_l, conf_l) if conf_l >= conf_r else (label_r, conf_r)
    last_surface = str(_state.get("last_surface_label", "unknown") or "unknown")
    min_hold = _clamp(_gain(s, "haptic_surface_transition_min_hold_ms", 380.0), 80.0, 1200.0) / 1000.0
    cooldown = _clamp(_gain(s, "haptic_surface_transition_cooldown_ms", 550.0), 120.0, 1800.0) / 1000.0
    conf_delta = _clamp(_gain(s, "haptic_surface_transition_conf_delta", 0.14), 0.0, 0.60)
    last_conf = max(surface_candidates_l.get(last_surface, 0.0), surface_candidates_r.get(last_surface, 0.0))
    cand_label = str(_state.get("surface_candidate_label", "unknown") or "unknown")
    if dominant_label != last_surface and dominant_conf > 0.18 and speed > 8.0:
        if dominant_label != cand_label:
            _state["surface_candidate_label"] = dominant_label
            _state["surface_candidate_since"] = now
            _state["surface_candidate_conf"] = dominant_conf
        held = now - float(_state.get("surface_candidate_since", now) or now)
        cooldown_ok = (now - float(_state.get("last_surface_transition_time", 0.0) or 0.0)) >= cooldown
        confident = dominant_conf >= max(0.24, last_conf + conf_delta)
        if held >= min_hold and cooldown_ok and confident:
            _state["surface_transition_until"] = now + 0.080
            _state["surface_transition_label"] = f"{last_surface}->{dominant_label}"
            _state["surface_transition_l"] = _clamp(0.16 + conf_l * 0.52)
            _state["surface_transition_r"] = _clamp(0.16 + conf_r * 0.52)
            _state["last_surface_label"] = dominant_label
            _state["last_surface_transition_time"] = now
            _state["surface_candidate_label"] = dominant_label
            _state["surface_candidate_since"] = now
    elif dominant_conf > 0.22:
        _state["last_surface_label"] = dominant_label
        _state["surface_candidate_label"] = dominant_label
        _state["surface_candidate_since"] = now
    if now <= float(_state.get("surface_transition_until", 0.0)):
        surface_transition_l = _scale_event(float(_state.get("surface_transition_l", 0.0)), s)
        surface_transition_r = _scale_event(float(_state.get("surface_transition_r", 0.0)), s)
        surface_transition_label = str(_state.get("surface_transition_label", ""))
    else:
        surface_transition_l = 0.0
        surface_transition_r = 0.0
        surface_transition_label = ""

    # Weight transfer / lateral load. Positive accel_x is treated as right-side load; invert in settings if reversed.
    weight_strength = _clamp(_gain(s, "haptic_lateral_g_strength", 0.55), 0.0, 1.5) * (1.0 if spatial_haptics_enabled else 0.55)
    weight_speed = _speed_norm(speed, 25.0, 120.0)
    weight_amp = lat_signal * weight_speed * (0.55 + 0.45 * weight_strength)
    # Small pulse when lateral load changes side quickly.
    last_lat = float(_state.get("last_lat_g", 0.0))
    if abs(lat_g - last_lat) > 0.55 and abs_lat > lat_thr and speed > 35.0:
        _state["weight_pulse_until"] = now + 0.075
        _state["weight_pulse_side"] = 1.0 if lat_g > 0.0 else -1.0
        _state["weight_pulse_amp"] = _clamp(abs(lat_g - last_lat) / 1.4) * 0.55
    _state["last_lat_g"] = lat_g
    weight_l_raw = weight_amp if lat_g < 0.0 else 0.0
    weight_r_raw = weight_amp if lat_g > 0.0 else 0.0
    weight_l = _smooth("weight_l", weight_l_raw, 0.42, 0.16)
    weight_r = _smooth("weight_r", weight_r_raw, 0.42, 0.16)
    pulse_l = pulse_r = 0.0
    if now <= float(_state.get("weight_pulse_until", 0.0)):
        if float(_state.get("weight_pulse_side", 0.0)) < 0.0:
            pulse_l = float(_state.get("weight_pulse_amp", 0.0))
        else:
            pulse_r = float(_state.get("weight_pulse_amp", 0.0))

    # Kerb: wheel-specific with a short hold to prevent packet flicker.
    kerb = {}
    for w in WHEELS:
        active = int(_tg(t, f"wheel_on_rumble_strip_{w}", 0)) > 0 and speed > 3.0 and special_events_enabled
        kerb[w] = _scale_event(_bool_event(f"kerb_{w}", active, now, amp=1.0, hold_s=_hold_s(s, "haptic_kerb_hold_ms", 70.0, 20.0, 180.0)), s)
        if active and w in ("fl", "fr"):
            _schedule_rear_echo("l" if w == "fl" else "r", 0.50, now, speed, s, tone=-0.25)

    # Puddle: wheel-specific bright burst.
    puddle = {}
    for w in WHEELS:
        active = int(_tg(t, f"wheel_in_puddle_{w}", 0)) > 0 and speed > 4.0 and special_events_enabled
        if active and w in ("fl", "fr"):
            _schedule_rear_echo("l" if w == "fl" else "r", 0.42 + wetness * 0.10, now, speed, s, tone=1.00)
        puddle_tail = _clamp(_gain(s, "haptic_puddle_tail_strength", 0.55), 0.0, 1.0)
        puddle_priority = _clamp(_gain(s, "haptic_puddle_priority", 0.90), 0.0, 1.5)
        puddle_ms = _hold_s(s, "haptic_puddle_burst_ms", 105.0, 30.0, 250.0)
        # keep puddle as a crisp splash, not a long wet buzz.
        puddle_release = puddle_ms * (0.42 + puddle_tail * 0.38 + wetness * 0.10)
        puddle[w] = _scale_event(_event(f"puddle_{w}", (0.98 + 0.16 * puddle_priority + wetness * 0.10) if active else 0.0, now, floor=max(_gain(s, "haptic_event_floor", 0.15) * 1.25, 0.34), hold_s=puddle_ms * 0.90, release_s=puddle_release), s)

    # Gravel/dirt: stronger normalization than the early test build, with floor.
    # Kerb ducks gravel to avoid double-hitting the same event.
    gravel_bg = _clamp(_gain(s, "haptic_gravel_background_strength", 0.62), 0.0, 1.0)
    duck = _clamp(_gain(s, "haptic_surface_ducking", 0.78), 0.0, 1.0)
    gravel_l_raw = _clamp((_side_max(t, "surface_rumble", "left") - 0.070) / 0.34) * 1.35 * (0.55 + 0.45 * gravel_bg)
    gravel_r_raw = _clamp((_side_max(t, "surface_rumble", "right") - 0.070) / 0.34) * 1.35 * (0.55 + 0.45 * gravel_bg)
    if kerb["fl"] or kerb["rl"]:
        gravel_l_raw *= 0.28
    if kerb["fr"] or kerb["rr"]:
        gravel_r_raw *= 0.28
    # Water and sharp events must cut through offroad chatter.
    puddle_l_now = max(puddle["fl"], puddle["rl"])
    puddle_r_now = max(puddle["fr"], puddle["rr"])
    if puddle_l_now > 0.0:
        gravel_l_raw *= 1.0 - min(0.92, duck * (0.70 + 0.25 * puddle_l_now))
    if puddle_r_now > 0.0:
        gravel_r_raw *= 1.0 - min(0.92, duck * (0.70 + 0.25 * puddle_r_now))
    gravel_release = _release_alpha_from_ms(s, "haptic_gravel_release_ms", 170.0)
    gravel_l = _smooth("gravel_l", _clamp(gravel_l_raw), 0.50, gravel_release)
    gravel_r = _smooth("gravel_r", _clamp(gravel_r_raw), 0.50, gravel_release)

    # Let low-grip/snow/water surfaces own background identity. Dry road texture
    # and generic offroad buzz should back off so snow/ice/sand are not masked.
    cold_surface_l = max(ice_l, packed_snow_l, loose_snow_l, slush_l)
    cold_surface_r = max(ice_r, packed_snow_r, loose_snow_r, slush_r)
    water_surface_l = max(thin_water_l, deep_water_l, wet_tire_tail_l)
    water_surface_r = max(thin_water_r, deep_water_r, wet_tire_tail_r)
    road_l *= 1.0 - max(ice_l * 0.70, cold_surface_l * 0.42, water_surface_l * 0.28, sand_l * 0.22)
    road_r *= 1.0 - max(ice_r * 0.70, cold_surface_r * 0.42, water_surface_r * 0.28, sand_r * 0.22)
    rough_asphalt_l *= 1.0 - max(ice_l * 0.80, cold_surface_l * 0.50, water_surface_l * 0.25)
    rough_asphalt_r *= 1.0 - max(ice_r * 0.80, cold_surface_r * 0.50, water_surface_r * 0.25)
    dirt_l *= 1.0 - max(slush_l * 0.42, loose_snow_l * 0.35, sand_l * 0.25)
    dirt_r *= 1.0 - max(slush_r * 0.42, loose_snow_r * 0.35, sand_r * 0.25)

    # Dominant-surface gate: the classifier may infer many weak candidates at once,
    # but the pad must not play all continuous textures simultaneously. Keep the
    # dominant identity and a small secondary hint only. This removes the "cart
    # rattle" feel from non-asphalt roads.
    # --- REFACTORED: Non-dominant layers now return 0.0 instead of 0.08 ---
    # This eliminates the "averaged buzzing" from 16 layers all contributing 8%.
    def _dom_keep(label: str, layer: str) -> float:
        if layer == label:
            return 1.0
        if label in ("packed_snow", "loose_snow") and layer in ("packed_snow", "loose_snow"):
            return 0.85
        if label in ("thin_water", "deep_water", "wet_asphalt") and layer in ("thin_water", "deep_water", "wet_tire_tail", "wet_asphalt"):
            return 0.72
        if label in ("dirt", "gravel") and layer in ("dirt", "gravel"):
            return 0.40
        if label == "slush" and layer in ("wet_asphalt", "mud"):
            return 0.30
        if label == "sand" and layer in ("dirt", "gravel"):
            return 0.20
        if label == "dry_asphalt" and layer in ("road", "rough_asphalt"):
            return 0.55 if layer == "rough_asphalt" else 1.0
        return 0.0  # was 0.08; now completely silent

    road_l *= _dom_keep(label_l, "road") * road_motion_gate
    road_r *= _dom_keep(label_r, "road") * road_motion_gate
    gravel_l *= _dom_keep(label_l, "gravel") * surface_motion_gate * offroad_low_speed_gate
    gravel_r *= _dom_keep(label_r, "gravel") * surface_motion_gate * offroad_low_speed_gate
    rough_asphalt_l *= _dom_keep(label_l, "rough_asphalt") * road_motion_gate
    rough_asphalt_r *= _dom_keep(label_r, "rough_asphalt") * road_motion_gate
    dirt_l *= _dom_keep(label_l, "dirt") * surface_motion_gate * offroad_low_speed_gate
    dirt_r *= _dom_keep(label_r, "dirt") * surface_motion_gate * offroad_low_speed_gate
    grass_l *= _dom_keep(label_l, "grass") * surface_motion_gate * offroad_low_speed_gate
    grass_r *= _dom_keep(label_r, "grass") * surface_motion_gate * offroad_low_speed_gate
    wet_asphalt_l *= _dom_keep(label_l, "wet_asphalt") * road_motion_gate
    wet_asphalt_r *= _dom_keep(label_r, "wet_asphalt") * road_motion_gate
    mud_l *= _dom_keep(label_l, "mud") * surface_motion_gate * offroad_low_speed_gate
    mud_r *= _dom_keep(label_r, "mud") * surface_motion_gate * offroad_low_speed_gate
    spray_l *= _dom_keep(label_l, "wet_asphalt") * surface_motion_gate
    spray_r *= _dom_keep(label_r, "wet_asphalt") * surface_motion_gate
    ice_l *= _dom_keep(label_l, "ice") * surface_motion_gate
    ice_r *= _dom_keep(label_r, "ice") * surface_motion_gate
    packed_snow_l *= _dom_keep(label_l, "packed_snow") * surface_motion_gate * offroad_low_speed_gate
    packed_snow_r *= _dom_keep(label_r, "packed_snow") * surface_motion_gate * offroad_low_speed_gate
    loose_snow_l *= _dom_keep(label_l, "loose_snow") * surface_motion_gate * offroad_low_speed_gate
    loose_snow_r *= _dom_keep(label_r, "loose_snow") * surface_motion_gate * offroad_low_speed_gate
    slush_l *= _dom_keep(label_l, "slush") * surface_motion_gate * offroad_low_speed_gate
    slush_r *= _dom_keep(label_r, "slush") * surface_motion_gate * offroad_low_speed_gate
    sand_l *= _dom_keep(label_l, "sand") * surface_motion_gate * offroad_low_speed_gate
    sand_r *= _dom_keep(label_r, "sand") * surface_motion_gate * offroad_low_speed_gate
    thin_water_l *= _dom_keep(label_l, "thin_water") * surface_motion_gate
    thin_water_r *= _dom_keep(label_r, "thin_water") * surface_motion_gate
    deep_water_l *= _dom_keep(label_l, "deep_water") * surface_motion_gate
    deep_water_r *= _dom_keep(label_r, "deep_water") * surface_motion_gate
    wet_tire_tail_l *= _dom_keep(label_l, "wet_tire_tail") * surface_motion_gate
    wet_tire_tail_r *= _dom_keep(label_r, "wet_tire_tail") * surface_motion_gate


    # Wheelspin: body-haptic supplement only. Keep weaker than trigger but more audible than the early test build.
    accel = int(_tg(t, "accel", 0))
    throttle = _clamp((accel - 28) / 220.0)
    torque_boost = 0.75 + 0.35 * _torque_norm(t) + 0.20 * max(_power_norm(t), _boost_norm(t))
    wheel_l_raw = _clamp((_side_driven_max(t, "tire_slip_ratio", "left") - 0.40) / 1.45) * throttle * 1.42 * torque_boost
    wheel_r_raw = _clamp((_side_driven_max(t, "tire_slip_ratio", "right") - 0.40) / 1.45) * throttle * 1.42 * torque_boost
    wheel_l = _smooth("wheel_l", _clamp(wheel_l_raw), 0.55, 0.22)
    wheel_r = _smooth("wheel_r", _clamp(wheel_r_raw), 0.55, 0.22)

    # Scrub / asphalt grip / body slide. Offroad is treated as background; asphalt
    # grip gets boosted so deliberate tarmac slides are not weak.
    rough = _rough_context(gravel_l, gravel_r, kerb, puddle)
    offroad_factor = _clamp(max(gravel_l, gravel_r) * 1.15)
    asphalt_factor = _clamp((1.0 - rough * 0.82) * _speed_norm(speed, 30.0, 110.0))
    scrub_scale = 1.0 - min(0.70, rough * 0.62)
    # Lateral-G preloads scrub so tire-limit feedback arrives before the slip signal is already large.
    side_sep = _clamp(_gain(s, "haptic_side_grip_separation", 1.35), 0.5, 2.0) if spatial_haptics_enabled else 0.75
    grip_warn_l = lat_signal * side_sep * (0.48 + 0.32 * asphalt_factor) if lat_g < 0.0 and speed > 30.0 else 0.0
    grip_warn_r = lat_signal * side_sep * (0.48 + 0.32 * asphalt_factor) if lat_g > 0.0 and speed > 30.0 else 0.0
    angle_l = _side_max(t, "tire_slip_angle", "left")
    angle_r = _side_max(t, "tire_slip_angle", "right")
    combined_l = _side_max(t, "tire_combined_slip", "left")
    combined_r = _side_max(t, "tire_combined_slip", "right")
    scrub_l_raw = (_clamp((angle_l - 0.09) / 0.78) * 1.32 + grip_warn_l) * scrub_scale
    scrub_r_raw = (_clamp((angle_r - 0.09) / 0.78) * 1.32 + grip_warn_r) * scrub_scale
    scrub_l = _smooth("scrub_l", _clamp(scrub_l_raw), 0.50, 0.18)
    scrub_r = _smooth("scrub_r", _clamp(scrub_r_raw), 0.50, 0.18)

    # Asphalt Grip Sense: stronger than generic scrub, but only on relatively clean tarmac.
    # Uses lateral-G + slip-angle + combined-slip so the limit arrives earlier and sharper.
    asphalt_grip_strength = _clamp(_gain(s, "haptic_asphalt_grip_strength", 0.75), 0.0, 1.5)
    dry_grip_l = asphalt_factor * asphalt_grip_strength * (
        _clamp((angle_l - 0.055) / 0.55) * 0.50 +
        _clamp((combined_l - 0.55) / 1.25) * 0.25 +
        (lat_signal * side_sep if lat_g < 0.0 else 0.0) * 0.48
    )
    dry_grip_r = asphalt_factor * asphalt_grip_strength * (
        _clamp((angle_r - 0.055) / 0.55) * 0.50 +
        _clamp((combined_r - 0.55) / 1.25) * 0.25 +
        (lat_signal * side_sep if lat_g > 0.0 else 0.0) * 0.48
    )
    wet_grip_l = asphalt_factor * wetness * asphalt_grip_strength * (
        _clamp((angle_l - 0.030) / 0.42) * 0.42 +
        _clamp((combined_l - 0.38) / 0.95) * 0.24 +
        (lat_signal * side_sep if lat_g < 0.0 else 0.0) * 0.54
    )
    wet_grip_r = asphalt_factor * wetness * asphalt_grip_strength * (
        _clamp((angle_r - 0.030) / 0.42) * 0.42 +
        _clamp((combined_r - 0.38) / 0.95) * 0.24 +
        (lat_signal * side_sep if lat_g > 0.0 else 0.0) * 0.54
    )
    asphalt_grip_l_raw = dry_grip_l * (1.0 - wetness * 0.30) + wet_grip_l * 0.90
    asphalt_grip_r_raw = dry_grip_r * (1.0 - wetness * 0.30) + wet_grip_r * 0.90
    asphalt_grip_l = _smooth("asphalt_grip_l", _clamp(asphalt_grip_l_raw), 0.58, 0.18)
    asphalt_grip_r = _smooth("asphalt_grip_r", _clamp(asphalt_grip_r_raw), 0.58, 0.18)

    # Slide body: lateral velocity + yaw rotation gives the car-body drifting/rotating feel.
    # It is intentionally low/mid frequency in the renderer and complements trigger scrub.
    vx_kmh = abs(float(_tg(t, "velocity_x", 0.0))) * 3.6
    yaw_rate = abs(float(_tg(t, "angular_velocity_y", 0.0)))
    handbrake_n = _clamp(int(_tg(t, "handbrake", 0)) / 255.0)
    side_vel_n = _clamp((vx_kmh - 5.0) / 55.0) * _clamp(_gain(s, "haptic_velocity_x_strength", 0.55), 0.0, 1.5)
    yaw_n = _clamp((yaw_rate - 0.18) / 1.85) * _clamp(_gain(s, "haptic_yaw_rate_strength", 0.45), 0.0, 1.5)
    slide_raw = _clamp((side_vel_n * 0.55 + yaw_n * 0.35 + handbrake_n * 0.18) * _speed_norm(speed, 25.0, 105.0))
    # Choose the felt side from lateral velocity first, lateral-G second.
    slide_sign = 1.0 if float(_tg(t, "velocity_x", 0.0)) > 0.0 else -1.0 if float(_tg(t, "velocity_x", 0.0)) < 0.0 else (1.0 if lat_g > 0 else -1.0)
    last_slide_sign = float(_state.get("last_slide_sign", 0.0))
    if slide_raw > 0.22 and last_slide_sign != 0.0 and slide_sign != last_slide_sign:
        _state["slide_pulse_until"] = now + 0.075
        _state["slide_pulse_side"] = slide_sign
        _state["slide_pulse_amp"] = _clamp(slide_raw * 0.75)
    if slide_raw > 0.08:
        _state["last_slide_sign"] = slide_sign
    slide_l_raw = slide_raw if slide_sign < 0.0 else slide_raw * 0.12
    slide_r_raw = slide_raw if slide_sign > 0.0 else slide_raw * 0.12
    wet_slide_soften = 1.0 - wetness * asphalt_factor * 0.22
    slide_l = _smooth("slide_l", slide_l_raw * (0.55 + 0.45 * (1.0 - offroad_factor)) * wet_slide_soften, 0.42, 0.14)
    slide_r = _smooth("slide_r", slide_r_raw * (0.55 + 0.45 * (1.0 - offroad_factor)) * wet_slide_soften, 0.42, 0.14)
    slide_pulse_l = slide_pulse_r = 0.0
    if now <= float(_state.get("slide_pulse_until", 0.0)):
        if float(_state.get("slide_pulse_side", 0.0)) < 0.0:
            slide_pulse_l = float(_state.get("slide_pulse_amp", 0.0))
        else:
            slide_pulse_r = float(_state.get("slide_pulse_amp", 0.0))

    # Vehicle behavior classifier: separate front washout, rear rotation and
    # four-wheel slide. This keeps drifting from feeling identical to understeer.
    front_slip = max(
        abs(float(_tg(t, "tire_combined_slip_fl", 0.0))), abs(float(_tg(t, "tire_combined_slip_fr", 0.0))),
        abs(float(_tg(t, "tire_slip_angle_fl", 0.0))), abs(float(_tg(t, "tire_slip_angle_fr", 0.0))),
    )
    rear_slip = max(
        abs(float(_tg(t, "tire_combined_slip_rl", 0.0))), abs(float(_tg(t, "tire_combined_slip_rr", 0.0))),
        abs(float(_tg(t, "tire_slip_angle_rl", 0.0))), abs(float(_tg(t, "tire_slip_angle_rr", 0.0))),
    )
    steer_n = abs(float(_tg(t, "steer", 0.0))) / 127.0
    tire_temp_grip = _tire_temp_context(t)
    class_character = _vehicle_class_character(t)
    understeer_raw = _clamp((front_slip - rear_slip - 0.10) / 0.90) * steer_n * _speed_norm(speed, 35.0, 145.0)
    oversteer_raw = _clamp((rear_slip - front_slip - 0.08) / 0.90) * (0.35 + 0.65 * max(lat_signal, yaw_n, handbrake_n)) * _speed_norm(speed, 28.0, 130.0)
    four_wheel_slide_raw = _clamp(min(front_slip, rear_slip) - 0.45) * _speed_norm(speed, 35.0, 150.0) * (0.55 + 0.45 * lat_signal)
    # Ice lowers tire scrub texture but makes slide warning appear earlier.
    lowgrip_surface = max(ice_l, ice_r, packed_snow_l, packed_snow_r, slush_l, slush_r)
    under_side_l = understeer_raw if lat_g < 0.0 else understeer_raw * 0.08
    under_side_r = understeer_raw if lat_g > 0.0 else understeer_raw * 0.08
    understeer_l = _smooth("understeer_l", under_side_l * side_sep * (1.0 + lowgrip_surface * 0.18) * (1.06 - tire_temp_grip), 0.45, 0.16)
    understeer_r = _smooth("understeer_r", under_side_r * side_sep * (1.0 + lowgrip_surface * 0.18) * (1.06 - tire_temp_grip), 0.45, 0.16)
    oversteer_l = _smooth("oversteer_l", (oversteer_raw if slide_sign < 0.0 else oversteer_raw * 0.10) * (1.0 + class_character * 0.16), 0.45, 0.14)
    oversteer_r = _smooth("oversteer_r", (oversteer_raw if slide_sign > 0.0 else oversteer_raw * 0.10) * (1.0 + class_character * 0.16), 0.45, 0.14)
    four_wheel_slide = _smooth("four_wheel_slide", four_wheel_slide_raw, 0.42, 0.14)

    # 6.2 Slide Chaos / Drift: when the car is actually breaking loose, haptics
    # should become aggressive and side-biased. This sits above surface texture.
    throttle_pre = _clamp(int(_tg(t, "accel", 0)) / 255.0)
    rear_over_front = _clamp((rear_slip - front_slip - 0.03) / 0.82)
    front_over_rear = _clamp((front_slip - rear_slip - 0.06) / 0.82)
    yaw_slide = _clamp((yaw_rate - 0.22) / 1.25)
    side_slide = _clamp((vx_kmh - 10.0) / 72.0)
    drift_raw = _clamp(
        rear_over_front * (0.30 + 0.45 * max(yaw_slide, side_slide, handbrake_n) + 0.25 * throttle_pre)
        + slide_raw * 0.68
        + four_wheel_slide_raw * 0.45
        + handbrake_n * _speed_norm(speed, 25.0, 90.0) * 0.50
    ) * _speed_norm(speed, 35.0, 125.0)
    drift_conf = _smooth("drift_confidence", drift_raw, 0.66, 0.10)
    drift_side_bias = _clamp(_gain(s, "haptic_drift_side_bias", 0.82), 0.0, 1.0)
    own = 1.0
    other = max(0.02, 0.16 - drift_side_bias * 0.12)
    chaos_base = _clamp(drift_conf * (0.70 + 0.30 * max(yaw_slide, side_slide)))
    breakaway_base = _clamp(rear_over_front * (0.45 + 0.45 * throttle_pre + 0.30 * yaw_slide) * _speed_norm(speed, 35.0, 140.0))
    edge_base = _clamp(max(front_over_rear * steer_n, max(asphalt_grip_l_raw, asphalt_grip_r_raw) * 0.75) * _speed_norm(speed, 40.0, 150.0))
    if slide_sign < 0.0:
        slide_chaos_l_raw, slide_chaos_r_raw = chaos_base * own, chaos_base * other
        rear_breakaway_l_raw, rear_breakaway_r_raw = breakaway_base * own, breakaway_base * other
        side_scrub_edge_l_raw, side_scrub_edge_r_raw = edge_base * own, edge_base * other
    else:
        slide_chaos_l_raw, slide_chaos_r_raw = chaos_base * other, chaos_base * own
        rear_breakaway_l_raw, rear_breakaway_r_raw = breakaway_base * other, breakaway_base * own
        side_scrub_edge_l_raw, side_scrub_edge_r_raw = edge_base * other, edge_base * own
    slide_chaos_l = _smooth("slide_chaos_l", slide_chaos_l_raw, 0.70, 0.12)
    slide_chaos_r = _smooth("slide_chaos_r", slide_chaos_r_raw, 0.70, 0.12)
    rear_breakaway_l = _smooth("rear_breakaway_l", rear_breakaway_l_raw, 0.64, 0.12)
    rear_breakaway_r = _smooth("rear_breakaway_r", rear_breakaway_r_raw, 0.64, 0.12)
    side_scrub_edge_l = _smooth("side_scrub_edge_l", side_scrub_edge_l_raw, 0.62, 0.14)
    side_scrub_edge_r = _smooth("side_scrub_edge_r", side_scrub_edge_r_raw, 0.62, 0.14)

    # 6.3 Tire slip texture: body chaos is not the same as tire rubber sliding.
    # Asphalt drift gets thin scrub/sizzle; offroad drift gets granular drag.
    asphalt_like_l = 1.0 if label_l in {"dry_asphalt", "rough_asphalt", "wet_asphalt", "thin_water"} else 0.35
    asphalt_like_r = 1.0 if label_r in {"dry_asphalt", "rough_asphalt", "wet_asphalt", "thin_water"} else 0.35
    offroad_like_l = 1.0 if label_l in {"gravel", "dirt", "grass", "sand", "mud", "slush", "loose_snow", "packed_snow"} else 0.0
    offroad_like_r = 1.0 if label_r in {"gravel", "dirt", "grass", "sand", "mud", "slush", "loose_snow", "packed_snow"} else 0.0
    ice_like_l = 1.0 if label_l == "ice" else 0.0
    ice_like_r = 1.0 if label_r == "ice" else 0.0
    tire_slip_l = _clamp((side_slip_l - 0.18) / 1.15) * _speed_norm(speed, 28.0, 150.0)
    tire_slip_r = _clamp((side_slip_r - 0.18) / 1.15) * _speed_norm(speed, 28.0, 150.0)
    tire_scrub_l_raw = _clamp((tire_slip_l * 0.70 + max(asphalt_grip_l_raw, side_scrub_edge_l_raw) * 0.55) * asphalt_like_l * (1.0 - ice_like_l * 0.65))
    tire_scrub_r_raw = _clamp((tire_slip_r * 0.70 + max(asphalt_grip_r_raw, side_scrub_edge_r_raw) * 0.55) * asphalt_like_r * (1.0 - ice_like_r * 0.65))
    tire_smear_l_raw = _clamp((slide_l_raw + oversteer_l + four_wheel_slide_raw * 0.45) * (0.35 + 0.65 * asphalt_like_l))
    tire_smear_r_raw = _clamp((slide_r_raw + oversteer_r + four_wheel_slide_raw * 0.45) * (0.35 + 0.65 * asphalt_like_r))
    slip_sizzle_l_raw = _clamp(tire_slip_l * asphalt_like_l * _speed_norm(speed, 75.0, 210.0) * (0.35 + 0.65 * drift_conf))
    slip_sizzle_r_raw = _clamp(tire_slip_r * asphalt_like_r * _speed_norm(speed, 75.0, 210.0) * (0.35 + 0.65 * drift_conf))
    asphalt_drift_l_raw = _clamp(drift_conf * asphalt_like_l * (0.45 + 0.55 * max(tire_scrub_l_raw, slip_sizzle_l_raw)))
    asphalt_drift_r_raw = _clamp(drift_conf * asphalt_like_r * (0.45 + 0.55 * max(tire_scrub_r_raw, slip_sizzle_r_raw)))
    offroad_drift_l_raw = _clamp(drift_conf * offroad_like_l * (0.55 + 0.45 * max(gravel_l, dirt_l, sand_l, mud_l, loose_snow_l)))
    offroad_drift_r_raw = _clamp(drift_conf * offroad_like_r * (0.55 + 0.45 * max(gravel_r, dirt_r, sand_r, mud_r, loose_snow_r)))
    tire_scrub_l = _smooth("tire_scrub_l", tire_scrub_l_raw, 0.66, 0.16)
    tire_scrub_r = _smooth("tire_scrub_r", tire_scrub_r_raw, 0.66, 0.16)
    tire_smear_l = _smooth("tire_smear_l", tire_smear_l_raw, 0.58, 0.18)
    tire_smear_r = _smooth("tire_smear_r", tire_smear_r_raw, 0.58, 0.18)
    slip_sizzle_l = _smooth("slip_sizzle_l", slip_sizzle_l_raw, 0.72, 0.14)
    slip_sizzle_r = _smooth("slip_sizzle_r", slip_sizzle_r_raw, 0.72, 0.14)
    asphalt_drift_l = _smooth("asphalt_drift_l", asphalt_drift_l_raw, 0.64, 0.14)
    asphalt_drift_r = _smooth("asphalt_drift_r", asphalt_drift_r_raw, 0.64, 0.14)
    offroad_drift_l = _smooth("offroad_drift_l", offroad_drift_l_raw, 0.64, 0.16)
    offroad_drift_r = _smooth("offroad_drift_r", offroad_drift_r_raw, 0.64, 0.16)

    # Airborne / landing / bottom-out. Suspension fields are imperfect, so this
    # uses a conservative memory and only fires strong haptic events on clear changes.
    susp_vals = [abs(float(_tg(t, f"norm_suspension_travel_{w}", 0.0))) for w in WHEELS]
    avg_susp = sum(susp_vals) / max(1, len(susp_vals))
    max_susp = max(susp_vals)
    max_susp_delta = max(_susp_delta.values()) if _susp_delta else 0.0
    accel_z_abs = abs(float(_tg(t, "accel_z", 0.0)))
    airborne_raw = _clamp((0.10 - avg_susp) / 0.10) * _speed_norm(speed, 35.0, 115.0)
    airborne_prev = float(_state.get("airborne_memory", 0.0))
    airborne = _smooth("airborne_memory", airborne_raw, 0.55, 0.08)
    if airborne_prev > 0.32 and airborne < 0.20 and max_susp_delta > 0.055:
        _state["landing_until"] = now + 0.110
        _state["landing_amp"] = _scale_event(_clamp(0.30 + max_susp_delta * 3.0 + accel_z_abs / 30.0), s)
    if max_susp > 0.94 or (max_susp_delta > 0.16 and accel_z_abs > 11.0):
        _state["bottom_out_until"] = now + 0.090
        _state["bottom_out_amp"] = _scale_event(_clamp(0.34 + max_susp_delta * 2.8 + accel_z_abs / 34.0), s)
    landing = float(_state.get("landing_amp", 0.0)) if now <= float(_state.get("landing_until", 0.0)) else 0.0
    bottom_out = float(_state.get("bottom_out_amp", 0.0)) if now <= float(_state.get("bottom_out_until", 0.0)) else 0.0

    # Trigger-haptic ducking. Keep haptics as body/space information when the
    # trigger already owns the same traction/road signal.
    road_l *= _trigger_duck(s, "road", "left")
    road_r *= _trigger_duck(s, "road", "right")
    wheel_l *= _trigger_duck(s, "wheelspin")
    wheel_r *= _trigger_duck(s, "wheelspin")
    scrub_l *= _trigger_duck(s, "scrub")
    scrub_r *= _trigger_duck(s, "scrub")
    asphalt_grip_l *= _trigger_duck(s, "asphalt_grip")
    asphalt_grip_r *= _trigger_duck(s, "asphalt_grip")
    slide_l *= _trigger_duck(s, "slide")
    slide_r *= _trigger_duck(s, "slide")

    # Bump/landing: big suspension delta only; short hold. Wheel-specific for spatial feel.
    sens = max(0.10, _gain(s, "suspension_bump_sensitivity", 1.0))
    bump = {}
    for w in WHEELS:
        delta = _raw_susp_delta(t, w)
        # Surface classifier may have already touched suspension on this frame; use the cached side delta as a fallback.
        if delta <= 0.0:
            delta = max(0.0, float(_state.get(f"cached_susp_delta_{w}", 0.0)))
        _state[f"cached_susp_delta_{w}"] = 0.0
        # Stronger than the early test build, still avoids regular gravel chatter.
        raw = _clamp((delta - (0.055 / sens)) / 0.18) * 1.55
        bump_ms = _hold_s(s, "haptic_bump_decay_ms", 150.0, 50.0, 350.0)
        bump_shape = _clamp(_gain(s, "haptic_bump_sequence_strength", 0.65), 0.0, 1.0)
        # punchier hits with a shorter tail. Keeps texture quiet but lets bumps pop.
        bump[w] = _scale_event(_event(f"bump_{w}", raw * 1.08, now, floor=max(0.16, _gain(s, "haptic_event_floor", 0.15) * 1.25), hold_s=bump_ms * (0.42 + 0.22 * bump_shape), release_s=bump_ms * (0.55 + 0.18 * bump_shape)), s)
        if raw > 0.0 and w in ("fl", "fr"):
            _schedule_rear_echo("l" if w == "fl" else "r", raw * 0.65, now, speed, s, tone=-0.70)

    # Collision: stronger scale, floor, and hold. Try mild spatial bias from lateral acceleration.
    smash = max(0.0, float(_tg(t, "smashable_vel_diff", 0.0)))
    mass = max(0.0, float(_tg(t, "smashable_mass", 0.0)))
    # V2: lower threshold (0.38→0.12) and softer mass gate (0.20→0.08) to catch
    # NPC car collisions (low mass, low vel_diff). Original missed them entirely.
    collision_raw = _clamp((smash - 0.12) / 1.60) * _clamp((mass + 0.04) / 0.08) * 2.35
    if collision_raw > 0.0 and special_events_enabled:
        amp = _floor(collision_raw, max(0.40, _gain(s, "haptic_event_floor", 0.15) * 2.4))
        # Punchier, shorter collision envelope: it should cut through texture, not
        # become another gravel-like tail.
        _state["collision_amp"] = max(float(_state.get("collision_amp", 0.0)) * 0.62, amp)
        _state["collision_until"] = now + _hold_s(s, "haptic_collision_decay_ms", 135.0, 50.0, 260.0) * 0.55
        _state["collision_pan"] = _collision_pan(t, s)
    collision = _event("collision", 0.0, now, floor=max(0.40, _gain(s, "haptic_event_floor", 0.15) * 2.4), hold_s=0.15, release_s=0.09)
    # _event() above only fades existing values stored under collision_amp/until.
    if collision == 0.0:
        # fall back to explicit collision envelope storage for compatibility with _event logic
        until = float(_state.get("collision_until", 0.0))
        amp = float(_state.get("collision_amp", 0.0))
        if now <= until:
            collision = amp
        elif now <= until + _hold_s(s, "haptic_collision_decay_ms", 135.0, 50.0, 260.0):
            decay = _hold_s(s, "haptic_collision_decay_ms", 135.0, 50.0, 260.0)
            collision = _clamp(amp * (1.0 - ((now - until) / decay)))
        else:
            _state["collision_amp"] = 0.0
            collision = 0.0
    collision = _scale_event(collision, s)
    pan = float(_state.get("collision_pan", 0.0)) if collision > 0.0 else 0.0
    spatial = _clamp(_gain(s, "haptic_spatial_width", 1.0), 0.0, 1.5)
    pan = _clamp(pan * spatial, -0.80, 0.80)
    # Constant-power-ish but mild. Keep center hit strong on both grips.
    collision_l = _clamp(collision * (1.0 - max(0.0, pan) * 0.48 + max(0.0, -pan) * 0.24))
    collision_r = _clamp(collision * (1.0 - max(0.0, -pan) * 0.48 + max(0.0, pan) * 0.24))

    # Idle engine shake: stationary muscle/high-torque character. Disabled by default and kept subtle.
    rpm = max(0.0, float(_tg(t, "rpm", 0.0)))
    idle_rpm = max(1.0, float(_tg(t, "idle_rpm", 850.0)))
    max_rpm = max(idle_rpm + 1.0, float(_tg(t, "max_rpm", 7000.0)))
    accel_byte = int(_tg(t, "accel", 0))
    brake_byte = int(_tg(t, "brake", 0))
    torque_n = _torque_norm(t)
    power_n = _power_norm(t)
    boost_n = _boost_norm(t)
    rpm_above_idle = _clamp((rpm - idle_rpm) / max(500.0, max_rpm - idle_rpm))
    idle_cond = speed < 8.0 and accel_byte < 45 and rpm <= idle_rpm + 700.0
    idle_raw = 0.0
    if idle_cond:
        idle_raw = (1.0 - speed / 8.0) * (0.25 + torque_n * _clamp(_gain(s, "haptic_idle_torque_scale", 0.65), 0.0, 1.5))
        idle_raw *= 0.65 + 0.35 * _clamp(_gain(s, "haptic_idle_strength", 0.22), 0.0, 1.0)
    idle_engine = _smooth("idle_engine", _clamp(idle_raw), 0.22, 0.10)

    # Launch load: brake+throttle torque build-up for drag/lauch-control style starts.
    throttle_n = _clamp(accel_byte / 255.0)
    brake_n = _clamp(brake_byte / 255.0)
    launch_threshold = _clamp(_gain(s, "haptic_launch_threshold", 0.40), 0.05, 0.95)
    rpm_load = _clamp((rpm - idle_rpm) / max(900.0, max_rpm * 0.35))
    load_signal = throttle_n * brake_n * (0.35 + 0.35 * rpm_load + 0.20 * torque_n + 0.10 * max(power_n, boost_n))
    launch_raw = _clamp((load_signal - launch_threshold * 0.30) / max(0.10, 1.0 - launch_threshold * 0.30)) if speed < 12.0 and accel_byte > 35 and brake_byte > 45 else 0.0
    launch_load = _smooth("launch_load", launch_raw, 0.45, 0.18)
    was_launch = float(_state.get("launch_active_prev", 0.0)) > 0.20
    is_launch = launch_load > 0.22
    if was_launch and not is_launch and throttle_n > 0.35 and speed < 35.0:
        _state["launch_release_until"] = now + 0.120
        _state["launch_release_amp"] = max(float(_state.get("launch_release_amp", 0.0)), _clamp(float(_state.get("launch_load", 0.0)) * 0.90 + rpm_load * 0.25))
    _state["launch_active_prev"] = launch_load
    if now <= float(_state.get("launch_release_until", 0.0)):
        launch_release = float(_state.get("launch_release_amp", 0.0))
    elif now <= float(_state.get("launch_release_until", 0.0)) + 0.150:
        tail = 1.0 - ((now - float(_state.get("launch_release_until", 0.0))) / 0.150)
        launch_release = _clamp(float(_state.get("launch_release_amp", 0.0)) * tail)
    else:
        _state["launch_release_amp"] = 0.0
        launch_release = 0.0
    launch_release = _scale_event(launch_release, s)

    # Collision scrape/crack: small side contacts and breakable objects should not all feel like one low thump.
    accel_x = float(_tg(t, "accel_x", 0.0))
    accel_z = float(_tg(t, "accel_z", 0.0))
    yaw_rate_full = abs(float(_tg(t, "angular_velocity_y", 0.0)))
    scrape_raw = _clamp((abs(accel_x) - 2.4) / 8.5) * _speed_norm(speed, 18.0, 120.0)
    # If there is smashable data, make scrape/crack more likely, but keep it side-biased.
    scrape_raw = max(scrape_raw, _clamp((smash - 0.16) / 1.3) * _clamp(abs(accel_x) / 7.5))
    scrape_side_l = scrape_raw if accel_x < 0.0 else scrape_raw * 0.25
    scrape_side_r = scrape_raw if accel_x > 0.0 else scrape_raw * 0.25
    scrape_l = _scale_event(_smooth("scrape_l", scrape_side_l, 0.55, 0.20), s)
    scrape_r = _scale_event(_smooth("scrape_r", scrape_side_r, 0.55, 0.20), s)
    collision_crack = _scale_event(_clamp(_clamp((smash - 0.20) / 1.35) * (0.35 + 0.65 * _clamp(mass / 0.18)) + _clamp(abs(accel_z) / 22.0) * 0.20), s)

    # Engine detail: boost shimmer / torque surge / optional shift body kick.
    boost_build = _smooth("boost_build", _boost_norm(t) * throttle_n * _speed_norm(speed, 8.0, 130.0), 0.32, 0.10)
    torque_n = _torque_norm(t)
    torque_delta = max(0.0, torque_n - float(_state.get("last_torque_norm", 0.0)))
    _state["last_torque_norm"] = torque_n
    torque_surge = _smooth("torque_surge", _clamp(torque_delta * 3.8 + torque_n * throttle_n * _speed_norm(speed, 5.0, 90.0) * 0.25), 0.45, 0.12)
    gear_now = int(_tg(t, "gear", 0))
    gear_prev = _state.get("last_gear")
    valid_gear = gear_now > 0 and gear_now != 11
    shift_character = str(_state.get("shift_character", "street_sport") or "street_sport")
    shift_click = shift_clunk = shift_rattle = shift_tail = shift_torque_cut = 0.0
    if valid_gear and gear_prev is not None and int(gear_prev) > 0 and int(gear_prev) != 11 and gear_now != int(gear_prev) and speed > 12.0 and abs(gear_now - int(gear_prev)) <= 2:
        shift_dir = 1 if gear_now > int(gear_prev) else -1
        shift_character = _vehicle_shift_character(t, dominant_label)
        load = max(throttle_n, rpm_above_idle, _speed_norm(speed, 20.0, 170.0))
        char_mul = {
            # click, clunk, rattle, torque-cut, tail
            "beater_loose": (1.12, 1.42, 1.12, 1.00, 0.82),
            "classic_manual": (1.08, 1.20, 0.90, 0.88, 0.66),
            "street_sport": (1.18, 1.00, 0.34, 0.76, 0.44),
            "race_sharp": (1.30, 0.84, 0.00, 0.68, 0.24),
            "muscle_torque": (1.02, 1.48, 0.52, 0.86, 0.76),
            "rally_rough": (1.16, 1.30, 0.98, 0.88, 0.70),
            "luxury_smooth": (0.78, 0.72, 0.08, 0.42, 0.38),
            "ev_direct": (0.18, 0.24, 0.00, 0.12, 0.04),
        }.get(shift_character, (1.10, 1.00, 0.32, 0.72, 0.42))
        down_mul = 1.18 if shift_dir < 0 else 1.0
        # Tokyo log: shift RMS increased only about +0.03 over background. Raise
        # event amplitude here, then let 6.3.1 settings control final loudness.
        base = _clamp(0.52 + 0.52 * throttle_n + 0.36 * rpm_above_idle + 0.22 * _speed_norm(speed, 20.0, 180.0))
        _state["shift_dir"] = float(shift_dir)
        _state["shift_character"] = shift_character
        _state["shift_gear"] = float(gear_now)  # gear AFTER shift (2=1→2, 6=5→6)
        # 30ms delay: align haptic burst with trigger rigid→clack transition.
        # Trigger rigid lock is felt at 0ms; haptic should land at the clack (~32ms).
        _shift_delay = 0.030
        _state["shift_kick_until"] = now + _shift_delay + 0.185
        _state["shift_kick_amp"] = _clamp(base * (0.92 + char_mul[1] * 0.36) * down_mul)
        _state["shift_click_until"] = now + _shift_delay + 0.075
        _state["shift_click_amp"] = _clamp(base * char_mul[0] * (1.10 if shift_dir > 0 else 0.96))
        _state["shift_clunk_until"] = now + _shift_delay + (0.120 if shift_character in {"race_sharp", "street_sport"} else 0.165)
        _state["shift_clunk_amp"] = _clamp(base * char_mul[1] * down_mul)
        _state["shift_rattle_until"] = now + _shift_delay + (0.160 if shift_character in {"beater_loose", "classic_manual", "rally_rough"} else 0.070)
        _state["shift_rattle_amp"] = _clamp(base * char_mul[2])
        _state["shift_tail_until"] = now + _shift_delay + (0.190 if shift_character in {"beater_loose", "muscle_torque", "rally_rough"} else 0.145)
        _state["shift_tail_amp"] = _clamp(base * char_mul[4] * down_mul)
        _state["shift_torque_cut_until"] = now + _shift_delay + 0.060 + 0.105
        _state["shift_torque_cut_amp"] = _clamp(base * char_mul[3])
        _state["shift_surface_duck_until"] = now + _shift_delay + 0.155
        _state["shift_onset"] = now + _shift_delay  # haptic won't emit until this time
    if valid_gear:
        _state["last_gear"] = gear_now
    _shift_onset = float(_state.get("shift_onset", 0.0))
    _shift_ready = now >= _shift_onset  # wait for delay before emitting
    if _shift_ready and now <= float(_state.get("shift_kick_until", 0.0)):
        shift_kick = _scale_event(float(_state.get("shift_kick_amp", 0.0)), s)
    else:
        shift_kick = 0.0
    if _shift_ready and now <= float(_state.get("shift_click_until", 0.0)):
        shift_click = _scale_event(float(_state.get("shift_click_amp", 0.0)), s)
    if _shift_ready and now <= float(_state.get("shift_clunk_until", 0.0)):
        shift_clunk = _scale_event(float(_state.get("shift_clunk_amp", 0.0)), s)
    if _shift_ready and now <= float(_state.get("shift_rattle_until", 0.0)):
        shift_rattle = _scale_event(float(_state.get("shift_rattle_amp", 0.0)), s)
    if _shift_ready and now <= float(_state.get("shift_tail_until", 0.0)):
        shift_tail = _scale_event(float(_state.get("shift_tail_amp", 0.0)), s)
    if _shift_ready and now <= float(_state.get("shift_torque_cut_until", 0.0)):
        shift_torque_cut = _scale_event(float(_state.get("shift_torque_cut_amp", 0.0)), s)

    if not vehicle_flavor_enabled:
        idle_engine = launch_load = launch_release = boost_build = torque_surge = shift_kick = shift_click = shift_clunk = shift_rattle = shift_tail = shift_torque_cut = 0.0

    # Brake body supplement. ABS and pedal resistance remain trigger-owned; audio
    # adds only a restrained front-dive/body tick feeling.
    brake_slip = max(
        _side_max(t, "tire_slip_ratio", "left"), _side_max(t, "tire_slip_ratio", "right"),
        _side_max(t, "tire_combined_slip", "left"), _side_max(t, "tire_combined_slip", "right"),
    )
    brake_load_raw = brake_n * _speed_norm(speed, 18.0, 145.0) * (0.32 + 0.30 * lat_signal + 0.12 * wetness)
    abs_raw = _clamp((brake_slip - 0.68) / 1.15) * brake_n * _speed_norm(speed, 18.0, 100.0)
    if not bool(getattr(s, "haptic_brake_body_enabled", False)):
        brake_load_raw = 0.0
        abs_raw = 0.0
    brake_bias_l = 1.0 + (0.18 * lat_signal if lat_g < 0.0 else 0.0)
    brake_bias_r = 1.0 + (0.18 * lat_signal if lat_g > 0.0 else 0.0)
    brake_body_l = _smooth("brake_body_l", brake_load_raw * brake_bias_l, 0.42, 0.16)
    brake_body_r = _smooth("brake_body_r", brake_load_raw * brake_bias_r, 0.42, 0.16)
    abs_body_l = _scale_event(_smooth("abs_body_l", abs_raw * brake_bias_l, 0.62, 0.20), s) * _trigger_duck(s, "brake_abs")
    abs_body_r = _scale_event(_smooth("abs_body_r", abs_raw * brake_bias_r, 0.62, 0.20), s) * _trigger_duck(s, "brake_abs")

    rear_echo_l = _rear_echo("l", now)
    rear_echo_r = _rear_echo("r", now)

    # Surface + weather priority. Events must cut through background; background
    # should never mask a puddle/kerb/collision. This creates the 3-bus intent
    # before the audio renderer: continuous, vehicle/body, event.
    event_l = max(
        max(kerb["fl"], kerb["rl"]), puddle_l_now, max(bump["fl"], bump["rl"]),
        collision_l, scrape_l * 0.82, rear_echo_l * 0.70, abs_body_l * 0.55,
        surface_transition_l * 0.70, deep_water_l * 0.56, landing * 0.78, bottom_out * 0.92,
    )
    event_r = max(
        max(kerb["fr"], kerb["rr"]), puddle_r_now, max(bump["fr"], bump["rr"]),
        collision_r, scrape_r * 0.82, rear_echo_r * 0.70, abs_body_r * 0.55,
        surface_transition_r * 0.70, deep_water_r * 0.56, landing * 0.78, bottom_out * 0.92,
    )
    collision_duck_strength = _clamp(_gain(s, "haptic_collision_duck_strength", 0.88), 0.0, 1.2)
    collision_duck_min = _clamp(_gain(s, "haptic_collision_duck_min", 0.06), 0.02, 0.35)
    drift_side_l = max(slide_chaos_l, rear_breakaway_l, side_scrub_edge_l, tire_scrub_l, tire_smear_l, slip_sizzle_l, asphalt_drift_l, offroad_drift_l)
    drift_side_r = max(slide_chaos_r, rear_breakaway_r, side_scrub_edge_r, tire_scrub_r, tire_smear_r, slip_sizzle_r, asphalt_drift_r, offroad_drift_r)
    side_cue_l = max(weight_l, asphalt_grip_l, slide_l, understeer_l, oversteer_l, drift_side_l)
    side_cue_r = max(weight_r, asphalt_grip_r, slide_r, understeer_r, oversteer_r, drift_side_r)
    # --- REFACTORED: Removed texture-level ducking ---
    # Ducking now handled in a single stage at the mixer level.
    # Shift isolation is still done via zeroing in _render().
    # These are kept at 1.0 (bypass) to avoid 4-stage signal loss.
    continuous_duck_l = 1.0
    continuous_duck_r = 1.0
    vehicle_duck_l = 1.0
    vehicle_duck_r = 1.0

    road_l *= continuous_duck_l
    road_r *= continuous_duck_r
    gravel_l *= continuous_duck_l
    gravel_r *= continuous_duck_r
    rough_asphalt_l *= continuous_duck_l
    rough_asphalt_r *= continuous_duck_r
    dirt_l *= continuous_duck_l
    dirt_r *= continuous_duck_r
    grass_l *= continuous_duck_l
    grass_r *= continuous_duck_r
    wet_asphalt_l *= continuous_duck_l
    wet_asphalt_r *= continuous_duck_r
    mud_l *= continuous_duck_l
    mud_r *= continuous_duck_r
    spray_l *= continuous_duck_l
    spray_r *= continuous_duck_r
    ice_l *= continuous_duck_l
    ice_r *= continuous_duck_r
    packed_snow_l *= continuous_duck_l
    packed_snow_r *= continuous_duck_r
    loose_snow_l *= continuous_duck_l
    loose_snow_r *= continuous_duck_r
    slush_l *= continuous_duck_l
    slush_r *= continuous_duck_r
    sand_l *= continuous_duck_l
    sand_r *= continuous_duck_r
    thin_water_l *= continuous_duck_l
    thin_water_r *= continuous_duck_r
    deep_water_l *= continuous_duck_l
    deep_water_r *= continuous_duck_r
    wet_tire_tail_l *= continuous_duck_l
    wet_tire_tail_r *= continuous_duck_r

    weight_l *= vehicle_duck_l
    weight_r *= vehicle_duck_r
    asphalt_grip_l *= vehicle_duck_l
    asphalt_grip_r *= vehicle_duck_r
    slide_l *= vehicle_duck_l
    slide_r *= vehicle_duck_r
    wheel_l *= vehicle_duck_l
    wheel_r *= vehicle_duck_r
    scrub_l *= vehicle_duck_l
    scrub_r *= vehicle_duck_r
    brake_body_l *= vehicle_duck_l
    brake_body_r *= vehicle_duck_r
    understeer_l *= vehicle_duck_l
    understeer_r *= vehicle_duck_r
    oversteer_l *= vehicle_duck_l
    oversteer_r *= vehicle_duck_r
    slide_chaos_l *= vehicle_duck_l
    slide_chaos_r *= vehicle_duck_r
    rear_breakaway_l *= vehicle_duck_l
    rear_breakaway_r *= vehicle_duck_r
    side_scrub_edge_l *= vehicle_duck_l
    side_scrub_edge_r *= vehicle_duck_r
    tire_scrub_l *= vehicle_duck_l
    tire_scrub_r *= vehicle_duck_r
    tire_smear_l *= vehicle_duck_l
    tire_smear_r *= vehicle_duck_r
    slip_sizzle_l *= vehicle_duck_l
    slip_sizzle_r *= vehicle_duck_r
    asphalt_drift_l *= vehicle_duck_l
    asphalt_drift_r *= vehicle_duck_r
    offroad_drift_l *= vehicle_duck_l
    offroad_drift_r *= vehicle_duck_r

    # 6.2: below Forza ~90km/h, suppress body chatter that was perceived as cart-like.
    # Keep real collision/kerb/puddle/idle/shift events outside this gate.
    wheel_l *= low_speed_body_gate
    wheel_r *= low_speed_body_gate
    scrub_l *= low_speed_body_gate
    scrub_r *= low_speed_body_gate
    weight_l *= low_speed_body_gate
    weight_r *= low_speed_body_gate
    asphalt_grip_l *= low_speed_body_gate
    asphalt_grip_r *= low_speed_body_gate
    slide_l *= low_speed_body_gate
    slide_r *= low_speed_body_gate
    understeer_l *= low_speed_body_gate
    understeer_r *= low_speed_body_gate
    oversteer_l *= low_speed_body_gate
    oversteer_r *= low_speed_body_gate
    brake_body_l *= low_speed_body_gate
    brake_body_r *= low_speed_body_gate
    # Drift chaos gets a softer gate so deliberate low/mid-speed slides still shout.
    drift_gate = max(low_speed_body_gate, 0.35 + 0.65 * _speed_norm(speed, 50.0, 120.0))
    slide_chaos_l *= drift_gate
    slide_chaos_r *= drift_gate
    rear_breakaway_l *= drift_gate
    rear_breakaway_r *= drift_gate
    side_scrub_edge_l *= drift_gate
    side_scrub_edge_r *= drift_gate
    # Tire slip textures are allowed a little more presence at mid speed than body chaos.
    tire_gate = max(low_speed_body_gate, 0.45 + 0.55 * _speed_norm(speed, 45.0, 120.0))
    tire_scrub_l *= tire_gate
    tire_scrub_r *= tire_gate
    tire_smear_l *= tire_gate
    tire_smear_r *= tire_gate
    slip_sizzle_l *= tire_gate
    slip_sizzle_r *= tire_gate
    asphalt_drift_l *= tire_gate
    asphalt_drift_r *= tire_gate
    offroad_drift_l *= drift_gate
    offroad_drift_r *= drift_gate

    continuous_bus_l = max(road_l, gravel_l, rough_asphalt_l, dirt_l, grass_l, wet_asphalt_l, mud_l, spray_l, ice_l, packed_snow_l, loose_snow_l, slush_l, sand_l, thin_water_l, deep_water_l, wet_tire_tail_l)
    continuous_bus_r = max(road_r, gravel_r, rough_asphalt_r, dirt_r, grass_r, wet_asphalt_r, mud_r, spray_r, ice_r, packed_snow_r, loose_snow_r, slush_r, sand_r, thin_water_r, deep_water_r, wet_tire_tail_r)
    vehicle_bus_l = max(wheel_l, scrub_l, weight_l, asphalt_grip_l, slide_l, slide_chaos_l, rear_breakaway_l, side_scrub_edge_l, tire_scrub_l, tire_smear_l, slip_sizzle_l, asphalt_drift_l, offroad_drift_l, understeer_l, oversteer_l, four_wheel_slide, idle_engine, launch_load, boost_build, torque_surge, brake_body_l, landing, bottom_out)
    vehicle_bus_r = max(wheel_r, scrub_r, weight_r, asphalt_grip_r, slide_r, slide_chaos_r, rear_breakaway_r, side_scrub_edge_r, tire_scrub_r, tire_smear_r, slip_sizzle_r, asphalt_drift_r, offroad_drift_r, oversteer_r, understeer_r, four_wheel_slide, idle_engine, launch_load, boost_build, torque_surge, brake_body_r, landing, bottom_out)
    mix_l_est = continuous_bus_l + vehicle_bus_l + event_l
    mix_r_est = continuous_bus_r + vehicle_bus_r + event_r
    lr_delta = abs(mix_l_est - mix_r_est)
    center_body_level = max(idle_engine, launch_load, boost_build, torque_surge, shift_kick, shift_clunk, shift_tail, four_wheel_slide, landing, bottom_out)

    return HapticState(
        road_l=road_l, road_r=road_r,
        gravel_l=gravel_l, gravel_r=gravel_r,
        wheelspin_l=wheel_l, wheelspin_r=wheel_r,
        scrub_l=scrub_l, scrub_r=scrub_r,
        rough_asphalt_l=rough_asphalt_l, rough_asphalt_r=rough_asphalt_r,
        dirt_l=dirt_l, dirt_r=dirt_r,
        grass_l=grass_l, grass_r=grass_r,
        wet_asphalt_l=wet_asphalt_l, wet_asphalt_r=wet_asphalt_r,
        mud_l=mud_l, mud_r=mud_r,
        spray_l=spray_l, spray_r=spray_r,
        ice_l=ice_l, ice_r=ice_r,
        packed_snow_l=packed_snow_l, packed_snow_r=packed_snow_r,
        loose_snow_l=loose_snow_l, loose_snow_r=loose_snow_r,
        slush_l=slush_l, slush_r=slush_r,
        sand_l=sand_l, sand_r=sand_r,
        thin_water_l=thin_water_l, thin_water_r=thin_water_r,
        deep_water_l=deep_water_l, deep_water_r=deep_water_r,
        wet_tire_tail_l=wet_tire_tail_l, wet_tire_tail_r=wet_tire_tail_r,
        surface_transition_l=surface_transition_l, surface_transition_r=surface_transition_r,
        rear_echo_l=rear_echo_l, rear_echo_r=rear_echo_r,
        scrape_l=scrape_l, scrape_r=scrape_r,
        collision_crack=collision_crack,
        kerb_fl=kerb["fl"], kerb_fr=kerb["fr"], kerb_rl=kerb["rl"], kerb_rr=kerb["rr"],
        kerb_l=max(kerb["fl"], kerb["rl"]), kerb_r=max(kerb["fr"], kerb["rr"]),
        puddle_fl=puddle["fl"], puddle_fr=puddle["fr"], puddle_rl=puddle["rl"], puddle_rr=puddle["rr"],
        puddle_l=max(puddle["fl"], puddle["rl"]), puddle_r=max(puddle["fr"], puddle["rr"]),
        bump_fl=bump["fl"], bump_fr=bump["fr"], bump_rl=bump["rl"], bump_rr=bump["rr"],
        bump_l=max(bump["fl"], bump["rl"]), bump_r=max(bump["fr"], bump["rr"]),
        collision=collision, collision_l=collision_l, collision_r=collision_r,
        weight_l=weight_l, weight_r=weight_r,
        weight_pulse_l=pulse_l, weight_pulse_r=pulse_r,
        asphalt_grip_l=asphalt_grip_l, asphalt_grip_r=asphalt_grip_r,
        slide_l=slide_l, slide_r=slide_r,
        slide_pulse_l=slide_pulse_l, slide_pulse_r=slide_pulse_r,
        slide_chaos_l=slide_chaos_l, slide_chaos_r=slide_chaos_r,
        rear_breakaway_l=rear_breakaway_l, rear_breakaway_r=rear_breakaway_r,
        side_scrub_edge_l=side_scrub_edge_l, side_scrub_edge_r=side_scrub_edge_r,
        tire_scrub_l=tire_scrub_l, tire_scrub_r=tire_scrub_r,
        tire_smear_l=tire_smear_l, tire_smear_r=tire_smear_r,
        slip_sizzle_l=slip_sizzle_l, slip_sizzle_r=slip_sizzle_r,
        asphalt_drift_l=asphalt_drift_l, asphalt_drift_r=asphalt_drift_r,
        offroad_drift_l=offroad_drift_l, offroad_drift_r=offroad_drift_r,
        drift_confidence=drift_conf,
        understeer_l=understeer_l, understeer_r=understeer_r,
        oversteer_l=oversteer_l, oversteer_r=oversteer_r,
        four_wheel_slide=four_wheel_slide,
        airborne=airborne, landing=landing, bottom_out=bottom_out,
        tire_temp_grip=tire_temp_grip, vehicle_character=class_character,
        idle_engine=idle_engine,
        launch_load=launch_load,
        launch_release=launch_release,
        boost_build=boost_build,
        torque_surge=torque_surge,
        shift_kick=shift_kick,
        shift_click=shift_click, shift_clunk=shift_clunk, shift_rattle=shift_rattle,
        shift_tail=shift_tail, shift_torque_cut=shift_torque_cut,
        shift_character=shift_character,
        shift_gear=float(_state.get("shift_gear", 3.0)),
        brake_body_l=brake_body_l, brake_body_r=brake_body_r,
        abs_body_l=abs_body_l, abs_body_r=abs_body_r,
        wetness=wetness,
        ice_confidence=max(ice_l, ice_r),
        snow_confidence=max(packed_snow_l, packed_snow_r, loose_snow_l, loose_snow_r),
        slush_confidence=max(slush_l, slush_r),
        sand_confidence=max(sand_l, sand_r),
        surface_confidence=dominant_conf,
        dominant_surface=dominant_label,
        surface_transition=surface_transition_label,
        continuous_duck_l=continuous_duck_l, continuous_duck_r=continuous_duck_r,
        vehicle_duck_l=vehicle_duck_l, vehicle_duck_r=vehicle_duck_r,
        event_bus_l=event_l, event_bus_r=event_r,
        vehicle_bus_l=vehicle_bus_l, vehicle_bus_r=vehicle_bus_r,
        continuous_bus_l=continuous_bus_l, continuous_bus_r=continuous_bus_r,
        lr_delta=lr_delta,
        center_body_level=center_body_level,
        surface_gate=surface_motion_gate,
        speed_kmh=speed,
        accel_x=float(_tg(t, "accel_x", 0.0)),
        accel_y=float(_tg(t, "accel_y", 0.0)),
        accel_z=float(_tg(t, "accel_z", 0.0)),
        lateral_g_used=lat_g,
        # extended telemetry
        rpm_norm=rpm_norm,
        pitch_rate=pitch_rate,
        roll_rate=roll_rate,
        yaw_rate=yaw_rate,
        susp_velocity_l=susp_velocity_l,
        susp_velocity_r=susp_velocity_r,
        steer_velocity=steer_velocity,
        tire_temp_freq_mod=tire_temp_freq_mod,
        accel_longitudinal=accel_longitudinal,
        wheel_speed_diff=wheel_speed_diff,
        # engine enhancement
        engine_braking=engine_braking,
        corner_exit_torque=corner_exit_torque,
        turbo_spool=turbo_spool,
        engine_start=engine_start,
        cylinder_count=cylinder_count,
    )
