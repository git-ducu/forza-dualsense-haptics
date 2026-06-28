"""
Source Renderer Framework — telemetry-neutral rendering infrastructure.

Provides the abstract base class and data structures for bus-routed
haptic source rendering. Game adapters subclass SourceRenderer to
implement their specific effects.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .bus import HapticBus


# ═══════════════════════════════════════════════════════════════════════════
# Source Output
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SourceOutput:
    """Single source renderer output."""
    source_id: str
    bus: HapticBus
    samples_l: np.ndarray
    samples_r: np.ndarray
    level_l: float = 0.0
    level_r: float = 0.0
    active: bool = False

    def compute_levels(self) -> None:
        if len(self.samples_l) > 0:
            self.level_l = float(np.sqrt(np.mean(self.samples_l ** 2)))
            self.active = self.level_l > 0.001
        if len(self.samples_r) > 0:
            self.level_r = float(np.sqrt(np.mean(self.samples_r ** 2)))
            self.active = self.active or self.level_r > 0.001


@dataclass
class RenderContext:
    """Common rendering context passed to all renderers."""
    frames: int
    sr: int
    speed_kmh: float
    settings: object
    freq_low: float = 56.0
    freq_high: float = 420.0
    sharpness: float = 1.15

    def hz(self, frac: float) -> float:
        """Convert 0-1 fraction to frequency."""
        f = max(0.0, min(1.0, float(frac)))
        if self.sharpness != 1.0:
            f = min(1.0, max(0.0, f ** (1.0 / self.sharpness)))
        return self.freq_low + (self.freq_high - self.freq_low) * f


# ═══════════════════════════════════════════════════════════════════════════
# Response Filter (SimHub-style)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResponseFilter:
    """Source output response filter (SimHub ShakeIt style)."""
    gamma: float = 1.0
    threshold: float = 0.02
    min_force: float = 0.0
    attack_ms: float = 2.0
    release_ms: float = 30.0

    def apply(self, value: float) -> float:
        if value < self.threshold:
            return 0.0
        shaped = value ** (1.0 / self.gamma) if self.gamma != 1.0 else value
        if self.min_force > 0.0 and shaped > 0.0:
            shaped = max(self.min_force, shaped)
        return min(1.0, shaped)

    def apply_array(self, arr: np.ndarray) -> np.ndarray:
        result = arr.copy()
        result[np.abs(result) < self.threshold] = 0.0
        if self.gamma != 1.0:
            signs = np.sign(result)
            result = signs * (np.abs(result) ** (1.0 / self.gamma))
        if self.min_force > 0.0:
            active = np.abs(result) > 0.0
            result[active] = np.sign(result[active]) * np.maximum(
                np.abs(result[active]), self.min_force
            )
        return np.clip(result, -1.0, 1.0)


FILTER_PRESETS = {
    "default": ResponseFilter(),
    "subtle": ResponseFilter(gamma=0.7, threshold=0.05),
    "aggressive": ResponseFilter(gamma=1.5, threshold=0.01),
    "impact": ResponseFilter(gamma=1.0, threshold=0.1, attack_ms=1.0),
    "texture": ResponseFilter(gamma=0.8, threshold=0.03, attack_ms=6.0),
}


# ═══════════════════════════════════════════════════════════════════════════
# Base Renderer
# ═══════════════════════════════════════════════════════════════════════════

class SourceRenderer(ABC):
    """Abstract source renderer with gain stack and response filter."""

    def __init__(self, source_id: str, bus: HapticBus):
        self._source_id = source_id
        self._bus = bus
        self._enabled = True
        self._gain = 1.0
        self._filter = ResponseFilter()

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def bus(self) -> HapticBus:
        return self._bus

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, value: float) -> None:
        self._gain = max(0.0, min(2.0, value))

    @property
    def filter(self) -> ResponseFilter:
        return self._filter

    @filter.setter
    def filter(self, value: ResponseFilter) -> None:
        self._filter = value

    def set_filter_preset(self, preset_name: str) -> bool:
        if preset_name in FILTER_PRESETS:
            self._filter = FILTER_PRESETS[preset_name]
            return True
        return False

    @abstractmethod
    def render(self, st: Any, ctx: RenderContext) -> SourceOutput:
        """Render source audio. Implement in subclass."""
        pass

    def _apply_filter_to_output(self, output: SourceOutput) -> SourceOutput:
        if self._filter.gamma == 1.0 and self._filter.threshold <= 0.0:
            return output
        output.samples_l = self._filter.apply_array(output.samples_l)
        output.samples_r = self._filter.apply_array(output.samples_r)
        output.compute_levels()
        return output

    def _empty_output(self, ctx: RenderContext) -> SourceOutput:
        return SourceOutput(
            source_id=self._source_id,
            bus=self._bus,
            samples_l=np.zeros(ctx.frames, dtype=np.float32),
            samples_r=np.zeros(ctx.frames, dtype=np.float32),
            level_l=0.0,
            level_r=0.0,
            active=False,
        )
