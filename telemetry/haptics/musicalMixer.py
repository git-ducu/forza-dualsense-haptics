# -*- coding: utf-8 -*-
"""Telemetry-to-haptic musical mixer helpers.

This module keeps the 2.0 SimHub/music-style layer math out of the audio
backend.  It deliberately does not touch the adaptive trigger writer: trigger
algorithms stay the reference feel, while this mixer makes whole-pad haptics
support those trigger events with body, glue and punch layers.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Mapping

from dsio.haptics.waveform import noise, noise_burst, pulse_train, envelope_preset

try:  # haptics_audio already requires numpy when rendering
    import numpy as np
except Exception:  # pragma: no cover
    np = None


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        x = float(v)
    except Exception:
        x = 0.0
    return max(lo, min(hi, x))


def setting(settings: Any, name: str, default: float = 0.0) -> float:
    return float(getattr(settings, name, default))


def wide_gain(settings: Any, name: str, default: float = 1.0, hi: float = 3.0, power: float = 1.30) -> float:
    """User-facing tactile gain mapping.

    Below 1.0 it is linear so reductions are predictable. Above 1.0 it bends
    upward, because earlier builds exposed wide sliders that still felt too
    small once the signal reached the DualSense actuator.
    """
    raw = clamp(setting(settings, name, default), 0.0, hi)
    if raw <= 1.0:
        return raw
    return min(hi ** power, raw ** power)


@dataclass(slots=True)
class MusicalFeatures:
    road_texture: float = 0.0
    load_body: float = 0.0
    tire_edge: float = 0.0
    shift_punch: float = 0.0
    impact_punch: float = 0.0
    bump_punch: float = 0.0
    grip_punch: float = 0.0
    rear_breakaway_l: float = 0.0
    rear_breakaway_r: float = 0.0
    left_weight: float = 0.0
    right_weight: float = 0.0
    # extended telemetry features
    rpm_texture: float = 0.0        # engine rev body buzz
    body_motion: float = 0.0        # combined pitch+roll motion intensity
    susp_roughness: float = 0.0     # suspension velocity → road roughness proxy
    # -- NEW onset transient --
    accel_onset: float = 0.0        # sudden acceleration (longitudinal G+)
    decel_onset: float = 0.0        # sudden deceleration (longitudinal G-)
    shift_engage: float = 0.0       # shift engagement transient


@dataclass(slots=True)
class MixerControls:
    bass_master: float = 1.0
    high_master: float = 1.0
    glue_master: float = 1.0
    low_glue: float = 0.46
    high_glue: float = 0.38
    punch_master: float = 1.0
    low_punch: float = 1.0
    high_punch: float = 1.0
    mid_duck: float = 0.38
    trigger_harmony: float = 1.0
    shift_high_support: float = 1.0
    shift_low_support: float = 1.0
    mid_min_gain: float = 0.62
    punch_sustain_blend: float = 0.42


@dataclass(slots=True)
class MixerDiagnostics:
    feature_road: float = 0.0
    feature_load: float = 0.0
    feature_tire_edge: float = 0.0
    punch_shift: float = 0.0
    punch_impact: float = 0.0
    punch_bump: float = 0.0
    punch_grip: float = 0.0
    punch_level: float = 0.0
    hard_punch: float = 0.0
    soft_punch: float = 0.0
    punch_edge_shift: float = 0.0
    punch_edge_impact: float = 0.0
    punch_edge_bump: float = 0.0
    punch_edge_grip: float = 0.0
    glue_level_l: float = 0.0
    glue_level_r: float = 0.0
    high_glue_level_l: float = 0.0
    high_glue_level_r: float = 0.0
    mid_duck_gain: float = 1.0
    low_punch_l: float = 0.0
    low_punch_r: float = 0.0
    high_punch_l: float = 0.0
    high_punch_r: float = 0.0

    def render_stats(self) -> dict[str, float]:
        return {"mix_" + k: float(v) for k, v in asdict(self).items()}


def _f(st: Any, name: str, default: float = 0.0) -> float:
    return float(getattr(st, name, default))


def extract_features(st: Any) -> MusicalFeatures:
    """Extract stable SimHub-style feature levels from HapticState.

    The detailed textures in haptics_audio stay intact.  These features are a
    broad control layer for musical glue/punch buses and diagnostics.
    """
    speed = _f(st, "speed_kmh")
    road_texture = clamp(max(
        (_f(st, "road_l") + _f(st, "road_r")) * 0.35,
        (_f(st, "rough_asphalt_l") + _f(st, "rough_asphalt_r")) * 0.35,
        (_f(st, "gravel_l") + _f(st, "gravel_r")) * 0.25,
        (_f(st, "dirt_l") + _f(st, "dirt_r")) * 0.25,
        (_f(st, "kerb_l") + _f(st, "kerb_r")) * 0.18,
    ))
    load_body = clamp(max(
        _f(st, "idle_engine") * 0.35,
        _f(st, "launch_load") * 0.58,
        _f(st, "launch_release") * 0.72,
        _f(st, "boost_build") * 0.42,
        _f(st, "torque_surge") * 0.62,
        clamp((speed - 135.0) / 160.0) * 0.40,
        _f(st, "center_body_level") * 0.22,
    ))
    tire_edge = clamp(max(
        _f(st, "asphalt_grip_l"), _f(st, "asphalt_grip_r"),
        _f(st, "side_scrub_edge_l"), _f(st, "side_scrub_edge_r"),
        _f(st, "slip_sizzle_l"), _f(st, "slip_sizzle_r"),
        _f(st, "wheelspin_l") * 0.65, _f(st, "wheelspin_r") * 0.65,
        _f(st, "abs_body_l") * 0.75, _f(st, "abs_body_r") * 0.75,
        _f(st, "understeer_l") * 0.55, _f(st, "understeer_r") * 0.55,
        _f(st, "oversteer_l") * 0.55, _f(st, "oversteer_r") * 0.55,
    ))
    shift_punch = clamp(max(
        _f(st, "shift_kick"), _f(st, "shift_clunk"), _f(st, "shift_click") * 0.72,
        _f(st, "shift_torque_cut") * 0.42,
    ))
    impact_punch = clamp(max(
        _f(st, "collision"), _f(st, "collision_crack") * 0.85,
        _f(st, "scrape_l") * 0.45, _f(st, "scrape_r") * 0.45,
    ))
    bump_punch = clamp(max(
        _f(st, "bump_fl"), _f(st, "bump_fr"), _f(st, "bump_rl"), _f(st, "bump_rr"),
        _f(st, "landing") * 0.78, _f(st, "bottom_out"),
    ))
    rear_l = _f(st, "rear_breakaway_l")
    rear_r = _f(st, "rear_breakaway_r")
    grip_punch = clamp(max(tire_edge * 0.72, rear_l * 0.55, rear_r * 0.55))
    # extended telemetry feature extraction
    rpm_texture = clamp(_f(st, "rpm_norm") * 0.65 + _f(st, "rpm_norm") ** 2 * 0.35)
    body_motion = clamp(max(
        _f(st, "pitch_rate") * 0.75,
        _f(st, "roll_rate") * 0.85,
        _f(st, "yaw_rate") * 0.55,
    ))
    susp_roughness = clamp(max(
        _f(st, "susp_velocity_l"),
        _f(st, "susp_velocity_r"),
    ))
    # -- NEW onset longitudinal G force --
    # -- force --
    accel_long = _f(st, "accel_longitudinal")
    accel_onset_raw = clamp(max(0.0, accel_long) * 1.2)  # positive direction only
    decel_onset_raw = clamp(max(0.0, -accel_long) * 1.2)  # decel direction only
    # -- shift_clunk torque_surge --
    shift_engage_raw = clamp(_f(st, "shift_clunk") * 0.5 + _f(st, "torque_surge") * 0.5)
    return MusicalFeatures(
        road_texture=road_texture,
        load_body=load_body,
        tire_edge=tire_edge,
        shift_punch=shift_punch,
        impact_punch=impact_punch,
        bump_punch=bump_punch,
        grip_punch=grip_punch,
        rear_breakaway_l=rear_l,
        rear_breakaway_r=rear_r,
        left_weight=clamp(_f(st, "weight_l") + _f(st, "slide_l") * 0.85),
        right_weight=clamp(_f(st, "weight_r") + _f(st, "slide_r") * 0.85),
        rpm_texture=rpm_texture,
        body_motion=body_motion,
        susp_roughness=susp_roughness,
        accel_onset=accel_onset_raw,
        decel_onset=decel_onset_raw,
        shift_engage=shift_engage_raw,
    )


def read_controls(settings: Any) -> MixerControls:
    trigger_shift_gain = max(
        setting(settings, "trigger_shift_kick_gain", 1.0),
        setting(settings, "trigger_shift_clack_gain", 1.0),
    )
    harmony = clamp(setting(settings, "haptic_trigger_harmony_gain", 1.0), 0.0, 1.5)
    # When trigger shift is strong, do not duplicate the finger-click too much in
    # audio haptics.  Keep the whole-pad low thump instead: trigger = click/clack,
    # audio haptics = drivetrain body.
    shift_high_support = max(0.68, 1.0 - max(0.0, trigger_shift_gain - 1.0) * 0.10 * harmony)
    shift_low_support = 1.0 + max(0.0, trigger_shift_gain - 1.0) * 0.08 * harmony
    return MixerControls(
        bass_master=wide_gain(settings, "haptic_bass_foundation_gain", 1.0),
        high_master=wide_gain(settings, "haptic_high_edge_gain", 1.0),
        glue_master=wide_gain(settings, "haptic_spectrum_glue_gain", 1.0),
        low_glue=wide_gain(settings, "haptic_low_mid_glue_strength", 0.22),
        high_glue=wide_gain(settings, "haptic_high_mid_glue_strength", 0.18),
        punch_master=wide_gain(settings, "haptic_event_punch_gain", 1.0),
        low_punch=wide_gain(settings, "haptic_low_impact_gain", 1.0),
        high_punch=wide_gain(settings, "haptic_high_impact_gain", 1.0),
        mid_duck=clamp(setting(settings, "haptic_mid_duck_on_punch", 0.22), 0.0, 0.75),  # raised from 0.18; now single duck point
        trigger_harmony=harmony,
        shift_high_support=shift_high_support,
        shift_low_support=shift_low_support,
        mid_min_gain=clamp(setting(settings, "haptic_mid_min_gain", 0.70), 0.30, 0.90),  # raised from 0.62; single-stage floor
        punch_sustain_blend=clamp(setting(settings, "haptic_punch_sustain_blend", 0.42), 0.0, 1.0),
    )



def pick_freq(settings: Any, name: str, default_hz: float, hz: Callable[[float], float], fallback_frac: float) -> float:
    """Read an absolute DualSense frequency setting with safe fallback."""
    try:
        val = float(getattr(settings, name, default_hz))
    except Exception:
        val = float(default_hz)
    if val <= 0.0:
        return hz(fallback_frac)
    return max(35.0, min(560.0, val))

def haptic_priority_from_state(st: Any, settings: Any) -> float:
    """Limiter priority using the same feature model as the musical mixer."""
    f = extract_features(st)
    shift = f.shift_punch * wide_gain(settings, "haptic_shift_master_gain", 1.0, hi=2.8) * 0.58
    impact = f.impact_punch * wide_gain(settings, "haptic_impact_master_gain", 1.0, hi=2.5) * 0.74
    bump = f.bump_punch * 0.42
    grip = f.grip_punch * 0.32
    return clamp(max(shift, impact, bump, grip))


def apply_musical_mix(
    *,
    st: Any,
    settings: Any,
    oscs: dict[str, Any],
    frames: int,
    sr: int,
    hz: Callable[[float], float],
    continuous_l: Any,
    continuous_r: Any,
    vehicle_l: Any,
    vehicle_r: Any,
    event_l: Any,
    event_r: Any,
    transients: Mapping[str, float] | None = None,
):
    """Apply 2.0 musical glue + punch stage.

    Returns updated buses and diagnostics.  Arrays are modified/reused for speed,
    but returned explicitly so haptics_audio can stay readable.
    """
    if np is None:
        return continuous_l, continuous_r, vehicle_l, vehicle_r, event_l, event_r, MixerDiagnostics()

    f = extract_features(st)
    c = read_controls(settings)
    diag = MixerDiagnostics(
        feature_road=f.road_texture,
        feature_load=f.load_body,
        feature_tire_edge=f.tire_edge,
        punch_shift=f.shift_punch,
        punch_impact=f.impact_punch,
        punch_bump=f.bump_punch,
        punch_grip=f.grip_punch,
    )

    transients = transients or {}
    t_shift = clamp(transients.get("shift", 0.0))
    t_impact = clamp(transients.get("impact", 0.0))
    t_bump = clamp(transients.get("bump", 0.0))
    t_grip = clamp(transients.get("grip", 0.0))
    # Hard events should feel like one-shot punches, not a sustained held buzz.
    # Blend a small sustained body component back in so the output does not feel
    # neutered when telemetry envelopes are long.
    sustain = c.punch_sustain_blend
    shift_hit = max(t_shift, f.shift_punch * sustain)
    impact_hit = max(t_impact, f.impact_punch * sustain)
    bump_hit = max(t_bump, f.bump_punch * min(0.72, sustain + 0.16))
    grip_hit = max(t_grip, f.grip_punch * min(0.82, sustain + 0.22))
    hard_punch = clamp(max(shift_hit, impact_hit, bump_hit))
    soft_punch = clamp(grip_hit * 0.78)
    punch_level = clamp(max(hard_punch, soft_punch) * c.punch_master)
    diag.punch_edge_shift = t_shift
    diag.punch_edge_impact = t_impact
    diag.punch_edge_bump = t_bump
    diag.punch_edge_grip = t_grip
    diag.hard_punch = hard_punch
    diag.soft_punch = soft_punch
    diag.punch_level = punch_level

    # Glue: low-mid and high-mid bridges.  This is not a punch; it makes added
    # bass/high feel attached to road/body texture instead of pasted on top.
    if c.glue_master > 0.0:
        glue_l = clamp(f.load_body * 0.60 + f.road_texture * 0.28 + f.left_weight * 0.22)
        glue_r = clamp(f.load_body * 0.60 + f.road_texture * 0.28 + f.right_weight * 0.22)
        diag.glue_level_l = glue_l
        diag.glue_level_r = glue_r
        if max(glue_l, glue_r) > 0.0 and c.low_glue > 0.0:
            low_hz_l = pick_freq(settings, "haptic_freq_low_mid_glue_hz", 128.0, hz, 0.18)
            low_hz_r = pick_freq(settings, "haptic_freq_low_mid_glue_hz", 128.0, hz, 0.19) * 1.015
            # harmonic oscillator for richer low-mid bridge feel
            low_mid_l = oscs["low_mid_glue_l"].harmonic(frames, sr, low_hz_l, (1.0, 0.35, 0.08)) * 0.44 + noise(frames, 0.040)
            low_mid_r = oscs["low_mid_glue_r"].harmonic(frames, sr, low_hz_r, (1.0, 0.35, 0.08)) * 0.44 + noise(frames, 0.040)
            vehicle_l += low_mid_l * glue_l * c.glue_master * c.bass_master * c.low_glue * 0.42
            vehicle_r += low_mid_r * glue_r * c.glue_master * c.bass_master * c.low_glue * 0.42

        hi_glue_l = clamp(f.tire_edge * 0.55 + f.road_texture * 0.18 + _f(st, "asphalt_drift_l") * 0.28 + _f(st, "tire_scrub_l") * 0.22)
        hi_glue_r = clamp(f.tire_edge * 0.55 + f.road_texture * 0.18 + _f(st, "asphalt_drift_r") * 0.28 + _f(st, "tire_scrub_r") * 0.22)
        diag.high_glue_level_l = hi_glue_l
        diag.high_glue_level_r = hi_glue_r
        if max(hi_glue_l, hi_glue_r) > 0.0 and c.high_glue > 0.0:
            high_hz_l = pick_freq(settings, "haptic_freq_high_mid_glue_hz", 298.0, hz, 0.62)
            high_hz_r = pick_freq(settings, "haptic_freq_high_mid_glue_hz", 298.0, hz, 0.64) * 1.012
            # harmonic for richer high-mid bridge, noise_burst for edge definition
            high_mid_l = oscs["high_mid_glue_l"].harmonic(frames, sr, high_hz_l, (1.0, 0.4, 0.12)) * 0.28 + noise_burst(frames, sr, 260.0, 0.15)
            high_mid_r = oscs["high_mid_glue_r"].harmonic(frames, sr, high_hz_r, (1.0, 0.4, 0.12)) * 0.28 + noise_burst(frames, sr, 260.0, 0.15)
            vehicle_l += high_mid_l * hi_glue_l * c.glue_master * c.high_master * c.high_glue * 0.30
            vehicle_r += high_mid_r * hi_glue_r * c.glue_master * c.high_master * c.high_glue * 0.30

    # Punch: event-only kick/snare lane.  It ducks the middle briefly but keeps
    # the transient forward.  Shift high support is intentionally below low body
    # support when trigger feedback already supplies strong finger clicks.
    if punch_level > 0.0:
        duck = max(c.mid_min_gain, 1.0 - c.mid_duck * punch_level)
        diag.mid_duck_gain = duck
        continuous_l *= duck
        continuous_r *= duck
        vehicle_l *= 1.0 - (1.0 - duck) * 0.38
        vehicle_r *= 1.0 - (1.0 - duck) * 0.38

        low_l = clamp(impact_hit * 0.95 + shift_hit * 0.72 * c.shift_low_support + bump_hit * 0.62 + f.rear_breakaway_l * 0.34)
        low_r = clamp(impact_hit * 0.95 + shift_hit * 0.72 * c.shift_low_support + bump_hit * 0.62 + f.rear_breakaway_r * 0.34)
        high_l = clamp(impact_hit * 0.72 + shift_hit * 0.46 * c.shift_high_support + grip_hit * 0.64 + _f(st, "wheelspin_l") * 0.30 + _f(st, "abs_body_l") * 0.42)
        high_r = clamp(impact_hit * 0.72 + shift_hit * 0.46 * c.shift_high_support + grip_hit * 0.64 + _f(st, "wheelspin_r") * 0.30 + _f(st, "abs_body_r") * 0.42)
        diag.low_punch_l = low_l
        diag.low_punch_r = low_r
        diag.high_punch_l = high_l
        diag.high_punch_r = high_r

        low_punch_hz = pick_freq(settings, "haptic_freq_punch_body_hz", 68.0, hz, 0.075)
        high_punch_hz = pick_freq(settings, "haptic_freq_punch_edge_hz", 430.0, hz, 0.98)
        # sub_punch for visceral low body, harmonic for richer high edge,
        # envelope_preset shapes both so they punch and decay naturally.
        punch_env = envelope_preset(frames, sr, "impact", attack_override=1.5, release_override=40.0)
        low_sig_l = (oscs["punch_low_l"].sub_punch(frames, sr, low_punch_hz, 1.2, 28.0) * 1.20 + pulse_train(frames, sr, 24.0, 0.18) * 0.36 + noise(frames, 0.035)) * punch_env
        low_sig_r = (oscs["punch_low_r"].sub_punch(frames, sr, low_punch_hz * 1.015, 1.2, 28.0) * 1.20 + pulse_train(frames, sr, 24.0, 0.18) * 0.36 + noise(frames, 0.035)) * punch_env
        high_sig_l = (oscs["punch_high_l"].harmonic(frames, sr, high_punch_hz, (1.0, 0.45, 0.12)) * 0.32 + noise_burst(frames, sr, 350.0, 0.58) * pulse_train(frames, sr, 96.0, 0.18)) * punch_env
        high_sig_r = (oscs["punch_high_r"].harmonic(frames, sr, high_punch_hz * 1.012, (1.0, 0.45, 0.12)) * 0.32 + noise_burst(frames, sr, 350.0, 0.58) * pulse_train(frames, sr, 98.0, 0.18)) * punch_env

        event_l += low_sig_l * low_l * c.punch_master * c.bass_master * c.low_punch * 0.54
        event_r += low_sig_r * low_r * c.punch_master * c.bass_master * c.low_punch * 0.54
        event_l += high_sig_l * high_l * c.punch_master * c.high_master * c.high_punch * 0.34
        event_r += high_sig_r * high_r * c.punch_master * c.high_master * c.high_punch * 0.34

    return continuous_l, continuous_r, vehicle_l, vehicle_r, event_l, event_r, diag
