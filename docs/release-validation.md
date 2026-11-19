# 0.5.0 prototype validation

Tested on 19 November 2026 on MSI Claw A1M / Ultra 5 135H / MS-1T41, BIOS E1T41IMS.10F, CachyOS deckify kernel 7.2.11-1, Mesa 26.2.5, InputPlumber 0.83.1 and Steam client build 1794536281.

## Completed

- 41 Python tests passed on Linux: hardware guards, bounded writes, rollback, RAPL counter wrap, CPU accounting, DRM client deduplication, both RGB kernel names, compatibility ownership/rollback, OS installation boundaries, preferences and API authorization.
- JavaScript fixtures passed for Steam module discovery, React 19 portals/fibers, cleanup, native event forwarding, navigation origin/channel/focus gates, hidden/disabled controls, sliders, dropdown change events and repeat suppression.
- Actual native Steam focus/D-pad/A events reached the embedded panel; physical D-pad navigation was confirmed by the owner during playtesting.
- Owner playtesting reported good power-limit, RGB and monitoring results. A steady green RGB test was explicitly confirmed visible. These are initial usability results, not independent power-meter calibration or game benchmarks.
- Standard package built successfully with makepkg as a regular user on CachyOS. Source SHA-256 validated. Desktop entries validated. System and user service units validated with systemd-analyze.
- On-device package install, integration setup, repair, integration removal, pacman removal and reinstall passed. Pacman reported no changed package files immediately after install. Existing compatibility state was preserved/restored.
- The packaged service ran with the declared capability restrictions. API and CEF listeners were verified on loopback only.
- Actual opt-in preference writes and service-start restore succeeded while preserving the owner's current power/RGB values. Test preferences were cleared afterward; persistence was left opt-in.
- Persistent system service and login sidebar service were enabled. Service restart/reconnect was exercised. A full reboot was not performed during this release work.
- Allowlisted diagnostics exported successfully, with no tokens, Wi-Fi identifiers or raw journals.
- The owner opened the installed graphical Setup and Repair application and confirmed that default graphical repair, including authorization, completed successfully.
- The owner opened the extracted release's A1Daemon-Setup.desktop launcher on the existing Claw installation and confirmed that launcher and install/repair completed successfully.

## Outstanding / explicit limits

- The extracted portable launcher and repair passed owner testing on the existing installation. A fresh machine's first installation remains untested; the exact desktop trust prompt behavior was not separately reported.
- Resume-triggered saved-profile restore has implementation/unit coverage for preferences, but has not been exercised through a controlled physical suspend with saved settings.
- Sleep has initial owner-reported success with minimal sample size. No reliable failure rate, overnight drain or S0ix residency claim is made.
- No repeated reboot/upgrade campaign, independent power measurement, broad game performance matrix or external-controller matrix.
- Bazzite/SteamOS installation is deliberately blocked; it is not validated or advertised as supported.

The release is labelled **0.5.0 prototype / prerelease**. These limits should remain in its GitHub release notes and support matrix. Feedback is used to refine it; open upstream issues remain monitored rather than attracting speculative automatic workarounds.
