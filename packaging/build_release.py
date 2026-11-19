"""Build clean source/installer archives; no raw baselines, SSH scripts or credentials."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

VERSION='0.5.0'
ROOT=Path(__file__).resolve().parent.parent


def source(output):
    files=[]
    for directory in ['a1daemon','web','steam','packaging','tests','docs','.github']:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in {'packaging/a1daemon.service','packaging/a1daemon-steam.service'})
    files.extend(ROOT/name for name in ['README.md','LICENSE','pyproject.toml','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md','THIRD_PARTY.md','.gitignore','.gitattributes'] if (ROOT/name).exists())
    archive=output/f'a1daemon-{VERSION}.tar.gz'
    memory=io.BytesIO()
    with tarfile.open(fileobj=memory,mode='w',format=tarfile.PAX_FORMAT) as bundle:
        for path in sorted(files):
            if path.is_symlink():raise ValueError('Source symlinks are not permitted: '+str(path))
            relative=path.relative_to(ROOT).as_posix()
            data=path.read_text(encoding='utf-8').replace('\r\n','\n').encode()
            info=tarfile.TarInfo(f'a1daemon-{VERSION}/'+relative)
            info.size=len(data);info.mode=0o644;info.mtime=0
            bundle.addfile(info,io.BytesIO(data))
    archive.write_bytes(gzip.compress(memory.getvalue(),mtime=0))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'PKGBUILD').write_text((ROOT/'packaging/arch/PKGBUILD').read_text().replace('@SOURCE_SHA256@',digest),newline='\n')
    (output/'a1daemon.install').write_text((ROOT/'packaging/arch/a1daemon.install').read_text(),newline='\n')
    return archive


def installer(output,package):
    manifest={'version':VERSION,'package':package.name,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()}
    archive=output/f'A1Daemon-{VERSION}-CachyOS-Setup.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in ['setup.py','A1Daemon-Setup.desktop']:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.external_attr=(0o100755<<16)
            bundle.writestr(info,(ROOT/'packaging/bootstrap'/name).read_text().encode())
        bundle.writestr(package.name,package.read_bytes())
        bundle.writestr('bundle.json',json.dumps(manifest,indent=2)+'\n')
        bundle.writestr('START-HERE.txt','A1Daemon 0.5.0 prototype - CachyOS / MSI Claw A1M\n\n1. Extract this archive in Desktop Mode.\n2. Open A1Daemon-Setup.desktop and approve the desktop trust prompt if shown.\n3. Install, authorize with the OS dialog, then choose integration options.\n4. Restart Steam yourself when ready. No terminal commands are needed.\n\nSource and limitations: https://github.com/Xadro3/aidaemon\nMIT license. Independent project, no vendor/distro endorsement.\n')
    return archive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    parser.add_argument('--package',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    artifact=installer(args.output,args.package) if args.package else source(args.output)
    checksum=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (args.output/(artifact.name+'.sha256')).write_text(checksum+'  '+artifact.name+'\n')
    print(artifact)


if __name__=='__main__':main()
