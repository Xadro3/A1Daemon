import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a1daemon.hardware import Hardware, HardwareError


@unittest.skipIf(__import__('os').name=='nt', 'Linux sysfs filenames contain colons; run these tests on Linux')
class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.hw = Hardware(self.root, writes=True)
        for path, text in {
            'sys/class/dmi/id/board_name': 'MS-1T41',
            'sys/class/dmi/id/product_name': 'Claw A1M',
            'proc/stat': 'cpu 100 0 100 800 0 0 0 0 99 0\n',
            'proc/meminfo': 'MemTotal: 1000 kB\nMemAvailable: 600 kB\n',
        }.items():
            self.put(path, text)
        self.zone('intel-rapl:0')
        self.zone('intel-rapl-mmio:0')
        for name, value in {'enabled': 'false', 'brightness': '21', 'speed': '10', 'multi_intensity': '1 90 100', 'effect':'monocolor', 'effect_index':'monocolor breathe chroma rainbow frostfire'}.items():
            self.put('sys/class/leds/go:rgb:joystick_rings/' + name, value)

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return target

    def zone(self, name):
        for field, value in {'name':'package-0', 'energy_uj':'9000000', 'max_energy_range_uj':'10000000', 'constraint_0_name':'long_term', 'constraint_0_power_limit_uw':'43000000', 'constraint_1_name':'short_term', 'constraint_1_power_limit_uw':'45000000', 'constraint_2_name':'peak_power', 'constraint_2_power_limit_uw':'115000000'}.items():
            self.put(f'sys/class/powercap/{name}/{field}', value)

    def test_power_updates_both_interfaces_and_preserves_peak(self):
        self.hw.set_power(18,22)
        for name in ['intel-rapl:0','intel-rapl-mmio:0']:
            zone = self.root / 'sys/class/powercap' / name
            self.assertEqual((zone / 'constraint_0_power_limit_uw').read_text(), '18000000')
            self.assertEqual((zone / 'constraint_1_power_limit_uw').read_text(), '22000000')
            self.assertEqual((zone / 'constraint_2_power_limit_uw').read_text(), '115000000')

    def test_rejects_unsupported_hardware_and_disabled_writes(self):
        self.hw.writes = False
        with self.assertRaises(HardwareError): self.hw.set_power(18,22)
        self.hw.writes = True
        self.put('sys/class/dmi/id/board_name','OTHER')
        with self.assertRaises(HardwareError): self.hw.set_power(18,22)

    def test_power_validation_has_no_side_effects(self):
        for values in [(0,20),(18,40),(22,18),(True,22),(float('nan'),22),('18',22)]:
            with self.subTest(values=values), self.assertRaises(HardwareError): self.hw.set_power(*values)
        self.assertEqual(self.hw.power_state()['interfaces'][0]['constraints']['long_term']['watts'],43)

    def test_rolls_back_after_driver_rejects_second_write(self):
        original = Path.write_text
        failed = False
        def reject(path, value, *args, **kwargs):
            nonlocal failed
            if path.name == 'constraint_1_power_limit_uw' and not failed:
                failed = True
                raise OSError('simulated firmware rejection')
            return original(path, value, *args, **kwargs)
        with patch.object(Path,'write_text',reject):
            with self.assertRaisesRegex(HardwareError,'Original values restored'): self.hw.set_power(18,22)
        for state in self.hw.power_state()['interfaces']:
            self.assertEqual(state['constraints']['long_term']['watts'],43)
            self.assertEqual(state['constraints']['short_term']['watts'],45)

    def test_counter_wrap_uses_only_one_package(self):
        with patch('a1daemon.hardware.time.monotonic',return_value=10): self.hw.sample()
        self.put('sys/class/powercap/intel-rapl:0/energy_uj','1000000')
        with patch('a1daemon.hardware.time.monotonic',return_value=12): result=self.hw.sample()
        self.assertEqual(result['package_w'],1)

    def test_charging_is_not_reported_as_discharge(self):
        for name,value in {'type':'Battery','status':'Charging','capacity':'90','current_now':'2000000','voltage_now':'12000000'}.items():
            self.put('sys/class/power_supply/BAT1/'+name,value)
        battery=self.hw.sample()['battery']
        self.assertIsNone(battery['discharge_w'])
        self.assertEqual(battery['charge_w'],24)

    def test_cpu_excludes_guest_from_denominator(self):
        self.hw.sample()
        self.put('proc/stat','cpu 150 0 100 850 0 0 0 0 149 0\n')
        self.assertEqual(self.hw.sample()['cpu_percent'],50)

    def test_gpu_reports_actual_frequency_separately_from_request(self):
        self.put('sys/class/drm/card1/gt/gt0/rps_cur_freq_mhz','800')
        self.put('sys/class/drm/card1/gt/gt0/rps_act_freq_mhz','250')
        telemetry=self.hw.sample()
        self.assertEqual(telemetry['gpu_frequency_mhz']['gt0'],250)
        self.assertEqual(telemetry['gpu_requested_frequency_mhz']['gt0'],800)

    def test_rgb_rejects_bad_channels_and_effects(self):
        with self.assertRaises(HardwareError): self.hw.set_rgb(True,35,10,'rainbow',[101,0,0])
        with self.assertRaises(HardwareError): self.hw.set_rgb(True,35,10,'unknown',[1,2,3])
        self.hw.set_rgb(True,35,10,'breathe',[1,90,100])
        self.assertTrue(self.hw.rgb_state()['enabled'])

    def test_rgb_discovers_new_upstream_name(self):
        original = self.hw.rgb_path()
        modern = original.with_name('msi_claw:rgb:joystick_rings')
        original.rename(modern)
        self.assertEqual(self.hw.rgb_path(), modern)
        self.hw.set_rgb(True,35,10,'monocolor',[0,100,0])
        self.assertEqual(self.hw.rgb_state()['color'],[0,100,0])

    def test_rgb_does_not_select_unrelated_device(self):
        self.hw.rgb_path().rename(self.hw.rgb_path().with_name('external:rgb:joystick_rings'))
        self.assertFalse(self.hw.rgb_state()['available'])

    @unittest.skipIf(__import__('os').name=='nt', 'Windows symlinks require extra privileges')
    def test_gpu_fdinfo_deduplicates_clients(self):
        for process in ['100','101']:
            fd=self.root/'proc'/process/'fd'/'3'
            fd.parent.mkdir(parents=True)
            fd.symlink_to('/dev/dri/renderD128')
            self.put(f'proc/{process}/fdinfo/3','drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 7\ndrm-engine-render: 100000000 ns\n')
        self.assertIsNone(self.hw.gpu_utilization(1))
        for process in ['100','101']:
            self.put(f'proc/{process}/fdinfo/3','drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 7\ndrm-engine-render: 600000000 ns\n')
        self.assertEqual(self.hw.gpu_utilization(2),50)


if __name__ == '__main__': unittest.main()
