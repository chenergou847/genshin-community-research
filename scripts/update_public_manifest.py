"""Refresh the public file inventory after intentional edits; validation remains separate."""
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'publication/public-files-sha256.csv'


def main():
    target = ROOT / MANIFEST
    previous = target.read_bytes().decode('utf-8').splitlines(keepends=True)
    old = {next(csv.reader([line]))[0]: line for line in previous[1:]}
    inventory = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT
    ).decode('utf-8').split('\0')
    current = {p for p in inventory if p and p != MANIFEST and (ROOT / p).is_file()}
    paths = [p for p in old if p in current] + sorted(current - set(old))
    lines, changed = [previous[0]], []
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if relative in old and next(csv.reader([old[relative]]))[2] == sha:
            lines.append(old[relative])
        else:
            output = io.StringIO(newline='')
            csv.writer(output, lineterminator='\n').writerow([relative, len(data), sha])
            lines.append(output.getvalue())
            changed.append(relative)
    target.write_bytes(''.join(lines).encode('utf-8'))
    print(json.dumps({'files': len(paths), 'changed_or_new': changed}, ensure_ascii=False))


if __name__ == '__main__':
    main()
