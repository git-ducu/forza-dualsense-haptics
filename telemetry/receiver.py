# ── Forza telemetry UDP receiver ────────────────────────────────────────────
#
# Owns the UDP socket. Decoding and effect computation happen elsewhere.

from __future__ import annotations
import errno
import logging
import socket
import time

from .relay import UDPForwarder

log = logging.getLogger("dhe.receiver")

EXPECTED_PACKET_SIZE = 324

# Periodic rate logging interval (seconds)
_RATE_LOG_INTERVAL = 10.0


class TelemetryReceiver:
    """Receives Forza telemetry over UDP.

    Binds respecting the host setting (loopback stays local).
    Non-blocking drain ensures only the freshest packet is processed."""

    def __init__(self, host: str, port: int, timeoutSec: float = 0.5,
                 forwardTargets: str = "", forwardEnabled: bool = False):
        self._host = host
        self._port = port
        self._timeout = timeoutSec
        self._sock: socket.socket | None = None
        self._warnedSizes: set[int] = set()
        self._consecutiveErrors = 0
        self._RECONNECT_THRESHOLD = 10
        self._fwd = UDPForwarder(forwardTargets, forwardEnabled)

        # stats
        self.lastPacketTime: float = 0.0
        self.packetCount: int = 0
        self.badPacketCount: int = 0

        # rate tracking
        self._rateWindowStart: float = 0.0
        self._rateWindowCount: int = 0
        self._firstPacketLogged: bool = False

    # ── Context manager ─────────────────────────────────────────────────────

    def __enter__(self) -> "TelemetryReceiver":
        # Respect host setting: loopback → IPv4 only, wildcard → dual-stack
        if self._host in ("127.0.0.1", "localhost"):
            self._sock = self._bindIPv4()
        elif self._host in ("0.0.0.0", "::", ""):
            self._sock = self._bindDualStack() or self._bindIPv4()
        else:
            self._sock = self._bindIPv4()
        if self._sock is None:
            raise OSError(f"cannot bind UDP port {self._port} (in use or invalid host {self._host!r})")
        self._sock.settimeout(self._timeout)
        self._rateWindowStart = time.time()
        self._fwd.open()
        return self

    def __exit__(self, *_) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None
        self._fwd.close()

    # ── Public API ──────────────────────────────────────────────────────────

    def receiveLatestPacket(self) -> tuple[bytes | None, tuple | None]:
        """Block up to timeout for a packet, drain queue, return latest.
        Returns (rawBytes, addr) or (None, None) on timeout."""
        try:
            pkt, addr = self._sock.recvfrom(1500)
        except socket.timeout:
            return None, None
        except OSError as e:
            self._consecutiveErrors += 1
            log.warning("UDP recv error (%d/%d): %s",
                        self._consecutiveErrors, self._RECONNECT_THRESHOLD, e)
            if self._consecutiveErrors >= self._RECONNECT_THRESHOLD:
                self._reconnect()
            return None, None

        self._consecutiveErrors = 0
        if self._fwd.active:
            self._fwd.send(pkt)

        # flush stale packets — non-blocking read until empty
        self._sock.setblocking(False)
        try:
            while True:
                pkt, addr = self._sock.recvfrom(1500)
                if self._fwd.active:
                    self._fwd.send(pkt)
        except (BlockingIOError, OSError):
            pass
        finally:
            self._sock.setblocking(True)
            self._sock.settimeout(self._timeout)

        # Validate size BEFORE updating any valid-packet state
        if len(pkt) != EXPECTED_PACKET_SIZE:
            self.badPacketCount += 1
            if len(pkt) not in self._warnedSizes:
                self._warnedSizes.add(len(pkt))
                log.warning("dropped datagram: size=%d peer=%s:%d required=%d",
                            len(pkt), addr[0], addr[1], EXPECTED_PACKET_SIZE)
            return None, None

        # ── Valid packet ────────────────────────────────────────────────────
        self.lastPacketTime = time.time()
        self.packetCount += 1

        # First valid packet notification
        if not self._firstPacketLogged:
            self._firstPacketLogged = True
            log.info("First valid telemetry packet received from %s:%d (%d bytes)",
                     addr[0], addr[1], len(pkt))

        # Periodic packet rate logging
        self._rateWindowCount += 1
        now = time.time()
        elapsed = now - self._rateWindowStart
        if elapsed >= _RATE_LOG_INTERVAL:
            rate = self._rateWindowCount / elapsed
            log.info("Telemetry rate: %.1f packets/sec (total: %d, bad: %d)",
                     rate, self.packetCount, self.badPacketCount)
            self._rateWindowStart = now
            self._rateWindowCount = 0

        return pkt, addr

    # legacy alias for transition period
    def recv_latest(self):
        return self.receiveLatestPacket()

    # ── Socket management ───────────────────────────────────────────────────

    def _bindDualStack(self) -> socket.socket | None:
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.bind(("::", self._port))
            log.info("UDP bind success: [::]:%d (IPv4+IPv6)", self._port)
            return s
        except OSError as e:
            log.debug("dual-stack bind failed, falling back: %s", e)
            return None

    def _bindIPv4(self) -> socket.socket | None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            except OSError:
                pass
            s.bind((self._host, self._port))
            log.info("UDP bind success: %s:%d (IPv4)", self._host, self._port)
            return s
        except OSError as e:
            err_code = getattr(e, 'errno', None) or (e.args[0] if e.args else None)
            if err_code == errno.EADDRINUSE or err_code == 10048:
                log.error("UDP bind FAILED on %s:%d — port already in use. "
                          "Another DHE instance or telemetry app may be running. "
                          "Close other apps using port %d and retry.",
                          self._host, self._port, self._port)
            else:
                log.error("UDP bind FAILED on %s:%d — OS error: %s (errno=%s)",
                          self._host, self._port, e, err_code)
            return None

    def _reconnect(self) -> bool:
        log.info("UDP reconnecting on port %d...", self._port)
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._host in ("127.0.0.1", "localhost"):
            self._sock = self._bindIPv4()
        elif self._host in ("0.0.0.0", "::", ""):
            self._sock = self._bindDualStack() or self._bindIPv4()
        else:
            self._sock = self._bindIPv4()
        if self._sock is None:
            log.warning("UDP reconnect failed: cannot bind port %d", self._port)
            return False
        self._sock.settimeout(self._timeout)
        self._consecutiveErrors = 0
        log.info("UDP reconnected on port %d", self._port)
        return True

    # ── Static test helper ──────────────────────────────────────────────────

    @staticmethod
    def testBind(host: str, port: int) -> tuple[bool, str]:
        """Try binding to the given host:port and immediately release.
        Returns (success, message)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((host, port))
            s.close()
            return True, f"UDP port {port} is available on {host}"
        except OSError as e:
            err_code = getattr(e, 'errno', None) or (e.args[0] if e.args else None)
            if err_code == errno.EADDRINUSE or err_code == 10048:
                return False, (f"UDP port {port} is already in use. "
                               "Another DHE instance or telemetry app may be running.")
            return False, f"UDP bind failed on {host}:{port} — {e}"
