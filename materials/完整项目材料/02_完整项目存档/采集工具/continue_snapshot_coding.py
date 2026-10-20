"""Offline, explicit per-ID AI coding. No model calls, keyword classifier or redraw.

`show start count` displays pending material and ancestor text. `record file`
validates explicit read-and-reasoned annotations before updating the worktable.
Frozen sampling and raw records remain unchanged. All labels remain AI proposals.
"""
import argparse
from collections import Counter
import json
import re
from pathlib import Path
from observer.core import Study, digest, read_csv, read_json, write_csv, write_json, now
from observer import small
from observer.snapshot_sample import master_hashes

S=Study('正式采集_小样本v1_20261018')
TOPICS=dict(r='roster_build',d='damage_threshold',m='mechanic_understanding',o='operation_control',e='encounter_timing',b='buff_and_route',t='retry_time_cost',w='reward_motivation',c='co_op_social',x='technical_interface',z='other_current_experience')
KINDS=dict(F='firsthand_report',A='strategy_advice',Q='gameplay_question',C='evaluation_or_comparison',K='configuration_data',H='help_request',E='expectation_or_intention',S='social_or_meta',X='off_mode',T='mechanism_tip',P='platform_meta',O='other_gameplay_discussion',U='ambiguous',B='own_account_condition')
VERSION='snapshot-codebook-v0.2-USER-BOUNDARY-APPROVED'

def setup():
    frame=S.frozen('small_snapshot_frame_001.json')
    draw=S.frozen('small_snapshot_supplement_draw_001.json')
    lookup={r['id']:r for r in frame['comments']}
    videos={v['bvid']:v for v in S.frozen('small_video_selection.json')['videos']}
    queue_name='small_snapshot_coding_continuation_queue_001.json'
    if (S.path/queue_name).exists():
        queue=S.frozen(queue_name)
    else:
        coding=read_csv(S.path/'small_snapshot_supplement_coding.csv')
        pending={(r['mode'],r['id']) for r in coding if r['relevance']=='pending'}
        items=[]
        for mode in ('abyss','theater','stygian'):
            for bv,info in draw['samples'][mode].items():
                for ident in sorted(info['ids'],key=lambda i:(lookup[i]['ctime'],i)):
                    if (mode,ident) in pending:
                        items.append(dict(index=len(items)+1,mode=mode,id=ident,bvid=bv))
        assert len(items)==569 and {(x['mode'],x['id']) for x in items}==pending
        queue=small.seal(S,queue_name,dict(items=items,draw_hash=digest(draw),frame_hash=digest(frame),order='mode / frozen-source-order / ctime-ID; ordering only, not a new sample'))
        small.seal(S,'small_snapshot_coding_before_continuation_001.json',dict(rows=coding,master_hashes=master_hashes(S)))
        approval=dict(codebook_version=VERSION,approved_boundary='本期配队建议、机制提示和角色表现比较计为玩法相关讨论；明确自述实际经历另标本人体验；明确受阻再标体验问题。',
            user_reply='认可，按此口径继续（建议）',authorized_action='继续剩余569条AI初判；不等于逐条人工定稿',
            original_codebook_proposal_hash=digest(S.frozen('small_snapshot_codebook_proposal_001.json')),all_labels_remain_AI_proposals=True)
        small.seal(S,'small_snapshot_codebook_boundary_approval_001.json',approval)
        state=read_json(S.path/'执行状态.json');state.update(stage='CODING_CONTINUATION_AI_PROPOSALS_IN_PROGRESS',coding_boundary_approved=True,coding_completed=False)
        write_json(S.path/'执行状态.json',state)
    assert queue['draw_hash']==digest(draw) and queue['frame_hash']==digest(frame)
    return frame,draw,lookup,videos,queue

def ancestors(row,lookup):
    result=[];parent=row['parent_id'];seen={row['id']}
    while parent!='0' and parent not in seen:
        seen.add(parent);a=lookup.get(parent)
        result.append(dict(id=parent,available=a is not None,text=a['text'] if a else '',media=a['media'] if a else False,
            same_author_as_item=a['author_id']==row['author_id'] if a else None))
        if a is None: break
        parent=a['parent_id']
    return result

def public_text(t):
    return re.sub(r'回复\s*@[^:：]+[:：]\s*','回复[用户]：',t)

def show(start,count,lookup,videos,queue):
    last=None
    for item in queue['items'][start-1:start-1+count]:
        r=lookup[item['id']]
        if item['bvid']!=last:
            print(json.dumps(dict(source=item['bvid'],mode=item['mode'],title=videos[item['bvid']]['title']),ensure_ascii=False));last=item['bvid']
        # No silent text truncation: every own body and ancestor is available in this display.
        print(json.dumps(dict(n=item['index'],id=r['id'],text=public_text(r['text']),image=r['media'],role=r['author_role'],
            ancestors=[dict(text=public_text(a['text']) if a['available'] else '[缺正文]',image=a['media'],same_author=a['same_author_as_item']) for a in ancestors(r,lookup)]),ensure_ascii=False))

def record(path,frame,draw,lookup,queue):
    # index|R/I/U|topic shorthand|self topics (1=all)|kind|problem topics/-/old|evidence|reason|sentiment|flags
    entries=[];byindex={x['index']:x for x in queue['items']}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.startswith('#'): continue
        parts=line.split('|');assert len(parts)==10,(line,len(parts))
        ni,rel,th,st,kind,pr,ev,reason,sent,flags=parts
        item=byindex[int(ni)];raw=lookup[item['id']];anc=ancestors(raw,lookup)
        expand=lambda value:';'.join(TOPICS[c] for c in value if c!='-')
        topics=expand(th);selftopics=topics if st=='1' else expand(st)
        problem=expand(pr) if pr not in ('-','old') else ''
        relevance=dict(R='related',I='irrelevant',U='unknown')[rel]
        assert ev and ev in raw['text'],(ni,ev,raw['text'])
        assert reason and set(filter(None,selftopics.split(';')))<=set(filter(None,topics.split(';')))
        assert set(filter(None,problem.split(';')))<=set(filter(None,topics.split(';')))
        assert relevance=='related' or not topics
        media=raw['media'] or any(a['media'] for a in anc)
        gap=any(not a['available'] for a in anc)
        fs=list(filter(None,flags.split(';')))
        if raw['media'] and 'image_unread' not in fs:fs.append('image_unread')
        if any(a['media'] for a in anc) and 'ancestor_image_unread' not in fs:fs.append('ancestor_image_unread')
        if gap and 'missing_ancestor' not in fs:fs.append('missing_ancestor')
        row=dict(mode=item['mode'],id=item['id'],bvid=item['bvid'],queue_index=int(ni),relevance=relevance,themes=topics,self_experience_themes=selftopics,
            experience_kind=KINDS[kind],problem_status='current_reported' if problem else ('retrospective_only' if pr=='old' else 'none_explicit'),problem_themes=problem,
            evidence=ev,reason=reason,sentiment=sent or 'neutral',content_flags=';'.join(fs),context_status='checked_with_limits' if media or gap or relevance=='unknown' else 'checked',
            theme_status='unknown' if relevance=='unknown' else 'known',conditions='',action='',outcome='',difficulty='not_specified',
            reviewer='Codex_AI_initial_coding',review_kind='ai_proposal',final='no',codebook_version=VERSION)
        row['notes']='AI初判，待人工定稿；problem_status='+row['problem_status']+'；problem_themes='+problem+'；flags='+row['content_flags']
        entries.append(row)
    assert len(entries)==len({x['id'] for x in entries})
    coding_path=S.path/'small_snapshot_supplement_coding.csv';coding=read_csv(coding_path)
    existing={(r['mode'],r['id']):r for r in coding}
    for r in entries: assert existing[r['mode'],r['id']]['relevance']=='pending',r['id']
    masters=master_hashes(S)
    name=f"small_snapshot_coding_continuation_batch_{min(r['queue_index'] for r in entries):03}_{max(r['queue_index'] for r in entries):03}.json"
    proposal=small.seal(S,name,dict(rows=entries,draw_hash=digest(draw),frame_hash=digest(frame),codebook_version=VERSION,human_final_count=0))
    for r in entries: existing[r['mode'],r['id']].update({k:r[k] for k in small.CFIELDS if k in r})
    write_csv(coding_path,coding,small.CFIELDS)
    assert master_hashes(S)==masters
    summary=dict(total=len(coding),relevance=dict(Counter(r['relevance'] for r in coding)),ai_proposals=sum(r.get('review_kind')=='ai_proposal' for r in coding),human_final=sum(r.get('final')=='yes' for r in coding))
    state=read_json(S.path/'执行状态.json');state['coding_continuation']=dict(updated_at=now(),summary=summary,last_batch=name)
    write_json(S.path/'执行状态.json',state)
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['show','record']);parser.add_argument('arg');parser.add_argument('count',nargs='?',type=int,default=40);args=parser.parse_args()
    frame,draw,lookup,videos,queue=setup()
    if args.command=='show':show(int(args.arg),args.count,lookup,videos,queue)
    else:record(args.arg,frame,draw,lookup,queue)
