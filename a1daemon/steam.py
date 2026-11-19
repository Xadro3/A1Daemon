"""Own Steam adapter. Requires local CEF debugging; no Decky dependencies."""
import argparse
import json
import secrets
from pathlib import Path
import time
import urllib.request

from .cdp import CDP
from .resources import directory

ADAPTER = directory('steam') / 'adapter.js'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path, default=Path('/run/a1daemon/token'))
    parser.add_argument('--port', type=int, default=17641)
    parser.add_argument('--cef-port', type=int, default=8080)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    previous = None
    navigation_key = secrets.token_urlsafe(24)
    while True:
        clients = []
        try:
            token = '' if args.remove else args.token_file.read_text().strip()
            request = urllib.request.Request(f'http://127.0.0.1:{args.cef_port}/json')
            with urllib.request.urlopen(request, timeout=4) as response:
                targets = json.load(response)
            targets = [t for t in targets if t.get('title') == 'SharedJSContext' and t.get('webSocketDebuggerUrl')]
            if not targets:
                raise RuntimeError('Steam SharedJSContext is not available yet')
            status = []
            for target in targets:
                client = CDP(target['webSocketDebuggerUrl'])
                clients.append(client)
                expression = 'globalThis.__a1daemon?.dispose?.(); "removed"' if args.remove else ADAPTER.read_text(encoding='utf-8').replace('__A1_CONFIG__', json.dumps({'url': f'http://127.0.0.1:{args.port}/#token={token}', 'navigation_key': navigation_key}))
                result = client.call('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
                status.append(result.get('result', {}).get('value', 'Adapter returned no status'))
            message = json.dumps(status)
        except Exception as exc:
            message = f'Waiting for Steam sidebar: {exc}'
        finally:
            for client in clients:
                client.close()
        if message != previous:
            print(message, flush=True)
            previous = message
        if args.once or args.remove:
            return
        time.sleep(5)


if __name__ == '__main__':
    main()
