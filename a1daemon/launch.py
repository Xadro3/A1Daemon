"""Launch the standalone panel with a per-service authentication token."""
import argparse
from pathlib import Path
import webbrowser
from urllib.parse import quote

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path, default=Path('/run/a1daemon/token'))
    parser.add_argument('--port', type=int, default=17641)
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    webbrowser.open(f'http://127.0.0.1:{args.port}/#token={quote(token)}')

if __name__ == '__main__':
    main()
