"""Small PCM waveform helpers for DualSense audio-haptics experiments.

The output range is float32 -1.0..1.0. The caller is responsible for channel
mapping and device I/O.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

try:
    import numpy as np
except ImportError:  # pragma: no cover - vendor/runtime dependent
    np = None


TAU = math.tau


@dataclass(slots=True)
class Osc:
    """Oscillator with phase tracking for continuous waveform generation.
    
    Uses __slots__ for memory optimization (80+ instances in HapticAudioEngine).
    """
    phase: float = 0.0

    def sine(self, frames: int, sample_rate: int, freq: float):
        if np is None:
            out = [0.0] * frames
            step = TAU * float(freq) / float(sample_rate)
            ph = self.phase
            for i in range(frames):
                out[i] = math.sin(ph)
                ph += step
                if ph >= TAU:
                    ph -= TAU
            self.phase = ph
            return out
        idx = np.arange(frames, dtype=np.float32)
        phase = self.phase + TAU * float(freq) * idx / float(sample_rate)
        out = np.sin(phase).astype(np.float32)
        self.phase = float((phase[-1] + TAU * float(freq) / float(sample_rate)) % TAU) if frames else self.phase
        return out

    def harmonic(self, frames: int, sample_rate: int, freq: float,
                 overtones: tuple[float, ...] = (1.0, 0.4, 0.15)):
        """Generate a tone with harmonic overtones for richer tactile feel.

        overtones[0] = fundamental amplitude, [1] = 2nd harmonic, [2] = 3rd, etc.
        This produces the kind of rich waveform that makes LRA actuators feel
        more like real impacts rather than synthetic sine buzzes.
        """
        if np is None:
            return self.sine(frames, sample_rate, freq)
        idx = np.arange(frames, dtype=np.float32)
        out = np.zeros(frames, dtype=np.float32)
        base_phase = self.phase
        for i, amp in enumerate(overtones):
            if amp == 0.0:
                continue
            h = i + 1
            phase = base_phase * h + TAU * float(freq) * h * idx / float(sample_rate)
            out += np.sin(phase).astype(np.float32) * float(amp)
        # Normalize so peak doesn't exceed sum of overtones
        total = sum(abs(a) for a in overtones) or 1.0
        out /= total
        # Advance phase for fundamental only
        self.phase = float((base_phase + TAU * float(freq) * frames / float(sample_rate)) % TAU)
        return out

    def sub_punch(self, frames: int, sample_rate: int, freq: float = 42.0,
                  attack_ms: float = 1.5, sustain_ms: float = 25.0):
        """Sub-bass impact burst: fast attack, short sustain, harmonic content.

        Designed for DualSense LRA sweet spot (30-60Hz fundamental + harmonics).
        """
        sig = self.harmonic(frames, sample_rate, freq, (1.0, 0.55, 0.2, 0.08))
        env = envelope_preset(frames, sample_rate, "impact", attack_ms, sustain_ms)
        if np is not None:
            return sig * env
        return [s * e for s, e in zip(sig, env)]


def soft_clip(x):
    if np is None:
        return [max(-1.0, min(1.0, v / (1.0 + abs(v)))) for v in x]
    return np.tanh(x).astype(np.float32)


def envelope(frames: int, sample_rate: int, attack_ms: float = 4.0, release_ms: float = 12.0):
    if np is None:
        env = [1.0] * frames
        a = max(1, int(sample_rate * attack_ms / 1000.0))
        r = max(1, int(sample_rate * release_ms / 1000.0))
        for i in range(min(a, frames)):
            env[i] = i / max(1, a)
        for i in range(min(r, frames)):
            env[frames - 1 - i] = min(env[frames - 1 - i], i / max(1, r))
        return env
    env = np.ones(frames, dtype=np.float32)
    a = max(1, int(sample_rate * attack_ms / 1000.0))
    r = max(1, int(sample_rate * release_ms / 1000.0))
    if frames:
        aa = min(a, frames)
        rr = min(r, frames)
        env[:aa] *= np.linspace(0.0, 1.0, aa, endpoint=True, dtype=np.float32)
        env[-rr:] *= np.linspace(1.0, 0.0, rr, endpoint=True, dtype=np.float32)
    return env


# Envelope presets tuned for DualSense LRA characteristics.
# Impact: near-instant attack so the actuator "punches", moderate decay.
# Shift: slightly softer attack (mechanical engagement feel), quick release.
# Road: gentle fade in/out to avoid click artifacts on continuous textures.
# Idle: very gentle, long transitions to avoid percussive artifacts.
_ENVELOPE_PRESETS = {
    "impact":  (1.0, 30.0),
    "shift":   (2.0, 18.0),
    "road":    (6.0, 14.0),
    "idle":    (12.0, 25.0),
    "click":   (0.5, 8.0),
    "crack":   (0.3, 5.0),
}


def envelope_preset(frames: int, sample_rate: int, preset: str = "road",
                    attack_override: float | None = None,
                    release_override: float | None = None):
    """Get an envelope shaped for a specific haptic event type."""
    defaults = _ENVELOPE_PRESETS.get(preset, _ENVELOPE_PRESETS["road"])
    atk = attack_override if attack_override is not None else defaults[0]
    rel = release_override if release_override is not None else defaults[1]
    return envelope(frames, sample_rate, atk, rel)


def noise_burst(frames: int, sample_rate: int, bandwidth_hz: float = 400.0,
                amount: float = 1.0):
    """Band-limited noise burst for high-frequency edge/crack texture.

    bandwidth_hz controls the cutoff — lower values give a darker rumble,
    higher values give a sharp crack. The DualSense LRA responds best under 500Hz
    so bandwidth above that mostly wastes energy.
    """
    if np is None:
        import random
        return [(random.random() * 2.0 - 1.0) * amount for _ in range(frames)]
    # Generate white noise then apply a simple 1-pole lowpass
    raw = np.random.random(frames).astype(np.float32) * 2.0 - 1.0
    if bandwidth_hz < 20000.0 and sample_rate > 0:
        # RC lowpass: coefficient = dt / (RC + dt) where RC = 1/(2π·fc)
        rc = 1.0 / (TAU * min(float(bandwidth_hz), float(sample_rate) * 0.45))
        dt = 1.0 / float(sample_rate)
        alpha = float(dt / (rc + dt))
        # perf: approximate 1-pole IIR via short FIR convolution.
        # The impulse response of y[n]=alpha*x[n]+(1-alpha)*y[n-1] is
        # h[k] = alpha * (1-alpha)^k.  Truncate at -60dB (negligible tail).
        b = 1.0 - alpha
        if b > 0.001:
            # Number of taps for -60dB attenuation: (1-alpha)^N < 0.001
            n_taps = min(frames, max(4, int(-6.9 / np.log(b)) + 1))
            kernel = alpha * (b ** np.arange(n_taps, dtype=np.float32))
            raw = np.convolve(raw, kernel, mode="full")[:frames].astype(np.float32)
        else:
            raw *= alpha  # alpha ≈ 1: nearly unfiltered
    # Normalize peak to ~1.0 then scale
    peak = float(np.max(np.abs(raw))) or 1.0
    return (raw / peak * float(amount)).astype(np.float32)


def noise(frames: int, amount: float = 1.0):
    if np is None:
        import random
        return [(random.random() * 2.0 - 1.0) * amount for _ in range(frames)]
    return (np.random.random(frames).astype(np.float32) * 2.0 - 1.0) * float(amount)


def pulse_train(frames: int, sample_rate: int, hz: float, duty: float = 0.45):
    if np is None:
        out = [0.0] * frames
        period = max(1, int(sample_rate / max(1.0, hz)))
        on = max(1, int(period * duty))
        for i in range(frames):
            out[i] = 1.0 if (i % period) < on else 0.0
        return out
    period = max(1, int(sample_rate / max(1.0, hz)))
    on = max(1, int(period * duty))
    idx = np.arange(frames, dtype=np.int32) % period
    return (idx < on).astype(np.float32)


def make_test_texture(kind: str, sample_rate: int, duration_s: float, gain: float, freq: float | None = None):
    frames = max(1, int(sample_rate * duration_s))
    kind = (kind or "tone").lower()
    gain = max(0.0, float(gain))  # EXTREME: no cap
    osc = Osc()
    if kind in ("tone", "sine"):
        sig = osc.harmonic(frames, sample_rate, float(freq or 120.0), (1.0, 0.3, 0.1))
    elif kind == "kerb":
        base = osc.harmonic(frames, sample_rate, 95.0, (1.0, 0.45, 0.12))
        gate = pulse_train(frames, sample_rate, 22.0, 0.45)
        sig = base * gate if np is not None else [a*b for a, b in zip(base, gate)]
    elif kind == "gravel":
        low = osc.harmonic(frames, sample_rate, 58.0, (1.0, 0.5, 0.2))
        n = noise_burst(frames, sample_rate, 280.0, 0.55)
        sig = low * 0.50 + n * 0.50 if np is not None else [a*0.50+b*0.50 for a, b in zip(low, n)]
    elif kind == "puddle":
        high = osc.harmonic(frames, sample_rate, 180.0, (1.0, 0.6, 0.25))
        n = noise_burst(frames, sample_rate, 350.0, 0.45)
        sig = high * 0.60 + n * 0.40 if np is not None else [a*0.60+b*0.40 for a, b in zip(high, n)]
    elif kind in ("thump", "collision", "bump"):
        sig = osc.sub_punch(frames, sample_rate, 45.0, 1.0, 35.0)
    elif kind == "shift":
        # 150Hz square wave × 4 cycles (27ms) = strong "탁" impact.
        # 4 cycles = near-full LRA displacement, too short for buzz feel.
        t_arr = np.arange(frames, dtype=np.float32) / float(sample_rate)
        burst_dur = 4.0 / 150.0  # 4 full cycles = 26.7ms
        sig = np.sign(np.sin(2.0 * np.pi * 150.0 * t_arr))
        sig *= (t_arr < burst_dur).astype(np.float32)
        return np.clip(sig, -1.0, 1.0).astype(np.float32)
    else:
        sig = noise_burst(frames, sample_rate, 320.0, 0.6)
    env = envelope_preset(frames, sample_rate, "impact" if kind in ("thump", "collision", "bump", "shift") else "road")
    sig = sig * env * gain if np is not None else [a*b*gain for a, b in zip(sig, env)]
    return soft_clip(sig)


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def micro_delay(signal, sample_rate: int, delay_ms: float):
    """Apply a fractional-sample delay (0.3–2.0 ms) for spatial L/R cues.

    DualSense LRAs are ~10cm apart. A 1ms delay ≈ 34cm path difference which
    is exaggerated but perceptually effective on a handheld device. The delay
    uses linear interpolation to avoid allocating an FFT.
    """
    if np is None or delay_ms <= 0.0:
        return signal
    delay_samples = float(delay_ms) * float(sample_rate) / 1000.0
    n_whole = int(delay_samples)
    frac = delay_samples - n_whole
    if n_whole >= len(signal):
        return np.zeros_like(signal)
    out = np.zeros_like(signal)
    if frac < 1e-6:
        out[n_whole:] = signal[:len(signal) - n_whole]
    else:
        # Linear interpolation between integer delay positions
        end = len(signal) - n_whole - 1
        if end > 0:
            out[n_whole + 1:n_whole + 1 + end] = (
                signal[:end] * (1.0 - frac) + signal[1:end + 1] * frac
            )
    return out.astype(np.float32)


def apply_spatial(left, right, sample_rate: int, width: float = 1.0,
                  lr_bias: float = 0.0, delay_ms: float = 0.8):
    """Apply spatial processing to a stereo pair.

    width: 0.0 = mono, 1.0 = normal, >1.0 = exaggerated separation
    lr_bias: -1.0 = source from left, +1.0 = source from right
    delay_ms: micro-delay applied to the far side for direction cue
    """
    if np is None:
        return left, right
    w = max(0.0, min(2.0, float(width)))
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    out_l = mid + side * w
    out_r = mid - side * w
    # Apply micro-delay based on bias direction
    if abs(lr_bias) > 0.05 and delay_ms > 0.0:
        d = abs(lr_bias) * float(delay_ms)
        if lr_bias > 0:
            out_l = micro_delay(out_l, sample_rate, d)
        else:
            out_r = micro_delay(out_r, sample_rate, d)
    return out_l.astype(np.float32), out_r.astype(np.float32)
