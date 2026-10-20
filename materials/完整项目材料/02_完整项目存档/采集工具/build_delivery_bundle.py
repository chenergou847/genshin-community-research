"""Offline, auditable delivery and human review entry. Never finalizes AI labels."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from observer.core import digest, read_csv, read_json, write_json, write_csv, NAMES
from observer import small
from observer.snapshot_sample import master_hashes
from continue_snapshot_coding import ancestors, public_text, KINDS
from review_snapshot_labels import data, S

P = S.path.parent.parent
OUT = P / '交付_20261019'
KINDS_ZH = dict(firsthand_report='本人实际经历', strategy_advice='配队 / 攻略建议',
    gameplay_question='玩法问题', evaluation_or_comparison='评价或比较', configuration_data='配置数据',
    help_request='本人求助', expectation_or_intention='预期或意向', social_or_meta='社交 / 泛评价',
    off_mode='其他玩法', mechanism_tip='机制提示', platform_meta='平台发评 / 催更',
    other_gameplay_discussion='其他玩法讨论', ambiguous='含混表达', own_account_condition='本人账号条件',
    content_request='内容请求', retrospective_off_mode='回顾其他期次 / 玩法')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split(value):
    return list(filter(None, value.split(';')))


def main():
    frame, draw, lookup, videos, _ = data()
    review = S.frozen('small_snapshot_ai_review_001.json')
    estimates = S.frozen('small_snapshot_AI_exploratory_estimates_001.json')
    cases = S.frozen('small_snapshot_problem_cases_AI_001.json')['rows']
    cards = S.frozen('small_snapshot_problem_cards_AI_001.json')['cards']
    prior_completion = S.frozen('small_snapshot_AI_analysis_completion_001.json')
    raw_before = master_hashes(S)
    assert raw_before == review['master_hashes']
    assert len(review['rows']) == 600 and len(cases) == 76
    assert Counter(r['mode'] for r in review['rows']) == dict.fromkeys(NAMES, 200)
    assert Counter(r['relevance'] for r in review['rows']) == {'related':417,'irrelevant':125,'unknown':58}
    assert all(r['final']=='no' and not r['human_reviewed'] for r in review['rows'])
    materials = {(r['mode'],r['id']):r for r in read_csv(S.path/'small_snapshot_supplement_main_material.csv')}
    codebook = S.frozen('small_snapshot_codebook_proposal_001.json')['codebook']
    topics = [{k:t[k] for k in ('id','label','definition')} for t in codebook['themes']]
    # No new main draw. Repeated-review IDs selected without using AI outcomes.
    salt = S.frozen('small_snapshot_seed_001.json')['seed'] + '|manual-blind-review-v1|'
    ordered = {}
    for mode in NAMES:
        ids = [r['id'] for r in review['rows'] if r['mode']==mode]
        ordered[mode] = sorted(ids,key=lambda i:hashlib.sha256((salt+mode+'|'+i).encode()).hexdigest())[:30]
    registration = dict(purpose='human_blind_repeat_review_not_new_sample',
        registered_after_AI_review=True, registered_before_human_results=True,
        method='top30 SHA256 keyed-order per mode; original frozen seed with new purpose salt',
        outcome_independent_selection=True, draw_hash=digest(draw), review_hash=digest(review),
        ids=ordered, expected_n=90, human_results_n=0,
        same_person_recode_is_not_independent=True, changes_main_sample=False)
    reg_name = 'small_snapshot_human_review_registration_001.json'
    if not (S.path/reg_name).exists():
        small.seal(S,reg_name,registration)
    else:
        existing=S.frozen(reg_name)
        assert all(existing[k]==v for k,v in registration.items())
    OUT.mkdir(exist_ok=True)
    rows=[]
    for i,r in enumerate(review['rows'],1):
        raw=lookup[r['id']];m=materials[r['mode'],r['id']]
        chain=ancestors(raw,lookup)
        limits=[]
        if raw['media']:limits.append('本条有未读图片')
        if any(a['media'] for a in chain):limits.append('上文有未读图片')
        if any(not a['available'] for a in chain):limits.append('有缺失父正文，不能猜测缺失内容')
        a=dict(relevance=r['relevance'],themes=split(r['themes']),
            self_experience_themes=split(r['self_experience_themes']),problem_themes=split(r['problem_themes']),
            theme_status=r['theme_status'],problem_status=r['problem_status'],
            experience_kind=r['experience_kind'],sentiment=r['sentiment'],
            evidence=public_text(r['evidence']),notes=r['reason']+'；复核：'+r['review_reason'])
        assert a['experience_kind'] in KINDS_ZH
        rows.append(dict(index=i,mode=r['mode'],mode_name=NAMES[r['mode']],id=r['id'],bvid=r['bvid'],
            title=videos[r['bvid']]['title'],url=m['url'],text=public_text(raw['text']),
            ctime_bjt=raw['ctime_bjt'],level=raw['level'],author_role=raw['author_role'],
            limits=limits,ancestors=[dict(x,text=public_text(x['text'])) for x in chain],ai=a))
    rules=[codebook[k] for k in ('context_rules','uncertainty_rules','first_person_rules','problem_rules','commercial_rules','sentiment_rules')]
    common=dict(schema='genshin-human-review-v1',sample_draw_hash=digest(draw),
        codebook_version='snapshot-codebook-v0.3-AI-REVIEWED-EXPLORATORY',themes=topics,kinds=KINDS_ZH,rules=rules)
    main_package={**common,'package_id':'main600-'+digest(draw)[:16]+'-'+digest(review)[:16],
        'kind':'main600','rows':rows}
    blindrows=[{k:v for k,v in r.items() if k!='ai'} for r in rows if r['id'] in ordered[r['mode']]]
    blind_package={**common,'package_id':'blind90-'+digest(registration)[:20],
        'kind':'blind90','rows':blindrows}
    assert len(blindrows)==90 and all('ai' not in r for r in blindrows)
    template=Path('review_portal_template.html').read_text(encoding='utf-8')
    for name,obj in [('01_600条人工核验.html',main_package),('02_90条盲复核.html',blind_package)]:
        payload=json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
        (OUT/name).write_text(template.replace('__PAYLOAD__',payload),encoding='utf-8')
    # Private to the study directory, label-free registry for the offline importer.
    write_json(S.path/'small_snapshot_human_review_portal_manifest_001.json',dict(
        schema=common['schema'],packages={obj['kind']:dict(
            package_id=obj['package_id'],expected_keys=[r['mode']+':'+r['id'] for r in obj['rows']])
            for obj in [main_package,blind_package]},
        themes=[x['id'] for x in topics],kinds=list(KINDS_ZH),
        raw_master_hashes=raw_before,draw_hash=digest(draw),review_hash=digest(review)))
    for src,dest in [('small_snapshot_ai_reviewed_coding_001.csv','03_600条AI复核标签_非人工定稿.csv'),
                     ('small_snapshot_problem_cases_AI_001.csv','04_76条体验问题证据.csv'),
                     ('small_snapshot_AI_exploratory_estimates_001.csv','05_72项加权估计与区间_AI探索.csv'),
                     ('small_snapshot_AI_sensitivity_001.csv','06_敏感性检查.csv')]:
        shutil.copyfile(S.path/src,OUT/dest)
    # Cross-file validation, including the outputs sealed before this packaging step.
    for name,expected in prior_completion['output_sha256'].items():
        candidate=P/name if (P/name).exists() else S.path/name
        assert sha(candidate)==expected,(name,'earlier output changed')
    assert master_hashes(S)==raw_before
    qc=dict(raw_master_hashes_unchanged=True,prior_44_45_outputs_unchanged=True,
        main_review_rows=len(rows),blind_review_rows=len(blindrows),human_results_completed=0,
        main_review_AI_prefill_not_confirmation=True,blind_payload_has_no_AI_labels=True,
        unique_mode_IDs=len({(r['mode'],r['id']) for r in rows}),
        label_counts=dict(Counter(r['relevance'] for r in review['rows'])),
        scope='fixed_60_saved_window_bodies_only',
        missing_parent_or_capture_gaps_not_declared_recovered=True,
        original_human_acceptance_not_waived=True)
    write_json(S.path/'small_snapshot_delivery_qc_001.json',qc)
    print(json.dumps(dict(output=str(OUT),main_rows=600,blind_rows=90,raw_unchanged=True,human_final=0),ensure_ascii=False))


if __name__=='__main__':
    main()
