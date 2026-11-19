from pathlib import Path
import json
import os
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from a1daemon.platforms import support
from a1daemon.preferences import Preferences


class PreferencesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'preferences.json'
        self.preferences=Preferences(self.path)

    def test_only_explicitly_remembered_settings_are_restored(self):
        self.preferences.update('power',{'sustained_w':18,'boost_w':22},True)
        hardware=Mock(writes=True);hardware.supported.return_value=True
        self.assertIsNone(self.preferences.restore(hardware))
        hardware.set_power.assert_called_once_with(sustained_w=18,boost_w=22)
        hardware.set_rgb.assert_not_called()
        self.preferences.update('power',{},False)
        self.assertFalse(self.preferences.summary()['power'])

    def test_read_only_or_unsupported_hardware_is_never_restored(self):
        self.preferences.update('power',{'sustained_w':18,'boost_w':22},True)
        hardware=Mock(writes=False)
        self.preferences.restore(hardware);hardware.set_power.assert_not_called()
        hardware.writes=True;hardware.supported.return_value=False
        self.preferences.restore(hardware);hardware.set_power.assert_not_called()

    def test_corrupted_saved_state_is_reported_without_hardware_calls(self):
        self.path.write_text('{broken')
        hardware=Mock(writes=True);hardware.supported.return_value=True
        self.assertTrue(self.preferences.restore(hardware));hardware.set_power.assert_not_called()

    def test_driver_failure_is_reported_and_other_saved_section_is_attempted(self):
        self.preferences.update('power',{'sustained_w':18,'boost_w':22},True)
        self.preferences.update('rgb',{'enabled':True},True)
        hardware=Mock(writes=True);hardware.supported.return_value=True
        hardware.set_power.side_effect=OSError('rejected')
        self.assertIn('power: rejected',self.preferences.restore(hardware))
        hardware.set_rgb.assert_called_once()


class PlatformTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        for name,value in {'etc/os-release':'ID=cachyos\n','sys/class/dmi/id/board_name':'MS-1T41','sys/class/dmi/id/product_name':'Claw A1M'}.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)

    def test_cachyos_a1m_supported(self):
        self.assertTrue(support(self.root)[0])

    def test_immutable_distributions_are_blocked(self):
        for distro in ['bazzite','steamos','holo','arch']:
            (self.root/'etc/os-release').write_text('ID='+distro)
            self.assertFalse(support(self.root)[0])
        (self.root/'etc/os-release').write_text('ID=cachyos')
        (self.root/'run').mkdir();(self.root/'run/ostree-booted').touch()
        self.assertFalse(support(self.root)[0])

    def test_other_claw_generations_blocked(self):
        (self.root/'sys/class/dmi/id/board_name').write_text('MS-1T52')
        self.assertFalse(support(self.root)[0])


@unittest.skipIf(os.name=='nt','Linux account database required')
class SystemSetupTests(PlatformTests):
    def setUp(self):
        super().setUp()
        from a1daemon.setup_system import Setup
        self.calls=[];self.fail=False
        def runner(command):
            self.calls.append(command)
            if command[1] in ['is-active','is-enabled'] or (self.fail and command[1]=='restart'):
                raise subprocess.CalledProcessError(1,command)
        self.setup=Setup(self.root,runner)
        self.user=patch('a1daemon.setup_system.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=1000,pw_gid=1000))
        self.group=patch('a1daemon.setup_system.grp.getgrgid',return_value=SimpleNamespace(gr_name='player'))
        self.user.start();self.group.start();self.addCleanup(self.user.stop);self.addCleanup(self.group.stop)

    def test_install_is_user_independent_and_remove_restores_owned_state(self):
        self.setup.install('player',True)
        self.assertIn('Group=player',self.setup.dropin.read_text())
        self.assertTrue(self.setup.compat.state()['installed'])
        self.setup.remove()
        self.assertFalse(self.setup.dropin.exists());self.assertFalse(self.setup.config.exists())
        self.assertFalse(self.setup.compat.unit.exists())

    def test_failed_service_start_rolls_back_new_files(self):
        self.fail=True
        with self.assertRaises(RuntimeError):self.setup.install('player',True)
        self.assertFalse(self.setup.config.exists());self.assertFalse(self.setup.dropin.exists())
        self.assertFalse(self.setup.compat.unit.exists())

    def test_unowned_override_is_preserved(self):
        self.setup.dropin.parent.mkdir(parents=True)
        self.setup.dropin.write_text('external')
        with self.assertRaises(ValueError):self.setup.install('player',False)
        self.assertEqual(self.setup.dropin.read_text(),'external')

    def test_repair_can_disable_our_compatibility_without_losing_first_backup(self):
        self.setup.install('player',True)
        self.setup.install('player',False)
        self.assertFalse(self.setup.compat.unit.exists())


if __name__=='__main__':unittest.main()
