"""Create a consistent local SQLite backup without stopping the application."""
import argparse
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    source, destination = Path(args.source).resolve(), Path(args.destination).resolve()
    if not source.is_file() or destination.exists() or source == destination:
        parser.error('Kaynak var olmalı; hedef yeni bir dosya olmalı.')
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src:
        with sqlite3.connect(str(destination)) as dst:
            src.backup(dst)
    destination.chmod(0o600)


if __name__ == '__main__':
    main()
