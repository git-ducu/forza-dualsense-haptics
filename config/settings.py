"""All tunables in one place. Forces 0-255, frequencies in Hz.

Settings is organized into nested dataclasses by category for better
maintainability. The flat attribute access (settings.udp_port) is preserved
for backward compatibility via __getattr__/__setattr__.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class UDPSettings:
    """Network configuration for Forza Data Out."""
    host: str = "127.0.0.1"
    port: int = 5300
    timeout: float = 0.5
    forward: bool = False
    forward_to: str = "127.0.0.1:5301"


@dataclass
class TriggerSettings:
    """Adaptive trigger configuration."""
    # Pedal shared
    pedal_value_max: int = 255
    wall_zones: int = 3                       # was 2; wider wall for better end-stop feel
    
    # Custom trigger tuning
    road_texture_strength: float = 1.0
    left_road_strength: float = 0.75
    right_road_strength: float = 1.0
    wheelspin_sensitivity: float = 1.0
    wheelspin_hold_ms: float = 70.0
    tire_scrub_sensitivity: float = 2.0
    tire_scrub_road_strength: float = 1.0
    tire_scrub_offroad_strength: float = 0.35
    tire_scrub_max_force: float = 0.80
    tire_scrub_hold_ms: float = 60.0
    
    # Trigger master gains
    master_gain: float = 1.0
    shift_kick_gain: float = 1.0
    shift_clack_gain: float = 1.0
    shift_torque_cut_gain: float = 1.0
    shift_tail_gain: float = 1.0
    wheelspin_gain: float = 1.0
    abs_gain: float = 1.0
    
    # ABS settings
    abs_strength: float = 1.0
    abs_hold_ms: float = 75.0
    rev_limiter_strength: float = 1.0
    adaptive_acceleration_depth: float = 0.30
    suspension_bump_strength: float = 0.80    # was 0.55; bumps were barely felt
    suspension_bump_sensitivity: float = 1.0
    r2_effect_priority_mode: str = "balanced"
    adjustment_mode: str = "quick"
    enable_trigger_info_log: bool = False
    
    # Pedal base gains
    pedal_base_gain: float = 1.0
    grip_chatter_gain: float = 1.0
    impact_snap_gain: float = 1.0


@dataclass
class BrakeSettings:
    """L2 brake trigger configuration."""
    enable_resistance: bool = True
    deadzone: int = 50
    baseline_force: int = 1
    max_force: int = 7
    curve: float = 2.2
    wall_engage_at: int = 250
    wall_release_at: int = 200
    enable_static_wall: bool = False
    static_wall_at: int = 128
    static_wall_force: int = 255
    enable_handbrake_bonus: bool = False
    handbrake_bonus: int = 60
    
    # ABS pulse
    enable_abs: bool = True
    abs_brake_threshold: int = 80
    abs_min_speed_kmh: float = 15.0
    abs_slip_ratio_threshold: float = 1.0
    abs_combined_slip_threshold: float = 1.0
    abs_freq: int = 18
    abs_amp: int = 40
    enable_left_road_texture: bool = False


@dataclass
class ThrottleSettings:
    """R2 throttle trigger configuration."""
    enable_resistance: bool = True
    deadzone: int = 50
    baseline_force: int = 3
    max_force: int = 12
    curve: float = 2.8
    wall_engage_at: int = 250
    wall_release_at: int = 200
    
    # Rev limiter
    enable_rev_limiter: bool = True
    enable_rev_limiter_pattern: bool = False
    rev_limit_ratio: float = 0.93
    rev_limit_freq: int = 30
    rev_limit_amp: int = 50
    rev_limit_hold_ms: float = 120.0
    
    # Wheelspin buzz
    enable_wheelspin_buzz: bool = True
    wheelspin_amp: int = 27
    enable_right_road_texture: bool = True
    enable_positioned_vibration: bool = True
    enable_tire_scrub_buzz: bool = True
    enable_suspension_bump_buzz: bool = True
    
    # Idle buzz
    enable_idle_buzz: bool = True
    idle_max_speed_kmh: float = 5.0
    idle_accel_max: int = 64
    idle_freq: int = 30
    idle_amp_low: int = 1
    idle_amp_high: int = 30
    idle_period_s: float = 0.5
    
    # Gear shift
    enable_gear_shift: bool = True
    enable_gear_shift_brake: bool = True
    gear_shift_freq: int = 10
    gear_shift_amp: int = 255
    gear_shift_duration_ms: float = 100.0


@dataclass
class HapticAudioSettings:
    """DualSense haptic audio configuration."""
    enabled: bool = False
    enable_log: bool = False
    
    # Coarse switches
    idle_haptics_enabled: bool = True
    surface_texture_enabled: bool = True
    special_events_enabled: bool = True
    vehicle_flavor_enabled: bool = True
    spatial_haptics_enabled: bool = True
    
    # Device settings
    device_name: str = ""
    left_channel: int = 3
    right_channel: int = 4
    sample_rate: int = 48000
    buffer_ms: int = 10
    master_gain: float = 0.4
    signal_boost: float = 1.25
    
    # Layer enables
    road_enabled: bool = False
    kerb_enabled: bool = True
    gravel_enabled: bool = True
    puddle_enabled: bool = True
    wheelspin_enabled: bool = False
    scrub_enabled: bool = False
    bump_enabled: bool = True
    collision_enabled: bool = True
    weight_transfer_enabled: bool = False
    asphalt_grip_enabled: bool = False
    slide_body_enabled: bool = False
    idle_engine_enabled: bool = True
    launch_load_enabled: bool = True
    
    # Layer gains
    road_gain: float = 0.24
    kerb_gain: float = 0.62
    gravel_gain: float = 0.5
    puddle_gain: float = 0.68
    wheelspin_gain: float = 0.42
    scrub_gain: float = 0.42
    bump_gain: float = 0.58
    collision_gain: float = 0.72
    impact_master_gain: float = 1.0


@dataclass
class HapticMixerSettings:
    """Haptic mixer and mastering configuration."""
    # Band gains
    bass_foundation_gain: float = 1.0
    sub_bass_boost: float = 0.18
    high_edge_gain: float = 1.0
    high_shimmer_ratio: float = 0.15
    high_shimmer_cap: float = 0.2
    mid_texture_balance: float = 1.0
    
    # Glue settings
    spectrum_glue_gain: float = 1.0
    low_mid_glue_strength: float = 0.46
    high_mid_glue_strength: float = 0.38
    
    # Punch settings
    event_punch_gain: float = 1.00
    low_impact_gain: float = 1.00
    high_impact_gain: float = 1.00
    mid_duck_on_punch: float = 0.38
    mid_protect_enabled: bool = True
    mid_min_gain: float = 0.62
    punch_to_mid_limit: float = 55.0
    event_ratio_trim: float = 0.08
    punch_sustain_blend: float = 0.42
    
    # Mastering
    mastering_enabled: bool = True
    mastering_sidechain_strength: float = 0.1
    mastering_soft_saturation: float = 0.08
    duck_attack_ms: float = 8.0
    duck_release_ms: float = 110.0
    trigger_harmony_gain: float = 1.00


@dataclass
class SystemSettings:
    """System and application settings."""
    # Startup
    enable_startup_pulse: bool = True
    startup_pulse_force: int = 150
    
    # Reconnect
    enable_reconnect: bool = False
    reconnect_interval_s: float = 5.0
    
    # Controller selection
    controller_lock_serial: str = ""
    
    # Updates
    check_for_updates: bool = False
    
    # Language and developer
    language: str = "ko"
    developer_mode: bool = False
    
    # Diagnostics
    diagnostic_capture_seconds: int = 30
    diagnostic_target_size_mb: int = 5
    diagnostic_max_size_mb: int = 10
    diagnostic_sample_hz: int = 20
    
    # Auto exit
    exit_on_game_close: bool = True
    game_process_name_contains: tuple = ("forza",)
    game_poll_interval_s: float = 2.0
    telemetry_lost_exit_s: float = 60.0


@dataclass
class Settings:
    # MARK: UDP
    udp_host: str = "127.0.0.1"               # bind address for Forza Data Out
    udp_port: int = 5300                      # match Forza HUD setting
    udp_timeout: float = 0.5                  # socket recv timeout (s)
    udp_forward: bool = False                 # mirror raw packets to udp_forward_to (off by default)
    udp_forward_to: str = "127.0.0.1:5301"    # host:port targets (comma-separated) when udp_forward is on

    # MARK: Pedal shared
    pedal_value_max: int = 255                # raw pedal byte range. DO NOT CHANGE
    wall_zones: int = 3                       # was 2; wider wall for better end-stop feel

    # MARK: Custom trigger tuning
    # Multipliers/sensitivity controls for custom trigger algorithms. 1.0 = default.
    road_texture_strength: float = 1.0
    left_road_strength: float = 0.75
    right_road_strength: float = 1.0
    wheelspin_sensitivity: float = 1.0
    wheelspin_hold_ms: float = 70.0
    tire_scrub_sensitivity: float = 2.0
    tire_scrub_road_strength: float = 1.0
    tire_scrub_offroad_strength: float = 0.35
    tire_scrub_max_force: float = 0.80
    tire_scrub_hold_ms: float = 60.0
    # MARK: Trigger master
    # User-facing scale for trigger buzz effects. Keeps the algorithm shape intact
    # while letting the trigger side stay balanced against strong audio haptics.
    trigger_master_gain: float = 1.0
    trigger_l2_gain: float = 1.0   # L2 (brake) individual gain
    trigger_r2_gain: float = 1.0   # R2 (throttle) individual gain
    trigger_shift_kick_gain: float = 1.0
    trigger_shift_clack_gain: float = 1.0
    trigger_shift_torque_cut_gain: float = 1.0
    trigger_shift_tail_gain: float = 1.0
    trigger_wheelspin_gain: float = 1.0
    trigger_abs_gain: float = 1.0
    abs_strength: float = 1.0
    abs_hold_ms: float = 75.0
    rev_limiter_strength: float = 1.0
    # Engine enhancement - trigger effects
    enable_trigger_redline_pulse: bool = True     # R2 레드라인 경고 펄스
    trigger_redline_strength: float = 1.0
    redline_warning_width: float = 0.08           # usable RPM range 대비 경고 구간 폭
    enable_trigger_engine_brake: bool = False      # L2 엔진 브레이킹 저항 (기본 OFF: 급브레이크 방해)
    trigger_engine_brake_strength: float = 0.7
    adaptive_acceleration_depth: float = 0.30
    suspension_bump_strength: float = 0.80    # was 0.55; bumps were barely felt
    suspension_bump_sensitivity: float = 1.0
    r2_effect_priority_mode: str = "balanced"  # balanced / clean / texture / grip
    adjustment_mode: str = "quick"             # quick / detail; Settings tab edit mode
    enable_trigger_info_log: bool = False     # print current L2/R2 effect to the INFO log on changes

    # MARK: L2 brake resistance
    # Rigid curve: 0..wall_engage_at maps baseline..max_force, then firmware wall at 100%.
    enable_brake_resistance: bool = True      # enabled by default for tactile brake feel
    trigger_brake_gain: float = 0.85          # L2 brake-specific gain (separate from R2 pedal_gain)
    brake_deadzone: int = 50                  # ignore pedal below this byte
    brake_baseline_force: int = 0             # zero at start (v1.0 had resistance OFF; we emulate with 0 baseline)
    brake_max_force: int = 4                  # soft peak force 0-7 range (v1.0 was OFF entirely)
    brake_curve: float = 3.5                  # steep curve like v1.0(5.0): almost no resistance until deep press
    brake_wall_engage_at: int = 250           # byte that triggers firmware wall. DO NOT CHANGE
    brake_wall_release_at: int = 200          # hysteresis exit byte. DO NOT CHANGE
    enable_brake_static_wall: bool = False    # optional fixed wall mid-travel
    brake_static_wall_at: int = 128           # pedal byte where the static wall sits
    brake_static_wall_force: int = 255        # static wall strength

    # MARK: L2 handbrake bonus
    enable_handbrake_bonus: bool = False
    handbrake_bonus: int = 60                 # flat extra force while handbrake is engaged

    # MARK: L2 ABS pulse
    # Vibrates when tire slip crosses thresholds under hard braking.
    enable_abs: bool = True
    abs_brake_threshold: int = 80             # min brake byte to arm
    abs_min_speed_kmh: float = 15.0           # min speed to arm
    abs_slip_ratio_threshold: float = 1.0     # per-wheel slip trigger
    abs_combined_slip_threshold: float = 1.0  # combined slip trigger
    abs_freq: int = 18                        # pulse frequency (was 10; too low = inaudible tick)
    abs_amp: int = 62                         # base amp (baked-in: was 40 × old gain 1.56)

    # MARK: L2 road texture
    # Adds weak left-side road/kerb/puddle texture when not braking.
    enable_left_road_texture: bool = False

    # MARK: R2 throttle resistance
    # Light rigid curve: 0..wall_engage_at maps baseline..max_force, then firmware wall at 100%.
    enable_throttle_resistance: bool = True   # enabled by default for tactile throttle feel
    accel_deadzone: int = 50                  # ignore pedal below this byte
    throttle_baseline_force: int = 1          # minimal at start (v1.0 was 1; light touch)
    throttle_max_force: int = 8               # moderate peak (v1.0 was 8; keeps R2 controllable)
    throttle_curve: float = 3.8               # steep like v1.0(5.0): soft early, firm only near full travel
    throttle_wall_engage_at: int = 250        # byte that triggers firmware wall. DO NOT CHANGE
    throttle_wall_release_at: int = 200       # hysteresis exit byte. DO NOT CHANGE

    # MARK: R2 rev limiter
    # Vibrates when rpm/max_rpm exceeds the ratio; brief hold smooths rpm bounce.
    enable_rev_limiter: bool = True
    enable_rev_limiter_pattern: bool = False  # experimental chopped limiter pattern
    rev_limit_ratio: float = 0.93             # fraction of max_rpm to fire at
    rev_limit_freq: int = 30                  # distinct from gravel/dirt drift (15/45 Hz)
    rev_limit_amp: int = 50                   # base amp (was 12→30→50; need 50+ for strength 3-4/8 after gain)
    rev_limit_hold_ms: float = 120.0          # min on-time per trigger

    # MARK: R2 wheelspin buzz
    # `wheelspin_amp` is the tarmac reference. Off-road / water amps scale off it
    # (water 0.5x, dirt 1.5x, gravel 2x). Surface freqs are fixed in code.
    enable_wheelspin_buzz: bool = True
    wheelspin_amp: int = 27                   # base amp (baked-in: was 15 × old gain ~1.8)
    enable_right_road_texture: bool = True    # R2 road texture enabled for constant driving feel
    enable_trigger_positioned_vibration: bool = True   # gear/load-dependent vibration zones
    enable_tire_scrub_buzz: bool = True        # lateral tire scrub buzz for grip information
    # Trigger bump is now fused into L2/R2 road texture; kept hidden for old profile compatibility.
    enable_suspension_bump_buzz: bool = True


    # MARK: DualSense haptic audio
    # Direct audio-haptic output path. Requires USB DualSense exposed
    # as a 4-channel Windows audio output device.
    enable_haptic_audio: bool = True
    enable_haptic_audio_log: bool = False
    # User-facing coarse haptic switches. The detailed material/event gains stay
    # internal so the controller tab does not become a debug board.
    haptic_idle_haptics_enabled: bool = True
    haptic_surface_texture_enabled: bool = True
    haptic_special_events_enabled: bool = True
    haptic_vehicle_flavor_enabled: bool = True
    haptic_spatial_haptics_enabled: bool = True
    haptic_device_name: str = ""
    haptic_left_channel: int = 3              # 1-based output channel; default: ch3
    haptic_right_channel: int = 4             # 1-based output channel; default: ch4
    haptic_sample_rate: int = 48000
    haptic_buffer_ms: int = 10
    # Extra internal scale for Forza telemetry-driven haptics. Keep master gain user-friendly.
    haptic_signal_boost: float = 1.25
    haptic_road_enabled: bool = False
    haptic_kerb_enabled: bool = True
    haptic_gravel_enabled: bool = True
    haptic_puddle_enabled: bool = True
    haptic_wheelspin_enabled: bool = False
    haptic_scrub_enabled: bool = False
    haptic_bump_enabled: bool = True
    haptic_collision_enabled: bool = True
    haptic_weight_transfer_enabled: bool = False
    haptic_asphalt_grip_enabled: bool = False
    haptic_slide_body_enabled: bool = False
    haptic_idle_engine_enabled: bool = True
    haptic_launch_load_enabled: bool = True
    haptic_road_gain: float = 0.24
    haptic_kerb_gain: float = 0.62
    haptic_gravel_gain: float = 0.5
    haptic_puddle_gain: float = 0.68
    haptic_wheelspin_gain: float = 0.42
    haptic_scrub_gain: float = 0.42
    haptic_bump_gain: float = 0.58
    haptic_collision_gain: float = 0.72
    haptic_impact_master_gain: float = 1.0

    # 2.0 SimHub/music-style haptic mixer. 1.0 = neutral.
    # Low/mid/high are separate instrument bands; glue blends bands,
    # punch lets shifts/impacts/bumps cut through the texture.
    haptic_bass_foundation_gain: float = 1.0
    haptic_sub_bass_boost: float = 0.18
    haptic_high_edge_gain: float = 1.0
    haptic_high_shimmer_ratio: float = 0.15
    haptic_high_shimmer_cap: float = 0.2
    haptic_mid_texture_balance: float = 1.0
    haptic_spectrum_glue_gain: float = 1.0
    haptic_low_mid_glue_strength: float = 0.46
    haptic_high_mid_glue_strength: float = 0.38
    haptic_event_punch_gain: float = 1.00
    haptic_low_impact_gain: float = 1.00
    haptic_high_impact_gain: float = 1.00
    haptic_mid_duck_on_punch: float = 0.38
    haptic_mid_protect_enabled: bool = True
    haptic_mid_min_gain: float = 0.62              # minimum road-mid gain during punch/duck
    haptic_punch_to_mid_limit: float = 55.0        # guardrail; higher = punch allowed to dominate more
    haptic_event_ratio_trim: float = 0.08          # only used above punch_to_mid_limit
    haptic_punch_sustain_blend: float = 0.42       # held telemetry blended after one-shot edge
    haptic_mastering_enabled: bool = True
    haptic_mastering_sidechain_strength: float = 0.1
    haptic_mastering_soft_saturation: float = 0.08
    haptic_duck_attack_ms: float = 8.0
    haptic_duck_release_ms: float = 110.0
    # Keeps adaptive trigger events and audio haptics complementary.
    # Higher values make haptic shift/impact support the trigger with body
    # instead of duplicating the trigger click too hard in the high band.
    haptic_trigger_harmony_gain: float = 1.00
    haptic_engine_bass_strength: float = 0.42
    haptic_high_speed_bass_strength: float = 0.22
    haptic_bump_sub_strength: float = 0.52
    haptic_impact_sub_strength: float = 0.62
    haptic_impact_crack_high_strength: float = 0.6
    haptic_shift_bass_strength: float = 0.7
    haptic_shift_high_click_strength: float = 0.70
    haptic_rear_breakaway_low_strength: float = 0.62
    haptic_grip_edge_high_strength: float = 0.62
    haptic_wheelspin_edge_high_strength: float = 0.52
    haptic_brake_edge_high_strength: float = 0.48

    # 1.0 Final trigger companion controls.
    trigger_pedal_base_gain: float = 1.0
    trigger_grip_chatter_gain: float = 1.0
    trigger_impact_snap_gain: float = 1.0

    # Advanced haptic shaping. 1.0 = default where applicable.
    haptic_priority_mode: str = "balanced"       # balanced / texture / rally / grip / cinematic / clean
    haptic_spatial_width: float = 1.35             # L/R spread; 0=centered, 1=normal, 1.5=wide
    haptic_front_rear_contrast: float = 0.65      # front sharp vs rear low contrast
    haptic_trigger_ducking: float = 0.55          # reduce overlapping haptics when trigger already owns the signal
    haptic_kerb_hold_ms: float = 70.0
    haptic_gravel_release_ms: float = 170.0
    haptic_puddle_burst_ms: float = 105.0
    haptic_bump_decay_ms: float = 150.0
    haptic_collision_decay_ms: float = 180.0

    # Final haptic polish / safety.
    haptic_limiter_strength: float = 0.62        # stronger = less clipping when layers stack
    haptic_fatigue_control: float = 0.32         # reduces long continuous output; 0=off
    haptic_max_continuous_output: float = 0.62   # target continuous peak before fatigue gain starts
    haptic_freq_low_hz: float = 56.0             # lower end for body thumps / rear-wheel texture
    haptic_freq_high_hz: float = 420.0           # upper end for sharp tire edge / crack texture
    # Absolute DualSense tuning anchors. 0/negative falls back to the global low/high range.
    haptic_freq_road_texture_hz: float = 232.0
    haptic_freq_rough_road_hz: float = 305.0
    haptic_freq_kerb_front_hz: float = 348.0
    haptic_freq_kerb_rear_hz: float = 168.0
    haptic_freq_gravel_hz: float = 118.0
    haptic_freq_low_mid_glue_hz: float = 128.0
    haptic_freq_high_mid_glue_hz: float = 298.0
    haptic_freq_shift_body_hz: float = 76.0
    haptic_freq_impact_body_hz: float = 64.0
    haptic_freq_impact_crack_hz: float = 455.0
    haptic_freq_punch_body_hz: float = 68.0
    haptic_freq_punch_edge_hz: float = 430.0
    haptic_sharpness: float = 1.20               # 1=neutral, higher pushes textures sharper
    haptic_event_floor: float = 0.20             # minimum output when a real event is detected
    haptic_collision_direction_strength: float = 0.65
    haptic_puddle_tail_strength: float = 0.55
    haptic_bump_sequence_strength: float = 0.65
    haptic_grip_assist_strength: float = 0.55    # haptic wheelspin/scrub assist; triggers remain primary

    # Asphalt / lateral load / engine-load haptics.
    haptic_asphalt_speed_scale: float = 1.0      # speed contribution for subtle asphalt texture
    haptic_lateral_g_strength: float = 0.55      # weight-transfer body haptics
    haptic_lateral_g_threshold: float = 0.22     # G threshold before weight transfer starts
    haptic_lateral_g_sharpness: float = 1.20     # higher = sharper rise near tire load
    haptic_lateral_g_invert: bool = False        # flip left/right if car telemetry feels reversed
    haptic_surface_ducking: float = 0.78         # event layers duck continuous road/gravel
    haptic_gravel_background_strength: float = 0.34  # lower = less constant offroad masking
    haptic_puddle_priority: float = 0.90         # stronger puddle burst over offroad
    haptic_asphalt_grip_strength: float = 0.75   # asphalt slip + lateral-G grip texture
    haptic_slide_body_strength: float = 0.55     # lateral velocity / yaw body slide feel
    haptic_drift_snap_strength: float = 0.50     # quick left/right load transition pulse
    # 6.2: when the car is genuinely sliding/drifting, the pad should stop being polite.
    # These cues sit above surface texture and create the "car is breaking away" feel.
    haptic_slide_chaos_strength: float = 0.74
    haptic_drift_breakaway_strength: float = 0.72
    haptic_side_scrub_edge_strength: float = 0.62
    haptic_drift_surface_duck_strength: float = 0.55
    haptic_drift_side_bias: float = 0.82          # higher = drift can approach 9:1 side split
    # 6.3 tire-slip and surface-specific drift: tire scrub must feel different
    # from body chaos, and asphalt/offroad drifting should not share one texture.
    haptic_tire_scrub_texture_strength: float = 0.64
    haptic_tire_smear_strength: float = 0.52
    haptic_slip_sizzle_strength: float = 0.5
    haptic_asphalt_drift_strength: float = 0.68
    haptic_offroad_drift_strength: float = 0.66
    haptic_spatial_depth_gain: float = 1.00
    haptic_rear_echo_gain: float = 1.00
    haptic_shift_master_gain: float = 1.0
    haptic_shift_click_strength: float = 0.9
    haptic_shift_clunk_strength: float = 0.9
    haptic_shift_rattle_strength: float = 0.62
    haptic_shift_reverb_strength: float = 0.36
    haptic_shift_torque_cut_strength: float = 0.52
    haptic_shift_engagement_strength: float = 0.65   # NEW: 변속 후 토크 전달 충격
    haptic_transient_limiter_relief: float = 0.45
    haptic_velocity_x_strength: float = 0.55     # side velocity contribution
    haptic_yaw_rate_strength: float = 0.45       # yaw-rate contribution
    # Longitudinal G-force onset (가속/감속 시작 순간 충격)
    haptic_accel_onset_strength: float = 0.55    # NEW: 급가속 시작 충격
    haptic_decel_onset_strength: float = 0.50    # NEW: 급감속 시작 충격
    # Engine enhancement (6 features)
    haptic_rpm_harmonics_strength: float = 0.45  # 실린더 배음 (4/6/8기통 느낌)
    haptic_redline_warning_strength: float = 0.65 # 레드라인 펄스 경고
    haptic_redline_warning_width: float = 0.08     # 햅틱 레드라인 경고 구간 폭 (usable RPM range 비례)
    haptic_turbo_spool_strength: float = 0.40    # 터보 빌드업 고주파 휘슬
    haptic_engine_braking_strength: float = 0.50 # 엔진 브레이킹 저항감
    haptic_corner_exit_strength: float = 0.55    # 코너 출구 파워온 토크
    haptic_engine_start_strength: float = 0.70   # 시동 시퀀스
    haptic_idle_strength: float = 0.34           # low engine shake at idle / muscle cars
    haptic_idle_roughness: float = 0.45
    haptic_idle_torque_scale: float = 0.65
    haptic_launch_strength: float = 0.55         # brake+throttle launch load
    haptic_launch_roughness: float = 0.65
    haptic_launch_threshold: float = 0.40
    haptic_launch_release_thump: float = 0.55

    # Telemetry-exhaust / texture palette haptics. These keep triggers frozen and
    # make the body haptics more varied: surface classification, front→rear
    # event echoes, scrape/crack, boost/torque surge and shift body kick.
    haptic_surface_palette_enabled: bool = True
    haptic_surface_classifier_strength: float = 1.0
    haptic_texture_palette_strength: float = 1.0
    haptic_event_transient_strength: float = 1.00
    haptic_front_rear_event_queue_enabled: bool = True
    haptic_rear_echo_strength: float = 0.65
    haptic_rough_asphalt_strength: float = 0.55
    haptic_dirt_strength: float = 0.48
    haptic_grass_strength: float = 0.38
    haptic_scrape_enabled: bool = True
    haptic_scrape_strength: float = 0.62
    haptic_collision_crack_strength: float = 0.65
    haptic_boost_build_enabled: bool = True
    haptic_boost_strength: float = 0.42
    haptic_torque_surge_strength: float = 0.45
    haptic_shift_body_kick_enabled: bool = False
    haptic_shift_body_kick_strength: float = 0.82

    # Weather / wet-surface haptics. Forza Data Out does not expose a direct
    # weather enum here, so this is inferred from puddles + low-grip behavior.
    haptic_weather_wetness_enabled: bool = True
    haptic_weather_wetness_strength: float = 0.75
    haptic_wet_asphalt_strength: float = 0.55
    haptic_mud_strength: float = 0.45
    haptic_spray_strength: float = 0.40

    # Low-grip / seasonal surface haptics. These are inferred from roughness,
    # slip, puddle duration and suspension behavior: no direct snow/ice enum exists.
    haptic_low_grip_surfaces_enabled: bool = True
    haptic_water_detail_enabled: bool = True
    haptic_ice_strength: float = 0.42
    haptic_packed_snow_strength: float = 0.50
    haptic_loose_snow_strength: float = 0.48
    haptic_slush_strength: float = 0.52
    haptic_sand_strength: float = 0.46
    haptic_thin_water_strength: float = 0.34
    haptic_deep_water_strength: float = 0.58
    haptic_wet_tire_tail_strength: float = 0.36
    haptic_surface_transition_strength: float = 0.42

    # Vehicle dynamics haptic supplement. Triggers keep pedal/traction ownership;
    # these are body cues: understeer, oversteer, landing and bottom-out.
    haptic_vehicle_dynamics_enabled: bool = True
    haptic_understeer_strength: float = 0.34
    haptic_oversteer_strength: float = 0.40
    haptic_four_wheel_slide_strength: float = 0.30
    haptic_landing_strength: float = 0.58
    haptic_bottom_out_strength: float = 0.66

    # ═══════════════════════════════════════════════════════════════════════════
    # 4-LAYER GAIN STACK (SimHub 스타일)
    # Final = Master × Bus × Source × PerChannel
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Layer 1: MASTER (전체 볼륨)
    haptic_master_gain: float = 1.0
    
    # Layer 2: BUS (4개 버스)
    haptic_surface_bus_gain: float = 0.52    # 🛣️ 노면 (road, gravel, weather)
    haptic_vehicle_bus_gain: float = 0.72    # 🏎️ 차체 (slide, weight)
    haptic_engine_bus_gain: float = 0.65     # ⚙️ 엔진 (idle, rpm, boost)
    haptic_event_bus_gain: float = 0.84      # 💥 이벤트 (collision, shift)
    
    # Layer 4: PER-CHANNEL (L/R 밸런스)
    haptic_balance_lr: float = 0.0           # -1.0 = Left only, +1.0 = Right only
    
    # Layer 3: SOURCE는 각 소스별 개별 설정 (haptic_*_gain, haptic_*_strength 등)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Spatial/stereo settings
    haptic_side_crossfeed: float = 0.12           # delayed opposite-side echo; lower = wider L/R
    haptic_side_event_delay_ms: float = 22.0      # timing offset that makes side hits readable
    haptic_side_grip_separation: float = 1.35     # stronger L/R split for lateral-G and grip limit
    haptic_final_side_boost: float = 0.35         # final mid/side widener; keeps L/R cues from collapsing
    haptic_center_duck_strength: float = 0.46     # duck centered body layers when side cues are active
    haptic_side_vehicle_crossfeed: float = 0.055  # very light delayed echo for side vehicle/body cues
    haptic_side_vehicle_delay_ms: float = 20.0
    haptic_lateral_g_source: str = "accel_x"     # hidden diagnostic: accel_x / accel_y / accel_z

    # Surface classifier stability. Hidden/internal: keeps dry asphalt slides from
    # being misread as ice and prevents rapid surface-transition chatter.
    haptic_ice_classifier_strength: float = 0.62
    haptic_ice_min_speed_kmh: float = 40.0
    haptic_surface_transition_min_hold_ms: float = 380.0
    haptic_surface_transition_cooldown_ms: float = 550.0
    haptic_surface_transition_conf_delta: float = 0.14
    # 6.1 polish: keep high-speed road detail, but stop low-speed offroad
    # texture from becoming cart-like; impact duck separates crashes from texture.
    haptic_low_speed_surface_start_kmh: float = 10.0
    haptic_low_speed_surface_full_kmh: float = 115.0
    haptic_low_speed_offroad_bias: float = 0.82
    haptic_collision_duck_strength: float = 0.88
    haptic_collision_duck_min: float = 0.06

    # Optional haptic telemetry recorder for repeatable tuning. Off by default
    # because it writes JSONL while driving.
    haptic_telemetry_recording_enabled: bool = False
    haptic_telemetry_record_hz: float = 20.0
    haptic_telemetry_record_path: str = "data/haptic_telemetry_record.jsonl"

    # Trigger/haptic coordination and brake body supplement. Triggers keep pedal
    # traction/ABS ownership; haptics add body/space only.
    haptic_trigger_haptic_coordination_strength: float = 0.70
    haptic_brake_body_enabled: bool = False
    haptic_brake_body_strength: float = 0.42
    haptic_abs_body_strength: float = 0.32

    # MARK: extended telemetry layers
    # New haptic layers driven by previously unused telemetry fields.
    # Enabled by default; gains are the tuned optimal values (100% baseline).
    haptic_rpm_texture_enabled: bool = True
    haptic_rpm_texture_gain: float = 0.5
    haptic_body_motion_enabled: bool = False  # 기본 OFF: 피칭/롤 저음이 타이어 피드백을 마스킹
    haptic_body_motion_gain: float = 0.45
    haptic_traction_pulse_enabled: bool = True
    haptic_traction_pulse_gain: float = 0.4


    # MARK: R2 idle buzz
    # Engine-idle oscillation while stopped and accelerator pressed under ~25%.
    # Single chug pattern: vibrate amp toggles between low and high every half-period.
    enable_idle_buzz: bool = True
    idle_max_speed_kmh: float = 5.0           # only while car is essentially stopped
    idle_accel_max: int = 64                  # upper byte (~25% of 255): idle fades out past this press
    idle_freq: int = 30                       # base vibrate Hz
    idle_amp_low: int = 1                     # quiet half of the cycle
    idle_amp_high: int = 30                  # loud half of the cycle
    idle_period_s: float = 0.5                # full cycle length (sec)

    # MARK: Gear shift
    # One short burst on up/downshift while moving.
    enable_gear_shift: bool = True            # buzz on R2
    enable_gear_shift_brake: bool = True      # also buzz on L2 via the wall
    gear_shift_freq: int = 10
    gear_shift_amp: int = 255
    gear_shift_duration_ms: float = 100.0     # burst length

    # MARK: System - startup pulse
    enable_startup_pulse: bool = True
    startup_pulse_force: int = 150            # one-shot force test on connect

    # MARK: System - reconnect
    # Off by default for HidHide compatibility. On = USB unplug/replug recovers without restart.
    enable_reconnect: bool = False
    reconnect_interval_s: float = 5.0         # retry cadence when disconnected

    # MARK: System - controller selection
    # Lock to a specific DualSense by serial. Empty = auto (first found).
    # Soft lock: falls back to first-found if the locked one is missing.
    # USB and BT report different serials for the same controller.
    controller_lock_serial: str = ""

    # MARK: System - updates
    check_for_updates: bool = False           # legacy hidden setting; update UI removed


    # MARK: System - language
    # Module name in `lang/` (en, ko, tr, zh, zh_tw, ja). Unknown codes fall back to English.
    language: str = "ko"
    developer_mode: bool = False
    diagnostic_capture_seconds: int = 30
    diagnostic_target_size_mb: int = 5
    diagnostic_max_size_mb: int = 10
    diagnostic_sample_hz: int = 20

    # MARK: System - auto exit
    # Closes when the game process disappears; telemetry-lost is a fallback for Task Manager kills.
    exit_on_game_close: bool = True
    game_process_name_contains: tuple = ("forza",)   # substring match, case-insensitive
    game_poll_interval_s: float = 2.0                # psutil scan cadence
    telemetry_lost_exit_s: float = 60.0              # quit if no packets for this long after first packet

    # =========================================================================
    # Nested settings instances (for organized access)
    # =========================================================================
    # These are initialized via field(default_factory=...) to avoid mutable defaults
    # Access: settings.udp.port or settings.udp_port (both work)
    udp: UDPSettings = field(default_factory=UDPSettings)
    trigger: TriggerSettings = field(default_factory=TriggerSettings)
    brake: BrakeSettings = field(default_factory=BrakeSettings)
    throttle: ThrottleSettings = field(default_factory=ThrottleSettings)
    haptic_audio: HapticAudioSettings = field(default_factory=HapticAudioSettings)
    haptic_mixer: HapticMixerSettings = field(default_factory=HapticMixerSettings)
    system: SystemSettings = field(default_factory=SystemSettings)
