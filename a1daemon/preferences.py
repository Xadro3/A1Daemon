"""Opt-in global settings, stored atomically outside the package tree."""
import json
from pathlib import Path
import threading

from .compat import Compatibility


class Preferences:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.enabled = self.path is not None
        self.lock = threading.RLock()

    def load(self):
        if not self.path or not self.path.exists():
            return {'version':1}
        if self.path.stat().st_size > 16384:
            raise ValueError('Preferences file is too large')
        value = json.loads(self.path.read_text())
        if not isinstance(value, dict) or value.get('version') != 1 or set(value) - {'version','power','rgb'}:
            raise ValueError('Unsupported preferences format')
        return value

    def update(self, kind, settings, remember):
        if not self.enabled:
            return
        with self.lock:
            data = self.load()
            if remember:
                data[kind] = settings.copy()
            else:
                data.pop(kind, None)
            self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            Compatibility.atomic(self.path, json.dumps(data, indent=2)+'\n')

    def summary(self):
        with self.lock:
            data = self.load()
            return {'available':self.enabled, 'power': 'power' in data, 'rgb':'rgb' in data}

    def restore(self, hardware):
        if not self.enabled or not hardware.writes or not hardware.supported():
            return None
        errors = []
        with self.lock:
            try:
                data = self.load()
            except (OSError, ValueError) as exc:
                return str(exc)
            for kind in ('power','rgb'):
                if kind in data:
                    try:
                        getattr(hardware,'set_'+kind)(**data[kind])
                    except Exception as exc:
                        errors.append(f'{kind}: {exc}')
        return '; '.join(errors) or None
