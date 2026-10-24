"""核对内容编码覆盖、源字段、统计与网页数据；不测语义判断准确率。"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import csv, hashlib, json, re

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'analysis/content-20261024'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def main():
    original=read(ROOT/'materials/完整项目材料/01_当前交付/编码分析数据.json')['rows']
    frame=read(ROOT/'materials/完整项目材料/02_完整项目存档/采集工具/正式采集_小样本v1_20261018/small_snapshot_frame_001.json')['comments']
    parents={r['id']:r for r in frame}
    rows=read(OUT/'coded-statements.json')['rows'];stats=read(OUT/'statistics.json');book=read(OUT/'codebook.json')
    assert len(rows)==6526 and len({r['id'] for r in rows})==6526
    batches=[r for p in (OUT/'batches').glob('*.json') for r in read(p)['records']]
    assert len(batches)==6526 and {r['seq'] for r in batches}==set(range(1,6527))
    starts={'abyss':'2026-10-16T04:00:00+08:00','theater':'2026-10-01T04:00:00+08:00','stygian':'2026-09-30T10:00:00+08:00'}
    for i,(r,s) in enumerate(zip(rows,original),1):
        assert r['seq']==i
        for k in ['id','text','text_hash','author_id','bvid','root_id','parent_id','ctime_bjt','level']: assert r[k]==s[k],(i,k)
        assert hashlib.sha256(r['text'].encode()).hexdigest()==r['text_hash'],i
        assert r['source_mode']==s['mode']
        assert not r['independent_validation']
        assert set(r['claims'])<=set(book['codes']) and len(set(r['claims']))==len(r['claims'])
        assert r['valence'] in book['valence'] and r['relevance'] in book['scope']
        expected_window=datetime.fromisoformat(starts[r['target_mode']])<=datetime.fromisoformat(r['ctime_bjt'])<=datetime.fromisoformat('2026-10-17T23:09:00+08:00')
        assert r['target_window']==expected_window
        assert r['eligible']==(r['relevance']=='related' and expected_window)
        if r.get('basis'): assert r['basis'] in r['text'] or any(r['basis'] in parents.get(cid,{}).get('text','') for cid in r['context_ancestor_ids']),i
    assert stats['relevance']==dict(Counter(r['relevance'] for r in rows))
    assert stats['retargeted']==sum(r['source_mode']!=r['target_mode'] for r in rows)
    assert stats['excluded_target_window']==sum(r['relevance']=='related' and not r['target_window'] for r in rows)
    for mode,s in stats['modes'].items():
        relevant=[r for r in rows if r['eligible'] and r['target_mode']==mode]
        assert len(relevant)==s['denominator']
        assert len({r['author_id'] for r in relevant})==s['authors']
        assert dict(Counter(r['bvid'] for r in relevant))==stats['source_distribution'][mode]
        for key,item in s['claims'].items():
            selected=[r for r in relevant if key in r['claims']]
            assert item['n']==len(selected) and item['authors']==len({r['author_id'] for r in selected})
            assert item['videos']==len({r['bvid'] for r in selected})
            assert abs(item['share']-len(selected)/len(relevant))<1e-12
        for v,item in s['valence'].items(): assert item['n']==sum(r['valence']==v for r in relevant)
        author=defaultdict(lambda:[False,False])
        for r in relevant:
            author[r['author_id']][0] |= r['valence'] in ('P','M')
            author[r['author_id']][1] |= r['valence'] in ('N','M')
        categories=Counter('both' if p and n else 'positive_only' if p else 'negative_only' if n else 'none_or_unclear' for p,n in author.values())
        for k,v in s['author_valence'].items(): assert v['n']==categories[k]
        sensitivity=stats['sensitivity'][mode]
        assert sensitivity['largest_video']==max(stats['source_distribution'][mode],key=stats['source_distribution'][mode].get)
        assert sensitivity['exclude_largest_video']['denominator']==sum(r['bvid']!=sensitivity['largest_video'] for r in relevant)
    with (OUT/'逐条内容编码.csv').open(encoding='utf-8-sig',newline='') as f: csv_rows=list(csv.DictReader(f))
    assert len(csv_rows)==6526
    for r,c in zip(rows,csv_rows):
        for k in ['id','text','target_mode','author_id','valence']: assert r[k]==c[k]
        assert r['claims']==json.loads(c['claims'])
    for a,b in [('逐条内容编码.csv','content-coded.csv'),('观点分布.csv','content-statistics.csv'),('作者评价分布.csv','author-valence.csv')]: assert (OUT/a).read_bytes()==(ROOT/'docs/data'/b).read_bytes()
    md=(ROOT/'report/报告.md').read_text(encoding='utf-8')
    quotes=re.findall(r'^> (.+)\n\n\[证据(\d+)｜原视频\]',md,re.M)
    assert len(quotes)==15
    for text,seq in quotes: assert text in rows[int(seq)-1]['text']
    print(json.dumps({'status':'PASS','source_rows_unchanged':6526,'batch_coverage':6526,'eligible':sum(r['eligible'] for r in rows),'authors_in_review':len({r['author_id'] for r in rows}),'quotes_verified':len(quotes),'validation_scope':'覆盖、源字段、原文哈希、时间窗、聚合、作者去重、CSV与引文；不含语义准确率'},ensure_ascii=False))

if __name__=='__main__': main()
