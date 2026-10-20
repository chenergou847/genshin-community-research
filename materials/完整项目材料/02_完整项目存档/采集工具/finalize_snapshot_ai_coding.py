"""Validate and publish the 600 AI proposals, without human acceptance or estimates."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from observer.core import digest, read_csv, read_json, write_csv, write_json, NAMES, now
from observer import small
from observer.snapshot_sample import master_hashes
from continue_snapshot_coding import S, TOPICS, VERSION, setup, ancestors, public_text


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def finish():
    frame,draw,lookup,videos,queue=setup()
    result_name='small_snapshot_coding_full_result_001.json'
    if (S.path/result_name).exists():
        print(json.dumps(S.frozen(result_name)['summary'],ensure_ascii=False));return
    before=S.frozen('small_snapshot_coding_before_continuation_001.json')
    pilot=S.frozen('small_snapshot_coding_pilot_proposals_001.json')
    batches=sorted(S.path.glob('small_snapshot_coding_continuation_batch_*.json'))
    assert len(batches)==12
    continuation=[r for p in batches for r in S.frozen(p.name)['rows']]
    assert len(continuation)==569
    assert {r['queue_index'] for r in continuation}==set(range(1,570))
    assert {(r['mode'],r['id']) for r in continuation}=={(r['mode'],r['id']) for r in queue['items']}
    proposals={}
    for r in pilot['rows']+continuation:
        assert (r['mode'],r['id']) not in proposals
        row=dict(r);row['origin']='pilot' if 'queue_index' not in row else 'continuation'
        row['bvid']=lookup[r['id']]['bvid'];row['codebook_version']=VERSION
        proposals[r['mode'],r['id']]=row
    coding=read_csv(S.path/'small_snapshot_supplement_coding.csv')
    materials=read_csv(S.path/'small_snapshot_supplement_main_material.csv')
    material={(r['mode'],r['id']):r for r in materials}
    expected={(m,i) for m,vs in draw['samples'].items() for b,v in vs.items() for i in v['ids']}
    assert len(coding)==len(proposals)==len(expected)==600
    assert {(r['mode'],r['id']) for r in coding}==set(proposals)==set(material)==expected
    assert Counter(r['mode'] for r in coding)=={'abyss':200,'theater':200,'stygian':200}
    assert all(r['relevance'] in ('related','irrelevant','unknown') for r in coding)
    assert all(r['review_kind']=='ai_proposal' and r['final']=='no' for r in coding)
    prior={(r['mode'],r['id']):r for r in before['rows'] if r['relevance']!='pending'}
    assert len(prior)==31
    for row in coding:
        key=row['mode'],row['id'];p=proposals[key];raw=lookup[row['id']]
        if key in prior: assert row==prior[key],('prior_proposal_changed',key)
        for k in small.CFIELDS:
            if k in p and k!='notes':
                display="'"+str(p[k]) if str(p[k]).startswith(('=','+','-','@')) else p[k]
                assert row[k]==display,(key,k)
        assert p['evidence'] and p['evidence'] in raw['text']
        topics=set(filter(None,p['themes'].split(';')))
        selftopics=set(filter(None,p['self_experience_themes'].split(';')))
        problems=set(filter(None,p['problem_themes'].split(';')))
        assert topics<=set(TOPICS.values()) and selftopics<=topics and problems<=selftopics
        assert p['relevance']=='related' or not topics
        assert p['problem_status']=='current_reported' if problems else p['problem_status']!='current_reported'
        info=draw['samples'][p['mode']][p['bvid']]
        assert abs(float(material[key]['relative_weight'])-info['N']/info['m'])<1e-10
        assert float(material[key]['N'])==info['N'] and float(material[key]['m'])==info['m']
        # Spreadsheet formula protection may prefix only the display CSV. Raw JSON is canonical.
        assert material[key]['text'] in (raw['text'],"'"+raw['text'])
    assert master_hashes(S)==before['master_hashes']
    original=S.frozen('small_snapshot_draw_001.json')
    assert all(set(v['ids'])<=set(draw['samples'][m][b]['ids']) for m,vs in original['samples'].items() for b,v in vs.items())
    ordered=[proposals[r['mode'],r['id']] for r in coding]
    full=small.seal(S,'small_snapshot_coding_full_proposals_001.json',dict(rows=ordered,draw_hash=digest(draw),frame_hash=digest(frame),
        codebook_boundary_approval_hash=digest(S.frozen('small_snapshot_codebook_boundary_approval_001.json')),
        pilot_hash=digest(pilot),batch_hashes={p.name:digest(S.frozen(p.name)) for p in batches},
        operational_codebook_version=VERSION,human_final_count=0,independent_coding_validation_done=False))
    review=[];blind=[];rich=[];context_items=[]
    for p in ordered:
        key=p['mode'],p['id'];raw=lookup[p['id']];meta=material[key];anc=ancestors(raw,lookup)
        reasons=[]
        if p['relevance']=='unknown':reasons.append('相关性不明')
        fs=set(filter(None,p['content_flags'].split(';')))
        if any(x in fs for x in ('mode_not_explicit','possible_cross_mode','retrospective_experience','hypothetical_other_period','habitual_not_period_verified')):reasons.append('副本或期次边界')
        if 'suspected_commercial_content' in fs:reasons.append('疑似推广')
        if 'missing_ancestor' in fs:reasons.append('缺失祖先')
        if p['problem_status']=='current_reported':reasons.append('本人受阻证据')
        if 'observed_design_critique' in fs:reasons.append('一般批评与本人经历区分')
        if 'configuration_equivalence_unverified' in fs:reasons.append('配置与操作前提未核')
        if raw['media'] or any(a['media'] for a in anc):reasons.append('图片未读')
        priority='1_不明与边界' if any(x in reasons for x in ('相关性不明','副本或期次边界','疑似推广','缺失祖先')) else ('2_受阻与归因' if any(x in reasons for x in ('本人受阻证据','一般批评与本人经历区分','配置与操作前提未核')) else ('3_媒体限制' if '图片未读' in reasons else '4_其余'))
        parent_text='\n'.join(f"[{a['id']}; same_author={a['same_author_as_item']}; image_unread={a['media']}] "+(public_text(a['text']) if a['available'] else '[正文缺失]') for a in anc)
        common=dict(mode=p['mode'],副本=NAMES[p['mode']],id=p['id'],bvid=p['bvid'],title=meta['title'],url=meta['url'],
            text=public_text(raw['text']),ctime_bjt=raw['ctime_bjt'],level=raw['level'],author_role=raw['author_role'],
            parent_context=parent_text,own_image_unread=raw['media'],ancestor_image_unread=any(a['media'] for a in anc),
            N=meta['N'],m=meta['m'],relative_weight=meta['relative_weight'],sample_phase=meta['sample_phase'])
        ai=dict(ai_relevance=p['relevance'],ai_themes=p['themes'],ai_self_themes=p['self_experience_themes'],ai_experience_kind=p['experience_kind'],
            ai_problem_status=p['problem_status'],ai_problem_themes=p['problem_themes'],ai_evidence=p['evidence'],ai_reason=p['reason'],
            ai_sentiment=p['sentiment'],ai_flags=p['content_flags'],ai_context_status=p['context_status'],review_priority=priority,review_focus=';'.join(reasons))
        human=dict(human_relevance='',human_themes='',human_self_themes='',human_experience_kind='',human_problem_status='',human_problem_themes='',human_evidence='',human_sentiment='',human_notes='',reviewer='',final='no')
        review.append(dict(**common,**ai,**human))
        blind.append(dict(**common,**human))
        rich.append(dict(**p,N=meta['N'],m=meta['m'],relative_weight=meta['relative_weight']))
        context_items.append(dict(mode=p['mode'],id=p['id'],bvid=p['bvid'],text=raw['text'],media_unread=raw['media'],ancestors=anc))
    write_csv(S.path/'small_snapshot_coding_full_review_001.csv',review,list(review[0]))
    write_csv(S.path/'small_snapshot_coding_full_blind_material_001.csv',blind,list(blind[0]))
    focus=sorted((r for r in review if r['review_focus']),key=lambda r:(r['review_priority'],r['mode'],r['id']))
    write_csv(S.path/'small_snapshot_coding_priority_review_001.csv',focus,list(review[0]))
    unknown=[r for r in review if r['ai_relevance']=='unknown']
    write_csv(S.path/'small_snapshot_coding_unknown_review_001.csv',unknown,list(review[0]))
    problems=[r for r in review if r['ai_problem_status']=='current_reported']
    write_csv(S.path/'small_snapshot_coding_problem_review_001.csv',problems,list(review[0]))
    write_csv(S.path/'small_snapshot_coding_full_flat_001.csv',rich,list(dict.fromkeys(k for r in rich for k in r)))
    write_json(S.path/'small_snapshot_coding_full_context_001.json',dict(frame_hash=digest(frame),items=context_items))
    summary=dict(total=600,remaining_without_AI_proposal=0,AI_proposals=600,human_final=0,
        relevance_counts=dict(Counter(r['relevance'] for r in ordered)),
        per_mode={m:dict(Counter(r['relevance'] for r in ordered if r['mode']==m)) for m in NAMES},
        self_experience_utterances=sum(bool(r['self_experience_themes']) for r in ordered),
        current_reported_problem_utterances=len(problems),unknown_relevance=len(unknown),
        priority_review_rows=len(focus),priority_counts=dict(Counter(r['review_priority'] for r in review)),
        media_limited_rows=sum(r['own_image_unread'] or r['ancestor_image_unread'] for r in review),
        sampled_missing_ancestor=sum('missing_ancestor' in r['ai_flags'].split(';') for r in review),
        unit='sampled_utterance_ID_not_unique_people',population_proportions_computed=False,
        reliability_or_accuracy_measured=False,human_final_coding_complete=False,
        conditions_action_outcome_fields_fully_extracted=False)
    checks=dict(exact_600_IDs_and_200_per_mode=True,prior_31_proposals_unchanged=True,all_569_queue_IDs_once=True,
        original_232_retained=True,original_weights_and_draw_unchanged=True,raw_master_hashes_unchanged=True,
        every_evidence_is_own_body_substring=True,theme_sets_and_self_problem_subsets_valid=True,
        no_pending_AI_labels=True,all_600_final_no=True,independent_semantic_validation_done=False)
    outputs=['small_snapshot_coding_full_review_001.csv','small_snapshot_coding_full_blind_material_001.csv','small_snapshot_coding_priority_review_001.csv',
        'small_snapshot_coding_unknown_review_001.csv','small_snapshot_coding_problem_review_001.csv','small_snapshot_coding_full_flat_001.csv','small_snapshot_coding_full_context_001.json']
    result=small.seal(S,result_name,dict(summary=summary,checks=checks,full_proposal_hash=digest(full),draw_hash=digest(draw),
        master_file_sha256=master_hashes(S),output_file_sha256={n:sha(S.path/n) for n in outputs},
        interpretation='AI initial counts only; no weighted estimates, no human agreement, no saturation claim'))
    state=read_json(S.path/'执行状态.json')
    state.update(stage='ALL_600_AI_PROPOSALS_READY_HUMAN_REVIEW_PENDING',coding_AI_initial_completed=True,coding_completed=False,
        feedback_proportions_computed=False,current_research_record='43_全600条AI初判完成与审核交付_20261019.md',
        coding_continuation=dict(updated_at=now(),result_file=result_name,summary=summary),
        current_full_review_file='small_snapshot_coding_full_review_001.csv')
    write_json(S.path/'执行状态.json',state)
    table='\n'.join(f"| {NAMES[m]} | {summary['per_mode'][m].get('related',0)} | {summary['per_mode'][m].get('irrelevant',0)} | {summary['per_mode'][m].get('unknown',0)} | 200 |" for m in NAMES)
    report=f'''# 全600条AI初判完成与审核交付

更新：2026-10-19，北京时间。已按用户“认可，按此口径继续”的确认完成剩余569条，加上原31条，共600条AI初判。**待初判0条，人工逐条定稿0条。没有计算总体反馈比例。**

可复用任务描述：对既定600条发言逐条核对正文及必要语境；本期配队、机制提示和角色表现比较记玩法相关讨论，本人实际经历与明确受阻分开记录；不明保留，不换来源、不补抽，不把他人经历、图片或未来预期补成本人实战。交付带原文、证据与理由的AI审核表，留待人工裁决。

## 结果与可用入口

| 副本 | AI相关 | AI不相关 | AI不明 | 合计 |
| --- | ---: | ---: | ---: | ---: |
{table}
| 合计 | {summary['relevance_counts']['related']} | {summary['relevance_counts']['irrelevant']} | {summary['relevance_counts']['unknown']} | 600 |

这些是600条抽中发言的**未加权初判数量**，不是6526条中的占比，不是独立玩家数，也不是“有多少人遭遇产品缺陷”。同一发言可有多个主题；角色强弱、建议与本人受阻不能混算。AI将{summary['self_experience_utterances']}条标为包含本人经历或账号条件、{len(problems)}条标为包含本期明确受阻/不满；仍是待审核的评论主张，问题主题不是已证实原因。

- [完整600条人工审核表](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_full_review_001.csv)：正文、祖先、权重、AI相关性/主题/本人经历/问题/情绪/证据/理由和空白人工裁决列。
- [40条不明项](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_unknown_review_001.csv)：保留原ID与权重，不删除、不补抽。
- [本人受阻候选表](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_problem_review_001.csv)：{len(problems)}条，包含已解决卡点，不能等同尚未解决问题。
- [重点复核表](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_priority_review_001.csv)：{len(focus)}条，涵盖不明、期次/副本边界、缺父、疑似推广、归因与图片限制。
- [隐藏AI标签的原材料](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_full_blind_material_001.csv)：可供独立编码者使用；尚无人完成独立编码，不能声称盲核已通过。
- [结构化600条提案](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_full_proposals_001.json)、[结构校验结果](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_full_result_001.json)。

## 本轮实际如何工作

`continue_snapshot_coding.py`只读取本地已保存资料，不联网、不读取Cookie。先封存用户口径确认、编码前备份与569条续编码队列；排序只是方便阅读，不产生新样本。AI分12批读取每条完整正文和可用祖先；对少量指向含混的回复补查同线程文字，再逐条写入显式判断、原文摘录与理由。没有用关键词分类器给整批生成标签。纯技术检索只用于寻找上下文，不决定分类。

`coding_annotations_001.txt`至`012.txt`保存逐条语义判断，`record`核验后封存各批提案，再更新活动CSV。`finalize_snapshot_ai_coding.py`合并原31条及续编569条，检查ID、证据、标签集合和文件哈希，生成交付表；它不将提案自动定稿，也不计算比例。

原31条试编码逐项标签保持不变；本轮统一口径登记为`{VERSION}`。用户确认的是操作口径及继续AI初判，**不是600条逐项人工认定**。原42号提案与本轮各批快照均保留。

## 编码中的关键限制

1. 没有读取评论配图。{summary['media_limited_rows']}条本条或祖先含未读图片；其中正文足够的可识别主题，但不录入图中面板、阵容、难度或成绩。40条不明主要涉及纯表情、俚语、图片或卡片交换的目标不清。
2. 副本比较视频下可能谈另一个玩法，或只泛谈角色。明确跨副本的判无关；当前配队/角色比较但具体副本未明的另标`mode_not_explicit`，优先人工核对；不能直接视作幽境本人实战。旧期、每月概括与未来预期分开标记。
3. 抽中1条缺祖先回复保留，正文自身足够判为泛跨游戏聊天；仍记录缺失语境。不能据此说缺失父评论已找回或证实被平台删除。
4. 重复正文的不同ID仍保留；同一作者的多条发言不当作多人。祖先只解释语义，不整段继承其观点。一般设计批评没有明确本人经历时单标，不硬算第一手受阻。
5. 受阻之后通过的案例保留`resolved_obstacle`；抱怨“和攻略一样”仍需核对配置、能量、操作及选取前提。没有认定索敌、增益或机关存在BUG。
6. 本轮尚未逐项提取所有条件、动作、结果和难度到独立结构字段，正文和理由已留存。不能把600条AI分类完成说成问题分析报告完成。

## 可以推进的问题线索：待核，不是最终结论

| 副本 | 评论证据 | 下一步核查 |
| --- | --- | --- |
| 深渊 | [320856874272](https://www.bilibili.com/video/BV1AQJU6hE93/)：“打了一早上”“不清楚他的机制” | 核对机制信息、实际配置和失败过程，区分理解成本与强度门槛。 |
| 剧诗 | [315713410369](https://www.bilibili.com/video/BV1fuYP6tEva/)：“最后一关发现没冰了”“又重开” | 区分角色池、出战规划与抽取结果，核查回溯是否可用。 |
| 剧诗 | [315751105345](https://www.bilibili.com/video/BV1fuYP6tEva/)：“凹了两个小时放弃满星” | 分别记录奖励已达成、满花未达成及停止挑战成本。 |
| 幽境 | [315502915409](https://www.bilibili.com/video/BV137aA63EF6/)：“雷挂不上去”“不索敌” | 先核对敌方状态和协同攻击触发前提，不直接诊断技术故障。 |
| 幽境 | [319258388128](https://www.bilibili.com/video/BV1LhYc62EWa/)：风场、后跳、充能和多轮轴不一致 | 先比对攻略的完整配置和操作条件；评论者声称相同不等于已经核实相同。 |

还须保留低配通过、第一次满星、用回溯解决等正向和反例。以上线索集中在特定来源，不能根据出现次数排成全体玩家问题优先级。

## 样本与技术核对

- 600个原ID不变，每副本200；241根＋359回复。旧232条全部保留，新增368条的来源、窗口、种子和最终`N/m`权重不变。
- 续编569条与队列一一对应，无重复、无遗漏；原31条标签未改。证据摘录均来自该条正文，问题主题均属于本人的主题子集。
- 原9593条主档、6526条窗口框、抽样文件哈希未改变。全部600条仍`review_kind=ai_proposal`、`final=no`。
- 上述是文件与结构正确性检查，**不验证语义准确率、编码者一致性、检索充分性或主题饱和度**。

## 当前阶段与下一步

采集与600条技术抽样已有结果，本轮600条AI初判完成。接下来先做人工编码核验和争议裁决，再锁定最终标签，提取发生条件、影响、应对方式与反例。此后才能针对固定60来源、已保存6526条窗口正文，用最终权重估计反馈比例，报告不明比例、敏感性和区间；95%及±10个百分点仍是设计目标，尚未证明实际达到。

若进行独立复核，应先使用隐藏AI标签的材料，再对照提案裁决；不能把当前模型的自查当作独立复核。核定40条不明、混合副本和图片依赖项很重要，但只复核这些重点项不能估计全600条的分类错误率。最终结论不推广到未保存评论、未核验候选或全B站玩家。
'''
    (S.path.parent.parent/'43_全600条AI初判完成与审核交付_20261019.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(summary=summary,checks=checks),ensure_ascii=False))


if __name__=='__main__': finish()
