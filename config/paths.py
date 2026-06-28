"""Filesystem path constants for all execution modes.

All modules import paths from here. Supports:
    - Source execution: ROOT = project directory
    - PyInstaller frozen: ROOT = sys._MEIPASS

Writable user data (DATA) lives next to the EXE when frozen so settings
persist across launches; in source mode it sits under ROOT.
"""
import sys
from pathlib import Path

# ROOT: project root containing app.py + bundled assets.
# config/ is one level below ROOT.
ROOT = Path(__file__).resolve().parent.parent

# DATA: writable user data dir (user_preferences.json, crash.log, ...).
# Frozen EXE -> next to executable (MEIPASS would be wiped on exit).
# Source run -> data/ under ROOT.
if getattr(sys, "frozen", False):
    DATA = Path(sys.executable).resolve().parent / "data"
else:
    DATA = ROOT / "data"

