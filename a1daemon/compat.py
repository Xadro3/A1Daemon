"""Install reversible, hardware-scoped Claw suspend workarounds."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile


class CompatibilityError(Exception):
    pass


class Compatibility:
    def __init__(self, root=Path('/'), source=None):
        self.root = Path(root)
        self.source = Path(source or Path(__file__).resolve().parent.parent)
        self.state_file = self.path('/var/lib/a1daemon/compatibility.json')
        self.unit = self.path('/etc/systemd/system/a1daemon-compat.service')

    def path(self, absolute):
        return self.root / absolute.lstrip('/')

    @staticmethod
    def read(path):
        try:
            return path.read_text().strip()
        except OSError:
            return None

    def supported(self):
        return (self.read(self.path('/sys/class/dmi/id/board_name')) == 'MS-1T41'
                and self.read(self.path('/sys/class/dmi/id/product_name')) == 'Claw A1M')

    def targets(self):
        result = []
        if not self.supported():
            return result
        for device in sorted(self.path('/sys/bus/pci/devices').glob('*')):
            if self.read(device / 'vendor') == '0x8086' and self.read(device / 'device') == '0x272b':
                result.append(('wifi-d3cold', device / 'd3cold_allowed', '0', {'0', '1'}))
        keyboard = self.path('/sys/bus/serio/devices/serio0')
        if self.read(keyboard / 'description') == 'i8042 KBD port':
            result.append(('keyboard-wakeup', keyboard / 'power/wakeup', 'disabled', {'enabled', 'disabled'}))
        return result

    def state(self):
        if not self.state_file.exists():
            return {'version': 1, 'original_values': {}, 'installed': False}
        state = json.loads(self.state_file.read_text())
        if state.get('version') != 1:
            raise CompatibilityError('Unknown compatibility backup format.')
        return state

    @staticmethod
    def atomic(path, text, mode=0o600):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        try:
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, state):
        self.state_file.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.atomic(self.state_file, json.dumps(state, indent=2) + '\n')

    def key(self, path):
        return '/' + path.relative_to(self.root).as_posix()

    def status(self):
        state = self.state()
        return {'supported': self.supported(), 'installed': state.get('installed', False),
                'sleep_mode': self.read(self.path('/sys/power/mem_sleep')),
                'fixes': [{'id': name, 'path': self.key(path), 'current': self.read(path),
                           'desired': value, 'available': self.read(path) in valid,
                           'original': state['original_values'].get(self.key(path)),
                           'effective': self.read(path) == value}
                          for name, path, value, valid in self.targets()],
                'validation': 'Settings verified only; suspend, fan behaviour and Wi-Fi resume require a sleep test.'}

    def apply(self):
        if not self.supported():
            raise CompatibilityError('Compatibility fixes require MSI Claw A1M / MS-1T41.')
        state = self.state()
        changed = []
        try:
            for _, path, desired, valid in self.targets():
                current = self.read(path)
                if current not in valid or current == desired:
                    continue
                key = self.key(path)
                if key not in state['original_values']:
                    state['original_values'][key] = current
                    self.save(state)  # Save before touching the hardware, including on first boot.
                changed.append((path, current))
                path.write_text(desired)
                if self.read(path) != desired:
                    raise CompatibilityError(f'Driver did not accept {key}.')
        except (OSError, CompatibilityError) as exc:
            failures = []
            for path, original in reversed(changed):
                try:
                    path.write_text(original)
                    if self.read(path) != original:
                        failures.append(self.key(path))
                except OSError:
                    failures.append(self.key(path))
            detail = ' Rollback failed for: ' + ', '.join(failures) if failures else ' Changes from this attempt restored.'
            raise CompatibilityError(str(exc) + detail) from exc
        return self.status()

    def unit_text(self):
        script = self.source / 'a1daemon/compat.py'
        if any(c in str(script) for c in ('\n', '\r', '"', '%', '\\')):
            raise CompatibilityError('Unsupported source path for a systemd unit.')
        return f'''# Managed by A1Daemon; undo with: python3 -m a1daemon.compat uninstall
[Unit]
Description=A1Daemon Claw Wi-Fi and keyboard wake compatibility
After=systemd-udev-trigger.service
Before=sleep.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 "{script}" apply
TimeoutStartSec=15
NoNewPrivileges=yes
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target sleep.target
'''

    def install(self):
        if not self.supported():
            raise CompatibilityError('Refusing compatibility installation on an unsupported device.')
        state = self.state()
        if self.unit.exists() and not state.get('installed'):
            raise CompatibilityError('An unowned a1daemon-compat.service already exists; leaving it untouched.')
        if self.unit.exists() and self.unit.read_text() != state.get('unit_content'):
            raise CompatibilityError('The compatibility service was edited externally; leaving it untouched.')
        content = self.unit_text()
        state.update(installed=True, unit_content=content,
                     installed_at=state.get('installed_at', datetime.now(timezone.utc).isoformat()))
        self.save(state)
        self.atomic(self.unit, content, 0o644)
        return self.apply()

    def restore(self):
        if not self.supported():
            raise CompatibilityError('Refusing hardware restoration on an unsupported device.')
        state = self.state()
        errors = []
        allowed = {self.key(path): (path, desired, valid) for _, path, desired, valid in self.targets()}
        for key, original in list(state['original_values'].items()):
            if key not in allowed:
                errors.append(key + ': original device is missing or has changed')
                continue
            path, desired, valid = allowed[key]
            current = self.read(path)
            if original not in valid or current not in (desired, original):
                errors.append(key + ': externally changed or invalid value')
                continue
            try:
                path.write_text(original)
                if self.read(path) != original:
                    raise OSError('Readback did not match')
                del state['original_values'][key]
                self.save(state)
            except OSError as exc:
                errors.append(key + ': ' + str(exc))
        if errors:
            raise CompatibilityError('Restoration incomplete; backup retained: ' + '; '.join(errors))
        return self.status()

    def uninstall(self):
        state = self.state()
        if self.unit.exists() and self.unit.read_text() != state.get('unit_content'):
            raise CompatibilityError('The compatibility service was edited externally; leaving it untouched.')
        self.restore()
        self.unit.unlink(missing_ok=True)
        state = self.state()
        state.update(installed=False)
        self.save(state)
        return self.status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'install', 'apply', 'uninstall'])
    args = parser.parse_args()
    compat = Compatibility()
    try:
        if args.action != 'status' and os.geteuid() != 0:
            raise CompatibilityError('Run hardware changes with sudo.')
        if args.action == 'install':
            # A persistent privileged service must not execute user-writable source.
            for path in [compat.source, compat.source / 'a1daemon', Path(__file__).resolve()]:
                if path.stat().st_uid != 0 or path.stat().st_mode & 0o022:
                    raise CompatibilityError('Install from root-owned source without group/world write access.')
        if args.action == 'uninstall':
            state = compat.state()
            if compat.unit.exists() and compat.unit.read_text() != state.get('unit_content'):
                raise CompatibilityError('The compatibility service was edited externally; leaving it untouched.')
            if state.get('installed'):
                subprocess.run(['systemctl', 'disable', '--now', 'a1daemon-compat.service'], check=True)
        result = getattr(compat, args.action)()
        if args.action in ('install', 'uninstall'):
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            if args.action == 'install':
                subprocess.run(['systemctl', 'enable', '--now', 'a1daemon-compat.service'], check=True)
        print(json.dumps(result, indent=2))
    except (CompatibilityError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Compatibility: {exc}\n')


if __name__ == '__main__':
    main()
