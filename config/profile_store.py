"""JSON-backed settings persistence with named presets.

Structure:
    version, selectedPreset, presets (dict of named snapshots),
    app (app-scoped keys shared across all presets).
"""
import json
import logging
import re
from pathlib import Path

from . import paths

log = logging.getLogger("dhe")

_DATA = paths.DATA
PATH = _DATA / "user_preferences.json"
DEFAULT_PROFILE_NAME = "Default"
CORE_BASE_PROFILE_NAME = "DHE Core Base"

# App-scoped keys — independent of which preset is active.
APP_SCOPED_KEYS = frozenset({
    "udp_host",
    "udp_port",
    "udp_forward",
    "udp_forward_to",
    "enable_reconnect",
    "reconnect_interval_s",
    "enable_startup_pulse",
    "startup_pulse_force",
    "exit_on_game_close",
    "game_poll_interval_s",
    "check_for_updates",
    "language",
    "developer_mode",
    "diagnostic_capture_seconds",
    "diagnostic_target_size_mb",
    "diagnostic_max_size_mb",
    "diagnostic_sample_hz",
    "controller_lock_serial",
    "haptic_device_name",
    "haptic_left_channel",
    "haptic_right_channel",
    "haptic_sample_rate",
    "haptic_buffer_ms",
    "haptic_telemetry_recording_enabled",
    "haptic_telemetry_record_hz",
    "haptic_telemetry_record_path",
})

_SIMPLE = (bool, int, float, str)


class PreferencesError(Exception):
    """Raised when the settings file is unreadable or malformed."""

def _version() -> str:
    return "1.00"


def _fields(s) -> dict:
    return {k: v for k, v in vars(s).items() if isinstance(v, _SIMPLE)}


def _collectPresetValues(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k not in APP_SCOPED_KEYS}


def _collectAppValues(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k in APP_SCOPED_KEYS}


def _built_in_profile_snapshots(s) -> dict:
    """Restore profiles from the shipped JSON if it exists, else just Default."""
    defaults = _collectPresetValues(type(s)())
    shipped = _DATA / "user_preferences.json.default"
    if shipped.exists():
        try:
            raw = json.loads(shipped.read_text(encoding="utf-8"))
            profiles = raw.get("presets", {})
            if profiles:
                # Ensure every profile has all keys (fill missing from defaults)
                for name in profiles:
                    merged = {**defaults, **profiles[name]}
                    profiles[name] = merged
                if DEFAULT_PROFILE_NAME not in profiles:
                    profiles[DEFAULT_PROFILE_NAME] = defaults
                return profiles
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass
    return {DEFAULT_PROFILE_NAME: defaults}



def _applyStoredValues(s, snap: dict, fields: dict) -> None:
    """Write values from `snap` onto `s`, casting to the existing field type."""
    for k, current in fields.items():
        if k in snap:
            try:
                setattr(s, k, type(current)(snap[k]))
            except (TypeError, ValueError):
                pass


def _readStoreFile() -> dict:
    """Parse the JSON file; returns {} when file absent. Raises on corruption."""
    if not PATH.exists():
        return {}
    try:
        text = PATH.read_text(encoding="utf-8")
    except OSError as e:
        raise PreferencesError(f"Could not read {PATH.name}: {e}") from e
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise PreferencesError(f"{PATH.name} is corrupted ({e.msg} at line {e.lineno}).") from e
    if not isinstance(data, dict):
        raise PreferencesError(f"{PATH.name} must contain a JSON object at the top level.")
    return data


def _read() -> dict:
    """Lenient read that swallows errors for non-critical paths."""
    try:
        return _readStoreFile()
    except PreferencesError as e:
        log.warning("%s Falling back to empty preferences.", e)
        return {}


def _write(raw: dict) -> None:
    raw["version"] = _version()
    # atomic write — temp file then rename to avoid partial writes
    try:
        _DATA.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        tmp.replace(PATH)
    except OSError as e:
        log.warning("Could not save preferences: %s", e)


def _migrate_legacy(raw: dict, s) -> None:
    """Upgrade v0 flat layout: bare keys at top level → move into Default preset."""
    field_names = set(_fields(s).keys())
    legacy = {k: v for k, v in raw.items() if k in field_names}
    if not legacy:
        return
    raw.setdefault("presets", {})
    raw["presets"].setdefault(DEFAULT_PROFILE_NAME, {}).update(legacy)
    raw["selectedPreset"] = raw.get("selectedPreset") or DEFAULT_PROFILE_NAME
    for k in legacy:
        raw.pop(k, None)


def _normalizeStore(raw: dict, s) -> dict:
    """Normalize the store: ensure presets exist and active selection is valid."""
    _migrate_legacy(raw, s)
    raw.setdefault("presets", {})
    raw.setdefault("selectedPreset", "")
    raw.setdefault("app", {})

    # On first run (empty presets), seed built-in presets once
    if not raw["presets"]:
        for name, snap in _built_in_profile_snapshots(s).items():
            raw["presets"][name] = snap
        if DEFAULT_PROFILE_NAME not in raw["presets"]:
            raw["presets"][DEFAULT_PROFILE_NAME] = _collectPresetValues(type(s)())

    # If active preset is missing or empty, pick a sensible default
    if not raw["selectedPreset"] or raw["selectedPreset"] not in raw["presets"]:
        if CORE_BASE_PROFILE_NAME in raw["presets"]:
            raw["selectedPreset"] = CORE_BASE_PROFILE_NAME
        elif DEFAULT_PROFILE_NAME in raw["presets"]:
            raw["selectedPreset"] = DEFAULT_PROFILE_NAME
        else:
            raw["selectedPreset"] = next(iter(raw["presets"]), DEFAULT_PROFILE_NAME)
            if raw["selectedPreset"] not in raw["presets"]:
                raw["presets"][raw["selectedPreset"]] = _collectPresetValues(type(s)())

    # Ensure app-scoped keys have all system fields
    for k, v in _collectAppValues(s).items():
        raw["app"].setdefault(k, v)
    return raw


def load(s) -> None:
    """Read the file and apply the active preset to `s`.

    Raises PreferencesError if the file is unreadable / corrupted so the caller
    can prompt the user before any destructive recovery.
    """
    raw = _readStoreFile()
    raw = _normalizeStore(raw, s)
    _write(raw)
    snap = dict(raw["app"])
    snap.update(raw["presets"][raw["selectedPreset"]])
    _applyStoredValues(s, snap, _fields(s))


def reset_file() -> None:
    """Archive then delete the settings file so the next load rebuilds it."""
    if PATH.exists():
        backup = PATH.with_suffix(PATH.suffix + ".bak")
        try:
            backup.write_bytes(PATH.read_bytes())
            log.info("Backed up old preferences to %s", backup.name)
        except OSError as e:
            log.warning("Could not back up %s: %s", PATH.name, e)
        try:
            PATH.unlink()
        except OSError as e:
            log.warning("Could not delete %s: %s", PATH.name, e)


def save(s) -> None:
    # guard: I/O failures must not propagate into the UI event loop
    try:
        raw = _normalizeStore(_read(), s)
        # Merge into existing profile rather than replacing — preserves keys
        # that exist in the JSON but not in Settings (e.g. preset-only tuning
        # keys added in newer versions). Without this, loading a profile and
        # then saving would delete keys that Settings doesn't have as fields.
        active = raw["selectedPreset"]
        existing = raw["presets"].get(active, {})
        existing.update(_collectPresetValues(s))
        raw["presets"][active] = existing
        raw["app"].update(_collectAppValues(s))
        _write(raw)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        log.warning("preferences.save failed: %s", e)


# Debounced save: coalesces rapid successive saves into a single write.
import threading as _threading

_save_lock = _threading.Lock()
_save_timer: _threading.Timer | None = None
_SAVE_DEBOUNCE_S = 0.4


def save_debounced(s) -> None:
    """Schedule a save after a short debounce period. Repeated calls within the
    debounce window reset the timer so only one write occurs."""
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = _threading.Timer(_SAVE_DEBOUNCE_S, save, args=(s,))
        _save_timer.daemon = True
        _save_timer.start()


def flush_debounced(s) -> None:
    """Cancel any pending debounced save and write immediately.
    Call this on app shutdown to avoid losing the last edit."""
    global _save_timer
    with _save_lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None
    save(s)


def reset(s) -> None:
    """Restore the active preset to class defaults; mutate s in place so the
    running loop picks them up on its next frame. App-scoped fields are left intact."""
    defaults = type(s)()
    for k in _collectPresetValues(s):
        if hasattr(defaults, k):
            setattr(s, k, getattr(defaults, k))
    save(s)
