# -*- coding: utf-8 -*-
# ── Adaptive trigger policy ────────────────────────────────────────────────
#
# Stateless functions mapping VehicleState → (left TriggerEffect, right TriggerEffect).
# Timing across frames is tracked in EffectMemory.
#
# Entry point: computeTriggerFrame(vs, mem, tuning, now) → TriggerFrame

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import NamedTuple

from dsio.trigger.effects import (
    TriggerEffect, clearEffect,
    buildSimpleResistance, buildZoneFeedback, buildZoneVibration,
    buildZoneVibrationFromPosition, buildSoftZoneVibration,
)
from .vehicle import VehicleState
from . import dhe_custom as _roadFx


# ── Output container ──────────────────────────────────────────────────────────

class TriggerFrame(NamedTuple):
    left: TriggerEffect       # L2 (brake pedal)
    right: TriggerEffect      # R2 (throttle pedal)
    leftLabel: str            # diagnostic tag
    rightLabel: str


# ── Timing / memory for effects that span frames ─────────────────────────────

@dataclass
class EffectMemory:
    # gear shift detection
    previousGear: int = 0
    shiftKickUntil: float = 0.0
    shiftStartedAt: float = 0.0
    shiftDirection: int = 0             # +1 up, -1 down
    shiftRpmNorm: float = 0.0
    shiftAccelNorm: float = 0.0
    shiftBrakeNorm: float = 0.0

    # rev limiter hold
    revHoldUntil: float = 0.0
    revPeakRpm: float = 0.0

    # ABS pulse hold
    absHoldUntil: float = 0.0
    absFrequency: int = 0
    absAmplitude: int = 0

    # engine braking hold
    engineBrakeUntil: float = 0.0

    # end-stop wall hysteresis
    l2WallLatched: bool = False
    r2WallLatched: bool = False

    # slip onset / grip recovery
    previousSlipRatio: float = 0.0
    slipPulseUntil: float = 0.0
    gripReleaseUntil: float = 0.0
    gripTextureUntil: float = 0.0


# ── Pedal math ────────────────────────────────────────────────────────────────

def applyPedalResistanceCurve(pedalValue: int, deadZone: int, baseline: float,
                              peak: float, exponent: float, ceiling: int) -> float:
    """Maps pedal range [deadZone..ceiling] → [baseline..peak] using a
    progressive two-stage curve: smoothstep onset blended with power shaping
    for a natural stiffening feel at higher travel."""
    if pedalValue < deadZone:
        return baseline
    span = max(ceiling - deadZone, 1)
    t = min(1.0, (pedalValue - deadZone) / span)
    # Power curve provides steep/shallow control via exponent
    power = t ** exponent
    # Smoothstep adds tactile engagement at low pedal travel
    smooth = t * t * (3.0 - 2.0 * t)
    # Blend: 92% power character, 8% smoothstep onset for feel
    shaped = 0.92 * power + 0.08 * smooth
    return baseline + (peak - baseline) * shaped


def checkWallLatchHysteresis(currentValue: int, isLatched: bool,
                             engageThreshold: int, releaseThreshold: int) -> bool:
    # Hysteresis: engage at >= engageThreshold, release at < releaseThreshold
    if isLatched:
        return currentValue >= releaseThreshold
    return currentValue >= engageThreshold


# ── Gear shift detection + effect ─────────────────────────────────────────────

def detectGearShift(vs: VehicleState, mem: EffectMemory, tuning, now: float):
    # Arm shift kick if a genuine adjacent gear change while moving
    gear = vs.currentGear
    if mem.previousGear != 0 and gear != mem.previousGear:
        isValidShift = (
            vs.speedKmh > 5.0
            and mem.previousGear > 0
            and gear > 0
            and abs(gear - mem.previousGear) <= 1
        )
        if isValidShift:
            mem.shiftDirection = 1 if gear > mem.previousGear else -1
            mem.shiftRpmNorm = vs.rpmRatio
            mem.shiftAccelNorm = min(1.0, vs.throttle / 255.0)
            mem.shiftBrakeNorm = min(1.0, vs.brake / 255.0)

            baseDuration = tuning.shiftKickDurationMs / 1000.0  # e.g. 140ms
            kickGainFactor = max(0.80, min(1.45, tuning.shiftKickGain))
            baseDuration *= kickGainFactor
            load = max(mem.shiftAccelNorm, mem.shiftRpmNorm)
            if mem.shiftDirection > 0:
                baseDuration *= 0.75 + 0.35 * load
            else:
                baseDuration *= 0.65 + 0.25 * max(mem.shiftBrakeNorm, mem.shiftRpmNorm)
            mem.shiftStartedAt = now
            mem.shiftKickUntil = now + max(0.055, min(0.190, baseDuration))
    mem.previousGear = gear


def produceShiftKickEffect(mem: EffectMemory, tuning, now: float,
                           sideGain: float = 1.0) -> TriggerEffect | None:
    # Produces a multi-phase rigid "clack" sequence during shift window
    if now >= mem.shiftKickUntil:
        return None
    if sideGain <= 0.0:
        return None

    elapsed = max(0.0, now - mem.shiftStartedAt)
    load = max(mem.shiftAccelNorm, mem.shiftBrakeNorm, mem.shiftRpmNorm)
    masterGain = min(3.65, tuning.shiftKickGain * 1.3)

    # Phase 1: initial selector click → hard rigid lock (0..32ms)
    if elapsed < 0.032:
        lockStrength = max(4, min(8, int(8 * masterGain * sideGain)))
        zones = [0, 0, lockStrength, lockStrength, lockStrength,
                 lockStrength, 8, 8, 8, 8]
        return buildZoneFeedback(zones)

    # Phase 2: torque-cut notch → slightly softer rigid (32..58ms)
    if elapsed < 0.058:
        cutGain = min(1.80, tuning.shiftTorqueCutGain)
        lockStrength = max(3, min(7, int(6 * cutGain * sideGain)))
        zones = [0, 0, lockStrength, lockStrength, lockStrength,
                 lockStrength, 7, 7, 7, 7]
        return buildZoneFeedback(zones)

    # Phase 3: second mechanical clack (58..90ms)
    if elapsed < 0.090:
        clackGain = min(3.25, tuning.shiftClackGain * 1.3)
        lockStrength = max(3, min(8, int(8 * clackGain * masterGain * sideGain)))
        zones = [0, 0, lockStrength, lockStrength, lockStrength,
                 lockStrength, 8, 8, 8, 8]
        return buildZoneFeedback(zones)

    # No tail → clean end
    return None


# ── Rev limiter ──────────────────────────────────────────────────────────────

def computeRevLimiterBuzz(vs: VehicleState, mem: EffectMemory,
                          tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableRevLimiter:
        return None

    # Detect handbrake burnout (full throttle + handbrake + stationary)
    handbrakeWotStall = (
        vs.throttle >= 200 and vs.handbrake > 16 and vs.speedMps < 1.0
    )
    if handbrakeWotStall:
        mem.revPeakRpm = 1.0
        strength = min(2.5, tuning.revLimiterStrength)
        amp = max(1, int(tuning.revLimiterBaseAmp * strength))
        return _buildBuzzWithEndWall(amp, 90, tuning.endStopDepth)

    # Arm hold timer when at high RPM + throttle applied
    if vs.throttle >= tuning.r2DeadZone:
        if vs.rpmRatio > tuning.revLimiterThreshold:
            mem.revPeakRpm = max(mem.revPeakRpm * 0.65, vs.rpmRatio)
            mem.revHoldUntil = now + tuning.revLimiterHoldMs / 1000.0

    if now < mem.revHoldUntil:
        strength = min(2.5, tuning.revLimiterStrength)
        if tuning.enableRevLimiterPattern:
            # Amplitude-modulated tremolo instead of mechanical clatter
            overRatio = 0.0
            if tuning.revLimiterThreshold < 0.999:
                overRatio = min(1.0, max(0.0,
                    (mem.revPeakRpm - tuning.revLimiterThreshold)
                    / (1.0 - tuning.revLimiterThreshold)))
            period = max(0.048, 0.105 - overRatio * 0.048)
            phase = (now / period) % 1.0
            envelope = 0.50 + 0.50 * math.sin(phase * 2.0 * math.pi)
            freq = max(85, int(85 + overRatio * 35))
            amp = int(tuning.revLimiterBaseAmp * strength * (0.65 + overRatio * 0.55) * envelope)
            return _buildBuzzWithEndWall(max(1, min(255, amp)), freq, tuning.endStopDepth)
        # Non-pattern: smooth high-freq tremor
        freq = max(80, min(100, tuning.revLimiterBaseFreq + 50))
        amp = max(1, int(tuning.revLimiterBaseAmp * strength))
        return _buildBuzzWithEndWall(amp, freq, tuning.endStopDepth)

    mem.revPeakRpm = 0.0
    return None


# ── Redline pulse (pre-rev-limiter warning) ──────────────────────────────────

def computeRedlinePulse(vs: VehicleState, tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableRedlinePulse:
        return None
    if vs.maxRpm <= 0:
        return None
    rpmNorm = vs.rpmRatio
    revThreshold = tuning.revLimiterThreshold     # e.g. 0.93
    warningStart = 0.92
    if rpmNorm < warningStart or rpmNorm >= revThreshold:
        return None  # above threshold → rev limiter owns it
    overband = min(1.0, (rpmNorm - warningStart) / max(0.01, revThreshold - warningStart))
    strength = min(2.0, tuning.redlinePulseStrength)
    period = max(0.05, 0.09 - overband * 0.04)   # ~11Hz→20Hz
    phase = (now / period) % 1.0
    pulse = 0.5 + 0.5 * math.sin(phase * 2.0 * math.pi)
    baseForce = int(3 + overband * 3)
    pulseAmp = (3 + overband * 4) * strength
    force = max(1, min(8, int(baseForce + pulseAmp * pulse)))
    return buildSimpleResistance(0, force * 32)   # scale to 0-255 range


# ── Idle engine feel ─────────────────────────────────────────────────────────

def computeIdleResistance(vs: VehicleState, tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableIdleFeel:
        return None
    if vs.speedKmh >= tuning.idleMaxSpeedKmh:
        return None
    if not (1 <= vs.throttle <= tuning.idleThrottleMax):
        return None
    # Pulsing rigid resistance → feels like engine idle without losing pedal
    loud = (now / tuning.idlePeriodSec) % 1.0 < 0.5
    pedal = vs.throttle
    force = applyPedalResistanceCurve(
        pedal, max(1, tuning.r2DeadZone // 2),
        tuning.r2BaselineForce, tuning.r2PeakResistance,
        tuning.r2CurveExponent, tuning.r2WallEngage
    ) * tuning.pedalBaseGain
    strength = max(2, min(8, int(force)))
    if not loud:
        strength = max(1, strength - 1)   # slight dip for chug feel
    return buildSimpleResistance(0, strength * 32)


# ── ABS pulse ────────────────────────────────────────────────────────────────

def computeAbsPulseEffect(vs: VehicleState, mem: EffectMemory,
                          tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableAbs:
        return None
    if vs.brake < tuning.absBrakeThreshold or vs.speedKmh < tuning.absMinSpeedKmh:
        return None

    # Evaluate wheel lockup: check slip_ratio and combined_slip
    frontSlipRatio = max(abs(vs.tireSlipRatio[0]), abs(vs.tireSlipRatio[1]))
    rearSlipRatio = max(abs(vs.tireSlipRatio[2]), abs(vs.tireSlipRatio[3]))
    frontCombined = max(abs(vs.tireCombinedSlip[0]), abs(vs.tireCombinedSlip[1]))
    rearCombined = max(abs(vs.tireCombinedSlip[2]), abs(vs.tireCombinedSlip[3]))

    frontNorm = max(frontSlipRatio / max(0.001, tuning.absSlipRatioThreshold),
                    frontCombined / max(0.001, tuning.absCombinedSlipThreshold))
    rearNorm = max(rearSlipRatio / max(0.001, tuning.absSlipRatioThreshold),
                   rearCombined / max(0.001, tuning.absCombinedSlipThreshold))

    if frontNorm < 1.0 and rearNorm < 1.0:
        # Not locking → but maybe still in hold window
        if now < mem.absHoldUntil:
            return _buildBuzzWithEndWall(mem.absAmplitude, mem.absFrequency, tuning.endStopDepth)
        return None

    # Determine which axle is locking harder
    frontExcess = max(0.0, frontNorm - 1.0)
    rearExcess = max(0.0, rearNorm - 1.0)
    lockIntensity = min(1.0, max(frontExcess, rearExcess) / 2.0)
    brakeFactor = min(1.0, (vs.brake - tuning.absBrakeThreshold) /
                      max(1, 255 - tuning.absBrakeThreshold))

    if frontExcess > rearExcess * 1.25:
        freqBase = tuning.absBaseFreq + 14
        ampMul = 1.00
    elif rearExcess > frontExcess * 1.25:
        freqBase = max(4, tuning.absBaseFreq + 4)
        ampMul = 0.88
    else:
        freqBase = tuning.absBaseFreq + 10
        ampMul = 1.16

    strength = min(2.5, tuning.absStrength)
    amp = int(tuning.absBaseAmp * strength * ampMul * (1.20 + lockIntensity * 2.0 + brakeFactor * 0.80))
    amp = max(36, min(255, amp))    # minimum perceptible pulse
    freq = max(4, min(70, int(freqBase + lockIntensity * 11 + brakeFactor * 4)))

    mem.absAmplitude = amp
    mem.absFrequency = freq
    holdSec = max(0.0, min(0.250, tuning.absHoldMs / 1000.0))
    mem.absHoldUntil = now + holdSec
    return _buildBuzzWithEndWall(amp, freq, tuning.endStopDepth)


# ── Engine braking resistance (L2, throttle-off coasting) ────────────────────

def computeEngineBrakeResistance(vs: VehicleState, mem: EffectMemory,
                                 tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableEngineBrake:
        return None
    if vs.throttle > 15:        # throttle open → not coasting
        return None
    if vs.brake >= tuning.l2DeadZone:
        return None             # brake pedal → computeBrakeResistance owns L2
    if vs.speedKmh < 30.0:
        return None
    if vs.rpmRatio < 0.3:
        return None
    strength = min(1.5, tuning.engineBrakeStrength)
    if strength <= 0.0:
        return None
    force = int(1 + vs.rpmRatio * 3.0 * strength)
    force = max(1, min(5, force))
    mem.engineBrakeUntil = now + 0.10  # 100ms hold
    return buildSimpleResistance(0, force * 32)


# ── Wheelspin vibration ──────────────────────────────────────────────────────

def computeWheelSpinVibration(vs: VehicleState, tuning, now: float) -> TriggerEffect | None:
    if not tuning.enableWheelSpin:
        return None
    # Check driven wheels for longitudinal slip
    indices = vs.drivenWheelIndices
    maxSlip = max(abs(vs.tireSlipRatio[i]) for i in indices)
    if maxSlip < tuning.wheelSpinSlipThreshold:
        return None
    # Intensity ramps from threshold to saturation
    intensity = min(1.0, (maxSlip - tuning.wheelSpinSlipThreshold) /
                   max(0.1, tuning.wheelSpinSaturation - tuning.wheelSpinSlipThreshold))
    amp = max(2, min(7, int(tuning.wheelSpinBaseAmplitude + intensity * 3)))
    freq = max(50, int(55 + intensity * 35))  # 55Hz→90Hz based on slip
    return buildSoftZoneVibration(amp, freq, topBoost=1)


# ── Brake resistance (L2 ramp) ───────────────────────────────────────────────

def computeBrakeResistance(vs: VehicleState, tuning) -> TriggerEffect:
    if not tuning.enableBrakeResistance:
        if tuning.enableHandbrakeBonus and vs.handbrake > 0:
            return buildSimpleResistance(0, tuning.handbrakeBonus * 32)
        return clearEffect()

    masterGain = min(2.5, tuning.masterGain)
    brakeGain = min(2.0, tuning.brakeGain)
    l2Gain = min(2.0, tuning.l2Gain)
    if masterGain <= 0.0 or brakeGain <= 0.0 or l2Gain <= 0.0:
        return clearEffect()

    force = applyPedalResistanceCurve(
        vs.brake, tuning.l2DeadZone, tuning.l2BaselineForce,
        tuning.l2PeakResistance, tuning.l2CurveExponent, tuning.l2WallEngage
    ) * brakeGain * l2Gain * masterGain

    if tuning.enableHandbrakeBonus and vs.handbrake > 0:
        force += tuning.handbrakeBonus
    if force < 0.3:
        return clearEffect()
    strength = max(0, min(7, int(force)))     # leave 8 for wall-only
    return buildSimpleResistance(0, strength * 32)


# ── Throttle resistance + engine texture (R2) ────────────────────────────────

def computeThrottleResistance(vs: VehicleState, tuning) -> TriggerEffect:
    if not tuning.enableThrottleResistance:
        return clearEffect()
    if vs.throttle < tuning.r2DeadZone:
        return clearEffect()

    masterGain = min(2.5, tuning.masterGain)
    pedalGain = min(1.50, tuning.pedalBaseGain)
    r2Gain = min(2.0, tuning.r2Gain)
    if masterGain <= 0.0 or pedalGain <= 0.0 or r2Gain <= 0.0:
        return clearEffect()

    force = applyPedalResistanceCurve(
        vs.throttle, tuning.r2DeadZone, tuning.r2BaselineForce,
        tuning.r2PeakResistance, tuning.r2CurveExponent, tuning.r2WallEngage
    ) * pedalGain * r2Gain * masterGain
    strength = max(2, min(8, int(force)))

    # Below meaningful speed or RPM → just resistance, no vibration
    if vs.speedKmh < 5.0 or vs.rpmRatio < 0.15:
        return buildSimpleResistance(0, strength * 32)

    # During heavy slide → pure resistance (preserve driver modulation)
    drivenSlip = max(abs(vs.tireSlipRatio[i]) for i in vs.drivenWheelIndices)
    if drivenSlip > 0.35:
        return buildSimpleResistance(0, strength * 32)

    # Normal driving: light engine-texture overlay
    freq = int(45 + vs.rpmRatio * 35)  # 45Hz idle → 80Hz redline

    # Offroad dampening: if surface is bumpy, raise min freq to avoid clatter
    drivenRumble = max(vs.surfaceRumble[i] for i in vs.drivenWheelIndices)
    if drivenRumble > 0.15:
        freq = max(85, freq)

    # Vibration amplitude: subtle → just enough engine life
    throttleNorm = min(1.0, (vs.throttle - tuning.r2DeadZone) / max(1, 255 - tuning.r2DeadZone))
    torqueFactor = min(1.0, max(0.0, vs.torque / 500.0))
    offroadDamp = max(0.50, 1.0 - drivenRumble * 0.6) if drivenRumble > 0.15 else 1.0
    vibIntensity = (0.20 + throttleNorm * 0.15 + torqueFactor * 0.10) * offroadDamp
    vibStrength = max(2, min(strength, int(strength * vibIntensity)))

    return buildSoftZoneVibration(vibStrength, freq, topBoost=1)


# ── End-stop wall (firmware held) ────────────────────────────────────────────

def buildEndStopWall(depth: int) -> TriggerEffect:
    # Top `depth` zones at maximum strength → hard wall near end of travel
    n = max(1, min(9, int(depth)))
    zones = [0] * (10 - n) + [8] * n
    return buildZoneFeedback(zones)


# ── Slip onset / grip recovery ───────────────────────────────────────────────

def _evaluateSlipTransients(vs: VehicleState, mem: EffectMemory, tuning, now: float):
    # Track slip rate-of-change for onset pulse + grip recovery
    currentSlip = max(abs(vs.tireSlipRatio[i]) for i in vs.drivenWheelIndices)
    slipDelta = currentSlip - mem.previousSlipRatio
    mem.previousSlipRatio = currentSlip

    # Slip onset: rapid increase → brief resistance pulse (warning)
    if (slipDelta > 0.35 and vs.throttle > tuning.r2DeadZone):
        mem.slipPulseUntil = now + 0.055  # 55ms snap

    # Grip recovery: rapid decrease → brief release then texture
    if (slipDelta < -0.8 and currentSlip < 0.8 and mem.gripReleaseUntil < now):
        mem.gripReleaseUntil = now + 0.035
        mem.gripTextureUntil = now + 0.035 + 0.060


# ── Internal helper ──────────────────────────────────────────────────────────

def _buildBuzzWithEndWall(amplitude: int, frequency: int, wallDepth: int) -> TriggerEffect:
    # Vibrate zones with end-wall preserved so trigger doesn't go limp
    amp = max(1, min(8, (max(0, int(amplitude)) // 18) + 1))
    n = max(1, min(9, int(wallDepth)))
    zones = [amp] * (10 - n) + [8] * n
    return buildZoneVibration(zones, frequency)


def _mapAmplitudeToZoneStrength(rawAmp: int) -> int:
    # Map 0..255 range to zone strength 1..8
    return max(1, min(8, (max(0, int(rawAmp)) // 18) + 1))


# ── Main entry point ─────────────────────────────────────────────────────────

def computeTriggerFrame(vs: VehicleState, mem: EffectMemory,
                        tuning, now: float,
                        tDict: dict | None = None,
                        settings=None) -> TriggerFrame:
    # When game is not in race state, both triggers go neutral
    if not vs.isRacing:
        return TriggerFrame(clearEffect(), clearEffect(), "off", "off")

    # Master gain kill-switch: 0 = all trigger feedback disabled
    if tuning.masterGain <= 0.0:
        return TriggerFrame(clearEffect(), clearEffect(), "off", "off")

    # Detect gear changes once per frame (affects both L2 and R2)
    if tuning.enableGearShift or tuning.enableGearShiftBrake:
        detectGearShift(vs, mem, tuning, now)

    # Evaluate slip transients (needed for R2 onset/recovery effects)
    _evaluateSlipTransients(vs, mem, tuning, now)

    leftEffect, leftLabel = _resolveBrakeTrigger(vs, mem, tuning, now, tDict, settings)
    rightEffect, rightLabel = _resolveThrottleTrigger(vs, mem, tuning, now)
    return TriggerFrame(leftEffect, rightEffect, leftLabel, rightLabel)


# ── L2 resolver (brake pedal) ────────────────────────────────────────────────

def _resolveBrakeTrigger(vs: VehicleState, mem: EffectMemory,
                         tuning, now: float,
                         tDict: dict | None = None,
                         settings=None) -> tuple[TriggerEffect, str]:
    """
    L2 priority chain (top wins):
      1. Gear shift kick
      2. ABS pulse
      3. Engine brake resistance (throttle off + high RPM)
      4. Left road texture (only when not braking)
      5. End-stop wall (hysteresis latched)
      6. Brake resistance ramp
    """
    # 1. Gear shift kick — brief burst masks everything
    if tuning.enableGearShiftBrake:
        shiftEffect = produceShiftKickEffect(mem, tuning, now, sideGain=0.55)
        if shiftEffect is not None:
            return shiftEffect, "shift"

    # 2. ABS pulse — lockup buzz under hard braking
    absEffect = computeAbsPulseEffect(vs, mem, tuning, now)
    if absEffect is not None:
        return absEffect, "abs"

    # 3. Engine braking — light resistance when coasting at high RPM
    engBrake = computeEngineBrakeResistance(vs, mem, tuning, now)
    if engBrake is not None:
        return engBrake, "engine-brake"

    # 4. Left road texture — surface feel when not braking
    if tDict is not None and settings is not None:
        roadEffect = _roadFx.left_road_buzz(tDict, settings, now)
        if roadEffect is not None:
            return roadEffect, "road:left"

    # 5. Firmware end-stop wall — latched via hysteresis near 100% travel
    mem.l2WallLatched = checkWallLatchHysteresis(
        vs.brake, mem.l2WallLatched, tuning.l2WallEngage, tuning.l2WallRelease)
    if mem.l2WallLatched:
        return buildEndStopWall(tuning.endStopDepth), "wall"

    # 6. Default brake resistance ramp
    return computeBrakeResistance(vs, tuning), "brake"


# ── R2 resolver (throttle pedal) ─────────────────────────────────────────────

def _resolveThrottleTrigger(vs: VehicleState, mem: EffectMemory,
                            tuning, now: float) -> tuple[TriggerEffect, str]:
    """
    R2 priority chain (top wins):
      1. Gear shift kick
      2. Idle engine feel
      3. Redline pulse (92%..revLimitThreshold)
      4. Rev limiter buzz
      5. Slip onset pulse / Grip recovery
      6. Wheelspin vibration
      7. End-stop wall (hysteresis)
      8. Throttle resistance + engine texture
    """
    # 1. Gear shift kick
    if tuning.enableGearShift:
        shiftEffect = produceShiftKickEffect(mem, tuning, now, sideGain=1.0)
        if shiftEffect is not None:
            return shiftEffect, "shift"

    # 2. Idle feel → light pulsing resistance at standstill
    idleEffect = computeIdleResistance(vs, tuning, now)
    if idleEffect is not None:
        return idleEffect, "idle"

    # 3. Redline pre-warning → subtle pulse before rev limiter activates
    redlineEffect = computeRedlinePulse(vs, tuning, now)
    if redlineEffect is not None:
        return redlineEffect, "redline"

    # 4. Rev limiter → strong buzz when bouncing off redline
    revEffect = computeRevLimiterBuzz(vs, mem, tuning, now)
    if revEffect is not None:
        return revEffect, "rev-limiter"

    # 5. Slip transients → brief warnings/releases around grip edges
    if now < mem.gripReleaseUntil:
        return clearEffect(), "grip-release"
    if now < mem.gripTextureUntil:
        gripStrength = max(2, min(5, 3))
        return buildSoftZoneVibration(gripStrength, 130, topBoost=0), "grip-texture"
    if now < mem.slipPulseUntil:
        return buildSimpleResistance(0, 160), "slip-onset"  # ~5 * 32

    # 6. Wheelspin vibration
    spinEffect = computeWheelSpinVibration(vs, tuning, now)
    if spinEffect is not None:
        return spinEffect, "wheelspin"

    # 7. End-stop wall → latched via hysteresis
    mem.r2WallLatched = checkWallLatchHysteresis(
        vs.throttle, mem.r2WallLatched, tuning.r2WallEngage, tuning.r2WallRelease)
    if mem.r2WallLatched:
        return buildEndStopWall(tuning.endStopDepth), "wall"

    # 8. Default throttle resistance + engine texture
    return computeThrottleResistance(vs, tuning), "throttle"
