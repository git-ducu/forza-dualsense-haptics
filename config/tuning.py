# -*- coding: utf-8 -*-
# ── Tuning parameters — camelCase hierarchical structure ────────────────────
#
# This replaces the flat Settings class with typed, nested dataclasses.
# All field names use camelCase (C++ dev style, distinct from original).
# The JSON schema matches these field names exactly.

from __future__ import annotations
from dataclasses import dataclass, field


PEDAL_RAW_MAX = 255  # firmware pedal byte ceiling


@dataclass(slots=True)
class NetworkTuning:
    bindAddress: str = "127.0.0.1"
    listenPort: int = 5300
    socketTimeout: float = 0.5
    enableRelay: bool = False
    relayTargets: str = "127.0.0.1:5301"


@dataclass(slots=True)
class BrakeTuning:
    # L2 resistance curve
    enableResistance: bool = True
    l2DeadZone: int = 50
    l2BaselineForce: int = 0
    l2PeakResistance: int = 4
    l2CurveExponent: float = 3.5
    l2WallEngage: int = 250
    l2WallRelease: int = 200
    # static wall (optional mid-travel hard stop)
    enableStaticWall: bool = False
    staticWallPosition: int = 128
    staticWallForce: int = 255
    # handbrake
    enableHandbrakeBonus: bool = False
    handbrakeBonus: int = 60
    # ABS pulse
    enableAbsPulse: bool = True
    absBrakeThreshold: int = 80
    absMinSpeedKmh: float = 15.0
    absSlipRatioThreshold: float = 1.0
    absCombinedSlipThreshold: float = 1.0
    absPulseFreq: int = 18
    absPulseAmplitude: int = 62
    absBaseFreq: int = 18
    absBaseAmp: int = 62
    absHoldMs: float = 75.0
    absStrength: float = 1.0
    # engine brake on L2
    enableEngineBrake: bool = True
    engineBrakeStrength: float = 0.5
    # brake gain multiplier
    brakeGain: float = 1.0
    # road texture on brake trigger
    enableRoadTexture: bool = False


@dataclass(slots=True)
class ThrottleTuning:
    # R2 resistance curve
    enableResistance: bool = True
    r2DeadZone: int = 50
    r2BaselineForce: int = 1
    r2PeakResistance: int = 8
    r2CurveExponent: float = 3.8
    r2WallEngage: int = 250
    r2WallRelease: int = 200
    # rev limiter
    enableRevLimiter: bool = True
    enableRevPattern: bool = False
    revLimiterThreshold: float = 0.93
    revLimiterFreq: int = 30
    revLimiterAmp: int = 50
    revLimiterBaseFreq: int = 30
    revLimiterBaseAmp: int = 50
    revLimiterHoldMs: float = 120.0
    revLimiterStrength: float = 1.0
    # redline pulse
    enableRedlinePulse: bool = True
    redlinePulseStrength: float = 1.0
    # wheelspin
    enableWheelSpin: bool = True
    wheelSpinBaseAmplitude: int = 27
    wheelSpinSlipThreshold: float = 0.5
    wheelSpinSaturation: float = 3.0
    enableRoadTexture: bool = True
    enablePositionedVibration: bool = True
    enableTireScrub: bool = True
    enableSuspensionBump: bool = True
    # idle feel
    enableIdleBuzz: bool = True
    idleMaxSpeedKmh: float = 5.0
    idleAccelMax: int = 64
    idleThrottleMax: int = 64
    idleFreq: int = 30
    idleAmpLow: int = 1
    idleAmpHigh: int = 30
    idlePeriod: float = 0.5
    idlePeriodSec: float = 0.5
    # gear shift
    enableGearShift: bool = True
    enableGearShiftBrake: bool = True
    shiftKickFreq: int = 10
    shiftKickAmplitude: int = 255
    shiftKickDurationMs: float = 100.0
    shiftClackGain: float = 1.0
    shiftTorqueCutGain: float = 1.0
    # positioning
    adaptiveDepth: float = 0.30
    suspensionBumpStrength: float = 0.80
    suspensionBumpSensitivity: float = 1.0
    priorityMode: str = "balanced"


@dataclass(slots=True)
class TriggerGainTuning:
    # master + per-side + per-role gains
    masterGain: float = 1.0
    l2Gain: float = 1.0
    r2Gain: float = 1.0
    shiftKickGain: float = 1.0
    wheelSpinGain: float = 1.0
    absGain: float = 1.0
    gripChatterGain: float = 1.0
    pedalBaseGain: float = 1.0
    # road texture sensitivity
    roadTextureStrength: float = 1.0
    leftRoadStrength: float = 0.75
    rightRoadStrength: float = 1.0
    wheelSpinSensitivity: float = 1.0
    wheelSpinHoldMs: float = 70.0
    tireScrubSensitivity: float = 2.0
    tireScrubRoadStrength: float = 1.0
    tireScrubOffroadStrength: float = 0.35
    tireScrubMaxForce: float = 0.80
    tireScrubHoldMs: float = 60.0
    # end-stop wall
    endStopDepth: int = 3


@dataclass(slots=True)
class HapticDeviceTuning:
    enabled: bool = False
    deviceName: str = ""
    leftChannel: int = 3
    rightChannel: int = 4
    sampleRate: int = 48000
    bufferMs: int = 10
    masterGain: float = 0.4
    signalBoost: float = 1.25


@dataclass(slots=True)
class HapticMixerTuning:
    # band gains
    bassFoundation: float = 1.0
    subBassBoost: float = 0.18
    highEdge: float = 1.0
    midTextureBalance: float = 1.0
    # glue
    spectrumGlue: float = 1.0
    lowMidGlue: float = 0.46
    highMidGlue: float = 0.38
    # punch
    eventPunch: float = 1.0
    midDuckOnPunch: float = 0.38
    midProtectEnabled: bool = True
    midMinGain: float = 0.62
    # mastering
    masteringEnabled: bool = True
    sidechainStrength: float = 0.1
    softSaturation: float = 0.08
    duckAttackMs: float = 8.0
    duckReleaseMs: float = 110.0


@dataclass(slots=True)
class HapticBusTuning:
    surfaceBusGain: float = 0.52
    vehicleBusGain: float = 0.72
    engineBusGain: float = 0.65
    eventBusGain: float = 0.84
    balanceLR: float = 0.0


@dataclass(slots=True)
class SystemTuning:
    enableStartupPulse: bool = True
    startupPulseForce: int = 150
    enableReconnect: bool = False
    reconnectInterval: float = 5.0
    controllerSerial: str = ""
    language: str = "ko"
    developerMode: bool = False
    exitOnGameClose: bool = True
    gameProcessFilter: str = "forza"
    gamePollInterval: float = 2.0
    telemetryLostTimeout: float = 60.0


@dataclass(slots=True)
class Tuning:
    """Top-level tuning container — one instance per profile."""
    network: NetworkTuning = field(default_factory=NetworkTuning)
    brake: BrakeTuning = field(default_factory=BrakeTuning)
    throttle: ThrottleTuning = field(default_factory=ThrottleTuning)
    triggerGain: TriggerGainTuning = field(default_factory=TriggerGainTuning)
    hapticDevice: HapticDeviceTuning = field(default_factory=HapticDeviceTuning)
    hapticMixer: HapticMixerTuning = field(default_factory=HapticMixerTuning)
    hapticBus: HapticBusTuning = field(default_factory=HapticBusTuning)
    system: SystemTuning = field(default_factory=SystemTuning)


# ── Flat-access aliases: triggerMap flat name -> (sub-object, real field name)
_TUNING_ALIASES: dict[str, tuple[str, str]] = {
    "enableAbs": ("brake", "enableAbsPulse"),
    "enableBrakeResistance": ("brake", "enableResistance"),
    "enableThrottleResistance": ("throttle", "enableResistance"),
    "enableRevLimiterPattern": ("throttle", "enableRevPattern"),
    "enableIdleFeel": ("throttle", "enableIdleBuzz"),
}

# Sub-objects to search (ordered by likelihood of hit)
_TUNING_SUBS = ("brake", "throttle", "triggerGain", "network",
                "hapticDevice", "hapticMixer", "hapticBus", "system")


def _tuning_getattr(self, name: str):
    # 1) Check aliases
    alias = _TUNING_ALIASES.get(name)
    if alias:
        sub, real = alias
        return getattr(object.__getattribute__(self, sub), real)
    # 2) Search nested sub-objects
    for sub in _TUNING_SUBS:
        obj = object.__getattribute__(self, sub)
        if hasattr(type(obj), name):
            return getattr(obj, name)
    raise AttributeError(f"Tuning has no attribute {name!r}")


Tuning.__getattr__ = _tuning_getattr  # type: ignore[attr-defined]


# ── Settings → Tuning sync ───────────────────────────────────────────────────
# Bridges the flat Settings dataclass (user-facing, snake_case) into
# the nested Tuning hierarchy (engine-facing, camelCase).

def sync_tuning_from_settings(tuning: Tuning, s) -> None:
    """Update a Tuning instance from the live Settings object.

    Call this once at init and periodically (e.g. every frame or every second)
    so runtime picks up UI changes without restart.
    """
    b = tuning.brake
    th = tuning.throttle
    tg = tuning.triggerGain

    # ── Brake (L2) ──────────────────────────────────────────────────────────
    b.enableResistance = bool(getattr(s, "enable_brake_resistance", b.enableResistance))
    b.l2DeadZone = int(getattr(s, "brake_deadzone", b.l2DeadZone))
    b.l2BaselineForce = int(getattr(s, "brake_baseline_force", b.l2BaselineForce))
    b.l2PeakResistance = int(getattr(s, "brake_max_force", b.l2PeakResistance))
    b.l2CurveExponent = float(getattr(s, "brake_curve", b.l2CurveExponent))
    b.l2WallEngage = int(getattr(s, "brake_wall_engage_at", b.l2WallEngage))
    b.l2WallRelease = int(getattr(s, "brake_wall_release_at", b.l2WallRelease))
    b.enableStaticWall = bool(getattr(s, "enable_brake_static_wall", b.enableStaticWall))
    b.staticWallPosition = int(getattr(s, "brake_static_wall_at", b.staticWallPosition))
    b.staticWallForce = int(getattr(s, "brake_static_wall_force", b.staticWallForce))
    b.enableHandbrakeBonus = bool(getattr(s, "enable_handbrake_bonus", b.enableHandbrakeBonus))
    b.handbrakeBonus = int(getattr(s, "handbrake_bonus", b.handbrakeBonus))
    b.enableAbsPulse = bool(getattr(s, "enable_abs", b.enableAbsPulse))
    b.absBrakeThreshold = int(getattr(s, "abs_brake_threshold", b.absBrakeThreshold))
    b.absMinSpeedKmh = float(getattr(s, "abs_min_speed_kmh", b.absMinSpeedKmh))
    b.absSlipRatioThreshold = float(getattr(s, "abs_slip_ratio_threshold", b.absSlipRatioThreshold))
    b.absCombinedSlipThreshold = float(getattr(s, "abs_combined_slip_threshold", b.absCombinedSlipThreshold))
    b.absBaseFreq = int(getattr(s, "abs_freq", b.absBaseFreq))
    b.absPulseFreq = b.absBaseFreq
    b.absBaseAmp = int(getattr(s, "abs_amp", b.absBaseAmp))
    b.absPulseAmplitude = b.absBaseAmp
    b.absHoldMs = float(getattr(s, "abs_hold_ms", b.absHoldMs))
    b.absStrength = float(getattr(s, "abs_strength", b.absStrength))
    b.enableEngineBrake = bool(getattr(s, "enable_trigger_engine_brake", b.enableEngineBrake))
    b.engineBrakeStrength = float(getattr(s, "trigger_engine_brake_strength", b.engineBrakeStrength))
    b.brakeGain = float(getattr(s, "trigger_brake_gain", b.brakeGain))
    b.enableRoadTexture = bool(getattr(s, "enable_left_road_texture", b.enableRoadTexture))

    # ── Throttle (R2) ───────────────────────────────────────────────────────
    th.enableResistance = bool(getattr(s, "enable_throttle_resistance", th.enableResistance))
    th.r2DeadZone = int(getattr(s, "accel_deadzone", th.r2DeadZone))
    th.r2BaselineForce = int(getattr(s, "throttle_baseline_force", th.r2BaselineForce))
    th.r2PeakResistance = int(getattr(s, "throttle_max_force", th.r2PeakResistance))
    th.r2CurveExponent = float(getattr(s, "throttle_curve", th.r2CurveExponent))
    th.r2WallEngage = int(getattr(s, "throttle_wall_engage_at", th.r2WallEngage))
    th.r2WallRelease = int(getattr(s, "throttle_wall_release_at", th.r2WallRelease))
    th.enableRevLimiter = bool(getattr(s, "enable_rev_limiter", th.enableRevLimiter))
    th.enableRevPattern = bool(getattr(s, "enable_rev_limiter_pattern", th.enableRevPattern))
    th.revLimiterThreshold = float(getattr(s, "rev_limit_ratio", th.revLimiterThreshold))
    th.revLimiterFreq = int(getattr(s, "rev_limit_freq", th.revLimiterFreq))
    th.revLimiterBaseFreq = th.revLimiterFreq
    th.revLimiterAmp = int(getattr(s, "rev_limit_amp", th.revLimiterAmp))
    th.revLimiterBaseAmp = th.revLimiterAmp
    th.revLimiterHoldMs = float(getattr(s, "rev_limit_hold_ms", th.revLimiterHoldMs))
    th.revLimiterStrength = float(getattr(s, "rev_limiter_strength", th.revLimiterStrength))
    th.enableRedlinePulse = bool(getattr(s, "enable_trigger_redline_pulse", th.enableRedlinePulse))
    th.redlinePulseStrength = float(getattr(s, "trigger_redline_strength", th.redlinePulseStrength))
    th.enableWheelSpin = bool(getattr(s, "enable_wheelspin_buzz", th.enableWheelSpin))
    th.wheelSpinBaseAmplitude = int(getattr(s, "wheelspin_amp", th.wheelSpinBaseAmplitude))
    th.enableRoadTexture = bool(getattr(s, "enable_right_road_texture", th.enableRoadTexture))
    th.enablePositionedVibration = bool(getattr(s, "enable_trigger_positioned_vibration", th.enablePositionedVibration))
    th.enableTireScrub = bool(getattr(s, "enable_tire_scrub_buzz", th.enableTireScrub))
    th.enableSuspensionBump = bool(getattr(s, "enable_suspension_bump_buzz", th.enableSuspensionBump))
    th.enableIdleBuzz = bool(getattr(s, "enable_idle_buzz", th.enableIdleBuzz))
    th.idleMaxSpeedKmh = float(getattr(s, "idle_max_speed_kmh", th.idleMaxSpeedKmh))
    th.idleAccelMax = int(getattr(s, "idle_accel_max", th.idleAccelMax))
    th.idleThrottleMax = int(getattr(s, "idle_accel_max", th.idleThrottleMax))
    th.idleFreq = int(getattr(s, "idle_freq", th.idleFreq))
    th.idleAmpLow = int(getattr(s, "idle_amp_low", th.idleAmpLow))
    th.idleAmpHigh = int(getattr(s, "idle_amp_high", th.idleAmpHigh))
    th.idlePeriod = float(getattr(s, "idle_period_s", th.idlePeriod))
    th.idlePeriodSec = th.idlePeriod
    th.enableGearShift = bool(getattr(s, "enable_gear_shift", th.enableGearShift))
    th.enableGearShiftBrake = bool(getattr(s, "enable_gear_shift_brake", th.enableGearShiftBrake))
    th.shiftKickFreq = int(getattr(s, "gear_shift_freq", th.shiftKickFreq))
    th.shiftKickAmplitude = int(getattr(s, "gear_shift_amp", th.shiftKickAmplitude))
    th.shiftKickDurationMs = float(getattr(s, "gear_shift_duration_ms", th.shiftKickDurationMs))
    th.shiftClackGain = float(getattr(s, "trigger_shift_clack_gain", th.shiftClackGain))
    th.shiftTorqueCutGain = float(getattr(s, "trigger_shift_torque_cut_gain", th.shiftTorqueCutGain))
    th.adaptiveDepth = float(getattr(s, "adaptive_acceleration_depth", th.adaptiveDepth))
    th.suspensionBumpStrength = float(getattr(s, "suspension_bump_strength", th.suspensionBumpStrength))
    th.suspensionBumpSensitivity = float(getattr(s, "suspension_bump_sensitivity", th.suspensionBumpSensitivity))
    th.priorityMode = str(getattr(s, "r2_effect_priority_mode", th.priorityMode))

    # ── Trigger gains ───────────────────────────────────────────────────────
    tg.masterGain = float(getattr(s, "trigger_master_gain", tg.masterGain))
    tg.l2Gain = float(getattr(s, "trigger_l2_gain", tg.l2Gain))
    tg.r2Gain = float(getattr(s, "trigger_r2_gain", tg.r2Gain))
    tg.shiftKickGain = float(getattr(s, "trigger_shift_kick_gain", tg.shiftKickGain))
    tg.wheelSpinGain = float(getattr(s, "trigger_wheelspin_gain", tg.wheelSpinGain))
    tg.absGain = float(getattr(s, "trigger_abs_gain", tg.absGain))
    tg.gripChatterGain = float(getattr(s, "trigger_grip_chatter_gain", tg.gripChatterGain))
    tg.pedalBaseGain = float(getattr(s, "trigger_pedal_base_gain", tg.pedalBaseGain))
    tg.roadTextureStrength = float(getattr(s, "road_texture_strength", tg.roadTextureStrength))
    tg.leftRoadStrength = float(getattr(s, "left_road_strength", tg.leftRoadStrength))
    tg.rightRoadStrength = float(getattr(s, "right_road_strength", tg.rightRoadStrength))
    tg.wheelSpinSensitivity = float(getattr(s, "wheelspin_sensitivity", tg.wheelSpinSensitivity))
    tg.wheelSpinHoldMs = float(getattr(s, "wheelspin_hold_ms", tg.wheelSpinHoldMs))
    tg.tireScrubSensitivity = float(getattr(s, "tire_scrub_sensitivity", tg.tireScrubSensitivity))
    tg.tireScrubRoadStrength = float(getattr(s, "tire_scrub_road_strength", tg.tireScrubRoadStrength))
    tg.tireScrubOffroadStrength = float(getattr(s, "tire_scrub_offroad_strength", tg.tireScrubOffroadStrength))
    tg.tireScrubMaxForce = float(getattr(s, "tire_scrub_max_force", tg.tireScrubMaxForce))
    tg.tireScrubHoldMs = float(getattr(s, "tire_scrub_hold_ms", tg.tireScrubHoldMs))
    tg.endStopDepth = int(getattr(s, "wall_zones", tg.endStopDepth))
