"""Package the observed first random-prefix review; does not finalize eligibility."""
from collections import Counter
from pathlib import Path
from observer.core import Study, MODES, NAMES, digest, now, read_csv, write_json
from observer import small


def main():
    s = Study('正式采集_小样本v1_20261018')
    small.check(s)
    if (s.path / 'small_video_review_batch_001_confirmation.json').exists():
        s.frozen('small_video_review_batch_001_confirmation.json')
        print({'status': 'already_human_confirmed_read_existing_artifact'})
        return
    frame = s.frozen('small_candidate_frame.json')
    draw = s.frozen('small_video_draw.json')
    rows = {(r['mode'], r['bvid']): r for r in read_csv(s.path / 'small_video_review.csv')}
    observations = {
        ('abyss', 'BV1ABh26QEQ3'): dict(proposed_decision='exclude', content_type='实录',
            reason='视频明确标为9月深境螺旋，不是10月16日本期。',
            content_evidence='页面标题明确写9月；已查看视频开头深渊战斗画面。9月25日发布只作辅助证据，不能单凭提前发布排除前置攻略。',
            unresolved='等待用户核定排除；没有将AI初判填成人工定稿。'),
        ('abyss', 'BV1jjJY6MEwP'): dict(proposed_decision='include', content_type='实录',
            reason='7.1B深渊实录，10月17日发布，候选指向本期。',
            content_evidence='标题【深渊7.1B】；视频开头实机画面显示第12层第1间上半及95级敌人。',
            unresolved='需用户确认实机对应10月16日本期；未独立核完六间敌人，不把标题单独当作内容期次证明。'),
        ('theater', 'BV18wJt65E7V'): dict(proposed_decision='exclude', content_type='其他副本实录',
            reason='剧诗候选中命中了深境螺旋视频。',
            content_evidence='标题【2026年10月深渊】；实际播放开头画面显示第11层第1间及深渊祝福选择。',
            unresolved='仅排除其剧诗归属，不将它手动加入深渊随机队列。'),
        ('theater', 'BV1ovJa6TEMr'): dict(proposed_decision='exclude', content_type='其他活动',
            reason='讨论判测胜券本征竞猜活动，不是幻想真境剧诗。',
            content_evidence='页面标题和简介为当日预测；实机画面为两队竞猜、支持率及圈选预测，不是剧诗。',
            unresolved='等待用户核定排除。'),
        ('stygian', 'BV1myaB6BEm8'): dict(proposed_decision='include', content_type='攻略',
            reason='明确讨论7.1幽境危战三战场通关。',
            content_evidence='标题明确7.1及丘林老头/冰锅/冰棺；播放器章节可见丘林、冰锅；实际抽查到战斗及攻略开场说明。',
            unresolved='需用户确认三敌人组合对应9月30日本期；没有把整段27分29秒视频写成已完整观看。'),
        ('stygian', 'BV1zLJv6mE8T'): dict(proposed_decision='include', content_type='实录/直播切片',
            reason='幽境危战绝境挑战实录，10月17日发布。',
            content_evidence='实际视频开头展示幽境危战绝境三战场配队、110级敌人及三场73/83/60秒记录；仅作玩法及组合线索。',
            unresolved='需用户确认画面三敌人组合对应本期；标题没有期次，不能只按发布日期认定。'),
    }
    records = []
    for mode in MODES:
        for position, bv in enumerate(draw['orders'][mode][:2], 1):
            key = (mode, bv)
            r = rows[key]
            records.append(dict(mode=mode, position=position, bvid=bv, title=r['title'],
                published_at=r['published_at'], aid=r['aid'], primary_up=r['primary_up'],
                url='https://www.bilibili.com/video/' + bv + '/',
                reviewer='AI', final='no', review_kind='ai_proposal',
                observation_method='normal_public_web_metadata_and_CUA_rendered_page_video_spot_check',
                **observations[key]))
    path = s.path / 'small_video_review_batch_001_proposal.json'
    if path.exists():
        proposal = s.frozen(path.name)
    else:
        proposal = small.seal(s, path.name, dict(candidate_frame_hash=digest(frame),
            video_draw_hash=digest(draw), records=records,
            note='AI资格初判材料；不是已入选视频、完整观看记录或用户审核结果'))
    current = small.status(s)
    current.update(stage='CANDIDATE_FRAME_FROZEN_VIDEO_ELIGIBILITY_PENDING',
                   at=now(), formal_eligible_videos_locked=0,
                   formal_random_raw_comments_drawn=0,
                   first_review_proposals=len(records), first_review_human_final=0)
    write_json(s.path / '执行状态.json', current)
    counts = Counter(r['mode'] for r in frame['records'])
    lines = ['# 候选库冻结与首批随机来源资格核验', '',
        '更新时间：2026-10-18，北京时间。用户要求继续执行17号方案；没有更改关键词、页数、时间窗口或抽样种子。', '',
        '可复用任务描述：完成固定深度发现与遗漏审计，冻结候选库及随机顺序；从每副本随机前缀核验本期内容，人工核定后继续筛选至每副本20条合格来源，再采集入选视频的完整评论清单。', '',
        '## 已完成的真实执行', '',
        '- 复用成功缓存，只请求原来未成功的页面；正常会话恢复后完成主查询54/54、审计A 18/18、审计B 18/18。',
        '- 三组均已封存；已冻结候选库及一次随机全排列，没有重复抽种子。',
        f'- 不同候选视频1573个，视频×副本记录1634行：深渊{counts["abyss"]}、剧诗{counts["theater"]}、幽境{counts["stygian"]}。这些仍是候选，不是合格视频数。', '',
        '| 检索组 | 深渊新增候选 | 剧诗新增候选 | 幽境新增候选 |',
        '| --- | ---: | ---: | ---: |']
    for group, counts_by_mode in frame['new_candidate_counts'].items():
        lines.append('| ' + group + ' | ' + ' | '.join(str(counts_by_mode[m]) for m in MODES) + ' |')
    lines += ['', '新增按BVID×副本归属计算，跨副本可能重叠。它是查询实际带来的额外候选，不是全站漏检率或新增合格来源数。', '',
        '## 首批六条：仅为AI初判', '',
        '每个副本只取已冻结随机顺序第1、2条，读取详情并查看页面和实机片段。以下决定均未写成人工定稿；`small_video_review.csv`仍为pending。纳入建议中未解决的期次核对必须如实保留。', '',
        '| 副本/顺序 | 来源 | 建议 | 内容证据与待核点 |',
        '| --- | --- | --- | --- |']
    for r in proposal['records']:
        decision = '纳入待核' if r['proposed_decision'] == 'include' else '排除待核'
        lines.append(f'| {NAMES[r["mode"]]}/{r["position"]} | [{r["title"]}]({r["url"]}) | {decision} | {r["content_evidence"]} {r["unresolved"]} |')
    lines += ['', '## 当前边界与下一步', '',
        '主查询及审计完成只证明执行了预先固定的发现规则，不证明全站覆盖。随机队列已生成；尚无人工定稿来源，正式锁定视频0条、正式抽取评论0条。', '',
        '17号方案第4节规定“AI内容初判不能冒充人工定稿”。用户需要核对本批来源资格，尤其是三条拟纳入视频的实机期次；本次继续工作流的指令不被写成已完成逐条内容审核。核定后将保留用户意见和AI初判，沿原随机顺序继续，不因误命中换种子或跳过待核来源。', '',
        '原始记录位于`采集工具/正式采集_小样本v1_20261018/`：`small_discovery_main.json`、`small_discovery_audit_a.json`、`small_discovery_audit_b.json`、`small_candidate_frame.json`、`small_video_draw.json`、`small_video_queue.csv`、`small_video_review_batch_001_proposal.json`及各自哈希。元数据与评论缓存不包含会话文件内容。', '']
    (s.path.parent.parent / '19_候选库冻结与首批资格核验_20261018.md').write_text('\n'.join(lines), encoding='utf-8')
    print({'candidate_videos':1573, 'candidate_domain_rows':1634, 'review_proposals':len(records), 'human_final':0})


if __name__ == '__main__':
    main()
