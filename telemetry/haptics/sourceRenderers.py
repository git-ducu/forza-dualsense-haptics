"""
Forza Horizon Source Renderers --concrete haptic effect implementations.

Each renderer produces samples for one haptic source (idle, RPM, turbo, etc.)
and outputs to a specific bus. BusMixer collects all outputs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dsio.haptics.bus import HapticBus
from dsio.haptics.waveform import Osc
from dsio.haptics.renderer import (
    SourceOutput, RenderContext, ResponseFilter, FILTER_PRESETS, SourceRenderer,
)

if TYPE_CHECKING:
    from .audioEngine import HapticState



# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Utility
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# --틸리티 --수
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
def noise(frames: int, amp: float = 1.0) -> np.ndarray:
    """--이──이──성."""
    return (np.random.random(frames).astype(np.float32) * 2.0 - 1.0) * amp


def pulse_train(frames: int, sr: int, freq: float, duty: float = 0.5) -> np.ndarray:
    """--스 --레──성."""
    if freq <= 0 or duty <= 0:
        return np.zeros(frames, dtype=np.float32)
    period = sr / freq
    t = np.arange(frames, dtype=np.float32)
    phase = (t % period) / period
    return (phase < duty).astype(np.float32)


def _gain(value: float, lo: float, hi: float) -> float:
    """값을 범위──램--"""
    return max(lo, min(hi, float(value)))


def _ga(obj, attr: str, default):
    """getattr --축."""
    return getattr(obj, attr, default)


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Engine Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class IdleRenderer(SourceRenderer):
    """공회--진동 --더--"""
    
    def __init__(self):
        super().__init__("idle_engine", HapticBus.ENGINE)
        self._osc_low = Osc()
        self._osc_pulse = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        idle_amp = float(getattr(st, "idle_engine", 0.0))
        if idle_amp <= 0.0:
            return self._empty_output(ctx)
        
        # --정--서 게인/--프--스 --기
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_idle_strength", 0.38), 0.0, 2.0) * self._gain
        roughness = _gain(_ga(settings, "haptic_idle_roughness", 0.45), 0.0, 1.0)
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --이브폼 --성
        freq_low = ctx.hz(0.05 + roughness * 0.08)
        freq_pulse = ctx.hz(0.12)
        
        low = self._osc_low.sine(ctx.frames, ctx.sr, freq_low)
        chug = pulse_train(ctx.frames, ctx.sr, 8.0 + roughness * 10.0, 0.26) * \
               self._osc_pulse.sine(ctx.frames, ctx.sr, freq_pulse)
        
        sig = low * (0.86 - roughness * 0.14) + chug * (0.30 + roughness * 0.30) + \
              noise(ctx.frames, 0.055 * roughness)
        
        # 최종 출력
        amp = idle_amp * strength
        samples = sig * amp
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class RpmRenderer(SourceRenderer):
    """RPM 차체 진동 --더--"""
    
    def __init__(self):
        super().__init__("rpm_texture", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        rpm_norm = float(getattr(st, "rpm_norm", 0.0))
        if rpm_norm <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_rpm_texture_gain", 0.5), 0.0, 1.5) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # LRA sweet spot: 65-180Hz, rpm_norm maps idle--redline
        freq = 65.0 + rpm_norm * 115.0
        
        # --이브폼: sine + --간──이--        sig = self._osc.sine(ctx.frames, ctx.sr, freq) * 0.7 + noise(ctx.frames, 0.2)
        
        # RPM──른 진폭 (고RPM--수--강함)
        amp = rpm_norm * strength * 0.6
        samples = sig * amp
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Engine Enhancement Renderers (6──규 기능)
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class RpmHarmonicsRenderer(SourceRenderer):
    """RPM 기반 --모--스 --더--
    
    --린──에 --른 배음 추──4/6/8기통 --낌 차별--
    - 4기통: 기본 주파--+ 2배음 (밸런--드)
    - 6기통: 기본 + 1.5배음 + 3배음 (부--러--)
    - 8기통: 기본 + -- --브───(--블)
    """
    
    def __init__(self):
        super().__init__("rpm_harmonics", HapticBus.ENGINE)
        self._osc_fund = Osc()
        self._osc_h1 = Osc()
        self._osc_h2 = Osc()
        self._osc_sub = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        rpm_norm = float(getattr(st, "rpm_norm", 0.0))
        if rpm_norm < 0.15:  # idle --하--무시
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_rpm_harmonics_strength", 0.45), 0.0, 1.5) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --린──추정 (telemetry──정--서)
        cyl = int(getattr(st, "cylinder_count", 4))
        
        # 기본 주파-- RPM 비-- (40-120Hz)
        fund_freq = 40.0 + rpm_norm * 80.0
        
        # 기본--        fund = self._osc_fund.sine(ctx.frames, ctx.sr, fund_freq)
        
        if cyl <= 4:
            # 4기통: 2배음 강조 (기계──낌)
            h1 = self._osc_h1.sine(ctx.frames, ctx.sr, min(fund_freq * 2.0, 180.0)) * 0.35
            # FIX: h2 --한 180Hz (LRA sweet spot). --래 480Hz--무진--            h2 = self._osc_h2.sine(ctx.frames, ctx.sr, min(fund_freq * 3.0, 180.0)) * 0.08
            sig = fund * 0.55 + h1 + h2
        elif cyl <= 6:
            # 6기통: 1.5배음 + 3배음 (부--럽--균형--힌)
            h1 = self._osc_h1.sine(ctx.frames, ctx.sr, min(fund_freq * 1.5, 180.0)) * 0.30
            h2 = self._osc_h2.sine(ctx.frames, ctx.sr, min(fund_freq * 2.5, 180.0)) * 0.15
            sig = fund * 0.50 + h1 + h2
        else:
            # 8기통+: --브───강조 (깊-- --블)
            sub = self._osc_sub.sine(ctx.frames, ctx.sr, max(30.0, fund_freq * 0.5)) * 0.40
            h1 = self._osc_h1.sine(ctx.frames, ctx.sr, min(fund_freq * 2.0, 170.0)) * 0.20
            sig = fund * 0.40 + sub + h1
        
        # RPM──라 강도 증--
        amp = rpm_norm * strength * 0.5
        samples = (sig * amp).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class RedlineWarningRenderer(SourceRenderer):
    """--드--인 경고 --더--
    
    RPM 90%+ ──스 진동--로 --프───밍 --림.
    DualSense LRA--서 --실──껴지--빠른 --스.
    """
    
    def __init__(self):
        super().__init__("redline_warning", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        rpm_norm = float(getattr(st, "rpm_norm", 0.0))

        # Dynamic redline threshold based on usable RPM range (matches trigger logic)
        max_rpm = float(getattr(st, "max_rpm", 0.0))
        idle_rpm = float(getattr(st, "idle_rpm", 0.0))
        warning_width = float(getattr(ctx.settings, "haptic_redline_warning_width", 0.08))
        if max_rpm > 0 and idle_rpm >= 0:
            usable_range = max_rpm - idle_rpm
            margin_ratio = (usable_range * warning_width) / max_rpm
            redline_threshold = max(0.70, 0.93 - margin_ratio)
        else:
            redline_threshold = 0.90
        
        if rpm_norm < redline_threshold:
            return self._empty_output(ctx)
        
        # Duck haptic if trigger redline_pulse is also active above rev limiter threshold
        trigger_redline_on = bool(getattr(ctx.settings, "enable_trigger_redline_pulse", True))
        rev_limit_ratio = float(getattr(ctx.settings, "rev_limit_ratio", 0.93))
        if trigger_redline_on and rpm_norm >= rev_limit_ratio:
            duck_factor = 0.5
        else:
            duck_factor = 1.0
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_redline_warning_strength", 0.65), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --드--인 초과 --도 (0~1)
        over_redline = min(1.0, (rpm_norm - redline_threshold) / (1.0 - redline_threshold))
        
        # --스 주파-- 12Hz --25Hz (--험--에 --라 증--)
        pulse_freq = 12.0 + over_redline * 13.0
        
        # --스 --레--+ 캐리--(100Hz - LRA sweet spot)
        pulse = pulse_train(ctx.frames, ctx.sr, pulse_freq, 0.50)
        carrier = self._osc.sine(ctx.frames, ctx.sr, 100.0)
        
        sig = pulse * carrier
        amp = (0.5 + over_redline * 0.5) * strength * duck_factor
        samples = (sig * amp).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class TurboSpoolRenderer(SourceRenderer):
    """--보 ── --더--
    
    --보 빌드──고주──슬 --낌.
    부--트 증-- --도--비──미세 진동.
    """
    
    def __init__(self):
        super().__init__("turbo_spool", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        # haptic_textures.py--서 ── delta 계산───용
        spool_level = float(getattr(st, "turbo_spool", 0.0))
        
        if spool_level <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_turbo_spool_strength", 0.40), 0.0, 1.5) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # FIX: 180-280Hz --120-165Hz. LRA sweet spot --에--AM--로 "--슬" --현
        freq = 120.0 + spool_level * 45.0  # 120-165Hz (sweet spot 중앙)
        
        # AM modulation: 고속 진폭 변조로 "--이--잉" --낌
        am_freq = 8.0 + spool_level * 12.0  # 8-20Hz AM
        am = 0.6 + 0.4 * np.sin(2.0 * np.pi * am_freq * np.arange(ctx.frames, dtype=np.float32) / ctx.sr)
        
        sig = self._osc.sine(ctx.frames, ctx.sr, freq) * 0.65 * am + noise(ctx.frames, 0.20)
        amp = spool_level * strength * 0.45
        samples = (sig * amp).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class EngineBrakingRenderer(SourceRenderer):
    """--진 브레--킹 --더--
    
    감속──진 ───낌 (RPM --고 --로-- 0──.
    --주파 ─── + --간──블.
    """
    
    def __init__(self):
        super().__init__("engine_braking", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        engine_braking = float(getattr(st, "engine_braking", 0.0))
        
        if engine_braking <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_engine_braking_strength", 0.50), 0.0, 1.5) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # FIX: --주파 --블 (48-65Hz) - 35Hz--LRA --한--라 --함
        freq = 48.0 + engine_braking * 17.0
        
        sig = self._osc.sine(ctx.frames, ctx.sr, freq) * 0.75 + noise(ctx.frames, 0.18)
        amp = engine_braking * strength * 0.5
        samples = (sig * amp).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class CornerExitTorqueRenderer(SourceRenderer):
    """코너 출구 --크 --더--
    
    코너 출구--서 --워────크 --달 --낌.
    --티--링 복-- + 가--시 짧-- --크 ──
    """
    
    def __init__(self):
        super().__init__("corner_exit_torque", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        corner_exit = float(getattr(st, "corner_exit_torque", 0.0))
        
        if corner_exit <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_corner_exit_strength", 0.55), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # 중───크 --달 (55Hz) + attack envelope
        freq = 55.0
        
        sig = self._osc.sine(ctx.frames, ctx.sr, freq) * 0.70 + noise(ctx.frames, 0.20)
        # Attack envelope: 급격──라갔다 --서───
        t = np.arange(ctx.frames, dtype=np.float32) / float(ctx.sr)
        attack_env = np.minimum(1.0, t / 0.015)  # 15ms attack
        amp = corner_exit * strength * 0.6
        samples = (sig * amp * attack_env).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class EngineStartRenderer(SourceRenderer):
    """--동 --퀀──더--
    
    차량 --동 ────모터 ──화 --퀀--
    게임--서 차량 --택/리스───낌.
    """
    
    def __init__(self):
        super().__init__("engine_start", HapticBus.EVENT)
        self._osc_starter = Osc()
        self._osc_ignite = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        engine_start = float(getattr(st, "engine_start", 0.0))
        
        if engine_start <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_engine_start_strength", 0.70), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # FIX: ───모터 (빠른 --전-- + --화 ──(45--2Hz)
        starter = self._osc_starter.sine(ctx.frames, ctx.sr, 85.0) * 0.5
        starter += pulse_train(ctx.frames, ctx.sr, 20.0, 0.35) * 0.3
        
        # --화 --간 ────(52Hz - LRA --전 범위)
        ignite = self._osc_ignite.sine(ctx.frames, ctx.sr, 52.0) * 0.65
        
        sig = starter * 0.6 + ignite * 0.4
        amp = engine_start * strength
        samples = (sig * amp).astype(np.float32)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class LaunchRenderer(SourceRenderer):
    """발진 부──더--"""
    
    def __init__(self):
        super().__init__("launch_load", HapticBus.ENGINE)
        self._osc_load = Osc()
        self._osc_rough = Osc()
        self._osc_release = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        launch_load = float(getattr(st, "launch_load", 0.0))
        launch_release = float(getattr(st, "launch_release", 0.0))
        
        if launch_load <= 0.0 and launch_release <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_launch_strength", 0.55), 0.0, 2.0) * self._gain
        roughness = _gain(_ga(settings, "haptic_launch_roughness", 0.65), 0.0, 1.0)
        
        samples = np.zeros(ctx.frames, dtype=np.float32)
        
        if launch_load > 0.0 and strength > 0.0:
            load_sig = self._osc_load.sine(ctx.frames, ctx.sr, ctx.hz(0.10 + roughness * 0.15)) * 0.65
            load_sig += noise(ctx.frames, 0.20 + roughness * 0.18)
            load_sig += pulse_train(ctx.frames, ctx.sr, 12.0 + roughness * 18.0, 0.32) * \
                        self._osc_rough.sine(ctx.frames, ctx.sr, ctx.hz(0.24)) * 0.25
            samples += load_sig * launch_load * strength
        
        if launch_release > 0.0:
            release_strength = _gain(_ga(settings, "haptic_launch_release_thump", 0.55), 0.0, 2.0)
            if release_strength > 0.0:
                rel = self._osc_release.sine(ctx.frames, ctx.sr, ctx.hz(0.08)) * 0.85
                rel += noise(ctx.frames, 0.16)
                samples += rel * launch_release * release_strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Surface Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class RoadTextureRenderer(SourceRenderer):
    """--면 --스──더───팩--반응--
    
    --속 buzz --거. --스--션 --도 --파--크(--차/--음-- --에--짧-- burst.
    --상──로--= 거의 무음, --면 불연--점--서 "--걱" 충격.
    """
    
    def __init__(self):
        super().__init__("road_texture", HapticBus.SURFACE)
        self._osc_l = Osc()
        self._osc_r = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        road_l = float(getattr(st, "road_l", 0.0))
        road_r = float(getattr(st, "road_r", 0.0))
        
        if road_l <= 0.0 and road_r <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_road_gain", 0.24), 0.0, 1.5) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --팩--게이-- --스--션 --도가 threshold --상──만 출력
        susp_v_l = _gain(getattr(st, "susp_velocity_l", 0.0), 0.0, 1.0)
        susp_v_r = _gain(getattr(st, "susp_velocity_r", 0.0), 0.0, 1.0)
        threshold = 0.08
        impact_l = max(0.0, susp_v_l - threshold) / (1.0 - threshold)
        impact_r = max(0.0, susp_v_r - threshold) / (1.0 - threshold)
        
        if max(impact_l, impact_r) <= 0.0:
            return self._empty_output(ctx)
        
        # Burst --형: 85-130Hz 중──"--걱" (--속 sine --님)
        burst_freq = 85.0 + min(45.0, ctx.speed_kmh * 0.15)
        
        sig_l = self._osc_l.sine(ctx.frames, ctx.sr, burst_freq) * 0.70 + noise(ctx.frames, 0.25)
        sig_r = self._osc_r.sine(ctx.frames, ctx.sr, burst_freq * 1.02) * 0.70 + noise(ctx.frames, 0.25)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=(sig_l * road_l * impact_l * strength).astype(np.float32),
            samples_r=(sig_r * road_r * impact_r * strength).astype(np.float32),
        )
        output.compute_levels()
        return output


class GravelRenderer(SourceRenderer):
    """--갈/--프로드 --더--"""
    
    def __init__(self):
        super().__init__("gravel", HapticBus.SURFACE)
        self._osc_l = Osc()
        self._osc_r = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        gravel_l = float(getattr(st, "gravel_l", 0.0))
        gravel_r = float(getattr(st, "gravel_r", 0.0))
        
        if gravel_l <= 0.0 and gravel_r <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_gravel_gain", 0.5), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        speed = ctx.speed_kmh
        off_density = 0.22 + 0.78 * min(1.0, speed / 95.0)
        
        jitter_l = pulse_train(ctx.frames, ctx.sr, 7.0 + min(38.0, speed * 0.17), 0.22 + 0.16 * off_density)
        jitter_r = pulse_train(ctx.frames, ctx.sr, 8.5 + min(38.0, speed * 0.16), 0.20 + 0.16 * off_density)
        
        base_freq = 118.0 + min(46.0, speed * 0.08)
        base_l = self._osc_l.sine(ctx.frames, ctx.sr, base_freq)
        base_r = self._osc_r.sine(ctx.frames, ctx.sr, base_freq * 1.035)
        
        n_l = noise(ctx.frames, 0.68) * (0.45 + jitter_l * 0.65)
        n_r = noise(ctx.frames, 0.68) * (0.45 + jitter_r * 0.65)
        
        sig_l = base_l * 0.62 + n_l
        sig_r = base_r * 0.62 + n_r
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=(sig_l * gravel_l * strength).astype(np.float32),
            samples_r=(sig_r * gravel_r * strength).astype(np.float32),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Event Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class CollisionRenderer(SourceRenderer):
    """충돌 --더--"""
    
    def __init__(self):
        super().__init__("collision", HapticBus.EVENT)
        self._osc_low = Osc()
        self._osc_hi = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        collision = float(getattr(st, "collision", 0.0))
        if collision <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_collision_gain", 0.72), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # ──+ 고역 --랙
        low_freq = ctx.hz(0.08)
        hi_freq = ctx.hz(0.92)
        
        low = self._osc_low.sine(ctx.frames, ctx.sr, low_freq) * 0.7
        hi = self._osc_hi.sine(ctx.frames, ctx.sr, hi_freq) * 0.4 + noise(ctx.frames, 0.3)
        
        sig = (low * 0.65 + hi * 0.35) * collision * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=sig.astype(np.float32),
            samples_r=sig.astype(np.float32),
        )
        output.compute_levels()
        return output


class ShiftRenderer(SourceRenderer):
    """기어 변──더--"""
    
    def __init__(self):
        super().__init__("shift", HapticBus.EVENT)
        self._osc_click = Osc()
        self._osc_clunk = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        shift_click = float(getattr(st, "shift_click", 0.0))
        shift_clunk = float(getattr(st, "shift_clunk", 0.0))
        
        if shift_click <= 0.0 and shift_clunk <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        master = _gain(_ga(settings, "haptic_shift_master_gain", 1.0), 0.0, 2.5) * self._gain
        
        if master <= 0.0:
            return self._empty_output(ctx)
        
        samples = np.zeros(ctx.frames, dtype=np.float32)
        
        if shift_click > 0.0:
            click_strength = _gain(_ga(settings, "haptic_shift_click_strength", 0.9), 0.0, 2.0)
            # FIX: 376Hz--45Hz. LRA sweet spot --에--짧-- burst --성
            click = self._osc_click.sine(ctx.frames, ctx.sr, 145.0) * 0.6 + noise(ctx.frames, 0.35)
            samples += click * shift_click * click_strength * master
        
        if shift_clunk > 0.0:
            clunk_strength = _gain(_ga(settings, "haptic_shift_clunk_strength", 0.9), 0.0, 2.0)
            clunk = self._osc_clunk.sine(ctx.frames, ctx.sr, ctx.hz(0.15)) * 0.7 + noise(ctx.frames, 0.2)
            samples += clunk * shift_clunk * clunk_strength * master
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class ShiftEngagementRenderer(SourceRenderer):
    """변───크 --달 충격 --더--(Transient BURST).
    
    --용──드-- "변--하──밀릴때 --번--변--충격같-- --형--로"
    - LRA --리: --속 sine = "부르르" (--, 짧-- burst = "-- (--
    - 80Hz × 4 cycles = 50ms burst
    """
    
    def __init__(self):
        super().__init__("shift_engagement", HapticBus.EVENT)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        engagement = float(getattr(st, "shift_engagement", 0.0))
        
        if engagement <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_shift_engagement_strength", 0.65), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # BURST 방식: 80Hz × 4 cycles = 50ms --"--
        burst_hz = 80.0
        burst_cycles = 4.0
        burst_dur = burst_cycles / burst_hz  # 50ms
        burst_samples = min(ctx.frames, int(burst_dur * ctx.sr))
        
        # --능 최적-- burst 부분만 계산, --머지--0
        samples = np.zeros(ctx.frames, dtype=np.float32)
        t = np.arange(burst_samples, dtype=np.float32) / float(ctx.sr)
        burst = np.sign(np.sin(2.0 * np.pi * burst_hz * t))  # square wave for max LRA excursion
        samples[:burst_samples] = burst * engagement * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class AccelOnsetRenderer(SourceRenderer):
    """급───작 --간 충격 --더--(Transient BURST).
    
    --용──드-- "가--할──g 충격──번──다"
    - LRA --리: 짧-- burst(3-5 cycles)--야 "--
    - 90Hz × 4 cycles = 44ms burst
    """
    
    def __init__(self):
        super().__init__("accel_onset", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        accel = float(getattr(st, "accel_onset", 0.0))
        
        if accel <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_accel_onset_strength", 0.55), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # BURST 방식: 90Hz × 4 cycles = 44ms --"--
        burst_hz = 90.0
        burst_cycles = 4.0
        burst_dur = burst_cycles / burst_hz
        burst_samples = min(ctx.frames, int(burst_dur * ctx.sr))
        
        # --능 최적-- burst 부분만 계산
        samples = np.zeros(ctx.frames, dtype=np.float32)
        t = np.arange(burst_samples, dtype=np.float32) / float(ctx.sr)
        burst = np.sign(np.sin(2.0 * np.pi * burst_hz * t))
        samples[:burst_samples] = burst * accel * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class DecelOnsetRenderer(SourceRenderer):
    """급감──작 --간 충격 --더--(Transient BURST).
    
    --용──드-- "감속--때 --g 충격──번──다"
    - LRA --리: 짧-- burst(3-5 cycles)--야 "--
    - 75Hz × 5 cycles = 67ms burst (감속-- --간 --묵직--게)
    """
    
    def __init__(self):
        super().__init__("decel_onset", HapticBus.EVENT)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        decel = float(getattr(st, "decel_onset", 0.0))
        
        if decel <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_decel_onset_strength", 0.50), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # BURST 방식: 75Hz × 5 cycles = 67ms --"-- (감속-- 묵직)
        burst_hz = 75.0
        burst_cycles = 5.0
        burst_dur = burst_cycles / burst_hz
        burst_samples = min(ctx.frames, int(burst_dur * ctx.sr))
        
        # --능 최적-- burst 부분만 계산
        samples = np.zeros(ctx.frames, dtype=np.float32)
        t = np.arange(burst_samples, dtype=np.float32) / float(ctx.sr)
        burst = np.sign(np.sin(2.0 * np.pi * burst_hz * t))
        samples[:burst_samples] = burst * decel * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# Vehicle Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class SlideRenderer(SourceRenderer):
    """--라--드/--리--트 --더--"""
    
    def __init__(self):
        super().__init__("slide", HapticBus.VEHICLE)
        self._osc_l = Osc()
        self._osc_r = Osc()
        self._osc_chaos_l = Osc()
        self._osc_chaos_r = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        slide_l = float(getattr(st, "slide_l", 0.0))
        slide_r = float(getattr(st, "slide_r", 0.0))
        chaos_l = float(getattr(st, "slide_chaos_l", 0.0))
        chaos_r = float(getattr(st, "slide_chaos_r", 0.0))
        
        if max(slide_l, slide_r, chaos_l, chaos_r) <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        slide_strength = _gain(_ga(settings, "haptic_slide_body_strength", 0.55), 0.0, 2.0) * self._gain
        chaos_strength = _gain(_ga(settings, "haptic_slide_chaos_strength", 0.74), 0.0, 2.0)
        
        samples_l = np.zeros(ctx.frames, dtype=np.float32)
        samples_r = np.zeros(ctx.frames, dtype=np.float32)
        
        if max(slide_l, slide_r) > 0.0 and slide_strength > 0.0:
            sig_l = self._osc_l.sine(ctx.frames, ctx.sr, ctx.hz(0.32)) * 0.6 + noise(ctx.frames, 0.3)
            sig_r = self._osc_r.sine(ctx.frames, ctx.sr, ctx.hz(0.34)) * 0.6 + noise(ctx.frames, 0.3)
            samples_l += sig_l * slide_l * slide_strength
            samples_r += sig_r * slide_r * slide_strength
        
        if max(chaos_l, chaos_r) > 0.0 and chaos_strength > 0.0:
            c_l = self._osc_chaos_l.sine(ctx.frames, ctx.sr, ctx.hz(0.28)) * 0.5 + noise(ctx.frames, 0.45)
            c_r = self._osc_chaos_r.sine(ctx.frames, ctx.sr, ctx.hz(0.30)) * 0.5 + noise(ctx.frames, 0.45)
            samples_l += c_l * chaos_l * chaos_strength
            samples_r += c_r * chaos_r * chaos_strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples_l.astype(np.float32),
            samples_r=samples_r.astype(np.float32),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# 추-- Surface Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class KerbRenderer(SourceRenderer):
    """--석/커브 --더--"""
    
    def __init__(self):
        super().__init__("kerb", HapticBus.SURFACE)
        self._osc_l = Osc()
        self._osc_r = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        kerb_l = float(getattr(st, "kerb_l", 0.0))
        kerb_r = float(getattr(st, "kerb_r", 0.0))
        
        if kerb_l <= 0.0 and kerb_r <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_kerb_gain", 0.52), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --석: 빠른 --스 + 중──        speed = ctx.speed_kmh
        freq = 145.0 + min(85.0, speed * 0.3)
        pulse_rate = 12.0 + min(35.0, speed * 0.15)
        
        pulse_l = pulse_train(ctx.frames, ctx.sr, pulse_rate, 0.35)
        pulse_r = pulse_train(ctx.frames, ctx.sr, pulse_rate * 1.05, 0.35)
        
        sig_l = self._osc_l.sine(ctx.frames, ctx.sr, freq) * pulse_l * 0.7 + noise(ctx.frames, 0.25)
        sig_r = self._osc_r.sine(ctx.frames, ctx.sr, freq * 1.02) * pulse_r * 0.7 + noise(ctx.frames, 0.25)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=(sig_l * kerb_l * strength).astype(np.float32),
            samples_r=(sig_r * kerb_r * strength).astype(np.float32),
        )
        output.compute_levels()
        return output


class WetSurfaceRenderer(SourceRenderer):
    """── --면/물웅--이 --더--"""
    
    def __init__(self):
        super().__init__("wet_surface", HapticBus.SURFACE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        wet = float(getattr(st, "wet_surface", 0.0))
        puddle = float(getattr(st, "puddle", 0.0))
        
        if wet <= 0.0 and puddle <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        wet_strength = _gain(_ga(settings, "haptic_wet_gain", 0.35), 0.0, 2.0) * self._gain
        puddle_strength = _gain(_ga(settings, "haptic_puddle_gain", 0.55), 0.0, 2.0)
        
        samples = np.zeros(ctx.frames, dtype=np.float32)
        
        if wet > 0.0 and wet_strength > 0.0:
            # ── --면: 부--러─────운--            wet_sig = noise(ctx.frames, 0.6) * self._osc.sine(ctx.frames, ctx.sr, 88.0) * 0.4
            samples += wet_sig * wet * wet_strength
        
        if puddle > 0.0 and puddle_strength > 0.0:
            # 물웅--이: --플--시 --벤--            splash = self._osc.sine(ctx.frames, ctx.sr, 65.0) * 0.6 + noise(ctx.frames, 0.35)
            samples += splash * puddle * puddle_strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# 추-- Vehicle Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class WeightTransferRenderer(SourceRenderer):
    """--중 --동 --더--"""
    
    def __init__(self):
        super().__init__("weight_transfer", HapticBus.VEHICLE)
        self._osc_pitch = Osc()
        self._osc_roll = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        pitch_rate = float(getattr(st, "pitch_rate", 0.0))
        roll_rate = float(getattr(st, "roll_rate", 0.0))
        
        if abs(pitch_rate) <= 0.01 and abs(roll_rate) <= 0.01:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        pitch_str = _gain(_ga(settings, "haptic_body_pitch_strength", 0.45), 0.0, 2.0) * self._gain
        roll_str = _gain(_ga(settings, "haptic_body_roll_strength", 0.40), 0.0, 2.0)
        
        samples_l = np.zeros(ctx.frames, dtype=np.float32)
        samples_r = np.zeros(ctx.frames, dtype=np.float32)
        
        if abs(pitch_rate) > 0.01 and pitch_str > 0.0:
            # --치: 브레--킹 --이-- 가──쿼--            pitch_sig = self._osc_pitch.sine(ctx.frames, ctx.sr, 85.0) * 0.6 + noise(ctx.frames, 0.2)
            amp = abs(pitch_rate) * pitch_str
            samples_l += pitch_sig * amp
            samples_r += pitch_sig * amp
        
        if abs(roll_rate) > 0.01 and roll_str > 0.0:
            # -- L/R 분리 (좌회───른──강함)
            roll_sig = self._osc_roll.sine(ctx.frames, ctx.sr, 72.0) * 0.55 + noise(ctx.frames, 0.18)
            roll_amp = abs(roll_rate) * roll_str
            # roll_rate > 0 ──쪽--로 기울--짐 ──른──강함
            if roll_rate > 0:
                samples_l += roll_sig * roll_amp * 0.6
                samples_r += roll_sig * roll_amp
            else:
                samples_l += roll_sig * roll_amp
                samples_r += roll_sig * roll_amp * 0.6
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples_l.astype(np.float32),
            samples_r=samples_r.astype(np.float32),
        )
        output.compute_levels()
        return output


class WheelspinRenderer(SourceRenderer):
    """--스-- --더--"""
    
    def __init__(self):
        super().__init__("wheelspin", HapticBus.VEHICLE)
        self._osc_l = Osc()
        self._osc_r = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        spin_l = float(getattr(st, "wheelspin_l", 0.0))
        spin_r = float(getattr(st, "wheelspin_r", 0.0))
        
        if spin_l <= 0.0 and spin_r <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_wheelspin_gain", 0.48), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # FIX: --스--: 고주--noise --주 "찌이-- --낌 + sine-- 보조
        freq = min(200.0, 165.0 + spin_l * 35.0 + spin_r * 35.0)
        
        sig_l = self._osc_l.sine(ctx.frames, ctx.sr, freq) * 0.30 + noise(ctx.frames, 0.60)
        sig_r = self._osc_r.sine(ctx.frames, ctx.sr, freq * 1.03) * 0.30 + noise(ctx.frames, 0.60)
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=(sig_l * spin_l * strength).astype(np.float32),
            samples_r=(sig_r * spin_r * strength).astype(np.float32),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# 추-- Engine Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class BoostRenderer(SourceRenderer):
    """부--트/--보 --더--"""
    
    def __init__(self):
        super().__init__("boost", HapticBus.ENGINE)
        self._osc_build = Osc()
        self._osc_blow = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        boost_build = float(getattr(st, "boost_build", 0.0))
        boost_blow = float(getattr(st, "boost_blow", 0.0))
        
        if boost_build <= 0.0 and boost_blow <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        build_str = _gain(_ga(settings, "haptic_boost_strength", 0.60), 0.0, 2.0) * self._gain
        blow_str = _gain(_ga(settings, "haptic_boost_blow_strength", 0.55), 0.0, 2.0)
        
        samples = np.zeros(ctx.frames, dtype=np.float32)
        
        if boost_build > 0.0 and build_str > 0.0:
            # 부--트 빌드-- --점 --아지--whine
            build_freq = 95.0 + boost_build * 85.0
            build_sig = self._osc_build.sine(ctx.frames, ctx.sr, build_freq) * 0.55 + noise(ctx.frames, 0.18)
            samples += build_sig * boost_build * build_str
        
        if boost_blow > 0.0 and blow_str > 0.0:
            # 블로--오-- 짧-- ──
            blow_sig = self._osc_blow.sine(ctx.frames, ctx.sr, 72.0) * 0.65 + noise(ctx.frames, 0.28)
            samples += blow_sig * boost_blow * blow_str
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class TorqueRenderer(SourceRenderer):
    """--크 ── --더--"""
    
    def __init__(self):
        super().__init__("torque", HapticBus.ENGINE)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        torque_surge = float(getattr(st, "torque_surge", 0.0))
        
        if torque_surge <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_torque_strength", 0.50), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --크 ──: ────        sig = self._osc.sine(ctx.frames, ctx.sr, 55.0) * 0.7 + noise(ctx.frames, 0.22)
        samples = sig * torque_surge * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.astype(np.float32),
            samples_r=samples.astype(np.float32),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# 추-- Event Bus --더--들
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
class BumpRenderer(SourceRenderer):
    """범프/--철 --더──짧-- burst --팩--"""
    
    def __init__(self):
        super().__init__("bump", HapticBus.EVENT)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        bump = float(getattr(st, "bump", 0.0))
        
        if bump <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_bump_gain", 0.62), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # BURST 방식: 75Hz × 3 cycles = 40ms --"--걱" 짧-- 충격
        burst_hz = 75.0
        burst_cycles = 3.0
        burst_dur = burst_cycles / burst_hz
        burst_samples = min(ctx.frames, int(burst_dur * ctx.sr))
        
        samples = np.zeros(ctx.frames, dtype=np.float32)
        t = np.arange(burst_samples, dtype=np.float32) / float(ctx.sr)
        # square wave for max LRA excursion + decay envelope
        burst = np.sign(np.sin(2.0 * np.pi * burst_hz * t))
        decay = np.exp(-t * 25.0)  # fast decay for punch feel
        samples[:burst_samples] = burst * decay * bump * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.copy(),
            samples_r=samples.copy(),
        )
        output.compute_levels()
        return output


class LandingRenderer(SourceRenderer):
    """착--/--프 --더--"""
    
    def __init__(self):
        super().__init__("landing", HapticBus.EVENT)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        landing = float(getattr(st, "landing", 0.0))
        
        if landing <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_landing_strength", 0.58), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # FIX: 착--: ────(48Hz - 42Hz--LRA --함)
        sig = self._osc.sine(ctx.frames, ctx.sr, 48.0) * 0.75 + noise(ctx.frames, 0.2)
        samples = sig * landing * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.astype(np.float32),
            samples_r=samples.astype(np.float32),
        )
        output.compute_levels()
        return output


class ScrapeRenderer(SourceRenderer):
    """긁힘/--크--이──더--"""
    
    def __init__(self):
        super().__init__("scrape", HapticBus.EVENT)
        self._osc = Osc()
    
    def render(self, st: HapticState, ctx: RenderContext) -> SourceOutput:
        if not self._enabled:
            return self._empty_output(ctx)
        
        scrape = float(getattr(st, "scrape", 0.0))
        
        if scrape <= 0.0:
            return self._empty_output(ctx)
        
        settings = ctx.settings
        strength = _gain(_ga(settings, "haptic_scrape_gain", 0.48), 0.0, 2.0) * self._gain
        
        if strength <= 0.0:
            return self._empty_output(ctx)
        
        # --크--이-- 거친 --이--+ 중역
        sig = self._osc.sine(ctx.frames, ctx.sr, 135.0) * 0.4 + noise(ctx.frames, 0.55)
        samples = sig * scrape * strength
        
        output = SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=samples.astype(np.float32),
            samples_r=samples.astype(np.float32),
        )
        output.compute_levels()
        return output


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--# --더──토--# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
def create_all_renderers() -> list[SourceRenderer]:
    """모든 --스 --더──성."""
    return [
        # Engine Bus
        IdleRenderer(),
        RpmRenderer(),
        RpmHarmonicsRenderer(),
        RedlineWarningRenderer(),
        TurboSpoolRenderer(),
        EngineBrakingRenderer(),
        CornerExitTorqueRenderer(),
        LaunchRenderer(),
        BoostRenderer(),
        TorqueRenderer(),
        # Engine Bus - Transient
        AccelOnsetRenderer(),
        # Surface Bus
        RoadTextureRenderer(),
        GravelRenderer(),
        KerbRenderer(),
        WetSurfaceRenderer(),
        # Event Bus
        CollisionRenderer(),
        ShiftRenderer(),
        ShiftEngagementRenderer(),
        DecelOnsetRenderer(),
        EngineStartRenderer(),
        BumpRenderer(),
        LandingRenderer(),
        ScrapeRenderer(),
        # Vehicle Bus
        SlideRenderer(),
        WeightTransferRenderer(),
        WheelspinRenderer(),
    ]


def renderers_by_bus(renderers: list[SourceRenderer]) -> dict[HapticBus, list[SourceRenderer]]:
    """--더── 버스별로 그룹--"""
    result: dict[HapticBus, list[SourceRenderer]] = {bus: [] for bus in HapticBus}
    for r in renderers:
        result[r.bus].append(r)
    return result