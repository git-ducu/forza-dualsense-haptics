"""DHE — application entry point."""
import argparse
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

# Ensure vendor/ is on sys.path so bundled dependencies are found.
_VENDOR = _ROOT / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

# Project root must be on path for absolute package imports.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Early crash hook
_EARLY_CRASH_LOG = _ROOT / "data" / "crash.log"


def _print_and_write_crash(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        print("\nInterrupted.", file=sys.stderr)
        return
    try:
        _EARLY_CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_EARLY_CRASH_LOG, "w", encoding="utf-8") as f:
            f.write(f"Crash at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass
    print("\nDHE unhandled exception:", file=sys.stderr)
    traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
    print(f"\nCrash log: {_EARLY_CRASH_LOG}", file=sys.stderr)


sys.excepthook = _print_and_write_crash

try:
    from dotenv import load_dotenv
    load_dotenv("./dev.env")
except (ImportError, OSError):
    pass

from config import paths, profile_store as preferences
from config.settings import Settings
from runtime import loop
from runtime.factory import make_backend
from telemetry.receiver import TelemetryReceiver

log = logging.getLogger("dhe")

CRASH_LOG = paths.DATA / "crash.log"


def _excepthook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        print("\nInterrupted.", file=sys.stderr)
        return
    try:
        paths.DATA.mkdir(parents=True, exist_ok=True)
        with open(CRASH_LOG, "w", encoding="utf-8") as f:
            f.write(f"Crash at {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass
    print("\nDHE unhandled exception:", file=sys.stderr)
    traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
    print(f"\nCrash log: {CRASH_LOG}", file=sys.stderr)
    log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))


def setup_logging(debug: bool = False) -> None:
    if os.name == "nt":
        os.system("")  # enable ANSI escapes on Windows CMD
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="\033[92m%(asctime)s %(message)s\033[0m",
        force=True,
    )


def run(s: Settings) -> None:
    with make_backend(s) as ds:
        with TelemetryReceiver(s.udp_host, s.udp_port, s.udp_timeout,
                               s.udp_forward_to, s.udp_forward) as listener:
            log.info("Listening on %s:%d | Ctrl+C to quit", s.udp_host, s.udp_port)
            loop.run(ds, listener, s)


def run_gui(s: Settings) -> None:
    from ui.app import TriggerGUI
    TriggerGUI(s).run()


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def main():
    p = argparse.ArgumentParser(description="DHE — telemetry haptic engine")
    p.add_argument("--host", default=None, help="UDP bind address")
    p.add_argument("--port", type=int, default=None, help="UDP port")
    p.add_argument("--debug", action="store_true", help="Verbose per-packet logs")
    p.add_argument("--headless", action="store_true", help="Disable UI, use console logs")
    args = p.parse_args()

    settings = Settings()
    try:
        preferences.load(settings)
    except preferences.PreferencesError as e:
        print(f"\n{e}", file=sys.stderr)
        if not _confirm(f"Reset {preferences.PATH.name} to defaults? [y/N]: "):
            sys.exit(1)
        preferences.reset_file()
        preferences.load(settings)
    if args.host is not None:
        settings.udp_host = args.host
    if args.port is not None:
        settings.udp_port = args.port

    sys.excepthook = _excepthook

    try:
        if args.headless:
            setup_logging(args.debug)
            run(settings)
        else:
            run_gui(settings)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)


if __name__ == "__main__":
    main()
