"""Preserve the original prefix and extend it under size-proportional quotas."""
from collections import Counter
from fractions import Fraction
import hashlib

from . import small
from .core import GateError, MODES, NAMES, digest, permutation, read_csv, write_csv
from .snapshot_sample import export_materials, master_hashes, verify_draw


PROTOCOL='captured-snapshot-retained-prefix-v2'
PREFIX='small_snapshot_supplement_'


def allocate(sizes,lower,target):
    """Exact rational water filling, then largest-remainder integer rounding.

    q_v=max(lower_v,min(N_v,lambda*N_v)); sum(q_v)=target. Lower bounds
    retain the original m_v. This is constrained proportional allocation,
    not a claim of Neyman optimality for unknown theme/relevance variances.
    """
    integer=lambda x:isinstance(x,int) and not isinstance(x,bool)
    if (set(sizes)!=set(lower) or not integer(target)
            or any(not integer(n) or n<0 or not integer(lower[k]) or not 0<=lower[k]<=n for k,n in sizes.items())
            or not sum(lower.values())<=target<=sum(sizes.values())):
        raise GateError('supplement_allocation_constraints_invalid')
    fixed={k:Fraction(n) for k,n in sizes.items() if lower[k]==n}
    active=set(sizes)-set(fixed)
    while active:
        remaining=Fraction(target)-sum(fixed.values())
        multiplier=remaining/sum(sizes[k] for k in active)
        constrained={k:Fraction(lower[k]) if multiplier*sizes[k]<lower[k] else Fraction(sizes[k])
                     for k in active if multiplier*sizes[k]<lower[k] or multiplier*sizes[k]>sizes[k]}
        if constrained:
            fixed.update(constrained);active-=set(constrained)
        else:
            fixed.update({k:multiplier*sizes[k] for k in active});break
    quotas=fixed
    counts={k:q.numerator//q.denominator for k,q in quotas.items()}
    remainder=target-sum(counts.values())
    rank=sorted((k for k in sizes if counts[k]<sizes[k]),key=lambda k:(-(quotas[k]-counts[k]),k))
    if remainder>len(rank):raise GateError('supplement_integer_rounding_invalid')
    for k in rank[:remainder]:counts[k]+=1
    if sum(counts.values())!=target or any(not lower[k]<=counts[k]<=sizes[k] for k in sizes):
        raise GateError('supplement_allocation_not_feasible')
    return dict(counts=counts,continuous_quotas={k:[q.numerator,q.denominator] for k,q in quotas.items()},
                rule='q=max(original_m,min(N,lambda*N)); largest_fractional_remainder; BVID_tie_break')


def extend_draw(frame,baseline,allocations):
    verify_draw(frame,baseline)
    if set(allocations)!=set(frame['frames']):raise GateError('supplement_mode_inventory_changed')
    samples={}
    for mode,videos in frame['frames'].items():
        assigned=allocations[mode]['counts']
        if set(assigned)!=set(videos):raise GateError('supplement_video_inventory_changed')
        samples[mode]={}
        for bv,ids in videos.items():
            N,m=len(ids),assigned[bv];old=baseline['samples'][mode][bv]
            if not isinstance(m,int) or isinstance(m,bool) or not old['m']<=m<=N:
                raise GateError('supplement_quota_would_drop_original_or_overdraw')
            chosen=permutation(ids,baseline['seed'],mode+':saved_snapshot:'+bv)[:m]
            if chosen[:old['m']]!=old['ids']:
                raise GateError('supplement_original_prefix_changed')
            samples[mode][bv]=dict(N=N,m=m,ids=chosen,baseline_m=old['m'],added_m=m-old['m'],
                inclusion_probability=m/N if N else None,relative_weight=N/m if m else None)
    return dict(protocol=PROTOCOL,frame_hash=digest(frame),baseline_draw_hash=digest(baseline),
        original_seed_reused=baseline['seed'],samples=samples,
        generator=baseline['generator'],random_streams='same mode:saved_snapshot:BVID streams; extend prefix, never reroll',
        quota_rule='sizes_only_constrained_proportional_with_original_sample_lower_bounds',
        quota_decisions_independent_of_coded_outcomes=True,scope=frame['scope'],
        original_sample_retained=True,coding_completed=False,broader_video_domain_inference_allowed=False)


def verify_extension(frame,baseline,allocations,draw):
    expected=extend_draw(frame,baseline,allocations)
    if any(draw.get(k)!=v for k,v in expected.items()):
        raise GateError('supplement_draw_not_replayable')


def run(s,targets=None):
    small.check(s)
    targets={m:200 for m in MODES} if targets is None else targets
    if set(targets)!=set(MODES) or sum(targets.values())>600:
        raise GateError('supplement_budget_or_mode_invalid')
    frame=s.frozen('small_snapshot_frame_001.json');baseline=s.frozen('small_snapshot_draw_001.json')
    verify_draw(frame,baseline)
    first_report=s.frozen('small_snapshot_completion_001.json');original=master_hashes(s)
    if first_report['master_file_sha256']!=original or first_report['draw_hash']!=digest(baseline):
        raise GateError('supplement_baseline_or_master_changed')
    selection=s.frozen('small_video_selection.json')
    if frame['selection_hash']!=digest(selection):raise GateError('supplement_selection_changed')
    baseline_files={n:hashlib.sha256((s.path/n).read_bytes()).hexdigest() for n in (
        'small_snapshot_main_material.csv','small_snapshot_context_material.csv','small_snapshot_video_allocation.csv',
        'small_snapshot_coding.csv','small_snapshot_sample_bodies.json')}
    report_name=PREFIX+'completion_001.json';reg_name=PREFIX+'registration_001.json'
    allocation_name=PREFIX+'allocation_001.json';draw_name=PREFIX+'draw_001.json'
    allocations={m:allocate({b:x['N'] for b,x in vs.items()},{b:x['m'] for b,x in vs.items()},targets[m])
                 for m,vs in baseline['samples'].items()}
    if (s.path/report_name).exists():
        report=s.frozen(report_name);draw=s.frozen(draw_name)
        verify_extension(frame,baseline,allocations,draw)
        if report['targets']!=targets or report['master_file_sha256']!=original:
            raise GateError('supplement_registration_or_master_changed')
        for name,h in report['export_file_sha256'].items():
            if hashlib.sha256((s.path/name).read_bytes()).hexdigest()!=h:
                raise GateError('supplement_export_changed:'+name)
        return report
    if not (s.path/reg_name).exists():
        small.seal(s,reg_name,dict(protocol=PROTOCOL,
            human_reply='保留原232条，再补抽，总量不超过原600条上限',authorization_source='direct_user_reply_in_current_chat',
            frame_hash=digest(frame),baseline_draw_hash=digest(baseline),targets=targets,
            master_file_sha256=original,baseline_export_sha256=baseline_files,
            original_sample_size=first_report['raw_sample_rows'],
            allocation='retain original per-video counts as lower bounds; distribute by window N with common multiplier and exact integer rounding',
            outcome_independent_design=True,original_seed_and_order_extended=True,new_seed_generated=False,
            no_new_collection=True,no_video_replacement=True,no_comment_window_change=True,
            final_weights='N/final_m for every retained and added ID in the combined sample',
            variance='fixed-source stratified within-video SRS; not expanded to unobserved videos/comments',
            sampling_precision_not_guaranteed=True,source_scope=frame['scope'],
            baseline_coding_final_n=sum(r.get('final')=='yes' for r in read_csv(s.path/'small_snapshot_coding.csv'))))
    reg=s.frozen(reg_name)
    if reg['targets']!=targets or reg['frame_hash']!=digest(frame) or reg['baseline_draw_hash']!=digest(baseline):
        raise GateError('supplement_registered_inputs_changed')
    if not (s.path/allocation_name).exists():
        small.seal(s,allocation_name,dict(protocol=PROTOCOL,registration_hash=digest(reg),domains=allocations,
            note='All quotas frozen before viewing supplementary comment bodies or coding outcomes.'))
    allocation=s.frozen(allocation_name)
    if allocation['domains']!=allocations:raise GateError('supplement_allocation_changed')
    if not (s.path/draw_name).exists():
        small.seal(s,draw_name,extend_draw(frame,baseline,allocations))
    draw=s.frozen(draw_name);verify_extension(frame,baseline,allocations,draw)
    material=export_materials(s,frame,draw,selection,prefix=PREFIX,baseline_draw=baseline)
    fields=list(material[0]) if material else ['mode','id','sample_phase']
    added=[r for r in material if r['sample_phase']=='supplement']
    write_csv(s.path/(PREFIX+'new_material.csv'),added,fields)
    comparison=[]
    for m,vs in draw['samples'].items():
        for bv,x in vs.items():
            comparison.append(dict(mode=m,副本=NAMES[m],bvid=bv,N=x['N'],baseline_m=x['baseline_m'],
                added_m=x['added_m'],final_m=x['m'],final_weight=x['relative_weight']))
    write_csv(s.path/(PREFIX+'allocation_comparison.csv'),comparison,
              ['mode','副本','bvid','N','baseline_m','added_m','final_m','final_weight'])
    base_coding=read_csv(s.path/'small_snapshot_coding.csv')
    base_by={(r['mode'],r['id']):r for r in base_coding}
    expected_base={(m,i) for m,vs in baseline['samples'].items() for x in vs.values() for i in x['ids']}
    if len(base_by)!=len(base_coding) or set(base_by)!=expected_base:
        raise GateError('supplement_baseline_coding_IDs_changed')
    coding=read_csv(s.path/(PREFIX+'coding.csv'))
    for row in coding:
        key=row['mode'],row['id']
        if key in base_by:
            for k,v in base_by[key].items():
                if k not in ('mode','id') and v:row[k]=v
    write_csv(s.path/(PREFIX+'coding.csv'),coding,small.CFIELDS)
    domains={}
    for m,vs in draw['samples'].items():
        subset=[r for r in material if r['mode']==m]
        domains[m]=dict(name=NAMES[m],fixed_sources=len(vs),window_IDs=sum(x['N'] for x in vs.values()),
            baseline_n=sum(x['baseline_m'] for x in vs.values()),added_n=sum(x['added_m'] for x in vs.values()),
            final_n=sum(x['m'] for x in vs.values()),sources_receiving_extra=sum(x['added_m']>0 for x in vs.values()),
            roots=sum(r['level']=='root' for r in subset),replies=sum(r['level']=='reply' for r in subset),
            context_gap_n=sum(r['context_gap'] for r in subset),
            largest_source=max((dict(bvid=b,N=x['N'],old_m=x['baseline_m'],final_m=x['m']) for b,x in vs.items()),key=lambda x:x['N']))
    exports=[PREFIX+x for x in ('main_material.csv','new_material.csv','context_material.csv','video_allocation.csv',
                               'allocation_comparison.csv','sample_bodies.json')]
    if master_hashes(s)!=original or any(hashlib.sha256((s.path/n).read_bytes()).hexdigest()!=h for n,h in baseline_files.items()):
        raise GateError('supplement_modified_original_data_or_sample_files')
    return small.seal(s,report_name,dict(protocol=PROTOCOL,status='SUPPLEMENT_RANDOM_SAMPLING_COMPLETE_CODING_PENDING',
        targets=targets,domains=domains,original_n=first_report['raw_sample_rows'],added_n=len(added),final_n=len(material),
        unique_final_IDs=len({r['id'] for r in material}),frame_hash=digest(frame),baseline_draw_hash=digest(baseline),draw_hash=digest(draw),
        master_file_sha256=original,baseline_export_sha256=baseline_files,
        export_file_sha256={n:hashlib.sha256((s.path/n).read_bytes()).hexdigest() for n in exports},
        initial_coding_template_sha256=hashlib.sha256((s.path/(PREFIX+'coding.csv')).read_bytes()).hexdigest(),
        original_IDs_retained=True,original_files_unchanged=True,quota_and_prefix_replay_verified=True,
        scope=frame['scope'],feedback_proportions_computed=False,source_coverage_improved=False))
