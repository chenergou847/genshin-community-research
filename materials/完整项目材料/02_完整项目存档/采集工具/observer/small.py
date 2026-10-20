"""Bounded discovery, SRS of eligible videos, SRS of raw window utterances.

Eligibility is screened along a frozen random permutation. The first K eligible
videos are an SRS from the (possibly not fully classified) eligible domain. The
unknown common first-stage expansion factor cancels in within-mode ratios.
"""
import math
import re
import secrets
from collections import Counter

from .core import (Study, GateError, MODES, VIDEO_FIELDS, SCREEN_FIELDS, bvid, identifier,
                   digest, now, permutation, read_csv, read_json, read_jsonl,
                   source_hash, ts, write_csv, write_json, write_jsonl)
from .collect import payload, collect_video
from .context_policy import load_rule, source_eligible, ancestry_annotations

PROTOCOL='17-small-v1'
GROUPS=('main','audit_a','audit_b')
VFIELDS=VIDEO_FIELDS+['final','review_kind']
CFIELDS=SCREEN_FIELDS+['review_kind','theme_status']
RFIELDS=['bvid','status','count_semantics_evidence','reconciliation','pagination_evidence','reviewer','final']
AFIELDS=['mode','id','relevance','themes','self_experience_themes','reviewer','review_kind','final',
         'date_checked','role_checked','context_status','resolution','resolved_relevance','resolved_themes','resolved_self_experience_themes',
         'theme_status','resolved_theme_status']


def check(s):
    if s.config.get('protocol')!=PROTOCOL:
        raise GateError('该命令仅适用于17-small-v1')
    s.validate()
    s.frozen('registration.json') # prevents post-registration edits to time, scope or targets


def status(s):
    check(s)
    files=['small_candidate_frame.json','small_video_draw.json','small_video_selection.json','small_comment_frame.json','small_codebook.json','small_comment_draw.json','small_estimates.json']
    out=dict(protocol=s.config['protocol'],targets=s.config['targets'],t0=s.config['t0'],files={x:(s.path/x).exists() for x in files},
             note='目标不是实收数；文件存在也不代表审核或统计验收通过')
    out['bounded_queries_completed']={};out['discovery_groups_sealed']={}
    for g in GROUPS:
        name='small_discovery_'+g+'.json';progress=s.path/('small_discovery_'+g+'_progress.json')
        frozen=(s.path/name).exists();out['discovery_groups_sealed'][g]=frozen
        obj=s.frozen(name) if frozen else (read_json(progress) if progress.exists() else {'config_hash':s.config_hash,'queries':[]})
        if obj['config_hash']!=s.config_hash:raise GateError('检索进度来自不同配置')
        out['bounded_queries_completed'][g]=sum(q['status']=='bounded_complete' for q in obj['queries'])
    if (s.path/'small_candidate_frame.json').exists():
        f=s.frozen('small_candidate_frame.json');out['candidate_video_domain_rows']=len(f['records']);out['different_candidate_videos']=len({r['bvid'] for r in f['records']})
    if (s.path/'small_video_selection.json').exists():
        f=s.frozen('small_video_selection.json');out['selected_videos_by_mode']={m:len(v['selected']) for m,v in f['domains'].items()};out['different_selected_videos']=len(f['videos'])
    if (s.path/'small_comment_frame.json').exists():
        f=s.frozen('small_comment_frame.json');out['window_IDs_in_selected_videos']={m:sum(len(ids) for ids in vs.values()) for m,vs in f['frames'].items()}
    if (s.path/'small_comment_draw.json').exists():
        f,d,cb=load_comments(s);out['random_raw_sample_rows']={m:sum(v['m'] for v in vs.values()) for m,vs in d['samples'].items()}
        out['different_random_raw_sample_IDs']=len({i for vs in d['samples'].values() for v in vs.values() for i in v['ids']})
    return out


def seal(s,name,obj):
    if (s.path/name).exists():
        raise GateError('该阶段已冻结，不能覆盖或重抽：'+name)
    return s.immutable(name,dict(config_hash=s.config_hash,at=now(),source_hash=source_hash(),**obj))


def unique_map(rows,keys):
    d={tuple(r[k] for k in keys):r for r in rows}
    if len(d)!=len(rows):
        raise GateError('审核表出现重复主键')
    return d


def discover(s,api,group):
    check(s)
    if (s.path/'small_candidate_frame.json').exists():
        raise GateError('候选库已冻结；新检索需要新研究版本')
    previous={'audit_a':'main','audit_b':'audit_a'}.get(group)
    if previous:
        s.frozen('small_discovery_'+previous+'.json')
    limit=s.config['bounded_search'][group]
    summaries=[]
    lo,hi=int(ts(s.config['video_publish_start'])),int(ts(s.config['t0']))
    for q in (q for q in s.config['queries'] if q['group']==group):
        hits,pages=[],[]
        try:
            seen=set()
            for pn in range(1,limit+1):
                env=api.get('search',dict(search_type='video',keyword=q['keyword'],order=q['order'],page=pn,
                         page_size=20,pubtime_begin_s=lo,pubtime_end_s=hi))
                d=payload(env)
                if any(type(d.get(k)) is not int or d[k]<0 for k in ('page','pagesize','numPages','numResults')):
                    raise GateError('bounded_search_schema_changed')
                if d['page']!=pn or d['pagesize']!=20:
                    raise GateError('bounded_pagination_contract_changed')
                values=d.get('result')
                if values is None and d['numPages']==d['numResults']==0:
                    values=[]
                if not isinstance(values,list) or len(values)>20:
                    raise GateError('bounded_result_list_invalid')
                if not values and d['numResults']>0 and pn<=d['numPages']:
                    raise GateError('bounded_empty_before_reported_end')
                additions=[]
                for rank,item in enumerate(values,1):
                    if item.get('type','video')!='video':
                        continue
                    bv=bvid(item.get('bvid'))
                    pub=item.get('pubdate')
                    if type(pub) is not int or not lo<=pub<=hi:
                        raise GateError('bounded_date_filter_failed')
                    hits.append(dict(bvid=bv,page=pn,rank=rank,duplicate=bv in seen,
                                     captured_at=env['captured_at'],response_hash=env['response_hash']))
                    seen.add(bv)
                    additions.append((bv,q['mode'],dict(title=re.sub('<[^>]*>','',item.get('title','')),
                                     aid=str(item.get('aid','')),published_at=str(pub))))
                s.candidates(additions)
                pages.append(dict(page=pn,numPages=d['numPages'],numResults=d['numResults'],
                                  returned=len(values),response_hash=env['response_hash'],captured_at=env['captured_at']))
                if pn>=max(1,d['numPages']):
                    break
            summaries.append(dict(query=q,status='bounded_complete',hits=hits,pages=pages,
                                  stop='fixed_depth_or_reported_end',full_search_enumerated=False))
        except GateError as exc:
            summaries.append(dict(query=q,status='incomplete',reason=str(exc),hits=hits,pages=pages))
            write_json(s.path/('small_discovery_'+group+'_FAILED.json'),dict(config_hash=s.config_hash,at=now(),queries=summaries))
            raise
        write_json(s.path/('small_discovery_'+group+'_progress.json'),dict(config_hash=s.config_hash,at=now(),queries=summaries))
    return seal(s,'small_discovery_'+group+'.json',dict(queries=summaries,
                scope='union_of_recorded_bounded_responses_not_all_search_results'))


def freeze_candidates(s):
    check(s)
    discoveries={g:s.frozen('small_discovery_'+g+'.json') for g in GROUPS}
    paths={}
    additions={}
    new_counts={}
    known={m:set() for m in MODES}
    for g in GROUPS:
        expected={q['id'] for q in s.config['queries'] if q['group']==g}
        actual={x['query']['id'] for x in discoveries[g]['queries'] if x['status']=='bounded_complete'}
        if actual!=expected:
            raise GateError('登记的有界查询未完成')
        new_counts[g]={m:0 for m in MODES}
        for q in discoveries[g]['queries']:
            m=q['query']['mode']
            for h in q['hits']:
                key=(h['bvid'],m)
                paths.setdefault(key,set()).add(g)
                if h['bvid'] not in known[m]:
                    known[m].add(h['bvid']);new_counts[g][m]+=1
    metadata=unique_map(read_csv(s.path/'video_review.csv'),('bvid','mode'))
    for key,found in paths.items():
        if key not in metadata:
            raise GateError('候选工作表删除了已返回的视频')
        additions[key]=dict(metadata[key],discovery_groups=sorted(found))
    # Historical unbounded hits remain in their old studies; they are not silently
    # merged into a new finite frame. Their known references form a separate audit.
    records=[additions[k] for k in sorted(additions)]
    frame=seal(s,'small_candidate_frame.json',dict(records=records,discovery_hashes={g:digest(d) for g,d in discoveries.items()},
               new_candidate_counts=new_counts,eligibility_fully_classified=False,
               coverage_sufficiency='not_proven',inference_scope='eligible_video_domain_within_this_frozen_candidate_set'))
    write_csv(s.path/'small_video_review.csv',[dict(r,decision='pending',final='no',reviewer='',reason='',period_evidence='',review_kind='') for r in records],VFIELDS)
    return frame


def draw_videos(s):
    check(s)
    f=s.frozen('small_candidate_frame.json')
    seed=secrets.token_hex(32)
    orders={m:permutation(sorted({r['bvid'] for r in f['records'] if r['mode']==m}),seed,m+':videos') for m in MODES}
    result=seal(s,'small_video_draw.json',dict(seed=seed,candidate_frame_hash=digest(f),orders=orders,
                generator='HMAC-SHA256-counter-rejection-Fisher-Yates-v1'))
    write_csv(s.path/'small_video_queue.csv',[dict(mode=m,bvid=bv,position=i,url='https://www.bilibili.com/video/'+bv+'/')
              for m in MODES for i,bv in enumerate(orders[m],1)],['mode','bvid','position','url'])
    return result


def video_progress(s):
    d=s.frozen('small_video_draw.json');f=s.frozen('small_candidate_frame.json')
    if d['candidate_frame_hash']!=digest(f):
        raise GateError('视频队列对应不同候选库')
    for m in MODES:
        ids=sorted({r['bvid'] for r in f['records'] if r['mode']==m})
        if permutation(ids,d['seed'],m+':videos')!=d['orders'][m]:
            raise GateError('视频随机队列无法重放')
    rows=unique_map(read_csv(s.path/'small_video_review.csv'),('bvid','mode'))
    if set(rows)!={(r['bvid'],r['mode']) for r in f['records']}:
        raise GateError('视频审核表增删了候选')
    result={}
    for m in MODES:
        accepted,prefix=[],[]
        next_bv=None
        for bv in d['orders'][m]:
            r=rows[(bv,m)]
            if r.get('final')!='yes' or r.get('decision') not in ('include','exclude'):
                next_bv=bv;break
            if not all(r.get(k) for k in ('reason','reviewer','review_kind')):
                raise GateError('视频定稿需要处理人、依据与核验类型')
            automatic=r['review_kind']=='deterministic_date_rule'
            if automatic:
                if r['decision']!='exclude' or not r.get('published_at','').isdigit() or ts(s.config['video_publish_start'])<=int(r['published_at'])<=ts(s.config['t0']):
                    raise GateError('日期自动排除的证据无效')
            elif r['review_kind'] not in ('human_final','human_ai_agreement'):
                raise GateError('视频内容不能由AI初判冒充人工定稿')
            if r['decision']=='include':
                if not all(r.get(k) for k in ('period_evidence','aid','primary_up','published_at','content_type')):
                    raise GateError('纳入来源缺少本期内容证据或元数据')
                identifier(r['aid']);identifier(r['primary_up'])
                if not ts(s.config['video_publish_start'])<=int(r['published_at'])<=ts(s.config['t0']):
                    raise GateError('纳入视频超出发布窗口')
                accepted.append(r)
            prefix.append(r)
            if len(accepted)==20:
                break
        ready=len(accepted)==20 or next_bv is None
        result[m]=dict(status='ready' if ready else 'pending_review',selected=accepted,prefix=prefix,
                       next_bvid=next_bv,census=ready and len(prefix)==len(d['orders'][m]))
    return result


def enrich_next(s,api,limit):
    check(s)
    if not 1<=limit<=20:
        raise GateError('单次最多读取20个下一顺序候选，不能全库抓详情')
    progress=video_progress(s)
    rows=read_csv(s.path/'small_video_review.csv')
    todo=[];starts={}
    draw=s.frozen('small_video_draw.json')
    for m in MODES:
        if progress[m]['status']=='ready':
            continue
        order=draw['orders'][m];start=order.index(progress[m]['next_bvid'])
        starts[m]=order[start:start+limit]
    for rank in range(limit):
        todo.extend(starts[m][rank] for m in MODES if m in starts and rank<len(starts[m]))
    fetched=0
    for bv in dict.fromkeys(todo):
        if fetched>=limit:break
        env=api.get('view',{'bvid':bv});d=payload(env)
        for r in rows:
            if r['bvid']==bv:
                r.update(aid=identifier(d.get('aid')),primary_up=identifier((d.get('owner') or {}).get('mid')),
                         published_at=str(d.get('pubdate','')),title=d.get('title',''),description=d.get('desc',''),
                         coauthors=';'.join(identifier(x['mid']) for x in d.get('staff') or []))
                if r['published_at'].isdigit() and not ts(s.config['video_publish_start'])<=int(r['published_at'])<=ts(s.config['t0']):
                    r.update(decision='exclude',final='yes',reason='超出确认的视频发布日期范围',reviewer='date_rule',review_kind='deterministic_date_rule')
        write_csv(s.path/'small_video_review.csv',rows,VFIELDS)
        fetched+=1
    return fetched


def lock_videos(s):
    check(s);p=video_progress(s)
    if any(x['status']!='ready' for x in p.values()):
        raise GateError('随机前缀仍有待核视频，不能跳过或换成易采来源')
    videos={}
    for m,x in p.items():
        for r in x['selected']:
            if r['bvid'] not in videos:
                videos[r['bvid']]=dict(r,domains=[])
            elif any(videos[r['bvid']].get(k)!=r.get(k) for k in ('aid','primary_up','published_at','coauthors')):
                raise GateError('同一视频跨副本的元数据冲突')
            videos[r['bvid']]['domains'].append(m)
    return seal(s,'small_video_selection.json',dict(video_draw_hash=digest(s.frozen('small_video_draw.json')),
                domains=p,videos=list(videos.values()),first_stage='SRS_of_eligible_domain_via_random_permutation_screening',
                first_stage_population_size='unknown_unless_candidate_pool_exhausted',
                first_stage_common_factor='cancels_for_within_mode_ratios_no_population_totals'))


def source_count_mismatch(reason):
    return (reason == 'root_rcount_vs_reply_count_mismatch'
            or re.fullmatch(r'root_plus_reply_count_mismatch:[0-9]+!=[0-9]+', reason) is not None)


def load_collection_resume(s, selection, name):
    """Reuse an immutable saved prefix without accepting its failed sources."""
    saved = s.frozen(name)
    collection, rows, observations = saved['collection'], saved['comments'], saved['observations']
    if (collection.get('config_hash') != s.config_hash
        or collection.get('selection_hash') != digest(selection)
        or collection.get('comments_hash') != digest(rows)
        or collection.get('observations_hash') != digest(observations)):
        raise GateError('resume_snapshot_hash_mismatch')
    if (digest(read_json(s.path/'small_collection.json')) != digest(collection)
        or digest(read_jsonl(s.path/'small_comments.jsonl')) != digest(rows)
        or digest(read_jsonl(s.path/'small_observations.jsonl')) != digest(observations)):
        raise GateError('resume_live_files_changed')
    states = collection['videos']
    if (not states or len(states) > len(selection['videos'])
        or [v['bvid'] for v in states] != [v['bvid'] for v in selection['videos'][:len(states)]]):
        raise GateError('resume_not_original_locked_prefix')
    allowed = {v['bvid']: v['state_hash'] for v in saved['known_holds']}
    failed = {v['bvid']: v for v in states if v['status'] != 'enumerated_pending_review'}
    if set(allowed) != set(failed):
        raise GateError('resume_hold_inventory_mismatch')
    for bv, state in failed.items():
        reason = state.get('reason', '')
        diagnosed_integrity = reason == 'missing_ancestor' or source_count_mismatch(reason)
        if (state['status'] != 'incomplete' or not diagnosed_integrity
            or allowed[bv] != digest(state)):
            raise GateError('resume_cannot_skip_access_or_undiagnosed_failure')
    byid = unique_map(rows, ('id',))
    known = {v['bvid'] for v in states}
    if any(r['bvid'] not in known for r in rows):
        raise GateError('resume_rows_outside_saved_prefix')
    for state in states:
        body = [r for r in rows if r['bvid'] == state['bvid']]
        if (len(body) != state['unique_count']
            or sum(r['level'] == 'root' for r in body) != state['root_count']
            or sum(r['level'] == 'reply' for r in body) != state['reply_count']):
            raise GateError('resume_source_body_count_mismatch')
    if any(o['bvid'] not in known or (o['id'],) not in byid
           or byid[(o['id'],)]['bvid'] != o['bvid'] for o in observations):
        raise GateError('resume_observation_outside_saved_prefix')
    return collection, rows, observations


def collect_selected(s,api,resume_checkpoint=None,continue_source_count_failures=False):
    check(s);selection=s.frozen('small_video_selection.json')
    if (s.path/'small_comment_frame.json').exists() or (s.path/'small_comment_draw.json').exists():
        raise GateError('评论框已冻结')
    allrows,states,observations={},[],[]
    context_failures=[]
    if resume_checkpoint is not None:
        prior, saved_rows, observations = load_collection_resume(s, selection, resume_checkpoint)
        states = list(prior['videos'])
        allrows = {r['id']: r for r in saved_rows}
        context_failures = [v['bvid'] for v in states if v['status'] != 'enumerated_pending_review']
        s.event('collection_resume_saved_prefix', checkpoint=resume_checkpoint,
                sources_retained=len(states), known_holds=context_failures,
                statistics_remain_blocked=bool(context_failures))
    if not selection['videos']:
        write_jsonl(s.path/'small_comments.jsonl',[]);write_jsonl(s.path/'small_observations.jsonl',[])
        write_json(s.path/'small_collection.json',dict(config_hash=s.config_hash,selection_hash=digest(selection),videos=[],comments_hash=digest([]),observations_hash=digest([])))
    for video in selection['videos'][len(states):]:
        video_api = api.for_video(video) if hasattr(api, 'for_video') else api
        status,rows,obs=collect_video(s,video_api,video)
        states.append(status);observations.extend(obs)
        for r in rows:
            if r['id'] in allrows and allrows[r['id']]['bvid']!=r['bvid']:
                raise GateError('跨视频评论ID冲突')
            allrows[r['id']]=r
        values=sorted(allrows.values(),key=lambda r:r['id'])
        write_jsonl(s.path/'small_comments.jsonl',values)
        write_jsonl(s.path/'small_observations.jsonl',observations)
        write_json(s.path/'small_collection.json',dict(config_hash=s.config_hash,selection_hash=digest(selection),
                   videos=states,comments_hash=digest(values),observations_hash=digest(observations)))
        if status['status']!='enumerated_pending_review':
            # These failures stay incomplete and block every statistical gate.
            # Explicit execution policy may continue independent sources after
            # source-count discrepancies. Access/paging/schema failures stop.
            reason = status.get('reason', '')
            if reason == 'missing_ancestor' or (continue_source_count_failures and source_count_mismatch(reason)):
                context_failures.append(video['bvid'])
                s.event('source_integrity_hold_collection_continues', bvid=video['bvid'],
                        reason=reason, statistics_remain_blocked=True)
                continue
            raise GateError('入选视频未完整枚举；保留失败，不换来源、不从热评抽10条')
    path=s.path/'small_collection_review.csv'
    if not path.exists():
        write_csv(path,[dict(bvid=v['bvid'],status='pending',final='no') for v in selection['videos']],RFIELDS)
    if context_failures:
        raise GateError('既有未通过来源或缺失父评论仍待解决；其余来源采集已保存，但不能冻结统计清单')
    return states


def freeze_comments(s):
    check(s);selection=s.frozen('small_video_selection.json')
    c=read_json(s.path/'small_collection.json')
    if c['config_hash']!=s.config_hash or c['selection_hash']!=digest(selection):
        raise GateError('采集配置或来源清单不一致')
    context=load_rule(s,selection,c)
    states=unique_map(c['videos'],('bvid',))
    if set(states)!={(v['bvid'],) for v in selection['videos']} or any(not source_eligible(context,x) for x in states.values()):
        raise GateError('入选来源尚未全部采集完整')
    reviews=unique_map(read_csv(s.path/'small_collection_review.csv'),('bvid',))
    if set(reviews)!=set(states) or any(r.get('status')!='accepted' or r.get('final')!='yes' or not all(r.get(k) for k in ('count_semantics_evidence','reconciliation','pagination_evidence','reviewer')) for r in reviews.values()):
        raise GateError('需要逐视频核验数量口径、根/回复终点与差额')
    rows=read_jsonl(s.path/'small_comments.jsonl');obs=read_jsonl(s.path/'small_observations.jsonl')
    if digest(rows)!=c['comments_hash'] or digest(obs)!=c['observations_hash']:
        raise GateError('采集正文或观测记录已变化')
    byid=unique_map(rows,('id',));selected={v['bvid'] for v in selection['videos']}
    for (bv,),state in states.items():
        actual=[r for r in rows if r['bvid']==bv]
        if len(actual)!=state['unique_count'] or sum(r['level']=='root' for r in actual)!=state['root_count'] or sum(r['level']=='reply' for r in actual)!=state['reply_count']:
            raise GateError('正文根/回复数量与采集状态不一致')
    for r in rows:
        identifier(r['id'])
        if r['bvid'] not in selected:
            raise GateError('评论来自未入选视频')
    annotations=ancestry_annotations(rows,allow_missing=context is not None)
    if context:
        expected={i for v in context['sources'].values() for i in v['ancestor_affected_descendant_IDs']}
        if set(annotations)!=expected:
            raise GateError('缺失语境标记与独立审计不一致')
    frames={m:{} for m in MODES}
    for m,d in selection['domains'].items():
        for video in d['selected']:
            frames[m][video['bvid']]=sorted(r['id'] for r in rows if r['bvid']==video['bvid'] and ts(s.config['periods'][m]['start'])<=r['ctime']<=ts(s.config['t0']))
    return seal(s,'small_comment_frame.json',dict(selection_hash=digest(selection),collection=c,collection_reviews=list(reviews.values()),
                comments=rows,frames=frames,scope='complete_window_ID_frames_only_for_randomly_selected_videos',
                context_annotations=annotations,context_policy=context['rule'] if context else None,
                context_integrity_audit_hash=digest(context['audit']) if context else None))


def freeze_codebook(s):
    check(s);cb=read_json(s.path/'codebook.json')
    if not all(cb.get(k) for k in ('version','relevance_rules','context_rules','examples','reviewer')):
        raise GateError('代码本需明确相关性、语境、例子及人工核定人')
    if (s.path/'small_context_rule_decision_002.json').exists() and not cb.get('uncertainty_rules'):
        raise GateError('修订后的代码本需说明相关性不明与主题不明及其分母处理')
    themes=cb.get('themes',[]);ids=[t.get('id') for t in themes]
    if not ids or len(set(ids))!=len(ids) or any(not all(t.get(k) for k in ('id','definition','include','exclude')) for t in themes):
        raise GateError('主题定义不完整或重复')
    if 'other_current_experience' not in ids:
        raise GateError('代码本需要其他本期体验类别')
    review=cb.get('exploration_review',{})
    if review.get('status')!='limited' or not all(review.get(k) for k in ('evidence','reviewer')):
        raise GateError('本固定小预算版本如实登记limited，不冒称通过原主题饱和门槛')
    return seal(s,'small_codebook.json',dict(codebook=cb,qualitative_status=qual_status(s)))


def draw_comments(s):
    check(s);f=s.frozen('small_comment_frame.json');cb=s.frozen('small_codebook.json')
    seed=secrets.token_hex(32);samples={};materials=[]
    lookup={r['id']:r for r in f['comments']}
    for mode,videos in f['frames'].items():
        samples[mode]={}
        for bv,ids in videos.items():
            chosen=permutation(ids,seed,mode+':comments:'+bv)[:10]
            samples[mode][bv]=dict(N=len(ids),m=len(chosen),ids=chosen,relative_weight=len(ids)/len(chosen) if chosen else None)
            for i in chosen:
                r=lookup[i]
                gap=f.get('context_annotations',{}).get(i,{})
                materials.append(dict(mode=mode,id=i,bvid=bv,text=r['text'],root_id=r['root_id'],parent_id=r['parent_id'],level=r['level'],
                                      ctime=r['ctime'],author_role=r['author_role'],relative_weight=samples[mode][bv]['relative_weight'],
                                      context_gap=bool(gap),missing_ancestor_id=gap.get('first_missing_ancestor_id','')))
    d=seal(s,'small_comment_draw.json',dict(seed=seed,comment_frame_hash=digest(f),codebook_hash=digest(cb),samples=samples,
                unit='raw_window_utterance_no_relevance_replacement',generator='HMAC-SHA256-counter-rejection-Fisher-Yates-v1'))
    write_csv(s.path/'small_main_material.csv',materials,['mode','id','bvid','text','root_id','parent_id','level','ctime','author_role','relative_weight','context_gap','missing_ancestor_id'])
    write_csv(s.path/'small_coding.csv',[dict(mode=r['mode'],id=r['id'],relevance='pending',final='no',
        theme_status='pending' if f.get('context_policy') else 'known',
        notes='缺失祖先正文；核对自身表达与已存语境，不能补抽' if r['context_gap'] else '') for r in materials],CFIELDS)
    return d


def load_comments(s):
    f=s.frozen('small_comment_frame.json');d=s.frozen('small_comment_draw.json');cb=s.frozen('small_codebook.json')
    if d['comment_frame_hash']!=digest(f) or d['codebook_hash']!=digest(cb):
        raise GateError('评论框或代码本变更')
    if set(d['samples'])!=set(MODES):
        raise GateError('抽样副本缺失')
    for mode,videos in f['frames'].items():
        if set(videos)!=set(d['samples'][mode]):raise GateError('抽样视频增删')
        for bv,ids in videos.items():
            x=d['samples'][mode][bv];chosen=permutation(ids,d['seed'],mode+':comments:'+bv)[:10]
            weight=len(ids)/len(chosen) if chosen else None
            if x!=dict(N=len(ids),m=len(chosen),ids=chosen,relative_weight=weight):
                raise GateError('评论抽取、窗口数量或权重无法重放')
    return f,d,cb


def codes(s,rows=None):
    f,d,cb=load_comments(s)
    rows=read_csv(s.path/'small_coding.csv') if rows is None else rows
    mapping=unique_map(rows,('mode','id'))
    expected={(m,i) for m,vs in d['samples'].items() for v in vs.values() for i in v['ids']}
    if set(mapping)!=expected:raise GateError('编码表增删了随机抽中ID')
    allowed={x['id'] for x in cb['codebook']['themes']}
    for r in rows:
        if r.get('final')!='yes' or r.get('relevance') not in ('related','irrelevant','unknown') or not all(r.get(k) for k in ('reason','evidence','reviewer')) or r.get('context_status') not in ('checked','checked_with_limits','unreadable_recorded'):
            raise GateError('随机原始发言尚未全部定稿')
        if r.get('review_kind') not in ('human_final','human_ai_agreement'):
            raise GateError('AI初判不能冒充人工定稿')
        theme_status=r.get('theme_status') or ('pending' if f.get('context_policy') else 'known')
        if theme_status not in ('known','unknown'):
            raise GateError('需核定主题可判定性，不能把不明当作没有主题')
        if theme_status=='unknown' and (r.get('themes') or r.get('self_experience_themes')):
            raise GateError('主题不明项不能计入已知主题')
        if r['id'] in f.get('context_annotations',{}) and r['context_status']=='checked':
            raise GateError('缺父回复需记录语境限制及判断依据')
        for field in ('themes','self_experience_themes'):
            if not set(filter(None,r.get(field,'').split(';'))).issubset(allowed):raise GateError('主题不在冻结代码本')
        if not set(filter(None,r.get('self_experience_themes','').split(';'))).issubset(set(filter(None,r.get('themes','').split(';')))):
            raise GateError('本人经历主题须也是该发言提及主题')
        if r['relevance']!='related' and (r.get('themes') or r.get('self_experience_themes')):
            raise GateError('不相关或不明发言不能计入主题')
    return mapping


def lock_coding(s,reason=None):
    check(s);mapping=codes(s);f,d,cb=load_comments(s)
    prior=sorted(s.path.glob('small_coding_locked_*.json'))
    if prior and not reason:raise GateError('编码已锁定；修订需填写原因，不更换随机样本')
    version=len(prior)+1;name=f'small_coding_locked_{version:03}.json'
    rows=sorted(mapping.values(),key=lambda r:(r['mode'],r['id']))
    snapshot=seal(s,name,dict(rows=rows,draw_hash=digest(d),codebook_hash=digest(cb),revision_reason=reason,
                  prior_hash=digest(s.frozen(prior[-1].name)) if prior else None))
    write_json(s.path/'small_coding_current.json',dict(file=name,hash=digest(snapshot)))
    blind=[];materials=[];lookup={r['id']:r for r in f['comments']}
    for m in MODES:
        ids=sorted(i for mode,i in mapping if mode==m)
        for i in permutation(ids,d['seed'],m+':blind')[:30]:
            blind.append(dict(mode=m,id=i,final='no'))
            r=lookup[i];materials.append(dict(mode=m,id=i,text=r['text'],bvid=r['bvid'],root_id=r['root_id'],parent_id=r['parent_id']))
    write_csv(s.path/f'small_blind_review_{version:03}.csv',blind,AFIELDS)
    write_csv(s.path/f'small_blind_material_{version:03}.csv',materials,['mode','id','bvid','text','root_id','parent_id'])
    return dict(version=version,blind_n=len(blind))


def adjudicated(s,require_audit=True):
    current=read_json(s.path/'small_coding_current.json');locked=s.frozen(current['file'])
    if current['file']!=sorted(s.path.glob('small_coding_locked_*.json'))[-1].name:raise GateError('当前编码指针不能退回旧快照冒充最新修订')
    if digest(locked)!=current['hash']:raise GateError('编码快照指针哈希不一致')
    live=sorted(codes(s).values(),key=lambda r:(r['mode'],r['id']))
    if digest(live)!=digest(locked['rows']):raise GateError('编码锁定后变化；需带原因重新锁定并复核')
    f,d,cb=load_comments(s)
    if locked['draw_hash']!=digest(d) or locked['codebook_hash']!=digest(cb):raise GateError('编码快照对应不同抽样/代码本')
    mapping={(r['mode'],r['id']):dict(r) for r in live}
    version=int(current['file'].rsplit('_',1)[-1].split('.')[0])
    audit=read_csv(s.path/f'small_blind_review_{version:03}.csv')
    aud=unique_map(audit,('mode','id'))
    expected={(m,i) for m in MODES for i in permutation(sorted(i for mode,i in mapping if mode==m),d['seed'],m+':blind')[:30]}
    if set(aud)!=expected:raise GateError('盲复核增删了固定随机ID')
    counts={m:dict(n=0,disagreements=0,corrections=0,pending=0,review_kinds=[]) for m in MODES}
    for key,r in aud.items():
        m=key[0];counts[m]['n']+=1
        if r.get('final')!='yes' or r.get('review_kind') not in ('human_ai_agreement','same_person_blind_recode','independent_human_coders') or not all(r.get(k) for k in ('reviewer','resolution')) or r.get('context_status') not in ('checked','checked_with_limits','unreadable_recorded') or any(r.get(k)!='yes' for k in ('date_checked','role_checked')):
            counts[m]['pending']+=1;continue
        counts[m]['review_kinds'].append(r['review_kind'])
        original=mapping[key]
        allowed={x['id'] for x in cb['codebook']['themes']}
        if r.get('relevance') not in ('related','irrelevant','unknown') or any(not set(filter(None,r.get(k,'').split(';'))).issubset(allowed) for k in ('themes','self_experience_themes')):
            counts[m]['pending']+=1;continue
        if ((f.get('context_policy') and r.get('theme_status') not in ('known','unknown'))
                or (r.get('theme_status')=='unknown' and (r.get('themes') or r.get('self_experience_themes')))):
            counts[m]['pending']+=1;continue
        comparable=lambda row:(row.get('relevance'),row.get('theme_status') or 'known',set(filter(None,row.get('themes','').split(';'))),set(filter(None,row.get('self_experience_themes','').split(';'))))
        if comparable(r)!=comparable(original):
            counts[m]['disagreements']+=1
            resolved={k:original.get(k,'') for k in CFIELDS}
            resolved.update(relevance=r.get('resolved_relevance',''),themes=r.get('resolved_themes',''),self_experience_themes=r.get('resolved_self_experience_themes',''),
                            theme_status=r.get('resolved_theme_status') or original.get('theme_status') or 'known')
            try:codes(s,[resolved if (x['mode'],x['id'])==key else x for x in live])
            except GateError:counts[m]['pending']+=1;continue
            if comparable(resolved)!=comparable(original):counts[m]['corrections']+=1
            resolved['notes']=(resolved.get('notes','')+'；复核裁决人：'+r['reviewer']+'；依据：'+r['resolution']).strip('；')
            mapping[key]=resolved
    for m,x in counts.items():
        x['correction_rate']=x['corrections']/x['n'] if x['n'] else None
        x['agreement_rate']=1-x['disagreements']/x['n'] if x['n'] else None
        x['pass']=x['pending']==0 and (not x['n'] or (x['agreement_rate']>=.90 and x['correction_rate']<=.05))
        x['review_kinds']=sorted(set(x['review_kinds']))
    if require_audit and not all(x['pass'] for x in counts.values()):raise GateError('盲复核未完成或修正率超过5%；需回查受影响编码')
    return mapping,dict(domains=counts,rows=audit,locked_hash=digest(locked))


# Two-sided t critical values for df1..30; no runtime numerical dependency.
T95=[None,12.706205,4.302653,3.182446,2.776445,2.570582,2.446912,2.364624,2.306004,2.262157,2.228139,
     2.200985,2.178813,2.160369,2.144787,2.131450,2.119905,2.109816,2.100922,2.093024,2.085963,
     2.079614,2.073873,2.068658,2.063899,2.059539,2.055529,2.051831,2.048407,2.045230,2.042272]


def ratio_estimate(clusters,census=False):
    """Taylor ratio; ultimate-video-cluster WR approximation (omits video FPC).

    Each record has raw N and sampled y/r indicators. For a video census, use
    within-video SRS variance instead. Boundary/zero-variance samples do not prove
    absence: return a vacuous interval unless both stages are actual censuses.
    """
    totals=[];within=0.;df_within=0
    for c in clusters:
        N=c['N'];values=c['values'];m=len(values)
        if (N==0 and m) or (N>0 and not 1<=m<=N):raise GateError('窗口总数或抽样数量不合法')
        w=N/m if m else 0
        totals.append((sum(x['y'] for x in values)*w,sum(x['r'] for x in values)*w))
    A=sum(a for a,d in totals);D=sum(d for a,d in totals)
    if D<=0:return dict(proportion=None,interval95=None,precision_target_met=False,reason='no_observed_related_denominator')
    p=A/D
    all_comments_census=all(len(c['values'])==c['N'] for c in clusters)
    if census and all_comments_census:
        return dict(proportion=p,interval95=None,sampling_variance=0,precision_target_met=True,reason='finite_frame_census_no_sampling_error')
    if census:
        for c in clusters:
            N,m=c['N'],len(c['values'])
            if m>1 and m<N:
                z=[x['y']-p*x['r'] for x in c['values']];mean=sum(z)/m
                within+=N*N*(1-m/N)*sum((v-mean)**2 for v in z)/(m*(m-1))
                df_within+=m-1
        var=within/(D*D);df=df_within;method='video_census_within_video_SRS_Taylor'
    else:
        k=len(clusters);contributing=sum(d>0 for a,d in totals)
        df=min(k-1,contributing-1)
        var=k/(k-1)*sum((a-p*d)**2 for a,d in totals)/(D*D) if k>1 else 0
        method='ultimate_video_cluster_Taylor_WR_approx_no_video_FPC'
    if var<=0 or df<1 or p in (0.,1.):
        return dict(proportion=p,interval95=[0.,1.],precision_target_met=False,reason='sparse_or_zero_variance_not_evidence_of_absence',method=method)
    critical=T95[min(df,30)] # df>30 uses the larger df30 critical value conservatively.
    half=critical*math.sqrt(var)
    return dict(proportion=p,interval95=[max(0.,p-half),min(1.,p+half)],unclipped_halfwidth=half,
                sampling_variance=var,df=df,method=method,precision_target_met=half<=.10,
                note='nominal_approximate_pointwise_interval_excludes_coverage_and_coding_bias')


def estimates(s,draft=False):
    check(s);f,d,cb=load_comments(s);selection=s.frozen('small_video_selection.json')
    if draft:
        mapping=codes(s);audit={'status':'not_required_for_draft'}
    else:
        mapping,audit=adjudicated(s)
    lookup={r['id']:r for r in f['comments']};result={}
    themes=[t['id'] for t in cb['codebook']['themes']]
    for mode,videos in d['samples'].items():
        records=[];unknown,related,related_all,theme_unknown=0.,0.,0.,0.
        for bv,v in videos.items():
            for i in v['ids']:
                code=mapping[(mode,i)];w=v['relative_weight']
                records.append(dict(bvid=bv,id=i,w=w,code=code,body=lookup[i]))
                uncertain_theme=code['relevance']=='related' and code.get('theme_status')=='unknown'
                unknown+=w*(code['relevance']=='unknown' or uncertain_theme)
                related+=w*(code['relevance']=='related' and not uncertain_theme)
                related_all+=w*(code['relevance']=='related');theme_unknown+=w*uncertain_theme
        metrics={}
        for field in ('themes','self_experience_themes'):
            metrics[field]={}
            for theme in themes:
                clusters=[];A=0.
                for bv,v in videos.items():
                    values=[]
                    for i in v['ids']:
                        code=mapping[(mode,i)];r=int(code['relevance']=='related' and code.get('theme_status')!='unknown')
                        y=int(bool(r) and theme in code.get(field,'').split(';'))
                        values.append(dict(y=y,r=r));A+=(v['relative_weight'] or 0)*y
                    clusters.append(dict(N=v['N'],values=values))
                estimate=ratio_estimate(clusters,selection['domains'][mode]['census'])
                estimate['unknown_relevance_bounds']=[A/(related+unknown),(A+unknown)/(related+unknown)] if related+unknown else None
                estimate['unknown_content_bounds']=estimate['unknown_relevance_bounds']
                estimate['point_estimate_scope']='related_utterances_with_determinate_theme_coding'
                metrics[field][theme]=estimate
        def points(items):
            known=[x for x in items if x['code']['relevance']=='related' and x['code'].get('theme_status')!='unknown']
            denominator=sum(x['w'] for x in known)
            return {t:(sum(x['w'] for x in known if t in x['code'].get('themes','').split(';'))/denominator if denominator else None) for t in themes}
        up={v['bvid']:v['primary_up'] for v in selection['videos']}
        contribution=Counter();threads=Counter()
        for r in records:
            if r['code']['relevance']=='related':contribution[up[r['bvid']]]+=r['w'];threads[r['body']['root_id']]+=r['w']
        largest_up=contribution.most_common(1)[0][0] if contribution else None
        largest_thread=threads.most_common(1)[0][0] if threads else None
        sensitivity=dict(exclude_video_authors=points([r for r in records if r['body']['author_role']=='audience']),
            remove_largest_sampled_uploader=points([r for r in records if up[r['bvid']]!=largest_up]),
            remove_largest_sampled_thread=points([r for r in records if r['body']['root_id']!=largest_thread]),
            roots_only=points([r for r in records if r['body']['level']=='root']),replies_only=points([r for r in records if r['body']['level']=='reply']),
            leave_one_video_out={bv:points([r for r in records if r['bvid']!=bv]) for bv in videos})
        result[mode]=dict(selected_videos=len(videos),different_uploaders=len({up[b] for b in videos}),raw_sample_n=len(records),
             window_IDs_in_selected_videos=sum(v['N'] for v in videos.values()),relative_weighted_related_denominator=related,
             relative_weighted_known_related_total=related_all,relative_weighted_theme_unknown=theme_unknown,
             observed_content_types=dict(Counter(r['content_type'] for r in selection['domains'][mode]['selected'])),
             zero_window_videos=sum(v['N']==0 for v in videos.values()),raw_root_reply_counts=dict(Counter(r['body']['level'] for r in records)),
             related_sample_n=sum(r['code']['relevance']=='related' for r in records),unknown_sample_n=sum(r['code']['relevance']=='unknown' for r in records),
             theme_unknown_sample_n=sum(r['code']['relevance']=='related' and r['code'].get('theme_status')=='unknown' for r in records),
             unknown_content_sample_n=sum(r['code']['relevance']=='unknown' or (r['code']['relevance']=='related' and r['code'].get('theme_status')=='unknown') for r in records),
             weighted_unknown_share=unknown/(related+unknown) if related+unknown else None,
             uncertainty_risk_flag=unknown/(related+unknown)>.10 if related+unknown else True,
             metrics=metrics,sensitivity=sensitivity,sensitivity_scope='diagnostics_with_changed_domains_not_replacements_for_main_estimate')
    output=dict(config_hash=s.config_hash,at=now(),status='DRAFT' if draft else 'AUDITED_FINITE_FRAME_ESTIMATES',domains=result,
                audit=audit,source_hash=source_hash(),draw_hash=digest(d),codebook_hash=digest(cb),coding_hash=digest(list(mapping.values())),
                scope='eligible_domain_of_frozen_bounded_candidate_set_not_Bilibili_or_independent_players',
                coverage_sufficiency='not_proven',thematic_saturation='not_claimed',precision_target=.10)
    write_json(s.path/('small_estimates_DRAFT.json' if draft else 'small_estimates.json'),output)
    return output


def qual_queue(s,mode,bv,role):
    check(s);f=s.frozen('small_comment_frame.json');selection=s.frozen('small_video_selection.json')
    if bv not in f['frames'][mode] or role not in ('development','validation'):
        raise GateError('补查从已入选且完整枚举的视频中选择，角色必须明确')
    if (s.path/'small_codebook.json').exists():raise GateError('代码本已冻结；新主题只能另作探索，不改开发/验证记录')
    path=s.path/'small_qual_registry.json'
    if not (s.path/'small_qual_seed.json').exists():seal(s,'small_qual_seed.json',dict(seed=secrets.token_hex(32),comment_frame_hash=digest(f)))
    seed=s.frozen('small_qual_seed.json')
    if seed['comment_frame_hash']!=digest(f):raise GateError('定性随机种子对应不同评论框')
    qual_status(s) # validates every earlier fixed selection before adding another
    registry=read_json(path) if path.exists() else dict(items=[])
    videos={v['bvid']:v for v in selection['videos']};up=videos[bv]['primary_up']
    prior=[x for x in registry['items'] if x['mode']==mode]
    if any(x['bvid']==bv or x['primary_up']==up for x in prior):raise GateError('定性来源重复UP或已用于开发，不能冒充新验证来源')
    if role=='validation' and (sum(x['role']=='development' for x in prior)<6 or any(x.get('final')!='yes' for x in prior if x['role']=='development')):
        raise GateError('先完成6个开发来源的审核，再启用未使用的验证来源')
    if sum(x['role']==role for x in prior)>=({'development':6,'validation':3}[role]):raise GateError('已达到登记的定性补查预算')
    if role=='development' and any(x['role']=='validation' for x in prior):raise GateError('验证后不能继续开发并宣称仍是未使用来源')
    ids=permutation(f['frames'][mode][bv],seed['seed'],mode+':qual:'+bv)[:10]
    fixed=dict(mode=mode,bvid=bv,primary_up=up,role=role,ids=ids)
    seal(s,'small_qual_draw_'+mode+'_'+bv+'.json',fixed)
    item=dict(fixed,new_information=None,evidence=None,reviewer=None,review_kind=None,final='no')
    registry['items'].append(item);write_json(path,registry)
    lookup={r['id']:r for r in f['comments']}
    write_csv(s.path/('small_qual_'+mode+'_'+bv+'.csv'),[dict(id=i,text=lookup[i]['text'],root_id=lookup[i]['root_id'],parent_id=lookup[i]['parent_id']) for i in ids],['id','text','root_id','parent_id'])
    return item


def qual_status(s):
    fixed=[s.frozen(p.name) for p in s.path.glob('small_qual_draw_*.json')]
    p=s.path/'small_qual_registry.json';rows=read_json(p)['items'] if p.exists() else []
    expected={(x['mode'],x['bvid']):x for x in fixed};actual=unique_map(rows,('mode','bvid'))
    if set(expected)!=set(actual):raise GateError('定性记录增删了已冻结的来源')
    result={}
    for key,x in expected.items():
        if any(actual[key].get(k)!=x[k] for k in ('mode','bvid','primary_up','role','ids')):raise GateError('定性来源/角色/随机ID被更换')
    for m in MODES:
        items=[r for r in rows if r['mode']==m]
        if len({r['primary_up'] for r in items})!=len(items):raise GateError('定性开发和验证复用了UP')
        completed=lambda r:r.get('final')=='yes' and r.get('review_kind') in ('human_final','human_ai_agreement') and all(r.get(k) for k in ('reviewer','evidence')) and r.get('new_information') in ('none','problem','condition','counterexample','multiple')
        dev=[r for r in items if r['role']=='development'];val=[r for r in items if r['role']=='validation']
        result[m]=dict(development=len(dev),validation=len(val),reviewed=sum(completed(r) for r in items),
                      budget_review_complete=len(dev)==6 and len(val)==3 and all(completed(r) for r in items),
                      validation_new_information=any(r.get('new_information') not in (None,'none') for r in val),
                      original_thematic_saturation_gate='not_claimed')
    return result
