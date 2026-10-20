"""Prepare the agreed 30 calibration cases and a disjoint 30-case holdout.

Offline only. Existing 600 AI labels are proposals, never human judgments.
"""
from collections import Counter
import hashlib
from pathlib import Path
import re
import secrets

from observer import small
from observer.core import Study, digest, permutation, read_json, read_jsonl, write_csv
from observer.snapshot_sample import master_hashes


S=Study(Path(__file__).parent/'正式采集_小样本v1_20261018')
OUT=S.path.parent.parent/'全量编码_20261019'
PREFIX='full_corpus_'
FIELDS=['relevance','themes','experience_kind','self_experience_themes','problem_status',
        'problem_themes','sentiment','theme_status','reason','content_flags']
LABELS={'related':'相关','irrelevant':'不相关','unknown':'不明','positive':'正向','negative':'负向',
        'mixed':'混合','neutral':'中性','current_reported':'明确自述本期受阻',
        'none_explicit':'没有明确本期受阻','retrospective_only':'仅回顾旧期问题',
        'firsthand_report':'本人本期经历','help_request':'本人求助',
        'own_account_condition':'本人账号条件','strategy_advice':'配队／策略建议',
        'evaluation_or_comparison':'评价／比较','expectation_or_intention':'预期／打算',
        'mechanism_tip':'机制提示','configuration_data':'配置补充',
        'social_or_meta':'社交／玩梗','off_mode':'其他副本','retrospective_off_mode':'其他内容的旧经历',
        'content_request':'催更','platform_meta':'平台发评','ambiguous':'指向不明'}
MODES={'abyss':'深境螺旋','theater':'幻想真境剧诗','stygian':'幽境危战'}


def public_text(text):
    text=re.sub(r'回复\s*@[^:：\n]+[:：]', '回复[用户]：',text)
    return re.sub(r'@[^\s@]+','[用户]',text)


def keep(name,payload):
    if (S.path/name).exists():return S.frozen(name)
    return small.seal(S,name,payload)


def main():
    small.check(S)
    before=master_hashes(S)
    frame=S.frozen('small_snapshot_frame_001.json')
    queue=S.frozen('small_snapshot_coding_pilot_queue_001.json')
    prior=S.frozen('small_snapshot_ai_review_001.json')
    cb=S.frozen('small_snapshot_codebook_proposal_001.json')['codebook']
    old_material=read_json(S.path/'small_snapshot_coding_pilot_material_001.json')
    by={(r['mode'],r['id']):r for r in prior['rows']}
    mat={(r['mode'],r['id']):r for r in old_material['items']}
    target={m:sorted(i for ids in videos.values() for i in ids) for m,videos in frame['frames'].items()}
    target_keys={(m,i) for m,ids in target.items() for i in ids}
    if sum(map(len,target.values()))!=6526:raise ValueError('已确认的6526条目标框发生变化')
    selected=queue['selected']
    keys={(r['mode'],r['id']) for r in selected}
    assert len(selected)==len(keys)==30 and keys<=target_keys
    assert Counter(r['mode'] for r in selected)==dict(abyss=10,theater=10,stygian=10)
    registration=keep(PREFIX+'review_registration_001.json',dict(
        user_confirmation='确认，按此执行',authority='direct_user_reply_in_current_chat',
        confirmed_task='对全部6526条评论编码；先人工审核30条校准，再审核30条独立随机结果；AI负责其余最终项目编码，低把握或规则冲突集中由用户裁决；保留AI审核标记，交付全量编码表与分副本报告。',
        target_frame_hash=digest(frame),target_keys_hash=digest(sorted(target_keys)),
        total_target_rows=6526,by_mode={m:len(ids) for m,ids in target.items()},
        calibration_n=30,validation_n=30,calibration_source_queue_hash=digest(queue),
        calibration_selection='reuse existing source-diverse pilot, 10 per mode; not a random accuracy test',
        baseline_AI_labels_hash=digest(prior),baseline_codebook_hash=digest(cb),
        human_approval_for_AI_project_final=True,all_rows_human_review_required=False,
        final_label_authorship='human calibration / AI project coding / human adjudication, recorded per row',
        scope='saved_normalized_in_window_bodies_of_60_fixed_sources; not whole Bilibili',
        model_training=False,learning_method='versioned project codebook, human decisions and examples',
        ambiguous_media='unread media recorded; self-contained text may be coded; unresolvable content stays unknown',
        exception_policy='batch substantive rule conflicts; reuse existing decisions; do not ask repeatedly about the same rule',
        audit_policy='holdout excludes calibration, uses fresh seed and 10 SRS per mode; reveal after full AI labels are frozen; compare human independent labels before showing AI; report raw disagreements and uncertainty, no accuracy guarantee from 30 cases',
        audit_disagreement_policy='trace disagreement types through the corpus; if rules are tuned on holdout, disclose it is no longer independent validation',
        weights='full-corpus descriptive counts use weight 1; original sampled-case weights are not used for full-corpus proportions',
        raw_master_sha256=before))
    assert registration['raw_master_sha256']==before and registration['target_frame_hash']==digest(frame)
    calibration=[]
    for index,keyrow in enumerate(selected,1):
        key=(keyrow['mode'],keyrow['id']);item=mat[key];ai=by[key]
        calibration.append(dict(number=index,mode=key[0],id=key[1],bvid=item['bvid'],
            title=public_text(item['title']),text=public_text(item['text']),date=item['date'],
            level=item['level'],author_role=item['author_role'],media_unread=bool(item['media']),
            ancestors=[dict(id=a['id'],available=a['available'],text=public_text(a['text']),
                            media_unread=bool(a['media'])) for a in item['ancestors']],
            AI_proposal={k:ai.get(k,'') for k in FIELDS},human_review_status='pending'))
    packet=keep(PREFIX+'calibration_packet_001.json',dict(registration_hash=digest(registration),
        items=calibration,prior_labels_are_AI_only=True,calibration_n=30,human_judgments_received=0))
    assert packet['items']==calibration
    held_name=PREFIX+'validation_holdout_001.json'
    if not (S.path/held_name).exists():
        seed=secrets.token_hex(32)
        validation=[]
        for mode,ids in target.items():
            rest=[i for i in ids if (mode,i) not in keys]
            validation.extend(dict(mode=mode,id=i,population_size=len(rest),inclusion_probability=10/len(rest))
                for i in permutation(rest,seed,mode+':full_corpus_validation_v1')[:10])
        keep(held_name,dict(registration_hash=digest(registration),target_frame_hash=digest(frame),seed=seed,
            rows=validation,status='SEALED_NOT_REVIEWED',human_judgments_received=0,
            no_AI_labels_in_holdout=True,not_used_for_calibration=True))
    held=S.frozen(held_name)
    assert held['registration_hash']==digest(registration)
    assert len(held['rows'])==30 and not keys&{(x['mode'],x['id']) for x in held['rows']}
    expected=[]
    for mode,ids in target.items():
        rest=[i for i in ids if (mode,i) not in keys]
        expected.extend(dict(mode=mode,id=i,population_size=len(rest),inclusion_probability=10/len(rest))
            for i in permutation(rest,held['seed'],mode+':full_corpus_validation_v1')[:10])
    assert held['rows']==expected
    body={r['id']:r for r in frame['comments']}
    work=[]
    for mode,ids in target.items():
        for ident in ids:
            r=body[ident];key=(mode,ident)
            work.append(dict(mode=mode,id=ident,bvid=r['bvid'],root_id=r['root_id'],parent_id=r['parent_id'],
                level=r['level'],text_hash=r['text_hash'],ctime=r['ctime'],author_role=r['author_role'],
                media_unread=bool(r['media']),context_gap=ident in frame['context_annotations'],
                prior_AI_proposal_available=key in by,prior_AI_proposal=by.get(key),
                full_corpus_final_status='pending_calibration'))
    work_packet=keep(PREFIX+'work_queue_001.json',dict(registration_hash=digest(registration),
        target_frame_hash=digest(frame),target_keys_hash=digest(sorted(target_keys)),rows=work,
        total=6526,prior_AI_proposals=sum(r['prior_AI_proposal_available'] for r in work),
        prior_AI_proposals_not_final=True,new_final_rows=0))
    assert len(work_packet['rows'])==6526
    themes={t['id']:t['label'] for t in cb['themes']}
    def words(value):return '、'.join(themes.get(t,t) for t in value.split(';') if t) or '—'
    OUT.mkdir(exist_ok=True)
    lines=['# 首批30条人工校准\n',
        '先审核这30条，不需要逐条审核全部6526条。你给出的裁决会成为本项目后续AI编码的规则和示例。\n',
        '**回复方式：**认可全部可回复“30条全部认可”；有修改可回复“其余认可；第12条改为……；第13条……”。不确定就写“不确定”，不要勉强判断。也可以逐批回复。\n',
        '**每条主要检查：**是否涉及本期目标副本；发言属于本人经历、账号条件、建议、预期还是闲聊；是否明确报告本期受阻。主题和倾向也可直接指出需要修改之处。\n',
        '上文仅用于解释指向，不能把别人的经历算给当前发言。标注“有图片未读”时，不据文字猜图里的配置或成绩。主题名称不等于负面问题。\n',
        '以下判断全部是AI提案，尚无人审；这30条偏重来源多样性，只用于校准，不用于计算准确率或反馈占比。\n']
    csvrows=[]
    for item in calibration:
        a=item['AI_proposal'];n=item['number']
        lines.extend([f"## {n:02d}｜{MODES[item['mode']]}\n",
            f"来源：[{item['title']}](https://www.bilibili.com/video/{item['bvid']}/)｜{item['date']}｜{'根评论' if item['level']=='root' else '回复'}\n",
            '**本条原文**\n', '\n'.join('> '+line for line in item['text'].splitlines())+'\n'])
        if item['ancestors']:
            lines.append('**必要上文（近→远）**\n')
            for parent in item['ancestors']:
                lines.append('- '+(parent['text'] if parent['available'] else '父正文未取得')+('【有图片未读】' if parent['media_unread'] else '')+'\n')
        if item['media_unread']:lines.append('本条附有图片，尚未读图。\n')
        brief=f"{LABELS.get(a['relevance'],a['relevance'])}；{LABELS.get(a['experience_kind'],a['experience_kind'])}；{LABELS.get(a['problem_status'],a['problem_status'])}"
        lines.extend([f"**AI初判：{brief}。**\n",
            f"主题：{words(a['themes'])}；倾向：{LABELS.get(a['sentiment'],a['sentiment'])}。\n",
            '理由：'+a['reason']+'\n','你的裁决：待审核。\n'])
        csvrows.append(dict(number=n,mode=item['mode'],id=item['id'],text=item['text'],
            context='\n'.join(p['text'] if p['available'] else '父正文未取得' for p in item['ancestors']),
            AI_judgment=brief,AI_themes=words(a['themes']),AI_sentiment=LABELS.get(a['sentiment'],a['sentiment']),
            AI_reason=a['reason'],human_verdict='',human_correction='',human_reason=''))
    if not (OUT/'01_首批30条校准.md').exists():
        (OUT/'01_首批30条校准.md').write_text('\n'.join(lines),encoding='utf-8')
    if not (OUT/'01_首批30条校准.csv').exists():
        write_csv(OUT/'01_首批30条校准.csv',csvrows,['number','mode','id','text','context','AI_judgment','AI_themes',
            'AI_sentiment','AI_reason','human_verdict','human_correction','human_reason'])
    assert master_hashes(S)==before
    state=read_json(S.path/'执行状态.json')
    state.setdefault('prior_human_review_600_protocol',state.get('human_review',{}))
    if not state.get('full_corpus_review',{}).get('calibration_received'):
        state.update(stage='FULL_CORPUS_AWAITING_30_HUMAN_CALIBRATION',current_protocol='full-corpus-calibrated-AI-v1',
            current_research_record='48_全量编码与30加30人机协作审核_20261019.md')
        state['full_corpus_review']=dict(registration=PREFIX+'review_registration_001.json',target_rows=6526,
        calibration_packet=PREFIX+'calibration_packet_001.json',calibration_expected=30,calibration_received=0,
        validation_holdout=held_name,validation_expected=30,validation_received=0,
        AI_project_final_authorized=True,all_rows_human_review_required=False,full_corpus_coding_complete=False,
        baseline_AI_proposals=600,baseline_AI_proposals_are_not_calibrated_final_labels=True,
        audit_accuracy_measured=False,raw_master_unchanged=True,
            work_queue=PREFIX+'work_queue_001.json',
            required_human_action='审核全量编码_20261019/01_首批30条校准.md；聊天回复全部认可或按编号修正')
        state['human_review']=dict(protocol='full-corpus-calibrated-AI-v1',calibration_expected=30,
            calibration_received=0,validation_expected=30,validation_received=0,
            all_rows_human_review_required=False,AI_project_final_authorized=True,
            required_action=state['full_corpus_review']['required_human_action'])
        state['all_rows_human_acceptance_required']=False
        state['delivery_status']='FULL_CORPUS_HUMAN_CALIBRATION_PENDING'
    from observer.core import write_json
    write_json(S.path/'执行状态.json',state)
    print('已准备30条校准：每副本10条；另封存30条核验，与校准无重合。人审结果0条；原数据未改。')
    print(str(OUT/'01_首批30条校准.md'))


if __name__=='__main__':main()
