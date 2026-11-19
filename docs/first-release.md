# 0.5.0 prototype release scope

The first public release is **0.5.0, marked as a GitHub prerelease**, under MIT at https://github.com/Xadro3/aidaemon. The goal is a small working version that owners can use and give feedback on while it is refined. It is not a claim of broad hardware/distro certification.

## Included

Native Steam tab without Decky, controller navigation, package-power presets/custom limits, RGB, telemetry, reversible A1M Wi-Fi/keyboard-wake mitigations, optional global power/RGB persistence, native package ownership, graphical setup/repair/uninstall, persistent service startup and reviewed diagnostic export.

CachyOS KDE on MSI Claw A1M / Ultra 5 135H is the tested target. Other A1M CPU variants are untested; other Claw generations and Bazzite/SteamOS installation are blocked. Their guidance is respected by avoiding unsupported host modifications rather than claiming untested compatibility. [Distribution review](distribution-guidance.md)

## Publication checklist

- [x] Native package builds as a regular user and desktop/service files validate.
- [x] Package install, repair, integration removal, pacman removal and reinstall exercised on the Claw.
- [x] Boot/login services enabled; service restart and sidebar reconnection exercised.
- [x] Opt-in settings save and service-start restore exercised on actual hardware.
- [x] Both kernel RGB names supported; bounded writes and restoration paths tested.
- [x] Allowlisted support report review/export implemented and report contents inspected.
- [x] MIT license, security/trust boundary, support matrix, upstream issue review and pinned-action CI added.
- [x] Installed graphical repair flow confirmed by the owner.
- [x] Clean source/package/installer reviewed and checksummed; release commit `833a02073e63725335b2cfa22c4772e4ef97c544` passed GitHub CI.
- [x] Extracted setup launcher and repair confirmed by the owner on the existing Claw installation. Fresh-machine installation and exact trust prompt behavior remain untested.
- [x] Repository private vulnerability reporting enabled.
- [x] GitHub prerelease published with all six public asset downloads verified against local hashes.

Published release: https://github.com/Xadro3/A1Daemon/releases/tag/v0.5.0. This validation record was updated after publication; the versioned release assets and tag remain unchanged.

## Feedback-led validation after the prototype

Repeated AC/battery sleep cycles, long-duration drain/residency, full reboot/upgrade campaigns, more games, external controllers and physical saved-profile restore across suspend. Record counts and durations. Small-sample sleep success remains provisional in the release notes.

Open upstream controller-resume issues remain monitored. Automatic controller/audio resets, fan/EC controls, kernel/BIOS/GPU-driver switching, fingerprint support, FPS overlays, per-game profiles and broader distro packaging are deferred. They should not delay feedback on the working prototype or be added as speculative default workarounds.
