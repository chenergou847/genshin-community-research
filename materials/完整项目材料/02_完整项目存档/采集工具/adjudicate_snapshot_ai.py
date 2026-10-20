"""Versioned second AI review. Human-final labels and old proposals stay untouched."""
import json
from collections import Counter
from copy import deepcopy
from observer.core import digest, write_csv, write_json
from observer import small
from observer.snapshot_sample import master_hashes
from review_snapshot_labels import data, S

VERSION='snapshot-codebook-v0.3-AI-REVIEWED-EXPLORATORY'

def review():
    f,d,L,v,old=data()
    if (S.path/'small_snapshot_ai_review_001.json').exists():
        return S.frozen('small_snapshot_ai_review_001.json')
    before=master_hashes(S)
    rows=deepcopy(old);by={i:r for i,r in enumerate(rows,1)};changes={}
    def amend(k,reason,**fields):
        r=by[k];r.update(fields);changes[k]=reason
    def uncertain(k,reason,flag):
        r=by[k];r['candidate_themes_before_relevance_review']=r['themes']
        amend(k,reason,relevance='unknown',themes='',self_experience_themes='',problem_themes='',problem_status='unknown',theme_status='unknown',experience_kind='ambiguous',sentiment='unknown')
        r['content_flags']=';'.join(dict.fromkeys(filter(None,(r['content_flags']+';'+flag).split(';'))))
    # The 11 already flagged mixed-domain items plus 4 analogous replies.
    mixed=[546,549,550,551,552,554,562,564,566,569,574,575,577,584,423]
    for k in mixed:
        uncertain(k,'比较视频同时涉及多个副本；正文和可用祖先未能确定是所分配的本期幽境，不能以角色通用强度代替本域相关性。','domain_ambiguous_after_context_review')
    for k in (397,525,599):
        uncertain(k,'根评论只有泛夸赞，未明确对象是UP、角色还是玩法；与同类“太强了”统一保留不明。','praise_target_unresolved')
    uncertain(251,'“之前”不能直接等同上期；当前文字也未证实本期，撤销根据角色名称推定旧期的初判，保留期次不明。','period_ambiguous_after_review')
    amend(155,'“减速带”已足以确定在谈难度；反语方向和图片结果仍不明，因此相关而情绪不明，不能补出本人已通关。',
        relevance='related',themes='damage_threshold',self_experience_themes='',experience_kind='evaluation_or_comparison',theme_status='known',sentiment='unknown',problem_status='none_explicit',problem_themes='')
    amend(287,'本条只喊技能台词，没有评价、配置、建议或本人经历；不把父评论组队讨论整体继承为当前观点。',
        relevance='irrelevant',themes='',self_experience_themes='',experience_kind='social_or_meta',problem_status='none_explicit',problem_themes='')
    amend(76,'当前文字可能是逆环境晒成绩的反语；没有读取图片，不能确认不满或本人受阻。保留增益话题，受阻状态记不明。',
        self_experience_themes='',experience_kind='evaluation_or_comparison',problem_status='unknown',problem_themes='',sentiment='unknown')
    by[76]['content_flags']+=';ironic_tone_unresolved'
    for k,reason in {
        140:'只说明常驻满命不易及当前持有情况，未明确这种条件已经造成本期通关受阻；保留本人账号条件，取消问题标签。',
        333:'本条只补充自己的装备词条；不把其他回复中的卡关继承为本条新受阻。',
        457:'本人说明需要拆分反应队，未明确实际失败或不满；保留分配条件，取消明确受阻。'
    }.items():amend(k,reason,problem_status='none_explicit',problem_themes='')
    amend(293,'明确的是早关烦躁和代打互动不适，没有具体操作失误或重试时长。移除推定的操作/耗时问题，保留未明原因的负面体验与互助不适。',
        themes='roster_build;co_op_social;other_current_experience',self_experience_themes='co_op_social;other_current_experience',problem_themes='co_op_social;other_current_experience')
    amend(466,'“极限”能表达难度压力，但没有时间或重试信息；移除由语气推断的流程耗时标签。',
        themes='damage_threshold',self_experience_themes='damage_threshold',problem_themes='damage_threshold')
    amend(487,'“打哭了”未指明高兴还是受挫，图片未读。保留实际体验相关性，受阻与情绪均记不明。',problem_status='unknown',problem_themes='',sentiment='unknown')
    by[487]['content_flags']+=';affect_direction_unresolved'
    amend(328,'少看的是己方技能动画带来的用时/流程取舍，不是敌人刷新或转阶段；改归时间成本话题。',themes='roster_build;retry_time_cost')
    amend(272,'“懒得重打”是本人停止继续尝试的动机；补到本人主题，仍不把目标放弃当作已证实的机制原因。',self_experience_themes='damage_threshold;retry_time_cost;reward_motivation')
    diffs=[]
    for k,(r,prev) in enumerate(zip(rows,old),1):
        changed={name:dict(before=prev.get(name),after=r.get(name)) for name in set(prev)|set(r) if prev.get(name)!=r.get(name)}
        r.update(review_pass='second_AI_review',review_kind='ai_reviewed_provisional',reviewer='Codex_AI_second_pass',final='no',codebook_version=VERSION,
            review_decision='amended' if k in changes else 'confirmed_with_existing_limits',
            review_reason=changes.get(k,'逐条复读正文后保留原判断；原理由及媒体、语境等限制继续适用。'),human_reviewed=False,independent_reviewed=False)
        if k in changes:
            r['reason']=changes[k]
            diffs.append(dict(k=k,mode=r['mode'],id=r['id'],reason=changes[k],changes=changed))
        if r['relevance']=='related':
            topics=set(filter(None,r['themes'].split(';')))
            assert set(filter(None,r['self_experience_themes'].split(';')))<=topics
            assert set(filter(None,r['problem_themes'].split(';')))<=set(filter(None,r['self_experience_themes'].split(';')))
        else:assert not r['themes'] and not r['self_experience_themes'] and not r['problem_themes']
        assert r['evidence'] in L[r['id']]['text']
    assert len(rows)==600 and {(r['mode'],r['id']) for r in rows}=={(r['mode'],r['id']) for r in old}
    summary=dict(reviewed=600,amended_rows=len(diffs),unchanged_rows=600-len(diffs),relevance=dict(Counter(r['relevance'] for r in rows)),
        per_mode={m:dict(Counter(r['relevance'] for r in rows if r['mode']==m)) for m in ('abyss','theater','stygian')},
        current_reported_problems=sum(r['problem_status']=='current_reported' for r in rows),
        related_problem_status_unknown=sum(r['relevance']=='related' and r['problem_status']=='unknown' for r in rows),
        human_final=0,independent_coder_validation=False,accuracy_estimated=False)
    result=small.seal(S,'small_snapshot_ai_review_001.json',dict(version=VERSION,status='AI_REVIEWED_PROVISIONAL_NOT_HUMAN_FINAL',
        authorization='用户：核验标签，再提炼问题、计算反馈比例。按此执行AI复核及条件性探索估计；不冒充人工定稿。',
        reviewed_original_indices=list(range(1,601)),original_proposal_hash=digest(S.frozen('small_snapshot_coding_full_proposals_001.json')),
        draw_hash=digest(d),frame_hash=digest(f),master_hashes=before,rows=rows,changes=diffs,summary=summary,
        no_new_sample_or_collection=True,original_human_gates_unchanged=True,classification_error_not_measured=True))
    flat=[]
    for r in rows:
        raw=L[r['id']];a=dict(r,text=raw['text'],url='https://www.bilibili.com/video/'+r['bvid']+'/',raw_level=raw['level'])
        a.pop('candidate_themes_before_relevance_review',None);flat.append(a)
    write_csv(S.path/'small_snapshot_ai_reviewed_coding_001.csv',flat,list(dict.fromkeys(k for r in flat for k in r)))
    write_json(S.path/'small_snapshot_ai_review_changes_001.json',dict(changes=diffs,summary=summary))
    assert master_hashes(S)==before
    return result

if __name__=='__main__':print(json.dumps(review()['summary'],ensure_ascii=False))
