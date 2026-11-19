"""Privileged setup of package-owned services; never downloads or runs shell text."""
import argparse
import base64
import grp
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import time
import urllib.request

from .compat import Compatibility, CompatibilityError
from .platforms import support
from . import __version__


class Setup:
    def __init__(self, root=Path('/'), runner=None):
        self.root = Path(root)
        self.run = runner or (lambda command: subprocess.run(command,check=True,capture_output=True,text=True))
        self.config = self.path('/etc/a1daemon/install.json')
        self.dropin = self.path('/etc/systemd/system/a1daemon.service.d/10-user.conf')
        self.compat = Compatibility(self.root,Path('/usr/lib/a1daemon'))

    def path(self, name):
        return self.root/name.lstrip('/')

    def state(self):
        if not self.config.exists(): return None
        data = json.loads(self.config.read_text())
        if data.get('application') != 'a1daemon' or data.get('schema') != 1:
            raise ValueError('An unrelated installation configuration exists; refusing to overwrite it.')
        return data

    @staticmethod
    def snapshot(path):
        return base64.b64encode(path.read_bytes()).decode() if path.exists() else None

    @staticmethod
    def restore_file(path, content, mode):
        if content is None: path.unlink(missing_ok=True)
        else: Compatibility.atomic(path,base64.b64decode(content).decode(),mode)

    def command(self, *args):
        return self.run(['/usr/bin/systemctl',*args])

    def active(self, unit):
        try: self.command('is-active','--quiet',unit);return True
        except subprocess.CalledProcessError:return False

    def enabled(self, unit):
        try: self.command('is-enabled','--quiet',unit);return True
        except subprocess.CalledProcessError:return False

    def health_check(self):
        if self.root != Path('/'):return
        error='Service did not respond'
        for _ in range(40):
            try:
                token=self.path('/run/a1daemon/token').read_text().strip()
                request=urllib.request.Request('http://127.0.0.1:17641/api/state',headers={'Authorization':'Bearer '+token})
                with urllib.request.urlopen(request,timeout=1) as response:data=json.load(response)
                if data.get('version')==__version__ and data.get('writes_enabled') and data.get('telemetry') and not data.get('telemetry_error'):
                    return
                error='Hardware service is not ready: '+str(data.get('telemetry_error'))
            except (OSError,ValueError) as exc:error=str(exc)
            time.sleep(.25)
        raise RuntimeError(error)

    def install(self, username, compatibility):
        supported, reason = support(self.root)
        if not supported: raise ValueError(reason)
        user = pwd.getpwnam(username)
        if user.pw_uid < 1000: raise ValueError('Select a regular desktop user.')
        group = grp.getgrgid(user.pw_gid).gr_name
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.-]*\$?',group): raise ValueError('Unsupported group name.')
        previous = self.state()
        if previous and previous['user'] != username:
            raise ValueError('0.5 supports one desktop user. Remove the existing setup before changing users.')
        if self.path('/etc/systemd/system/a1daemon.service').exists():
            raise ValueError('A manual a1daemon.service overrides the package unit. Leaving it untouched.')
        if self.dropin.exists() and (not previous or self.dropin.read_text()!=previous['dropin']):
            raise ValueError('A service override was edited externally; leaving it untouched.')
        watched = [(self.config,0o600),(self.dropin,0o644),(self.compat.state_file,0o600),(self.compat.unit,0o644)]
        backups = [(path,self.snapshot(path),mode) for path,mode in watched]
        values = [(path,self.compat.read(path)) for _,path,_,valid in self.compat.targets() if self.compat.read(path) in valid]
        was_active, was_enabled = self.active('a1daemon.service'), self.enabled('a1daemon.service')
        was_prototype = self.active('a1daemon-prototype.service')
        prototype_unit = self.command('cat','a1daemon-prototype.service').stdout if was_prototype else None
        compat_enabled = self.enabled('a1daemon-compat.service')
        dropin = f'# Managed by A1Daemon setup\n[Service]\nGroup={group}\n'
        state = dict(previous) if previous else {'application':'a1daemon','schema':1,'user':username,
            'previous_compat_state':self.snapshot(self.compat.state_file),
            'previous_compat_unit':self.snapshot(self.compat.unit),'previous_compat_enabled':compat_enabled}
        state.update(dropin=dropin,compatibility=compatibility)
        try:
            Compatibility.atomic(self.config,json.dumps(state,indent=2)+'\n')
            Compatibility.atomic(self.dropin,dropin,0o644)
            if compatibility:
                self.compat.install()
            elif previous and previous.get('compatibility'):
                self.restore_compatibility(previous)
            self.command('daemon-reload')
            if compatibility:self.command('enable','--now','a1daemon-compat.service')
            if was_prototype:self.command('stop','a1daemon-prototype.service')
            self.command('enable','a1daemon.service')
            self.command('restart','a1daemon.service')
            self.health_check()
        except Exception as exc:
            failures = []
            for path,value in values:
                try:path.write_text(value)
                except OSError as error:failures.append(str(error))
            for path,content,mode in backups:
                try:self.restore_file(path,content,mode)
                except OSError as error:failures.append(str(error))
            for args in [('daemon-reload',),('enable' if was_enabled else 'disable','a1daemon.service'),
                         ('enable' if compat_enabled else 'disable','a1daemon-compat.service'),
                         ('restart' if was_active else 'stop','a1daemon.service')]:
                try:self.command(*args)
                except Exception as error:failures.append(str(error))
            if was_prototype:
                try:
                    Compatibility.atomic(self.path('/run/systemd/system/a1daemon-prototype.service'),prototype_unit,0o644)
                    self.command('daemon-reload')
                    self.command('start','a1daemon-prototype.service')
                except Exception as error:failures.append(str(error))
            detail = '; rollback errors: '+ '; '.join(failures) if failures else '; previous configuration restored'
            raise RuntimeError(str(exc)+detail) from exc
        return {'user':username,'compatibility':compatibility,'service':'a1daemon.service'}

    def restore_compatibility(self, state):
        if not state.get('compatibility'):return
        self.command('disable','--now','a1daemon-compat.service')
        self.compat.uninstall()
        self.restore_file(self.compat.state_file,state.get('previous_compat_state'),0o600)
        self.restore_file(self.compat.unit,state.get('previous_compat_unit'),0o644)
        self.command('daemon-reload')
        if state.get('previous_compat_enabled'):self.command('enable','--now','a1daemon-compat.service')

    def remove(self):
        state = self.state()
        if not state:return {'removed':True,'note':'No configured integration found.'}
        if self.dropin.exists() and self.dropin.read_text()!=state['dropin']:
            raise ValueError('Service override was edited externally; refusing to remove it.')
        self.command('disable','--now','a1daemon.service')
        self.restore_compatibility(state)
        self.dropin.unlink(missing_ok=True)
        self.config.unlink()
        self.command('daemon-reload')
        return {'removed':True,'note':'Saved preferences retained in /var/lib/a1daemon.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','remove'])
    parser.add_argument('--user')
    parser.add_argument('--compatibility',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0:parser.error('Use the graphical setup authorization prompt.')
    try:
        setup=Setup()
        if args.action=='install' and not args.user:raise ValueError('A desktop user is required.')
        result=setup.install(args.user,args.compatibility) if args.action=='install' else setup.remove()
        print(json.dumps(result))
    except (ValueError, OSError, RuntimeError, CompatibilityError, subprocess.CalledProcessError) as exc:
        parser.exit(1,f'Setup: {exc}\n')


if __name__=='__main__':main()
