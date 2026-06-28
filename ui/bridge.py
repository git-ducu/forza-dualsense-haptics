# -*- coding: utf-8 -*-
# ── UI Bridge — backend↔frontend communication ──────────────────────────────
#
# Replaces the original _QueueLogHandler pattern with a proper pub/sub bridge.
# All UI code talks to the backend exclusively through this layer.

from __future__ import annotations
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class EngineStatus:
    """Snapshot of backend state for UI display."""
    controllerConnected: bool = False
    controllerName: str = ""
    telemetryActive: bool = False
    packetRate: float = 0.0
    currentProfile: str = "default"
    hapticAudioActive: bool = False
    lastError: str = ""


class LogBridge(logging.Handler):
    """Captures log records for display in the UI log page."""

    def __init__(self, maxSize: int = 2000):
        super().__init__()
        self._queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=maxSize)
        self._listeners: list[Callable[[logging.LogRecord], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(record)
            except queue.Empty:
                pass
        for cb in self._listeners:
            try:
                cb(record)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[logging.LogRecord], None]) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[logging.LogRecord], None]) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    def drain(self, limit: int = 200) -> list[logging.LogRecord]:
        # Pull up to `limit` records from the queue
        records = []
        for _ in range(limit):
            try:
                records.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return records


class UIBridge:
    """Central bridge between UI and engine threads.

    UI pages call methods here; the bridge forwards to the engine thread.
    Engine pushes status back via updateStatus().
    """

    def __init__(self):
        self._status = EngineStatus()
        self._statusLock = threading.Lock()
        self._commandQueue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._resultQueue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.logBridge = LogBridge()

    @property
    def status(self) -> EngineStatus:
        with self._statusLock:
            return self._status

    def updateStatus(self, **kwargs) -> None:
        # Called by engine thread to push state updates
        with self._statusLock:
            for k, v in kwargs.items():
                if hasattr(self._status, k):
                    setattr(self._status, k, v)

    def sendCommand(self, command: str, payload: Any = None) -> None:
        # Queue a command for the engine to process
        self._commandQueue.put_nowait((command, payload))

    def pollCommands(self) -> list[tuple[str, Any]]:
        # Called by engine thread to drain pending commands
        cmds = []
        while not self._commandQueue.empty():
            try:
                cmds.append(self._commandQueue.get_nowait())
            except queue.Empty:
                break
        return cmds

    # ── Convenience command senders (called by UI pages) ───────────────────

    def requestTriggerCheck(self) -> None:
        self.sendCommand("triggerCheck")

    def requestHapticChannelScan(self) -> None:
        self.sendCommand("hapticChannelScan")

    def requestHapticChannelTest(self, channel: int) -> None:
        self.sendCommand("hapticChannelTest", channel)

    def requestHapticTextureTest(self, kind: str) -> None:
        self.sendCommand("hapticTextureTest", kind)

    def requestHapticDeviceList(self) -> None:
        self.sendCommand("hapticDeviceList")

    def requestTriggerVibrate(self, freq: float, amp: int) -> None:
        self.sendCommand("triggerVibrate", {"freq": freq, "amp": amp})

    def requestTriggerOff(self) -> None:
        self.sendCommand("triggerOff")

    # ── Result delivery (engine → UI) ─────────────────────────────────────

    def pushResult(self, resultType: str, data: Any = None) -> None:
        """Engine pushes async results back to the UI."""
        self._resultQueue.put_nowait((resultType, data))

    def pollResults(self) -> list[tuple[str, Any]]:
        """UI drains results (call from QTimer on main thread)."""
        results = []
        while not self._resultQueue.empty():
            try:
                results.append(self._resultQueue.get_nowait())
            except queue.Empty:
                break
        return results
