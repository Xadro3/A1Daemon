# Claw A1M playtest record

Device: MSI Claw A1M, Core Ultra 5 135H, CachyOS. Recorded on 19 November 2026. Reports below describe this device and session, not a compatibility guarantee for other owners.

| Feature | Current evidence | Status |
| --- | --- | --- |
| Power limits | Register writes/readback verified on both RAPL interfaces; user reports good playtest results | Passing initial playtesting; no instrumented sustained-load enforcement test |
| RGB | User confirmed visible steady green, then reported good results with the settings | Passing initial playtesting |
| Monitoring | Live telemetry and sampling logic verified; user reports good results | Passing initial playtesting; accuracy not independently calibrated |
| Sleep | Targeted D3cold/keyboard-wake workarounds installed; user reports sleep seems to work | Provisional: minimal sample, cycle count and duration unspecified |
| D-pad navigation | Original iframe Gamepad API path failed; native Steam bridge deployed, native event tests passed, user confirmed physical navigation works | Passing initial playtesting after fix |

The navigation change retains a native Steam focus target instead of moving browser focus into the iframe. It forwards D-pad and A actions to a matching panel instance, skips hidden/disabled controls, emits input/change events for sliders and dropdowns, and leaves B/system buttons with Steam. The bridge validates the Steam origin and per-instance channel. RGB channel sliders provide a controller path around the browser colour picker.

Remaining sleep validation: repeated short and long cycles on AC and battery, Wi-Fi reconnect, unintended wakeups, fan settling, and measured standby drain/residency. Record the kernel/firmware versions and cycle duration with failures. No cycle count or long-duration result should be inferred from the initial success report.
