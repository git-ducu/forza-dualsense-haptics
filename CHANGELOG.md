# Changelog

## v1.03 — Driving Feedback Triggers

### Added
- Predictive ABS trigger feedback (L2)
- Throttle traction feedback (R2)
- Drift fade behavior for R2 wheelspin
- Slip onset pulse and grip recovery transients (R2)
- Redline pre-warning pulse (R2)
- Idle engine feel at standstill (R2)

### Fixed
- Trigger fail-safe: sends OFF/OFF on runtime errors instead of leaving stale resistance
- Protected telemetry sink from crashing the driving loop
- Updated release package version

### Notes
- **R2 throttle, wheelspin, and drift behavior changed from v1.02.** The priority chain is now: gear shift > idle > redline > rev limiter > slip onset > wheelspin > end-stop wall > throttle resistance.
- L2 priority: gear shift > ABS > engine brake > road texture > end-stop wall > brake resistance.

## v1.02

Initial public release.
