#!/usr/bin/env python3
"""Offline release bootstrap. Delegates installed files to pacman."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def message(text, error=False):
    if shutil.which('kdialog'):
        subprocess.run(['kdialog','--title','A1Daemon 0.5 Setup','--error' if error else '--msgbox',text])
    else:
        print(text,file=sys.stderr)


def main():
    if not shutil.which('kdialog'):
        message('A1Daemon 0.5 requires CachyOS KDE and its kdialog package.',True);return 1
    try:
        release={}
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key,value=line.split('=',1);release[key]=value.strip('"')
        if release.get('ID')!='cachyos' or Path('/run/ostree-booted').exists():
            raise RuntimeError('This 0.5 prototype supports CachyOS only. Bazzite and SteamOS are not modified; no read-only protection will be disabled.')
        if Path('/sys/class/dmi/id/board_name').read_text().strip()!='MS-1T41':
            raise RuntimeError('This release requires an MSI Claw A1M (MS-1T41).')
        directory=Path(__file__).resolve().parent
        manifest=json.loads((directory/'bundle.json').read_text())
        package=directory/manifest['package']
        if package.parent!=directory or package.is_symlink() or not package.is_file():raise RuntimeError('Invalid package path.')
        if hashlib.sha256(package.read_bytes()).hexdigest()!=manifest['sha256']:
            raise RuntimeError('Package checksum failed. Download and extract a fresh release archive.')
        result=subprocess.run(['kdialog','--title','A1Daemon 0.5 Setup','--warningyesno',
            'Install A1Daemon 0.5.0 prototype using the system package manager?\n\nThe next step opens the OS authorization prompt. Setup then lets you choose hardware workarounds and Steam integration. This is an independent project, not endorsed by MSI, Valve or the distributions.'])
        if result.returncode:return 0
        result=subprocess.run(['/usr/bin/pkexec','/usr/bin/pacman','-U','--noconfirm',str(package)],capture_output=True,text=True,timeout=300)
        if result.returncode:raise RuntimeError((result.stderr or result.stdout or 'Installation cancelled.')[-4000:])
        return subprocess.call(['/usr/bin/a1daemon','setup'])
    except Exception as exc:
        message(str(exc),True);return 1


if __name__=='__main__':raise SystemExit(main())
