"""DualSense audio-haptics backend.

Direct audio-haptic output path. This stays isolated from the HID trigger writer:
if audio-haptics fails, DHE trigger feedback keeps running.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from math import exp as _exp
import threading
import time as _time

from dsio.audio.device import find_device, list_output_devices, dualsense_candidates
from dsio.haptics.waveform import Osc, make_test_texture, noise, noise_burst, pulse_train, soft_clip, envelope_preset
from .musicalMixer import apply_musical_mix, extract_features, haptic_priority_from_state, pick_freq
from dsio.haptics.transient import HapticTransientBank
from dsio.haptics.mastering import HapticMasteringChain
from .transientPresets import make_forza_transient_bank

log = logging.getLogger("dhe")

try:  # optional runtime dependency; imported lazily at stream open too
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


@dataclass(slots=True)
class StereoLevel:
    """Stereo L/R level pair for haptic signals."""
    l: float = 0.0
    r: float = 0.0
    
    def __iter__(self):
        return iter((self.l, self.r))
    
    def max(self) -> float:
        return max(self.l, self.r)
    
    def sum(self) -> float:
        return self.l + self.r


@dataclass
class WheelLevels:
    """Four-wheel level for wheel-specific events."""
    fl: float = 0.0
    fr: float = 0.0
    rl: float = 0.0
    rr: float = 0.0
    
    @property
    def front_l(self) -> float:
        return self.fl
    
    @property
    def front_r(self) -> float:
        return self.fr
    
    @property
    def rear_l(self) -> float:
        return self.rl
    
    @property
    def rear_r(self) -> float:
        return self.rr
    
    def to_stereo(self) -> tuple[float, float]:
        """Combine to L/R stereo: L = FL+RL, R = FR+RR"""
        return (self.fl + self.rl, self.fr + self.rr)


@dataclass
class HapticState:
    # Continuous/background side textures
    road_l: float = 0.0
    road_r: float = 0.0
    gravel_l: float = 0.0
    gravel_r: float = 0.0
    wheelspin_l: float = 0.0
    wheelspin_r: float = 0.0
    scrub_l: float = 0.0
    scrub_r: float = 0.0
    rough_asphalt_l: float = 0.0
    rough_asphalt_r: float = 0.0
    dirt_l: float = 0.0
    dirt_r: float = 0.0
    grass_l: float = 0.0
    grass_r: float = 0.0
    wet_asphalt_l: float = 0.0
    wet_asphalt_r: float = 0.0
    mud_l: float = 0.0
    mud_r: float = 0.0
    spray_l: float = 0.0
    spray_r: float = 0.0
    # Expanded surface/weather classifier layers. These are inferred because
    # Forza Data Out does not expose a material/weather enum here.
    ice_l: float = 0.0
    ice_r: float = 0.0
    packed_snow_l: float = 0.0
    packed_snow_r: float = 0.0
    loose_snow_l: float = 0.0
    loose_snow_r: float = 0.0
    slush_l: float = 0.0
    slush_r: float = 0.0
    sand_l: float = 0.0
    sand_r: float = 0.0
    thin_water_l: float = 0.0
    thin_water_r: float = 0.0
    deep_water_l: float = 0.0
    deep_water_r: float = 0.0
    wet_tire_tail_l: float = 0.0
    wet_tire_tail_r: float = 0.0
    surface_transition_l: float = 0.0
    surface_transition_r: float = 0.0
    rear_echo_l: float = 0.0
    rear_echo_r: float = 0.0
    scrape_l: float = 0.0
    scrape_r: float = 0.0
    collision_crack: float = 0.0

    # Wheel-specific events. Front/rear cannot be true channels on DualSense,
    # so the renderer encodes them using different frequency/envelope shapes.
    kerb_fl: float = 0.0
    kerb_fr: float = 0.0
    kerb_rl: float = 0.0
    kerb_rr: float = 0.0
    puddle_fl: float = 0.0
    puddle_fr: float = 0.0
    puddle_rl: float = 0.0
    puddle_rr: float = 0.0
    bump_fl: float = 0.0
    bump_fr: float = 0.0
    bump_rl: float = 0.0
    bump_rr: float = 0.0

    # Backward-compatible aggregate fields used by logs/UI.
    kerb_l: float = 0.0
    kerb_r: float = 0.0
    puddle_l: float = 0.0
    puddle_r: float = 0.0
    bump_l: float = 0.0
    bump_r: float = 0.0

    # Collision can be spatially biased if telemetry gives a lateral impulse.
    collision: float = 0.0
    collision_l: float = 0.0
    collision_r: float = 0.0

    # Body/vehicle-state layers.
    weight_l: float = 0.0
    weight_r: float = 0.0
    weight_pulse_l: float = 0.0
    weight_pulse_r: float = 0.0
    asphalt_grip_l: float = 0.0
    asphalt_grip_r: float = 0.0
    slide_l: float = 0.0
    slide_r: float = 0.0
    slide_pulse_l: float = 0.0
    slide_pulse_r: float = 0.0
    # 6.2 drift/slide chaos: separate from road texture so drift can cut through.
    slide_chaos_l: float = 0.0
    slide_chaos_r: float = 0.0
    rear_breakaway_l: float = 0.0
    rear_breakaway_r: float = 0.0
    side_scrub_edge_l: float = 0.0
    side_scrub_edge_r: float = 0.0
    tire_scrub_l: float = 0.0
    tire_scrub_r: float = 0.0
    tire_smear_l: float = 0.0
    tire_smear_r: float = 0.0
    slip_sizzle_l: float = 0.0
    slip_sizzle_r: float = 0.0
    asphalt_drift_l: float = 0.0
    asphalt_drift_r: float = 0.0
    offroad_drift_l: float = 0.0
    offroad_drift_r: float = 0.0
    drift_confidence: float = 0.0
    understeer_l: float = 0.0
    understeer_r: float = 0.0
    oversteer_l: float = 0.0
    oversteer_r: float = 0.0
    four_wheel_slide: float = 0.0
    airborne: float = 0.0
    landing: float = 0.0
    bottom_out: float = 0.0
    tire_temp_grip: float = 1.0
    vehicle_character: float = 0.0
    idle_engine: float = 0.0
    launch_load: float = 0.0
    launch_release: float = 0.0
    boost_build: float = 0.0
    torque_surge: float = 0.0
    # Post-shift torque engagement: torque delivered through drivetrain after shift
    shift_engagement: float = 0.0      # Transient: clutch engagement shock
    shift_kick: float = 0.0
    shift_click: float = 0.0
    shift_clunk: float = 0.0
    shift_rattle: float = 0.0
    shift_tail: float = 0.0
    shift_torque_cut: float = 0.0
    shift_character: str = "street_sport"
    shift_gear: float = 3.0  # gear number after shift (for low/high gear feel)
    # Longitudinal G-force onset feedback (accel/decel onset impact)
    # Not continuous vibration -- only fires at moment of onset
    accel_onset: float = 0.0           # Transient: sudden acceleration onset
    decel_onset: float = 0.0           # Transient: sudden deceleration onset
    brake_body_l: float = 0.0
    brake_body_r: float = 0.0
    abs_body_l: float = 0.0
    abs_body_r: float = 0.0
    wetness: float = 0.0
    ice_confidence: float = 0.0
    snow_confidence: float = 0.0
    slush_confidence: float = 0.0
    sand_confidence: float = 0.0
    surface_confidence: float = 0.0
    dominant_surface: str = "unknown"
    surface_transition: str = ""
    continuous_duck_l: float = 1.0
    continuous_duck_r: float = 1.0
    vehicle_duck_l: float = 1.0
    vehicle_duck_r: float = 1.0
    event_bus_l: float = 0.0
    event_bus_r: float = 0.0
    vehicle_bus_l: float = 0.0
    vehicle_bus_r: float = 0.0
    continuous_bus_l: float = 0.0
    continuous_bus_r: float = 0.0
    lr_delta: float = 0.0
    center_body_level: float = 0.0
    surface_gate: float = 1.0
    speed_kmh: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    lateral_g_used: float = 0.0

    # extended telemetry fields -- derived from previously-unused Forza data
    rpm_norm: float = 0.0           # 0..1 normalized RPM (idle→max)
    max_rpm: float = 0.0            # vehicle max RPM (for adaptive redline)
    idle_rpm: float = 0.0           # vehicle idle RPM
    pitch_rate: float = 0.0         # angular_velocity_x: braking dive / accel squat
    roll_rate: float = 0.0          # angular_velocity_z: cornering roll
    yaw_rate: float = 0.0           # angular_velocity_y: spin/drift rate
    susp_velocity_l: float = 0.0    # per-side suspension compression velocity
    susp_velocity_r: float = 0.0
    steer_velocity: float = 0.0     # steering wheel rotation rate (turn-in speed)
    tire_temp_freq_mod: float = 1.0 # frequency shift from tire temp (cold=bright, hot=muted)
    accel_longitudinal: float = 0.0 # forward/brake acceleration (velocity_change proxy)
    wheel_speed_diff: float = 0.0   # front-rear wheel speed difference (traction signal)
    
    # Engine enhancement fields (6 new features)
    rpm_harmonics: float = 0.0      # NEW: cylinder harmonic intensity (4/6/8 cyl feel)
    redline_warning: float = 0.0    # NEW: redline pulse warning (RPM 90%+)
    turbo_spool: float = 0.0        # NEW: turbo build-up high-freq whistle
    engine_braking: float = 0.0     # NEW: engine braking drag feel
    corner_exit_torque: float = 0.0 # NEW: corner exit power/torque
    engine_start: float = 0.0       # NEW: start sequence (cranking→idle)
    cylinder_count: int = 4         # estimated cylinder count (4/6/8/10/12)

    # Audio-render callback diagnostics. These reflect what is actually sent to
    # the DualSense channels after bus mix, signal boost, limiter and master gain.
    render_l_rms: float = 0.0
    render_r_rms: float = 0.0
    render_lr_delta: float = 0.0
    render_l_peak: float = 0.0
    render_r_peak: float = 0.0
    render_limiter_gain: float = 1.0

# Internal engine amplitude baseline. Not user-facing.
# Makes settings 1.0 feel strong; users lower to 0.6-0.8 to reduce.
_ENGINE_BASE_AMP = 1.5

HAPTIC_PRIORITY_MODES = {
    "balanced": {"road": 1.00, "kerb": 1.00, "gravel": 1.00, "puddle": 1.00, "wheelspin": 1.00, "scrub": 1.00, "bump": 1.00, "collision": 1.00, "weight": 1.00, "asphalt_grip": 1.00, "slide": 1.00, "engine": 1.00, "palette": 1.00, "scrape": 1.00, "weather": 1.00, "brake": 1.00, "snow": 1.00, "ice": 1.00, "slush": 1.00, "sand": 1.00, "water": 1.00, "transition": 1.00},
    "texture": {"road": 1.35, "kerb": 1.15, "gravel": 1.12, "puddle": 1.08, "wheelspin": 0.75, "scrub": 0.80, "bump": 0.95, "collision": 0.95, "weight": 1.05, "asphalt_grip": 1.10, "slide": 0.85, "engine": 0.80, "palette": 1.20, "scrape": 0.90, "weather": 1.18, "brake": 0.90, "snow": 1.16, "ice": 1.12, "slush": 1.12, "sand": 1.10, "water": 1.12, "transition": 1.12},
    "rally": {"road": 0.95, "kerb": 1.08, "gravel": 1.28, "puddle": 1.12, "wheelspin": 0.90, "scrub": 0.80, "bump": 1.35, "collision": 1.08, "weight": 1.15, "asphalt_grip": 0.90, "slide": 1.10, "engine": 0.85, "palette": 1.18, "scrape": 1.10, "weather": 1.22, "brake": 1.05, "snow": 1.24, "ice": 1.05, "slush": 1.22, "sand": 1.25, "water": 1.12, "transition": 1.14},
    "grip": {"road": 0.82, "kerb": 0.90, "gravel": 0.88, "puddle": 0.90, "wheelspin": 1.22, "scrub": 1.25, "bump": 0.82, "collision": 0.90, "weight": 1.30, "asphalt_grip": 1.35, "slide": 1.15, "engine": 0.75, "palette": 0.92, "scrape": 0.85, "weather": 1.05, "brake": 1.12, "snow": 1.05, "ice": 1.18, "slush": 1.05, "sand": 0.95, "water": 1.00, "transition": 1.05},
    "cinematic": {"road": 0.72, "kerb": 0.92, "gravel": 0.92, "puddle": 1.30, "wheelspin": 0.75, "scrub": 0.75, "bump": 1.25, "collision": 1.42, "weight": 1.05, "asphalt_grip": 0.85, "slide": 1.05, "engine": 1.10, "palette": 0.95, "scrape": 1.30, "weather": 1.18, "brake": 1.10, "snow": 1.16, "ice": 1.16, "slush": 1.18, "sand": 1.12, "water": 1.22, "transition": 1.22},
    "clean": {"road": 0.00, "kerb": 0.85, "gravel": 0.45, "puddle": 0.55, "wheelspin": 0.00, "scrub": 0.00, "bump": 0.60, "collision": 0.90, "weight": 0.00, "asphalt_grip": 0.00, "slide": 0.00, "engine": 0.00, "palette": 0.20, "scrape": 0.20, "weather": 0.30, "brake": 0.25, "snow": 0.35, "ice": 0.35, "slush": 0.30, "sand": 0.25, "water": 0.30, "transition": 0.45},
}



class HapticAudioEngine:
    def __init__(self, settings):
        self.settings = settings
        self._stream = None
        self._device = None
        self._state = HapticState()
        self._lock = threading.Lock()
        self._running = False
        self._warned = False
        self._stream_error_count = 0  # consecutive callback errors → trigger self-stop
        self._fatigue = 0.0
        self._last_peak = 0.0
        self._last_limiter_gain = 1.0
        self._limiter_smooth = 1.0  # smoothed limiter gain to avoid pumping
        self._fade = 0.0  # 0→1 ramp on start, 1→0 on stop (prevents pop/click)
        self._fade_target = 0.0
        self._render_stats = {
            "render_l_rms": 0.0, "render_r_rms": 0.0, "render_lr_delta": 0.0,
            "render_l_peak": 0.0, "render_r_peak": 0.0, "render_limiter_gain": 1.0,
        }
        self._last_mixer_diag = {}
        self._transients = make_forza_transient_bank()
        self._mastering = HapticMasteringChain()
        self._osc = {
            "road_l": Osc(), "road_r": Osc(),
            "gravel_l": Osc(), "gravel_r": Osc(),
            "kerb_fl": Osc(), "kerb_fr": Osc(), "kerb_rl": Osc(), "kerb_rr": Osc(),
            "puddle_fl": Osc(), "puddle_fr": Osc(), "puddle_rl": Osc(), "puddle_rr": Osc(),
            "wheel_l": Osc(), "wheel_r": Osc(),
            "scrub_l": Osc(), "scrub_r": Osc(),
            "bump_fl": Osc(), "bump_fr": Osc(), "bump_rl": Osc(), "bump_rr": Osc(),
            "collision": Osc(), "collision_hi": Osc(),
            "weight_l": Osc(), "weight_r": Osc(), "weight_pulse_l": Osc(), "weight_pulse_r": Osc(),
            "asphalt_grip_l": Osc(), "asphalt_grip_r": Osc(),
            "slide_l": Osc(), "slide_r": Osc(), "slide_pulse_l": Osc(), "slide_pulse_r": Osc(),
            "slide_chaos_l": Osc(), "slide_chaos_r": Osc(),
            "rear_breakaway_l": Osc(), "rear_breakaway_r": Osc(),
            "side_scrub_edge_l": Osc(), "side_scrub_edge_r": Osc(),
            "tire_scrub_l": Osc(), "tire_scrub_r": Osc(),
            "tire_smear_l": Osc(), "tire_smear_r": Osc(),
            "slip_sizzle_l": Osc(), "slip_sizzle_r": Osc(),
            "asphalt_drift_l": Osc(), "asphalt_drift_r": Osc(),
            "offroad_drift_l": Osc(), "offroad_drift_r": Osc(),
            "idle_engine": Osc(), "idle_pulse": Osc(),
            "launch_load": Osc(), "launch_rough": Osc(), "launch_release": Osc(),
            "rough_asphalt_l": Osc(), "rough_asphalt_r": Osc(),
            "dirt_l": Osc(), "dirt_r": Osc(), "grass_l": Osc(), "grass_r": Osc(),
            "wet_asphalt_l": Osc(), "wet_asphalt_r": Osc(),
            "mud_l": Osc(), "mud_r": Osc(), "spray_l": Osc(), "spray_r": Osc(),
            "ice_l": Osc(), "ice_r": Osc(),
            "packed_snow_l": Osc(), "packed_snow_r": Osc(),
            "loose_snow_l": Osc(), "loose_snow_r": Osc(),
            "slush_l": Osc(), "slush_r": Osc(),
            "sand_l": Osc(), "sand_r": Osc(),
            "thin_water_l": Osc(), "thin_water_r": Osc(),
            "deep_water_l": Osc(), "deep_water_r": Osc(),
            "wet_tire_tail_l": Osc(), "wet_tire_tail_r": Osc(),
            "surface_transition_l": Osc(), "surface_transition_r": Osc(),
            "understeer_l": Osc(), "understeer_r": Osc(),
            "oversteer_l": Osc(), "oversteer_r": Osc(),
            "four_wheel_slide": Osc(),
            "landing": Osc(), "bottom_out": Osc(),
            "rear_echo_l": Osc(), "rear_echo_r": Osc(),
            "scrape_l": Osc(), "scrape_r": Osc(), "crack": Osc(),
            "boost_build": Osc(), "torque_surge": Osc(), "shift_kick": Osc(),
            "shift_click": Osc(), "shift_clunk": Osc(), "shift_rattle": Osc(),
            "shift_tail": Osc(), "shift_cut": Osc(),
            "brake_body_l": Osc(), "brake_body_r": Osc(), "abs_body_l": Osc(), "abs_body_r": Osc(),
            "engine_bass": Osc(), "high_speed_bass": Osc(),
            "bump_sub_l": Osc(), "bump_sub_r": Osc(),
            "grip_edge_l": Osc(), "grip_edge_r": Osc(),
            "wheelspin_edge_l": Osc(), "wheelspin_edge_r": Osc(),
            "brake_edge_l": Osc(), "brake_edge_r": Osc(),
            "rear_breakaway_low_l": Osc(), "rear_breakaway_low_r": Osc(),
            "shift_bass": Osc(), "shift_high_click": Osc(),
            "impact_sub": Osc(), "impact_crack_high": Osc(),
            "low_mid_glue_l": Osc(), "low_mid_glue_r": Osc(),
            "high_mid_glue_l": Osc(), "high_mid_glue_r": Osc(),
            "punch_low_l": Osc(), "punch_low_r": Osc(),
            "punch_high_l": Osc(), "punch_high_r": Osc(),
        }
        self._delay_buffers: dict[str, np.ndarray] = {}
        self._delay_positions: dict[str, int] = {}
        # perf: pre-allocated bus arrays to avoid np.zeros() per callback.
        # Sized lazily on first render when actual blocksize is known.
        self._bus_size = 0
        self._bus_left = None
        self._bus_right = None
        self._bus_cont_l = None
        self._bus_cont_r = None
        self._bus_veh_l = None
        self._bus_veh_r = None
        self._bus_evt_l = None
        self._bus_evt_r = None
        # 6.3.1: audio-buffer shifter sequencer. Telemetry gear changes are coarse;
        # this preserves click -> torque-cut gap -> clunk -> tail timing.
        self._shift_seq_pos = 999.0
        self._shift_seq_prev_active = False

    @property
    def running(self) -> bool:
        if self._running and self._stream is not None:
            # Check if sounddevice stream is actually alive
            try:
                if not self._stream.active:
                    log.warning("HAPTIC audio: stream inactive (device disconnected?). Marking stopped.")
                    self._running = False
                    self._stream = None
                    self._device = None
                    register_engine(None)
                    return False
            except (RuntimeError, OSError, AttributeError):
                self._running = False
                self._stream = None
                self._device = None
                register_engine(None)
                return False
        return self._running

    def start(self) -> bool:
        if self._running:
            return True
        try:
            import sounddevice as sd
            if np is None:
                raise RuntimeError("numpy is required by sounddevice output")
            dev = find_device(getattr(self.settings, "haptic_device_name", ""), min_channels=4)
            if dev is None:
                if not self._warned:
                    log.warning("HAPTIC audio: no 4-channel output device found. Check USB DualSense audio device.")
                return False
            sr = int(getattr(self.settings, "haptic_sample_rate", 48000) or 48000)
            blocksize = max(64, int(sr * float(getattr(self.settings, "haptic_buffer_ms", 10)) / 1000.0))
            self._device = dev
            self._stream = sd.OutputStream(
                device=dev.index,
                samplerate=sr,
                channels=4,
                dtype="float32",
                blocksize=blocksize,
                callback=self._callback,
                latency="low",
            )
            self._stream.start()
            self._running = True
            self._warned = False  # Reset so new errors are reported
            self._stream_error_count = 0
            self._fade_target = 1.0
            register_engine(self)
            log.info("HAPTIC audio started: %s | L=ch%d R=ch%d sr=%d block=%d", dev.label,
                     int(getattr(self.settings, "haptic_left_channel", 3)),
                     int(getattr(self.settings, "haptic_right_channel", 4)), sr, blocksize)
            return True
        except (ImportError, RuntimeError, OSError) as exc:
            if not self._warned:
                self._warned = True
                log.warning("HAPTIC audio start failed: %s", exc)
            return False

    def stop(self) -> None:
        if self._stream is not None:
            # fade out before closing to prevent click/pop
            self._fade_target = 0.0
            import time as _time
            _time.sleep(0.08)  # ~80ms for fade to reach near-zero
            try:
                self._stream.stop()
                self._stream.close()
            except (RuntimeError, OSError):
                pass
        self._stream = None
        self._running = False
        register_engine(None)
        if self._device is not None:
            log.info("HAPTIC audio stopped")
        self._device = None

    def update(self, state: HapticState) -> None:
        if not self._running:
            return
        with self._lock:
            self._state = state

    def _snapshot(self) -> HapticState:
        with self._lock:
            return self._state

    def render_stats(self) -> dict:
        with self._lock:
            return dict(self._render_stats)

    def _ch_indices(self):
        # Settings are 1-based for user-facing ch1/ch2/ch3/ch4 labels.
        l = max(0, min(3, int(getattr(self.settings, "haptic_left_channel", 3)) - 1))
        r = max(0, min(3, int(getattr(self.settings, "haptic_right_channel", 4)) - 1))
        return l, r

    def _callback(self, outdata, frames, time_info, status):  # noqa: ARG002
        if status:
            self._stream_error_count += 1
            if self._stream_error_count <= 3:
                log.warning("HAPTIC audio status: %s (count=%d)", status, self._stream_error_count)
            if self._stream_error_count >= 10:
                # Device likely gone → mark for auto-restart by loop
                log.error("HAPTIC audio: too many stream errors, marking stopped for auto-recovery.")
                self._running = False
                outdata.fill(0.0)
                return
        else:
            self._stream_error_count = 0
        outdata.fill(0.0)
        st = self._snapshot()
        _settings = self.settings
        
        # Cache frequently accessed settings to avoid repeated getattr calls
        # (59+ getattr calls per callback → 10 cached lookups)
        _cached_sr = int(getattr(_settings, "haptic_sample_rate", 48000) or 48000)
        _cached_master = _gain(getattr(_settings, "haptic_master_gain", 0.40), 0.0, 1.0)
        _cached_signal_boost = _gain(getattr(_settings, "haptic_signal_boost", 1.55), 0.50, 3.00)
        _cached_fatigue_ctl = _gain(getattr(_settings, "haptic_fatigue_control", 0.35), 0.0, 1.0)
        _cached_max_cont = _gain(getattr(_settings, "haptic_max_continuous_output", 0.70), 0.20, 1.0)
        _cached_limiter_strength = _gain(getattr(_settings, "haptic_limiter_strength", 0.65), 0.0, 1.0)
        _cached_transient_relief = _gain(getattr(_settings, "haptic_transient_limiter_relief", 0.45), 0.0, 1.0)
        
        sr = _cached_sr
        master = _cached_master
        if master <= 0.0:
            return
        left, right = self._render(st, frames, sr)
        signal_boost = _cached_signal_boost
        if signal_boost != 1.0:
            left *= signal_boost
            right *= signal_boost
        # Internal base amplitude lift. All user-facing gains stay at 1.0 = neutral
        # while the engine outputs at a higher baseline. Users lower gains to reduce,
        # rather than having to boost everything above 1.0 to feel anything.
        left *= _ENGINE_BASE_AMP
        right *= _ENGINE_BASE_AMP

        # Final safety stage: keep the haptics sharp but avoid stacked-layer clipping
        # and long-session fatigue. This happens in the audio callback, so keep it
        # lightweight and allocation-free except for simple numpy reductions.
        try:
            l_peak = float(np.max(np.abs(left)))
            r_peak = float(np.max(np.abs(right)))
            l_rms = float(np.sqrt(np.mean(left * left)))
            r_rms = float(np.sqrt(np.mean(right * right)))
            peak = max(l_peak, r_peak)
            rms = max(l_rms, r_rms)
        except (ValueError, TypeError, FloatingPointError):
            l_peak = r_peak = l_rms = r_rms = peak = rms = 0.0

        fatigue_ctl = _cached_fatigue_ctl
        max_cont = _cached_max_cont
        if fatigue_ctl > 0.0:
            # Slow attack / faster recovery. 100 callbacks/s at the default 10ms buffer.
            overload = max(0.0, rms - max_cont * 0.55)
            self._fatigue = max(0.0, min(1.0, self._fatigue * 0.992 + overload * 0.030))
            fatigue_gain = 1.0 - fatigue_ctl * 0.45 * self._fatigue
        else:
            self._fatigue = 0.0
            fatigue_gain = 1.0

        limiter_strength = _cached_limiter_strength
        transient_relief = _cached_transient_relief
        priority = haptic_priority_from_state(st, _settings)
        # raised threshold by 25% for bass headroom. Log showed 26.6% limiter
        # engagement which squashes low-freq punch before it reaches the actuator.
        # Shift transients get massive relief so the "--" impulse punches through.
        shift_priority_boost = 1.0
        if getattr(st, "shift_click", 0.0) > 0.0 or getattr(st, "shift_kick", 0.0) > 0.0:
            shift_priority_boost = 3.0  # triple the headroom during shift
        threshold = max(0.35, max_cont * 1.25) * (1.0 + transient_relief * 0.65 * priority) * shift_priority_boost
        limiter_strength *= (1.0 - transient_relief * 0.48 * priority)
        if shift_priority_boost > 1.0:
            limiter_strength *= 0.15  # nearly disable limiter during shift
        hard_gain = 1.0 if peak <= threshold else threshold / max(peak, 1e-6)
        # smooth the limiter gain to avoid audible pumping. Fast attack
        # (1.5ms) catches transients; slower release (38ms) for natural recovery.
        target_limiter = 1.0 - limiter_strength * (1.0 - hard_gain)
        dt_ms = 1000.0 * max(1, int(frames)) / max(1, int(sr))
        if target_limiter < self._limiter_smooth:
            alpha = 1.0 - _exp(-dt_ms / 1.5)   # attack 1.5ms
        else:
            alpha = 1.0 - _exp(-dt_ms / 38.0)  # release 38ms
        self._limiter_smooth += (target_limiter - self._limiter_smooth) * alpha
        limiter_gain = self._limiter_smooth
        # smooth fade envelope (prevents click/pop on start/stop)
        if self._fade != self._fade_target:
            fade_alpha = 1.0 - _exp(-dt_ms / 25.0)  # ~25ms fade tau
            self._fade += (self._fade_target - self._fade) * fade_alpha
            if self._fade < 0.001:
                self._fade = 0.0
        # During shift: bypass fatigue and limiter entirely.
        # The shift impulse amplitude is already budget-controlled (peak < 0.80)
        # so it doesn't need limiting. Any residual limiter/fatigue state from
        # previous frames would crush the impulse.
        if getattr(st, "shift_click", 0.0) > 0.0 or getattr(st, "shift_kick", 0.0) > 0.0:
            fatigue_gain = 1.0
            limiter_gain = 1.0
            self._limiter_smooth = 1.0  # reset so next frame doesn't pump
            self._fatigue = max(0.0, self._fatigue - 0.10)  # bleed off fatigue

        final_gain = master * fatigue_gain * limiter_gain * self._fade
        self._last_peak = peak * master
        self._last_limiter_gain = limiter_gain
        with self._lock:
            self._render_stats["render_l_rms"] = l_rms * final_gain
            self._render_stats["render_r_rms"] = r_rms * final_gain
            self._render_stats["render_lr_delta"] = abs(l_rms - r_rms) * final_gain
            self._render_stats["render_l_peak"] = l_peak * final_gain
            self._render_stats["render_r_peak"] = r_peak * final_gain
            self._render_stats["render_limiter_gain"] = limiter_gain
            for src in (getattr(self, "_last_mixer_diag", None),
                        getattr(self, "_shift_diag", None)):
                if src:
                    self._render_stats.update(src)

        li, ri = self._ch_indices()
        # use np.clip instead of soft_clip (tanh). Mastering already applies
        # tanh saturation on events; limiter+fatigue control peaks. Double-tanh
        # was shaving attack transients by ~15%.
        outdata[:, li] = np.clip(left * final_gain, -1.0, 1.0)
        outdata[:, ri] = np.clip(right * final_gain, -1.0, 1.0)

    def _render(self, st: HapticState, frames: int, sr: int):
        now = _time.monotonic()
        # perf: reuse pre-allocated arrays instead of np.zeros() each callback
        if self._bus_size != frames:
            self._bus_size = frames
            self._bus_left = np.zeros(frames, dtype=np.float32)
            self._bus_right = np.zeros(frames, dtype=np.float32)
            self._bus_cont_l = np.zeros(frames, dtype=np.float32)
            self._bus_cont_r = np.zeros(frames, dtype=np.float32)
            self._bus_veh_l = np.zeros(frames, dtype=np.float32)
            self._bus_veh_r = np.zeros(frames, dtype=np.float32)
            self._bus_evt_l = np.zeros(frames, dtype=np.float32)
            self._bus_evt_r = np.zeros(frames, dtype=np.float32)
            # 4th bus: engine/drivetrain (RPM, idle, boost, torque) - separate from vehicle
            self._bus_eng_l = np.zeros(frames, dtype=np.float32)
            self._bus_eng_r = np.zeros(frames, dtype=np.float32)
        left = self._bus_left; left.fill(0.0)  # noqa: F841 → used only at bus-sum stage
        right = self._bus_right; right.fill(0.0)  # noqa: F841
        continuous_l = self._bus_cont_l; continuous_l.fill(0.0)
        continuous_r = self._bus_cont_r; continuous_r.fill(0.0)
        vehicle_l = self._bus_veh_l; vehicle_l.fill(0.0)
        vehicle_r = self._bus_veh_r; vehicle_r.fill(0.0)
        event_l = self._bus_evt_l; event_l.fill(0.0)
        event_r = self._bus_evt_r; event_r.fill(0.0)
        engine_l = self._bus_eng_l; engine_l.fill(0.0)
        engine_r = self._bus_eng_r; engine_r.fill(0.0)
        # perf: local alias for settings → avoids 80+ self.settings attr lookups
        # per render. Python local access is ~2x faster than attribute chains.
        _settings = self.settings
        _ga = getattr  # local alias for getattr
        speed = max(0.0, float(st.speed_kmh))
        surface_enabled = bool(_ga(_settings, "haptic_surface_texture_enabled", True))
        special_events_enabled = bool(_ga(_settings, "haptic_special_events_enabled", True))
        idle_enabled = bool(_ga(_settings, "haptic_idle_haptics_enabled", True))
        vehicle_flavor_enabled = bool(_ga(_settings, "haptic_vehicle_flavor_enabled", True))
        spatial_haptics_enabled = bool(_ga(_settings, "haptic_spatial_haptics_enabled", True))

        # Gate idle_engine at source: when idle haptics are disabled, zero the
        # amplitude so downstream consumers (engine bass, musical mixer glue)
        # cannot leak idle vibration.  Strength scaling is applied once in the
        # dedicated add_lr call and in the engine-bass leak path below.
        _idle_strength = _gain(_ga(_settings, "haptic_idle_strength", 0.38), 0.0, 3.0)
        if not idle_enabled or _idle_strength <= 0.0:
            st.idle_engine = 0.0

        side_focus = max(
            abs(float(st.weight_l) - float(st.weight_r)),
            abs(float(st.asphalt_grip_l) - float(st.asphalt_grip_r)),
            abs(float(st.slide_l) - float(st.slide_r)),
            abs(float(st.slide_chaos_l) - float(st.slide_chaos_r)),
            abs(float(st.rear_breakaway_l) - float(st.rear_breakaway_r)),
            abs(float(st.side_scrub_edge_l) - float(st.side_scrub_edge_r)),
            abs(float(st.tire_scrub_l) - float(st.tire_scrub_r)),
            abs(float(st.tire_smear_l) - float(st.tire_smear_r)),
            abs(float(st.slip_sizzle_l) - float(st.slip_sizzle_r)),
            abs(float(st.asphalt_drift_l) - float(st.asphalt_drift_r)),
            abs(float(st.offroad_drift_l) - float(st.offroad_drift_r)),
            abs(float(st.understeer_l) - float(st.understeer_r)),
            abs(float(st.oversteer_l) - float(st.oversteer_r)),
            abs(float(st.brake_body_l) - float(st.brake_body_r)),
            abs(float(st.event_bus_l) - float(st.event_bus_r)) * 0.55,
            min(1.0, abs(float(st.lateral_g_used)) * 0.42),
        )
        side_focus = max(0.0, min(1.0, side_focus))
        center_duck_strength = _gain(_ga(_settings, "haptic_center_duck_strength", 0.46), 0.0, 0.80)
        center_vehicle_duck = 1.0 - (center_duck_strength * side_focus if spatial_haptics_enabled else 0.0)

        def gain_attr(name: str, default: float = 0.25) -> float:
            # 2.0: most tactile controls expose 0..2/3 ranges. Older code clipped
            # per-effect gains to 1.0, so strong presets looked different in the UI
            # but did not really hit harder. Use a mild musical gain curve above 1.0
            # so 1.5/2.0 are clearly audible without making 1.0 change behavior.
            raw = _gain(_ga(_settings, name, default), 0.0, 3.0)
            if raw <= 1.0:
                return raw
            return min(4.0, raw ** 1.28)

        mode = str(_ga(_settings, "haptic_priority_mode", "balanced")).lower()
        mode_mul = HAPTIC_PRIORITY_MODES.get(mode, HAPTIC_PRIORITY_MODES["balanced"])
        spatial_width = _gain(_ga(_settings, "haptic_spatial_width", 1.35), 0.0, 1.8) if spatial_haptics_enabled else 0.65
        fr_contrast = _gain(_ga(_settings, "haptic_front_rear_contrast", 0.65), 0.0, 1.5)
        f_low = _gain(_ga(_settings, "haptic_freq_low_hz", 56.0), 20.0, 180.0)
        f_high = _gain(_ga(_settings, "haptic_freq_high_hz", 420.0), 120.0, 520.0)
        if f_high <= f_low + 20.0:
            f_high = f_low + 20.0
        sharpness = _gain(_ga(_settings, "haptic_sharpness", 1.15), 0.50, 2.00)

        def hz(frac: float) -> float:
            # frac 0..1 mapped to user-tunable haptic frequency range. Higher
            # sharpness pushes textures toward the high end without changing UI gain.
            f = max(0.0, min(1.0, float(frac)))
            if sharpness != 1.0:
                f = min(1.0, max(0.0, f ** (1.0 / sharpness)))
            return f_low + (f_high - f_low) * f

        def hz_named(name: str, default_hz: float, fallback_frac: float) -> float:
            return pick_freq(_settings, name, default_hz, hz, fallback_frac)

        def layer_mul(layer: str) -> float:
            return float(mode_mul.get(layer, 1.0))

        # 1.1 spectrum split: previous builds exposed bass/high sliders, but most
        # normal layers still occupied the middle band. Apply the mid balance to
        # surface/body texture layers only, and leave dedicated low/high/one-shot
        # layers untouched so the pad no longer feels like "only mids".
        bass_gain_names = {
            "haptic_engine_bass_strength", "haptic_high_speed_bass_strength",
            "haptic_bump_sub_strength", "haptic_impact_sub_strength",
            "haptic_shift_bass_strength", "haptic_rear_breakaway_low_strength",
            "haptic_shift_body_kick_strength", "haptic_landing_strength", "haptic_bottom_out_strength",
        }
        high_gain_names = {
            "haptic_grip_edge_high_strength", "haptic_wheelspin_edge_high_strength",
            "haptic_brake_edge_high_strength", "haptic_shift_high_click_strength",
            "haptic_impact_crack_high_strength", "haptic_collision_crack_strength",
            "haptic_side_scrub_edge_strength", "haptic_slip_sizzle_strength",
        }
        event_exempt_layers = {"shift", "collision", "bump", "rear_echo", "landing"}
        mid_balance_layers = {
            "road", "gravel", "ice", "snow", "slush", "sand", "water", "transition",
            "weight", "asphalt_grip", "slide", "drift", "engine", "wheelspin",
            "scrub", "brake", "understeer", "oversteer", "scrape",
        }

        def band_balance(layer: str | None, gain_name: str) -> float:
            if gain_name in bass_gain_names or gain_name in high_gain_names:
                return 1.0
            if layer in event_exempt_layers:
                return 1.0
            if layer in mid_balance_layers:
                return _gain(_ga(_settings, "haptic_mid_texture_balance", 1.0), 0.0, 1.5)
            return 1.0

        def wide_gain_setting(name: str, default: float = 1.0, hi: float = 3.0, power: float = 1.28) -> float:
            raw = _gain(_ga(_settings, name, default), 0.0, hi)
            if raw <= 1.0:
                return raw
            return min(hi ** power, raw ** power)

        def spatial_pair(side: str, amp: float) -> tuple[float, float]:
            a = max(0.0, float(amp))
            if a <= 0.0:
                return 0.0, 0.0
            # width 0 = mostly centered, width 1 = separated, width >1 = wider/harder.
            # Keep immediate crossfeed tiny; delayed crossfeed is added at the final
            # event bus stage so side hits read as space, not mono buzz.
            cross = max(0.0, 1.0 - spatial_width) * 0.38
            if spatial_width >= 1.0:
                cross = 0.006
            own = 1.0 + max(0.0, spatial_width - 1.0) * 0.72
            if side == "left":
                return a * own, a * cross
            return a * cross, a * own

        def bus_arrays(layer: str | None, gain_name: str):
            # 4-bus routing: surface (continuous) / vehicle / engine / event
            # Engine bus: RPM, idle, boost, torque - SEPARATE from vehicle body motion
            event_names = {"kerb", "puddle", "bump", "collision", "scrape", "rear_echo", "transition", "water", "shift", "engine_start", "decel_onset", "shift_engagement"}
            engine_names = {"idle", "rpm", "boost", "torque", "launch", "turbo", "engine_braking", "corner_exit", "redline", "rpm_harmonics", "accel_onset"}  # engine/drivetrain bus
            vehicle_names = {"weight", "asphalt_grip", "slide", "drift", "wheelspin", "scrub", "brake", "understeer", "oversteer", "landing"}
            
            # Engine bus routing (RPM, idle, boost, torque)
            if layer in engine_names or gain_name in {
                "haptic_idle_strength", "haptic_idle_roughness",
                "haptic_rpm_texture_gain", "haptic_engine_bass_strength",
                "haptic_launch_strength", "haptic_launch_roughness", "haptic_launch_release_thump",
                "haptic_boost_strength", "haptic_torque_surge_strength",
                "haptic_high_speed_bass_strength",
            }:
                return engine_l, engine_r
            
            # Event bus routing (impacts, shifts)
            if layer in event_names or gain_name in {
                "haptic_kerb_gain", "haptic_puddle_gain", "haptic_bump_gain", "haptic_collision_gain",
                "haptic_impact_master_gain",
                "haptic_scrape_strength", "haptic_collision_crack_strength", "haptic_rear_echo_strength",
                "haptic_surface_transition_strength", "haptic_deep_water_strength",
                "haptic_shift_body_kick_strength", "haptic_shift_click_strength", "haptic_shift_clunk_strength",
                "haptic_shift_rattle_strength", "haptic_shift_tail_strength", "haptic_shift_reverb_strength", "haptic_shift_torque_cut_strength",
                "haptic_shift_bass_strength", "haptic_shift_high_click_strength",
                "haptic_bump_sub_strength", "haptic_impact_sub_strength", "haptic_impact_crack_high_strength",
            }:
                return event_l, event_r
            
            # Vehicle bus routing (body motion, tire feedback)
            if layer in vehicle_names or gain_name in {
                "haptic_wheelspin_gain", "haptic_scrub_gain", "haptic_lateral_g_strength",
                "haptic_asphalt_grip_strength", "haptic_slide_body_strength", "haptic_drift_snap_strength",
                "haptic_tire_scrub_texture_strength", "haptic_tire_smear_strength", "haptic_slip_sizzle_strength",
                "haptic_asphalt_drift_strength", "haptic_offroad_drift_strength",
                "haptic_grip_edge_high_strength", "haptic_wheelspin_edge_high_strength", "haptic_rear_breakaway_low_strength",
                "haptic_brake_body_strength", "haptic_abs_body_strength", "haptic_brake_edge_high_strength",
                "haptic_understeer_strength", "haptic_oversteer_strength", "haptic_landing_strength", "haptic_bottom_out_strength",
            }:
                return vehicle_l, vehicle_r
            
            # Default: surface (continuous) bus
            return continuous_l, continuous_r

        def add_spatial(sig, amp, side: str, gain_name: str, layer: str, default: float = 0.25):
            g = gain_attr(gain_name, default) * layer_mul(layer) * band_balance(layer, gain_name)
            if g <= 0 or amp <= 0:
                return
            l_bus, r_bus = bus_arrays(layer, gain_name)
            if layer in {"kerb", "puddle", "bump", "scrape", "collision", "rear_echo", "transition", "water", "shift"}:
                # keep background quiet but make one-shot contact points pop.
                # The value is still controlled by the existing transient knob/profile.
                g *= 0.92 + 0.26 * _gain(_ga(_settings, "haptic_event_transient_strength", 1.0), 0.0, 1.5)
            l_amp, r_amp = spatial_pair(side, amp)
            if l_amp > 0:
                l_bus += sig * l_amp * g
            if r_amp > 0:
                r_bus += sig * r_amp * g

        def add_lr(l_sig, r_sig, l_amp, r_amp, gain_name: str, default: float = 0.25, layer: str | None = None):
            g = gain_attr(gain_name, default) * (layer_mul(layer) if layer else 1.0) * band_balance(layer, gain_name)
            if g <= 0:
                return
            l_bus, r_bus = bus_arrays(layer, gain_name)
            if layer in {"kerb", "puddle", "bump", "scrape", "collision", "rear_echo", "transition", "water", "shift"}:
                g *= 0.92 + 0.26 * _gain(_ga(_settings, "haptic_event_transient_strength", 1.0), 0.0, 1.5)
            elif layer in {"weight", "asphalt_grip", "slide", "brake", "understeer", "oversteer"}:
                # L/R vehicle cues need to read clearly through center body layers.
                g *= 1.18
            elif layer == "drift":
                # 6.2: drift/major slip should feel loud and unstable, not like polite road texture.
                g *= 1.42
            elif layer in {"engine", "landing"}:
                # Keep center-body flavour, but let lateral/grip cues come forward.
                g *= 1.06
            if l_amp > 0:
                l_bus += l_sig * float(l_amp) * g
            if r_amp > 0:
                r_bus += r_sig * float(r_amp) * g

        def add_left(sig, amp, gain_name: str, default: float = 0.25, layer: str | None = None):
            g = gain_attr(gain_name, default) * (layer_mul(layer) if layer else 1.0) * band_balance(layer, gain_name)
            if g > 0 and amp > 0:
                l_bus, _ = bus_arrays(layer, gain_name)
                l_bus += sig * float(amp) * g

        def add_right(sig, amp, gain_name: str, default: float = 0.25, layer: str | None = None):
            g = gain_attr(gain_name, default) * (layer_mul(layer) if layer else 1.0) * band_balance(layer, gain_name)
            if g > 0 and amp > 0:
                _, r_bus = bus_arrays(layer, gain_name)
                r_bus += sig * float(amp) * g

        # Background asphalt: redesigned to IMPACT-reactive instead of continuous buzz.
        # Normal on-road = near-silent. Bumps/joints/seams trigger brief impulses.
        # susp_velocity spikes on road discontinuities → short burst; continuous sine removed.
        if surface_enabled and bool(_ga(_settings, "haptic_road_enabled", False)):
            susp_v_l = max(0.0, min(1.0, getattr(st, "susp_velocity_l", 0.0)))
            susp_v_r = max(0.0, min(1.0, getattr(st, "susp_velocity_r", 0.0)))
            # Gate: only emit signal when suspension is actively moving (road seam / joint)
            # threshold 0.08 filters out gentle cruising, passes bumps/cracks
            road_impact_threshold = 0.08
            impact_l = max(0.0, susp_v_l - road_impact_threshold) / (1.0 - road_impact_threshold)
            impact_r = max(0.0, susp_v_r - road_impact_threshold) / (1.0 - road_impact_threshold)
            if max(impact_l, impact_r) > 0.0:
                # Short burst waveform: low-mid frequency thump
                burst_freq = 85.0 + min(45.0, speed * 0.15)
                road_l_sig = self._osc["road_l"].sine(frames, sr, burst_freq) * 0.70 + noise(frames, 0.25)
                road_r_sig = self._osc["road_r"].sine(frames, sr, burst_freq * 1.02) * 0.70 + noise(frames, 0.25)
                # Amplitude from suspension velocity (sharp attack, no sustain)
                add_lr(road_l_sig, road_r_sig,
                       impact_l * st.road_l * layer_mul("road"),
                       impact_r * st.road_r * layer_mul("road"),
                       "haptic_road_gain", 0.24)

        # Texture palette: separate smooth/rough asphalt, dirt/grass-like and rear echoes.
        # This is where the haptics stop feeling like one generic buzz.
        if surface_enabled and bool(_ga(_settings, "haptic_surface_palette_enabled", True)):
            pal = _gain(_ga(_settings, "haptic_texture_palette_strength", 1.0), 0.0, 1.5) * layer_mul("palette")
            # 1.0: friend telemetry preset trims constant mid-road buzz; keep Jaewan's
            # rich detail, but let bass/high-edge layers breathe.
            pal *= _gain(_ga(_settings, "haptic_mid_texture_balance", 1.0), 0.0, 1.5)
            rough_l = self._osc["rough_asphalt_l"].sine(frames, sr, hz_named("haptic_freq_rough_road_hz", 305.0, 0.74)) * 0.44 + noise(frames, 0.40)
            rough_r = self._osc["rough_asphalt_r"].sine(frames, sr, hz_named("haptic_freq_rough_road_hz", 305.0, 0.75) * 1.010) * 0.44 + noise(frames, 0.40)
            # 6.1: offroad should not share the same steady rhythm as tarmac.
            # Dirt/grass use lower, less regular grains; asphalt remains thin/fast.
            # Forza scale: 40~90km/h is still "low speed". Avoid slow, cart-like
            # pulse cadence there; let offroad grain density bloom only after speed rises.
            grain_gate = max(0.0, min(1.0, (speed - 55.0) / 105.0))
            dirt_gate_l = pulse_train(frames, sr, 10.0 + min(30.0, speed * 0.11), 0.18 + 0.20 * grain_gate)
            dirt_gate_r = pulse_train(frames, sr, 11.5 + min(30.0, speed * 0.10), 0.16 + 0.20 * grain_gate)
            dirt_l = self._osc["dirt_l"].sine(frames, sr, hz(0.17)) * (0.22 + 0.16 * grain_gate) + noise(frames, 0.24) * (0.42 + dirt_gate_l * 0.58 * grain_gate)
            dirt_r = self._osc["dirt_r"].sine(frames, sr, hz(0.19)) * (0.22 + 0.16 * grain_gate) + noise(frames, 0.24) * (0.42 + dirt_gate_r * 0.58 * grain_gate)
            grass_l = self._osc["grass_l"].sine(frames, sr, hz(0.11)) * (0.36 + 0.18 * grain_gate) + noise(frames, 0.12 + 0.05 * grain_gate)
            grass_r = self._osc["grass_r"].sine(frames, sr, hz(0.13)) * (0.36 + 0.18 * grain_gate) + noise(frames, 0.12 + 0.05 * grain_gate)
            add_lr(rough_l, rough_r, st.rough_asphalt_l * pal, st.rough_asphalt_r * pal, "haptic_rough_asphalt_strength", 0.55)
            add_lr(dirt_l, dirt_r, st.dirt_l * pal, st.dirt_r * pal, "haptic_dirt_strength", 0.48)
            add_lr(grass_l, grass_r, st.grass_l * pal, st.grass_r * pal, "haptic_grass_strength", 0.38)
            weather = layer_mul("weather")
            wet_l = self._osc["wet_asphalt_l"].sine(frames, sr, hz(0.86)) * 0.38 + noise(frames, 0.34)
            wet_r = self._osc["wet_asphalt_r"].sine(frames, sr, hz(0.87)) * 0.38 + noise(frames, 0.34)
            mud_l = self._osc["mud_l"].sine(frames, sr, hz(0.11)) * 0.66 + noise(frames, 0.24)
            mud_r = self._osc["mud_r"].sine(frames, sr, hz(0.12)) * 0.66 + noise(frames, 0.24)
            spray_l = self._osc["spray_l"].sine(frames, sr, hz(0.94)) * 0.30 + noise(frames, 0.32)
            spray_r = self._osc["spray_r"].sine(frames, sr, hz(0.95)) * 0.30 + noise(frames, 0.32)
            add_lr(wet_l, wet_r, st.wet_asphalt_l * pal * weather, st.wet_asphalt_r * pal * weather, "haptic_wet_asphalt_strength", 0.55)
            add_lr(mud_l, mud_r, st.mud_l * pal * weather, st.mud_r * pal * weather, "haptic_mud_strength", 0.45)
            add_lr(spray_l, spray_r, st.spray_l * pal * weather, st.spray_r * pal * weather, "haptic_spray_strength", 0.40)

            # Snow/ice/sand/water palette. Ice is intentionally thin and almost
            # empty until grip is being lost; snow is soft crunch; sand is muted drag.
            ice_l = self._osc["ice_l"].sine(frames, sr, hz(0.96)) * 0.22 + noise(frames, 0.12)
            ice_r = self._osc["ice_r"].sine(frames, sr, hz(0.97)) * 0.22 + noise(frames, 0.12)
            ps_l = self._osc["packed_snow_l"].sine(frames, sr, hz(0.28)) * 0.50 + pulse_train(frames, sr, 18.0 + min(14.0, speed * 0.05), 0.22) * noise(frames, 0.20)
            ps_r = self._osc["packed_snow_r"].sine(frames, sr, hz(0.29)) * 0.50 + pulse_train(frames, sr, 18.5 + min(14.0, speed * 0.05), 0.22) * noise(frames, 0.20)
            ls_l = self._osc["loose_snow_l"].sine(frames, sr, hz(0.18)) * 0.58 + noise(frames, 0.22)
            ls_r = self._osc["loose_snow_r"].sine(frames, sr, hz(0.19)) * 0.58 + noise(frames, 0.22)
            sl_l = self._osc["slush_l"].sine(frames, sr, hz(0.15)) * 0.52 + noise(frames, 0.28)
            sl_r = self._osc["slush_r"].sine(frames, sr, hz(0.16)) * 0.52 + noise(frames, 0.28)
            sand_drag_gate = max(0.0, min(1.0, (speed - 45.0) / 120.0))
            sand_l = self._osc["sand_l"].sine(frames, sr, hz(0.10)) * (0.42 + 0.20 * sand_drag_gate) + noise(frames, 0.10 + 0.08 * sand_drag_gate)
            sand_r = self._osc["sand_r"].sine(frames, sr, hz(0.11)) * (0.42 + 0.20 * sand_drag_gate) + noise(frames, 0.10 + 0.08 * sand_drag_gate)
            thin_l = self._osc["thin_water_l"].sine(frames, sr, hz(0.88)) * 0.24 + noise(frames, 0.18)
            thin_r = self._osc["thin_water_r"].sine(frames, sr, hz(0.89)) * 0.24 + noise(frames, 0.18)
            deep_l = self._osc["deep_water_l"].sine(frames, sr, hz(0.23)) * 0.50 + noise(frames, 0.34)
            deep_r = self._osc["deep_water_r"].sine(frames, sr, hz(0.24)) * 0.50 + noise(frames, 0.34)
            tail_l = self._osc["wet_tire_tail_l"].sine(frames, sr, hz(0.72)) * 0.25 + noise(frames, 0.14)
            tail_r = self._osc["wet_tire_tail_r"].sine(frames, sr, hz(0.73)) * 0.25 + noise(frames, 0.14)
            tr_l = self._osc["surface_transition_l"].sine(frames, sr, hz(0.64)) * pulse_train(frames, sr, 30.0, 0.30)
            tr_r = self._osc["surface_transition_r"].sine(frames, sr, hz(0.65)) * pulse_train(frames, sr, 30.0, 0.30)
            add_lr(ice_l, ice_r, st.ice_l * pal, st.ice_r * pal, "haptic_ice_strength", 0.42, layer="ice")
            add_lr(ps_l, ps_r, st.packed_snow_l * pal, st.packed_snow_r * pal, "haptic_packed_snow_strength", 0.50, layer="snow")
            add_lr(ls_l, ls_r, st.loose_snow_l * pal, st.loose_snow_r * pal, "haptic_loose_snow_strength", 0.48, layer="snow")
            add_lr(sl_l, sl_r, st.slush_l * pal, st.slush_r * pal, "haptic_slush_strength", 0.52, layer="slush")
            add_lr(sand_l, sand_r, st.sand_l * pal, st.sand_r * pal, "haptic_sand_strength", 0.46, layer="sand")
            add_lr(thin_l, thin_r, st.thin_water_l * pal, st.thin_water_r * pal, "haptic_thin_water_strength", 0.34, layer="water")
            add_lr(deep_l, deep_r, st.deep_water_l * pal, st.deep_water_r * pal, "haptic_deep_water_strength", 0.58, layer="water")
            add_lr(tail_l, tail_r, st.wet_tire_tail_l * pal, st.wet_tire_tail_r * pal, "haptic_wet_tire_tail_strength", 0.36, layer="water")
            add_lr(tr_l, tr_r, st.surface_transition_l * pal, st.surface_transition_r * pal, "haptic_surface_transition_strength", 0.42, layer="transition")
            echo_gate = pulse_train(frames, sr, 20.0 + min(28.0, speed * 0.22), 0.40)
            echo_l = self._osc["rear_echo_l"].sine(frames, sr, hz(0.16)) * echo_gate
            echo_r = self._osc["rear_echo_r"].sine(frames, sr, hz(0.17)) * echo_gate
            add_lr(echo_l, echo_r, st.rear_echo_l * pal, st.rear_echo_r * pal, "haptic_rear_echo_strength", 0.65)

        # Lateral-G weight transfer: outside grip gets a body-load buzz, with optional snap pulse.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_weight_transfer_enabled", False)):
            w_l_sig = self._osc["weight_l"].sine(frames, sr, hz(0.42)) * 0.65 + noise(frames, 0.28)
            w_r_sig = self._osc["weight_r"].sine(frames, sr, hz(0.43)) * 0.65 + noise(frames, 0.28)
            add_lr(w_l_sig, w_r_sig, st.weight_l * layer_mul("weight"), st.weight_r * layer_mul("weight"), "haptic_lateral_g_strength", 0.55)
            p_l = self._osc["weight_pulse_l"].sine(frames, sr, hz(0.78)) * pulse_train(frames, sr, 34.0, 0.36)
            p_r = self._osc["weight_pulse_r"].sine(frames, sr, hz(0.79)) * pulse_train(frames, sr, 34.0, 0.36)
            add_lr(p_l, p_r, st.weight_pulse_l * layer_mul("weight"), st.weight_pulse_r * layer_mul("weight"), "haptic_lateral_g_strength", 0.55)

        # ----- extended telemetry render layers -----
        # RPM body texture: subtle engine vibration that follows rev band.
        # LRA sweet spot ~150Hz; rpm_norm maps idle..redline to 65..180Hz.
        # Gated by speed to avoid idle buzz when parked.
        rpm_n = max(0.0, min(1.0, getattr(st, "rpm_norm", 0.0)))
        if rpm_n > 0.02 and speed > 8.0 and bool(_ga(_settings, "haptic_rpm_texture_enabled", True)):
            rpm_freq = 65.0 + rpm_n * 115.0   # 65→180 Hz: stays in LRA sweet spot
            rpm_amp = rpm_n * 0.035 * (0.05 + 0.95 * min(1.0, speed / 100.0))
            if "rpm_texture_l" not in self._osc:
                self._osc["rpm_texture_l"] = Osc()
                self._osc["rpm_texture_r"] = Osc()
                self._osc["rpm_harmonic2_l"] = Osc()
                self._osc["rpm_harmonic2_r"] = Osc()
                self._osc["rpm_harmonic3_l"] = Osc()
                self._osc["rpm_harmonic3_r"] = Osc()
            rpm_sig_l = self._osc["rpm_texture_l"].sine(frames, sr, rpm_freq)
            rpm_sig_r = self._osc["rpm_texture_r"].sine(frames, sr, rpm_freq * 1.015)
            rpm_g = _gain(_ga(_settings, "haptic_rpm_texture_gain", 0.80), 0.0, 1.5)
            # Cylinder-count-based RPM harmonics (4/6/8+ cyl differentiation).
            # 4cyl: mechanical 2nd harmonic, 6cyl: smooth 1.5x+2.5x, 8cyl+: sub-bass rumble.
            harm_str = _gain(_ga(_settings, "haptic_rpm_harmonics_strength", 0.45), 0.0, 1.5)
            if rpm_n > 0.15 and harm_str > 0.0:
                cyl = int(getattr(st, "cylinder_count", 4))
                fund_freq = 40.0 + rpm_n * 80.0  # 40-120Hz fundamental
                if "rpm_harm_sub" not in self._osc:
                    self._osc["rpm_harm_sub"] = Osc()
                fund_l = self._osc["rpm_harmonic2_l"].sine(frames, sr, fund_freq)
                fund_r = self._osc["rpm_harmonic2_r"].sine(frames, sr, fund_freq * 1.01)
                if cyl <= 4:
                    # 4-cyl: 2nd harmonic emphasis (mechanical feel)
                    h1_l = self._osc["rpm_harmonic3_l"].sine(frames, sr, min(fund_freq * 2.0, 180.0)) * 0.35
                    h1_r = self._osc["rpm_harmonic3_r"].sine(frames, sr, min(fund_freq * 2.0, 180.0) * 1.02) * 0.35
                    harm_sig_l = fund_l * 0.55 + h1_l
                    harm_sig_r = fund_r * 0.55 + h1_r
                elif cyl <= 6:
                    # 6-cyl: 1.5x + 2.5x harmonics (smooth, balanced)
                    h1_l = self._osc["rpm_harmonic3_l"].sine(frames, sr, min(fund_freq * 1.5, 180.0)) * 0.30
                    h1_r = self._osc["rpm_harmonic3_r"].sine(frames, sr, min(fund_freq * 1.5, 180.0) * 1.02) * 0.30
                    harm_sig_l = fund_l * 0.50 + h1_l
                    harm_sig_r = fund_r * 0.50 + h1_r
                else:
                    # 8-cyl+: sub-bass emphasis (deep rumble)
                    sub_l = self._osc["rpm_harm_sub"].sine(frames, sr, max(30.0, fund_freq * 0.5)) * 0.40
                    h1_l = self._osc["rpm_harmonic3_l"].sine(frames, sr, min(fund_freq * 2.0, 170.0)) * 0.20
                    h1_r = self._osc["rpm_harmonic3_r"].sine(frames, sr, min(fund_freq * 2.0, 170.0) * 1.02) * 0.20
                    harm_sig_l = fund_l * 0.40 + sub_l + h1_l
                    harm_sig_r = fund_r * 0.40 + sub_l + h1_r
                harm_amp = rpm_n * harm_str * 0.5
                rpm_sig_l += harm_sig_l * harm_amp
                rpm_sig_r += harm_sig_r * harm_amp
                # Boost base amplitude when harmonics are active (keeps overall loudness)
                rpm_amp *= (1.0 + min(1.0, rpm_n) * harm_str * 0.35)
            # RPM goes to continuous bus → independent of vehicle bus gain,
            # so chassis vibration can be killed without losing engine feel.
            # FIX: RPM goes to engine bus, not continuous(surface), to avoid being buried by road noise.
            engine_l += rpm_sig_l * rpm_amp * rpm_g
            engine_r += rpm_sig_r * rpm_amp * rpm_g

        # ── Turbo spool: high-freq whistle on boost build-up ──
        _turbo = float(getattr(st, "turbo_spool", 0.0))
        if _turbo > 0.01:
            _turbo_str = _gain(_ga(_settings, "haptic_turbo_spool_strength", 0.40), 0.0, 1.5)
            if _turbo_str > 0.0:
                if "turbo_spool" not in self._osc:
                    self._osc["turbo_spool"] = Osc()
                # AM modulation for "whiiiiing" spool feel (120-165Hz carrier)
                _ts_freq = 120.0 + _turbo * 45.0
                _ts_am_freq = 8.0 + _turbo * 12.0
                _ts_am = 0.6 + 0.4 * np.sin(2.0 * np.pi * _ts_am_freq * np.arange(frames, dtype=np.float32) / float(sr))
                _ts_sig = self._osc["turbo_spool"].sine(frames, sr, _ts_freq) * 0.65 * _ts_am + noise(frames, 0.20)
                _ts_amp = _turbo * _turbo_str * 0.45
                engine_l += _ts_sig * _ts_amp
                engine_r += _ts_sig * _ts_amp

        # ── Engine braking: drag feel on deceleration ──
        _eb = float(getattr(st, "engine_braking", 0.0))
        if _eb > 0.01:
            _eb_str = _gain(_ga(_settings, "haptic_engine_braking_strength", 0.50), 0.0, 1.5)
            if _eb_str > 0.0:
                if "engine_braking" not in self._osc:
                    self._osc["engine_braking"] = Osc()
                _eb_freq = 48.0 + _eb * 17.0  # 48-65Hz low rumble
                _eb_sig = self._osc["engine_braking"].sine(frames, sr, _eb_freq) * 0.75 + noise(frames, 0.18)
                _eb_amp = _eb * _eb_str * 0.5
                engine_l += _eb_sig * _eb_amp
                engine_r += _eb_sig * _eb_amp

        # ── Corner exit torque: power delivery feel on corner exit ──
        _cet = float(getattr(st, "corner_exit_torque", 0.0))
        if _cet > 0.01:
            _cet_str = _gain(_ga(_settings, "haptic_corner_exit_strength", 0.55), 0.0, 2.0)
            if _cet_str > 0.0:
                if "corner_exit" not in self._osc:
                    self._osc["corner_exit"] = Osc()
                _cet_sig = self._osc["corner_exit"].sine(frames, sr, 55.0) * 0.70 + noise(frames, 0.20)
                # 15ms attack envelope
                _cet_t = np.arange(frames, dtype=np.float32) / float(sr)
                _cet_env = np.minimum(1.0, _cet_t / 0.015)
                _cet_amp = _cet * _cet_str * 0.6
                engine_l += _cet_sig * _cet_amp * _cet_env
                engine_r += _cet_sig * _cet_amp * _cet_env

        # ── Redline warning: pulse vibration (adaptive threshold) ──
        _rl_max_rpm = float(getattr(st, "max_rpm", 0.0))
        _rl_idle_rpm = float(getattr(st, "idle_rpm", 0.0))
        _rl_width = float(_ga(_settings, "haptic_redline_warning_width", 0.08))
        if _rl_max_rpm > 0 and _rl_idle_rpm >= 0:
            _rl_usable = _rl_max_rpm - _rl_idle_rpm
            _rl_margin = (_rl_usable * _rl_width) / _rl_max_rpm
            _rl_threshold = max(0.70, 0.93 - _rl_margin)
        else:
            _rl_threshold = 0.90
        _rl_rev_limit = float(_ga(_settings, "rev_limit_ratio", 0.93))
        if rpm_n >= _rl_threshold:
            _rl_str = _gain(_ga(_settings, "haptic_redline_warning_strength", 0.65), 0.0, 2.0)
            if _rl_str > 0.0:
                if "redline_warn" not in self._osc:
                    self._osc["redline_warn"] = Osc()
                # Duck haptic if trigger redline_pulse is also active
                _rl_duck = 0.5 if (bool(_ga(_settings, "enable_trigger_redline_pulse", True)) and rpm_n >= _rl_rev_limit) else 1.0
                _rl_over = min(1.0, (rpm_n - _rl_threshold) / max(0.01, 1.0 - _rl_threshold))
                _rl_pulse_freq = 12.0 + _rl_over * 13.0  # 12-25Hz pulse
                _rl_pulse = pulse_train(frames, sr, _rl_pulse_freq, 0.50)
                _rl_carrier = self._osc["redline_warn"].sine(frames, sr, 100.0)
                _rl_sig = _rl_pulse * _rl_carrier
                _rl_amp = (0.5 + _rl_over * 0.5) * _rl_str * _rl_duck
                engine_l += _rl_sig * _rl_amp
                engine_r += _rl_sig * _rl_amp

        # Pitch/roll body motion: braking dive and cornering lean as low rumble.
        # These use the vehicle bus so mastering can duck them during events.
        pitch_r = max(0.0, min(1.0, getattr(st, "pitch_rate", 0.0)))
        roll_r = max(0.0, min(1.0, getattr(st, "roll_rate", 0.0)))
        if (pitch_r > 0.03 or roll_r > 0.03) and speed > 15.0 and bool(_ga(_settings, "haptic_body_motion_enabled", True)):
            if "body_pitch" not in self._osc:
                self._osc["body_pitch"] = Osc()
                self._osc["body_roll_l"] = Osc()
                self._osc["body_roll_r"] = Osc()
            body_gain = _gain(_ga(_settings, "haptic_body_motion_gain", 0.08), 0.0, 1.5)
            # Pitch: symmetric mono rumble at ~85Hz, amplitude from pitch_rate
            if pitch_r > 0.03:
                pitch_sig = self._osc["body_pitch"].sine(frames, sr, 85.0) * pitch_r * 0.005 * body_gain
                vehicle_l += pitch_sig
                vehicle_r += pitch_sig
            # Roll: lateralized → lean left means right-heavy, so right gets more.
            if roll_r > 0.03:
                lat_g_sign = 1.0 if getattr(st, "lateral_g_used", 0.0) >= 0.0 else -1.0
                roll_amp = roll_r * 0.005 * body_gain
                # Cornering right (lat_g>0) → car leans left → left actuator heavier
                vehicle_l += self._osc["body_roll_l"].sine(frames, sr, 72.0) * roll_amp * (0.45 + 0.55 * max(0.0, lat_g_sign))
                vehicle_r += self._osc["body_roll_r"].sine(frames, sr, 73.0) * roll_amp * (0.45 + 0.55 * max(0.0, -lat_g_sign))

        # Wheel speed diff: drivetrain traction pulse. AWD/RWD power split creates
        # a subtle front-rear speed gap that pulses as traction breaks/recovers.
        ws_diff = max(0.0, min(1.0, getattr(st, "wheel_speed_diff", 0.0)))
        if ws_diff > 0.08 and speed > 20.0 and bool(_ga(_settings, "haptic_traction_pulse_enabled", True)):
            if "traction_pulse" not in self._osc:
                self._osc["traction_pulse"] = Osc()
            trac_freq = 110.0 + ws_diff * 60.0  # 110→170 Hz
            trac_amp = ws_diff * 0.004 * _gain(_ga(_settings, "haptic_traction_pulse_gain", 0.40), 0.0, 1.5)
            trac_sig = self._osc["traction_pulse"].sine(frames, sr, trac_freq) * trac_amp
            vehicle_l += trac_sig
            vehicle_r += trac_sig
        # ----- end extended telemetry render layers -----

        # Asphalt grip sense: asphalt-only tire-limit texture. This fills the gap where
        # clean tarmac felt empty but avoids drowning offroad/puddle layers.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_asphalt_grip_enabled", False)):
            g_l_sig = self._osc["asphalt_grip_l"].sine(frames, sr, hz(0.68)) * 0.62 + noise(frames, 0.36)
            g_r_sig = self._osc["asphalt_grip_r"].sine(frames, sr, hz(0.69)) * 0.62 + noise(frames, 0.36)
            add_lr(g_l_sig, g_r_sig, st.asphalt_grip_l * layer_mul("asphalt_grip"), st.asphalt_grip_r * layer_mul("asphalt_grip"), "haptic_asphalt_grip_strength", 0.75)

        # Slide / drift body feel: lateral velocity + yaw body growl, not a second
        # trigger scrub. It is lower and wider so the car feels like it is rotating.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_slide_body_enabled", False)):
            s_l = self._osc["slide_l"].sine(frames, sr, hz(0.30)) * 0.60 + noise(frames, 0.30)
            s_r = self._osc["slide_r"].sine(frames, sr, hz(0.31)) * 0.60 + noise(frames, 0.30)
            add_lr(s_l, s_r, st.slide_l * layer_mul("slide"), st.slide_r * layer_mul("slide"), "haptic_slide_body_strength", 0.55)
            sp_l = self._osc["slide_pulse_l"].sine(frames, sr, hz(0.82)) * pulse_train(frames, sr, 38.0, 0.34)
            sp_r = self._osc["slide_pulse_r"].sine(frames, sr, hz(0.83)) * pulse_train(frames, sr, 38.0, 0.34)
            add_lr(sp_l, sp_r, st.slide_pulse_l * layer_mul("slide"), st.slide_pulse_r * layer_mul("slide"), "haptic_drift_snap_strength", 0.50)

        # 6.2 Slide Chaos: major drift/breakaway gets its own unstable side texture.
        # This is intentionally more aggressive than normal lateral-G so drifting
        # reads as the car losing control instead of a mild 6:4 side bias.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_vehicle_dynamics_enabled", True)):
            if max(st.slide_chaos_l, st.slide_chaos_r, st.rear_breakaway_l, st.rear_breakaway_r, st.side_scrub_edge_l, st.side_scrub_edge_r) > 0.0:
                chaos_gate_l = pulse_train(frames, sr, 28.0 + min(42.0, speed * 0.18), 0.42)
                chaos_gate_r = pulse_train(frames, sr, 31.0 + min(42.0, speed * 0.17), 0.40)
                chaos_l = self._osc["slide_chaos_l"].sine(frames, sr, hz(0.50)) * 0.42 + noise(frames, 0.58) * (0.45 + chaos_gate_l * 0.55)
                chaos_r = self._osc["slide_chaos_r"].sine(frames, sr, hz(0.52)) * 0.42 + noise(frames, 0.58) * (0.45 + chaos_gate_r * 0.55)
                rear_l = self._osc["rear_breakaway_l"].sine(frames, sr, hz(0.20)) * 0.64 + noise(frames, 0.30)
                rear_r = self._osc["rear_breakaway_r"].sine(frames, sr, hz(0.22)) * 0.64 + noise(frames, 0.30)
                edge_l = self._osc["side_scrub_edge_l"].sine(frames, sr, hz(0.88)) * 0.36 + noise(frames, 0.44)
                edge_r = self._osc["side_scrub_edge_r"].sine(frames, sr, hz(0.90)) * 0.36 + noise(frames, 0.44)
                add_lr(chaos_l, chaos_r, st.slide_chaos_l, st.slide_chaos_r, "haptic_slide_chaos_strength", 0.74, layer="drift")
                add_lr(rear_l, rear_r, st.rear_breakaway_l, st.rear_breakaway_r, "haptic_drift_breakaway_strength", 0.72, layer="drift")
                add_lr(edge_l, edge_r, st.side_scrub_edge_l, st.side_scrub_edge_r, "haptic_side_scrub_edge_strength", 0.62, layer="drift")

        # 6.3 tire slip texture: rubber scrub/smear/sizzle is distinct from body chaos.
        # Asphalt drift is thin and sharp; offroad drift is grainy and lower.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_vehicle_dynamics_enabled", True)):
            tire_active = max(st.tire_scrub_l, st.tire_scrub_r, st.tire_smear_l, st.tire_smear_r, st.slip_sizzle_l, st.slip_sizzle_r, st.asphalt_drift_l, st.asphalt_drift_r, st.offroad_drift_l, st.offroad_drift_r)
            if tire_active > 0.0:
                # tire_scrub: lateral friction -- high freq noise-heavy texture
                scrub_l = self._osc["tire_scrub_l"].sine(frames, sr, hz(0.88)) * 0.30 + noise(frames, 0.52)
                scrub_r = self._osc["tire_scrub_r"].sine(frames, sr, hz(0.90)) * 0.30 + noise(frames, 0.52)
                smear_l = self._osc["tire_smear_l"].sine(frames, sr, hz(0.46)) * 0.50 + noise(frames, 0.20)
                smear_r = self._osc["tire_smear_r"].sine(frames, sr, hz(0.48)) * 0.50 + noise(frames, 0.20)
                # slip_sizzle: tire slip "sizzle" -- high freq noise with pulse gating
                sizzle_gate_l = pulse_train(frames, sr, 44.0 + min(42.0, speed * 0.16), 0.28)
                sizzle_gate_r = pulse_train(frames, sr, 47.0 + min(42.0, speed * 0.15), 0.27)
                sizzle_l = self._osc["slip_sizzle_l"].sine(frames, sr, hz(0.98)) * 0.12 + noise(frames, 0.72) * (0.55 + sizzle_gate_l * 0.45)
                sizzle_r = self._osc["slip_sizzle_r"].sine(frames, sr, hz(0.99)) * 0.12 + noise(frames, 0.72) * (0.55 + sizzle_gate_r * 0.45)
                asphalt_l = scrub_l * 0.52 + sizzle_l * 0.48
                asphalt_r = scrub_r * 0.52 + sizzle_r * 0.48
                off_gate_l = pulse_train(frames, sr, 18.0 + min(38.0, speed * 0.14), 0.36)
                off_gate_r = pulse_train(frames, sr, 21.0 + min(38.0, speed * 0.13), 0.34)
                off_l = self._osc["offroad_drift_l"].sine(frames, sr, hz(0.24)) * 0.38 + noise(frames, 0.52) * (0.38 + off_gate_l * 0.62)
                off_r = self._osc["offroad_drift_r"].sine(frames, sr, hz(0.26)) * 0.38 + noise(frames, 0.52) * (0.38 + off_gate_r * 0.62)
                add_lr(scrub_l, scrub_r, st.tire_scrub_l, st.tire_scrub_r, "haptic_tire_scrub_texture_strength", 0.64, layer="drift")
                add_lr(smear_l, smear_r, st.tire_smear_l, st.tire_smear_r, "haptic_tire_smear_strength", 0.52, layer="drift")
                add_lr(sizzle_l, sizzle_r, st.slip_sizzle_l, st.slip_sizzle_r, "haptic_slip_sizzle_strength", 0.50, layer="drift")
                add_lr(asphalt_l, asphalt_r, st.asphalt_drift_l, st.asphalt_drift_r, "haptic_asphalt_drift_strength", 0.68, layer="drift")
                add_lr(off_l, off_r, st.offroad_drift_l, st.offroad_drift_r, "haptic_offroad_drift_strength", 0.66, layer="drift")

        # 1.0 high-end tire edge: thin grip-limit warning above the mid texture.
        if spatial_haptics_enabled:
            high_master = wide_gain_setting("haptic_high_edge_gain", 1.5, 3.0)
            if high_master > 0.0:
                edge_l_amp = max(st.asphalt_grip_l * 0.86, st.side_scrub_edge_l * 0.72, st.understeer_l * 0.66, st.oversteer_l * 0.52)
                edge_r_amp = max(st.asphalt_grip_r * 0.86, st.side_scrub_edge_r * 0.72, st.understeer_r * 0.66, st.oversteer_r * 0.52)
                if max(edge_l_amp, edge_r_amp) > 0.0:
                    edge_gate_l = pulse_train(frames, sr, 62.0 + min(42.0, speed * 0.16), 0.22)
                    edge_gate_r = pulse_train(frames, sr, 65.0 + min(42.0, speed * 0.15), 0.21)
                    edge_l = (self._osc["grip_edge_l"].sine(frames, sr, hz(0.995)) * 0.34 + noise(frames, 0.78)) * (0.30 + 0.70 * edge_gate_l)
                    edge_r = (self._osc["grip_edge_r"].sine(frames, sr, hz(0.985)) * 0.34 + noise(frames, 0.78)) * (0.30 + 0.70 * edge_gate_r)
                    drift_trim = 1.0 - min(0.35, float(getattr(st, "drift_confidence", 0.0)) * 0.35)
                    add_lr(edge_l, edge_r, edge_l_amp * high_master * drift_trim, edge_r_amp * high_master * drift_trim, "haptic_grip_edge_high_strength", 0.62, layer="drift")

        # Under/oversteer and big vertical body events. These are vehicle-body cues,
        # not trigger duplicates. They explain whether the front washes out, rear rotates,
        # or the whole car lands/bottoms out.
        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_vehicle_dynamics_enabled", True)):
            u_l = self._osc["understeer_l"].sine(frames, sr, hz(0.74)) * 0.44 + noise(frames, 0.22)
            u_r = self._osc["understeer_r"].sine(frames, sr, hz(0.75)) * 0.44 + noise(frames, 0.22)
            o_l = self._osc["oversteer_l"].sine(frames, sr, hz(0.24)) * 0.62 + noise(frames, 0.20)
            o_r = self._osc["oversteer_r"].sine(frames, sr, hz(0.25)) * 0.62 + noise(frames, 0.20)
            fs = self._osc["four_wheel_slide"].sine(frames, sr, hz(0.34)) * 0.46 + noise(frames, 0.18)
            add_lr(u_l, u_r, st.understeer_l, st.understeer_r, "haptic_understeer_strength", 0.34, layer="understeer")
            add_lr(o_l, o_r, st.oversteer_l, st.oversteer_r, "haptic_oversteer_strength", 0.40, layer="oversteer")
            add_lr(fs, fs, st.four_wheel_slide, st.four_wheel_slide, "haptic_four_wheel_slide_strength", 0.30, layer="slide")
            bass_master = wide_gain_setting("haptic_bass_foundation_gain", 1.5, 3.0)
            if bass_master > 0.0:
                rb_l = self._osc["rear_breakaway_low_l"].sine(frames, sr, hz(0.070)) * 1.34 + noise(frames, 0.055)
                rb_r = self._osc["rear_breakaway_low_r"].sine(frames, sr, hz(0.074)) * 1.34 + noise(frames, 0.055)
                add_lr(rb_l, rb_r, max(st.oversteer_l, st.rear_breakaway_l) * bass_master, max(st.oversteer_r, st.rear_breakaway_r) * bass_master, "haptic_rear_breakaway_low_strength", 0.62, layer="oversteer")
            land = self._osc["landing"].sub_punch(frames, sr, hz(0.08), 1.8, 25.0) * 1.24 + noise(frames, 0.10)
            bottom = self._osc["bottom_out"].sub_punch(frames, sr, hz(0.05), 2.0, 20.0) * 1.35 + noise(frames, 0.08)
            add_lr(land, land, st.landing, st.landing, "haptic_landing_strength", 0.58, layer="landing")
            add_lr(bottom, bottom, st.bottom_out, st.bottom_out, "haptic_bottom_out_strength", 0.66, layer="landing")

        # Idle / engine-load body texture. Kept deliberately subtle; launch load is stronger.
        if idle_enabled and vehicle_flavor_enabled and bool(_ga(_settings, "haptic_idle_engine_enabled", False)) and st.idle_engine > 0.0:
            rough = _gain(_ga(_settings, "haptic_idle_roughness", 0.45), 0.0, 1.0)
            low = self._osc["idle_engine"].sine(frames, sr, hz(0.05 + rough * 0.08))
            chug = pulse_train(frames, sr, 8.0 + rough * 10.0, 0.26) * self._osc["idle_pulse"].sine(frames, sr, hz(0.12))
            # Idle should be present as a low throb, not as stationary surface chatter.
            # Raise the low/chug body slightly and keep noise restrained.
            sig = low * (0.86 - rough * 0.14) + chug * (0.30 + rough * 0.30) + noise(frames, 0.055 * rough)
            add_lr(sig, sig, st.idle_engine * layer_mul("engine"), st.idle_engine * layer_mul("engine"), "haptic_idle_strength", 0.38)

        # Launch load: brake+throttle torque build-up, plus release thump.
        if vehicle_flavor_enabled and bool(_ga(_settings, "haptic_launch_load_enabled", False)):
            if st.launch_load > 0.0:
                rough = _gain(_ga(_settings, "haptic_launch_roughness", 0.65), 0.0, 1.0)
                load_sig = self._osc["launch_load"].sine(frames, sr, hz(0.10 + rough * 0.15)) * 0.65 + noise(frames, 0.20 + rough * 0.18)
                load_sig += pulse_train(frames, sr, 12.0 + rough * 18.0, 0.32) * self._osc["launch_rough"].sine(frames, sr, hz(0.24)) * 0.25
                add_lr(load_sig, load_sig, st.launch_load * layer_mul("engine"), st.launch_load * layer_mul("engine"), "haptic_launch_strength", 0.55)
            if st.launch_release > 0.0:
                rel = self._osc["launch_release"].sine(frames, sr, hz(0.08)) * 0.85 + noise(frames, 0.16)
                add_lr(rel, rel, st.launch_release * layer_mul("engine"), st.launch_release * layer_mul("engine"), "haptic_launch_release_thump", 0.55)

        # Gravel/dirt: stronger noisy low-mid rumble. This was intentionally boosted
        # from the early test build so master gain does not need to sit at 0.8.
        if surface_enabled and bool(_ga(_settings, "haptic_gravel_enabled", False)):
            # Gravel/offroad: irregular grains instead of a steady on-road-like buzz.
            # Low speed is deliberately sparse; with speed it becomes dense texture.
            off_density = 0.22 + 0.78 * min(1.0, speed / 95.0)
            jitter_l = pulse_train(frames, sr, 7.0 + min(38.0, speed * 0.17), 0.22 + 0.16 * off_density)
            jitter_r = pulse_train(frames, sr, 8.5 + min(38.0, speed * 0.16), 0.20 + 0.16 * off_density)
            base_l = self._osc["gravel_l"].sine(frames, sr, hz_named("haptic_freq_gravel_hz", 118.0, 0.11) + min(46.0, speed * 0.08))
            base_r = self._osc["gravel_r"].sine(frames, sr, hz_named("haptic_freq_gravel_hz", 118.0, 0.13) * 1.035 + min(46.0, speed * 0.075))
            n_l = noise(frames, 0.68) * (0.45 + jitter_l * 0.65)
            n_r = noise(frames, 0.68) * (0.45 + jitter_r * 0.65)
            add_lr(base_l * 0.34 + n_l * 0.66, base_r * 0.34 + n_r * 0.66,
                   st.gravel_l * layer_mul("gravel") * _gain(_ga(_settings, "haptic_gravel_background_strength", 0.62), 0.0, 1.0),
                   st.gravel_r * layer_mul("gravel") * _gain(_ga(_settings, "haptic_gravel_background_strength", 0.62), 0.0, 1.0), "haptic_gravel_gain", 0.50)

        # Kerb / rumble strip: wheel-specific spatial encoding.
        # Front wheels: sharper/high frequency. Rear wheels: lower/thumpier.
        if special_events_enabled and bool(_ga(_settings, "haptic_kerb_enabled", False)):
            pulse_hz = 14.0 + min(46.0, speed * 0.28)
            gate = pulse_train(frames, sr, pulse_hz, 0.50)
            front_l = self._osc["kerb_fl"].sine(frames, sr, hz_named("haptic_freq_kerb_front_hz", 348.0, 0.56) + min(72.0, speed * 0.18) + fr_contrast * 18.0) * gate
            front_r = self._osc["kerb_fr"].sine(frames, sr, hz_named("haptic_freq_kerb_front_hz", 348.0, 0.57) * 1.012 + min(72.0, speed * 0.18) + fr_contrast * 18.0) * gate
            rear_l = self._osc["kerb_rl"].sine(frames, sr, max(45.0, hz_named("haptic_freq_kerb_rear_hz", 168.0, 0.28) + min(42.0, speed * 0.10) - fr_contrast * 8.0)) * gate
            rear_r = self._osc["kerb_rr"].sine(frames, sr, max(45.0, hz_named("haptic_freq_kerb_rear_hz", 168.0, 0.29) * 1.012 + min(42.0, speed * 0.10) - fr_contrast * 8.0)) * gate
            add_spatial(front_l, st.kerb_fl, "left", "haptic_kerb_gain", "kerb", 0.62)
            add_spatial(front_r, st.kerb_fr, "right", "haptic_kerb_gain", "kerb", 0.62)
            add_spatial(rear_l, st.kerb_rl, "left", "haptic_kerb_gain", "kerb", 0.62)
            add_spatial(rear_r, st.kerb_rr, "right", "haptic_kerb_gain", "kerb", 0.62)

        # Puddle: short bright burst, spatial per wheel. Puddle gets priority over
        # continuous gravel/road so it cuts through offroad chatter.
        if special_events_enabled and bool(_ga(_settings, "haptic_puddle_enabled", False)):
            duck = _gain(_ga(_settings, "haptic_surface_ducking", 0.78), 0.0, 1.0)
            if duck > 0.0:
                l_p = max(st.puddle_fl, st.puddle_rl)
                r_p = max(st.puddle_fr, st.puddle_rr)
                continuous_l *= 1.0 - duck * 0.72 * l_p
                continuous_r *= 1.0 - duck * 0.72 * r_p
                vehicle_l *= 1.0 - duck * 0.16 * l_p
                vehicle_r *= 1.0 - duck * 0.16 * r_p
            f_l = self._osc["puddle_fl"].sine(frames, sr, hz(0.88 + 0.08 * fr_contrast)) * 0.70 + noise(frames, 0.46)
            f_r = self._osc["puddle_fr"].sine(frames, sr, hz(0.89 + 0.08 * fr_contrast)) * 0.70 + noise(frames, 0.46)
            r_l = self._osc["puddle_rl"].sine(frames, sr, hz(0.60 - 0.08 * fr_contrast)) * 0.70 + noise(frames, 0.42)
            r_r = self._osc["puddle_rr"].sine(frames, sr, hz(0.61 - 0.08 * fr_contrast)) * 0.70 + noise(frames, 0.42)
            add_spatial(f_l, st.puddle_fl, "left", "haptic_puddle_gain", "puddle", 0.50)
            add_spatial(f_r, st.puddle_fr, "right", "haptic_puddle_gain", "puddle", 0.50)
            add_spatial(r_l, st.puddle_rl, "left", "haptic_puddle_gain", "puddle", 0.50)
            add_spatial(r_r, st.puddle_rr, "right", "haptic_puddle_gain", "puddle", 0.50)

        # Wheelspin and scrub are only body-haptic spices. Triggers remain the main source.
        if vehicle_flavor_enabled and bool(_ga(_settings, "haptic_wheelspin_enabled", False)):
            l_sig = self._osc["wheel_l"].sine(frames, sr, hz(0.66)) * 0.80 + noise(frames, 0.20)
            r_sig = self._osc["wheel_r"].sine(frames, sr, hz(0.67)) * 0.80 + noise(frames, 0.20)
            add_lr(l_sig, r_sig, st.wheelspin_l * layer_mul("wheelspin") * _gain(_ga(_settings, "haptic_grip_assist_strength", 0.55), 0.0, 1.0), st.wheelspin_r * layer_mul("wheelspin") * _gain(_ga(_settings, "haptic_grip_assist_strength", 0.55), 0.0, 1.0), "haptic_wheelspin_gain", 0.36)
            high_master = wide_gain_setting("haptic_high_edge_gain", 1.5, 3.0)
            # grip recovery high-freq burst → when wheelspin decreases rapidly
            # (tire regaining grip), emit a short 280Hz shimmer as "contact restored" cue.
            # Uses the delta between previous and current wheelspin level.
            prev_ws = getattr(self, "_prev_wheelspin", 0.0)
            curr_ws = max(st.wheelspin_l, st.wheelspin_r)
            ws_recovery = max(0.0, prev_ws - curr_ws)
            self._prev_wheelspin = curr_ws
            grip_cooldown = getattr(self, "_grip_burst_until", 0.0)
            if ws_recovery > 0.08 and high_master > 0.0 and now > grip_cooldown:
                self._grip_burst_until = now + 0.080  # 80ms cooldown
                if "grip_recovery_l" not in self._osc:
                    self._osc["grip_recovery_l"] = Osc()
                    self._osc["grip_recovery_r"] = Osc()
                grip_burst_l = self._osc["grip_recovery_l"].sine(frames, sr, 280.0) * ws_recovery * 0.42
                grip_burst_r = self._osc["grip_recovery_r"].sine(frames, sr, 295.0) * ws_recovery * 0.42
                vehicle_l += grip_burst_l * high_master * 0.55
                vehicle_r += grip_burst_r * high_master * 0.55
            wh_l = (self._osc["wheelspin_edge_l"].sine(frames, sr, hz(0.97)) * 0.18 + noise(frames, 0.52)) * pulse_train(frames, sr, 58.0 + min(44.0, speed * 0.18), 0.25)
            wh_r = (self._osc["wheelspin_edge_r"].sine(frames, sr, hz(0.98)) * 0.18 + noise(frames, 0.52)) * pulse_train(frames, sr, 60.0 + min(44.0, speed * 0.17), 0.24)
            add_lr(wh_l, wh_r, st.wheelspin_l * high_master, st.wheelspin_r * high_master, "haptic_wheelspin_edge_high_strength", 0.52, layer="drift")

        if spatial_haptics_enabled and bool(_ga(_settings, "haptic_scrub_enabled", False)):
            l_sig = self._osc["scrub_l"].sine(frames, sr, hz(0.38)) * 0.70 + noise(frames, 0.30)
            r_sig = self._osc["scrub_r"].sine(frames, sr, hz(0.39)) * 0.70 + noise(frames, 0.30)
            add_lr(l_sig, r_sig, st.scrub_l * layer_mul("scrub") * _gain(_ga(_settings, "haptic_grip_assist_strength", 0.55), 0.0, 1.0), st.scrub_r * layer_mul("scrub") * _gain(_ga(_settings, "haptic_grip_assist_strength", 0.55), 0.0, 1.0), "haptic_scrub_gain", 0.30)

        # Big suspension hits / landings: wheel-specific, front sharper, rear lower.
        if special_events_enabled and bool(_ga(_settings, "haptic_bump_enabled", False)):
            add_spatial(self._osc["bump_fl"].sine(frames, sr, hz(0.22 + 0.10 * fr_contrast)), st.bump_fl, "left", "haptic_bump_gain", "bump", 0.58)
            add_spatial(self._osc["bump_fr"].sine(frames, sr, hz(0.23 + 0.10 * fr_contrast)), st.bump_fr, "right", "haptic_bump_gain", "bump", 0.58)
            add_spatial(self._osc["bump_rl"].sine(frames, sr, hz(0.08 + 0.02 * fr_contrast)), st.bump_rl, "left", "haptic_bump_gain", "bump", 0.58)
            add_spatial(self._osc["bump_rr"].sine(frames, sr, hz(0.09 + 0.02 * fr_contrast)), st.bump_rr, "right", "haptic_bump_gain", "bump", 0.58)
            bass_master = wide_gain_setting("haptic_bass_foundation_gain", 1.5, 3.0)
            if bass_master > 0.0:
                sub_l = self._osc["bump_sub_l"].sub_punch(frames, sr, hz(0.055), 1.2, 30.0) * 1.42 + noise(frames, 0.045)
                sub_r = self._osc["bump_sub_r"].sub_punch(frames, sr, hz(0.058), 1.2, 30.0) * 1.42 + noise(frames, 0.045)
                add_spatial(sub_l, max(st.bump_fl, st.bump_rl) * bass_master, "left", "haptic_bump_sub_strength", "bump", 0.52)
                add_spatial(sub_r, max(st.bump_fr, st.bump_rr) * bass_master, "right", "haptic_bump_sub_strength", "bump", 0.52)

        # Scrape / side-contact: one-sided rough scrape, distinct from a blunt collision.
        if special_events_enabled and bool(_ga(_settings, "haptic_scrape_enabled", True)):
            sc_l = self._osc["scrape_l"].sine(frames, sr, hz(0.48)) * 0.44 + noise(frames, 0.48)
            sc_r = self._osc["scrape_r"].sine(frames, sr, hz(0.49)) * 0.44 + noise(frames, 0.48)
            add_lr(sc_l, sc_r, st.scrape_l * layer_mul("scrape"), st.scrape_r * layer_mul("scrape"), "haptic_scrape_strength", 0.62)

        # Boost / torque surge / mechanical shift sequence. Engine flavour does not
        # rewrite trigger output; it adds whole-pad drivetrain feel.
        shift_active = max(st.shift_kick, st.shift_click, st.shift_clunk, st.shift_rattle, getattr(st, "shift_tail", 0.0), getattr(st, "shift_torque_cut", 0.0)) > 0.0
        if not shift_active:
            self._shift_diag = {}
        shift_master = _gain(_ga(_settings, "haptic_shift_master_gain", 1.0), 0.0, 2.80)
        torque_cut = _gain(_ga(_settings, "haptic_shift_torque_cut_strength", 0.52), 0.0, 1.0) * float(getattr(st, "shift_torque_cut", 0.0))
        # The clutch/torque-cut gap should feel like the engine stopped pushing for
        # a blink between click and clunk. Duck engine/body; keep road readable.
        shift_engine_duck = 1.0 - min(0.80, torque_cut * 0.80)
        if vehicle_flavor_enabled and bool(_ga(_settings, "haptic_boost_build_enabled", True)):
            boost_sig = self._osc["boost_build"].sine(frames, sr, hz(0.82)) * 0.48 + noise(frames, 0.24)
            surge_sig = self._osc["torque_surge"].sine(frames, sr, hz(0.18)) * 0.70 + noise(frames, 0.12)
            add_lr(boost_sig, boost_sig, st.boost_build * layer_mul("engine") * center_vehicle_duck * shift_engine_duck, st.boost_build * layer_mul("engine") * center_vehicle_duck * shift_engine_duck, "haptic_boost_strength", 0.42)
            add_lr(surge_sig, surge_sig, st.torque_surge * layer_mul("engine") * center_vehicle_duck * shift_engine_duck, st.torque_surge * layer_mul("engine") * center_vehicle_duck * shift_engine_duck, "haptic_torque_surge_strength", 0.45)
            bass_master = wide_gain_setting("haptic_bass_foundation_gain", 1.5, 3.0)
            if bass_master > 0.0:
                speed_floor = max(0.0, min(1.0, (speed - 135.0) / 150.0)) * (0.35 + 0.65 * center_vehicle_duck)
                engine_amp = max(st.idle_engine * 0.78 * _idle_strength, st.launch_load * 0.90, st.launch_release * 1.00, st.torque_surge * 0.78, st.boost_build * 0.54)
                engine_bass = self._osc["engine_bass"].sine(frames, sr, hz(0.050)) * 1.36 + noise(frames, 0.045)
                high_bass = self._osc["high_speed_bass"].sine(frames, sr, hz(0.065)) * 1.02 + noise(frames, 0.032)
                add_lr(engine_bass, engine_bass, engine_amp * bass_master * shift_engine_duck, engine_amp * bass_master * shift_engine_duck, "haptic_engine_bass_strength", 0.42, layer="engine")
                add_lr(high_bass, high_bass, speed_floor * bass_master, speed_floor * bass_master, "haptic_high_speed_bass_strength", 0.22, layer="engine")
        if vehicle_flavor_enabled and shift_active:
            # 6.3.1 mechanical shifter: click -> torque-cut void -> metallic clunk
            # -> adjustable tail/reverb. This reads more like clutch/gear engagement
            # than a flat tick.
            character = str(getattr(st, "shift_character", "street_sport") or "street_sport")
            if not self._shift_seq_prev_active:
                self._shift_seq_pos = 0.0
            self._shift_seq_prev_active = True
            t0 = float(self._shift_seq_pos)
            t = (np.arange(frames, dtype=np.float32) / float(sr)) + t0
            self._shift_seq_pos = t0 + frames / float(sr)

            # Gear-dependent burst: low gears = heavy thud, high gears = sharp click.
            # Low gears (1-3): large freq change, gear 4+: subtle change
            gear = max(1.0, min(10.0, float(getattr(st, "shift_gear", 3.0))))
            # Gears 1-3: steep freq change (80/100/120Hz), 4+: gentle (120/140/145/150...)
            if gear <= 3.0:
                # Low gear: 20Hz/gear steps (80/100/120Hz)
                burst_hz = 80.0 + (gear - 1.0) * 20.0
            else:
                # High gear: 120Hz base, 5Hz/gear increments (subtle)
                burst_hz = 120.0 + (gear - 3.0) * 5.0
            burst_hz = max(80.0, min(160.0, burst_hz))  # cap at 160Hz
            # cycles: 1-3 gears heavy (7/6/5), 4+ gears subtle (5/4.7/4.4/...)
            if gear <= 3.0:
                burst_cycles = 8.0 - gear  # 7/6/5 cycles
            else:
                # High gear: 5 cycles base, subtly decreasing (0.3/gear)
                burst_cycles = max(3.0, 5.0 - (gear - 3.0) * 0.3)
            burst_dur = burst_cycles / burst_hz
            attack = np.sign(np.sin(2.0 * np.pi * burst_hz * t))
            attack *= (t < burst_dur).astype(np.float32)
            attack_low = attack.copy()

            shift_event_mul = shift_master * 5.0  # 0.5 saturates to ±1.0 after full chain
            # Duck (not zero) event bus → reduce kerb/bump to 20% so shift cuts through
            # without completely discarding simultaneous impacts.
            event_l *= 0.20
            event_r *= 0.20
            if st.shift_click > 0.0:
                add_lr(attack, attack, st.shift_click * shift_event_mul, st.shift_click * shift_event_mul, "haptic_shift_click_strength", 1.50, layer="shift")
            if st.shift_kick > 0.0:
                add_lr(attack_low, attack_low, st.shift_kick * shift_event_mul, st.shift_kick * shift_event_mul, "haptic_shift_body_kick_strength", 1.30, layer="shift")
            # Shift sub-bass: low-frequency thud for gear engagement body feel
            shift_bass_amp = max(st.shift_click, st.shift_kick, st.shift_clunk) * shift_event_mul
            if shift_bass_amp > 0.0:
                bass_sig = self._osc["shift_bass"].sine(frames, sr, hz(0.045)) * 1.2 + noise(frames, 0.06)
                bass_env = (t < burst_dur * 1.5).astype(np.float32)
                bass_sig *= bass_env
                add_lr(bass_sig, bass_sig, shift_bass_amp, shift_bass_amp, "haptic_shift_bass_strength", 0.80, layer="shift")
            # Shift signal chain diagnostics → written to render_stats / raw_logs
            # Only update if this callback has a bigger peak (first callback has
            # the impulse; subsequent ones are near-zero and would overwrite).
            if st.shift_click > 0.0 or st.shift_kick > 0.0:
                _ev_peak = max(float(np.max(np.abs(event_l))), float(np.max(np.abs(event_r))))
                _imp_peak = float(np.max(np.abs(attack)))
                _bus = _gain(_ga(_settings, "haptic_event_bus_gain", 0.84), 0.0, 2.4)
                _prev_peak = self._shift_diag.get("shift_ev_peak", 0.0) if isinstance(getattr(self, "_shift_diag", None), dict) else 0.0
                if _ev_peak > _prev_peak:
                    self._shift_diag = {
                        "shift_ev_peak": round(_ev_peak, 4),
                        "shift_imp_peak": round(_imp_peak, 4),
                        "shift_mul": round(shift_event_mul, 4),
                        "shift_final_out": round(_ev_peak * _bus, 4),
                    }
        else:
            self._shift_seq_prev_active = False
        if vehicle_flavor_enabled and bool(_ga(_settings, "haptic_brake_body_enabled", False)):
            b_l = self._osc["brake_body_l"].sine(frames, sr, hz(0.14)) * 0.76 + noise(frames, 0.10)
            b_r = self._osc["brake_body_r"].sine(frames, sr, hz(0.15)) * 0.76 + noise(frames, 0.10)
            add_lr(b_l, b_r, st.brake_body_l * layer_mul("brake"), st.brake_body_r * layer_mul("brake"), "haptic_brake_body_strength", 0.42)
            # ABS pulse: square wave at 18-32Hz for distinct "thud" feel
            abs_freq = 18.0 + min(14.0, speed * 0.07)  # 18-32Hz based on speed
            tick = np.sign(np.sin(2.0 * np.pi * abs_freq * (np.arange(frames, dtype=np.float32) / float(sr))))
            tick *= pulse_train(frames, sr, abs_freq, 0.45)  # duty cycle 45%
            a_l = tick * 0.85 + self._osc["abs_body_l"].sine(frames, sr, hz(0.54)) * 0.15
            a_r = tick * 0.85 + self._osc["abs_body_r"].sine(frames, sr, hz(0.55)) * 0.15
            add_lr(a_l, a_r, st.abs_body_l * layer_mul("brake") * 1.25, st.abs_body_r * layer_mul("brake") * 1.25, "haptic_abs_body_strength", 0.42)
            high_master = wide_gain_setting("haptic_high_edge_gain", 1.5, 3.0)
            be_l = (self._osc["brake_edge_l"].sine(frames, sr, hz(0.93)) * 0.22 + noise(frames, 0.48)) * pulse_train(frames, sr, 72.0, 0.20)
            be_r = (self._osc["brake_edge_r"].sine(frames, sr, hz(0.94)) * 0.22 + noise(frames, 0.48)) * pulse_train(frames, sr, 74.0, 0.20)
            add_lr(be_l, be_r, st.abs_body_l * high_master, st.abs_body_r * high_master, "haptic_brake_edge_high_strength", 0.48, layer="brake")

        # Collision is top priority. It ducks background and adds a strong low thump.
        if special_events_enabled and bool(_ga(_settings, "haptic_collision_enabled", False)) and st.collision > 0:
            continuous_l *= 0.04
            continuous_r *= 0.04
            vehicle_l *= 0.10
            vehicle_r *= 0.10
            # Collision must dominate: +200% vs background, not +35%.
            # Stronger ducking (0.04/0.10) + tripled bass amplitudes.
            impact_master = _gain(_ga(_settings, "haptic_impact_master_gain", 1.0), 0.0, 2.50)
            thump_gate = pulse_train(frames, sr, 22.0, 0.22)
            low = self._osc["collision"].harmonic(frames, sr, hz(0.035), (1.0, 0.55, 0.18)) * (2.20 + thump_gate * 1.40)
            hi = self._osc["collision_hi"].harmonic(frames, sr, hz(0.48), (1.0, 0.3)) * 0.42
            bass_master = wide_gain_setting("haptic_bass_foundation_gain", 1.5, 3.0)
            high_master = wide_gain_setting("haptic_high_edge_gain", 1.5, 3.0)
            # Tripled sub-punch for visceral weight on every collision type
            sub = (self._osc["impact_sub"].sub_punch(frames, sr, hz_named("haptic_freq_impact_body_hz", 64.0, 0.060), 1.8, 22.0) * 6.50 + noise(frames, 0.08)) * (0.55 + thump_gate * 0.45) * bass_master
            # Bass rumble tail: decaying 55Hz sine for sustained weight
            if "collision_bass_tail" not in self._osc:
                self._osc["collision_bass_tail"] = Osc()
            bass_tail = self._osc["collision_bass_tail"].sine(frames, sr, 55.0) * 1.80
            crack_hi = (self._osc["impact_crack_high"].harmonic(frames, sr, hz_named("haptic_freq_impact_crack_hz", 455.0, 1.00), (1.0, 0.6, 0.25)) * 0.62 + noise_burst(frames, sr, 380.0, 0.72)) * high_master
            sig = low + hi + sub * gain_attr("haptic_impact_sub_strength", 0.62) + bass_tail * st.collision * bass_master * 1.60
            if st.collision_crack > 0.0:
                crack_gain = _gain(_ga(_settings, "haptic_collision_crack_strength", 0.80), 0.0, 1.8)
                sig = sig + self._osc["crack"].sine(frames, sr, hz(0.96)) * st.collision_crack * crack_gain
                sig = sig + crack_hi * st.collision_crack * gain_attr("haptic_impact_crack_high_strength", 0.60)
            # Use the spatial collision envelopes when present. Center fallback is
            # kept for direct hits, then scaled by impact master above normal gain.
            c_l = st.collision_l if max(st.collision_l, st.collision_r) > 0.0 else st.collision
            c_r = st.collision_r if max(st.collision_l, st.collision_r) > 0.0 else st.collision
            add_lr(sig, sig, c_l * impact_master * layer_mul("collision"), c_r * impact_master * layer_mul("collision"),
                   "haptic_collision_gain", 0.90, layer="collision")

        # Delayed side echo: this is the main L/R spatial cue. Immediate crossfeed
        # sounds mono on DualSense; a weak 15-30ms opposite-side echo reads as space.
        # pre-allocated delay avoids per-callback allocation (audio-thread safe).
        def delayed(src, key: str, delay_ms: float):
            delay = max(0, int(sr * max(0.0, float(delay_ms)) / 1000.0))
            if delay <= 0:
                return np.zeros_like(src)
            need = delay + frames
            buf = self._delay_buffers.get(key)
            if buf is None or len(buf) < need:
                # Allocate once: holds delay history + one block workspace
                buf = np.zeros(need, dtype=np.float32)
                self._delay_buffers[key] = buf
            # Read delayed output from front of buffer
            out = buf[:frames].copy()
            # Shift buffer left by frames, append new source at the end
            buf[:delay] = buf[frames:frames + delay]
            buf[delay:need] = src.astype(np.float32, copy=False)
            return out

        if spatial_haptics_enabled:
            side_cf = _gain(_ga(_settings, "haptic_side_crossfeed", 0.12), 0.0, 0.45)
            # Strong direction feedback wants 7:3~8:2, not a polite 6:4.
            if side_focus > 0.12:
                side_cf *= max(0.25, 1.0 - side_focus * 1.10)
            side_delay = _gain(_ga(_settings, "haptic_side_event_delay_ms", 22.0), 0.0, 45.0)
            if side_cf > 0.0 and side_delay > 0.0:
                src_l = event_l.copy()
                src_r = event_r.copy()
                event_l = event_l + delayed(src_r, "event_r_to_l", side_delay) * side_cf
                event_r = event_r + delayed(src_l, "event_l_to_r", side_delay) * side_cf

            veh_cf = _gain(_ga(_settings, "haptic_side_vehicle_crossfeed", 0.055), 0.0, 0.22)
            veh_delay = _gain(_ga(_settings, "haptic_side_vehicle_delay_ms", 20.0), 0.0, 40.0)
            if veh_cf > 0.0 and veh_delay > 0.0 and side_focus > 0.04:
                src_l = vehicle_l.copy()
                src_r = vehicle_r.copy()
                vehicle_l = vehicle_l + delayed(src_r, "veh_r_to_l", veh_delay) * veh_cf
                vehicle_r = vehicle_r + delayed(src_l, "veh_l_to_r", veh_delay) * veh_cf

        # 2.0 SimHub/music-style glue + punch stage.
        # Refactored into haptic_mixer.py so telemetry feature extraction,
        # band glue, event punch and diagnostics can evolve without bloating the
        # audio backend. Adaptive trigger logic remains untouched; this stage
        # complements it by keeping finger-clicks on triggers and whole-pad body
        #/impact in audio haptics.
        features = extract_features(st)
        dt_ms = 1000.0 * max(1, int(frames)) / max(1, int(sr))
        transients = self._transients.update({
            "shift": features.shift_punch,
            "impact": features.impact_punch,
            "bump": features.bump_punch,
            "grip": features.grip_punch,
            # NEW: accel/decel onset (momentary impact)
            "accel_onset": features.accel_onset,
            "decel_onset": features.decel_onset,
            "shift_engage": features.shift_engage,
        }, dt_ms)
        # Store transient results in HapticState for renderers
        st.accel_onset = transients.get("accel_onset", 0.0)
        st.decel_onset = transients.get("decel_onset", 0.0)
        st.shift_engagement = transients.get("shift_engage", 0.0)

        # ── Engine start: starter motor + ignition sequence (event bus) ──
        _es = float(getattr(st, "engine_start", 0.0))
        if _es > 0.01:
            _es_str = _gain(_ga(_settings, "haptic_engine_start_strength", 0.70), 0.0, 2.0)
            if _es_str > 0.0:
                if "engine_start_s" not in self._osc:
                    self._osc["engine_start_s"] = Osc()
                    self._osc["engine_start_i"] = Osc()
                # Starter motor: 85Hz + 20Hz pulse train
                _es_starter = self._osc["engine_start_s"].sine(frames, sr, 85.0) * 0.5
                _es_starter += pulse_train(frames, sr, 20.0, 0.35) * 0.3
                # Ignition catch: 52Hz LRA-range thump
                _es_ignite = self._osc["engine_start_i"].sine(frames, sr, 52.0) * 0.65
                _es_sig = _es_starter * 0.6 + _es_ignite * 0.4
                _es_amp = _es * _es_str
                event_l += _es_sig * _es_amp
                event_r += _es_sig * _es_amp

        # ── Accel onset: sudden acceleration burst (engine bus) ──
        if st.accel_onset > 0.01:
            _ao_str = _gain(_ga(_settings, "haptic_accel_onset_strength", 0.55), 0.0, 2.0)
            if _ao_str > 0.0:
                # BURST: 90Hz × 4 cycles = 44ms sharp thump
                _ao_dur = 4.0 / 90.0
                _ao_n = min(frames, int(_ao_dur * sr))
                _ao_t = np.arange(_ao_n, dtype=np.float32) / float(sr)
                _ao_burst = np.zeros(frames, dtype=np.float32)
                _ao_burst[:_ao_n] = np.sign(np.sin(2.0 * np.pi * 90.0 * _ao_t)) * st.accel_onset * _ao_str
                engine_l += _ao_burst
                engine_r += _ao_burst

        # ── Decel onset: sudden deceleration burst (event bus) ──
        if st.decel_onset > 0.01:
            _do_str = _gain(_ga(_settings, "haptic_decel_onset_strength", 0.50), 0.0, 2.0)
            if _do_str > 0.0:
                # BURST: 75Hz × 5 cycles = 67ms heavier thump
                _do_dur = 5.0 / 75.0
                _do_n = min(frames, int(_do_dur * sr))
                _do_t = np.arange(_do_n, dtype=np.float32) / float(sr)
                _do_burst = np.zeros(frames, dtype=np.float32)
                _do_burst[:_do_n] = np.sign(np.sin(2.0 * np.pi * 75.0 * _do_t)) * st.decel_onset * _do_str
                event_l += _do_burst
                event_r += _do_burst

        # ── Shift engagement: clutch engagement shock (event bus) ──
        if st.shift_engagement > 0.01:
            _se_str = _gain(_ga(_settings, "haptic_shift_engagement_strength", 0.65), 0.0, 2.0)
            if _se_str > 0.0:
                # BURST: 80Hz × 4 cycles = 50ms crisp thud
                _se_dur = 4.0 / 80.0
                _se_n = min(frames, int(_se_dur * sr))
                _se_t = np.arange(_se_n, dtype=np.float32) / float(sr)
                _se_burst = np.zeros(frames, dtype=np.float32)
                _se_burst[:_se_n] = np.sign(np.sin(2.0 * np.pi * 80.0 * _se_t)) * st.shift_engagement * _se_str
                event_l += _se_burst
                event_r += _se_burst

        continuous_l, continuous_r, vehicle_l, vehicle_r, event_l, event_r, mix_diag = apply_musical_mix(
            st=st, settings=_settings, oscs=self._osc, frames=frames, sr=sr, hz=hz,
            continuous_l=continuous_l, continuous_r=continuous_r,
            vehicle_l=vehicle_l, vehicle_r=vehicle_r, event_l=event_l, event_r=event_r,
            transients=transients,
        )
        self._last_mixer_diag = mix_diag.render_stats()

        # Sub-bass foundation layer (40-80Hz) → adds persistent low-end body
        # that the tester reported missing. Speed-gated to avoid idle rumble.
        # Goes to vehicle bus so mastering can duck it during events.
        if speed > 15.0 and bool(_ga(_settings, "haptic_vehicle_flavor_enabled", True)):
            sub_bass_boost = _gain(_ga(_settings, "haptic_sub_bass_boost", 0.0), 0.0, 0.54)
            if sub_bass_boost > 0.0:
                if "sub_bass_l" not in self._osc:
                    self._osc["sub_bass_l"] = Osc()
                    self._osc["sub_bass_r"] = Osc()
                # Frequency shifts slightly with speed for organic feel
                sb_freq = 45.0 + min(30.0, speed * 0.08)  # 45-75Hz
                sb_l = self._osc["sub_bass_l"].sine(frames, sr, sb_freq) * sub_bass_boost
                sb_r = self._osc["sub_bass_r"].sine(frames, sr, sb_freq * 1.02) * sub_bass_boost
                bass_master = _gain(_ga(_settings, "haptic_bass_foundation_gain", 1.5), 0.0, 3.0)
                vehicle_l += sb_l * bass_master * 0.20
                vehicle_r += sb_r * bass_master * 0.20

        # High-frequency shimmer layer (250-400Hz) → auxiliary sparkle for
        # slip recovery, wet surfaces, high-RPM. Capped at 20% of total output.
        high_shimmer_enabled = speed > 20.0 and _gain(_ga(_settings, "haptic_high_edge_gain", 1.5), 0.0, 3.0) > 0.0
        if high_shimmer_enabled:
            shimmer_ratio = _gain(_ga(_settings, "haptic_high_shimmer_ratio", 0.08), 0.0, 0.45)
            if shimmer_ratio > 0.0:
                # Shimmer driven by grip-edge + wetness + high-rpm
                shimmer_drive = max(
                    getattr(st, "asphalt_grip_l", 0.0), getattr(st, "asphalt_grip_r", 0.0),
                    getattr(st, "wet_asphalt_l", 0.0) * 0.6,
                    max(0.0, (getattr(st, "rpm_norm", 0.0) - 0.7)) * 1.5,
                )
                shimmer_drive = min(1.0, shimmer_drive)
                if shimmer_drive > 0.05:
                    if "shimmer_l" not in self._osc:
                        self._osc["shimmer_l"] = Osc()
                        self._osc["shimmer_r"] = Osc()
                    sh_freq = 280.0 + shimmer_drive * 80.0  # 280-360Hz
                    sh_l = self._osc["shimmer_l"].sine(frames, sr, sh_freq) * shimmer_drive * shimmer_ratio * 0.35
                    sh_r = self._osc["shimmer_r"].sine(frames, sr, sh_freq * 1.03) * shimmer_drive * shimmer_ratio * 0.35
                    continuous_l += sh_l
                    continuous_r += sh_r

        # Bus master gains make practical tuning easier: lower constant buzz without
        # killing events, or raise vehicle body feel without raising weather/noise.
        # During shift: ZERO out continuous+vehicle+engine so LRA is completely still
        # before the impulse hits. This replicates the "test button" clean path
        # where the engine is paused and only the impulse plays.
        if shift_active:
            continuous_l[:] = 0.0
            continuous_r[:] = 0.0
            vehicle_l[:] = 0.0
            vehicle_r[:] = 0.0
            engine_l[:] = 0.0
            engine_r[:] = 0.0
            # event bus was already written by kerb/bump/collision before shift.
            # Don't zero here → shift code is ABOVE this point and already wrote.
            # Instead, zero event bus INSIDE the shift block, before add_lr.
        
        # Apply bus master gains (4-layer gain stack: Bus × Source)
        # Note: haptic_master_gain is applied at the callback level (final_gain),
        # so bus gains here are independent multipliers only.
        surface_bus = _gain(_ga(_settings, "haptic_surface_bus_gain", 0.52), 0.0, 2.0)
        vehicle_bus = _gain(_ga(_settings, "haptic_vehicle_bus_gain", 0.72), 0.0, 2.2)
        engine_bus = _gain(_ga(_settings, "haptic_engine_bus_gain", 0.65), 0.0, 2.0)
        event_bus = _gain(_ga(_settings, "haptic_event_bus_gain", 0.84), 0.0, 2.4)
        
        continuous_l *= surface_bus
        continuous_r *= surface_bus
        vehicle_l *= vehicle_bus
        vehicle_r *= vehicle_bus
        engine_l *= engine_bus
        engine_r *= engine_bus
        event_l *= event_bus
        event_r *= event_bus

        # 4-bus mastering (engine bus now included)
        continuous_l, continuous_r, vehicle_l, vehicle_r, engine_l, engine_r, event_l, event_r, master_diag = self._mastering.process(
            st=st, features=extract_features(st), settings=_settings, frames=frames, sr=sr,
            continuous_l=continuous_l, continuous_r=continuous_r,
            vehicle_l=vehicle_l, vehicle_r=vehicle_r,
            engine_l=engine_l, engine_r=engine_r,
            event_l=event_l, event_r=event_r,
        )
        self._last_mixer_diag.update(master_diag.render_stats())

        # Four-bus mix. Event bus is never limiter-ducked by continuous texture;
        # continuous and vehicle ducks are already computed in haptic_textures.
        # Engine bus is now separate from vehicle - user can independently control RPM/idle.
        left = continuous_l + vehicle_l + engine_l + event_l
        right = continuous_r + vehicle_r + engine_r + event_r

        # directional preservation: logs showed state-side delta was much larger
        # than render-side delta. Keep constant buzz quiet, but preserve side cues
        # right before limiter/soft-clip by widening mid/side only when real L/R
        # vehicle or event information exists.
        if spatial_haptics_enabled:
            side_bus_delta = max(
                abs(float(st.event_bus_l) - float(st.event_bus_r)),
                abs(float(st.vehicle_bus_l) - float(st.vehicle_bus_r)),
                side_focus,
            )
            side_bus_delta = max(0.0, min(1.0, side_bus_delta))
            side_boost = _gain(_ga(_settings, "haptic_final_side_boost", 0.35), 0.0, 0.90) * side_bus_delta
            # 6.2: major drift needs more separation than normal cornering.
            drift_boost = max(0.0, min(1.0, float(getattr(st, "drift_confidence", 0.0))))
            if drift_boost > 0.0:
                side_boost = min(0.95, side_boost + drift_boost * _gain(_ga(_settings, "haptic_drift_side_bias", 0.82), 0.0, 1.0) * 0.35)
            if side_boost > 0.0:
                mid = (left + right) * 0.5
                side = (left - right) * 0.5
                mid *= (1.0 - min(0.38, side_boost * (0.44 + 0.18 * drift_boost)))
                side *= (1.0 + side_boost * (1.42 + 0.70 * drift_boost))
                left = mid + side
                right = mid - side

        # Do not soft-clip here. The callback applies the final limiter/soft-clip after
        # master gain, so double clipping was shaving off short punchy events.
        return left, right


# --- one-shot tests ---------------------------------------------------------


def available_device_labels() -> list[str]:
    try:
        return [d.label for d in list_output_devices(min_channels=1)]
    except (ImportError, RuntimeError, OSError) as exc:
        log.warning("HAPTIC device list failed: %s", exc)
        return []


def candidate_device_labels() -> list[str]:
    try:
        return [d.label for d in dualsense_candidates()]
    except (ImportError, RuntimeError, OSError) as exc:
        log.warning("HAPTIC candidate list failed: %s", exc)
        return []


def _device_or_raise(settings):
    dev = find_device(getattr(settings, "haptic_device_name", ""), min_channels=4)
    if dev is None:
        labels = available_device_labels()[:8]
        hint = " | ".join(labels) if labels else "no output devices visible"
        raise RuntimeError(f"No 4-channel haptic audio device found. Visible: {hint}")
    return dev


# Track the active engine so test functions can pause/resume it
_active_engine: HapticAudioEngine | None = None
_test_lock = threading.Lock()  # serialize texture/channel test playback


def register_engine(engine: HapticAudioEngine | None) -> None:
    global _active_engine
    _active_engine = engine


def _pause_engine() -> None:
    """Temporarily stop the engine stream so sd.play can use the device."""
    e = _active_engine
    if e is not None and e._stream is not None:
        try:
            e._stream.stop()
        except (RuntimeError, OSError):
            pass


def _resume_engine() -> None:
    """Restart the engine stream after a test play."""
    e = _active_engine
    if e is not None and e._stream is not None:
        try:
            e._stream.start()
        except (RuntimeError, OSError):
            pass


def play_channel_test(settings, channel: int, freq: float = 100.0, duration_s: float = 0.30, gain: float | None = None) -> None:
    if np is None:
        raise RuntimeError("numpy is required")
    import sounddevice as sd
    dev = _device_or_raise(settings)
    sr = int(getattr(settings, "haptic_sample_rate", 48000) or 48000)
    ch = max(0, min(3, int(channel) - 1))
    g = float(gain if gain is not None else getattr(settings, "haptic_master_gain", 0.40))
    if float(freq) <= 0:
        freq = (80.0, 120.0, 170.0, 220.0)[ch]
    sig = make_test_texture("tone", sr, duration_s, max(0.0, min(1.0, g)), freq=float(freq))
    data = np.zeros((len(sig), 4), dtype=np.float32)
    data[:, ch] = sig
    log.info("HAPTIC test ch%d %.0fHz gain=%.2f on %s", channel, float(freq), max(0.0, min(1.0, g)), dev.label)
    with _test_lock:
        _pause_engine()
        try:
            sd.play(data, samplerate=sr, device=dev.index, blocking=True)
            sd.stop()
        finally:
            _resume_engine()


def play_channel_scan(settings, duration_s: float = 0.28, gap_s: float = 0.18, gain: float | None = None) -> None:
    """Sequentially play ch1..ch4. Use this before enabling Forza haptics."""
    import time as _time
    freqs = (80.0, 120.0, 170.0, 220.0)
    log.info("HAPTIC channel scan start: ch1 -> ch4")
    for i, f in enumerate(freqs, start=1):
        play_channel_test(settings, i, freq=f, duration_s=duration_s, gain=gain)
        _time.sleep(max(0.0, float(gap_s)))
    log.info("HAPTIC channel scan done. Set L/R output channels to the two channels felt in the grips.")


def play_texture_test(settings, kind: str, duration_s: float = 0.45) -> None:
    if np is None:
        raise RuntimeError("numpy is required")
    import sounddevice as sd
    dev = _device_or_raise(settings)
    sr = int(getattr(settings, "haptic_sample_rate", 48000) or 48000)
    master = _gain(getattr(settings, "haptic_master_gain", 0.40), 0.0, 1.0)
    sig = make_test_texture(kind, sr, duration_s, master)
    data = np.zeros((len(sig), 4), dtype=np.float32)
    li = max(0, min(3, int(getattr(settings, "haptic_left_channel", 3)) - 1))
    ri = max(0, min(3, int(getattr(settings, "haptic_right_channel", 4)) - 1))
    data[:, li] = sig
    data[:, ri] = sig
    log.info("HAPTIC texture test %s on %s | L=ch%d R=ch%d", kind, dev.label, li + 1, ri + 1)
    with _test_lock:
        _pause_engine()
        try:
            sd.play(data, samplerate=sr, device=dev.index, blocking=True)
            sd.stop()
        finally:
            _resume_engine()


def play_texture_sequence(settings, kinds=("kerb", "thump", "shift"), duration_s: float = 0.42, gap_s: float = 0.18) -> None:
    import time as _time
    log.info("HAPTIC texture scan start: %s", ", ".join(kinds))
    for kind in kinds:
        play_texture_test(settings, str(kind), duration_s=duration_s)
        _time.sleep(max(0.0, float(gap_s)))
    log.info("HAPTIC texture scan done")


def _gain(v, lo=0.0, hi=1.0) -> float:
    try:
        f = float(v)
    except (ValueError, TypeError):
        f = lo
    return max(lo, min(hi, f))


def play_setting_tick(settings, duration_s: float = 0.06) -> None:
    """Ultra-short haptic tick for UI feedback. Does NOT pause engine."""
    if np is None:
        return
    try:
        import sounddevice as sd
        dev = _device_or_raise(settings)
    except Exception:
        return
    sr = int(getattr(settings, "haptic_sample_rate", 48000) or 48000)
    frames = int(sr * duration_s)
    # 75Hz square burst × gain 0.35 → subtle "thock"
    t = np.arange(frames, dtype=np.float32) / sr
    sig = (np.sign(np.sin(2.0 * np.pi * 75.0 * t)) * 0.35).astype(np.float32)
    # Quick fade-out
    fade = int(frames * 0.3)
    if fade > 0:
        sig[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    data = np.zeros((frames, 4), dtype=np.float32)
    li = max(0, min(3, int(getattr(settings, "haptic_left_channel", 3)) - 1))
    ri = max(0, min(3, int(getattr(settings, "haptic_right_channel", 4)) - 1))
    data[:, li] = sig
    data[:, ri] = sig
    try:
        sd.play(data, samplerate=sr, device=dev.index, blocking=True)
        sd.stop()
    except Exception:
        pass
