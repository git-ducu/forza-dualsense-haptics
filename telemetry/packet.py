# ── Forza Data Out packet decoder ───────────────────────────────────────────
#
# Unpacks the raw 324-byte UDP payload into a typed VehicleState object.

from __future__ import annotations
import struct

from .vehicle import VehicleState

EXPECTED_PACKET_SIZE = 324

# Pre-compiled struct formats for each logical section of the packet.
# This avoids per-frame lambda allocations and repeated unpack_from calls.
_FMT_HEADER  = struct.Struct('<i I f f f')           # on, timestamp, maxRpm, idleRpm, rpm
_FMT_MOTION  = struct.Struct('<12f')                  # accel(3) + vel(3) + angVel(3) + orient(3)
_FMT_WHEELS4F = struct.Struct('<4f')                  # 4 floats per wheel group
_FMT_WHEELS4I = struct.Struct('<4i')                  # 4 ints per wheel group
_FMT_CAR     = struct.Struct('<5i')                   # ordinal, class, PI, driveLayout, cylinders
_FMT_FH6     = struct.Struct('<I f f')               # carGroup, smashVelDiff, smashMass (FH6 extra)
_FMT_POS     = struct.Struct('<3f')                   # position xyz
_FMT_SPEED   = struct.Struct('<f')                    # speed m/s
_FMT_ENGINE  = struct.Struct('<3f')                   # power, torque, tireTemp[0]... (reused)
_FMT_LAP     = struct.Struct('<4f H')                # bestLap, lastLap, curLap, raceTime, lapNum


class PacketReader:
    """Decodes Forza Data Out UDP packets into VehicleState.
    Stateless — a single instance can decode any number of packets."""

    __slots__ = ()

    def decodeDataOutPacket(self, raw: bytes) -> VehicleState:
        """Decode a 324-byte Forza Data Out packet into a VehicleState.
        Raises ValueError if the packet is too short."""
        if len(raw) < EXPECTED_PACKET_SIZE:
            raise ValueError(f"packet too short: {len(raw)} bytes (need {EXPECTED_PACKET_SIZE})")

        # helper closures over raw buffer
        f4 = lambda off: struct.unpack_from('<4f', raw, off)
        i4 = lambda off: struct.unpack_from('<4i', raw, off)

        # header: offsets 0-19
        onFlag, timestampMs, maxRpm, idleRpm, engineRpm = _FMT_HEADER.unpack_from(raw, 0)

        # motion: offsets 20-67
        (ax, ay, az, vx, vy, vz, avx, avy, avz, yaw, pitch, roll) = _FMT_MOTION.unpack_from(raw, 20)

        # per-wheel groups
        suspTravel     = f4(68)      # normalized suspension travel
        slipRatio      = f4(84)      # tire slip ratio
        wheelRotSpeed  = f4(100)     # wheel rotation speed rad/s
        rumbleStrip    = i4(116)     # on rumble strip
        inPuddle       = i4(132)     # in puddle
        surfRumble     = f4(148)     # surface rumble magnitude
        slipAngle      = f4(164)     # tire slip angle
        combinedSlip   = f4(180)     # tire combined slip
        suspMeters     = f4(196)     # suspension travel in meters

        # car identity: offsets 212-231
        carOrd, carCls, carPI, driveLayout, numCyl = _FMT_CAR.unpack_from(raw, 212)

        # FH6 extra fields: 232-243 (skip — not used by core logic)
        # carGroup, smashVelDiff, smashMass = _FMT_FH6.unpack_from(raw, 232)

        # position: 244-255
        posX, posY, posZ = _FMT_POS.unpack_from(raw, 244)

        # speed: 256
        speedMps = struct.unpack_from('<f', raw, 256)[0]

        # engine: 260-267
        power, torque = struct.unpack_from('<2f', raw, 260)

        # tire temps: 268-283
        tireTemps = f4(268)

        # boost, fuel, distance: 284-295
        boost, fuel, distance = struct.unpack_from('<3f', raw, 284)

        # lap timing: 296-313
        bestLap, lastLap, curLap, raceTime = struct.unpack_from('<4f', raw, 296)
        lapNum = struct.unpack_from('<H', raw, 312)[0]

        # trailing single-byte fields: 314-322
        racePos   = raw[314]
        throttle  = raw[315]
        brake     = raw[316]
        clutch    = raw[317]
        handbrake = raw[318]
        gear      = raw[319]
        steer     = struct.unpack_from('<b', raw, 320)[0]
        driveLine = struct.unpack_from('<b', raw, 321)[0]
        aiBrake   = struct.unpack_from('<b', raw, 322)[0]

        return VehicleState(
            isRacing=onFlag != 0,
            timestampMs=timestampMs,
            engineRpm=engineRpm,
            maxRpm=maxRpm,
            idleRpm=idleRpm,
            currentGear=gear,
            numCylinders=numCyl,
            driveLayout=driveLayout,
            throttle=throttle,
            brake=brake,
            clutch=clutch,
            handbrake=handbrake,
            steer=steer,
            speedMps=speedMps,
            accelX=ax,
            accelY=ay,
            accelZ=az,
            velocityX=vx,
            velocityY=vy,
            velocityZ=vz,
            angularVelocityX=avx,
            angularVelocityY=avy,
            angularVelocityZ=avz,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            suspensionTravel=suspTravel,
            suspensionTravelMeters=suspMeters,
            tireSlipRatio=slipRatio,
            tireCombinedSlip=combinedSlip,
            tireSlipAngle=slipAngle,
            wheelRotationSpeed=wheelRotSpeed,
            wheelOnRumbleStrip=rumbleStrip,
            wheelInPuddle=inPuddle,
            surfaceRumble=surfRumble,
            tireTemp=tireTemps,
            power=power,
            torque=torque,
            boost=boost,
            fuel=fuel,
            carOrdinal=carOrd,
            carClass=carCls,
            performanceIndex=carPI,
            positionX=posX,
            positionY=posY,
            positionZ=posZ,
            distanceTraveled=distance,
            bestLapTime=bestLap,
            lastLapTime=lastLap,
            currentLapTime=curLap,
            currentRaceTime=raceTime,
            lapNumber=lapNum,
            racePosition=racePos,
            normalizedDrivingLine=driveLine,
            normalizedAiBrakeDiff=aiBrake,
        )
