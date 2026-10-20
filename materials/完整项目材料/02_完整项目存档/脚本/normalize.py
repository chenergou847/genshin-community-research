"""Normalize actual DOM captures. No network, hidden API or keyword sentiment inference."""
from pathlib import Path
import csv, json, hashlib, re
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '数据'
sources = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA/'页面读取').glob('*.json'))]
raw, grouped, source_summary = [], {}, []
for source in sources:
    source_obs = []
    for batch in source['batches']:
        for row in batch['rows']:
            assert len(row) == len(source['columns'])
            item = dict(zip(source['columns'], row))
            assert not re.search(r'\d{6,}', item['text']), (source['source_id'], item['position'])
            item.update(source_id=source['source_id'], mode=source['mode'], period=source['period'],
                        url=source['url'], published_at=source['published_at'],
                        sort=batch['sort'], captured_at=batch['captured_at'])
            raw.append(item)
            source_obs.append(item)
            # This is a provisional matching key, NOT a verified platform comment ID.
            key = (item['source_id'], item['user_id'], item['text'])
            if key not in grouped:
                digest = hashlib.sha256('\0'.join(key).encode()).hexdigest()[:10]
                grouped[key] = {**item, 'record_id': f"{item['source_id']}-{item['user_id']}",
                                'match_key': digest, 'observations': []}
            grouped[key]['observations'].append({'sort':item['sort'],'position':item['position'],
                                                 'captured_at':item['captured_at'],
                                                 'date_display':item['date_display'],
                                                 'likes_display':item['likes_display']})
    source_rows = [r for k,r in grouped.items() if k[0] == source['source_id']]
    source_summary.append({'source_id':source['source_id'], 'mode':source['mode'],
                           'observations':len(source_obs), 'matched_records':len(source_rows),
                           'pinned':sum(bool(r['pinned']) for r in source_rows),
                           'hot':sum(r['sort']=='最热' for r in source_obs),
                           'new':sum(r['sort']=='最新' for r in source_obs)})
records = list(grouped.values())
assert len({r['record_id'] for r in records}) == len(records), 'Repeated same-author distinct comments need stable suffixes'
summary = {'source_count':len(sources),'page_observations':len(raw),
           'provisionally_matched_records':len(records),
           'pinned_records':sum(bool(r['pinned']) for r in records),
           'non_pinned_records':sum(not r['pinned'] for r in records),
           'anonymous_ids_including_authors':len({r['user_id'] for r in records}),
           'by_source':source_summary,
           'method':'同视频+匿名作者+脱敏原文暂合并；未取得平台评论ID，不能认证真实唯一评论数。'}
(DATA/'读取记录.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2),encoding='utf-8')
(DATA/'暂合并记录.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
(DATA/'采集摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
