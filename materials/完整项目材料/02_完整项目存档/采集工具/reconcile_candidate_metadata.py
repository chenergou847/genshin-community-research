"""After discovery stops, restore observed metadata from prior local versions.

Does not copy eligibility decisions or overwrite current observations. Keeps every
candidate; excludes only explicitly out-of-window dates under the user's new rule.
"""
import argparse
from pathlib import Path
from observer.core import Study, VIDEO_FIELDS, digest, now, read_csv, ts, write_csv, write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--study',required=True)
    args=parser.parse_args()
    s=Study(args.study)
    s.assert_mutable()
    rows=read_csv(s.path/'video_review.csv')
    fields=('published_at','aid','primary_up','coauthors','description','tags')
    sources=sorted((p for p in Path('.').glob('正式采集_v*_20261017') if p.resolve()!=s.path),
                   key=lambda p:p.stat().st_mtime,reverse=True)
    observations={}
    provenance=[]
    for source in sources:
        old=read_csv(source/'video_review.csv')
        provenance.append(dict(path=str(source),table_hash=digest(old)))
        for r in old:
            dest=observations.setdefault((r['bvid'],r['mode']),{})
            for k in fields:
                if r.get(k) and not dest.get(k):
                    dest[k]=r[k]
    restored,excluded=0,0
    for row in rows:
        prior=observations.get((row['bvid'],row['mode']),{})
        for k in fields:
            if prior.get(k) and not row.get(k):
                row[k]=prior[k]
                restored+=1
        if row['decision']=='pending' and s.config.get('video_publish_start') and row['published_at'].isdigit() and int(row['published_at']) < ts(s.config['video_publish_start']):
            row.update(decision='exclude',reason='早于用户确认的2026-09-01视频发布下限',reviewer='deterministic_date_rule_user_confirmed',notes='旧候选保留；元数据来自既有公开检索观测；仅按日期排除，不冒称人工内容核验')
            excluded+=1
    write_csv(s.path/'video_review.csv',rows,VIDEO_FIELDS)
    report=dict(at=now(),restored_metadata_fields=restored,excluded_outside_publication_window=excluded,
                sources=provenance,rows_hash=digest(rows),prior_eligibility_decisions_copied=False)
    write_json(s.path/'元数据回填记录.json',report)
    s.event('observed_metadata_restored',**report)
    print({'restored_fields':restored,'excluded_date_rows':excluded,'candidate_rows':len(rows)})


if __name__=='__main__':
    main()
