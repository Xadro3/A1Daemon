"""KDE graphical setup; elevation is performed only through the OS polkit dialog."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile

from . import __version__
from .diagnostics import collect
from .platforms import support


def dialog(*args):
    result=subprocess.run(['/usr/bin/kdialog','--title','A1Daemon '+__version__,*args],capture_output=True,text=True)
    return result.returncode,result.stdout.strip()


def run(command, allow_failure=False):
    result=subprocess.run(command,capture_output=True,text=True,timeout=180)
    if result.returncode and not allow_failure:
        raise RuntimeError((result.stderr or result.stdout or 'The operation was cancelled or failed.')[-4000:])
    return result


def user_state():
    base=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))
    path=base/'a1daemon/setup.json'
    return path,json.loads(path.read_text()) if path.exists() else {}


def configure():
    supported,reason=support()
    if not supported:raise RuntimeError(reason)
    code,selection=dialog('--checklist',reason+'\nChoose the integration to enable. Existing controller software stays in place.',
        'compat','Wi-Fi resume and keyboard wake workarounds','on',
        'sidebar','Start the Steam sidebar at login (requires local CEF debugging)','on')
    if code:return
    import shlex
    selected=shlex.split(selection)
    user=pwd.getpwuid(os.getuid()).pw_name
    command=['/usr/bin/pkexec','/usr/bin/a1daemon','setup-system','install','--user',user]
    if 'compat' in selected:command.append('--compatibility')
    dialog('--passivepopup','Applying setup. Approve the operating system authorization dialog when asked.','5')
    run(command)
    state_path,state=user_state()
    run(['/usr/bin/systemctl','--user','stop','a1daemon-steam-adapter.service'],True)
    run(['/usr/bin/systemctl','--user','daemon-reload'])
    if 'sidebar' in selected:
        steam=next((p.resolve() for p in [Path.home()/'.steam/steam',Path.home()/'.local/share/Steam'] if p.is_dir()),None)
        if steam is None:raise RuntimeError('Hardware service installed, but Steam was not found. Install Steam, then use Repair.')
        marker=steam/'.cef-enable-remote-debugging'
        if not marker.exists():marker.touch();state['created_cef_marker']=str(marker)
        run(['/usr/bin/systemctl','--user','enable','--now','a1daemon-steam.service'])
    else:
        run(['/usr/bin/systemctl','--user','disable','--now','a1daemon-steam.service'],True)
    state_path.parent.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps(state,indent=2)+'\n')
    dialog('--msgbox','Setup is complete. Power and lighting changes require Apply.\n\nIf Steam is already open, restart it when convenient to enable local debugging, then enter Big Picture. An active game has not been closed.')


def remove():
    code,_=dialog('--warningyesno','Remove A1Daemon integration and its package?\nSaved settings are retained locally. Our compatibility changes are restored. Other software is left in place.')
    if code:return
    run(['/usr/bin/systemctl','--user','disable','--now','a1daemon-steam.service'],True)
    run(['/usr/bin/pkexec','/usr/bin/a1daemon','setup-system','remove'])
    state_path,state=user_state()
    marker=state.get('created_cef_marker')
    allowed=[(Path.home()/'.steam/steam').resolve()/'.cef-enable-remote-debugging',(Path.home()/'.local/share/Steam').resolve()/'.cef-enable-remote-debugging']
    if marker and Path(marker) in allowed:Path(marker).unlink(missing_ok=True)
    state_path.unlink(missing_ok=True)
    run(['/usr/bin/pkexec','/usr/bin/pacman','-R','--noconfirm','a1daemon'])
    dialog('--msgbox','A1Daemon removed. Restart Steam when convenient to remove any in-memory sidebar tab and debugging session.')


def export():
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',delete=False) as stream:
        temporary=Path(stream.name)
        stream.write(json.dumps(collect(),indent=2)+'\n')
    try:
        code,_=dialog('--textbox',str(temporary),'800','550')
        if code:return
        code,target=dialog('--getsavefilename',str(Path.home()/'a1daemon-support.json'),'*.json')
        if code==0 and target:shutil.copyfile(temporary,target)
    finally:temporary.unlink(missing_ok=True)


def main():
    if os.geteuid()==0:raise SystemExit('Open setup as the desktop user; authorization is requested for system changes only.')
    try:
        code,action=dialog('--menu','A1Daemon 0.5 prototype · MSI Claw A1M\nChoose an action:',
            'install','Install or repair integration','open','Open Claw Control',
            'diagnostics','Review and export support report','remove','Uninstall')
        if code:return
        if action=='install':configure()
        elif action=='remove':remove()
        elif action=='diagnostics':export()
        elif action=='open':run(['/usr/bin/a1daemon','launch'])
    except Exception as exc:dialog('--error',str(exc))


if __name__=='__main__':main()
