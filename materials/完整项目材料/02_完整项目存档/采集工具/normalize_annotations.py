"""Expand explicitly authored annotation lists and let explicit rows override shorthand.

No text classification or defaults. Report conflicts and missing rows before recording.
"""
import sys
from pathlib import Path

p=Path(sys.argv[1]);start,end=map(int,sys.argv[2:4])
lines=p.read_text(encoding='utf-8-sig').splitlines()
explicit={int(x.split('|')[0]) for x in lines if x and not x.startswith(('@','#'))}
result=[];seen={};conflicts=[]
for line in lines:
    if not line or line.startswith('#'):continue
    if line.startswith('@'):
        parts=line.split('|');indices=[]
        for chunk in parts[-1].split(','):
            bounds=list(map(int,chunk.split('-')))
            indices.extend(n for n in range(bounds[0],bounds[-1]+1) if n not in explicit)
        if not indices:continue
        parts[-1]=','.join(map(str,indices));line='|'.join(parts)
        fields=line[1:].split('|')
        template=fields[:2] if len(fields)==3 else fields[:6]
        for n in indices:
            if n in seen and seen[n]!=template:conflicts.append(n)
            seen[n]=template
    else:seen[int(line.split('|')[0])]=line.split('|')[1:7]
    result.append(line)
print('missing',sorted(set(range(start,end+1))-set(seen)))
print('bulk_conflicts',conflicts)
if not conflicts:p.write_text('\n'.join(result)+'\n',encoding='utf-8')
