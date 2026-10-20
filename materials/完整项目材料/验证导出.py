"""Check this export using only Python's standard library."""
from pathlib import Path
import csv,hashlib,json
p=Path(__file__).resolve().parent
bad=[];count=0
with (p/'文件清单_SHA256.csv').open(encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f):
        x=p/row['relative_path'];count+=1
        if not x.is_file():bad.append(row['relative_path']+':missing');continue
        h=hashlib.sha256(x.read_bytes()).hexdigest()
        if x.stat().st_size!=int(row['bytes']) or h!=row['sha256']:bad.append(row['relative_path']+':mismatch')
print(json.dumps({'checked':count,'passed':not bad,'failures':bad},ensure_ascii=True))
raise SystemExit(1 if bad else 0)
