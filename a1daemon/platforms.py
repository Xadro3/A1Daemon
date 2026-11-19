"""Conservative installation support boundaries for the 0.5 prototype."""
from pathlib import Path
import shlex


def os_release(path=Path('/etc/os-release')):
    values = {}
    for line in path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, raw = line.split('=',1)
            parsed = shlex.split(raw)
            values[key] = parsed[0] if parsed else ''
    return values


def support(root=Path('/')):
    release = os_release(root/'etc/os-release')
    board = (root/'sys/class/dmi/id/board_name').read_text().strip()
    product = (root/'sys/class/dmi/id/product_name').read_text().strip()
    if release.get('ID') != 'cachyos' or (root/'run/ostree-booted').exists():
        return False, '0.5.0 installs on CachyOS only. Bazzite/SteamOS need a separately tested host integration; read-only protection will not be changed.'
    if board != 'MS-1T41' or product != 'Claw A1M':
        return False, '0.5.0 requires MSI Claw A1M / MS-1T41. Other Claw generations are not supported.'
    return True, 'CachyOS on MSI Claw A1M detected. Core Ultra 5 135H is the tested CPU variant.'
