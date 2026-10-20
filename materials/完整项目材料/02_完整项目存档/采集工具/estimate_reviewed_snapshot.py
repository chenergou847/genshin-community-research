"""Conditional finite-snapshot, AI-reviewed EXPLORATORY estimates only.

The original human acceptance gate remains closed. Videos are fixed strata;
every sampled utterance stays in its original stratum, including domain zeros.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math
import json
from observer.core import digest, write_csv, write_json, NAMES
from observer import small
from observer.snapshot_sample import master_hashes
from continue_snapshot_coding import S, TOPICS

METRICS=['self_content_any','reported_problem_any']+['themes.'+v for v in TOPICS.values()]+['problem_themes.'+v for v in TOPICS.values()]

def indicators(r,metric):
    if r['relevance']!='related':return 0,0,int(r['relevance']=='unknown')
    if metric=='reported_problem_any' or metric.startswith('problem_themes.'):
        if r['problem_status']=='unknown':return 0,0,1
        y=int(r['problem_status']=='current_reported') if metric=='reported_problem_any' else int(metric.split('.',1)[1] in r['problem_themes'].split(';'))
        return y,1,0
    if metric=='self_content_any':return int(bool(r['self_experience_themes'])),1,0
    field,topic=metric.split('.',1)
    if r.get('theme_status')=='unknown':return 0,0,1
    return int(topic in r[field].split(';')),1,0

def logistic(x):
    if x>=0:return 1/(1+math.exp(-min(x,700)))
    e=math.exp(max(x,-700));return e/(1+e)

def ratio(clusters):
    """HT ratio + within-stratum SRSWOR residual variance + logit-t interval."""
    A=D=U=0.;n_y=n_d=0;parts=[];census=True
    for c in clusters:
        N=c['N'];z=c['values'];n=len(z)
        if N==0:
            assert not n;continue
        assert 1<=n<=N
        if n<N:assert n>=2
        census &= n==N
        w=N/n;A+=w*sum(a for a,b,u in z);D+=w*sum(b for a,b,u in z);U+=w*sum(u for a,b,u in z)
        n_y+=sum(a for a,b,u in z);n_d+=sum(b for a,b,u in z)
    result=dict(weighted_numerator=A,weighted_known_denominator=D,weighted_unknown_mass=U,
        sample_positive=n_y,sample_known_denominator=n_d,unknown_share_of_potential_related=U/(D+U) if D+U else None,
        unknown_extreme_scenario_bounds=[A/(D+U),(A+U)/(D+U)] if D+U else None,
        bounds_include_sampling_error=False)
    if D<=0:return dict(**result,proportion=None,interval95=None,precision_target_met=False,reason='no_determinate_denominator')
    p=A/D
    for c in clusters:
        N=c['N'];n=len(c['values'])
        if n and n<N:
            residual=[a-p*b for a,b,u in c['values']];mean=sum(residual)/n
            vh=N*N*(1-n/N)*sum((e-mean)**2 for e in residual)/(n*(n-1))
            parts.append((vh,n-1))
    v=sum(vh for vh,df in parts)/(D*D)
    effective_df=(sum(vh for vh,df in parts)**2/sum(vh*vh/df for vh,df in parts if vh)) if any(vh for vh,df in parts) else None
    sparse=n_y<5 or n_d-n_y<5
    if census:ci=[p,p];reason='fixed_frame_census_given_labels'
    elif v<=0 or p in (0.,1.):ci=[0.,1.];reason='zero_variance_or_endpoint_is_not_absence'
    else:
        critical=small.T95[min(30,max(1,int(effective_df)))]
        center=math.log(p/(1-p));margin=critical*math.sqrt(v)/(p*(1-p))
        ci=[logistic(center-margin),logistic(center+margin)];reason='nominal_approximate_pointwise_logit_t'
    return dict(**result,proportion=p,interval95=ci,sampling_variance=v,effective_df=effective_df,
        sparse_support_flag=sparse,precision_target_met=(not sparse or census) and max(p-ci[0],ci[1]-p)<=.10,
        method='fixed_video_strata_SRSWOR_HT_ratio_Taylor_residual_logit_t',reason=reason,
        interval_excludes_coverage_and_classification_error=True)

def clusters_for(draw,m,lookup,metric,include=lambda r:True):
    clusters=[]
    for bv,v in draw['samples'][m].items():
        values=[]
        for i in v['ids']:
            r=lookup[m,i]
            values.append(indicators(r,metric) if include(r) else (0,0,0))
        clusters.append(dict(N=v['N'],values=values))
    return clusters

def run():
    review=S.frozen('small_snapshot_ai_review_001.json');draw=S.frozen('small_snapshot_supplement_draw_001.json');frame=S.frozen('small_snapshot_frame_001.json')
    old=S.frozen('small_snapshot_coding_full_proposals_001.json');videos={r['bvid']:r for r in S.frozen('small_video_selection.json')['videos']}
    assert review['status']=='AI_REVIEWED_PROVISIONAL_NOT_HUMAN_FINAL' and review['draw_hash']==digest(draw)
    assert all(r['final']=='no' and not r['human_reviewed'] for r in review['rows'])
    registration_name='small_snapshot_AI_exploratory_estimation_registration_001.json'
    if not (S.path/registration_name).exists():
        small.seal(S,registration_name,dict(status='EXPLORATORY_AI_LABELS_NOT_HUMAN_FINAL',authorization='用户要求核验标签、提炼问题并计算反馈比例；仅生成明确标识的AI复核探索结果。',
            scope='fixed_60_sources_saved_normalized_in_window_bodies_only',draw_hash=digest(draw),review_hash=digest(review),
            unit='utterance_ID_not_person',weights='N_video/final_m_video; no second weight for retained/new',
            metrics=METRICS,denominators='themes/self: determinate-related utterances; reported problems: related and determinate problem status',
            variance='within_fixed_video_stratum_SRSWOR_HT_ratio_Taylor_residual',CI='logit transform; Satterthwaite residual-component df; floor df and use at most df30 t95 critical value; pointwise nominal approximation',
            endpoints='noncensus p=0/1 or variance=0 => [0,1], not proof of absence',sparse='positive or complementary observed support <5 => do not claim precision met',
            unknown_bounds='[A/(D+U),(A+U)/(D+U)]; scenario only, no sampling error or unsaved-body correction',
            human_gate_unchanged=True,formal_estimates_generated=False))
    lookup={(r['mode'],r['id']):r for r in review['rows']};raw={r['id']:r for r in frame['comments']}
    oldlookup={(r['mode'],r['id']):r for r in old['rows']}
    result={};flat=[];sensitivity_rows=[]
    for m,vs in draw['samples'].items():
        N=sum(v['N'] for v in vs.values());status=Counter();unweighted=Counter();source_contribution=Counter();author_contribution=Counter();thread_contribution=Counter()
        for bv,v in vs.items():
            w=v['N']/v['m'] if v['m'] else 0
            for i in v['ids']:
                r=lookup[m,i];status[r['relevance']]+=w;unweighted[r['relevance']]+=1
                if r['relevance']=='related':
                    source_contribution[bv]+=w;author_contribution[videos[bv]['primary_up']]+=w;thread_contribution[raw[i]['root_id']]+=w
        assert abs(sum(status.values())-N)<1e-7
        metrics={key:ratio(clusters_for(draw,m,lookup,key)) for key in METRICS}
        largest_source=max(vs,key=lambda b:vs[b]['N']);largest_up=max(author_contribution,key=author_contribution.get) if author_contribution else None
        largest_thread=max(thread_contribution,key=thread_contribution.get) if thread_contribution else None
        scopes={
            'audience_only':lambda r:raw[r['id']]['author_role']=='audience',
            'roots_only':lambda r:raw[r['id']]['level']=='root',
            'replies_only':lambda r:raw[r['id']]['level']=='reply',
            'exclude_largest_source':lambda r:r['bvid']!=largest_source,
            'exclude_largest_uploader':lambda r:videos[r['bvid']]['primary_up']!=largest_up,
            'exclude_largest_thread':lambda r:raw[r['id']]['root_id']!=largest_thread,
            'exclude_suspected_commercial':lambda r:'suspected_commercial_content' not in r['content_flags'].split(';'),
            'text_without_own_or_ancestor_image':lambda r:r['context_status']=='checked',
        }
        sensitivity={}
        for name,keep in scopes.items():
            sensitivity[name]={key:ratio(clusters_for(draw,m,lookup,key,keep)) for key in METRICS}
        broad=deepcopy(lookup)
        for key,r in list(broad.items()):
            if 'domain_ambiguous_after_context_review' in r['content_flags'].split(';'):broad[key]=oldlookup[key]
        sensitivity['allow_ambiguous_mixed_video_role_discussion']={key:ratio(clusters_for(draw,m,broad,key)) for key in METRICS}
        loo={bv:{key:ratio(clusters_for(draw,m,lookup,key,lambda r:r['bvid']!=bv))['proportion'] for key in METRICS} for bv,v in vs.items() if v['m']}
        result[m]=dict(frame_N=N,sample_n=sum(v['m'] for v in vs.values()),selected_videos=len(vs),nonempty_sources=sum(v['N']>0 for v in vs.values()),
            label_counts=dict(unweighted),weighted_label_masses=dict(status),weighted_label_shares={k:x/N for k,x in status.items()},
            relatedness_extreme_scenario_bounds=[status['related']/N,(status['related']+status['unknown'])/N],
            source_contribution_to_known_related=dict(source_contribution),largest_source=largest_source,largest_source_frame_share=vs[largest_source]['N']/N,
            largest_related_source_share=max(source_contribution.values())/status['related'] if status['related'] else None,
            largest_related_uploader_share=max(author_contribution.values())/status['related'] if status['related'] else None,
            largest_related_thread_share=max(thread_contribution.values())/status['related'] if status['related'] else None,
            metrics=metrics,sensitivity=sensitivity,leave_one_source_out=loo,
            sensitivity_scope='changed_subdomains_or_coding_assumptions; not substitute estimates for the main domain')
        for key,x in metrics.items():flat.append(dict(mode=m,副本=NAMES[m],metric=key,**x))
        for name,items in sensitivity.items():
            for key,x in items.items():sensitivity_rows.append(dict(mode=m,scenario=name,metric=key,point=x['proportion'],known_weight=x['weighted_known_denominator'],unknown_weight=x['weighted_unknown_mass']))
    payload=dict(status='AI_REVIEWED_EXPLORATORY_NOT_HUMAN_FINAL',formal_human_acceptance=False,scope='fixed_60_sources_6526_saved_window_bodies_not_Bilibili_or_players',
        label_review_hash=digest(review),draw_hash=digest(draw),registration_hash=digest(S.frozen(registration_name)),domains=result,
        confidence='nominal_pointwise_approximate_95%; conditional_on_AI_labels_and_fixed_saved_frame; no_classification_error_included',
        thematic_saturation_claimed=False,coverage_sufficiency_proven=False,all_metrics_precision_target_met=False)
    name='small_snapshot_AI_exploratory_estimates_001.json'
    if (S.path/name).exists():assert S.frozen(name)['domains']==result
    else:small.seal(S,name,payload)
    # Lists/dicts are kept structured in JSON; display CSV has explicit scalar columns.
    display=[]
    for r in flat:
        item={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        item['ci95_lower'],item['ci95_upper']=(r['interval95'] or [None,None])
        item['unknown_scenario_lower'],item['unknown_scenario_upper']=(r['unknown_extreme_scenario_bounds'] or [None,None])
        display.append(item)
    write_csv(S.path/'small_snapshot_AI_exploratory_estimates_001.csv',display,list(dict.fromkeys(k for r in display for k in r)))
    write_csv(S.path/'small_snapshot_AI_sensitivity_001.csv',sensitivity_rows,list(sensitivity_rows[0]))
    assert master_hashes(S)==review['master_hashes']
    print(json.dumps({m:dict(label_counts=x['label_counts'],weighted_label_shares=x['weighted_label_shares'],reported_problem_any=x['metrics']['reported_problem_any'],largest_related_source_share=x['largest_related_source_share']) for m,x in result.items()},ensure_ascii=False))
    return payload

if __name__=='__main__':run()
