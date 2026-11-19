# A1Daemon 0.5.0

**Prototype controls and integration for MSI Claw A1M on CachyOS.** Power, lighting and monitoring live in a dedicated Claw tab in Steam's existing Quick Access sidebar. No Decky dependency.

This is an independent MIT-licensed project, not endorsed by MSI, Valve, CachyOS or Bazzite. Version 0.5 is an early working release for feedback, with explicit limitations. [Validation record](docs/release-validation.md) · [Support matrix](docs/support-matrix.md) · [Security and system changes](SECURITY.md)

## Install without a terminal

The 0.5 installer targets **CachyOS KDE on Claw A1M / MS-1T41**. Ultra 5 135H is the tested CPU. Bazzite, SteamOS and other Claw generations are deliberately blocked until their host integration is separately tested; setup never disables read-only protection.

1. In Desktop Mode, download `A1Daemon-0.5.0-CachyOS-Setup.zip` from the [GitHub release](https://github.com/Xadro3/aidaemon/releases).
2. Extract the archive and open **A1Daemon-Setup.desktop**. KDE may ask you to trust/allow the launcher; confirm only for a release you downloaded from this repository.
3. Approve installation through the normal OS authorization dialog. The release includes its native package; pacman owns the installed files.
4. In **A1Daemon Setup and Repair**, choose **Install or repair integration**, select the workarounds/sidebar options, and approve the system configuration prompt.
5. Restart Steam yourself when convenient, then enter Big Picture. Setup does not close an active game. Local CEF debugging is required for the tab and can stop working after a Steam update; the standalone panel remains available.

The runtime has no pip/npm/Git dependency or online account requirement. Missing distro dependencies may need the package manager's network access. Setup uses KDE dialogs and polkit, never an application-owned password field. Release checksums are supplied for integrity, not as an independent publisher signature.

## Use

Open Quick Access and select the **Claw lightning icon**. Press **Right** to enter the panel. Up/Down moves the blue highlight; Left/Right adjusts sliders/dropdowns or moves between buttons; A activates; B follows Steam's normal back navigation. Touch and keyboard also work. RGB channel sliders avoid requiring a touch-only colour picker.

- **Power:** Quiet 10/15 W, Balanced 18/22 W, Performance 25/28 W, and custom sustained/boost limits. The prototype policy is 6–28 W. It is a package budget shared by CPU/GPU, not wall draw. Readback is displayed; other power managers can override limits.
- **Lighting:** On/Off, colour, five kernel effects, brightness and speed. Dynamic effects use their own colours. Changes require Apply.
- **Monitoring:** package watts, battery charge/discharge flow, CPU utilization, RAM, package temperature, GPU clocks and i915 render-engine activity. GPU activity is not a combined GPU/media percentage. FPS is not integrated. Charging watts are not whole-device consumption.
- **Remember:** optional per-section checkbox to save applied power/RGB settings for service startup and detected resume. It is off by default. Saved values are validated through the same hardware controls. Resume persistence still needs broader physical-cycle testing.

Desktop application entries provide **A1Daemon Claw Control** and **A1Daemon Setup and Repair**. The latter offers support-report review/export and uninstall.

## Compatibility workarounds

Optional setup applies a board-scoped Wi-Fi D3cold restriction for Intel PCI 8086:272b and disables wake permission for the identified internal i8042 keyboard. They run at boot and before sleep, preserve original values, and have an uninstall path. Keyboard/volume wake is disabled by the selected workaround; power-button wake configuration is unchanged.

Sleep has initial owner-reported success with a **small sample size**. There is no claim of measured overnight drain or complete suspend reliability. No fan/EC registers, kernel, GPU driver binding, boot arguments, global PCI policy or controller daemon is replaced. [Community issue review](docs/community-issues.md)

## Repair, updates and removal

Use **A1Daemon Setup and Repair** to reapply integration or remove it. Updates use a newly downloaded release package and the same setup flow. The OS package manager tracks runtime files; systemd tracks services. Existing independently installed workarounds are preserved. Saved preferences remain under `/var/lib/a1daemon` after removal for reinstall, and can be deleted by an administrator if no longer wanted.

If setup created Steam's debugging marker, graphical uninstall removes it. A Steam restart is required to end the current debugging session and clear any remaining in-memory tab. Removing integration does not automatically reset the power/RGB values most recently applied to hardware.

## Tested and remaining limits

- CachyOS deckify 7.2.11-1, BIOS E1T41IMS.10F, Mesa 26.2.5, InputPlumber 0.83.1 and Steam client 1794536281 on an Ultra 5 Claw A1M.
- 41 Linux Python tests plus JavaScript adapter/navigation fixtures; native package install/repair/uninstall/reinstall and saved-settings restore exercised on-device.
- Physical D-pad and power/RGB/monitoring passed initial owner playtesting. Full reboot, repeated upgrade/sleep campaigns and broad game/controller matrices remain outstanding.
- A1Daemon preserves InputPlumber ownership. Controller recovery after resume, audio resets, gyro configuration, display tuning, fan curves, per-game profiles and broader distro support are deferred.

See [release validation](docs/release-validation.md) for the exact distinction between automated checks, on-device tests and owner reports.

## Development

Python 3.11+ and Node for JavaScript checks; no runtime dependency installation is needed for the unit suites:

```sh
python -m unittest discover -s tests -v
node tests/test_adapter.cjs
node tests/test_navigation.cjs
python packaging/build_release.py
```

The complete suite needs Linux. Source archives are normalized and checksummed; they exclude raw baselines, developer SSH tools and private logs. Build the generated PKGBUILD with makepkg as a normal user, then create the setup archive with `python packaging/build_release.py --package <package-file>`. [Contributing](CONTRIBUTING.md) · [Distribution guidance review](docs/distribution-guidance.md) · [Third-party interfaces](THIRD_PARTY.md) · [MIT license](LICENSE)

Maintainers: keep private vulnerability reporting enabled, preserve explicit support boundaries and review the exact artifacts before publishing a prerelease.
