"""
Haptic Bus Architecture — telemetry-neutral signal routing framework.

Provides the structural types for bus-based haptic mixing.
Game adapters populate HAPTIC_SOURCES with their own source definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HapticBus(str, Enum):
    """Output bus classification — physical mixing stage."""
    SURFACE = "surface"
    VEHICLE = "vehicle"
    EVENT = "event"
    ENGINE = "engine"


class HapticCategory(str, Enum):
    """User-facing category for UI grouping. Extend per game."""
    ROAD_FEEL = "노면 감각"
    SURFACE_TYPE = "노면 종류"
    WEATHER = "날씨 영향"
    BODY_MOTION = "차체 거동"
    ENGINE_VIBRATION = "엔진 진동"
    DRIVETRAIN = "구동계"
    TIRE_FEEDBACK = "타이어 피드백"
    IMPACT = "충격/이벤트"


@dataclass
class HapticSource:
    """Individual haptic source definition."""
    id: str
    name_ko: str
    name_en: str
    bus: HapticBus
    category: HapticCategory
    settings: tuple[str, ...] = ()
    description_ko: str = ""
    description_en: str = ""


@dataclass
class BusLevel:
    """Per-bus real-time level."""
    left: float = 0.0
    right: float = 0.0
    peak_left: float = 0.0
    peak_right: float = 0.0


@dataclass
class SourceLevel:
    """Per-source real-time level (UI display)."""
    source_id: str
    left: float = 0.0
    right: float = 0.0
    active: bool = False


@dataclass
class HapticBusState:
    """Full bus system state — consumed by UI."""
    surface: BusLevel = field(default_factory=BusLevel)
    vehicle: BusLevel = field(default_factory=BusLevel)
    event: BusLevel = field(default_factory=BusLevel)
    engine: BusLevel = field(default_factory=BusLevel)
    master: BusLevel = field(default_factory=BusLevel)
    active_sources: list[SourceLevel] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Source Registry — game adapters call register() to populate
# ═══════════════════════════════════════════════════════════════════════════

HAPTIC_SOURCES: dict[str, HapticSource] = {}


def register(*sources: HapticSource) -> None:
    """Register haptic sources. Called by game adapters at import time."""
    for s in sources:
        HAPTIC_SOURCES[s.id] = s


def get_sources_by_bus(bus: HapticBus) -> list[HapticSource]:
    return [s for s in HAPTIC_SOURCES.values() if s.bus == bus]


def get_sources_by_category(category: HapticCategory) -> list[HapticSource]:
    return [s for s in HAPTIC_SOURCES.values() if s.category == category]


def get_sources_for_setting(setting_key: str) -> list[HapticSource]:
    return [s for s in HAPTIC_SOURCES.values() if setting_key in s.settings]


def get_setting_impact_text(setting_key: str, lang: str = "ko") -> str:
    sources = get_sources_for_setting(setting_key)
    if not sources:
        return ""
    if lang == "ko":
        return f"영향: {', '.join(s.name_ko for s in sources)}"
    return f"Affects: {', '.join(s.name_en for s in sources)}"


def get_category_sources_text(category: HapticCategory, lang: str = "ko") -> str:
    sources = get_sources_by_category(category)
    if lang == "ko":
        return ", ".join(s.name_ko for s in sources)
    return ", ".join(s.name_en for s in sources)


# Bus master gain setting keys (4-Layer Gain Stack Layer 2)
BUS_MASTER_SETTINGS = {
    HapticBus.SURFACE: "haptic_surface_bus_gain",
    HapticBus.VEHICLE: "haptic_vehicle_bus_gain",
    HapticBus.ENGINE: "haptic_engine_bus_gain",
    HapticBus.EVENT: "haptic_event_bus_gain",
}

MASTER_GAIN_SETTING = "haptic_master_gain"
