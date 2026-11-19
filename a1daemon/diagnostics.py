"""Deliberately allowlisted diagnostics: no raw logs or device serials."""
import argparse
import json
from pathlib import Path
import platform
import subprocess

from . import __version__
from .hardware import Hardware
from .platforms import os_release


def collect():
    hardware=Hardware()
    packages={}
    for package in ['linux-cachyos-deckify','mesa','vulkan-intel','linux-firmware-intel','inputplumber','hhd','gamescope']:
        try:
            result=subprocess.run(['/usr/bin/pacman','-Q',package],capture_output=True,text=True,timeout=3)
            if result.returncode==0:packages[package]=result.stdout.strip().split(maxsplit=1)[1]
        except (OSError,subprocess.TimeoutExpired):pass
    release=os_release()
    return {'application':'A1Daemon','version':__version__,'kernel':platform.release(),
            'os':{key:release[key] for key in ['ID','VERSION_ID','BUILD_ID'] if key in release},
            'hardware':hardware.snapshot()['device'],'packages':packages,
            'capabilities':{'supported_board':hardware.supported(),'rgb':hardware.rgb_state()['available'],
                            'power_interfaces':[i['interface'] for i in hardware.power_state()['interfaces']],
                            'sleep_modes':hardware.read(hardware.path('/sys/power/mem_sleep'))},
            'privacy':'Allowlisted metadata only. No passwords, tokens, Wi-Fi names, serials, account data or raw journals are collected.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    text=json.dumps(collect(),indent=2)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')


if __name__=='__main__':main()
