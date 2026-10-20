"""Prepare a source-diverse coding pilot inside the already fixed 600 IDs."""
import json
from observer.core import Study, digest, permutation, write_json
from observer import small


if __name__=='__main__':
    s=Study('正式采集_小样本v1_20261018')
    frame=s.frozen('small_snapshot_frame_001.json')
    draw=s.frozen('small_snapshot_supplement_draw_001.json')
    baseline=s.frozen('small_snapshot_draw_001.json')
    selection=s.frozen('small_video_selection.json')
    video={v['bvid']:v for v in selection['videos']}
    lookup={r['id']:r for r in frame['comments']}
    name='small_snapshot_coding_pilot_queue_001.json'
    if (s.path/name).exists():
        queue=s.frozen(name)
        assert queue['draw_hash']==digest(draw)
    else:
        selected=[]
        for mode,vs in draw['samples'].items():
            order=permutation([b for b,x in vs.items() if x['m']],baseline['seed'],mode+':coding_pilot_sources_v1')
            prioritized=[];seen_up=set()
            for b in order:
                if video[b]['primary_up'] not in seen_up:
                    prioritized.append(b);seen_up.add(video[b]['primary_up'])
            prioritized.extend(b for b in order if b not in prioritized)
            within={b:permutation(vs[b]['ids'],baseline['seed'],mode+':coding_pilot_comments_v1:'+b) for b in order}
            chosen=[];round_no=0
            while len(chosen)<10:
                changed=False
                for b in prioritized:
                    if round_no<len(within[b]) and len(chosen)<10:
                        chosen.append(dict(mode=mode,id=within[b][round_no],bvid=b,role='pilot'))
                        changed=True
                if not changed:break
                round_no+=1
            selected.extend(chosen)
        selected_keys={(r['mode'],r['id']) for r in selected}
        diagnostics=[dict(mode=m,id=i,bvid=b,role='missing_context_diagnostic')
            for m,vs in draw['samples'].items() for b,x in vs.items() for i in x['ids']
            if i in frame['context_annotations'] and (m,i) not in selected_keys]
        queue=small.seal(s,name,dict(draw_hash=digest(draw),frame_hash=digest(frame),
            unit='existing_600_sample_IDs_only',purpose='codebook_development_not_population_estimation',
            selection_rule='seeded_source_order_with_distinct_UP_priority; one_comment_per_source_per_round; 10_per_mode',
            selected=selected,diagnostics=diagnostics,all_pilot_results_AI_draft=True,
            original_random_sample_unchanged=True,no_theme_or_sentiment_selection=True))
    materials=[]
    for item in queue['selected']+queue['diagnostics']:
        r=lookup[item['id']];ancestors=[];parent=r['parent_id'];seen={r['id']}
        while parent!='0' and parent not in seen:
            seen.add(parent);a=lookup.get(parent)
            ancestors.append(dict(id=parent,available=a is not None,text=a['text'] if a else '',
                                  media=a.get('media',[]) if a else []))
            if a is None:break
            parent=a['parent_id']
        materials.append(dict(**item,text=r['text'],date=r['ctime_bjt'],level=r['level'],
            author_role=r['author_role'],title=video[r['bvid']]['title'],media=r['media'],
            media_readability=r['media_readability'],context_gap=frame['context_annotations'].get(r['id']),
            ancestors=ancestors))
    write_json(s.path/'small_snapshot_coding_pilot_material_001.json',dict(queue_hash=digest(queue),items=materials))
    print(json.dumps(dict(pilot=len(queue['selected']),diagnostics=len(queue['diagnostics']),items=materials),ensure_ascii=False))
