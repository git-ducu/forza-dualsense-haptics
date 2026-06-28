# -*- coding: utf-8 -*-
# ── Config store — JSON serialization for Tuning objects ────────────────────
#
# Handles load/save of tuning profiles to disk. Uses dataclass field
# introspection for automatic schema derivation.

from __future__ import annotations
import json
import logging
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Type, TypeVar

from .tuning import Tuning

log = logging.getLogger("dhe.config")
T = TypeVar("T")


def saveTuning(tuning: Tuning, path: Path) -> None:
    # Serialize Tuning to JSON file
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(tuning)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.debug("Saved tuning to %s", path)


def loadTuning(path: Path) -> Tuning:
    # Deserialize JSON into Tuning, filling missing fields with defaults
    if not path.exists():
        log.info("No tuning file at %s, using defaults", path)
        return Tuning()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _buildDataclass(Tuning, raw)


def _buildDataclass(cls: Type[T], data: dict) -> T:
    # Recursively construct dataclass from dict, ignoring unknown keys
    if not isinstance(data, dict):
        return cls()
    # resolve type hints (handles forward references from __future__ annotations)
    import typing
    hints = typing.get_type_hints(cls)
    kwargs = {}
    for fld in fields(cls):
        if fld.name not in data:
            continue
        val = data[fld.name]
        ftype = hints.get(fld.name)
        if ftype is not None and is_dataclass(ftype):
            kwargs[fld.name] = _buildDataclass(ftype, val)
        else:
            kwargs[fld.name] = val
    return cls(**kwargs)


def exportDefaults(path: Path) -> None:
    # Write a fresh defaults file for reference
    saveTuning(Tuning(), path)
