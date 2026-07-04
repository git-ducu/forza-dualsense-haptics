"""Telemetry processing loop — reads UDP packets, computes trigger effects, drives haptic audio."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from telemetry.haptics.audioEngine import HapticAudioEngine, HapticState
from telemetry.process import ProcessWatcher
from telemetry import surfaceEffects as haptic_textures
from runtime import diagnostics
from telemetry.packet import PacketReader

if TYPE_CHECKING:
    from config.settings import Settings
    from dsio.device import DualSenseWriter
    from telemetry.receiver import TelemetryReceiver

log = logging.getLogger("dhe")


def _max_abs(t: dict, prefix: str) -> float:
    return max(abs(t[f"{prefix}_{wheel}"]) for wheel in ("fl", "fr", "rl", "rr"))


def _max_abs_wheels(t: dict, prefix: str, wheels: tuple[str, ...]) -> float:
    return max(abs(float(t[f"{prefix}_{wheel}"])) for wheel in wheels)


def _driven_wheels(t: dict) -> tuple[str, ...]:
    return {0: ("fl", "fr"), 1: ("rl", "rr"), 2: ("fl", "fr", "rl", "rr")}.get(int(t["drive_train"]), ("fl", "fr", "rl", "rr"))


def _trigger_detail(t: dict, frame) -> str:
    driven = _driven_wheels(t)
    spin_ratio = _max_abs_wheels(t, "tire_slip_ratio", driven)
    spin_combined = _max_abs_wheels(t, "tire_combined_slip", driven)
    road_l = max(abs(float(t[f"surface_rumble_{w}"])) for w in ("fl", "rl"))
    road_r = max(abs(float(t[f"surface_rumble_{w}"])) for w in ("fr", "rr"))
    scrub_f = _max_abs_wheels(t, "tire_slip_angle", ("fl", "fr"))
    scrub_r = _max_abs_wheels(t, "tire_slip_angle", ("rl", "rr"))
    abs_f = max(_max_abs_wheels(t, "tire_slip_ratio", ("fl", "fr")), _max_abs_wheels(t, "tire_combined_slip", ("fl", "fr")))
    abs_r = max(_max_abs_wheels(t, "tire_slip_ratio", ("rl", "rr")), _max_abs_wheels(t, "tire_combined_slip", ("rl", "rr")))
    rpm_ratio = (float(t["rpm"]) / float(t["max_rpm"])) if float(t["max_rpm"]) > 0 else 0.0
    return (
        f"L2={getattr(frame, 'leftLabel', '?')} R2={getattr(frame, 'rightLabel', '?')} | "
        f"{t['speed']:.1f}km/h gear={t['gear']} gas={t['accel']} brake={t['brake']} rpm={rpm_ratio:.2f} | "
        f"spinR={spin_ratio:.2f} spinC={spin_combined:.2f} roadL={road_l:.2f} roadR={road_r:.2f} "
        f"scrubF={scrub_f:.2f} scrubR={scrub_r:.2f} absF={abs_f:.2f} absR={abs_r:.2f}"
    )


def _haptic_detail(st: HapticState, render_stats: dict | None = None) -> str:
    render_stats = render_stats or {}
    l_rms = float(render_stats.get('render_l_rms', 0.0))
    r_rms = float(render_stats.get('render_r_rms', 0.0))
    side_sum = max(1e-6, l_rms + r_rms)
    side_ratio = f"L{int(round(l_rms / side_sum * 100)):02d}:R{int(round(r_rms / side_sum * 100)):02d}"
    render_tail = (
        f" renderRMS={l_rms:.3f}/{r_rms:.3f}"
        f" render?={float(render_stats.get('render_lr_delta', 0.0)):.3f}"
        f" side={side_ratio}"
        f" peak={float(render_stats.get('render_l_peak', 0.0)):.3f}/{float(render_stats.get('render_r_peak', 0.0)):.3f}"
        f" lim={float(render_stats.get('render_limiter_gain', 1.0)):.2f}"
        f" mixP={float(render_stats.get('mix_punch_level', 0.0)):.2f}"
        f" hard={float(render_stats.get('mix_hard_punch', 0.0)):.2f} soft={float(render_stats.get('mix_soft_punch', 0.0)):.2f}"
        f" roadMid={float(render_stats.get('mix_road_mid_rms', 0.0)):.3f} p/m={float(render_stats.get('mix_punch_to_mid_ratio', 0.0)):.2f}"
        f" glue={float(render_stats.get('mix_glue_level_l', 0.0)):.2f}/{float(render_stats.get('mix_glue_level_r', 0.0)):.2f}"
        f" duck={float(render_stats.get('mix_mid_duck_gain', 1.0)):.2f}"
    )
    return (
        f"road={st.road_l:.2f}/{st.road_r:.2f} rough={getattr(st, 'rough_asphalt_l', 0):.2f}/{getattr(st, 'rough_asphalt_r', 0):.2f} "
        f"kerb={st.kerb_l:.2f}/{st.kerb_r:.2f} gravel={st.gravel_l:.2f}/{st.gravel_r:.2f} "
        f"dirt={getattr(st, 'dirt_l', 0):.2f}/{getattr(st, 'dirt_r', 0):.2f} puddle={st.puddle_l:.2f}/{st.puddle_r:.2f} "
        f"surface={getattr(st, 'dominant_surface', '?')}({getattr(st, 'surface_confidence', 0):.2f}) trans={getattr(st, 'surface_transition', '') or '-'} "
        f"wet={getattr(st, 'wetness', 0):.2f} wetasp={getattr(st, 'wet_asphalt_l', 0):.2f}/{getattr(st, 'wet_asphalt_r', 0):.2f} "
        f"mud={getattr(st, 'mud_l', 0):.2f}/{getattr(st, 'mud_r', 0):.2f} spray={getattr(st, 'spray_l', 0):.2f}/{getattr(st, 'spray_r', 0):.2f} "
        f"ice={getattr(st, 'ice_l', 0):.2f}/{getattr(st, 'ice_r', 0):.2f} snow={max(getattr(st, 'packed_snow_l', 0), getattr(st, 'loose_snow_l', 0)):.2f}/{max(getattr(st, 'packed_snow_r', 0), getattr(st, 'loose_snow_r', 0)):.2f} "
        f"slush={getattr(st, 'slush_l', 0):.2f}/{getattr(st, 'slush_r', 0):.2f} sand={getattr(st, 'sand_l', 0):.2f}/{getattr(st, 'sand_r', 0):.2f} "
        f"water={getattr(st, 'thin_water_l', 0):.2f}/{getattr(st, 'thin_water_r', 0):.2f}/{getattr(st, 'deep_water_l', 0):.2f}/{getattr(st, 'deep_water_r', 0):.2f} "
        f"grip={getattr(st, 'asphalt_grip_l', 0):.2f}/{getattr(st, 'asphalt_grip_r', 0):.2f} slide={getattr(st, 'slide_l', 0):.2f}/{getattr(st, 'slide_r', 0):.2f} "
        f"under={getattr(st, 'understeer_l', 0):.2f}/{getattr(st, 'understeer_r', 0):.2f} over={getattr(st, 'oversteer_l', 0):.2f}/{getattr(st, 'oversteer_r', 0):.2f} land={getattr(st, 'landing', 0):.2f} bottom={getattr(st, 'bottom_out', 0):.2f} "
        f"brake={getattr(st, 'brake_body_l', 0):.2f}/{getattr(st, 'brake_body_r', 0):.2f} absb={getattr(st, 'abs_body_l', 0):.2f}/{getattr(st, 'abs_body_r', 0):.2f} "
        f"scrape={getattr(st, 'scrape_l', 0):.2f}/{getattr(st, 'scrape_r', 0):.2f} echo={getattr(st, 'rear_echo_l', 0):.2f}/{getattr(st, 'rear_echo_r', 0):.2f} "
        f"bump={st.bump_l:.2f}/{st.bump_r:.2f} collision={st.collision:.2f} crack={getattr(st, 'collision_crack', 0):.2f} "
        f"busC={getattr(st, 'continuous_bus_l', 0):.2f}/{getattr(st, 'continuous_bus_r', 0):.2f} busV={getattr(st, 'vehicle_bus_l', 0):.2f}/{getattr(st, 'vehicle_bus_r', 0):.2f} busE={getattr(st, 'event_bus_l', 0):.2f}/{getattr(st, 'event_bus_r', 0):.2f} "
        f"lr?={getattr(st, 'lr_delta', 0):.2f} center={getattr(st, 'center_body_level', 0):.2f} gate={getattr(st, 'surface_gate', 1):.2f} "
        f"duckC={getattr(st, 'continuous_duck_l', 1):.2f}/{getattr(st, 'continuous_duck_r', 1):.2f} duckV={getattr(st, 'vehicle_duck_l', 1):.2f}/{getattr(st, 'vehicle_duck_r', 1):.2f} "
        f"engine={getattr(st, 'idle_engine', 0):.2f}/{getattr(st, 'launch_load', 0):.2f}/{getattr(st, 'boost_build', 0):.2f} speed={st.speed_kmh:.1f}"
        + render_tail
    )


def _haptic_wanted(s: Settings) -> bool:
    return bool(getattr(s, "enable_haptic_audio", False))



def _haptic_record_path(settings: Settings | None = None) -> Path:
    raw = getattr(settings, "haptic_telemetry_record_path", "data/haptic_telemetry_record.jsonl") if settings is not None else "data/haptic_telemetry_record.jsonl"
    return Path(str(raw) or "data/haptic_telemetry_record.jsonl")


def _write_haptic_record(t: dict, st: HapticState, now: float, render_stats: dict | None = None, settings: Settings | None = None) -> None:
    render_stats = render_stats or {}
    try:
        path = _haptic_record_path(settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "time": now,
            "telemetry": {k: t[k] for k in t.keys() if isinstance(t[k], (int, float, bool))},
            "haptic": {
                "surface": getattr(st, "dominant_surface", "unknown"),
                "surface_confidence": getattr(st, "surface_confidence", 0.0),
                "transition": getattr(st, "surface_transition", ""),
                "road": [st.road_l, st.road_r],
                "gravel": [st.gravel_l, st.gravel_r],
                "wet": getattr(st, "wetness", 0.0),
                "ice": [getattr(st, "ice_l", 0.0), getattr(st, "ice_r", 0.0)],
                "snow": [max(getattr(st, "packed_snow_l", 0.0), getattr(st, "loose_snow_l", 0.0)), max(getattr(st, "packed_snow_r", 0.0), getattr(st, "loose_snow_r", 0.0))],
                "slush": [getattr(st, "slush_l", 0.0), getattr(st, "slush_r", 0.0)],
                "sand": [getattr(st, "sand_l", 0.0), getattr(st, "sand_r", 0.0)],
                "puddle": [st.puddle_l, st.puddle_r],
                "kerb": [st.kerb_l, st.kerb_r],
                "understeer": [getattr(st, "understeer_l", 0.0), getattr(st, "understeer_r", 0.0)],
                "oversteer": [getattr(st, "oversteer_l", 0.0), getattr(st, "oversteer_r", 0.0)],
                "landing": getattr(st, "landing", 0.0),
                "bottom_out": getattr(st, "bottom_out", 0.0),
                "bus": [[getattr(st, "continuous_bus_l", 0.0), getattr(st, "continuous_bus_r", 0.0)], [getattr(st, "vehicle_bus_l", 0.0), getattr(st, "vehicle_bus_r", 0.0)], [getattr(st, "event_bus_l", 0.0), getattr(st, "event_bus_r", 0.0)]],
                "lr_delta": getattr(st, "lr_delta", 0.0),
                "center_body_level": getattr(st, "center_body_level", 0.0),
                "surface_gate": getattr(st, "surface_gate", 1.0),
                "axis": {
                    "accel_x": float(t["accel_x"]), "accel_y": float(t["accel_y"]), "accel_z": float(t["accel_z"]),
                    "velocity_x": float(t["velocity_x"]), "angular_velocity_y": float(t["angular_velocity_y"]),
                    "lateral_g_used": getattr(st, "lateral_g_used", 0.0),
                },
                "render": {
                    "l_rms": float(render_stats.get("render_l_rms", 0.0)),
                    "r_rms": float(render_stats.get("render_r_rms", 0.0)),
                    "lr_delta": float(render_stats.get("render_lr_delta", 0.0)),
                    "side_ratio_l": float(render_stats.get("render_l_rms", 0.0)) / max(1e-6, float(render_stats.get("render_l_rms", 0.0)) + float(render_stats.get("render_r_rms", 0.0))),
                    "l_peak": float(render_stats.get("render_l_peak", 0.0)),
                    "r_peak": float(render_stats.get("render_r_peak", 0.0)),
                    "limiter_gain": float(render_stats.get("render_limiter_gain", 1.0)),
                    "mix_feature_road": float(render_stats.get("mix_feature_road", 0.0)),
                    "mix_feature_load": float(render_stats.get("mix_feature_load", 0.0)),
                    "mix_feature_tire_edge": float(render_stats.get("mix_feature_tire_edge", 0.0)),
                    "mix_punch_level": float(render_stats.get("mix_punch_level", 0.0)),
                    "mix_punch_shift": float(render_stats.get("mix_punch_shift", 0.0)),
                    "mix_punch_impact": float(render_stats.get("mix_punch_impact", 0.0)),
                    "mix_punch_bump": float(render_stats.get("mix_punch_bump", 0.0)),
                    "mix_punch_grip": float(render_stats.get("mix_punch_grip", 0.0)),
                    "mix_mid_duck_gain": float(render_stats.get("mix_mid_duck_gain", 1.0)),
                    "mix_low_punch_l": float(render_stats.get("mix_low_punch_l", 0.0)),
                    "mix_low_punch_r": float(render_stats.get("mix_low_punch_r", 0.0)),
                    "mix_high_punch_l": float(render_stats.get("mix_high_punch_l", 0.0)),
                    "mix_high_punch_r": float(render_stats.get("mix_high_punch_r", 0.0)),
                    "mix_hard_punch": float(render_stats.get("mix_hard_punch", 0.0)),
                    "mix_soft_punch": float(render_stats.get("mix_soft_punch", 0.0)),
                    "mix_punch_edge_shift": float(render_stats.get("mix_punch_edge_shift", 0.0)),
                    "mix_punch_edge_impact": float(render_stats.get("mix_punch_edge_impact", 0.0)),
                    "mix_punch_edge_bump": float(render_stats.get("mix_punch_edge_bump", 0.0)),
                    "mix_punch_edge_grip": float(render_stats.get("mix_punch_edge_grip", 0.0)),
                    "mix_road_mid_rms": float(render_stats.get("mix_road_mid_rms", 0.0)),
                    "mix_surface_mid_rms": float(render_stats.get("mix_surface_mid_rms", 0.0)),
                    "mix_vehicle_rms": float(render_stats.get("mix_vehicle_rms", 0.0)),
                    "mix_event_rms": float(render_stats.get("mix_event_rms", 0.0)),
                    "mix_punch_to_mid_ratio": float(render_stats.get("mix_punch_to_mid_ratio", 0.0)),
                    "mix_glue_to_mid_ratio": float(render_stats.get("mix_glue_to_mid_ratio", 0.0)),
                    "mix_mid_protect_gain": float(render_stats.get("mix_mid_protect_gain", 1.0)),
                    "mix_sidechain_gain": float(render_stats.get("mix_sidechain_gain", 1.0)),
                    "mix_event_trim_gain": float(render_stats.get("mix_event_trim_gain", 1.0)),
                },
            },
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    except (OSError, TypeError, json.JSONDecodeError) as e:
        log.debug("haptic record failed: %s", e)

def run(ds: "DualSenseWriter", listener: "TelemetryReceiver", s: "Settings", stop_event: Event | None = None, telemetry_sink=None) -> None:
    """Main driving loop: receives telemetry, updates triggers, runs haptic engine."""
    from dsio.trigger.effects import clearEffect
    from telemetry.triggerMap import computeTriggerFrame, EffectMemory, TriggerFrame
    from config.tuning import Tuning, sync_tuning_from_settings
    OFF = clearEffect()
    mem = EffectMemory()
    tuning = Tuning()
    sync_tuning_from_settings(tuning, s)
    reader = PacketReader()
    prev = None
    last_pkt = time.monotonic()
    last_log = 0.0
    last_effect_log = 0.0
    last_effect_pair = None
    last_haptic_log = 0.0
    last_haptic_record = 0.0
    last_tuning_sync = 0.0
    last_trigger_error_log = 0.0
    pkt_count = 0

    watcher = ProcessWatcher(s.game_process_name_contains, s.game_poll_interval_s)
    haptic_engine = HapticAudioEngine(s)
    _haptic_retry_after = 0.0  # cooldown: don't spam start() on missing device



    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            now = time.monotonic()

            # Sync tuning from settings every 0.5s to pick up live UI changes
            if now - last_tuning_sync >= 0.5:
                last_tuning_sync = now
                sync_tuning_from_settings(tuning, s)

            # MARK: haptic audio can be toggled while the loop is running.
            if _haptic_wanted(s) and not haptic_engine.running:
                if now >= _haptic_retry_after:
                    if not haptic_engine.start():
                        _haptic_retry_after = now + 3.0  # retry every 3s
            elif not _haptic_wanted(s) and haptic_engine.running:
                haptic_engine.stop()

            if s.exit_on_game_close:
                # MARK: defensive - never let watcher errors kill the loop silently
                try:
                    if watcher.should_exit():
                        log.info("Game process closed --exiting.")
                        break
                except (OSError, RuntimeError) as e:
                    log.warning("game-close watcher error: %s", e)

            pkt, addr = listener.recv_latest()

            if pkt is None:
                idle = now - last_pkt
                if idle > 5.0 and not getattr(listener, "lost", False):
                    log.warning("Telemetry stream inactive: verify Data Out, host, port, and firewall")
                    listener.lost = True
                if idle > 1.0 and prev != (OFF, OFF):
                    ds.set(OFF, OFF); prev = (OFF, OFF)
                # Fallback exit: telemetry was flowing, then stopped for too long
                # (game killed via Task Manager, or psutil missed the process).
                if pkt_count > 0 and idle > s.telemetry_lost_exit_s:
                    log.info("Telemetry lost for %.0fs --exiting.", idle)
                    break
                continue

            pkt_count += 1
            last_pkt = now
            listener.lost = False
            if pkt_count == 1:
                log.info("Telemetry stream opened from %s:%d, datagram=%d bytes", addr[0], addr[1], len(pkt))

            try:
                vs = reader.decodeDataOutPacket(pkt)
                t = vs.asLegacyDict()
            except ValueError as e:
                log.warning("Bad packet from %s:%d (%d bytes): %s", addr[0], addr[1], len(pkt), e)
                continue

            # MARK: never let a trigger logic bug kill the loop - fail-safe OFF/OFF
            try:
                frame = computeTriggerFrame(vs, mem, tuning, now, t, s)
                left, right = frame.left, frame.right
            except Exception as e:
                if now - last_trigger_error_log > 1.0:
                    log.warning("computeTriggerFrame failed: %s", e)
                    last_trigger_error_log = now
                left, right = clearEffect(), clearEffect()
                frame = TriggerFrame(left, right, "off", "off")

            # MARK: optional audio-haptic output path. Failure must not affect triggers.
            hst = None
            render_stats = None
            if haptic_engine.running:
                try:
                    hst = haptic_textures.build_state(t, s, now)
                    haptic_engine.update(hst)
                    render_stats = haptic_engine.render_stats()
                    if getattr(s, "enable_haptic_audio_log", False) and now - last_haptic_log >= 0.50:
                        last_haptic_log = now
                        log.info("HAPTIC %s", _haptic_detail(hst, render_stats))
                    if getattr(s, "haptic_telemetry_recording_enabled", False):
                        hz = max(1.0, float(getattr(s, "haptic_telemetry_record_hz", 20.0)))
                        if now - last_haptic_record >= 1.0 / hz:
                            last_haptic_record = now
                            _write_haptic_record(t, hst, now, render_stats, s)
                except Exception as e:
                    log.debug("haptic update failed: %s", e)

            # Feed live telemetry + bus levels to GUI (after haptic so render_stats is ready)
            if telemetry_sink is not None:
                try:
                    if render_stats:
                        t["_bus_surface"] = render_stats.get("mix_surface_mid_rms", 0)
                        t["_bus_vehicle"] = render_stats.get("mix_vehicle_rms", 0)
                        t["_bus_engine"] = render_stats.get("mix_engine_rms", 0)
                        t["_bus_event"] = render_stats.get("mix_event_rms", 0)
                    telemetry_sink(t)
                except Exception as e:
                    log.debug("telemetry_sink failed: %s", e)

            try:
                diagnostics.record_runtime_sample(s, t, hst, render_stats, frame)
            except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                log.debug("diagnostic runtime sample failed: %s", e)

            if getattr(s, "enable_trigger_info_log", False):
                pair = (frame.leftLabel, frame.rightLabel)
                # INFO log goes to the existing Logs tab; no file is written.
                # Throttle to avoid flooding while still catching effect changes.
                if pair != last_effect_pair and now - last_effect_log >= 0.18:
                    last_effect_pair = pair
                    last_effect_log = now
                    log.info("TRIGGER %s", _trigger_detail(t, frame))

            frame = (left, right)
            if frame != prev:
                try:
                    ds.set(left, right); prev = frame
                except (OSError, RuntimeError) as e:
                    # MARK: HID write can fail on disconnect; reconnect logic will retry
                    log.debug("ds.set failed: %s", e)

            if now - last_log >= 1.0:
                last_log = now
                tag = "RACE" if t["on"] else "MENU"
                slip_r = _max_abs(t, "tire_slip_ratio")
                slip_c = _max_abs(t, "tire_combined_slip")
                log.debug("[%s] %6.1f km/h | gear %d | gas %3d R=%s | brake %3d L=%s | slip %.2f combined %.2f",
                          tag, t["speed"], t["gear"], t["accel"], right, t["brake"], left, slip_r, slip_c)
    finally:
        haptic_engine.stop()
