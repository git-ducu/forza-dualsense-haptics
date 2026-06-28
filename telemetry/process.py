"""Exit when the Forza Horizon process disappears. Cross-platform: Windows + Linux/Proton
(Proton runs the Windows binary, so the process name is the same on both)."""
import logging
import os
import time

import psutil

log = logging.getLogger("dhe")


class ProcessWatcher:
    def __init__(self, name_contains=("forza",), poll_interval_s: float = 1.0):
        self.needles = tuple(n.lower() for n in name_contains)
        self.poll_interval = poll_interval_s
        self._last_check = 0.0
        self._matched = None  # actual process name we locked onto

    def _find(self) -> str | None:
        # MARK: per-process try/except - psutil can raise on protected/vanishing procs
        try:
            iterator = psutil.process_iter(["name", "exe"])
        except Exception as e:
            log.warning("process_iter failed: %s", e)
            return None
        for p in iterator:
            try:
                name = p.info.get("name") or ""
                exe_base = os.path.basename(p.info.get("exe") or "")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                continue
            except Exception:
                continue
            haystack = (name + " " + exe_base).lower()
            if any(needle in haystack for needle in self.needles):
                return name or exe_base
        return None

    def should_exit(self) -> bool:
        """True once the watched process has been seen and then disappeared.
        Throttled to one real check per poll_interval_s."""
        now = time.monotonic()
        if now - self._last_check < self.poll_interval:
            return False
        self._last_check = now
        # MARK: never let a psutil/OS error kill the main loop
        try:
            found = self._find()
        except Exception as e:
            log.warning("ProcessWatcher._find crashed: %s", e)
            return False
        if found and not self._matched:
            self._matched = found
            log.info("Detected game process '%s' - will exit when it closes.", found)
            return False
        if self._matched and not found:
            log.info("Game process '%s' closed.", self._matched)
            return True
        return False
