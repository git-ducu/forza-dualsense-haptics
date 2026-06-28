# -*- coding: utf-8 -*-
"""
Bus Mixer - source output collection and per-bus level tracking.

--스 --더--들--출력--버스별로 --산--고,
UI──시──벨 --냅--을 --집.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from dsio.haptics.bus import HapticBus
from dsio.haptics.renderer import SourceOutput, SourceRenderer, RenderContext

if TYPE_CHECKING:
    pass  # No game-specific type needed at this level


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
# 버스 --태 (--벨 추적--
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--

@dataclass
class SourceLevel:
    """개별 --스──재 --벨."""
    source_id: str
    bus: HapticBus
    level_l: float
    level_r: float
    active: bool
    
    @property
    def level_mono(self) -> float:
        """모노 --벨 (L/R --균)."""
        return (self.level_l + self.level_r) / 2.0


@dataclass
class BusState:
    """버스 --태 --냅--(UI --시--."""
    bus: HapticBus
    level_l: float = 0.0
    level_r: float = 0.0
    sources: list[SourceLevel] = field(default_factory=list)
    
    @property
    def level_mono(self) -> float:
        return (self.level_l + self.level_r) / 2.0
    
    @property
    def active_sources(self) -> list[SourceLevel]:
        return [s for s in self.sources if s.active]


@dataclass
class MixerState:
    """--체 믹서 --태 --냅--"""
    buses: dict[HapticBus, BusState] = field(default_factory=dict)
    master_level_l: float = 0.0
    master_level_r: float = 0.0
    
    def __post_init__(self):
        for bus in HapticBus:
            if bus not in self.buses:
                self.buses[bus] = BusState(bus=bus)
    
    def get_active_sources(self) -> list[SourceLevel]:
        """모든 --성 --스 반환."""
        result = []
        for bus_state in self.buses.values():
            result.extend(bus_state.active_sources)
        return result
    
    def get_top_sources(self, n: int = 5) -> list[SourceLevel]:
        """--벨 기-- --위 N──스."""
        active = self.get_active_sources()
        active.sort(key=lambda s: s.level_mono, reverse=True)
        return active[:n]


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
# 버스 믹서
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--

@dataclass
class BusMixResult:
    """버스 믹싱 결과."""
    bus: HapticBus
    samples_l: np.ndarray
    samples_r: np.ndarray
    level_l: float
    level_r: float


class BusMixer:
    """--스 출력 --버스 --산 + --벨 추적.
    
    4-Layer Gain Stack (SimHub ───:
    Final = Master × Bus × Source × PerChannel
    """
    
    def __init__(self, renderers: list[SourceRenderer]):
        self._renderers = renderers
        self._renderers_by_bus: dict[HapticBus, list[SourceRenderer]] = {bus: [] for bus in HapticBus}
        for r in renderers:
            self._renderers_by_bus[r.bus].append(r)
        
        # Layer 1: Master gain
        self._master_gain: float = 1.0
        
        # Layer 2: Bus gains
        self._bus_gains: dict[HapticBus, float] = {bus: 1.0 for bus in HapticBus}
        
        # Layer 4: Per-channel (L/R balance)
        self._balance_lr: float = 0.0  # -1.0 = Left only, +1.0 = Right only
        
        # 최근 --태 --냅--(UI --근--
        self._last_state: MixerState = MixerState()
    
    @property
    def renderers(self) -> list[SourceRenderer]:
        return self._renderers
    
    @property
    def last_state(self) -> MixerState:
        """마───더링의 --태 --냅--(UI --시--."""
        return self._last_state
    
    @property
    def master_gain(self) -> float:
        return self._master_gain
    
    @master_gain.setter
    def master_gain(self, value: float) -> None:
        self._master_gain = max(0.0, min(2.0, value))
    
    def set_bus_gain(self, bus: HapticBus, gain: float) -> None:
        """버스 게인 --정 (Layer 2)."""
        self._bus_gains[bus] = max(0.0, min(2.0, gain))
    
    def get_bus_gain(self, bus: HapticBus) -> float:
        """버스 게인 조회."""
        return self._bus_gains.get(bus, 1.0)
    
    def update_gains_from_settings(self, settings) -> None:
        """settings--서 모든 게인 --기 (4-layer)."""
        # Layer 1: Master
        self._master_gain = max(0.0, min(2.0, float(getattr(settings, "haptic_master_gain", 1.0))))
        
        # Layer 2: Bus
        gain_keys = {
            HapticBus.SURFACE: "haptic_surface_bus_gain",
            HapticBus.VEHICLE: "haptic_vehicle_bus_gain",
            HapticBus.ENGINE: "haptic_engine_bus_gain",
            HapticBus.EVENT: "haptic_event_bus_gain",
        }
        for bus, key in gain_keys.items():
            self._bus_gains[bus] = max(0.0, min(2.0, float(getattr(settings, key, 1.0))))
        
        # Layer 4: Per-channel
        self._balance_lr = max(-1.0, min(1.0, float(getattr(settings, "haptic_balance_lr", 0.0))))
    
    def _compute_channel_gains(self) -> tuple[float, float]:
        """L/R 밸런--에--채널 게인 계산."""
        if self._balance_lr >= 0:
            # --른쪽으--치우───쪽 감소
            gain_l = 1.0 - self._balance_lr
            gain_r = 1.0
        else:
            # --쪽--로 치우───른--감소
            gain_l = 1.0
            gain_r = 1.0 + self._balance_lr
        return gain_l, gain_r
    
    def render_all(
        self,
        st: object,
        ctx: RenderContext,
    ) -> tuple[dict[HapticBus, BusMixResult], MixerState]:
        """모든 --더──행 --버스──산 ──태 --냅--"""
        
        # 버스--버퍼 초기--
        bus_buffers_l: dict[HapticBus, np.ndarray] = {
            bus: np.zeros(ctx.frames, dtype=np.float32) for bus in HapticBus
        }
        bus_buffers_r: dict[HapticBus, np.ndarray] = {
            bus: np.zeros(ctx.frames, dtype=np.float32) for bus in HapticBus
        }
        
        # --태 --냅--초기--
        state = MixerState()
        
        # ──더──행
        for renderer in self._renderers:
            if not renderer.enabled:
                continue
            
            output = renderer.render(st, ctx)
            bus = output.bus
            
            # 버퍼──산
            bus_buffers_l[bus] += output.samples_l
            bus_buffers_r[bus] += output.samples_r
            
            # --스 --벨 기록
            source_level = SourceLevel(
                source_id=output.source_id,
                bus=output.bus,
                level_l=output.level_l,
                level_r=output.level_r,
                active=output.active,
            )
            state.buses[bus].sources.append(source_level)
        
        # 4-Layer Gain Stack --용
        # Final = Master × Bus × Source (Source─── --더--에──용--
        channel_l, channel_r = self._compute_channel_gains()
        
        # 버스--결과 --성 + 게인 --용
        results: dict[HapticBus, BusMixResult] = {}
        for bus in HapticBus:
            # Layer 1 (Master) × Layer 2 (Bus) × Layer 4 (Channel)
            bus_gain = self._master_gain * self._bus_gains[bus]
            samples_l = bus_buffers_l[bus] * bus_gain * channel_l
            samples_r = bus_buffers_r[bus] * bus_gain * channel_r
            
            # 버스 --벨 계산 (게인 --용 --
            level_l = float(np.sqrt(np.mean(samples_l ** 2))) if len(samples_l) > 0 else 0.0
            level_r = float(np.sqrt(np.mean(samples_r ** 2))) if len(samples_r) > 0 else 0.0
            
            results[bus] = BusMixResult(
                bus=bus,
                samples_l=samples_l,
                samples_r=samples_r,
                level_l=level_l,
                level_r=level_r,
            )
            
            state.buses[bus].level_l = level_l
            state.buses[bus].level_r = level_r
        
        # 마스──벨
        all_l = sum(r.samples_l for r in results.values())
        all_r = sum(r.samples_r for r in results.values())
        state.master_level_l = float(np.sqrt(np.mean(all_l ** 2))) if len(all_l) > 0 else 0.0
        state.master_level_r = float(np.sqrt(np.mean(all_r ** 2))) if len(all_r) > 0 else 0.0
        
        self._last_state = state
        return results, state
    
    def get_renderer(self, source_id: str) -> SourceRenderer | None:
        """--스 ID──더--조회."""
        for r in self._renderers:
            if r.source_id == source_id:
                return r
        return None
    
    def set_renderer_enabled(self, source_id: str, enabled: bool) -> bool:
        """--스 --성--비활--화."""
        renderer = self.get_renderer(source_id)
        if renderer:
            renderer.enabled = enabled
            return True
        return False
    
    def set_renderer_gain(self, source_id: str, gain: float) -> bool:
        """--스 게인 --정."""
        renderer = self.get_renderer(source_id)
        if renderer:
            renderer.gain = gain
            return True
        return False


# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--
# --퍼 --수
# --═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--═--

def format_source_levels(state: MixerState, threshold: float = 0.01) -> str:
    """--스 --벨──람──기 --운 문자--로 --맷."""
    lines = []
    for bus in HapticBus:
        bus_state = state.buses[bus]
        active = [s for s in bus_state.sources if s.level_mono >= threshold]
        if not active:
            continue
        lines.append(f"[{bus.name}] ({bus_state.level_mono:.2f})")
        for src in sorted(active, key=lambda s: s.level_mono, reverse=True):
            pct = int(src.level_mono * 100)
            lines.append(f"  {src.source_id}: {pct}%")
    return "\n".join(lines) if lines else "(no active sources)"


def format_top_sources(state: MixerState, n: int = 5) -> str:
    """--위 N──스--간결--게 --시."""
    top = state.get_top_sources(n)
    if not top:
        return "(idle)"
    parts = [f"{s.source_id}:{int(s.level_mono*100)}%" for s in top]
    return " | ".join(parts)
