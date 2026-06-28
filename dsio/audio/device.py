"""Audio device discovery for the DualSense haptic-audio backend."""
from __future__ import annotations

from dataclasses import dataclass
import logging

log = logging.getLogger("dhe")


@dataclass
class HapticDeviceInfo:
    index: int
    name: str
    channels: int
    default_samplerate: int
    hostapi: str = ""

    @property
    def label(self) -> str:
        api = f" [{self.hostapi}]" if self.hostapi else ""
        return f"{self.index}: {self.name} ({self.channels}ch @ {self.default_samplerate}Hz){api}"


def _sd():
    try:
        import sounddevice as sd
        return sd
    except ImportError as exc:
        raise RuntimeError("sounddevice is not installed. Run setup_vendor.bat again.") from exc


def list_output_devices(min_channels: int = 1) -> list[HapticDeviceInfo]:
    sd = _sd()
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    out: list[HapticDeviceInfo] = []
    for idx, d in enumerate(devices):
        ch = int(d.get("max_output_channels", 0) or 0)
        if ch < int(min_channels):
            continue
        hostapi_name = ""
        try:
            hostapi_name = str(hostapis[int(d.get("hostapi", 0))].get("name", ""))
        except (IndexError, KeyError, TypeError):
            pass
        out.append(HapticDeviceInfo(
            index=idx,
            name=str(d.get("name", f"Device {idx}")),
            channels=ch,
            default_samplerate=int(float(d.get("default_samplerate", 48000) or 48000)),
            hostapi=hostapi_name,
        ))
    return out


def _device_score(d: HapticDeviceInfo) -> tuple[int, int, int, int]:
    """Lower score is better. Prefer USB DualSense-like, WASAPI, 48k, 4ch.

    The same DualSense appears through MME/DirectSound/WASAPI/WDM-KS. WASAPI
    4ch @ 48000Hz is the most predictable default for PCM haptics. WDM-KS can
    feel sharp but is less friendly, so it stays second.
    """
    name = d.name.lower()
    api = d.hostapi.lower()
    is_dual = 0 if any(k in name for k in ("dualsense", "wireless controller", "playstation")) else 1
    if "wasapi" in api:
        api_rank = 0
    elif "wdm" in api or "ks" in api:
        api_rank = 1
    elif "directsound" in api:
        api_rank = 2
    elif "mme" in api:
        api_rank = 3
    else:
        api_rank = 4
    sr_rank = 0 if abs(int(d.default_samplerate) - 48000) <= 1 else 1
    ch_rank = 0 if int(d.channels) == 4 else 1
    return (is_dual, api_rank, sr_rank, ch_rank)


def dualsense_candidates() -> list[HapticDeviceInfo]:
    keys = ("dualsense", "wireless controller", "controller", "playstation")
    devices = list_output_devices(min_channels=4)
    cand = [d for d in devices if any(k in d.name.lower() for k in keys)]
    return sorted(cand or devices, key=_device_score)


def find_device(name_or_index: str | int | None, min_channels: int = 4) -> HapticDeviceInfo | None:
    devices = list_output_devices(min_channels=min_channels)
    if name_or_index is None or str(name_or_index).strip() == "":
        cand = dualsense_candidates()
        return cand[0] if cand else None
    raw = str(name_or_index).strip()
    try:
        want = int(raw.split(":", 1)[0])
        for d in devices:
            if d.index == want:
                return d
    except (ValueError, IndexError):
        pass
    low = raw.lower()
    for d in devices:
        if low == d.name.lower() or low in d.name.lower() or low in d.label.lower():
            return d
    return None
