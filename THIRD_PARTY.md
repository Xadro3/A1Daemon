# Interfaces and third-party components

The distributed runtime contains original A1Daemon Python/JavaScript/HTML/CSS under MIT. There are no vendored third-party runtime libraries.

- Python, kdialog/Qt, systemd, polkit and the Linux kernel are provided by the distribution under their own licenses. They are not relicensed by this project.
- Existing Linux RAPL, sysfs LED, hwmon, battery and DRM interfaces provide hardware access.
- InputPlumber continues to own the controller. HHD and its Claw implementation informed research but are not bundled or imported.
- Steam is proprietary software supplied by Valve. The adapter discovers its existing React runtime and adds a tab in memory. No Steam code/assets are distributed or modified on disk. This is an internal integration, not an official Valve plugin API.
- Decky source was consulted to understand the public examples of tab structure. No Decky packages/runtime are imported or shipped. Upstream interfaces are credited in the source/documentation.

Contributors must review licenses before importing any implementation from other projects; merely having similar hardware support does not make source code interchangeable.
