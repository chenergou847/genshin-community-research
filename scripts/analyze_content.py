"""汇总已完成的语义编码；不按关键词生成观点或态度。仅使用标准库。"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import csv, hashlib, io, json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'analysis/content-20261024'
SOURCE = ROOT / 'materials/完整项目材料/01_当前交付/编码分析数据.json'
MODES = {'abyss': '深境螺旋', 'theater': '幻想真境剧诗', 'stygian': '幽境危战'}
START = {'abyss': '2026-10-16T04:00:00+08:00', 'theater': '2026-10-01T04:00:00+08:00', 'stygian': '2026-09-30T10:00:00+08:00'}
END = '2026-10-17T23:09:00+08:00'
VALENCE = {'P': '仅明确认可', 'N': '仅明确不满', 'M': '同条兼有认可与不满', '0': '未作明确体验评价', 'U': '评价不明'}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (list, dict)) else row.get(k, '') for k in fields})

def measure(rows, denominator):
    return {'n': len(rows), 'share': len(rows)/denominator if denominator else 0,
            'authors': len({r['author_id'] for r in rows}),
            'videos': len({r['bvid'] for r in rows}),
            'threads': len({r['root_id'] if r['root_id'] not in ('0', '', None) else r['id'] for r in rows})}

def summarize(rows, codes):
    n = len(rows)
    authors = defaultdict(set)
    for r in rows: authors[r['author_id']].add(r['valence'])
    categories = Counter()
    for states in authors.values():
        positive = bool(states & {'P', 'M'}); negative = bool(states & {'N', 'M'})
        key = 'both' if positive and negative else 'positive_only' if positive else 'negative_only' if negative else 'none_or_unclear'
        categories[key] += 1
    return {'denominator': n, 'authors': len(authors), 'videos': len({r['bvid'] for r in rows}),
            'valence': {v: measure([r for r in rows if r['valence'] == v], n) for v in VALENCE},
            'author_valence': {k: {'n': categories[k], 'share': categories[k]/len(authors) if authors else 0} for k in ['positive_only', 'negative_only', 'both', 'none_or_unclear']},
            'claims': {k: {'label': v['label'], **measure([r for r in rows if k in r['claims']], n)} for k, v in codes.items()}}

def main():
    source = json.loads(SOURCE.read_text(encoding='utf-8-sig'))['rows']
    book = json.loads((OUT/'codebook.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == book['source_sha256']
    annotations = [r for p in sorted((OUT/'batches').glob('*.json')) for r in json.loads(p.read_text(encoding='utf-8'))['records']]
    assert len(annotations) == len(source) == 6526
    assert sorted(r['seq'] for r in annotations) == list(range(1, 6527))
    indexed = {r['seq']: dict(r) for r in annotations}
    for change in json.loads((OUT/'corrections.json').read_text(encoding='utf-8')):
        indexed[change['seq']].update(change['changes'])
    focused = json.loads((OUT/'focused-views.json').read_text(encoding='utf-8'))['codes']
    for code, seqs in focused.items():
        for seq in seqs: indexed[seq]['claims'] = sorted(set(indexed[seq]['claims']) | {code})
    rows = []
    for seq, s in enumerate(source, 1):
        a = indexed[seq]
        if 'function' not in a:
            extra = {'gameplay_question':['question'], 'help_request':['question'], 'strategy_advice':['advice'], 'mechanism_tip':['advice']}.get(s['experience_kind'], [])
            a['claims'] = sorted(set(a['claims']) | set(extra))
        assert a['id'] == s['id'] and a['text_hash'] == s['text_hash']
        target = a.get('target_mode', s['mode'])
        assert target in MODES and a['valence'] in VALENCE
        assert set(a['claims']) <= set(book['codes'])
        assert not (a['relevance'] != 'related' and a['valence'] in {'P', 'N', 'M'}), seq
        window = datetime.fromisoformat(START[target]) <= datetime.fromisoformat(s['ctime_bjt']) <= datetime.fromisoformat(END)
        rows.append({**a, 'source_mode': s['mode'], 'target_mode': target,
                     'eligible': a['relevance'] == 'related' and window, 'target_window': window,
                     'function': a.get('function', s['experience_kind']),
                     'text': s['text'], 'ctime_bjt': s['ctime_bjt'], 'level': s['level'], 'like': s['like'],
                     'author_role': s['author_role'], 'context_status': s['context_status'],
                     'content_flags': s['content_flags'], 'context_ancestor_ids': s['context_ancestor_ids'],
                     'legacy_sentiment': s['sentiment'], 'legacy_relevance': s['relevance'],
                     'valence_label': VALENCE[a['valence']], 'claim_labels': [book['codes'][k]['label'] for k in a['claims']]})
    dump(OUT/'coded-statements.json', {'version': 'content-review-v1-final', 'unit': 'comment_id', 'rows': rows})
    flat = ['seq','id','source_mode','target_mode','eligible','target_window','bvid','author_id','root_id','parent_id','ctime_bjt','level','author_role','like','text','relevance','valence','valence_label','claims','claim_labels','basis','context_ancestor_ids','context_status','content_flags','text_hash','legacy_relevance','legacy_sentiment','reviewer','independent_validation']
    write_csv(OUT/'逐条内容编码.csv', rows, flat)
    stats = {'version': 'content-review-v1-final', 'total_reviewed': len(rows), 'relevance': dict(Counter(r['relevance'] for r in rows)),
             'excluded_target_window': sum(r['relevance']=='related' and not r['target_window'] for r in rows),
             'retargeted': sum(r['source_mode'] != r['target_mode'] for r in rows), 'modes': {}, 'sensitivity': {}, 'source_distribution': {}}
    claim_table=[]; attitude_table=[]; author_table=[]; sensitivity=[]
    for mode, label in MODES.items():
        related = [r for r in rows if r['eligible'] and r['target_mode']==mode]
        summary = summarize(related, book['codes']);stats['modes'][mode] = summary
        counts = Counter(r['bvid'] for r in related)
        dominant = counts.most_common(1)[0][0]
        stats['source_distribution'][mode] = dict(counts.most_common())
        variants = {
            'exclude_largest_video': [r for r in related if r['bvid'] != dominant],
            'roots_only': [r for r in related if r['level']=='root'],
            'viewers_only': [r for r in related if r['author_role'] == 'audience'],
            'exclude_promotion': [r for r in related if not any(('promo' in x.lower() or 'commercial' in x.lower()) for x in str(r['content_flags']).split(';'))],
            'deduplicate_author_text': list({(r['author_id'], r['text_hash']):r for r in related}.values()),
        }
        stats['sensitivity'][mode] = {k: summarize(v, book['codes']) for k,v in variants.items()}
        stats['sensitivity'][mode]['largest_video'] = dominant
        for code, item in summary['claims'].items(): claim_table.append({'mode':mode,'副本':label,'code':code,'观点':item['label'],'相关发言分母':summary['denominator'],'发言条数':item['n'],'发言占比':round(item['share'],6),'去重作者数':item['authors'],'来源视频数':item['videos'],'根线程数':item['threads']})
        for v, item in summary['valence'].items(): attitude_table.append({'mode':mode,'副本':label,'态度':VALENCE[v],'发言条数':item['n'],'相关发言分母':summary['denominator'],'占比':round(item['share'],6),'去重作者数':item['authors']})
        for v, item in summary['author_valence'].items(): author_table.append({'mode':mode,'副本':label,'作者评价':v,'作者数':item['n'],'相关作者分母':summary['authors'],'占比':round(item['share'],6)})
        for variant, result in stats['sensitivity'][mode].items():
            if variant=='largest_video': continue
            for code,item in result['claims'].items(): sensitivity.append({'mode':mode,'副本':label,'分层':variant,'code':code,'观点':item['label'],'发言条数':item['n'],'相关发言分母':result['denominator'],'占比':round(item['share'],6),'作者数':item['authors']})
    dump(OUT/'statistics.json', stats)
    for filename, table in [('观点分布.csv',claim_table),('发言评价分布.csv',attitude_table),('作者评价分布.csv',author_table),('敏感性分析.csv',sensitivity)]: write_csv(OUT/filename,table,list(table[0]))
    public = ROOT/'docs/data';public.mkdir(parents=True, exist_ok=True)
    for a,b in [('逐条内容编码.csv','content-coded.csv'),('观点分布.csv','content-statistics.csv'),('作者评价分布.csv','author-valence.csv')]: (public/b).write_bytes((OUT/a).read_bytes())
    for mode,s in stats['modes'].items():
        assert sum(x['n'] for x in s['valence'].values()) == s['denominator']
        assert sum(x['n'] for x in s['author_valence'].values()) == s['authors']
    print(json.dumps({'reviewed':6526,'relevance':stats['relevance'],'retargeted':stats['retargeted'],'excluded_target_window':stats['excluded_target_window'],'modes':{k:{'n':v['denominator'],'authors':v['authors'],'valence':{a:b['n'] for a,b in v['valence'].items()},'author_valence':v['author_valence']} for k,v in stats['modes'].items()}},ensure_ascii=False))

if __name__ == '__main__': main()
