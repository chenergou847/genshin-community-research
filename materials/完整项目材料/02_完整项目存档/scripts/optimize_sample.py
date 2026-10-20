"""根据已发生的网页核验和明确取舍，生成v2样本清单；不联网、不采集评论。"""
import csv
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '数据'
audit = json.loads((DATA / '样本详情核验_20261017.json').read_text(encoding='utf-8'))
selection = json.loads((DATA / '样本取舍_v2.json').read_text(encoding='utf-8'))
cards = json.loads((DATA / '扩检候选卡片.json').read_text(encoding='utf-8'))

def fnv(value):
    s = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    h = 2166136261
    for ch in s:
        h = ((h ^ ord(ch)) * 16777619) & 0xffffffff
    return len(s), format(h, 'x')

assert fnv(audit['rows']) == (3548, 'e8b19b72'), '网页核验数据转存不一致'
assert len(audit['rows']) == len({r[0] for r in audit['rows']}) == 35
meta = {row[0]: dict(zip(audit['columns'], row)) for row in audit['rows']}
pool = {r[0]: {'编号': r[0], '副本': r[1], 'bvid': r[2], '标题': r[3], '发现查询': r[10]} for r in cards['rows']}
for sid, mode, bvid, title, hits in selection['extra_sources']:
    pool[sid] = {'编号': sid, '副本': mode, 'bvid': bvid, '标题': title, '发现查询': hits}
decisions = {r[0]: dict(zip(selection['columns'], r)) for r in selection['decisions']}
assert len(pool) == len(decisions) == 35 and set(pool) == set(decisions)
raw = json.loads((DATA / '扩检批次索引.json').read_text(encoding='utf-8'))
visible_bvids = {v for b in raw['batches'] for v in b[7]}
assert {s['bvid'] for s in pool.values()} <= visible_bvids

def band(s):
    n = int(Decimal(s[:-1]) * 10000) if s.endswith('万') else int(s)
    return '不足1000' if n < 1000 else '1000—9999' if n < 10000 else '10000及以上'

def route(s):
    if s == '攻略/机制':
        return '攻略/机制'
    if '普通实录' in s:
        return '普通实录'
    if '联机/匹配' in s:
        return '联机/匹配'
    return '讨论/体验'

tz = timezone(timedelta(hours=8))
out = []
for sid, candidate in pool.items():
    fact = meta[candidate['bvid']]
    choice = decisions[sid]
    comments = fact['comment_total_display']
    source = {**candidate, **choice,
        'UP主': fact['author'],
        'UP账号ID_文本': 'UID:' + fact['uid'],
        '公开UP主页': f"https://space.bilibili.com/{fact['uid']}",
        '发布时间_北京时间': fact['published_at_BJT'],
        '播放展示值_核验时': fact['play_display'],
        '播放分段_按展示值': band(fact['play_display']),
        '页面评论总数展示_非根评论数': comments,
        '加载根线程数_含可能置顶': fact['loaded_threads'],
        '评论入口状态': '页面显示零评论' if comments == '0' else '评论头与根线程可见；未建立正文样本',
        '详情核验时间_北京时间': datetime.fromisoformat(fact['captured_at_UTC'].replace('Z', '+00:00')).astimezone(tz).isoformat(timespec='seconds'),
        '视频链接': f"https://www.bilibili.com/video/{candidate['bvid']}/",
        '简介摘录_筛选用': audit['description_excerpts'].get(candidate['bvid'], ''),
        '补核标签原文': audit['tags'].get(candidate['bvid'], ''),
        '共同创作者_公开署名': '；'.join(f"{p['name']}（{p['credited_role']}；UID:{p['uid']}）" for p in audit['co_creators'].get(candidate['bvid'], [])),
        '核验边界': '已核标题、日期、公开主账号及评论入口；未完整看片，未逐条编码新增评论',
        '新增评论正文数据集': '未建立'
    }
    if sid == 'S-B07':
        source['本期归属状态'] = '条件保留：标题未明7.1，核实正文前不进本期问题统计'
    elif sid in {'T-B09', 'T-B10', 'S-C01', 'S-B09'}:
        source['本期归属状态'] = '背景或案例待核；不能直接归为本期具体问题'
    else:
        source['本期归属状态'] = '标题/简介/日期提供本期线索；评论仍须逐条归期'
    out.append(source)

main = [r for r in out if r['样本用途'] == '主观察']
assert len(main) == len({r['UP账号ID_文本'] for r in main}) == 15
assert Counter(r['副本'] for r in main) == {'深境螺旋': 5, '幻想真境剧诗': 5, '幽境危战': 5}
assert all(Counter(r['内容入口复判'] for r in main if r['副本'] == m)['攻略/机制'] <= 2 for m in ['深境螺旋', '幻想真境剧诗', '幽境危战'])
assert Counter(r['样本用途'] for r in out) == {'主观察': 15, '专项对照': 5, '视频案例': 9, '背景待核': 3, '候补': 3}
assert sum(r['页面评论总数展示_非根评论数'] == '0' for r in out) == 10
assert all(r['页面评论总数展示_非根评论数'] != '0' for r in main)

with (ROOT / '11_优化样本清单.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(out[0]))
    writer.writeheader()
    writer.writerows(out)

summary = {
    '版本': selection['version'], '已核视频入口': len(out), '公开主UP账号数': len({r['UP账号ID_文本'] for r in out}),
    '原候选核验': 30, '原命中池补核': 5,
    '用途': dict(Counter(r['样本用途'] for r in out)),
    '主观察来源数': len(main), '主观察不同主UP账号数': len({r['UP账号ID_文本'] for r in main}),
    '主观察入口类型': dict(Counter(route(r['内容入口复判']) for r in main)),
    '主观察播放分段': dict(Counter(r['播放分段_按展示值'] for r in main)),
    '页面零评论来源数': 10, '零评论用途': dict(Counter(r['样本用途'] for r in out if r['页面评论总数展示_非根评论数'] == '0')),
    '条件主观察': ['S-B07'], '新增评论正文样本数': 0,
    '注意': '15是来源名单，不是15条已分析视频；不把加载线程数计为已采集评论。'
}
(DATA / '样本覆盖_v2.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def md(s):
    return str(s).replace('|', '\\|').replace('\n', '<br>')

lines = [
    '# 优化后的样本来源与取舍（v2）', '',
    '2026-10-17。已逐条打开原30条候选详情与评论入口，并从此前191个原始命中中补核5条。核验内容为标题、发布时间、公开主账号、简介和评论入口状态；个别含糊来源另查标签。尚未完整观看视频或建立新增评论正文样本。', '',
    '**本轮结果：35条核验记录，收敛为15条主观察入口，每副本5条、15个不同主UP账号；另外保留专项对照5条、视频案例9条、背景待核3条、候补3条。**主观察中S-B07的具体版本仍待核，核实前不进本期问题统计。', '',
    '这是用于发现体验问题的目的抽样。取舍规则在本轮核验过程中形成，没有伪装成预注册或随机抽样；增加覆盖与可追溯性不能消除搜索算法、发视频和发表评论的自选择偏差。', '',
    '## 可复用任务描述', '',
    '面向原神产品运营岗位的B站社区观察，优化近期深境螺旋、幻想真境剧诗、幽境危战的来源名单。通过核对期次线索、公开作者身份、内容入口和评论可用性，减少攻略及挑战内容集中；保留低曝光、低互动及零评论案例。先按固定口径横向读取，再验证具体体验问题，报告来源、反例与边界，不估计全体玩家问题发生率。', '',
    '## 15条主观察入口', '',
    '主观察每副本最多2条攻略入口；保留普通实录与讨论，幽境另保留匹配入口。每个主账号只保留1条。账号不同只能证明账号去重，不能证明信息链或经历完全独立，正文中的引用仍需继续记录。播放分段按读取时展示值计算：不足1000为4条，1000—9999为4条，10000及以上为7条；这些比例是覆盖安排，没有总体权重含义。', '',
    '表中评论数字为“页面总数展示 / 当时已加载根线程”，根线程含可能的置顶。总数可能含回复，两者均不是本研究已纳入的评论数。'
]
for mode in ['深境螺旋', '幻想真境剧诗', '幽境危战']:
    lines += ['', f'### {mode}', '', '| 来源与原题 | 主UP | 入口 | 播放展示 | 评论总数/加载线程 | 选取理由 |', '| --- | --- | --- | ---: | ---: | --- |']
    for r in main:
        if r['副本'] != mode:
            continue
        title = f"[{md(r['编号'])} · {md(r['标题'])}]({r['视频链接']})"
        author = f"[{md(r['UP主'])}]({r['公开UP主页']})"
        lines.append('| ' + ' | '.join([title, author, md(r['内容入口复判']), r['播放展示值_核验时'], f"{r['页面评论总数展示_非根评论数']}/{r['加载根线程数_含可能置顶']}", md(r['取舍依据'])]) + ' |')
lines += [
    '', '## 其余来源的用途', '',
    '| 用途 | 数量 | 处理方式 |', '| --- | ---: | --- |',
    '| 专项对照 | 5 | 低金限制挑战、满命配置自述、助演依赖流程单列。出现的问题仍可成案，结论限定具体条件，不用挑战成绩定义普通玩家难度。 |',
    '| 视频案例 | 9 | 本次均显示零评论，仍保留低曝光、角色环境、N4/N5/N6和联机记录。只有核对视频内容后才能作为作者经历，不能冒充社区多人反馈。 |',
    '| 背景待核 | 3 | 期次含糊、跨两年整体评价、未明确高难的日常资源刷取，暂不作本期具体问题的直接证据。 |',
    '| 候补 | 3 | 相似攻略保留备查，避免持续叠加求助型评论区；补位须记录失效原因和覆盖维度，不能因观点符合预设而换入。 |', '',
    '完整35条的逐项理由、公开账号、核验日期与限制见[优化样本清单CSV](11_优化样本清单.csv)。来源用途不会决定某条反馈是否值得处理，只决定可支持的结论范围。', '',
    '## 本次实际修正', '',
    '- 原30条中9条在核验时显示零评论；新补核的日常刷取来源也为零，共10条。没有拿高互动视频把它们全部替换掉：9条进入案例库，另1条因高难相关性不足保留背景。',
    '- A-B05仅显示1条评论、1个根线程仍留主观察；T-C02仅显示2条、2个根线程仍留主观察。不设最低评论量门槛凑满样本。',
    '- S-C02显示20条评论，当时加载4个根线程；T-B07显示5条、加载2个根线程。后续分别记录总数、根评论观测和暂合并结果。',
    '- A-B07简介写满命角色，改为特定投入情境对照；A-B03、A-B10、S-B04的限制挑战也分别记录。它们的正负表达均不等于普通玩家的体验分布。',
    '- T-C01标题的最低28人+1助演并不等于低门槛，简介又推荐2命及以上助演，因此单列为流程与助演条件对照。',
    '- T-B09的修辞标题及空白简介不足以确认本期具体内容，T-B10则为跨两年的模式评价，均转背景。补入T-C03：标题直接指明7.1与水冰风，作为更明确的当期讨论入口；实际态度仍待上下文核查。',
    '- 已按公开UID确认糖果味Ooo在A-B10/S-B04、御坂10312号在A-B08/S-B05重复出现。主观察15条没有重复主账号；专项与案例跨视频并用时仍须合并作者关系。',
    '- S-B02为联合创作，页面署名唔得比（UP主）与Kolliter（策划角色）；一条作品不算两个独立来源。T-B05简介明确引用原试采作者的攻略，也不当作独立机制复现。',
    '- 已另开原试采A03核对UID，确认与T-C03同为七号小食堂（383695402）。试采与主观察名单分开，合并讨论时不把两个副本的视频算作两位独立作者。', '',
    '## 正式读取前冻结的规则', '',
    '1. 此版名单在新增评论编码前冻结。原6条试采仍独立保存，不直接并入新名单的分母。若来源失效或正文归期不符，在CSV记录原编号、原因与替代者；优先同覆盖维度，不按情绪选补位。',
    '2. 主观察每条最多读取非置顶根评论最热前10条与最新前10条；实际不足据实记录。置顶、作者补充、回复分开。不用其他视频的更多评论补足空缺，也不为凑满300条而不断追加。',
    '3. 每条评论核对实际期次、难度、配置与自述结果；不由视频标题补齐。正向、受阻后通过、未通过、降档、奖励满足即止和无法判断都可保留，不给情绪配额。专项与案例作为独立用途记录，不混成总体比例。',
    '4. 同一问题报告来源分布、不同发言者与反例；同UP、协作或明确引用关系单列。能识别的重复发言去重，无法核准跨视频身份时明确保留限制。跨视频出现也不直接称普遍。',
    '5. 编码后逐一移除视频复核结论：若一项解释依赖单一视频或作者，就降为个案或特定受众线索。该检验目前尚未执行，因为新增评论正文还未建立。', '',
    '## 仍存在的缺口', '',
    '- S-B07标题未明7.1，标签兼有搞笑与游戏实况。核实版本及实际情境前只保留匹配讨论入口，不进本期问题统计。',
    '- N4目前有视频案例，没有确认的独立评论覆盖；深渊11层及以下的评论覆盖也未确认。不能把15条名单说成覆盖所有难度。',
    '- 未解锁、主动放弃、不追满奖励等经历尚未完成逐条识别。上传通关视频与愿意评论者更可见，沉默者仍无法通过此名单观察。',
    '- 深渊发布窗口只有10/16—10/17；剧诗、幽境包含更长时间跨度。不能把三副本的反馈数量或失败自述直接当作可比难度。',
    '- 作者定位和播放量不能替代玩家资历、付费或配置分层；这些条件只能从明确自述记录，并标记自述与缺失。', '',
    '本轮完成的是来源核验与样本用途优化。原试采数据仍为202次根评论观测、166条暂合并记录（含3条置顶），另有7条定向回复；本轮没有新增已编码评论，也没有完成最终体验报告。'
]
(ROOT / '10_样本优化与取舍.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

# 修正旧候选表的当前核验状态，同时保留原卡片日期等历史字段。
old_path = ROOT / '08_扩检候选视频.csv'
with old_path.open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    old_fields = reader.fieldnames
    old_rows = list(reader)
new_fields = ['样本用途_v2', '详情核验发布时间_北京时间', '核验公开UP主页', '当前取舍入口']
old_fields += [k for k in new_fields if k not in old_fields]
by_id = {r['编号']: r for r in out}
for row in old_rows:
    current = by_id[row['编号']]
    row['详情核验状态'] = '已直接核对标题、日期、公开主账号及评论入口；正文归期未完成'
    row['正式纳入状态'] = current['样本用途'] + '；尚未完成正文分析'
    row['样本用途_v2'] = current['样本用途']
    row['详情核验发布时间_北京时间'] = current['发布时间_北京时间']
    row['核验公开UP主页'] = current['公开UP主页']
    row['当前取舍入口'] = '10_样本优化与取舍.md / 11_优化样本清单.csv'
with old_path.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=old_fields)
    writer.writeheader()
    writer.writerows(old_rows)
print(json.dumps(summary, ensure_ascii=False, indent=2))
