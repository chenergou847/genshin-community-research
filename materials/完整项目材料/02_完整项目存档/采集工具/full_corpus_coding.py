"""Human-calibrated full-corpus coding, with explicit per-row AI annotations.

Only the approved root-with-no-readable-words rule is automated. Remaining new
semantic labels must be explicitly supplied after reading compact batch context.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

from observer import small
from observer.core import Study,digest,now,read_json,write_json,write_csv
from observer.snapshot_sample import master_hashes

S=Study(Path(__file__).parent/'正式采集_小样本v1_20261018')
TOPICS=dict(r='roster_build',d='damage_threshold',m='mechanic_understanding',o='operation_control',
    e='encounter_timing',b='buff_and_route',t='retry_time_cost',w='reward_motivation',
    c='co_op_social',x='technical_interface',z='other_current_experience')
KINDS=dict(F='firsthand_report',B='own_account_condition',Q='gameplay_question',A='strategy_advice',
    C='evaluation_or_comparison',T='mechanism_tip',K='configuration_data',E='expectation_or_intention',
    O='other_gameplay_discussion',H='help_request',S='social_or_meta',X='off_mode',P='platform_meta',U='ambiguous')
SENTS=dict(p='positive',n='negative',m='mixed',s='neutral',u='unknown')
REASONS=dict(social='社交、玩梗或立场互动，当前发言没有目标本期玩法主张。',
    cross='当前内容指向其他副本、其他游戏或非本期经历。',platform='当前内容涉及视频或平台互动，不是本期副本体验。',
    ambiguous='现有正文和上文不足以可靠确定本期玩法指向或含义，保留不明。',
    media='判断所需图片未读或必要语境缺失，保留不明。',
    own='当前作者自述本期玩法过程、结果或账号条件；自述未被外部验证。',
    advice='当前发言为本期配队、角色替换或操作建议，不自动算本人受阻。',
    ask='当前发言询问本期玩法、配置或机制；没有明确受阻时不推定打不过。',
    compare='当前发言比较本期角色或配队表现；不把角色评价等同副本整体满意。',
    tip='当前发言解释本期机制或角色功能，不自动认为存在体验问题。',
    expect='当前发言表达本期预期或意图，尚不能记作已通关或已领取。',
    problem='当前作者明确陈述本期受阻或不满；原因仅作线索，不认定产品缺陷。',
    other='可识别为本期玩法讨论，具体判断以正文与已存上文为依据。')


def seal(name,obj):
    if (S.path/name).exists():return S.frozen(name)
    return small.seal(S,name,obj)


def root_nonverbal(row):
    if row['level']!='root':return False
    stripped=re.sub(r'\[[^\]\n]{1,100}\]','',row['text'])
    return not any(unicodedata.category(c)[0] in 'LN' for c in stripped)


def setup():
    reg=S.frozen('full_corpus_review_registration_001.json')
    packet=S.frozen('full_corpus_calibration_packet_001.json')
    frame=S.frozen('small_snapshot_frame_001.json')
    target=S.frozen('full_corpus_work_queue_001.json')
    prior=S.frozen('small_snapshot_ai_review_001.json')
    assert master_hashes(S)==reg['raw_master_sha256']
    prior_by={(r['mode'],r['id']):r for r in prior['rows']}
    approval=seal('full_corpus_human_calibration_001.json',dict(user_reply='全部认可',
        authority='direct_user_reply_in_current_chat',packet_hash=digest(packet),
        rows=[dict(number=r['number'],mode=r['mode'],id=r['id'],verdict='accepted',
            approved_fields=list(r['AI_proposal']),approved_AI_proposal=r['AI_proposal']) for r in packet['items']],
        human_confirmed_n=30,calibration_not_accuracy_validation=True))
    cb=S.frozen('small_snapshot_codebook_proposal_001.json')['codebook']
    cb=dict(cb,version='full-corpus-calibrated-v1',status='AI_CODEBOOK_CALIBRATED_WITH_30_HUMAN_ACCEPTANCES',
        all_codes_AI_initial_only=False,human_calibration_hash=digest(approval),
        root_nonverbal_rule='根评论无可读语义词，仅表情、符号或不可读图片占位，记unknown；不从视频标题补体验。',
        calibration_is_not_model_training=True)
    book=seal('full_corpus_codebook_001.json',dict(codebook=cb,registration_hash=digest(reg)))
    raw={r['id']:r for r in frame['comments']}
    approved={(r['mode'],r['id']) for r in packet['items']}
    initial_name='full_corpus_initial_labels_001.json'
    if not (S.path/initial_name).exists():
        initial=[];changes=[]
        for item in target['rows']:
            key=item['mode'],item['id'];r=raw[item['id']]
            if key in prior_by:
                label=dict(prior_by[key]);label.update(final='yes',project_final=True,
                    review_kind='human_calibration_acceptance' if key in approved else 'AI_project_final_reused_review',
                    human_reviewed=key in approved,human_confirmed_fields=list(packet['items'][0]['AI_proposal']) if key in approved else [],
                    reviewer='human_user' if key in approved else 'Codex_AI',
                    origin='prior_600_AI_review_adopted_under_accepted_calibration',codebook_version=cb['version'])
                if root_nonverbal(r) and label['relevance']!='unknown':
                    changes.append(dict(mode=key[0],id=key[1],old_relevance=label['relevance'],new_relevance='unknown',
                        reason='apply accepted nonverbal-root rule consistently'))
                    label.update(relevance='unknown',themes='',self_experience_themes='',problem_themes='',
                        problem_status='none_explicit',experience_kind='ambiguous',theme_status='unknown',sentiment='unknown',
                        reason='依据人审17、18号同类根评论规则；无可读语义，不能从标题补体验。',
                        origin='calibration_rule_consistency_correction',human_reviewed=False,reviewer='Codex_AI')
                initial.append(label)
            elif root_nonverbal(r):
                initial.append(dict(mode=key[0],id=key[1],bvid=r['bvid'],relevance='unknown',themes='',
                    self_experience_themes='',problem_themes='',problem_status='none_explicit',
                    experience_kind='ambiguous',theme_status='unknown',sentiment='unknown',evidence=r['text'],
                    reason='依据人审17、18号校准规则：根评论只有表情、符号或不可读媒体占位，无法核定玩法含义。',
                    content_flags='nonverbal_root_rule'+(';image_unread' if r['media'] else ''),
                    context_status='checked_with_limits',review_kind='AI_calibrated_exact_rule',reviewer='Codex_AI',
                    human_reviewed=False,final='yes',project_final=True,codebook_version=cb['version']))
        seal(initial_name,dict(rows=initial,changes_to_old_AI=changes,codebook_hash=digest(book),
            human_calibration_hash=digest(approval),method='reuse prior 600 reviewed proposals; exact approved nonverbal-root rule only; no general keyword classifier'))
    initial=S.frozen(initial_name)
    coded={(r['mode'],r['id']) for r in initial['rows']}
    video={v['bvid']:v for v in S.frozen('small_video_selection.json')['videos']}
    items=[]
    for mode in ('abyss','theater','stygian'):
        for bv in frame['frames'][mode]:
            pending=[raw[i] for i in frame['frames'][mode][bv] if (mode,i) not in coded]
            pending.sort(key=lambda r:(raw.get(r['root_id'],r)['ctime'],r['root_id'],r['ctime'],r['id']))
            for r in pending:items.append(dict(n=len(items)+1,mode=mode,id=r['id'],bvid=bv))
    queue=seal('full_corpus_semantic_queue_001.json',dict(items=items,frame_hash=digest(frame),initial_hash=digest(initial)))
    assert queue['items']==items
    return frame,raw,video,queue,initial,book


def labels(initial):
    rows=list(initial['rows'])
    for path in sorted(S.path.glob('full_corpus_semantic_batch_*.json')):rows.extend(S.frozen(path.name)['rows'])
    mapping={(r['mode'],r['id']):r for r in rows}
    if len(mapping)!=len(rows):raise ValueError('重复编码ID')
    return mapping


def public(text):return re.sub(r'回复\s*@[^:：\n]+[:：]\s*','↳',text)


def show(start,count,raw,video,queue):
    selected=queue['items'][start-1:start-1+count]
    refs={r['id']:str(r['n']) for r in selected};context={};context_rows=[]
    authors={}
    def actor(r):
        ident=r.get('author_id')
        if ident not in authors:authors[ident]=str(len(authors)+1)
        return authors[ident]
    def reference(ident):
        if ident=='0':return '-'
        if ident in refs:return refs[ident]
        if ident in context:return context[ident]
        ref='c'+str(len(context)+1);context[ident]=ref
        r=raw.get(ident)
        if r is None:context_rows.append([ref,'missing']);return ref
        parent=reference(r['parent_id'])
        context_rows.append([ref,parent,actor(r),'图' if r['media'] else '',public(r['text'])])
        return ref
    material=[];last=None
    for item in selected:
        r=raw[item['id']];parent=reference(r['parent_id'])
        if item['bvid']!=last:
            material.append(['SOURCE',item['mode'],item['bvid'],video[item['bvid']]['title']]);last=item['bvid']
        material.append([item['n'],parent,actor(r),('图' if r['media'] else '')+('UP' if r['author_role']!='audience' else ''),public(r['text'])])
    for row in context_rows:print(json.dumps(row,ensure_ascii=False,separators=(',',':')))
    for row in material:print(json.dumps(row,ensure_ascii=False,separators=(',',':')))


def record(path,raw,queue,initial,book):
    lookup={r['n']:r for r in queue['items']};existing=labels(initial);new=[]
    # n|R/I/U|topic letters|self topic letters or 1|kind|problem topics or -|p/n/m/s/u|reason key
    expanded=[]
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.startswith('#'):continue
        if line.startswith('@'):
            fields=line[1:].split('|')
            if len(fields)==3:
                rel,reason,indices=fields
                template=rel+'|-|-|'+('S' if rel=='I' else 'U')+f'|-|u|{reason}'
            else:
                assert len(fields)==8
                *values,indices=fields;template='|'.join(values)
            for chunk in indices.split(','):
                bounds=list(map(int,chunk.split('-')))
                for n in range(bounds[0],bounds[-1]+1):
                    expanded.append(f'{n}|'+template)
        else:expanded.append(line)
    distinct={}
    for line in expanded:
        parts=line.split('|');n=int(parts[0])
        if n in distinct and distinct[n].split('|')[1:7]!=parts[1:7]:
            raise ValueError(('同一编号存在冲突判定',n))
        distinct[n]=line
    assert len(distinct)==max(distinct)-min(distinct)+1,'批内漏掉编号'
    for line in distinct.values():
        parts=line.split('|')
        if len(parts) not in (8,9):raise ValueError(('需要8或9列',line))
        ni,rel,th,st,kind,problem,sent,reason=parts[:8]
        item=lookup[int(ni)];r=raw[item['id']]
        key=item['mode'],item['id']
        if key in existing:raise ValueError(('重复',key))
        expand=lambda value:';'.join(TOPICS[c] for c in value if c!='-')
        topics=expand(th);selftopics=topics if st=='1' else expand(st);problems=expand(problem)
        relevance={'R':'related','I':'irrelevant','U':'unknown'}[rel]
        assert set(selftopics.split(';'))-{''}<=set(topics.split(';'))
        assert set(problems.split(';'))-{''}<=set(selftopics.split(';'))
        assert relevance=='related' or not topics+selftopics+problems
        flags=list(filter(None,parts[8].split(';'))) if len(parts)==9 else []
        p=r['parent_id'];seen={r['id']}
        if r['media']:flags.append('image_unread')
        while p!='0' and p not in seen:
            seen.add(p);a=raw.get(p)
            if not a:flags.append('missing_ancestor');break
            if a['media']:flags.append('ancestor_image_unread')
            p=a['parent_id']
        explanation=REASONS.get(reason,reason)
        assert len(explanation)>5
        row=dict(mode=item['mode'],id=item['id'],bvid=item['bvid'],semantic_index=int(ni),
            relevance=relevance,themes=topics,self_experience_themes=selftopics,experience_kind=KINDS[kind],
            problem_status='current_reported' if problems else 'none_explicit',problem_themes=problems,
            sentiment=SENTS[sent],theme_status='unknown' if relevance=='unknown' or (relevance=='related' and not topics) else 'known',
            evidence=r['text'],reason=explanation,content_flags=';'.join(sorted(set(flags))),
            context_status='checked_with_limits' if flags or relevance=='unknown' else 'checked',
            reviewer='Codex_AI',review_kind='AI_semantic_project_final',human_reviewed=False,
            final='yes',project_final=True,codebook_version=book['codebook']['version'],
            origin='explicit_read_and_reasoned_batch_annotation')
        new.append(row)
    assert len(new)==len({(r['mode'],r['id']) for r in new})
    name=f"full_corpus_semantic_batch_{min(r['semantic_index'] for r in new):04}_{max(r['semantic_index'] for r in new):04}.json"
    small.seal(S,name,dict(rows=new,queue_hash=digest(queue),codebook_hash=digest(book),all_new_rows_AI=True))
    status(initial,queue)


def status(initial,queue):
    current=labels(initial)
    state=read_json(S.path/'执行状态.json');reg=S.frozen('full_corpus_review_registration_001.json')
    assert master_hashes(S)==reg['raw_master_sha256']
    summary=dict(total_target=6526,coded=len(current),remaining=6526-len(current),
        calibration_human_confirmed=30,new_semantic_queue=len(queue['items']),
        relevance=dict(Counter(r['relevance'] for r in current.values())),
        methods=dict(Counter(r['review_kind'] for r in current.values())),validation_received=0)
    state.update(stage='FULL_CORPUS_AI_CODING_IN_PROGRESS')
    state['full_corpus_review'].update(calibration_received=30,progress=summary,full_corpus_coding_complete=False)
    state['human_review']['calibration_received']=30
    write_json(S.path/'执行状态.json',state)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['status','show','record']);ap.add_argument('arg',nargs='?');ap.add_argument('count',nargs='?',type=int,default=100);args=ap.parse_args()
    frame,raw,video,queue,initial,book=setup()
    if args.command=='show':show(int(args.arg),args.count,raw,video,queue)
    elif args.command=='record':record(args.arg,raw,queue,initial,book)
    else:status(initial,queue)
