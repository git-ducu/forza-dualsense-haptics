"""Small block-rate transient helpers for DHE haptic audio.

The haptic renderer already receives held telemetry envelopes.  For musical
punch, held values are not enough: a shift/impact should hit once, then decay
instead of re-triggering every callback.  This module tracks rising edges at the
audio-block rate and returns short one-shot envelopes that the mixer can blend
with sustained body cues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import exp
from typing import Mapping


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        x = float(v)
    except Exception:
        x = 0.0
    return max(lo, min(hi, x))


@dataclass(slots=True)
class TransientTracker:
    """Rising-edge one-shot envelope for one signal."""

    threshold: float = 0.055
    release_ms: float = 95.0
    previous: float = 0.0
    envelope: float = 0.0

    def update(self, level: float, dt_ms: float) -> float:
        level = _clamp(level)
        dt = max(0.0, float(dt_ms))
        release = max(8.0, float(self.release_ms))
        decay = exp(-dt / release) if dt > 0.0 else 1.0
        self.envelope *= decay
        # perf: clamp denormal floats to zero (prevents x86 FP stall)
        if self.envelope < 1e-10:
            self.envelope = 0.0

        # Rising edge above the previous held value.  Very small jitter is ignored
        # so a sustained crash/kerb does not keep re-firing the punch lane.
        edge = max(0.0, level - self.previous)
        if edge >= self.threshold:
            self.envelope = max(self.envelope, _clamp(edge * 1.35 + level * 0.16))
        self.previous = max(level, self.previous * decay * 0.72)
        return _clamp(self.envelope)


@dataclass(slots=True)
class HapticTransientBank:
    """Named transient tracker bank. Game adapters pass their own tracker config.
    
    If no trackers provided, defaults to an empty bank.
    """

    trackers: dict[str, TransientTracker] = field(default_factory=dict)
    _shift_cooldown_remaining_ms: float = 0.0

    def update(self, levels: Mapping[str, float], dt_ms: float) -> dict[str, float]:
        dt = max(0.0, float(dt_ms))
        # Shift가 발동하면 쿨다운 시작
        shift_level = float(levels.get("shift", 0.0))
        if shift_level > 0.05:
            self._shift_cooldown_remaining_ms = 300.0
        self._shift_cooldown_remaining_ms = max(0.0, self._shift_cooldown_remaining_ms - dt)
        # 쿨다운 중이면 accel/decel onset 입력을 0으로 눌러서 발동 차단
        effective = dict(levels)
        if self._shift_cooldown_remaining_ms > 0.0:
            effective["accel_onset"] = 0.0
            effective["decel_onset"] = 0.0
        return {name: tracker.update(float(effective.get(name, 0.0)), dt) for name, tracker in self.trackers.items()}
