# 0.5.0 support matrix

| Target | Status |
| --- | --- |
| MSI Claw A1M, Ultra 5 135H, CachyOS KDE | Tested prototype target |
| Other CPU variants of Claw A1M / MS-1T41 | Detected by board; not independently tested |
| Other Claw generations: 7/8 AI+, A8 | Installer rejects them |
| Bazzite, SteamOS, other distros | Installer rejects them; host integration is deferred |
| Native Steam tab | Tested on client 1794536281; internal API may change |
| Standalone panel | Available through the application menu |
| InputPlumber | Retained as controller owner; version 0.83.1 tested |
| HHD integration / replacement controller mapper | Not included |
| Power/RGB/monitoring | Initial owner playtesting passed; see measurement limits |
| Sleep | Provisional, small sample |
| FPS/frame-time overlay / fan curves / EC tuning | Not included |

Required runtime: compatible Linux interfaces for Intel package power and the Claw LED driver, Python 3.11+, systemd, polkit, KDE kdialog and a Steam installation for the sidebar. Missing kernel features are not installed or replaced by setup. The standalone monitor can show available metrics, but missing hardware controls remain unavailable.
