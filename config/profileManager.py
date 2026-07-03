"""Named Settings snapshots stored inside user_preferences.json."""
import base64
import json
import logging
import zlib

from . import profile_store as preferences

log = logging.getLogger("dhe")

SHARE_PREFIX = "DHE:"
_DEFAULT = preferences.DEFAULT_PROFILE_NAME
_CORE = getattr(preferences, "CORE_BASE_PROFILE_NAME", "DHE Core Base")

# ── Preset metadata: display labels and descriptions ──
PRESET_META: dict[str, dict[str, str]] = {
    "DHE Core Base": {
        "label_ko": "코어 베이스",
        "label_en": "Core Base",
        "desc_ko": "기준 세팅. 트리거와 햅틱이 균형 잡힌 기본값.",
        "desc_en": "Reference preset. Balanced trigger and haptic defaults.",
    },
}


def get_preset_display(name: str, lang: str = "ko") -> tuple[str, str]:
    """Return (display_label, description) for a preset name."""
    meta = PRESET_META.get(name)
    if not meta:
        return name, ""
    label = meta.get(f"label_{lang}", meta.get("label_en", name))
    desc = meta.get(f"desc_{lang}", meta.get("desc_en", ""))
    return f"{name}  ({label})", desc


def load_profiles() -> dict:
    """Snapshot of {'active': str, 'presets': dict} from disk."""
    raw = preferences._read()
    return {
        "active": raw.get("selectedPreset", "") or "",
        "presets": raw.get("presets", {}) or {},
    }


def list_profile_names(store: dict) -> list:
    """All profile names with Default/Core Base pinned to the top."""
    names = list(store.get("presets", {}).keys())
    pinned = [n for n in (_DEFAULT, _CORE) if n in names]
    rest = sorted((n for n in names if n not in pinned), key=str.lower)
    return pinned + rest


def _unique(name: str, taken: dict) -> str:
    """Return `name` or `name1`, `name2`, ... if it collides."""
    if name not in taken:
        return name
    i = 1
    while f"{name}{i}" in taken:
        i += 1
    return f"{name}{i}"


def _write_store(profs: dict, active: str) -> None:
    raw = preferences._read()
    raw["presets"] = profs
    raw["selectedPreset"] = active
    preferences._write(raw)


def _defaults() -> dict:
    from .settings import Settings
    return preferences._collectPresetValues(Settings())


def save_profile(name: str, s) -> str:
    """Save current settings as a new profile. Auto-suffixes on collision.
    Returns the final stored name, or "" if `name` was empty."""
    name = name.strip()
    if not name:
        return ""
    store = load_profiles()
    final = _unique(name, store["presets"])
    store["presets"][final] = preferences._collectPresetValues(s)
    _write_store(store["presets"], final)
    return final


def apply_profile(name: str, s) -> bool:
    store = load_profiles()
    snap = store["presets"].get(name)
    if snap is None:
        return False
    preferences._applyStoredValues(s, snap, preferences._collectPresetValues(s))
    _write_store(store["presets"], name)
    return True


def delete_profile(name: str) -> bool:
    store = load_profiles()
    profs = store["presets"]
    if name not in profs or name in {_DEFAULT, _CORE}:
        return False
    del profs[name]
    active = store["active"]
    if active == name:
        # Prefer Core Base, then Default, so tuning remains on the canonical baseline.
        active = _CORE if _CORE in profs else (_DEFAULT if _DEFAULT in profs else next(
            iter(sorted(profs.keys(), key=str.lower)), ""))
    _write_store(profs, active)
    return True


def rename_profile(old: str, new: str) -> str:
    """Rename `old` to `new`, auto-suffixing on collision. Returns "" if
    rejected (Default locked, old missing, new empty)."""
    new = new.strip()
    if not new or old == new or old == _DEFAULT:
        return ""
    store = load_profiles()
    profs = store["presets"]
    if old not in profs:
        return ""
    final = _unique(new, {k: v for k, v in profs.items() if k != old})
    # Preserve insertion order so the list doesn't reshuffle.
    profs_new = {(final if k == old else k): v for k, v in profs.items()}
    active = final if store["active"] == old else store["active"]
    _write_store(profs_new, active)
    return final


# MARK: share codes --------------------------------------------------------

def export_profile(name: str) -> str:
    """Encode profile `name` as a short DHE: code. Empty if missing.
    Only fields that differ from current built-in defaults are encoded."""
    store = load_profiles()
    snap = store["presets"].get(name)
    if snap is None:
        return ""
    defaults = _defaults()
    diff = {k: v for k, v in snap.items() if defaults.get(k) != v}
    payload = json.dumps([name, diff], separators=(",", ":")).encode("utf-8")
    blob = zlib.compress(payload, level=9)
    return SHARE_PREFIX + base64.urlsafe_b64encode(blob).rstrip(b"=").decode("ascii")


def import_profile(code: str) -> str:
    """Decode a DHE: code into a new profile (auto-suffixed). Returns ""
    on failure. Unknown keys are dropped; missing keys fall back to current
    defaults so codes stay compatible across versions."""
    code = (code or "").strip()
    if not code.startswith(SHARE_PREFIX):
        return ""
    body = code[len(SHARE_PREFIX):]
    pad = "=" * (-len(body) % 4)
    try:
        blob = base64.urlsafe_b64decode(body + pad)
        payload = json.loads(zlib.decompress(blob).decode("utf-8"))
    except (ValueError, OSError, zlib.error, json.JSONDecodeError):
        return ""
    if not (isinstance(payload, list) and len(payload) == 2
            and isinstance(payload[1], dict)):
        return ""
    name = str(payload[0]).strip() or "Imported"
    defaults = _defaults()
    cleaned = {k: v for k, v in payload[1].items() if k in defaults}
    store = load_profiles()
    final = _unique(name, store["presets"])
    store["presets"][final] = {**defaults, **cleaned}
    _write_store(store["presets"], store["active"])
    return final
