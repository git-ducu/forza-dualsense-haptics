"""Forza-specific transient bank configuration."""
from dsio.haptics.transient import TransientTracker, HapticTransientBank


def make_forza_transient_bank() -> HapticTransientBank:
    """Create a transient bank tuned for Forza Horizon haptics."""
    return HapticTransientBank(trackers={
        "shift": TransientTracker(threshold=0.045, release_ms=85.0),
        "impact": TransientTracker(threshold=0.050, release_ms=125.0),
        "bump": TransientTracker(threshold=0.045, release_ms=95.0),
        "grip": TransientTracker(threshold=0.060, release_ms=70.0),
        "accel_onset": TransientTracker(threshold=0.08, release_ms=120.0),
        "decel_onset": TransientTracker(threshold=0.08, release_ms=100.0),
        "shift_engage": TransientTracker(threshold=0.05, release_ms=130.0),
    })
