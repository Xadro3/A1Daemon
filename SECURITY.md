# Security and privileged changes

A1Daemon 0.5.0 is a prototype. It is an independent project, not endorsed by MSI, Valve, CachyOS or Bazzite. Only CachyOS on Claw A1M is an installation target in this release.

The hardware service runs as root because RAPL, RGB and some DRM telemetry interfaces require privileged access. Its HTTP listener is bound to 127.0.0.1, validates Host, requires a per-service bearer token for all API reads/writes, accepts only bounded predefined operations, and executes no commands supplied by the client. The token is root-owned, readable by the selected user's primary group. A single desktop user is supported. Setup uses polkit authorization rather than collecting a password. Do not put authentication tokens in issue reports.

The service has systemd filesystem/capability restrictions. It must retain write access to the required sysfs controls; this is not a claim of complete sandbox isolation. Software running as the selected user can access that user's token. Root and a compromised Steam client remain trusted principals in this prototype.

The sidebar needs Steam's local CEF debugging endpoint. The test device binds it to 127.0.0.1:8080. This is not a supported Valve plugin API. Steam updates can break the adapter. Never expose CEF or the application API to a network, and disable the opt-in/debugging session on uninstall if it was created by setup. Setup never terminates an active game or restarts Steam without the user doing so.

Package files live under /usr and belong to pacman. Application state/backups live under /var/lib/a1daemon; configuration overrides live under /etc. User setup state follows XDG paths. Runtime tokens live under /run. No root read-only protection, kernel, BIOS, graphics-driver binding, controller daemon or global PCI policy is replaced. Optional compatibility changes are board/device-scoped and reversible. Existing independently installed workarounds are preserved.

Support exports contain allowlisted version/capability metadata, not raw journals, Wi-Fi identifiers, accounts, serials or credentials. Reports are reviewed locally before saving. There is no telemetry upload, account service or automatic update channel. Release checksums detect corruption; they do not independently prove publisher identity.

Report vulnerabilities using GitHub's private vulnerability reporting for https://github.com/Xadro3/aidaemon when available. If unavailable, open a minimal issue asking for a private contact without posting exploit details or secrets. The repository must enable private reporting before public release.
