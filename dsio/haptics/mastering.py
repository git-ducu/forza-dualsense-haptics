"""Final bus mastering for DHE DualSense haptics.

This is intentionally small and conservative.  The effect renderer and
haptic_mixer create the sound; this module only makes the final three buses sit
together like a mix: protect road-mid texture, smooth duck recovery, keep punch
from swallowing the mid bus, and expose useful diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import exp
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

from .mixer import clamp, setting


def _rms(x: Any) -> float:
    if np is None:
        return 0.0
    try:
        return float(np.sqrt(np.mean(x * x)))
    except Exception:
        return 0.0


@dataclass(slots=True)
class HapticMasteringDiagnostics:
    low_rms: float = 0.0
    road_mid_rms: float = 0.0
    surface_mid_rms: float = 0.0
    vehicle_rms: float = 0.0
    engine_rms: float = 0.0     # NEW: 엔진 버스 RMS
    event_rms: float = 0.0
    punch_to_mid_ratio: float = 0.0
    glue_to_mid_ratio: float = 0.0
    mid_protect_gain: float = 1.0
    sidechain_gain: float = 1.0
    event_trim_gain: float = 1.0
    soft_sat_drive: float = 0.0

    def render_stats(self) -> dict[str, float]:
        return {"mix_" + k: float(v) for k, v in asdict(self).items()}


class _Smoother:
    def __init__(self, value: float = 1.0):
        self.value = float(value)

    def update(self, target: float, dt_ms: float, attack_ms: float, release_ms: float) -> float:
        target = float(target)
        if target < self.value:
            tau = max(1.0, float(attack_ms))
        else:
            tau = max(1.0, float(release_ms))
        a = 1.0 - exp(-max(0.0, float(dt_ms)) / tau)
        self.value += (target - self.value) * a
        return self.value


class HapticMasteringChain:
    """Block-rate bus mastering state.

    Defaults are deliberately transparent.  It should not make the program feel
    nerfed; it only catches pathological event-vs-road masking and makes duck
    recovery smoother.
    """

    def __init__(self) -> None:
        self._sidechain = _Smoother(1.0)

    def process(
        self,
        *,
        st: Any = None,
        features: Any = None,
        settings: Any,
        frames: int,
        sr: int,
        continuous_l: Any,
        continuous_r: Any,
        vehicle_l: Any,
        vehicle_r: Any,
        engine_l: Any = None,  # NEW: 엔진 버스
        engine_r: Any = None,
        event_l: Any,
        event_r: Any,
    ):
        """4-bus 마스터링 프로세스.
        
        Engine bus receives less sidechain ducking from Event (preserve continuous sources).
        """
        diag = HapticMasteringDiagnostics()
        
        # 엔진 버스 기본값
        if engine_l is None:
            engine_l = np.zeros_like(continuous_l) if np is not None else continuous_l
        if engine_r is None:
            engine_r = np.zeros_like(continuous_r) if np is not None else continuous_r
        
        if np is None or not bool(getattr(settings, "haptic_mastering_enabled", True)):
            return continuous_l, continuous_r, vehicle_l, vehicle_r, engine_l, engine_r, event_l, event_r, diag

        dt_ms = 1000.0 * max(1, int(frames)) / max(1, int(sr))
        f = features
        hard_punch = clamp(max(
            getattr(f, 'impact_punch', 0.0),
            getattr(f, 'shift_punch', 0.0),
            getattr(f, 'bump_punch', 0.0),
        ))
        road_feature = clamp(
            getattr(f, 'road_texture', 0.0) + getattr(f, 'tire_edge', 0.0) * 0.22
        )

        cont_rms = max(_rms(continuous_l), _rms(continuous_r))
        veh_rms = max(_rms(vehicle_l), _rms(vehicle_r))
        eng_rms = max(_rms(engine_l), _rms(engine_r))  # NEW: 엔진 RMS
        event_rms = max(_rms(event_l), _rms(event_r))
        mid_rms = max(cont_rms, 0.18)  # perceptual floor so normal punch is not misread as masking
        diag.road_mid_rms = cont_rms
        diag.surface_mid_rms = cont_rms * road_feature
        diag.vehicle_rms = veh_rms
        diag.engine_rms = eng_rms  # NEW
        diag.event_rms = event_rms
        diag.low_rms = veh_rms
        diag.punch_to_mid_ratio = event_rms / mid_rms
        diag.glue_to_mid_ratio = veh_rms / mid_rms

        mid_floor = clamp(setting(settings, "haptic_mid_min_gain", 0.78), 0.30, 0.90)
        # Sidechain ducking: events duck the mid/surface bus so transients cut through.
        sidechain_depth = clamp(setting(settings, "haptic_mastering_sidechain_strength", 0.0), 0.0, 0.50)
        duck_target = 1.0 - sidechain_depth * clamp(event_rms / max(mid_rms, 0.01), 0.0, 1.0)
        attack = setting(settings, "haptic_duck_attack_ms", 4.0)
        release = setting(settings, "haptic_duck_release_ms", 110.0)
        sidechain_gain = self._sidechain.update(duck_target, dt_ms, attack, release)
        diag.sidechain_gain = sidechain_gain

        # Keep the real road-mid layer from disappearing.  Strong events can make
        # room, but they cannot zero out the texture bus unless the user disables
        # mid protection.
        if bool(getattr(settings, "haptic_mid_protect_enabled", True)) and road_feature > 0.03:
            protected = max(mid_floor, sidechain_gain)
            continuous_l *= protected
            continuous_r *= protected
            diag.mid_protect_gain = protected
        else:
            continuous_l *= sidechain_gain
            continuous_r *= sidechain_gain
            diag.mid_protect_gain = sidechain_gain

        # --- REFACTORED: Vehicle bus ducking disabled (single-stage duck in mixer) ---
        # veh_duck_depth was 0.06; now bypassed to avoid 4-stage signal loss.
        # Event priority is handled entirely at the mixer punch stage.

        # Event-to-mid ratio guard.  Very high limit by default: it is not a
        # limiter for normal punch, only a guard against the event bus eating road.
        limit = max(8.0, setting(settings, "haptic_punch_to_mid_limit", 55.0))
        if bool(getattr(settings, "haptic_mid_protect_enabled", True)) and diag.punch_to_mid_ratio > limit:
            over = min(1.0, (diag.punch_to_mid_ratio - limit) / max(1.0, limit))
            trim = 1.0 - over * clamp(setting(settings, "haptic_event_ratio_trim", 0.20), 0.0, 0.65)
            event_l *= trim
            event_r *= trim
            diag.event_trim_gain = trim
        else:
            diag.event_trim_gain = 1.0

        # Mild soft saturation prevents hard clipping before the final limiter.
        # Event bus gets the strongest saturation; continuous/vehicle get lighter
        # treatment that only engages when their RMS is elevated.
        drive = clamp(setting(settings, "haptic_mastering_soft_saturation", 0.03), 0.0, 0.45)
        diag.soft_sat_drive = drive
        if drive > 0.0:
            # Event bus: bypass tanh so shift/collision transients pass
            # through at their true amplitude. The final limiter + np.clip
            # provide safety; tanh was flattening all amplitudes to ~0.87
            # regardless of input, killing any perceived loudness difference.
            # continuous bus — lighter saturation, only when signal is hot
            if cont_rms > 0.45:
                k_cont = 1.0 + drive * 0.7
                continuous_l = np.tanh(continuous_l * k_cont) / k_cont
                continuous_r = np.tanh(continuous_r * k_cont) / k_cont
            # vehicle bus — medium saturation when signal is hot
            if veh_rms > 0.40:
                k_veh = 1.0 + drive * 1.2
                vehicle_l = np.tanh(vehicle_l * k_veh) / k_veh
                vehicle_r = np.tanh(vehicle_r * k_veh) / k_veh
            # engine bus — light saturation (preserve continuous source character)
            if eng_rms > 0.50:
                k_eng = 1.0 + drive * 0.5
                engine_l = np.tanh(engine_l * k_eng) / k_eng
                engine_r = np.tanh(engine_r * k_eng) / k_eng

        # High-frequency ratio cap. The shimmer layer (250-400Hz) must stay
        # below a fraction of the other buses to avoid "buzzy" dominance over
        # bass/mid. Only activate when vehicle+event buses have content — during
        # quiet cruising the continuous bus (road textures) should not be ducked.
        hf_cap = clamp(setting(settings, "haptic_high_shimmer_cap", 0.30), 0.05, 0.60)
        other_rms = veh_rms + event_rms + eng_rms  # include engine in other_rms
        if cont_rms > 0.01 and other_rms > 0.01:
            hf_ratio = cont_rms / max(0.01, other_rms)
            if hf_ratio > (1.0 + hf_cap):
                hf_trim = (1.0 + hf_cap) / hf_ratio
                continuous_l *= hf_trim
                continuous_r *= hf_trim

        return continuous_l, continuous_r, vehicle_l, vehicle_r, engine_l, engine_r, event_l, event_r, diag
