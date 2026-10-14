# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2-neil.1] - 2026-10-14

### Fixed
- Heat/cool setpoint writes no longer revert ~20s later. Setpoints are snapped
  to the nearest whole degF and sent as 2-decimal Celsius (67F -> 19.44), the
  encoding the thermostat accepts; heat and cool are always sent together.
- Enforce the app's limits (heat 40-90F, cool 50-93F) and 3F minimum deadband
  by pushing the companion setpoint.

## [0.1.1] - 2026-08-23

### Fixed
- Fan running binary sensor now reads "on" while heating or cooling is active.
  The device's `isFanOn` flag only tracks the standalone fan (On/Circulate) and
  stays false during a heat/cool call, so the sensor previously showed the fan
  off while the blower was clearly running. It now reflects the blower by also
  considering the heating/cooling equipment state.

## [0.1.0] - 2026-08-23

First release — a simple, functional integration for cloud-only Wi-Fi Aprilaire
thermostats (verified against the **8920W**).

### Added
- Climate entity: current temperature and humidity; heat / cool / auto / off modes;
  single and dual (heat + cool) setpoints; fan modes (auto / on / circulate); live
  HVAC action (heating / cooling / fan / idle).
- Humidifier controls (when the system has one): a **switch** (on/off) and a
  **number** for the 1–7 dial level (Aprilaire's `autoModeSetpoint`). Setting a
  level turns the humidifier on at that level; the device reports level 0 while off.
- Sensors: indoor temperature, indoor humidity, outdoor temperature (when present),
  and Wi-Fi signal (diagnostic).
- Per-equipment **running** binary sensors — fan, heating, cooling, and humidifier —
  each with the `running` device class so it gets its own on/off history, logbook
  entries, and runtime.
- Config flow with email/password login, multi-device discovery/picker, and reauth.
- Optimistic writes with a delayed reconcile so UI changes appear immediately and
  are confirmed on the device's next cloud check-in.
- Polling aligned to wall-clock multiples of the scan interval (`:00` each minute
  by default) instead of drifting to an arbitrary offset.
- Local dev box (`devbox/`) and a unit + HA-harness test suite.

[Unreleased]: https://github.com/Grygon/HA-Aprilaire-Cloud/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Grygon/HA-Aprilaire-Cloud/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Grygon/HA-Aprilaire-Cloud/releases/tag/v0.1.0
