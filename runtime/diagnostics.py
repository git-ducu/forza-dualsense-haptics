# -*- coding: utf-8 -*-
"""Compact diagnostic ZIP export for tester feedback."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import time
import zipfile
from pathlib import Path
from typing import Any

from config import paths, profile_store as preferences, profileManager as profiles, option_registry


# ── Path sanitization ─────────────────────────────────────────────────────────

_USER_HOME = Path.home()
_USERNAME_PATTERN = re.compile(
    r'(?i)([A-Z]:\\Users\\|/home/)([^\\/"<>|*?]+)',
)


def _sanitize_path(p: str) -> str:
    """Replace user-home prefix with ~/ to avoid leaking usernames."""
    try:
        path = Path(p)
        if path.is_relative_to(paths.ROOT):
            return str(path.relative_to(paths.ROOT))
        if path.is_relative_to(_USER_HOME):
            return "~/" + str(path.relative_to(_USER_HOME)).replace("\\", "/")
    except (ValueError, TypeError):
        pass
    # Fallback: regex mask username from absolute paths
    return _USERNAME_PATTERN.sub(lambda m: m.group(1) + "***", p)


def _sanitize_dict(d: dict) -> dict:
    """Recursively sanitize path-like string values in a dict."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str) and (("\\" in v and ":\\" in v) or v.startswith("/")):
            out[k] = _sanitize_path(v)
        elif isinstance(v, dict):
            out[k] = _sanitize_dict(v)
        else:
            out[k] = v
    return out


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, Path): return str(v)
    if isinstance(v, dict): return {str(k): _jsonable(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)): return [_jsonable(x) for x in v]
    return str(v)


def _settings_snapshot(settings) -> dict:
    return {k: _jsonable(v) for k, v in vars(settings).items() if isinstance(v, (str, int, float, bool))}


def _hash_file(path: Path) -> str:
    try:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return ""


def _tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists(): return []
    try:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    return lines[-limit:]


def _parse_jsonl(lines: list[str]) -> list:
    out = []
    for line in lines:
        try: out.append(json.loads(line))
        except json.JSONDecodeError: out.append({"raw": line[:600]})
    return out


def _summarize_records(records: list[dict]) -> dict:
    keys = [
        "mix_low_rms", "mix_road_mid_rms", "mix_surface_mid_rms", "mix_high_rms",
        "mix_event_rms", "mix_punch_rms", "mix_punch_to_mid_ratio",
        "mix_mid_protect_gain", "mix_sidechain_gain",
        "mix_event_trim_gain", "render_limiter_reduction",
        "speed", "rpm", "gear", "brake", "throttle",
        # extended telemetry diagnostics
        "rpm_norm", "pitch_rate", "roll_rate", "yaw_rate",
        "susp_vel_l", "susp_vel_r", "steer_vel", "tire_temp_freq",
        "accel_long", "ws_diff",
        # engine renderers
        "engine_braking", "turbo_spool", "corner_exit", "redline_warning",
        # tire
        "slip_sizzle", "tire_scrub",
        # stream health
        "stream_error_count",
    ]
    out = {"sample_count": len(records)}
    for k in keys:
        vals = []
        for r in records:
            try:
                v = r.get(k)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            except (KeyError, TypeError, AttributeError):
                pass
        if vals:
            vals_sorted = sorted(vals)
            p95 = vals_sorted[min(len(vals_sorted)-1, int(len(vals_sorted)*0.95))]
            out[k] = {"avg": sum(vals)/len(vals), "max": max(vals), "p95": p95}
    return out


def _write_json(zf: zipfile.ZipFile, name: str, obj: Any):
    zf.writestr(name, json.dumps(_jsonable(obj), indent=2, ensure_ascii=False))


def _write_hid_status(zf: zipfile.ZipFile):
    """Write HID enumerate-only status (no device open — avoids exclusive lock)."""
    try:
        import hid
        devices = hid.enumerate(0x054C, 0x0CE6)  # Sony DualSense
        if not devices:
            zf.writestr("hid_status.txt", "DualSense: not found via HID enumerate\n")
            return
        lines = [f"DualSense HID devices found: {len(devices)}\n"]
        for i, d in enumerate(devices):
            transport = "Bluetooth" if d.get("interface_number", 0) == -1 else "USB"
            serial = d.get("serial_number", "") or ""
            masked_serial = (serial[:4] + "****") if len(serial) > 4 else "unknown"
            lines.append(f"  [{i}] {transport}, serial={masked_serial}, "
                         f"usage_page=0x{d.get('usage_page', 0):04X}\n")
        zf.writestr("hid_status.txt", "".join(lines))
    except Exception as e:
        zf.writestr("hid_status.txt", f"HID enumerate unavailable: {e}\n")


def export_diagnostic_bundle(settings, out_dir: str | Path | None = None, note: str = "") -> Path:
    out_root = Path(out_dir) if out_dir else paths.DATA / "diagnostics"
    out_root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_root / f"dhe_diagnostic_{ts}.zip"

    try: pref_raw = preferences._read()
    except (OSError, json.JSONDecodeError) as e: pref_raw = {"error": str(e)}
    try: store = profiles.load_profiles()
    except (OSError, json.JSONDecodeError) as e: store = {"error": str(e)}

    capture_seconds = int(getattr(settings, "diagnostic_capture_seconds", 30) or 30)
    sample_hz = int(getattr(settings, "diagnostic_sample_hz", 20) or 20)
    line_limit = max(80, min(2000, capture_seconds * sample_hz))

    record_path = Path(str(getattr(settings, "haptic_telemetry_record_path", "data/haptic_telemetry_record.jsonl") or "data/haptic_telemetry_record.jsonl"))
    if not record_path.is_absolute(): record_path = paths.ROOT / record_path
    recent_lines = _tail_lines(record_path, line_limit)
    recent_records = _parse_jsonl(recent_lines)

    files = [
        paths.ROOT / "README.md", paths.ROOT / "CHANGELOG.md",
        paths.ROOT / "dsio" / "trigger" / "effects.py",
        paths.ROOT / "telemetry" / "haptics" / "audioEngine.py",
        paths.ROOT / "dsio" / "haptics" / "mixer.py",
        paths.ROOT / "dsio" / "haptics" / "mastering.py",
        paths.ROOT / "telemetry" / "haptics" / "sourceRenderers.py",
        paths.ROOT / "dsio" / "haptics" / "waveform.py",
        paths.ROOT / "config" / "profile_store.py",
        paths.ROOT / "config" / "option_registry.py",
        paths.ROOT / "config" / "settings.py",
        paths.ROOT / "runtime" / "loop.py",
    ]

    settings_snapshot = _settings_snapshot(settings)
    summary = {
        "schema": "dhe-diagnostic-zip-v1",
        "created_at": ts,
        "app_version": preferences._version(),
        "note": note,
        "platform": {"system": platform.system(), "release": platform.release(), "python": platform.python_version()},
        "active_preset": store.get("active"),
        "base_profile": preferences.CORE_BASE_PROFILE_NAME,
        "available_presets": sorted(list((store.get("presets") or {}).keys())),
        "core_base_delta_count": len(option_registry.changed_from_core(settings)),
        "haptic_device": {
            "name": getattr(settings, "haptic_device_name", ""),
            "left_channel": getattr(settings, "haptic_left_channel", None),
            "right_channel": getattr(settings, "haptic_right_channel", None),
            "sample_rate": getattr(settings, "haptic_sample_rate", None),
            "buffer_ms": getattr(settings, "haptic_buffer_ms", None),
            "master_gain": getattr(settings, "haptic_master_gain", None),
            "bus_engine_gain": getattr(settings, "haptic_bus_engine_gain", None),
            "bus_surface_gain": getattr(settings, "haptic_bus_surface_gain", None),
            "bus_event_gain": getattr(settings, "haptic_bus_event_gain", None),
        },
        "telemetry_record": {"path": _sanitize_path(str(record_path)), "lines_in_bundle": len(recent_lines), "capture_seconds": capture_seconds, "sample_hz": sample_hz},
        "haptic_summary": _summarize_records([r for r in recent_records if isinstance(r, dict)]),
        "trigger_summary": {
            "mode": getattr(settings, "r2_effect_priority_mode", "balanced"),
            "master_gain": getattr(settings, "trigger_master_gain", None),
            "l2_gain": getattr(settings, "trigger_l2_gain", None),
            "r2_gain": getattr(settings, "trigger_r2_gain", None),
            "shift_kick": getattr(settings, "trigger_shift_kick_gain", None),
            "shift_clack": getattr(settings, "trigger_shift_clack_gain", None),
            "abs_gain": getattr(settings, "trigger_abs_gain", None),
            "wheelspin_gain": getattr(settings, "trigger_wheelspin_gain", None),
            "redline_pulse": getattr(settings, "enable_trigger_redline_pulse", None),
            "redline_strength": getattr(settings, "trigger_redline_strength", None),
            "engine_brake": getattr(settings, "enable_trigger_engine_brake", None),
        },
        "tester_focus": [
            "brake resistance curve",
            "brake / throttle deadzone response",
            "adaptive trigger + wall collision",
            "high RPM rev limiter feel",
            "wheelspin buzz on launch",
            "ABS trigger chatter",
            "road texture L/R balance",
            "haptic spatial separation",
            "kerb/gravel surface transitions",
            "suspension bump transients",
            "shift clack timing",
            "idle engine hum baseline",
        ],
    }
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
        _write_json(zf, "summary.json", _sanitize_dict(summary))
        _write_json(zf, "settings.json", _sanitize_dict(settings_snapshot))
        _write_json(zf, "diff_from_core_base.json", option_registry.changed_from_core(settings))
        _write_json(zf, "preferences.json", _sanitize_dict(pref_raw) if isinstance(pref_raw, dict) else pref_raw)
        _write_json(zf, "file_hashes.json", {str(p.relative_to(paths.ROOT)): _hash_file(p) for p in files if p.exists()})
        _write_json(zf, "replay_summary.json", summary["haptic_summary"])
        zf.writestr("recent_haptics.jsonl", "\n".join(recent_lines[-line_limit:]))
        zf.writestr("recent_triggers.jsonl", json.dumps(summary["trigger_summary"], ensure_ascii=False))
        zf.writestr("recent_telemetry.jsonl", "\n".join(recent_lines[-line_limit:]))

        # ── User-readable files ─────────────────────────────────────────────
        zf.writestr("README_issue_instructions.txt",
                    "DHE Diagnostic Bundle\n"
                    "=====================\n\n"
                    "This folder/zip was generated by DHE --export-diagnostics.\n\n"
                    "To report an issue:\n"
                    "1. Go to https://github.com/git-ducu/forza-dualsense-haptics/issues\n"
                    "2. Create a New Issue\n"
                    "3. Attach this entire .zip file to the issue\n"
                    "4. Describe what happened and what you expected\n\n"
                    "This bundle does NOT contain passwords, tokens, or full file paths.\n")
        zf.writestr("app_version.txt",
                    f"DHE version: {summary.get('app_version', 'unknown')}\n"
                    f"Export time: {ts}\n")
        zf.writestr("windows_info.txt",
                    f"OS: {platform.system()} {platform.release()} ({platform.version()})\n"
                    f"Architecture: {platform.machine()}\n"
                    f"Python: {platform.python_version()}\n")
        # HID status — enumerate only, no device open (safe from exclusive lock)
        _write_hid_status(zf)

    max_mb = int(getattr(settings, "diagnostic_max_size_mb", 10) or 10)
    # Size guard: if somehow too large, rewrite with half the raw lines.
    if out_path.stat().st_size > max_mb * 1024 * 1024 and recent_lines:
        recent_lines = recent_lines[-max(50, len(recent_lines)//2):]
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
            summary["telemetry_record"]["lines_in_bundle"] = len(recent_lines)
            summary["telemetry_record"]["trimmed_for_size"] = True
            _write_json(zf, "summary.json", _sanitize_dict(summary))
            _write_json(zf, "settings.json", _sanitize_dict(settings_snapshot))
            _write_json(zf, "diff_from_core_base.json", option_registry.changed_from_core(settings))
            _write_json(zf, "preferences.json", _sanitize_dict(pref_raw) if isinstance(pref_raw, dict) else pref_raw)
            _write_json(zf, "file_hashes.json", {str(p.relative_to(paths.ROOT)): _hash_file(p) for p in files if p.exists()})
            zf.writestr("recent_haptics.jsonl", "\n".join(recent_lines))
            zf.writestr("recent_triggers.jsonl", json.dumps(summary["trigger_summary"], ensure_ascii=False))
            zf.writestr("recent_telemetry.jsonl", "\n".join(recent_lines))
    return out_path


if __name__ == "__main__":
    from config.settings import Settings
    s = Settings()
    try: preferences.load(s)
    except (OSError, json.JSONDecodeError, preferences.PreferencesError): pass
    print(export_diagnostic_bundle(s))

# ---------------------------------------------------------------------------
# DHE 1.1 hotfix: runtime ring buffer + continuous raw logging
# ---------------------------------------------------------------------------
from collections import deque
import os
import queue
import shutil
import threading

_RING_MAX_SAMPLES = 2400  # 120s at 20Hz
_RING = deque(maxlen=_RING_MAX_SAMPLES)
_RING_LOCK = threading.Lock()
_LAST_RING_WRITE = 0.0
_LAST_DIAGNOSTIC_PATH = None


def _compact_telemetry(t: dict) -> dict:
    def g(key, default=0.0):
        try:
            return t.get(key, default)
        except (KeyError, TypeError, AttributeError):
            return default
    return {
        "speed": float(g("speed", 0.0)),
        "rpm": float(g("rpm", 0.0)),
        "gear": int(g("gear", 0)),
        "throttle": float(g("accel", g("throttle", 0.0))),
        "brake": float(g("brake", 0.0)),
        "slip_ratio": max(float(g("tire_slip_ratio_fl", 0.0)), float(g("tire_slip_ratio_fr", 0.0)), float(g("tire_slip_ratio_rl", 0.0)), float(g("tire_slip_ratio_rr", 0.0))),
        "on": bool(g("on", False)),
    }


def record_runtime_sample(settings, telemetry: dict | None = None, haptic_state=None, render_stats: dict | None = None, controller=None):
    """Cheap runtime sampler called from the driving loop.

    Keeps a fixed-size 120s ring buffer and mirrors the same compact records to
    Continuous Raw Logging when that developer feature is enabled.
    """
    global _LAST_RING_WRITE
    now = time.monotonic()
    # Keep the in-memory diagnostic buffer at ~20Hz even if telemetry packets
    # arrive faster.
    if now - _LAST_RING_WRITE < 0.05:
        return
    _LAST_RING_WRITE = now
    wall = time.time()
    rec = {"type": "runtime", "t": wall}
    if telemetry is not None:
        rec["telemetry"] = _compact_telemetry(telemetry)
    if haptic_state is not None:
        rec["haptic"] = {
            "surface": getattr(haptic_state, "dominant_surface", "unknown"),
            "road": [getattr(haptic_state, "road_l", 0.0), getattr(haptic_state, "road_r", 0.0)],
            "kerb": [getattr(haptic_state, "kerb_l", 0.0), getattr(haptic_state, "kerb_r", 0.0)],
            "gravel": [getattr(haptic_state, "gravel_l", 0.0), getattr(haptic_state, "gravel_r", 0.0)],
            "bump": [getattr(haptic_state, "bump_l", 0.0), getattr(haptic_state, "bump_r", 0.0)],
            "collision": getattr(haptic_state, "collision", 0.0),
            # telemetry-derived
            "rpm_norm": getattr(haptic_state, "rpm_norm", 0.0),
            "pitch_rate": getattr(haptic_state, "pitch_rate", 0.0),
            "roll_rate": getattr(haptic_state, "roll_rate", 0.0),
            "yaw_rate": getattr(haptic_state, "yaw_rate", 0.0),
            "susp_vel": [getattr(haptic_state, "susp_velocity_l", 0.0), getattr(haptic_state, "susp_velocity_r", 0.0)],
            "steer_vel": getattr(haptic_state, "steer_velocity", 0.0),
            "tire_temp_freq": getattr(haptic_state, "tire_temp_freq_mod", 1.0),
            "accel_long": getattr(haptic_state, "accel_longitudinal", 0.0),
            "ws_diff": getattr(haptic_state, "wheel_speed_diff", 0.0),
            # shift
            "shift_click": getattr(haptic_state, "shift_click", 0.0),
            "shift_kick": getattr(haptic_state, "shift_kick", 0.0),
            # engine renderers (new)
            "engine_braking": getattr(haptic_state, "engine_braking", 0.0),
            "turbo_spool": getattr(haptic_state, "turbo_spool", 0.0),
            "corner_exit": getattr(haptic_state, "corner_exit", 0.0),
            "redline_warning": getattr(haptic_state, "redline_warning", 0.0),
            # tire detail (new)
            "slip_sizzle": getattr(haptic_state, "slip_sizzle", 0.0),
            "tire_scrub": getattr(haptic_state, "tire_scrub", 0.0),
        }
    if render_stats:
        rec["render"] = {
            "l_rms": float(render_stats.get("render_l_rms", 0.0)),
            "r_rms": float(render_stats.get("render_r_rms", 0.0)),
            "limiter": float(render_stats.get("render_limiter_gain", 1.0)),
            "road_mid": float(render_stats.get("mix_road_mid_rms", 0.0)),
            "punch_to_mid": float(render_stats.get("mix_punch_to_mid_ratio", 0.0)),
            "shift_peak": float(render_stats.get("shift_final_out", render_stats.get("shift_ev_peak", 0.0))),
            "bus_master": float(render_stats.get("bus_master_gain", 1.0)),
            "bus_engine": float(render_stats.get("bus_engine_gain", 1.0)),
            "bus_surface": float(render_stats.get("bus_surface_gain", 1.0)),
            "bus_event": float(render_stats.get("bus_event_gain", 1.0)),
            "stream_error_count": int(render_stats.get("stream_error_count", 0)),
        }
    if controller is not None:
        rec["trigger"] = {
            "l2": str(getattr(controller, "last_l2_effect", "")),
            "r2": str(getattr(controller, "last_r2_effect", "")),
        }
    with _RING_LOCK:
        _RING.append(rec)
    RAW_LOGGER.write(rec)


def ring_records() -> list[dict]:
    with _RING_LOCK:
        return list(_RING)


def ring_status() -> dict:
    with _RING_LOCK:
        count = len(_RING)
    seconds = min(120.0, count / 20.0)
    # Conservative estimate of JSONL size.
    return {"samples": count, "seconds": seconds, "estimated_mb": max(0.1, count * 350 / (1024 * 1024))}


class ContinuousRawLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue(maxsize=20000)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active = False
        self._session_dir: Path | None = None
        self._file = None
        self._file_index = 1
        self._bytes = 0
        self._start_time = 0.0
        self._stop_time = 0.0
        self._current_file_path: Path | None = None
        self._split_bytes = 512 * 1024 * 1024
        self._last_error = ""

    def is_active(self) -> bool:
        return self._active

    def start(self, settings) -> Path:
        with self._lock:
            if self._active and self._session_dir:
                return self._session_dir
            ts = time.strftime("%Y%m%d_%H%M%S")
            root = paths.DATA / "raw_logs"
            root.mkdir(parents=True, exist_ok=True)
            self._session_dir = root / ts
            self._session_dir.mkdir(parents=True, exist_ok=True)
            self._file_index = 1
            self._bytes = 0
            self._start_time = time.time()
            self._stop_time = 0.0
            self._last_error = ""
            self._stop.clear()
            self._active = True
            self._write_session_files(settings)
            self._open_next_file_locked()
            self._thread = threading.Thread(target=self._writer_loop, daemon=True)
            self._thread.start()
            self.write({"type": "raw_log_start", "t": time.time(), "session_dir": str(self._session_dir)})
            return self._session_dir

    def stop(self):
        with self._lock:
            if not self._active:
                return
            self.write({"type": "raw_log_stop", "t": time.time()})
            self._stop_time = time.time()
            self._active = False
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            if self._file:
                try:
                    self._file.flush(); self._file.close()
                except OSError:
                    pass
                self._file = None
            self._write_readme_locked()

    def write(self, record: dict):
        if not self._active:
            return
        try:
            self._q.put_nowait(record)
        except queue.Full:
            self._last_error = "queue_full"

    def mark(self, label: str = "user_issue"):
        self.write({"type": "marker", "label": label, "t": time.time(), "note": "user marked an issue"})

    def _writer_loop(self):
        while not self._stop.is_set() or not self._q.empty():
            try:
                rec = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                line = json.dumps(_jsonable(rec), ensure_ascii=False, separators=(",", ":")) + "\n"
                data = line.encode("utf-8")
                with self._lock:
                    if self._file is None:
                        self._open_next_file_locked()
                    if self._file and self._bytes >= self._split_bytes:
                        self._open_next_file_locked()
                    if self._file:
                        self._file.write(line)
                        self._bytes += len(data)
            except (OSError, TypeError, json.JSONDecodeError) as e:
                self._last_error = str(e)

    def _open_next_file_locked(self):
        if not self._session_dir:
            return
        if self._file:
            try:
                self._file.flush(); self._file.close()
            except OSError:
                pass
        path = self._session_dir / f"raw_{self._file_index:03d}.jsonl"
        self._file_index += 1
        self._bytes = 0
        self._current_file_path = path
        self._file = path.open("a", encoding="utf-8")

    def _write_session_files(self, settings):
        if not self._session_dir:
            return
        try:
            store = profiles.load_profiles()
        except (OSError, json.JSONDecodeError) as e:
            store = {"error": str(e)}
        snapshot = {k: _jsonable(v) for k, v in vars(settings).items() if isinstance(v, (str, int, float, bool))}
        (self._session_dir / "session_info.json").write_text(json.dumps({
            "schema": "dhe-raw-session-v1",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "app_version": preferences._version(),
            "active_preset": store.get("active"),
            "unlimited_total_size": True,
            "file_split_mb": int(self._split_bytes / (1024 * 1024)),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (self._session_dir / "settings_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        (self._session_dir / "changed_settings_snapshot.json").write_text(json.dumps(option_registry.changed_from_defaults(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        (self._session_dir / "tester_notes.txt").write_text("── ─────\n", encoding="utf-8")
        files = [
            paths.ROOT / "app.py",
            paths.ROOT / "ui" / "app.py",
            paths.ROOT / "ui" / "pages" / "tuningPage.py",
            paths.ROOT / "runtime" / "diagnostics.py",
            paths.ROOT / "config" / "settings.py",
            paths.ROOT / "config" / "option_registry.py",
        ]
        (self._session_dir / "file_hashes.json").write_text(json.dumps({str(p.relative_to(paths.ROOT)): _hash_file(p) for p in files if p.exists()}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_readme_locked(self):
        if not self._session_dir:
            return
        end = self._stop_time or time.time()
        elapsed = max(0, int(end - self._start_time)) if self._start_time else 0
        try:
            total = sum(p.stat().st_size for p in self._session_dir.glob("**/*") if p.is_file())
        except OSError:
            total = 0
        text = (
            "DHE raw logging session\n"
            f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._start_time or time.time()))}\n"
            f"Duration: {elapsed//60:02d}:{elapsed%60:02d}\n"
            f"Total size: {total / (1024*1024):.1f} MB\n"
            "Files are split for editor compatibility. Total session size is not capped.\n"
        )
        try:
            (self._session_dir / "README_TEST_SESSION.txt").write_text(text, encoding="utf-8")
            markers = 0
            raw_files = list(self._session_dir.glob("raw_*.jsonl"))
            for path in raw_files:
                try:
                    markers += sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if '"type":"marker"' in line or '"type": "marker"' in line)
                except OSError:
                    pass
            summary = {
                "schema": "dhe-raw-analysis-v1",
                "duration_s": elapsed,
                "total_mb": total / (1024 * 1024),
                "raw_files": len(raw_files),
                "markers": markers,
                "last_error": self._last_error,
            }
            (self._session_dir / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def status(self) -> dict:
        with self._lock:
            session = self._session_dir
            active = self._active
            start = self._start_time
            stop = self._stop_time
            err = self._last_error
            current_file = self._current_file_path
        total = 0
        if session and session.exists():
            try:
                total = sum(p.stat().st_size for p in session.glob("**/*") if p.is_file())
            except OSError:
                total = 0
        free = None
        try:
            free = shutil.disk_usage(str(paths.DATA)).free
        except OSError:
            pass
        return {
            "active": active,
            "session_dir": str(session) if session else "",
            "elapsed_s": max(0, (time.time() if active else (stop or start)) - start) if start else 0,
            "bytes": total,
            "current_file": str(current_file) if current_file else "",
            "free_bytes": free,
            "last_error": err,
        }

    def zip_current_session(self) -> Path:
        st = self.status()
        session = Path(st.get("session_dir") or "")
        if not session.exists():
            raise FileNotFoundError("no raw log session")
        out = session.with_suffix(".zip")
        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as zf:
            for p in session.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(session))
        return out


RAW_LOGGER = ContinuousRawLogger()


def export_recent_diagnostic(settings, out_dir: str | Path | None = None, note: str = "") -> Path:
    """Save the current ring buffer as a compact ZIP.

    UI captures can wait 30s after a click, then call this. The resulting bundle
    includes the previous buffered window plus the additional after-click window.
    """
    global _LAST_DIAGNOSTIC_PATH
    path = export_diagnostic_bundle(settings, out_dir=out_dir, note=note)
    records = ring_records()
    if records:
        # Rewrite/add runtime ring files into the existing bundle without
        # disturbing the existing diagnostic structure.
        with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
            zf.writestr("ring_runtime.jsonl", "\n".join(json.dumps(_jsonable(r), ensure_ascii=False, separators=(",", ":")) for r in records))
            zf.writestr("ring_status.json", json.dumps(ring_status(), ensure_ascii=False, indent=2))
    _LAST_DIAGNOSTIC_PATH = path
    return path
