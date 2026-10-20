"""A finite saved-corpus sample, never a claim of complete Bilibili coverage.

Original acquisition failures remain failures. This protocol conditions on the
fixed 60 sources and their already normalized, provenance-audited saved bodies.
"""
from collections import Counter
import hashlib
import secrets

from . import small
from .context_policy import ancestry_annotations
from .core import GateError, MODES, NAMES, digest, permutation, read_csv, read_json, read_jsonl, ts, write_csv, write_json


PROTOCOL='captured-snapshot-v1'
PREFIX='small_snapshot_'
# These findings limit coverage, not the identity of each included saved body.
COVERAGE_FINDINGS={'missing_ancestor','global_server_total_disagrees','thread_inventory_incomplete',
                   'thread_declared_count_disagrees','cached_preview_IDs_not_in_inventory',
                   'reply_page_count_disagrees','root_terminal_missing','reply_terminal_missing'}
MASTER_FILES=('small_collection.json','small_comments.jsonl','small_observations.jsonl')


def master_hashes(s):
    return {n:hashlib.sha256((s.path/n).read_bytes()).hexdigest() for n in MASTER_FILES}


def build_frame(config,selection,collection,rows,observations,audit):
    if (collection['selection_hash']!=digest(selection) or collection['comments_hash']!=digest(rows)
            or collection['observations_hash']!=digest(observations)
            or audit['collection_hash']!=digest(collection) or audit['selection_hash']!=digest(selection)
            or audit['comments_hash']!=digest(rows) or audit['observations_hash']!=digest(observations)):
        raise GateError('saved_snapshot_input_hash_mismatch')
    if audit['summary'].get('corrupt_cache_files'):
        raise GateError('saved_snapshot_corrupt_cache')
    selected={v['bvid']:v for v in selection['videos']}
    states={v['bvid']:v for v in collection['videos']}
    findings={v['bvid']:v for v in audit['sources']}
    if (len(selected)!=len(selection['videos']) or len(states)!=len(collection['videos'])
            or len(findings)!=len(audit['sources']) or set(selected)!=set(states) or set(selected)!=set(findings)):
        raise GateError('saved_snapshot_source_inventory_mismatch')
    if len({r['id'] for r in rows})!=len(rows):
        raise GateError('saved_snapshot_duplicate_ID')
    counts=Counter(r['bvid'] for r in rows)
    source_report=[]
    for bv,state in states.items():
        source=findings[bv]
        fatal=set(source['errors'])-COVERAGE_FINDINGS
        if fatal:
            raise GateError('saved_snapshot_body_or_provenance_failure:'+bv+':'+','.join(sorted(fatal)))
        if counts[bv]!=state['unique_count'] or counts[bv]!=source['unique_IDs']:
            raise GateError('saved_snapshot_saved_count_mismatch')
        actual=[r for r in rows if r['bvid']==bv]
        if (sum(r['level']=='root' for r in actual)!=state['root_count']
                or sum(r['level']=='reply' for r in actual)!=state['reply_count']):
            raise GateError('saved_snapshot_saved_role_count_mismatch')
        source_report.append(dict(bvid=bv,original_acquisition_status=state['status'],
            original_reason=state.get('reason'),original_audit_findings=source['errors'],
            saved_IDs=counts[bv],server_total_at_original_capture=source.get('server_total'),
            complete_accessible_enumeration_claimed=False,retained_in_saved_corpus=True))
    for r in rows:
        if (r['bvid'] not in selected or not isinstance(r['id'],str) or not r['id'].isdigit()
                or not isinstance(r['ctime'],int) or isinstance(r['ctime'],bool)
                or hashlib.sha256(r['text'].encode()).hexdigest()!=r['text_hash']):
            raise GateError('saved_snapshot_invalid_body')
    annotations=ancestry_annotations(rows,True)
    frames={m:{} for m in MODES}
    for mode in MODES:
        for video in selection['domains'][mode]['selected']:
            bv=video['bvid']
            if bv not in selected or bv in frames[mode]:
                raise GateError('saved_snapshot_domain_inventory_mismatch')
            frames[mode][bv]=sorted(r['id'] for r in rows if r['bvid']==bv
                and ts(config['periods'][mode]['start'])<=r['ctime']<=ts(config['t0']))
    expected={i for a in audit['sources'] for i in a['ancestor_affected_descendant_IDs']}
    if set(annotations)!=expected:
        raise GateError('saved_snapshot_context_audit_mismatch')
    return dict(protocol=PROTOCOL,scope='fixed_selected_videos_normalized_saved_bodies_in_original_windows_only',
        selection_hash=digest(selection),collection_hash=digest(collection),comments_hash=digest(rows),
        observations_hash=digest(observations),audit_hash=digest(audit),frames=frames,comments=rows,
        source_dispositions=source_report,context_annotations=annotations,
        old_enumeration_acceptance_unchanged=True,first_stage_conditioned_on_fixed_sources=True,
        broader_video_domain_inference_allowed=False,deleted_or_unsaved_bodies_in_frame=False,
        saved_preview_bodies_not_normalized_to_master_excluded=True,
        inferential_method='all_fixed_sources_are_censused_within_source_SRS_without_replacement',
        variance_method='within_video_SRS_Taylor_for_fixed_saved_corpus_not_original_candidate_population')


def draw_from_frame(frame,seed):
    samples={}
    for mode,videos in frame['frames'].items():
        samples[mode]={}
        for bv,ids in videos.items():
            chosen=permutation(ids,seed,mode+':saved_snapshot:'+bv)[:10]
            N,m=len(ids),len(chosen)
            samples[mode][bv]=dict(N=N,m=m,ids=chosen,inclusion_probability=m/N if N else None,
                                  relative_weight=N/m if m else None)
    return dict(protocol=PROTOCOL,seed=seed,frame_hash=digest(frame),samples=samples,
        generator='HMAC-SHA256-counter-rejection-Fisher-Yates-v1',
        unit='saved_normalized_window_utterance_ID_without_relevance_screening',
        status='TECHNICAL_RANDOM_SAMPLE_FROZEN_CODING_PENDING',
        replacements_allowed=False,theme_coding_completed=False,
        coding_order_amendment='sample_IDs_frozen_before_final_codebook; no_redraw_after_coding',
        scope=frame['scope'],broader_video_domain_inference_allowed=False)


def verify_draw(frame,draw):
    replay=draw_from_frame(frame,draw['seed'])
    # Immutable-file metadata is deliberately outside the replay payload.
    if any(draw.get(k)!=v for k,v in replay.items()):
        raise GateError('saved_snapshot_draw_not_replayable')


def export_materials(s,frame,draw,selection,prefix='small_snapshot_',baseline_draw=None):
    lookup={r['id']:r for r in frame['comments']}
    videos={v['bvid']:v for v in selection['videos']}
    material=[];context_rows=[];source_rows=[]
    for mode,items in draw['samples'].items():
        for bv,sample in items.items():
            v=videos[bv]
            source_rows.append(dict(mode=mode,副本=NAMES[mode],bvid=bv,title=v['title'],N=sample['N'],m=sample['m'],
                weight=sample['relative_weight'],url='https://www.bilibili.com/video/'+bv+'/'))
            for ident in sample['ids']:
                r=lookup[ident];gap=frame['context_annotations'].get(ident,{})
                record=dict(mode=mode,副本=NAMES[mode],id=ident,bvid=bv,title=v['title'],text=r['text'],
                    ctime_bjt=r['ctime_bjt'],level=r['level'],root_id=r['root_id'],parent_id=r['parent_id'],
                    author_role=r['author_role'],N=sample['N'],m=sample['m'],relative_weight=sample['relative_weight'],
                    inclusion_probability=sample['inclusion_probability'],context_gap=bool(gap),
                    missing_ancestor_id=gap.get('first_missing_ancestor_id',''),url='https://www.bilibili.com/video/'+bv+'/')
                if baseline_draw is not None:
                    base=baseline_draw['samples'][mode][bv]
                    record.update(sample_phase='retained' if ident in base['ids'] else 'supplement',
                                  baseline_m=base['m'],added_m=sample['m']-base['m'])
                material.append(record)
                parent=r['parent_id'];seen={ident};depth=0
                while parent!='0' and parent not in seen:
                    seen.add(parent);depth+=1
                    item=lookup.get(parent)
                    context_rows.append(dict(mode=mode,sampled_id=ident,ancestor_id=parent,depth=depth,
                        available=item is not None,text=item['text'] if item else '',
                        ctime_bjt=item['ctime_bjt'] if item else '',context_only=True))
                    if item is None:break
                    parent=item['parent_id']
    fields=['mode','副本','id','bvid','title','text','ctime_bjt','level','root_id','parent_id','author_role',
            'N','m','relative_weight','inclusion_probability','context_gap','missing_ancestor_id','url']
    if baseline_draw is not None:fields+=['sample_phase','baseline_m','added_m']
    write_csv(s.path/(prefix+'main_material.csv'),material,fields)
    write_csv(s.path/(prefix+'context_material.csv'),context_rows,
              ['mode','sampled_id','ancestor_id','depth','available','text','ctime_bjt','context_only'])
    write_csv(s.path/(prefix+'video_allocation.csv'),source_rows,['mode','副本','bvid','title','N','m','weight','url'])
    if not (s.path/(prefix+'coding.csv')).exists():
        write_csv(s.path/(prefix+'coding.csv'),[dict(mode=r['mode'],id=r['id'],relevance='pending',theme_status='pending',
            final='no',notes='语境缺失，核对后可编码或记不明；不得补抽' if r['context_gap'] else '') for r in material],small.CFIELDS)
    else:
        coding=read_csv(s.path/(prefix+'coding.csv'))
        if (len(coding)!=len(material) or {(r['mode'],r['id']) for r in coding}!={(r['mode'],r['id']) for r in material}):
            raise GateError('saved_snapshot_coding_IDs_changed')
    write_json(s.path/(prefix+'sample_bodies.json'),dict(
        sample_body_rows=[dict(mode=r['mode'],body=lookup[r['id']]) for r in material],
        purpose='exact_saved_text; CSV_formula_escaping_does_not_modify_these_bodies'))
    return material


def run(s):
    small.check(s)
    selection=s.frozen('small_video_selection.json')
    # This confirmation remains the authority for retaining missing context.
    s.frozen('small_context_rule_decision_002.json')
    collection=read_json(s.path/'small_collection.json')
    rows=read_jsonl(s.path/'small_comments.jsonl');obs=read_jsonl(s.path/'small_observations.jsonl')
    audit=s.frozen('small_integrity_audit_010.json')
    original=master_hashes(s)
    reg_name=PREFIX+'registration_001.json';frame_name=PREFIX+'frame_001.json'
    seed_name=PREFIX+'seed_001.json';draw_name=PREFIX+'draw_001.json';report_name=PREFIX+'completion_001.json'
    if (s.path/report_name).exists():
        report=s.frozen(report_name);frame=s.frozen(frame_name);draw=s.frozen(draw_name)
        verify_draw(frame,draw)
        if report['master_file_sha256']!=original:raise GateError('saved_snapshot_master_changed_after_sampling')
        for name,h in report['export_file_sha256'].items():
            if hashlib.sha256((s.path/name).read_bytes()).hexdigest()!=h:
                raise GateError('saved_snapshot_export_changed:'+name)
        return report
    if not (s.path/reg_name).exists():
        small.seal(s,reg_name,dict(protocol=PROTOCOL,human_instruction='那就变通啊，执行完告诉我',
            authorization_source='direct_user_message_in_current_chat',selection_hash=digest(selection),
            master_file_sha256=original,source_audit_hash=digest(audit),
            task='freeze saved finite comment corpus and draw at most 10 raw window IDs per fixed video; keep context uncertainty and all source failures',
            original_population_target_superseded_for_this_output_only=True,
            scope='60 fixed selected videos; normalized saved in-window bodies only; not all accessible Bilibili comments',
            targets=dict(comments_per_video=10,confidence_level=.95,precision_goal=.10),
            precision_goal_not_a_guarantee=True,coding_and_estimation_not_completed_by_sampling=True,
            no_new_network_collection=True,no_source_substitution=True,no_relevance_replacement=True,
            workflow_amendment='separate technical random sampling from final codebook and human coding acceptance; record future coding revisions without redrawing',
            coverage_findings_allowed_only_for_captured_scope=sorted(COVERAGE_FINDINGS),
            all_other_body_and_provenance_findings_fatal=True))
    reg=s.frozen(reg_name)
    if reg['master_file_sha256']!=original or reg['selection_hash']!=digest(selection):
        raise GateError('saved_snapshot_registration_inputs_changed')
    if not (s.path/frame_name).exists():
        payload=build_frame(s.config,selection,collection,rows,obs,audit)
        payload['source_review_snapshot']=read_csv(s.path/'small_collection_review.csv')
        payload['source_review_note']='Original review failures and missing pages retained; not relabeled accepted by this protocol.'
        small.seal(s,frame_name,payload)
    frame=s.frozen(frame_name)
    if frame['collection_hash']!=digest(collection):raise GateError('saved_snapshot_frame_collection_changed')
    if not (s.path/seed_name).exists():
        small.seal(s,seed_name,dict(seed=secrets.token_hex(32),frame_hash=digest(frame),registration_hash=digest(reg)))
    seed=s.frozen(seed_name)
    if seed['frame_hash']!=digest(frame) or seed['registration_hash']!=digest(reg):
        raise GateError('saved_snapshot_seed_bound_to_other_frame')
    if not (s.path/draw_name).exists():
        small.seal(s,draw_name,draw_from_frame(frame,seed['seed']))
    draw=s.frozen(draw_name);verify_draw(frame,draw)
    material=export_materials(s,frame,draw,selection)
    domains={}
    for mode,items in draw['samples'].items():
        sampled=[r for r in material if r['mode']==mode]
        domains[mode]=dict(name=NAMES[mode],fixed_videos=len(items),nonempty_videos=sum(v['N']>0 for v in items.values()),
            zero_window_videos=sum(v['N']==0 for v in items.values()),saved_window_IDs=sum(v['N'] for v in items.values()),
            raw_sample_n=sum(v['m'] for v in items.values()),roots=sum(r['level']=='root' for r in sampled),
            replies=sum(r['level']=='reply' for r in sampled),sampled_context_gap_n=sum(r['context_gap'] for r in sampled))
    exports=['small_snapshot_main_material.csv','small_snapshot_context_material.csv','small_snapshot_video_allocation.csv',
             'small_snapshot_sample_bodies.json']
    if master_hashes(s)!=original:raise GateError('saved_snapshot_master_files_modified')
    return small.seal(s,report_name,dict(protocol=PROTOCOL,status='RANDOM_SAMPLING_COMPLETE_CODING_PENDING',
        domains=domains,master_file_sha256=original,frame_hash=digest(frame),draw_hash=digest(draw),
        export_file_sha256={n:hashlib.sha256((s.path/n).read_bytes()).hexdigest() for n in exports},
        initial_coding_template_sha256=hashlib.sha256((s.path/'small_snapshot_coding.csv').read_bytes()).hexdigest(),
        original_source_review_counts=dict(Counter(r['status'] for r in frame['source_review_snapshot'])),
        raw_sample_rows=len(material),unique_sampled_IDs=len({r['id'] for r in material}),
        saved_raw_unique_IDs=len(rows),original_full_enumeration_verified=False,
        original_strict_protocol_sample_generated=False,broader_video_domain_inference_allowed=False,
        coding_completed=False,feedback_proportions_computed=False,seed_replay_verified=True,
        scope=frame['scope']))
