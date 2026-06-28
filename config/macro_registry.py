"""Macro sliders for DHE Settings/Dashboard.

Macros are not stored as separate settings. Detailed Settings values are the
source of truth. Dashboard summarizes macro state; Settings can apply macros,
and manual detailed edits are reflected back as Custom/Mixed macro state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from . import option_registry


@dataclass(frozen=True)
class MacroSpec:
    key: str
    label_en: str
    label_ko: str
    min_value: float = 0.70
    max_value: float = 1.30
    default: float = 1.00
    description_en: str = ""
    description_ko: str = ""
    weights: Dict[str, float] = None

    def label(self, lang: str = "ko") -> str:
        return f"{self.label_ko} / {self.label_en}" if lang == "ko" else f"{self.label_en} / {self.label_ko}"


MACROS = [
    MacroSpec("macro_body_rumble", "Body rumble", "차체 울림", 0.70, 1.30, 1.0,
              "Low body, drivetrain thump and impact weight.", "저역 차체감, 변속/충돌 body를 같이 조절.", {
        "haptic_bass_foundation_gain": 1.00,
        "haptic_shift_bass_strength": 0.70,
        "haptic_shift_body_kick_strength": 0.55,
        "haptic_impact_sub_strength": 0.75,
        "haptic_engine_bass_strength": 0.45,
        "haptic_low_mid_glue_strength": 0.35,
    }),
    MacroSpec("macro_road_texture", "Road texture", "도로 질감", 0.70, 1.30, 1.0,
              "Mid road grain, roughness and surface palette.", "중역 도로 입자감과 노면 팔레트를 같이 조절.", {
        "haptic_road_gain": 1.00,
        "haptic_mid_texture_balance": 0.90,
        "haptic_texture_palette_strength": 0.75,
        "haptic_gravel_gain": 0.45,
        "haptic_mid_min_gain": 0.35,
    }),
    MacroSpec("macro_event_punch", "Event punch", "이벤트 타격감", 0.70, 1.30, 1.0,
              "Shift, bump and impact attack without replacing the trigger feel.", "변속/요철/충돌의 앞 타격을 조절.", {
        "haptic_event_punch_gain": 1.00,
        "haptic_shift_master_gain": 0.65,
        "haptic_impact_master_gain": 0.75,
        "haptic_bump_sub_strength": 0.55,
        "haptic_punch_sustain_blend": 0.35,
    }),
    MacroSpec("macro_fingertip_edge", "Fingertip edge", "손끝 엣지감", 0.70, 1.30, 1.0,
              "High crack, kerb edge and tire buzz. Too much can get tiring.", "고역 크랙/연석/타이어 버즈. 과하면 피곤함.", {
        "haptic_high_edge_gain": 1.00,
        "haptic_impact_crack_high_strength": 0.65,
        "haptic_shift_high_click_strength": 0.50,
        "haptic_grip_edge_high_strength": 0.55,
        "haptic_wheelspin_edge_high_strength": 0.45,
    }),
    MacroSpec("macro_space_width", "Space / width", "공간감", 0.70, 1.30, 1.0,
              "Left/right spread and virtual front/rear contrast.", "좌우 폭과 전후 대비를 같이 조절.", {
        "haptic_spatial_width": 1.00,
        "haptic_front_rear_contrast": 0.65,
        "haptic_spatial_depth_gain": 0.60,
        "haptic_final_side_boost": 0.55,
    }),
    MacroSpec("macro_trigger_priority", "Trigger priority", "트리거 우선도", 0.70, 1.30, 1.0,
              "Higher keeps trigger feel clearer by making haptics less intrusive.", "올릴수록 트리거 철컥/저항/ABS 느낌이 더 잘 드러나도록 햅틱을 덜 튀게 조정.", {
        "haptic_trigger_harmony_gain": 1.00,
        "haptic_trigger_ducking": 0.70,
        "haptic_high_edge_gain": -0.25,
        "haptic_event_punch_gain": -0.20,
    }),
]

MACRO_BY_KEY = {m.key: m for m in MACROS}


def _base_value(attr: str):
    base = option_registry.core_base_overrides()
    return base.get(attr)


def _clamp(attr: str, value: float, developer_mode: bool = False) -> float:
    rng = option_registry.all_ranges(developer_mode).get(attr)
    if rng:
        lo, hi = rng
        return max(float(lo), min(float(hi), float(value)))
    return float(value)


def apply_macro(settings, macro_key: str, macro_value: float) -> dict:
    macro = MACRO_BY_KEY[macro_key]
    delta = float(macro_value) - 1.0
    changed = {}
    for attr, weight in (macro.weights or {}).items():
        if not hasattr(settings, attr):
            continue
        base = _base_value(attr)
        if base is None:
            base = getattr(settings, attr)
        if not isinstance(base, (int, float)) or isinstance(base, bool):
            continue
        new = float(base) * (1.0 + delta * float(weight))
        new = _clamp(attr, new, getattr(settings, "developer_mode", False))
        old = getattr(settings, attr)
        if isinstance(old, int):
            new = int(round(new))
        setattr(settings, attr, new)
        changed[attr] = {"old": old, "new": new, "macro": macro_key}
    return changed


def compute_macro_state(settings, macro_key: str) -> dict:
    macro = MACRO_BY_KEY[macro_key]
    ratios = []
    details = {}
    for attr, weight in (macro.weights or {}).items():
        if not hasattr(settings, attr):
            continue
        base = _base_value(attr)
        cur = getattr(settings, attr)
        if base in (None, 0) or not isinstance(base, (int, float)) or isinstance(base, bool):
            continue
        # Invert apply formula: ratio = 1 + (cur/base - 1) / weight
        if weight == 0:
            continue
        ratio = 1.0 + ((float(cur) / float(base)) - 1.0) / float(weight)
        ratios.append(ratio)
        details[attr] = {"core": base, "current": cur, "implied_macro": ratio}
    if not ratios:
        return {"value": 1.0, "state": "Normal", "details": details}
    avg = sum(ratios) / len(ratios)
    spread = max(ratios) - min(ratios)
    state = "Normal"
    if spread > 0.14:
        state = "Custom"
    elif avg > 1.03:
        state = "Boosted"
    elif avg < 0.97:
        state = "Reduced"
    return {"value": max(macro.min_value, min(macro.max_value, avg)), "state": state, "details": details}


def macros_for_controls():
    return MACROS


def macros_for_settings():
    return MACROS
