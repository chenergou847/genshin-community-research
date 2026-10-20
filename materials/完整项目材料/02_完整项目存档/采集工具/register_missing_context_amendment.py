"""Register the user's approved parent-context exception; offline, no draw."""
from collections import Counter
from pathlib import Path
import argparse
import json

from observer import small
from observer.context_policy import RULE, RULE_FILE, ancestry_annotations, load_rule, source_eligible
from observer.core import Study, GateError, digest, now, read_csv, read_json, read_jsonl, ts, write_csv, write_json


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--study',default='正式采集_小样本v1_20261018')
    args=ap.parse_args()
    s=Study(args.study);small.check(s)
    final_name='small_context_disposition_015.json'
    if (s.path/final_name).exists():
        print(json.dumps(s.frozen(final_name)['summary'],ensure_ascii=False));return
    if any((s.path/n).exists() for n in ('small_comment_frame.json','small_codebook.json','small_comment_draw.json')):
        raise GateError('必须在正式评论框、代码本与第二阶段随机样本生成前登记')
    selection=s.frozen('small_video_selection.json')
    collection=read_json(s.path/'small_collection.json')
    rows=read_jsonl(s.path/'small_comments.jsonl');obs=read_jsonl(s.path/'small_observations.jsonl')
    assert digest(rows)==collection['comments_hash'] and digest(obs)==collection['observations_hash']
    audit=s.frozen('small_integrity_audit_010.json')
    assert audit['collection_hash']==digest(collection) and audit['comments_hash']==digest(rows)
    previous=s.frozen('small_context_rule_decision_001.json')
    if not (s.path/RULE_FILE).exists():
        small.seal(s,RULE_FILE,dict(policy=RULE,selection_hash=digest(selection),
            baseline_collection_hash=digest(collection),prior_decision_hash=digest(previous),
            strict_missing_parent_required=False,count_paging_provenance_gates_unchanged=True,
            human_reply='同意，保留不明并继续比例估计（建议）',source='direct_user_reply_in_current_chat',
            confirmed_question='是否同意把“缺失父正文就停止抽样”改为“可读子回复照常进入抽样清单，抽中后语境不足则标记不明”，继续估计可读评论的反馈比例？',
            registration_timing='after_gap_inspection_before_comment_frame_codebook_and_second_stage_draw',
            rules=dict(keep_all_readable_children=True,invent_parent_text=False,replace_unknown_sample=False,
                replace_sources=False,deletion_is_confirmed=False,report_weighted_unknown_and_bounds=True,
                distinguish_unknown_relevance_from_unknown_theme=True,precision_target_unchanged=.10)))
    write_json(s.path/'small_context_integrity_current.json',dict(file='small_integrity_audit_010.json',hash=digest(audit)))
    context=load_rule(s,selection,collection)
    annotations=ancestry_annotations(rows,True)
    assert set(annotations)=={i for a in audit['sources'] for i in a['ancestor_affected_descendant_IDs']}
    snapshot=small.seal(s,'small_collection_review_before_context_015.json',dict(rows=read_csv(s.path/'small_collection_review.csv')))
    reviews=snapshot['rows']
    pure_context=[v['bvid'] for v in collection['videos'] if v.get('reason')=='missing_ancestor' and source_eligible(context,v)]
    for r in reviews:
        if r['bvid'] in pure_context:
            r.update(status='pending_context_source_page_review',final='no',
                reconciliation='015修订：缺父语境不再单独阻塞；原分页及数量技术核对通过；独立页面及后续时点变化尚待核验，不自动验收')
        elif r['bvid']=='BV137aA63EF6':
            r['reconciliation']='015修订仅解除缺父语境门槛；原快照3430对3434仍差4条，继续阻塞'
    write_csv(s.path/'small_collection_review.csv',reviews,small.RFIELDS)
    review_by={r['bvid']:r for r in reviews}
    sources=[]
    for v in collection['videos']:
        bv=v['bvid'];a=context['sources'][bv]
        sources.append(dict(bvid=bv,acquisition_status_unchanged=v['status'],original_findings=a['errors'],
            enumeration_eligible_under_amendment=source_eligible(context,v),
            non_context_findings=[e for e in a['errors'] if e!='missing_ancestor'],
            missing_parent_IDs=a['missing_parent_IDs'],affected_descendants=a['ancestor_affected_descendant_IDs'],
            review_status=review_by[bv]['status'],review_final=review_by[bv]['final']))
    summary=dict(sources=len(sources),technical_enumeration_eligible=sum(x['enumeration_eligible_under_amendment'] for x in sources),
        technical_count_or_other_holds=sum(not x['enumeration_eligible_under_amendment'] for x in sources),
        parent_only_sources_reclassified=len(pure_context),source_review_status_counts=dict(Counter(r['status'] for r in reviews)),
        unique_readable_IDs=len(rows),roots=sum(r['level']=='root' for r in rows),replies=sum(r['level']=='reply' for r in rows),
        missing_unique_parent_IDs=len({p for a in audit['sources'] for p in a['missing_parent_IDs']}),
        ancestor_affected_descendants=len(annotations),formal_random_comments_drawn=0,
        affected_window_counts={m:sum(r['id'] in annotations and ts(s.config['periods'][m]['start'])<=r['ctime']<=ts(s.config['t0'])
            for r in rows if r['bvid'] in {v['bvid'] for v in selection['domains'][m]['selected']}) for m in selection['domains']})
    try:
        small.freeze_comments(s)
    except GateError as exc:
        summary['freeze_gate_result']=str(exc)
    else:
        raise AssertionError('Existing non-context failures must still block the frame')
    result=small.seal(s,final_name,dict(summary=summary,sources=sources,context_annotations=annotations,
        rule_hash=digest(context['rule']),audit_file=context['audit_file'],audit_hash=digest(audit),
        selection_hash=digest(selection),collection_hash=digest(collection),comments_hash=digest(rows),observations_hash=digest(obs),
        scope='same_frozen_video_domain_and_comment_windows; missing bodies are context references, not sampling units',
        coding_rules=dict(relevance='related/irrelevant/unknown',theme_status='known/unknown',
            known_relevant_theme_unknown='keep relevance=related, theme_status=unknown, no theme assignment',
            point_denominator='weighted related and theme-determinate utterances; label conditional scope',
            sensitivity='D=known theme-determinate related weight; A=theme weight; U=unknown relevance or known-related unknown-theme weight; bounds=[A/(D+U),(A+U)/(D+U)]',
            bounds_are_not_95_percent_CIs=True,affected_does_not_mean_uncodable=True)))
    state=read_json(s.path/'执行状态.json')
    state.update(strict_missing_parent_required=False,missing_parent_rule_user_decision=context['rule']['human_reply'],
        stage='CONTEXT_RULE_AMENDED_OTHER_INTEGRITY_GATES_REMAIN',
        context_amendment=dict(at=now(),file=RULE_FILE,report=final_name,research_record='38_缺失父正文处理规则修订_20261019.md',**summary))
    state['integrity_audit'].update(technical_eligible_under_context_amendment=summary['technical_enumeration_eligible'],
        non_context_integrity_holds=summary['technical_count_or_other_holds'],context_amendment=final_name,
        formal_random_comments_drawn=0,collection_freeze_gate_verified_blocked=True)
    write_json(s.path/'执行状态.json',state)
    assert read_json(s.path/'small_collection.json')==collection
    assert digest(read_jsonl(s.path/'small_comments.jsonl'))==digest(rows)
    assert digest(read_jsonl(s.path/'small_observations.jsonl'))==digest(obs)
    assert not (s.path/'small_comment_frame.json').exists()
    print(json.dumps(result['summary'],ensure_ascii=False))


if __name__=='__main__':
    main()
