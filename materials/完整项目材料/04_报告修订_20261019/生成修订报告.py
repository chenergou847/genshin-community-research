"""仅以冻结数据生成修订报告；不联网、不编码、不修改CSV或原始档。"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT / '01_当前交付' / '编码分析数据.json'
RAW = ROOT / '02_完整项目存档/采集工具/正式采集_小样本v1_20261018/small_snapshot_frame_001.json'
TARGETS = [ROOT / '01_当前交付/04_社区观察分析报告.md',
           ROOT / '02_完整项目存档/全量编码_20261019/04_社区观察分析报告.md']
EVIDENCE = [331, 510, 1045, 1172, 1192, 1249, 1256, 1277, 1301,
            1437, 1440, 1445, 1449, 1705, 1731, 1787, 3480, 3487,
            3500, 3511, 3526, 3529, 3816, 4517, 4635, 5735]
SELECTED = {
    'abyss': ['roster_build', 'damage_threshold', 'mechanic_understanding',
              'encounter_timing', 'retry_time_cost', 'reward_motivation'],
    'theater': ['roster_build', 'damage_threshold', 'buff_and_route',
                'retry_time_cost', 'co_op_social', 'reward_motivation'],
    'stygian': ['roster_build', 'damage_threshold', 'mechanic_understanding',
                'operation_control', 'retry_time_cost', 'co_op_social', 'reward_motivation'],
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def table(headers, rows):
    def cell(x):
        return str(x).replace('|', '／').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


def pct(value):
    return f'{value * 100:.1f}%'


def build():
    d = read(INPUT)
    rows, st = d['rows'], d['statistics']
    raw = {r['id']: r for r in read(RAW)['comments']}
    q = {r.get('semantic_index'): r for r in rows if r.get('semantic_index')}
    excerpts = read(HERE / '报告引用摘录.json')
    assert len(rows) == len({r['id'] for r in rows}) == 6526
    assert Counter(r['mode'] for r in rows) == {'abyss': 1451, 'theater': 879, 'stygian': 4196}
    assert Counter(r['relevance'] for r in rows) == {'related': 4698, 'irrelevant': 1666, 'unknown': 162}
    assert Counter(r['level'] for r in rows) == {'root': 2288, 'reply': 4238}
    assert sum(bool(r['problem_themes']) for r in rows) == 706
    assert sum(r['like'] for r in rows) == 26488
    assert sum(r['like'] == 0 for r in rows) == 4516
    assert sum(sorted((r['like'] for r in rows), reverse=True)[:10]) == 6763
    assert len(raw) == 9593
    assert sum(r['level'] == 'root' for r in raw.values()) == 3251
    assert sum(r['human_reviewed'] for r in rows) == 30
    assert all(r['text'] == raw[r['id']]['text'] for r in rows)
    assert sum(t['image_unread'] for t in st['totals']) == 981
    assert sum(t['missing_ancestor'] for t in st['totals']) == 20
    study = RAW.parent
    seen, discovery_checks = set(), []
    for group, expected in [('main', (54, 157, 3118, 1381)),
                            ('audit_a', (18, 18, 320, 100)),
                            ('audit_b', (18, 18, 360, 92))]:
        queries = read(study / f'small_discovery_{group}.json')['queries']
        ids = {hit['bvid'] for query in queries for hit in query['hits']}
        actual = (len(queries), sum(len(query['pages']) for query in queries),
                  sum(len(query['hits']) for query in queries), len(ids - seen))
        assert actual == expected, (group, actual)
        assert all(query['status'] == 'bounded_complete' for query in queries)
        seen.update(ids)
        discovery_checks.append({'group': group, 'queries_pages_hits_new': actual})
    assert len(seen) == 1573
    candidates = read(study / 'small_candidate_frame.json')['records']
    assert len(candidates) == 1634
    assert Counter(r['mode'] for r in candidates) == {'abyss': 673, 'theater': 463, 'stygian': 498}
    selection = read(study / 'small_video_selection.json')
    assert len(selection['videos']) == 60
    for mode, prefix_n in [('abyss', 26), ('theater', 28), ('stygian', 25)]:
        domain = selection['domains'][mode]
        assert len(domain['selected']) == 20
        assert len(domain['prefix']) == prefix_n
    for x in st['metrics']:
        field = 'themes' if x['metric_type'] == '主题' else 'problem_themes'
        rs = [r for r in rows if r['mode'] == x['mode'] and r['relevance'] == 'related']
        selected = [r for r in rs if x['theme'] in r[field].split(';')]
        assert x['n'] == len(selected)
        assert x['related_denominator'] == len(rs)
        assert abs(x['equal_share_related'] - len(selected) / len(rs)) < 1e-10
        assert abs(x['attention_share'] - sum(r['attention_weight'] for r in selected) /
                   sum(r['attention_weight'] for r in rs)) < 1e-10
        assert x['sources'] == len({r['bvid'] for r in selected})

    def metric(mode, theme, kind='主题'):
        return next(x for x in st['metrics'] if x['mode'] == mode and
                    x['theme'] == theme and x['metric_type'] == kind)

    def sensitivity(mode, theme):
        x = next(x for x in st['sensitivities'] if x['mode'] == mode and
                 x['theme'] == theme and x['metric_type'] == '本人明确问题' and
                 x['scenario'] == 'exclude_largest_source')
        largest = next(t['largest_source'] for t in st['totals'] if t['mode'] == mode)
        rs = [r for r in rows if r['mode'] == mode and r['relevance'] == 'related' and r['bvid'] != largest]
        assert x['denominator'] == len(rs)
        assert x['n'] == sum(theme in r['problem_themes'].split(';') for r in rs)
        return x

    def quote(n):
        r, excerpt = q[n], excerpts[str(n)]
        assert excerpt in r['text']
        assert r['text'] == raw[r['id']]['text']
        assert r['like'] == raw[r['id']]['like']
        assert r['ctime_bjt'] == raw[r['id']]['ctime_bjt']
        return (f'> {excerpt}\n\n'
                f'[证据{n}｜原视频](https://www.bilibili.com/video/{r["bvid"]}/)'
                f'，评论ID `{r["id"]}`，{r["ctime_bjt"].replace("T", " ")}，'
                f'采集快照{r["like"]}赞。')

    repl = {}
    starts = {'abyss': '2026-10-16 04:00', 'theater': '2026-10-01 04:00', 'stygian': '2026-09-30 10:00'}
    windows, overview, concentration = [], [], []
    for t in st['totals']:
        m = t['mode']
        assert t['n'] == sum(r['mode'] == m for r in rows)
        sources = [s for s in st['sources'] if s['mode'] == m]
        windows.append([d['modes'][m], starts[m], '2026-10-17 23:09',
                        f'{sum(s["n"] > 0 for s in sources)}／20', f'{t["n"]:,}'])
        overview.append([d['modes'][m], f'{t["n"]:,}', f'{t["related"]:,}', t['irrelevant'],
                         t['unknown'], t['problem_comments'], pct(t['problem_comments'] / t['related'])])
        concentration.append([d['modes'][m], t['largest_source'],
                              f'{t["largest_source_n"]:,}／{t["n"]:,}', pct(t['largest_source_share'])])
        topic_rows = []
        for theme in SELECTED[m]:
            a, b = metric(m, theme), metric(m, theme, '本人明确问题')
            topic_rows.append([d['themes'][theme], f'{a["n"]:,}（{pct(a["equal_share_related"])}）',
                               f'{b["n"]}（{pct(b["equal_share_related"])}）', pct(a['attention_share']), a['sources']])
        repl[f'TOPICS_{m}'] = table(['主题', '谈及主题：条数（占比）', '本人该主题问题：条数（占比）',
                                      '谈及主题关注度', '谈及主题来源数'], topic_rows)
    overview.append(['合计', '6,526', '4,698', '1,666', '162', '706', '15.0%'])
    repl['WINDOWS'] = table(['副本', '评论窗口起点', '共同截止', '有窗口正文来源／锁定来源', '窗口正文'], windows)
    repl['OVERVIEW'] = table(['副本', '全部窗口发言', '相关', '不相关', '不明', '本人问题表达', '问题表达／相关'], overview)
    repl['CONCENTRATION'] = table(['副本', '窗口正文最多的来源', '该来源正文／副本正文', '占比'], concentration)
    sr = []
    for m, theme in [('abyss', 'mechanic_understanding'), ('theater', 'retry_time_cost'),
                     ('theater', 'buff_and_route'), ('stygian', 'damage_threshold'), ('stygian', 'roster_build')]:
        x, y = metric(m, theme, '本人明确问题'), sensitivity(m, theme)
        sr.append([d['modes'][m], d['themes'][theme], pct(x['equal_share_related']),
                   f'{y["n"]}／{y["denominator"]:,}', pct(y['share'])])
    repl['SENSITIVITY'] = table(['副本', '本人问题主题', '原占比', '去掉最大来源后条数／相关分母', '剩余占比'], sr)
    er = []
    for n in EVIDENCE:
        r = q[n]
        assert r['text'] == raw[r['id']]['text']
        er.append([n, d['modes'][r['mode']], f'[{r["bvid"]}](https://www.bilibili.com/video/{r["bvid"]}/)',
                   f'`{r["id"]}`', r['level'], r['like'], f'`{r["root_id"]}`'])
    repl['EVIDENCE_INDEX'] = table(['证据', '副本', '来源视频', '评论ID', '层级', '快照赞数', '根ID'], er)
    repl.update({f'Q{n}': quote(int(n)) for n in excerpts})
    template = (HERE / '报告正文模板.md').read_text(encoding='utf-8')
    assert set(re.findall(r'\{\{([^{}]+)\}\}', template)) == set(repl)
    report = re.sub(r'\{\{([^{}]+)\}\}', lambda m: repl[m[1]], template)
    assert '{{' not in report
    assert '## 4. 借鉴网络民族志' not in report
    assert '从观察到可验证的运营动作' not in report
    return report, {'coded_rows': len(rows), 'metrics_recalculated': len(st['metrics']),
                    'quote_excerpts_checked': len(excerpts), 'evidence_rows_checked': len(EVIDENCE),
                    'discovery_checked': discovery_checks,
                    'no_network_requests': True, 'raw_data_written': False,
                    'input_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只比对已生成正文，不写文件')
    args = parser.parse_args()
    report, checks = build()
    for i, path in enumerate(TARGETS):
        content = report if i == 0 else report.replace('../04_报告修订_20261019/', '../../04_报告修订_20261019/')
        if args.check:
            assert path.read_text(encoding='utf-8') == content, f'报告与来源不一致：{path}'
        else:
            path.write_text(content, encoding='utf-8', newline='\n')
    if not args.check:
        (HERE / '报告生成校验.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='checked' if args.check else 'written', **checks), ensure_ascii=False))


if __name__ == '__main__':
    main()
