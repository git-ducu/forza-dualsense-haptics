# ── Forza Horizon telemetry state ───────────────────────────────────────────
#
# Immutable per-frame vehicle snapshot decoded from telemetry Data Out UDP.
# This is the single source of truth for all downstream mappers —
# trigger logic and haptic logic both consume this, never raw bytes.

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VehicleState:
    """One frame of Forza telemetry. All values are physical units."""

    # race state
    isRacing: bool
    timestampMs: int

    # powertrain
    engineRpm: float
    maxRpm: float
    idleRpm: float
    currentGear: int
    numCylinders: int
    driveLayout: int          # 0=FWD, 1=RWD, 2=AWD

    # inputs (raw 0-255 pedal bytes)
    throttle: int
    brake: int
    clutch: int
    handbrake: int
    steer: int                # signed -127..128

    # motion
    speedMps: float           # meters per second
    accelX: float             # lateral
    accelY: float             # vertical
    accelZ: float             # longitudinal
    velocityX: float
    velocityY: float
    velocityZ: float
    angularVelocityX: float
    angularVelocityY: float
    angularVelocityZ: float

    # orientation
    yaw: float
    pitch: float
    roll: float

    # per-wheel: order is always (FL, FR, RL, RR)
    suspensionTravel: tuple[float, float, float, float]
    suspensionTravelMeters: tuple[float, float, float, float]
    tireSlipRatio: tuple[float, float, float, float]
    tireCombinedSlip: tuple[float, float, float, float]
    tireSlipAngle: tuple[float, float, float, float]
    wheelRotationSpeed: tuple[float, float, float, float]
    wheelOnRumbleStrip: tuple[int, int, int, int]
    wheelInPuddle: tuple[int, int, int, int]
    surfaceRumble: tuple[float, float, float, float]
    tireTemp: tuple[float, float, float, float]

    # engine
    power: float              # watts
    torque: float             # Nm
    boost: float
    fuel: float

    # car info
    carOrdinal: int
    carClass: int
    performanceIndex: int

    # position / lap
    positionX: float
    positionY: float
    positionZ: float
    distanceTraveled: float
    bestLapTime: float
    lastLapTime: float
    currentLapTime: float
    currentRaceTime: float
    lapNumber: int
    racePosition: int

    # driving line / AI
    normalizedDrivingLine: int
    normalizedAiBrakeDiff: int

    # ── Derived convenience ─────────────────────────────────────────────────

    @property
    def speedKmh(self) -> float:
        return self.speedMps * 3.6

    @property
    def rpmRatio(self) -> float:
        return self.engineRpm / self.maxRpm if self.maxRpm > 0 else 0.0

    @property
    def drivenWheelIndices(self) -> tuple[int, ...]:
        # 0=FWD(FL,FR), 1=RWD(RL,RR), 2=AWD(all)
        return {0: (0, 1), 1: (2, 3), 2: (0, 1, 2, 3)}.get(self.driveLayout, (0, 1, 2, 3))

    def asLegacyDict(self) -> dict:
        """Convert to the flat snake_case dict consumed by surfaceEffects/loop."""
        fl, fr, rl, rr = 0, 1, 2, 3
        return {
            "on": self.isRacing,
            "timestamp_ms": self.timestampMs,
            "rpm": self.engineRpm,
            "max_rpm": self.maxRpm,
            "idle_rpm": self.idleRpm,
            "gear": self.currentGear,
            "num_cylinders": self.numCylinders,
            "drive_train": self.driveLayout,
            "accel": self.throttle,
            "brake": self.brake,
            "clutch": getattr(self, "clutch", 0),
            "handbrake": getattr(self, "handbrake", 0),
            "steer": getattr(self, "steer", 0),
            "speed": self.speedKmh,
            "accel_x": self.accelX,
            "accel_y": self.accelY,
            "accel_z": self.accelZ,
            "velocity_x": self.velocityX,
            "velocity_y": self.velocityY,
            "velocity_z": self.velocityZ,
            "angular_velocity_x": self.angularVelocityX,
            "angular_velocity_y": self.angularVelocityY,
            "angular_velocity_z": self.angularVelocityZ,
            "yaw": self.yaw,
            "pitch": self.pitch,
            "roll": self.roll,
            "norm_suspension_travel_fl": self.suspensionTravel[fl],
            "norm_suspension_travel_fr": self.suspensionTravel[fr],
            "norm_suspension_travel_rl": self.suspensionTravel[rl],
            "norm_suspension_travel_rr": self.suspensionTravel[rr],
            "suspension_travel_meters_fl": self.suspensionTravelMeters[fl],
            "suspension_travel_meters_fr": self.suspensionTravelMeters[fr],
            "suspension_travel_meters_rl": self.suspensionTravelMeters[rl],
            "suspension_travel_meters_rr": self.suspensionTravelMeters[rr],
            "tire_slip_ratio_fl": self.tireSlipRatio[fl],
            "tire_slip_ratio_fr": self.tireSlipRatio[fr],
            "tire_slip_ratio_rl": self.tireSlipRatio[rl],
            "tire_slip_ratio_rr": self.tireSlipRatio[rr],
            "tire_combined_slip_fl": self.tireCombinedSlip[fl],
            "tire_combined_slip_fr": self.tireCombinedSlip[fr],
            "tire_combined_slip_rl": self.tireCombinedSlip[rl],
            "tire_combined_slip_rr": self.tireCombinedSlip[rr],
            "tire_slip_angle_fl": self.tireSlipAngle[fl],
            "tire_slip_angle_fr": self.tireSlipAngle[fr],
            "tire_slip_angle_rl": self.tireSlipAngle[rl],
            "tire_slip_angle_rr": self.tireSlipAngle[rr],
            "wheel_rotation_speed_fl": self.wheelRotationSpeed[fl],
            "wheel_rotation_speed_fr": self.wheelRotationSpeed[fr],
            "wheel_rotation_speed_rl": self.wheelRotationSpeed[rl],
            "wheel_rotation_speed_rr": self.wheelRotationSpeed[rr],
            "wheel_on_rumble_strip_fl": self.wheelOnRumbleStrip[fl],
            "wheel_on_rumble_strip_fr": self.wheelOnRumbleStrip[fr],
            "wheel_on_rumble_strip_rl": self.wheelOnRumbleStrip[rl],
            "wheel_on_rumble_strip_rr": self.wheelOnRumbleStrip[rr],
            "wheel_in_puddle_fl": self.wheelInPuddle[fl],
            "wheel_in_puddle_fr": self.wheelInPuddle[fr],
            "wheel_in_puddle_rl": self.wheelInPuddle[rl],
            "wheel_in_puddle_rr": self.wheelInPuddle[rr],
            "surface_rumble_fl": self.surfaceRumble[fl],
            "surface_rumble_fr": self.surfaceRumble[fr],
            "surface_rumble_rl": self.surfaceRumble[rl],
            "surface_rumble_rr": self.surfaceRumble[rr],
            "tire_temp_fl": self.tireTemp[fl],
            "tire_temp_fr": self.tireTemp[fr],
            "tire_temp_rl": self.tireTemp[rl],
            "tire_temp_rr": self.tireTemp[rr],
            "power": self.power,
            "torque": self.torque,
            "boost": self.boost,
            "fuel": self.fuel,
            "car_ordinal": self.carOrdinal,
            "car_class": self.carClass,
            "car_performance_index": self.performanceIndex,
            "position_x": self.positionX,
            "position_y": self.positionY,
            "position_z": self.positionZ,
            "distance_traveled": self.distanceTraveled,
            "best_lap_time": self.bestLapTime,
            "last_lap_time": self.lastLapTime,
            "current_lap_time": self.currentLapTime,
            "current_race_time": self.currentRaceTime,
            "lap_number": self.lapNumber,
            "race_position": self.racePosition,
            "normalized_driving_line": self.normalizedDrivingLine,
            "normalized_ai_brake_difference": self.normalizedAiBrakeDiff,
        }
