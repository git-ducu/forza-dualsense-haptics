# -*- mode: python ; coding: utf-8 -*-
"""DHE PyInstaller spec — single-folder distribution."""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
VENDOR = ROOT / "vendor"

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT), str(VENDOR)],
    binaries=[
        # PortAudio DLL for sounddevice
        (str(VENDOR / "_sounddevice_data" / "portaudio-binaries" / "libportaudio64bit.dll"), "."),
    ],
    datas=[
        # Default preferences template (created at runtime if missing)
        (str(ROOT / "data" / "user_preferences.json.default"), "data"),
    ],
    hiddenimports=[
        # Project packages
        "config",
        "config.settings",
        "config.profile_store",
        "config.paths",
        "config.tuning",
        "config.option_registry",
        "config.macro_registry",
        "config.store",
        "config.profileManager",
        "dsio",
        "dsio.device",
        "dsio.device.controller",
        "dsio.device.hidhide",
        "dsio.audio",
        "dsio.audio.device",
        "dsio.haptics",
        "dsio.haptics.bus_mixer",
        "dsio.haptics.bus",
        "dsio.haptics.mastering",
        "dsio.haptics.mixer",
        "dsio.haptics.renderer",
        "dsio.haptics.transient",
        "dsio.haptics.waveform",
        "dsio.trigger",
        "dsio.trigger.effects",
        "telemetry",
        "telemetry.packet",
        "telemetry.process",
        "telemetry.receiver",
        "telemetry.relay",
        "telemetry.vehicle",
        "telemetry.triggerMap",
        "telemetry.triggerHelpers",
        "telemetry.surfaceEffects",
        "telemetry.dhe_custom",
        "telemetry.haptics",
        "telemetry.haptics.audioEngine",
        "telemetry.haptics.musicalMixer",
        "telemetry.haptics.sourceRegistry",
        "telemetry.haptics.sourceRenderers",
        "telemetry.haptics.transientPresets",
        "runtime",
        "runtime.loop",
        "runtime.factory",
        "runtime.logSetup",
        "runtime.diagnostics",
        "runtime.selftest",
        "ui",
        "ui.app",
        "ui.bridge",
        "ui.components",
        "ui.style",
        "ui.pages",
        "ui.pages.tuningPage",
        "ui.pages.logPage",
        # Vendor libs
        "hid",
        "numpy",
        "psutil",
        "PIL",
        "sounddevice",
        "_sounddevice_data",
        "cffi",
        "dotenv",
        "PySide6",
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "shiboken6",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "pytest",
        "mypy",
        "ruff",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DHE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # windowed (no console window)
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DHE",
)
