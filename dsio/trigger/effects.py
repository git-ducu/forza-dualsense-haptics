# ── Adaptive trigger effect definitions ─────────────────────────────────────────
#
# Immutable TriggerEffect descriptors. Each factory function encodes
# firmware mode + parameters into a packed 11-byte payload used by
# the DualSense output report.

from __future__ import annotations
from enum import IntEnum
from typing import NamedTuple


# ── Firmware mode tags ──────────────────────────────────────────────────────

class Mode(IntEnum):
    CLEAR          = 0x05   # neutral / off
    SIMPLE_RES     = 0x01   # fixed resistance at position
    SIMPLE_VIB     = 0x06   # single-frequency buzz
    FEEDBACK       = 0x21   # 10-zone resistance map (3-bit packed)
    VIBRATION      = 0x26   # 10-zone vibration map + freq byte
    BOW            = 0x22   # spring-tension with rebound
    GALLOPING      = 0x23   # alternating two-step cadence
    WEAPON         = 0x25   # zone-bounded tension release
    WEAPON_SIMPLE  = 0x02   # raw position-bounded tension
    MACHINE        = 0x27   # amplitude-alternating oscillation
    FEEDBACK_LIM   = 0x11   # clamped resistance (0-10 scale)
    WEAPON_LIM     = 0x12   # clamped weapon variant


# ── TriggerEffect — immutable descriptor ────────────────────────────────────

class TriggerEffect(NamedTuple):
    mode: int
    payload: bytes          # variable length, padded to 10 on pack

    def pack(self) -> bytes:
        # 11 bytes: mode + payload right-padded with zeroes
        out = bytearray(11)
        out[0] = self.mode & 0xFF
        p = self.payload[:10]
        out[1:1+len(p)] = p
        return bytes(out)


# ── Factory functions ───────────────────────────────────────────────────────

def clearEffect() -> TriggerEffect:
    # neutral — no resistance, no vibration
    return TriggerEffect(Mode.CLEAR, b'')


def buildSimpleResistance(startPosition: int, force: int) -> TriggerEffect:
    # static push-back from startPosition (0-255) at given force (0-255)
    return TriggerEffect(Mode.SIMPLE_RES, bytes([_u8(startPosition), _u8(force)]))


def buildSimpleVibration(triggerPosition: int, amplitude: int, frequency: int) -> TriggerEffect:
    # single-zone buzz past triggerPosition
    return TriggerEffect(Mode.SIMPLE_VIB, bytes([_u8(frequency), _u8(amplitude), _u8(triggerPosition)]))


def buildZoneFeedback(zoneStrengths: list[int]) -> TriggerEffect:
    # 10-slot resistance map, each slot 0-8
    maskBytes, packedBits = _encodeZoneStrengthBits(zoneStrengths)
    return TriggerEffect(Mode.FEEDBACK, maskBytes + packedBits + b'\x00\x00\x00\x00')


def buildZoneVibration(zoneAmplitudes: list[int], frequency: int) -> TriggerEffect:
    # 10-slot vibration map with shared frequency
    maskBytes, packedBits = _encodeZoneStrengthBits(zoneAmplitudes)
    return TriggerEffect(Mode.VIBRATION, maskBytes + packedBits + bytes([0, 0, _u8(frequency), 0]))


def buildZoneVibrationFromPosition(startZone: int, amplitude: int, frequency: int, wallDepth: int) -> TriggerEffect:
    # positioned vibration: silent below startZone, buzz in mid, wall at top
    amp = max(1, min(8, int(amplitude)))
    w = max(1, min(9, int(wallDepth)))
    start = max(0, min(9 - w, int(startZone)))
    zones = [0] * start + [amp] * max(0, 10 - w - start) + [8] * w
    maskBytes, packedBits = _encodeZoneStrengthBits(zones)
    return TriggerEffect(Mode.VIBRATION, maskBytes + packedBits + bytes([0, 0, _u8(frequency), 0]))


def buildSoftZoneVibration(amplitude: int, frequency: int, topBoost: int = 0) -> TriggerEffect:
    # gentle vibration without hard end-wall — for informational texture
    amp = max(1, min(8, int(amplitude)))
    top = max(amp, min(8, amp + max(0, min(3, int(topBoost)))))
    zones = [amp] * 8 + [top] * 2
    maskBytes, packedBits = _encodeZoneStrengthBits(zones)
    return TriggerEffect(Mode.VIBRATION, maskBytes + packedBits + bytes([0, 0, _u8(frequency), 0]))


def buildSoftZoneVibrationFromPosition(startZone: int, amplitude: int, frequency: int, topBoost: int = 1) -> TriggerEffect:
    # positioned soft vibration — no hard max wall at end
    amp = max(1, min(8, int(amplitude)))
    start = max(0, min(5, int(startZone)))
    top = max(amp, min(8, amp + max(0, min(3, int(topBoost)))))
    zones = [0] * start + [amp] * max(0, 8 - start) + [top] * 2
    maskBytes, packedBits = _encodeZoneStrengthBits(zones)
    return TriggerEffect(Mode.VIBRATION, maskBytes + packedBits + bytes([0, 0, _u8(frequency), 0]))


def buildWeaponEffect(startZone: int, endZone: int, strength: int) -> TriggerEffect:
    # zone-bounded tension with release
    s = max(2, min(7, int(startZone)))
    e = max(s + 1, min(8, int(endZone)))
    f = max(1, min(8, int(strength)))
    zoneBits = (1 << s) | (1 << e)
    return TriggerEffect(Mode.WEAPON, bytes([zoneBits & 0xFF, (zoneBits >> 8) & 0xFF, f - 1]))


def buildBowEffect(startZone: int, endZone: int, resistForce: int, snapForce: int) -> TriggerEffect:
    # spring tension with rebound between zones
    s = max(0, min(8, int(startZone)))
    e = max(s + 1, min(8, int(endZone)))
    rf = max(1, min(8, int(resistForce)))
    sf = max(1, min(8, int(snapForce)))
    zoneBits = (1 << s) | (1 << e)
    pair = ((rf - 1) & 0x07) | (((sf - 1) & 0x07) << 3)
    return TriggerEffect(Mode.BOW, bytes([zoneBits & 0xFF, (zoneBits >> 8) & 0xFF, pair & 0xFF, (pair >> 8) & 0xFF]))


def buildGallopingEffect(startZone: int, endZone: int, firstFoot: int, secondFoot: int, frequency: int) -> TriggerEffect:
    # alternating two-step cadence at given frequency
    s = max(0, min(8, int(startZone)))
    e = max(s + 1, min(9, int(endZone)))
    ff = max(0, min(6, int(firstFoot)))
    sf = max(ff + 1, min(7, int(secondFoot)))
    zoneBits = (1 << s) | (1 << e)
    pair = (sf & 0x07) | ((ff & 0x07) << 3)
    return TriggerEffect(Mode.GALLOPING, bytes([zoneBits & 0xFF, (zoneBits >> 8) & 0xFF, pair & 0xFF, _u8(frequency)]))


def buildMachineEffect(startZone: int, endZone: int, ampA: int, ampB: int, frequency: int, period: int) -> TriggerEffect:
    # amplitude-alternating oscillation between two levels
    s = max(0, min(8, int(startZone)))
    e = max(s + 1, min(9, int(endZone)))
    a = max(0, min(7, int(ampA)))
    b = max(0, min(7, int(ampB)))
    zoneBits = (1 << s) | (1 << e)
    pair = (a & 0x07) | ((b & 0x07) << 3)
    return TriggerEffect(Mode.MACHINE, bytes([zoneBits & 0xFF, (zoneBits >> 8) & 0xFF, pair & 0xFF, _u8(frequency), _u8(period)]))


def buildResistanceSlope(startZone: int, endZone: int, startForce: int, endForce: int) -> TriggerEffect:
    # progressive ramp across zone range
    sp = max(0, min(8, int(startZone)))
    ep = max(sp + 1, min(9, int(endZone)))
    sf = max(1, min(8, int(startForce)))
    ef = max(1, min(8, int(endForce)))
    slope = (ef - sf) / max(1, ep - sp)
    zones = [0] * 10
    for i in range(sp, 10):
        zones[i] = round(sf + slope * (i - sp)) if i <= ep else ef
    return buildZoneFeedback(zones)


# ── Internal helpers ────────────────────────────────────────────────────────

def _u8(v) -> int:                                          # clamp to uint8
    return max(0, min(255, int(round(v))))


def _encodeZoneStrengthBits(strengths: list[int]) -> tuple[bytes, bytes]:
    # returns (2-byte active mask, 4-byte packed 3-bit-per-zone values)
    activeMask = 0
    packedValue = 0
    for i, s in enumerate(strengths[:10]):
        s = max(0, min(8, int(s)))
        if s > 0:
            activeMask |= 1 << i
            packedValue |= (s - 1) << (3 * i)
    return (activeMask.to_bytes(2, 'little'), packedValue.to_bytes(4, 'little'))
