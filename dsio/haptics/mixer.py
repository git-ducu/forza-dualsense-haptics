"""Haptic mixer utilities — telemetry-neutral helpers.

The heavy game-specific logic lives in the game adapter module. This provides
shared utility functions used by mastering and other core DSP.
"""
from __future__ import annotations


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float between lo and hi."""
    return max(lo, min(hi, float(v)))


def setting(settings, key: str, default: float = 1.0) -> float:
    """Read a numeric setting with fallback."""
    try:
        return float(getattr(settings, key, default))
    except (TypeError, ValueError):
        return default
