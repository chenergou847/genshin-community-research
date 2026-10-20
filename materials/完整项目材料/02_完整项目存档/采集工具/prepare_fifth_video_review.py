"""Package observed evidence for batch 005; never finalize human decisions."""
from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path

from observer import small
from observer.core import Study, NAMES, digest, now, read_csv, read_json, write_json


# These are observations of the saved first frames and three rendered-page
# spot checks. They are not automated inferences from a title or a full watch.
OBS = {
    'BV1fkJB6dERS': ('include', '实录',
        '标题明确10月、骇星之月；首帧实际活动页显示本期渊月祝福“骇星之月”。',
        '画面当期进度在较低层；不因未展示12层而排除。未完整观看。'),
    'BV1nbak6KEBa': ('include', '实录',
        '标题明确7.1剧诗月谕；首帧是剧诗待命角色配置，水冰风角色及托马线索与本期相符，简介描述本次角色不足、第四关失败。',
        '首帧未展示整张本期规则卡；本期归属以标题、配置及简介合并初判，待用户核定。'),
    'BV1TFe56uEhs': ('exclude', '旧期实录',
        '标题明确“2026年8月”；首帧显示幽境危战·星芒之役及旧敌人组合，不是本期炼煌之役。',
        '9月发布仍在视频发布日期范围内，但内容期次不合格。'),
    'BV1ReJ86FECd': ('include', '实录',
        '标题明确2026-10-16深渊；首帧12层地脉说明上半星烁反应伤害+75%、下半冰伤+75%，符合本期。',
        '首帧核查；未完整观看或验证通关表现。'),
    'BV1WstM6KE9k': ('exclude', '旧期攻略',
        '标题明确2026年9月、水雷草剧诗，简介也列旧期反应；首帧为另一旧教程页面，不是10月水冰风。',
        '不必判定画中旧教程究竟8月还是9月；已足以排除当前10月归属。'),
    'BV1wBJB68EJV': ('include', '讨论/成绩比较',
        '标题“龙黑7.1危战成绩单”；首帧实际内容是N6成绩、时间与评价的比较表，明确围绕7.1危战表现展开讨论。',
        '期次主要依赖标题及发布时间，待用户核定。表内点名、成绩和评价均为作者说法，不作为独立核验数据；报告不复刻其晒名表。'),
    'BV1iSJS6DEtJ': ('include', '攻略/实录',
        '首帧只有装饰片头，已另查正文开头：第12层第1间上半、97级“历经百战的秘谷睿鉴密士”战斗及走位教学字幕；标题明确7.1，10月16日发布。',
        '已保存正文截图；只做片段抽查，不声称完整观看或验证低配满星。'),
    'BV13paD6GENC': ('include', '实录',
        '标题和简介明确“剧诗记录：2026-10月”；首帧是图书馆剧诗入口及月谕圣牌收藏交互。',
        '首帧是入口，未展示全部本期规则与关卡；待用户结合材料核定，未完整观看。'),
    'BV1A5aB6FEuN': ('include', '实录',
        '首帧只是加载画面，已另查正文开头：幽境挑战中110级“游雪的护刃”与玛薇卡队战斗；标题明确7.1幽境。',
        '已保存正文截图；不把“全网首发”、金数、重试时间及DPS等作者自述作为已核验事实。'),
    'BV1CFJh6GEt6': ('include', '讨论/使用率比较',
        '标题明确7.1下半深渊；首帧正文直接显示“7.1下半深渊使用率”及比较图，属于本期讨论。',
        '仅核视频讨论对象；图中使用率不作为本研究的玩家比例或可信总体统计。'),
    'BV1CZa66qEwP': ('include', '实录',
        '标题明确2026.10.01剧诗月谕满星；首帧实际为繁体剧诗演出准备/回顾/奖励页面。',
        '未完整观看，也未独立核验“满星”；期次结合明确日期与目标玩法界面初判，待用户核定。'),
    'BV1k6pK6UE9i': ('include', '实录',
        '10月7日发布；标题与画面字幕均为“严格2金魈N5冰棺”，首帧实际为幽境场地开战倒计时，本期目标敌人线索明确。',
        '未核完整击杀、难度及金数；不因其不是N6而排除。'),
    'BV1AQJU6hE93': ('include', '实录/剪辑',
        '标题明确7.1深境螺旋、上半星烁与下半冰队；10月16日发布；首帧实际在深渊战斗场景。',
        '首帧未展示规则卡或敌人，期次结合明确标题及当期发布初判，待用户核定；未完整观看。'),
    'BV1Kiar6kE4i': ('include', '实录',
        '标题明确10月幻想真境剧诗水冰风；首帧实际为剧诗入口及月谕圣牌收藏，10月2日发布。',
        '首帧未展示全部本期关卡，待用户结合明确月份与元素组合核定。'),
    'BV1BTJb6fEak': ('include', '实录',
        '标题未写副本/期次，故另查正文开头：幽境挑战倒计时、110级秘源机兵·统御械与其护罩/冻结提示，八重神子等角色实际战斗；对应本期“冰锅”。',
        '已保存正文截图；不以幽境标签或发布时间单独认定，也不以难度7标签认定实际难度。只抽查开头。'),
    'BV1pYJ46PEaX': ('include', '实录',
        '标题明确7.1深渊，10月16日发布；首帧实际为第12层第1间祝福选择页面。',
        '首帧未展示地脉或敌人；期次依明确标题、发布时间及实际玩法界面初判，待用户核定。'),
    'BV168Hd61E3u': ('include', '实录',
        '标题明确7.1幻想真境剧诗水冰风；首帧实际为剧诗战斗场景，10月6日发布。',
        '未完整观看；首帧未展示整张本期规则卡，待用户结合标题核定。'),
    'BV1EBaZ6VE29': ('include', '讨论/通关案例汇总',
        '9月30日发布；标题与首帧正文均明确幽境N6三路，列冰锅、冰棺、丘林三个本期敌人通关案例。',
        '属于本期具体讨论；图中二手案例、金数和耗时均未独立核验。'),
    'BV1oqew6sEJW': ('exclude', '旧期实录',
        '标题明确“7.0B深渊”，9月16日发布；首帧为深渊12层祝福选择，但不是10月16日本期。',
        '按内容明确旧期排除；不因同角色或相同玩法界面混入当前期次。'),
    'BV1UtYP6LEX5': ('include', '攻略',
        '标题明确10月更新、水冰风、关卡分析与卓越模式；10月1日发布；首帧实际为剧诗图书馆入口。',
        '简介带推广内容，不影响其是否实质讨论本期的判断；未完整观看，也未验证攻略效果。'),
}


def main():
    s = Study('正式采集_小样本v1_20261018')
    small.check(s)
    if (s.path / 'small_video_review_batch_005_confirmation.json').exists():
        s.frozen('small_video_review_batch_005_confirmation.json')
        print({'status': 'already_human_confirmed'})
        return
    frame = s.frozen('small_candidate_frame.json')
    draw = s.frozen('small_video_draw.json')
    images = s.frozen('small_video_review_batch_005_first_frames.json')
    assert images['candidate_frame_hash'] == digest(frame)
    assert images['video_draw_hash'] == digest(draw)
    rows = {(r['mode'], r['bvid']): r for r in read_csv(s.path / 'small_video_review.csv')}
    assert len(images['records']) == len(OBS) == 20
    records = []
    for evidence in images['records']:
        mode, bv, position = evidence['mode'], evidence['bvid'], evidence['position']
        assert draw['orders'][mode][position - 1] == bv
        row = rows[mode, bv]
        assert row['decision'] == 'pending' and row['final'] == 'no'
        path = Path(evidence['path'])
        assert evidence['status'] == 'saved' and sha256(path.read_bytes()).hexdigest() == evidence['sha256']
        decision, kind, observation, limits = OBS[bv]
        r = dict(mode=mode, position=position, bvid=bv, title=row['title'],
                 published_at=row['published_at'], aid=row['aid'], primary_up=row['primary_up'],
                 url=f'https://www.bilibili.com/video/{bv}/',
                 proposed_decision=decision, content_type=kind, reason=observation,
                 content_evidence=observation, unresolved=limits,
                 reviewer='AI', final='no', review_kind='ai_proposal',
                 first_frame_path=str(path), first_frame_sha256=evidence['sha256'],
                 metadata_response_hash=evidence['metadata_response_hash'])
        spot = path.with_name(bv + '_spotcheck.png')
        if spot.exists():
            r['spotcheck_path'] = str(spot)
            r['spotcheck_sha256'] = sha256(spot.read_bytes()).hexdigest()
            r['spotcheck_method'] = 'CUA_rendered_public_video_opening_only'
        records.append(r)
    name = 'small_video_review_batch_005_proposal.json'
    payload = dict(candidate_frame_hash=digest(frame), video_draw_hash=digest(draw),
                   first_frames_manifest_hash=digest(images), records=records,
                   note='AI初判待用户核定；保留开头抽查局限，不等于已完整观看或正式样本锁定。')
    if (s.path / name).exists():
        proposal = s.frozen(name)
        for key, value in payload.items():
            assert proposal[key] == value, 'Already sealed proposal differs: ' + key
    else:
        proposal = small.seal(s, name, payload)

    progress = small.video_progress(s)
    final = [r for r in rows.values() if r['final'] == 'yes']
    state = read_json(s.path / '执行状态.json')
    state.update(small.status(s))
    state.update(at=now(), status='ACTIVE', stage='VIDEO_ELIGIBILITY_BATCH_005_AWAITING_HUMAN_REVIEW',
                 human_final_video_domain_rows=len(final),
                 human_included_video_domain_rows=sum(r['decision'] == 'include' for r in final),
                 human_excluded_video_domain_rows=sum(r['decision'] == 'exclude' for r in final),
                 eligibility_progress={m: dict(selected=len(v['selected']), reviewed_prefix=len(v['prefix']), status=v['status']) for m, v in progress.items()},
                 batch_005=dict(metadata_domain_rows_ready=20, first_frames_saved=20,
                                first_frames_target=20, first_frames_manifest_sealed=True,
                                proposal_ready=True, proposal_hash=digest(proposal), human_final_rows=0),
                 formal_eligible_videos_locked=0, formal_random_raw_comments_drawn=0)
    write_json(s.path / '执行状态.json', state)
    project = s.path.parent.parent
    counts = Counter(r['proposed_decision'] for r in proposal['records'])
    lines = ['# 第五批随机来源资格核验', '',
        '更新时间：2026-10-18，北京时间。用户已说“继续”，从暂停检查点恢复。冻结候选库、随机顺序和T0均未改变。', '',
        '可复用任务描述：沿三个副本已冻结的随机前缀，核定视频是否实质讨论本期；保留初判、原始证据、检查局限和用户决定，直至每副本20条合格来源。', '',
        f'本批20条：{counts["include"]}条拟纳入，{counts["exclude"]}条拟排除。目前均为AI初判，尚未写入正式人工决定。', '',
        '## 已有进度', '',
        '前四批46条已由用户核定：33条纳入、13条排除；深渊12/20、剧诗10/20、幽境11/20。本批取深渊17—23、剧诗17—23、幽境15—20号，全部保留原始随机顺序。', '',
        '20条首帧均已保存并核验哈希。首帧只有片头或加载画面的深渊19、幽境17另查正文；标题未写副本的幽境19也另查正文。其余仅做元数据与首帧核对，不能写成完整观看。', '',
        '## 逐条初判', '',
        '| 副本/随机顺序 | 来源与发布时间（北京时间） | 初判 | 实际证据 | 检查局限 |',
        '| --- | --- | --- | --- | --- |']
    bj = timezone(timedelta(hours=8))
    def esc(t):
        return str(t).replace('|', '\\|').replace('\n', ' ')
    for r in proposal['records']:
        pub = datetime.fromtimestamp(int(r['published_at']), bj).strftime('%Y-%m-%d %H:%M')
        image_link = f'[首帧](<{Path(r["first_frame_path"]).as_posix()}>)'
        if r.get('spotcheck_path'):
            image_link += f'、[正文截图](<{Path(r["spotcheck_path"]).as_posix()}>)'
        decision = '拟纳入' if r['proposed_decision'] == 'include' else '拟排除'
        lines.append(f'| {NAMES[r["mode"]]}/{r["position"]} | [{esc(r["title"])}]({r["url"]})<br>{pub} | {decision} | {esc(r["content_evidence"])} {image_link} | {esc(r["unresolved"])} |')
    lines += ['', '## 核定边界', '',
        '拟排除的是幽境15（标题8月且显示星芒之役）、剧诗18（9月水雷草旧攻略）、深渊23（7.0B旧期）。拟纳入既含实录和攻略，也含本期使用率/成绩讨论；不会因观点、通关表现、播放量、评论数或难度不同改变资格规则。', '',
        '幽境16为争议性成绩比较，标题明确7.1，但不能把作者对他人的评价或表内成绩当成已核验数据。深渊20、幽境20同理，只证明其讨论对象与本期相关，不采信其图表为本研究总体比例。', '',
        '用户核定后再写入人工审核表。本批如果按表核定，累计为66条已核、50条纳入、16条排除：深渊18/20、剧诗16/20、幽境16/20；这只是条件性进度，当前真实进度仍为前四批。正式视频样本尚未锁定，正式评论抽样仍为0。', '',
        '本批提案与首帧清单已分别封存为`small_video_review_batch_005_proposal.json`和`small_video_review_batch_005_first_frames.json`及哈希；三张正文截图也在提案内记录文件哈希。所有结果只对应固定规则建立的视频域，不声称全站覆盖或代表性已经通过。', '']
    (project / '24_第五批随机来源资格核验_20261018.md').write_text('\n'.join(lines), encoding='utf-8')
    definition = project / '00_任务定义.md'
    body = definition.read_text('utf-8')
    old = '当前状态：用户已要求暂停，已停止取证并保存检查点。46条候选经用户核定、33条合格；第五批20条详情已读，首帧保存8/20，正式评论仍为0。下次续接见`23_暂停与续接_20261018.md`，不要重新抽样。'
    new = '当前状态：用户已要求继续，已从检查点恢复。前四批46条经用户核定、33条合格；第五批20条首帧和3处正文抽查已完成，提案见`24_第五批随机来源资格核验_20261018.md`，待用户核定。候选库与随机顺序未改变，正式评论抽样仍为0。'
    if old in body:
        definition.write_text(body.replace(old, new, 1), encoding='utf-8')
    log = project / '04_参与与决策记录.md'
    marker = '## 2026-10-18 从暂停检查点续接并完成第五批初判'
    log_body = log.read_text('utf-8')
    if marker not in log_body:
        log.write_text(log_body + '\n\n' + marker + '\n\n'
            '用户直接指令“继续”撤销本次暂停。AI核对检查点与已保存证据，补齐第五批剩余12张首帧，全部20张核验后封存；另检查3处正文开头并保存截图。第五批17条拟纳入、3条拟排除，尚未记为人工确认。视频库、随机次序、T0和评论窗保持冻结；尚未锁定最终视频样本或抽取正式评论。\n', encoding='utf-8')
    print(dict(status='proposal_ready_awaiting_human', proposed=dict(counts), human_final=len(final), proposal_hash=digest(proposal)))


if __name__ == '__main__':
    main()
