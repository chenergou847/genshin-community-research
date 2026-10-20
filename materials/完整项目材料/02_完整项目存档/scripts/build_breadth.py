"""将已读取的B站扩检索引与候选卡片转成可审阅文件，不发起网络请求。"""
import csv
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '数据'
raw = json.loads((DATA / '扩检批次索引.json').read_text(encoding='utf-8'))
source = json.loads((DATA / '扩检候选卡片.json').read_text(encoding='utf-8'))
rows = [dict(zip(source['columns'], row)) for row in source['rows']]
batches = raw['batches']
tz = timezone(timedelta(hours=8))
all_hits = [v for b in batches for v in b[7]]
assert len(batches) == 21 and len(all_hits) == 252
assert len(set(all_hits)) == 191
assert len(rows) == len({r['bvid'] for r in rows}) == 30
assert Counter(r['副本'] for r in rows) == {'深境螺旋': 10, '幻想真境剧诗': 10, '幽境危战': 10}
assert all(r['bvid'] in all_hits for r in rows)
pilot = {'BV1saaz6iEE6', 'BV12hYw6vEzC', 'BV1E8JX6wEyG', 'BV1AQJU6hE93', 'BV1D7YF6iEJi', 'BV1RAad68EjF'}
assert not pilot.intersection(r['bvid'] for r in rows)

def stamp_local(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(tz).isoformat(timespec='seconds')

def play_value(s):
    return int(Decimal(s[:-1]) * 10000) if s.endswith('万') else int(s)

def play_band(s):
    n = play_value(s)
    return '不足1000' if n < 1000 else '1000—9999' if n < 10000 else '10000及以上'

def write_csv(path, fields, records):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

query_records = []
hit_records = []
for bid, mode, query, sort, ts, start, end, vids in batches:
    params = {'keyword': query}
    if sort != '综合':
        params['order'] = {'最新': 'pubdate', '最多播放': 'click'}[sort]
    if start:
        params['pubtime_begin_s'] = int(datetime.fromisoformat(start).replace(tzinfo=tz).timestamp())
        params['pubtime_end_s'] = int((datetime.fromisoformat(end) + timedelta(days=1)).replace(tzinfo=tz).timestamp()) - 1
    query_records.append({'查询编号': bid, '副本': mode, '关键词': query, '排序': sort,
                          '读取时间_北京时间': stamp_local(ts), '发布日期起点': start or '未筛选',
                          '发布日期终点': end or '未筛选', '视频卡片数': len(vids),
                          '可复查检索URL_已规范化': 'https://search.bilibili.com/all?' + urlencode(params)})
    for seq, vid in enumerate(vids, 1):
        hit_records.append({'查询编号': bid, '副本': mode, '保留后读取序号_非原始排名': seq, 'bvid': vid,
                            '视频链接': f'https://www.bilibili.com/video/{vid}/',
                            '状态': '原始命中；未统一核对详情，不等于合格样本'})
write_csv(DATA / '扩检检索记录.csv', list(query_records[0]), query_records)
write_csv(DATA / '扩检全部命中索引.csv', list(hit_records[0]), hit_records)

export_rows = []
for r in rows:
    c = dict(r)
    c['播放量分段_按展示值'] = play_band(c['播放展示值'])
    c['读取时间_北京时间'] = stamp_local(c['UTC读取时间'])
    c['视频链接'] = f"https://www.bilibili.com/video/{c['bvid']}/"
    c['详情核验状态'] = '待核；仅搜索卡片可见'
    c['评论采集状态'] = '未采集'
    c['正式纳入状态'] = '候选；待核后决定'
    export_rows.append(c)
write_csv(ROOT / '08_扩检候选视频.csv', list(export_rows[0]), export_rows)

summary = {'检索批次': len(batches), '卡片观测次数': len(all_hits), '按BVID合并的原始入口': len(set(all_hits)),
           '新增候选': len(rows), '作者显示名数_非账号认证': len({r['作者显示名'] for r in rows}),
           '播放展示分段': dict(Counter(play_band(r['播放展示值']) for r in rows)),
           '内容入口初判': dict(Counter(r['内容入口初判'] for r in rows)), '副本': {}}
for mode in ['深境螺旋', '幻想真境剧诗', '幽境危战']:
    subset = [b for b in batches if b[1] == mode]
    selected = [r for r in rows if r['副本'] == mode]
    summary['副本'][mode] = {'批次': len(subset), '卡片观测次数': sum(len(b[7]) for b in subset),
                         '按BVID合并的命中': len(set(v for b in subset for v in b[7])),
                         '新增候选': len(selected), '作者显示名': len({r['作者显示名'] for r in selected}),
                         '播放展示分段': dict(Counter(play_band(r['播放展示值']) for r in selected))}
assert max(Counter((r['副本'], r['作者显示名']) for r in rows).values()) == 1
assert max(Counter(r['作者显示名'] for r in rows).values()) == 2
(DATA / '扩检覆盖摘要.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def md(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')

lines = ['# 扩检候选与覆盖', '', '2026-10-17，站内搜索读取。30条新增候选尚未核对详情、观看正文或采集评论；标题中的配置、结果和态度均不视为已认证事实。', '',
         '21批查询共252次视频卡片命中，按BVID合并191个原始视频入口，含旧版和误命中。精选30条新增候选，每副本10条，按作者显示名暂去重28位；与原6条试采视频不重叠。', '',
         '| 副本 | 查询批次 | 卡片观测 | BVID合并命中（含误命中） | 新增候选 | 不足1000播放 | 1000—9999 | 10000及以上 |',
         '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
for mode, stat in summary['副本'].items():
    band = stat['播放展示分段']
    vals = [mode, stat['批次'], stat['卡片观测次数'], stat['按BVID合并的命中'], stat['新增候选'], band.get('不足1000', 0), band.get('1000—9999', 0), band.get('10000及以上', 0)]
    lines.append('| ' + ' | '.join(map(str, vals)) + ' |')
lines += ['', '各副本命中会重叠，不能直接相加得到全局191。播放值是读取时的页面简写值，按展示值分段；不是粉丝规模，也不是总体抽样权重。', '',
          '候选初判：攻略/机制10条，普通实录8条，讨论/体验6条，低配/限制挑战3条，联机/匹配2条，高配/极限挑战1条。同一作者跨副本各有两条的是糖果味Ooo、御坂10312号；账号标识待核。', '',
          '以下链接打开原视频。完整原始标题、采集时间、查询命中及待核事项见[候选CSV](08_扩检候选视频.csv)。']
for mode in summary['副本']:
    lines += ['', f'## {mode}', '', '| 编号与视频原题 | 作者显示名 | 卡片日期 | 播放展示 | 入口初判 | 核查重点 |', '| --- | --- | --- | ---: | --- | --- |']
    for r in rows:
        if r['副本'] == mode:
            title = f"[{md(r['编号'])} · {md(r['标题原文'])}](https://www.bilibili.com/video/{r['bvid']}/)"
            lines.append('| ' + ' | '.join([title, md(r['作者显示名']), md(r['页面日期原文']), md(r['播放展示值']), md(r['内容入口初判']), md(r['选择理由与待核事项'])]) + ' |')
lines += ['', '## 使用边界', '',
          '这些候选拓宽了入口，尚未证明反馈方向和问题分布。尤其是“满分”“打不下去”“水温”等修辞，需要观看上下文后判断；“到第8幕”不能直接编码成失败；模式整体评价不能直接归到本期机制。', '',
          '原6条视频仅作为试采，已有202次根评论观测、166条暂合并记录（含3条置顶），另有7条定向回复；本轮没有新增评论。详情核验后再按每视频最多最热10条、最新10条横扫，实际不足据实记录。', '',
          '范围与采集规则见[检索范围修订](07_检索范围修订.md)。查询记录、全部命中索引和覆盖摘要均保存在`数据/`目录。']
(ROOT / '09_扩检候选与覆盖.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
