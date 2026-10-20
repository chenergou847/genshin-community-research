"""仅核对本档逐文件字节、哈希与新增／缺失，不联网、不修改研究材料。"""
from pathlib import Path
import csv, hashlib, json

def main():
    root = Path(__file__).resolve().parent
    manifest = root / '04_全部文件清单_SHA256.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    bad, missing, expected = [], [], set()
    for row in rows:
        name = row['相对路径']; p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()):
            raise SystemExit('清单包含目录外路径')
        expected.add(name)
        if not p.is_file():
            missing.append(name); continue
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''):
                h.update(block)
        if p.stat().st_size != int(row['字节数']) or h.hexdigest() != row['SHA256']:
            bad.append(name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest}
    extra = sorted(actual-expected)
    result = {'status': 'PASS' if not (bad or missing or extra) else 'FAIL',
              'checked_files': len(rows), 'mismatches': bad, 'missing': missing, 'extra': extra}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)

if __name__ == '__main__':
    main()
