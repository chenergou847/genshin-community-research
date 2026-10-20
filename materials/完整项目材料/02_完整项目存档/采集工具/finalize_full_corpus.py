"""Freeze full AI coding and calculate corpus descriptions, never population weights."""
from collections import Counter, defaultdict
from copy import deepcopy
import json, math, re
from pathlib import Path
from full_corpus_coding import setup, labels, seal as frozen_seal, S, REASONS
from observer.core import digest, now, read_json, write_json
from observer.snapshot_sample import master_hashes

OUT=S.path.parent.parent/'全量编码_20261019'
MODES={'abyss':'深境螺旋','theater':'幻想真境剧诗','stygian':'幽境危战'}

def seal(name,obj):
    return frozen_seal(name,{k:v for k,v in obj.items() if k not in ('at','config_hash','source_hash')})

def main():
    frame,raw,video,queue,initial,book=setup()
    original=labels(initial);rows=deepcopy(list(original.values()))
    byn={r.get('semantic_index'):r for r in rows if r.get('semantic_index')}
    amendments=[]
    def amend(n,reason,**updates):
        r=byn[n];before={k:r.get(k) for k in updates}
        if all(before[k]==v for k,v in updates.items()):return
        r.update(updates)
        amendments.append(dict(mode=r['mode'],id=r['id'],semantic_index=n,before=before,after=updates,reason=reason))
    # Explicitly reread cases: bare results/configuration do not establish difficulty.
    remove_d='236 301 324 326 365 408 449 463 479 541 587 604 615 656 659 663 410 451 459 481 568 576 709 716 771 795 798 826 828 833 838 849 863 877 878 879 895 905 932 954 957 961 973 979 985 996 1032 1040 1043 1056 1062 1063 1066 1079 1092 1127 1157 1179 1181 1198 1203 1227 1231 1267 1268 1270 1275 1278 1285 1335 1339 1340 1341 1367 1372 1425 1513 1530 1566 1568 1583 1584 1599 1621 1698 1844 1944 2518 2546 2572 2573 2591 2610 2622 2630 2644 2648 2650 2661 2666 2668 2704 2708 2711 2722 2726 2730 2734 2745 2748 2752 2756 2793 2797 2801 2804 2816 2834 2840 2854 2857 2866 2869 2870 2889 2897 2903 2907 2936 2953 2961 2962 2966 2967 2969 2975 2983 2986 2988 2990 2997 3012 3021 3037 3051 3057 3058 3064 3067 3068 3072 3095 3097 3103 3104 3109 3126 3135 3169 3176 3177 3195 3196 3208 3217 3222 3223 3230 3240 3243 3251 3260 3280 3283 3293 3303 3372 3502 3547 3604 3612 3621 3623 3625 3632 3657 3676 3738 3747 3770 3884 3886 3931 3954 3984 3990 4030 4032 4145 4194 4249 4250 4252 4253 4277 4327 4365 4380 4437 4441 4442 4443 4444 4456 4460 4462 4464 4476 4480 4488 4490 4513 4519 4544 4758 4768 4771 4797 4806 4810 4812 4815 4822 4825 4826 4874 5023 5100 5109 5157 5182 5302 5305 5339 5374 5389 5392 5394 5420 5602 5618 5533 5535 5668 5669 5699 5708 5793 5845 5897'
    for n in map(int,remove_d.split()):
        r=byn[n]
        if 'damage_threshold' in r['problem_themes'].split(';'):continue
        th=[t for t in r['themes'].split(';') if t and t!='damage_threshold']
        st=[t for t in r['self_experience_themes'].split(';') if t and t!='damage_threshold']
        if not th:th=['other_current_experience'];st=th if r['experience_kind']=='firsthand_report' else []
        amend(n,'按校准规则复查：纯通关、配置、耗时或角色表现不自动增加难度主题。',themes=';'.join(th),self_experience_themes=';'.join(st))
    def recode(n,kind,topics,selftopics='',problem='',relevance='related',flag=''):
        r=byn[n]
        amend(n,'复读正文及必要上文后校正发言主体、话语类型或实际体验范围。',
              relevance=relevance,experience_kind=kind,themes=topics,self_experience_themes=selftopics,
              problem_themes=problem,problem_status='current_reported' if problem else 'none_explicit',
              theme_status='unknown' if relevance=='unknown' else 'known')
        if flag:r['content_flags']=';'.join(filter(None,[r.get('content_flags'),flag]))
    for n in (1490,1508):recode(n,'evaluation_or_comparison','damage_threshold')
    for n in (3072,3097,3176,3177,3222,3223,3770,5793):recode(n,'configuration_data','roster_build','roster_build')
    for n in (2708,2869,3068):recode(n,'strategy_advice','roster_build')
    for n in (2756,2986,3103,3104,4032,4442,4464,4488,5305):recode(n,'evaluation_or_comparison','roster_build')
    recode(2591,'mechanism_tip','mechanic_understanding',flag='simulation_or_dummy')
    recode(2734,'firsthand_report','retry_time_cost','retry_time_cost')
    recode(2903,'expectation_or_intention','reward_motivation;damage_threshold','reward_motivation')
    recode(2988,'mechanism_tip','mechanic_understanding',flag='external_program_error')
    recode(3283,'firsthand_report','co_op_social','co_op_social')
    recode(3303,'strategy_advice','co_op_social')
    recode(3372,'configuration_data','roster_build','roster_build',flag='simulation_or_dummy')
    recode(3492,'expectation_or_intention','roster_build;damage_threshold','roster_build')
    recode(3579,'firsthand_report','roster_build;mechanic_understanding;damage_threshold',
           'roster_build;mechanic_understanding;damage_threshold','damage_threshold')
    recode(3621,'gameplay_question','other_current_experience')
    for n in (3623,3625):recode(n,'firsthand_report','co_op_social','co_op_social')
    recode(3653,'firsthand_report','mechanic_understanding','mechanic_understanding','mechanic_understanding')
    recode(3657,'evaluation_or_comparison','co_op_social')
    recode(3676,'ambiguous','','',relevance='unknown',flag='image_unread')
    recode(5708,'configuration_data','roster_build','roster_build')
    for n in (3931,4135):byn[n]['content_flags']=';'.join(filter(None,[byn[n].get('content_flags'),'other_account']))
    for n in (2832,4635,4743,4857,5341,5515,5529):
        r=byn[n]
        amend(n,'语境复查：仅希望角色分身的夸张表达保留为需求线索，不直接计为本人已发生受阻。',
              problem_themes='',problem_status='none_explicit')
        r['content_flags']=';'.join(filter(None,[r.get('content_flags'),'figurative_language']))
    for r in rows:
        # Correct serialization of explicitly authored @I|cross / @I|platform shorthand.
        if r['reason']==REASONS['cross'] and r['experience_kind']=='social_or_meta':
            old=r['experience_kind'];r['experience_kind']='off_mode'
            amendments.append(dict(mode=r['mode'],id=r['id'],before={'experience_kind':old},
                after={'experience_kind':'off_mode'},reason='修正速记解析器：cross分类不能序列化为social。'))
        if r['reason']==REASONS['platform'] and r['experience_kind']=='social_or_meta':
            r['experience_kind']='platform_meta'
        rr=raw[r['id']];flags=set(filter(None,r.get('content_flags','').split(';')))
        if rr['media']:flags.add('image_unread')
        ancestor=[];p=rr['parent_id'];seen={rr['id']}
        while p!='0' and p not in seen:
            seen.add(p);a=raw.get(p)
            if a is None:flags.add('missing_ancestor');break
            ancestor.append(p)
            if a['media']:flags.add('ancestor_image_unread')
            p=a['parent_id']
        r.update(text=rr['text'],text_hash=rr['text_hash'],root_id=rr['root_id'],parent_id=rr['parent_id'],
            level=rr['level'],author_id=rr['author_id'],author_role=rr['author_role'],ctime_bjt=rr['ctime_bjt'],
            like=rr['like'],like_snapshot_at=rr['last_read_at'],declared_reply_count=rr.get('reply_count'),
            context_ancestor_ids=ancestor,content_flags=';'.join(sorted(flags)),
            attention_weight=1+min(math.log10(1+rr['like']),2),unit_weight=1,
            human_reviewed=r.get('human_reviewed',False),independent_validation=False)
        r['authorship']='human_calibration' if r['human_reviewed'] else 'AI_project_coding'
        r['coding_status']='project_final_AI_calibrated_no_independent_validation'
        r.pop('notes',None)
        if flags or r['relevance']=='unknown':r['context_status']='checked_with_limits'
    target={(m,i) for m,bs in frame['frames'].items() for ids in bs.values() for i in ids}
    actual={(r['mode'],r['id']) for r in rows}
    assert len(rows)==len(actual)==len({r['id'] for r in rows})==6526 and actual==target
    for r in rows:
        th=set(filter(None,r['themes'].split(';')));st=set(filter(None,r['self_experience_themes'].split(';')));pr=set(filter(None,r['problem_themes'].split(';')))
        assert pr<=st<=th
        assert r['relevance']=='related' or not th|st|pr
        assert bool(pr)==(r['problem_status']=='current_reported')
        assert r['evidence'] in raw[r['id']]['text'] or r['evidence']==''
        assert 1<=r['attention_weight']<=3 and r['like']>=0
    assert sum(r['human_reviewed'] for r in rows)==30
    reg=S.frozen('full_corpus_review_registration_001.json')
    assert master_hashes(S)==reg['raw_master_sha256']
    amendment=seal('full_corpus_semantic_amendments_002.json',dict(at=now(),changes=amendments,
        before_labels_hash=digest(list(original.values())),rule='apply accepted codebook, no holdout used'))
    waiver=seal('full_corpus_validation_waiver_001.json',dict(at=now(),authority='direct_user_reply_in_current_chat',
        user_reply='编码完的评论csv不需要给我核验，我相信你的判断，直接进入下一步。关注度指标、点赞加权等指标需要在分析报告中明确指出',
        human_calibration_n=30,independent_validation_n=0,holdout_used=False,
        validation_waived=True,accuracy_measured=False,full_AI_project_coding_authorized=True))
    rows.sort(key=lambda r:(list(MODES).index(r['mode']),r['bvid'],r['ctime_bjt'],r['id']))
    frozen=seal('full_corpus_labels_final_002.json',dict(at=now(),rows=rows,n=len(rows),
        scope=reg['scope'],codebook_hash=digest(book),amendment_hash=digest(amendment),
        waiver_hash=digest(waiver),raw_master_sha256=reg['raw_master_sha256'],
        human_calibration_n=30,independent_validation_n=0,accuracy_measured=False))
    assert frozen['rows']==rows
    themes={t['id']:t['label'] for t in book['codebook']['themes']}
    totals=[];metrics=[];sensitivities=[];source_rows=[]
    for mode in MODES:
        rs=[r for r in rows if r['mode']==mode];related=[r for r in rs if r['relevance']=='related'];unknown=[r for r in rs if r['relevance']=='unknown']
        countsrc=Counter(r['bvid'] for r in rs);largest=countsrc.most_common(1)[0][0]
        totals.append(dict(mode=mode,n=len(rs),related=len(related),irrelevant=sum(r['relevance']=='irrelevant' for r in rs),unknown=len(unknown),
            roots=sum(r['level']=='root' for r in rs),replies=sum(r['level']=='reply' for r in rs),
            unique_authors=len({r['author_id'] for r in rs}),problem_comments=sum(bool(r['problem_themes']) for r in rs),
            total_likes=sum(r['like'] for r in rs),zero_like=sum(r['like']==0 for r in rs),
            image_unread=sum('image_unread' in r['content_flags'].split(';') for r in rs),
            missing_ancestor=sum('missing_ancestor' in r['content_flags'].split(';') for r in rs),
            largest_source=largest,largest_source_n=countsrc[largest],largest_source_share=countsrc[largest]/len(rs)))
        for bv in frame['frames'][mode]:
            sr=[r for r in rs if r['bvid']==bv]
            source_rows.append(dict(mode=mode,bvid=bv,title=video[bv]['title'],n=len(sr),related=sum(r['relevance']=='related' for r in sr),
                problem_comments=sum(bool(r['problem_themes']) for r in sr),likes=sum(r['like'] for r in sr)))
        for field,label in [('themes','主题'),('problem_themes','本人明确问题')]:
            for theme,name in themes.items():
                hits=[r for r in related if theme in r[field].split(';')]
                denom=sum(r['attention_weight'] for r in related)
                metrics.append(dict(mode=mode,metric_type=label,theme=theme,theme_label=name,n=len(hits),
                    related_denominator=len(related),all_denominator=len(rs),equal_share_related=len(hits)/len(related),
                    equal_share_all=len(hits)/len(rs),attention_share=sum(r['attention_weight'] for r in hits)/denom,
                    raw_likes=sum(r['like'] for r in hits),raw_likes_share=sum(r['like'] for r in hits)/sum(r['like'] for r in related) if sum(r['like'] for r in related) else None,
                    sources=len({r['bvid'] for r in hits}),authors=len({r['author_id'] for r in hits}),
                    ambiguity_lower_all=len(hits)/len(rs),ambiguity_upper_all=(len(hits)+len(unknown))/len(rs)))
                for scenario,pool in [
                    ('exclude_largest_source',[r for r in related if r['bvid']!=largest]),
                    ('roots_only',[r for r in related if r['level']=='root']),
                    ('replies_only',[r for r in related if r['level']=='reply']),
                    ('exclude_context_gap',[r for r in related if 'missing_ancestor' not in r['content_flags'].split(';')]),
                    ('audience_only',[r for r in related if r['author_role']=='audience']),
                    ('exclude_flagged_promotion',[r for r in related if not re.search('commercial|promot|广告|推广',r['content_flags'],re.I)])]:
                    hh=[r for r in pool if theme in r[field].split(';')]
                    sensitivities.append(dict(mode=mode,metric_type=label,theme=theme,scenario=scenario,n=len(hh),denominator=len(pool),
                        share=len(hh)/len(pool) if pool else None,
                        attention_share=sum(r['attention_weight'] for r in hh)/sum(r['attention_weight'] for r in pool) if pool else None))
    stats=dict(at=now(),label_hash=digest(frozen),totals=totals,metrics=metrics,sensitivities=sensitivities,sources=source_rows,
        weight_formula='1 + min(log10(1 + like), 2)',weights_exploratory_not_sampling_weights=True,
        all_n=6526,likes=sum(r['like'] for r in rows),zero_like=sum(r['like']==0 for r in rows),
        top10_likes=sum(sorted(r['like'] for r in rows)[-10:]),
        unit='comment utterance ID; not unique player or unique liker',
        rank_inference_allowed=False,no_sampling_CI_for_census=True,independent_accuracy_validation=False)
    seal('full_corpus_analysis_002.json',stats)
    OUT.mkdir(exist_ok=True)
    write_json(OUT/'编码分析数据.json',dict(rows=rows,statistics=stats,themes=themes,modes=MODES))
    # CSV is a flat analytical interchange file; workbook APIs validate/export it separately.
    import csv
    fields=['mode','id','bvid','ctime_bjt','level','text','relevance','experience_kind','themes','self_experience_themes',
        'problem_status','problem_themes','sentiment','like','unit_weight','attention_weight','content_flags','author_id','author_role','root_id','parent_id',
        'human_reviewed','authorship','independent_validation','evidence','reason','like_snapshot_at']
    with (OUT/'全量编码明细.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    with (OUT/'分副本主题与关注度.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
    state=read_json(S.path/'执行状态.json')
    state.update(stage='FULL_CORPUS_CODED_ANALYSIS_IN_PROGRESS',current_protocol='full-corpus-calibrated-AI-v2-waived-validation',
        current_research_record='49_全量编码定稿与分析口径_20261019.md')
    state['full_corpus_review'].update(full_corpus_coding_complete=True,coded=6526,remaining=0,validation_received=0,
        validation_waived=True,validation_waiver_file='full_corpus_validation_waiver_001.json',audit_accuracy_measured=False,
        progress=dict(total_target=6526,coded=6526,remaining=0,human_calibration=30,AI_project_coded=6496),required_human_action=None)
    state['human_review'].update(validation_expected=0,validation_waived=True,required_action=None)
    write_json(S.path/'执行状态.json',state)
    print(json.dumps(dict(total=6526,related=sum(r['relevance']=='related' for r in rows),unknown=sum(r['relevance']=='unknown' for r in rows),
        problem_comments=sum(bool(r['problem_themes']) for r in rows),amendments=len(amendments),totals=totals),ensure_ascii=False))

if __name__=='__main__':main()
