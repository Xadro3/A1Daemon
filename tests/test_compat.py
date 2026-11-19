import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a1daemon.compat import Compatibility, CompatibilityError


@unittest.skipIf(os.name == 'nt', 'Requires Linux sysfs filenames')
class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.compat = Compatibility(self.root, Path('/opt/a1daemon-prototype'))
        for key, value in {
            '/sys/class/dmi/id/board_name':'MS-1T41',
            '/sys/class/dmi/id/product_name':'Claw A1M',
            '/sys/power/mem_sleep':'[s2idle] deep',
            '/sys/bus/pci/devices/0000:2b:00.0/vendor':'0x8086',
            '/sys/bus/pci/devices/0000:2b:00.0/device':'0x272b',
            '/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed':'1',
            '/sys/bus/serio/devices/serio0/description':'i8042 KBD port',
            '/sys/bus/serio/devices/serio0/power/wakeup':'enabled',
        }.items():
            self.put(key, value)

    def put(self, key, value):
        path = self.compat.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def test_install_repeat_and_uninstall_preserve_original_values(self):
        self.compat.install()
        initial = self.compat.state()['original_values'].copy()
        self.assertEqual(set(initial.values()), {'1', 'enabled'})
        self.compat.install()
        self.assertEqual(self.compat.state()['original_values'], initial)
        self.assertTrue(all(f['effective'] for f in self.compat.status()['fixes']))
        self.compat.uninstall()
        self.assertFalse(self.compat.unit.exists())
        for key, value in initial.items():
            self.assertEqual(self.compat.read(self.compat.path(key)), value)
        self.assertEqual(self.compat.state()['original_values'], {})
        self.assertEqual(self.compat.read(self.compat.path('/sys/power/mem_sleep')), '[s2idle] deep')

    def test_reapply_before_sleep_restores_workaround_not_backup(self):
        self.compat.install()
        self.put('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed', '1')
        self.compat.apply()
        self.assertTrue(all(f['effective'] for f in self.compat.status()['fixes']))
        self.assertEqual(len(self.compat.state()['original_values']), 2)

    def test_preexisting_fixes_are_not_owned_or_undone(self):
        self.put('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed', '0')
        self.put('/sys/bus/serio/devices/serio0/power/wakeup', 'disabled')
        self.compat.install()
        self.assertEqual(self.compat.state()['original_values'], {})
        self.compat.uninstall()
        self.assertTrue(all(f['effective'] for f in self.compat.status()['fixes']))

    def test_wrong_device_has_no_side_effects(self):
        self.put('/sys/class/dmi/id/board_name', 'OTHER')
        with self.assertRaises(CompatibilityError): self.compat.install()
        self.assertFalse(self.compat.unit.exists())
        self.assertFalse(self.compat.state_file.exists())

    def test_replaced_wifi_is_not_touched(self):
        self.put('/sys/bus/pci/devices/0000:2b:00.0/device', '0x1234')
        self.compat.install()
        self.assertEqual(self.compat.read(self.compat.path('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed')), '1')
        self.assertEqual([f['id'] for f in self.compat.status()['fixes']], ['keyboard-wakeup'])

    def test_missing_optional_sysfs_attribute_is_reported(self):
        self.compat.path('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed').unlink()
        self.compat.install()
        self.assertFalse(self.compat.status()['fixes'][0]['available'])

    def test_driver_write_failure_rolls_back_this_attempt(self):
        write = Path.write_text
        def fail(path, value, *args, **kwargs):
            if path.name == 'wakeup' and value == 'disabled':
                raise OSError('simulated rejection')
            return write(path, value, *args, **kwargs)
        with patch.object(Path, 'write_text', fail):
            with self.assertRaisesRegex(CompatibilityError, 'restored'): self.compat.apply()
        self.assertEqual(self.compat.read(self.compat.path('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed')), '1')

    def test_external_service_is_never_overwritten(self):
        self.compat.atomic(self.compat.unit, 'another service', 0o644)
        with self.assertRaises(CompatibilityError): self.compat.install()
        self.assertEqual(self.compat.unit.read_text(), 'another service')

    def test_external_service_edits_block_removal(self):
        self.compat.install()
        self.compat.unit.write_text('edited service')
        with self.assertRaises(CompatibilityError): self.compat.uninstall()
        self.assertTrue(self.compat.state()['installed'])

    def test_missing_original_device_keeps_backup_for_recovery(self):
        self.compat.install()
        self.put('/sys/bus/pci/devices/0000:2b:00.0/device', '0x1234')
        with self.assertRaisesRegex(CompatibilityError, 'backup retained'): self.compat.uninstall()
        self.assertIn('/sys/bus/pci/devices/0000:2b:00.0/d3cold_allowed', self.compat.state()['original_values'])


if __name__ == '__main__': unittest.main()
