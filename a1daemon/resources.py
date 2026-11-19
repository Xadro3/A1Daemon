from pathlib import Path


def directory(name):
    source = Path(__file__).resolve().parent.parent / name
    return source if source.is_dir() else Path('/usr/share/a1daemon') / name
