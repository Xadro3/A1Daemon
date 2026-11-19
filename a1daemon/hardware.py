"""Linux hardware access. No subprocesses, arbitrary paths or raw EC/MSR writes."""
from __future__ import annotations

import math
from pathlib import Path
import threading
import time


class HardwareError(Exception):
    pass


class Hardware:
    def __init__(self, root: Path = Path('/'), writes: bool = False):
        self.root = root
        self.writes = writes
        self.lock = threading.RLock()
        self.previous_energy = {}
        self.previous_cpu = None
        self.previous_gpu = None

    def path(self, name):
        return self.root / name.lstrip('/')

    @staticmethod
    def read(path, default=None):
        try:
            return path.read_text().strip()
        except (OSError, UnicodeError):
            return default

    @classmethod
    def number(cls, path):
        try:
            return int(cls.read(path))
        except (ValueError, TypeError):
            return None

    def supported(self):
        return (self.read(self.path('/sys/class/dmi/id/board_name')) == 'MS-1T41'
                and self.read(self.path('/sys/class/dmi/id/product_name')) == 'Claw A1M')

    def require_writes(self):
        if not self.writes:
            raise HardwareError('Hardware writes are disabled. Start with --enable-writes after reviewing the baseline.')
        if not self.supported():
            raise HardwareError('Hardware writes require an MSI Claw A1M board MS-1T41.')

    @staticmethod
    def bounded(value, low, high, name):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise HardwareError(f'{name} must be between {low} and {high}.')
        return value

    def zones(self):
        # Resolve aliases so the same package is never counted twice.
        return sorted({p.resolve() for p in self.path('/sys/class/powercap').glob('intel-rapl*') if (p / 'name').exists()})

    def power_state(self):
        result = []
        for zone in self.zones():
            if self.read(zone / 'name') != 'package-0':
                continue
            constraints = {}
            for name in zone.glob('constraint_*_name'):
                prefix = name.name.removesuffix('_name')
                constraints[self.read(name)] = {
                    'watts': self._scaled(self.number(zone / f'{prefix}_power_limit_uw'), 1e6),
                    'window_seconds': self._scaled(self.number(zone / f'{prefix}_time_window_us'), 1e6),
                }
            result.append({'interface': zone.name, 'constraints': constraints})
        return {'interfaces': result, 'prototype_range_w': [6, 28],
                'note': '6–28 W is a conservative prototype policy, not a validated operating range.'}

    @staticmethod
    def _scaled(value, factor):
        return None if value is None else value / factor

    def set_power(self, sustained_w, boost_w):
        self.require_writes()
        sustained = self.bounded(sustained_w, 6, 28, 'Sustained watts')
        boost = self.bounded(boost_w, sustained, 28, 'Boost watts')
        with self.lock:
            changes = []
            for zone in self.zones():
                if self.read(zone / 'name') != 'package-0':
                    continue
                for name in zone.glob('constraint_*_name'):
                    kind = self.read(name)
                    value = {'long_term': sustained, 'short_term': boost}.get(kind)
                    if value is not None:
                        path = zone / (name.name.removesuffix('_name') + '_power_limit_uw')
                        changes.append((path, str(round(value * 1e6))))
            kinds = {self.read(p.with_name(p.name.replace('_power_limit_uw', '_name'))) for p, _ in changes}
            if kinds != {'long_term', 'short_term'}:
                raise HardwareError('Both sustained and boost package constraints are required.')
            self._transaction(changes)
            return {'requested': {'sustained_w': sustained, 'boost_w': boost},
                    'readback': self.power_state(),
                    'status': 'Register readback matched. Enforcement under load remains unverified.'}

    def _transaction(self, changes):
        originals = [(p, self.read(p)) for p, _ in changes]
        if any(value is None for _, value in originals):
            raise HardwareError('Cannot snapshot current hardware settings.')
        try:
            for path, value in changes:
                path.write_text(value)
                if self.read(path) != value:
                    raise HardwareError(f'Firmware or driver rejected {path.name}.')
        except (OSError, HardwareError) as exc:
            failures = []
            for path, value in reversed(originals):
                try:
                    path.write_text(value)
                    if self.read(path) != value:
                        failures.append(path.name)
                except OSError:
                    failures.append(path.name)
            suffix = f' Rollback could not restore: {", ".join(failures)}.' if failures else ' Original values restored.'
            raise HardwareError(f'{exc}.{suffix}') from exc

    def rgb_path(self):
        # The deployed CachyOS driver and newer upstream HID driver use different
        # names for the same Claw interface. Discover the known names, not a broad
        # wildcard that might pick an unrelated external RGB device.
        names = ('msi_claw:rgb:joystick_rings', 'go:rgb:joystick_rings')
        for name in names:
            candidate = self.path('/sys/class/leds/' + name)
            if candidate.is_dir():
                return candidate
        return self.path('/sys/class/leds/' + names[0])

    def rgb_state(self):
        led = self.rgb_path()
        return {'available': led.exists(), 'enabled': self.read(led / 'enabled') == 'true',
                'brightness': self.number(led / 'brightness'), 'speed': self.number(led / 'speed'),
                'effect': self.read(led / 'effect'),
                'effects': (self.read(led / 'effect_index', '')).split(),
                'color': [int(v) for v in self.read(led / 'multi_intensity', '').split() if v.isdigit()]}

    def set_rgb(self, enabled, brightness, speed, effect, color):
        self.require_writes()
        if not isinstance(enabled, bool):
            raise HardwareError('Enabled must be a boolean.')
        if not isinstance(color, list) or len(color) != 3:
            raise HardwareError('Color must contain three channel values.')
        for name, value, high in [('Brightness', brightness, 100), ('Speed', speed, 20)] + [('Color', v, 100) for v in color]:
            self.bounded(value, 0, high, name)
            if not isinstance(value, int):
                raise HardwareError(f'{name} must be an integer.')
        if effect not in self.rgb_state()['effects']:
            raise HardwareError('Unsupported lighting effect.')
        led = self.rgb_path()
        with self.lock:
            self._transaction([(led / 'brightness', str(brightness)), (led / 'speed', str(speed)),
                               (led / 'multi_intensity', ' '.join(map(str, color))),
                               (led / 'effect', effect), (led / 'enabled', str(enabled).lower())])
        return self.rgb_state()

    def sample(self):
        with self.lock:
            now = time.monotonic()
            package_w = None
            # Prefer one MSR package domain; MMIO is an alternate view, not extra power.
            packages = [z for z in self.zones() if self.read(z / 'name') == 'package-0']
            packages.sort(key=lambda z: ('mmio' in z.name, z.name))
            if packages:
                zone = packages[0]
                energy, wrap = self.number(zone / 'energy_uj'), self.number(zone / 'max_energy_range_uj')
                previous = self.previous_energy.get(str(zone))
                if energy is not None:
                    if previous and 0 < now - previous[0] < 10:
                        delta = energy - previous[1]
                        if delta < 0 and wrap:
                            delta += wrap
                        if delta >= 0:
                            package_w = delta / (now - previous[0]) / 1e6
                    self.previous_energy[str(zone)] = (now, energy)
            battery = None
            for supply in self.path('/sys/class/power_supply').glob('*'):
                if self.read(supply / 'type') != 'Battery':
                    continue
                status = self.read(supply / 'status')
                voltage, current = self.number(supply / 'voltage_now'), self.number(supply / 'current_now')
                power = self.number(supply / 'power_now')
                magnitude = abs(power / 1e6) if power is not None else (abs(current * voltage / 1e12) if current is not None and voltage is not None else None)
                battery = {'percent': self.number(supply / 'capacity'), 'status': status,
                           'discharge_w': magnitude if status == 'Discharging' else None,
                           'charge_w': magnitude if status == 'Charging' else None,
                           'note': 'Battery flow, not wall power.'}
                break
            cpu = None
            stats = self.read(self.path('/proc/stat'), '').splitlines()
            if stats and stats[0].startswith('cpu '):
                values = list(map(int, stats[0].split()[1:9]))
                total, idle = sum(values), values[3] + (values[4] if len(values) > 4 else 0)
                if self.previous_cpu:
                    dt, di = total - self.previous_cpu[0], idle - self.previous_cpu[1]
                    if dt > 0 and 0 <= di <= dt:
                        cpu = (1 - di / dt) * 100
                self.previous_cpu = (total, idle)
            memory = {}
            for line in self.read(self.path('/proc/meminfo'), '').splitlines():
                parts = line.split()
                if parts[0] in ('MemTotal:', 'MemAvailable:'):
                    memory[parts[0].rstrip(':')] = int(parts[1]) * 1024
            temperatures = []
            for sensor in self.path('/sys/class/hwmon').glob('hwmon*'):
                if self.read(sensor / 'name') != 'coretemp':
                    continue
                for label in sensor.glob('temp*_label'):
                    if 'Package' in self.read(label, ''):
                        temperatures.append(self._scaled(self.number(label.with_name(label.name.replace('_label', '_input'))), 1000))
            frequencies, requested_frequencies = {}, {}
            for file in self.path('/sys/class/drm').glob('card*/gt/gt*/rps_cur_freq_mhz'):
                requested_frequencies[file.parent.name] = self.number(file)
                frequencies[file.parent.name] = self.number(file.with_name('rps_act_freq_mhz'))
            gpu_percent = self.gpu_utilization(now)
            return {'sample_monotonic_s': now, 'package_w': package_w, 'battery': battery,
                    'cpu_percent': cpu, 'memory': memory, 'package_temperature_c': next(iter(temperatures), None),
                    'gpu_frequency_mhz': frequencies, 'gpu_requested_frequency_mhz': requested_frequencies, 'gpu_percent': gpu_percent,
                    'gpu_note': 'Render-engine busy time from DRM clients; not a combined GPU percentage. Unavailable if the driver exposes no client counters.',
                    'fps': None, 'fps_note': 'Frame capture is not integrated in this prototype.'}

    def gpu_utilization(self, now):
        counters = {}
        # Deduplicate inherited/duplicated DRM descriptors by PCI device + client ID.
        for process in self.path('/proc').glob('[0-9]*'):
            try:
                descriptors = list((process / 'fd').iterdir())
            except OSError:
                continue
            for descriptor in descriptors:
                try:
                    if '/dev/dri/' not in str(descriptor.readlink()):
                        continue
                except OSError:
                    continue
                fields = {}
                for line in self.read(process / 'fdinfo' / descriptor.name, '').splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        fields[key] = value.strip()
                if fields.get('drm-driver') != 'i915' or fields.get('drm-pdev') != '0000:00:02.0':
                    continue
                key = fields.get('drm-client-id')
                raw = fields.get('drm-engine-render')
                if key and raw and raw.endswith(' ns'):
                    try:
                        counters[key] = int(raw.split()[0])
                    except ValueError:
                        pass
        previous = self.previous_gpu
        self.previous_gpu = (now, counters)
        if not counters or not previous or not 0 < now - previous[0] < 10:
            return None
        common = counters.keys() & previous[1].keys()
        if not common:
            return None
        busy = sum(max(0, counters[k] - previous[1][k]) for k in common)
        return min(100, busy / ((now - previous[0]) * 1e9) * 100)

    def snapshot(self):
        return {'device': {'product': self.read(self.path('/sys/class/dmi/id/product_name'), 'Unknown'),
                           'board': self.read(self.path('/sys/class/dmi/id/board_name'), 'Unknown'),
                           'kernel': self.read(self.path('/proc/sys/kernel/osrelease'), 'Unknown')},
                'writes_enabled': self.writes and self.supported(), 'power': self.power_state(), 'rgb': self.rgb_state()}
