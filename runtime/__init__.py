"""Runtime package — lazy imports to avoid heavy startup chain."""


def __getattr__(name: str):
    if name == "Engine":
        from .engine import Engine
        return Engine
    if name == "configureLogging":
        from .logSetup import configureLogging
        return configureLogging
    raise AttributeError(f"module 'runtime' has no attribute {name!r}")


__all__ = ["Engine", "configureLogging"]