"""Loopback-only authenticated prototype API and settings panel."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time

from .hardware import Hardware, HardwareError
from .resources import directory
from .preferences import Preferences
from . import __version__

WEB = directory('web')


class Application:
    def __init__(self, hardware, token, preferences=None):
        self.hardware, self.token = hardware, token
        self.telemetry = {}
        self.error = None
        self.stop = threading.Event()
        self.preferences = preferences or Preferences()
        self.restore_error = None

    def sample_forever(self):
        suspended = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic() if hasattr(time, 'CLOCK_BOOTTIME') else 0
        while not self.stop.is_set():
            try:
                if hasattr(time, 'CLOCK_BOOTTIME'):
                    current = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
                    if current - suspended > 2:
                        if self.stop.wait(1):return
                        self.restore_error = self.preferences.restore(self.hardware)
                    suspended = current
                self.telemetry = self.hardware.sample()
                self.error = None
            except Exception as exc:
                self.error = str(exc)
            self.stop.wait(1)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log credentials or fragment-bearing launch URLs.

        def respond(self, status, data, mime='application/json'):
            body = json.dumps(data, allow_nan=False).encode() if mime == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            if mime.startswith('text/html'):
                self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

        def authenticated(self):
            return hmac.compare_digest(self.headers.get('Authorization', '').encode(), ('Bearer ' + app.token).encode())

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {'error': 'Invalid host'})
            if self.path.startswith('/api/'):
                if not self.authenticated():
                    return self.respond(401, {'error': 'Launch from A1Daemon to authenticate.'})
                if self.path == '/api/state':
                    try:
                        return self.respond(200, {**app.hardware.snapshot(), 'version':__version__, 'preferences':app.preferences.summary(), 'restore_error':app.restore_error, 'telemetry': app.telemetry, 'telemetry_error': app.error})
                    except Exception as exc:
                        return self.respond(503, {'error': str(exc)})
                return self.respond(404, {'error': 'Unknown endpoint'})
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/navigation.js': ('navigation.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path not in files:
                return self.respond(404, {'error': 'Not found'})
            name, mime = files[self.path]
            self.respond(200, (WEB / name).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host() or not self.authenticated():
                return self.respond(403, {'error': 'Unauthorized'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.respond(415, {'error': 'Expected application/json'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid request length')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected an object')
                remember = data.pop('remember', False)
                if not isinstance(remember, bool):
                    raise ValueError('Remember must be a boolean')
                if remember and not app.preferences.enabled:
                    raise ValueError('Settings persistence is unavailable in this development service')
                if self.path == '/api/power':
                    result = app.hardware.set_power(**data)
                elif self.path == '/api/rgb':
                    result = app.hardware.set_rgb(**data)
                else:
                    return self.respond(404, {'error': 'Unknown endpoint'})
                try:
                    app.preferences.update(self.path.removeprefix('/api/'), data, remember)
                except (OSError, ValueError) as exc:
                    raise OSError('Hardware settings were applied, but saving preferences failed: '+str(exc)) from exc
                self.respond(200, result)
            except (ValueError, TypeError, HardwareError) as exc:
                self.respond(400, {'error': str(exc)})
            except OSError as exc:
                self.respond(503, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=17641)
    parser.add_argument('--token-file', type=Path, default=Path('/run/a1daemon/token'))
    parser.add_argument('--enable-writes', action='store_true')
    parser.add_argument('--preferences-file', type=Path)
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    preferences = Preferences(args.preferences_file)
    app = Application(Hardware(writes=args.enable_writes), token, preferences)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(app))
    if args.enable_writes:
        app.restore_error = preferences.restore(app.hardware)
    args.token_file.parent.mkdir(parents=True, exist_ok=True)
    # O_NOFOLLOW prevents replacing a symlink with root privileges.
    descriptor = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o640)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(token)
    os.chmod(args.token_file, 0o640)
    server.daemon_threads = True
    threading.Thread(target=app.sample_forever, daemon=True).start()
    print(f'A1Daemon listening on http://127.0.0.1:{args.port}; writes={args.enable_writes}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
