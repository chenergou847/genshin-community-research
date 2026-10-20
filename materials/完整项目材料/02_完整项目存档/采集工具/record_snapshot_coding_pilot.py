"""Record read-and-reasoned AI pilot proposals; never mark human final=yes."""
from collections import Counter
import hashlib
import json
from observer.core import Study, GateError, digest, read_csv, read_json, write_csv
from observer import small
from observer.snapshot_sample import master_hashes


LABELS=[]
def add(mode,ident,rel,themes,selfthemes,kind,evidence,reason,problem='none_explicit',sentiment='neutral',flags='',limits=False,conditions='',action='',outcome='',difficulty='not_specified',problem_themes=''):
    LABELS.append(dict(mode=mode,id=ident,relevance=rel,themes=themes,self_experience_themes=selfthemes,
        experience_kind=kind,evidence=evidence,reason=reason,problem_status=problem,problem_themes=problem_themes,
        sentiment=sentiment,content_flags=flags,context_status='checked_with_limits' if limits else 'checked',
        conditions=conditions,action=action,outcome=outcome,difficulty=difficulty,
        theme_status='unknown' if rel=='unknown' else 'known',reviewer='Codex_AI_initial_coding',review_kind='ai_proposal',final='no'))

add('abyss','320938363424','irrelevant','','','social_or_meta','苦也 这也','祖先是粉丝数玩梗；本条未表达副本、配队或通关体验。')
add('abyss','320930281520','related','roster_build','roster_build','firsthand_report','感觉又能玩了','明确自述这期使用旧角色配队，评价伤害与可玩性；奇域测得的12w不能作为本期深渊实测数据。',sentiment='positive',flags='off_mode_benchmark',conditions='自述老3+1凌华；另提及奇域测试',action='本期更换配队',outcome='自述伤害较高、旧角色又能玩')
add('abyss','317372849121','related','roster_build;damage_threshold','roster_build;damage_threshold','help_request','没输出不知道怎么过呢','包含本人的输出不足及通关求助；没有明确机制原因，不能诊断为副本数值或角色设计问题。',problem='current_reported',sentiment='negative',conditions='原文：下半月感电',outcome='自述不知如何通关',problem_themes='damage_threshold')
add('abyss','317260396977','related','roster_build','','strategy_advice','下半砂糖换莱能压住冰锅','结合父评论的配队求助，属于角色替换建议；并未自述本人卡关或验证操作。',conditions='下半；砂糖换莱',action='建议替换角色',outcome='建议者声称能压住冰锅',flags='ancestor_image_unread',limits=True)
add('abyss','320929118128','irrelevant','','','social_or_meta','[崩坏3_划水]','父评论与回复均为无明确玩法内容的互动表情；不从视频标题推定体验态度。',sentiment='unknown')
add('abyss','317288880161','related','roster_build','','evaluation_or_comparison','持有率太高了','明确讨论本期角色使用率及好友配置，保留为玩法相关比较；不是本人通关体验，也不采信使用率和装备截图为已核实统计。',sentiment='unknown',flags='community_statistic_unverified',conditions='本期使用率讨论；举好友装备配置为例')
add('abyss','320883454704','related','roster_build','','strategy_advice','上半月感电带冰主','本条面向他人继续建议上下半配队；不将祖先中他人的失误或本人早先文字自动继承成本条受阻经历。',conditions='上半、下半配队建议',action='推荐角色组合',outcome='建议者声称可快速通过',flags='ancestor_image_unread',limits=True)
add('abyss','320987902368','irrelevant','','','social_or_meta','你这话串的太明显了','沿祖先是跨游戏立场和删评争论；当前回复没有本期副本体验内容。')
add('abyss','317209071585','irrelevant','','','social_or_meta','别影响到你心情就好','当前发言是对争论的安抚；虽更早祖先讨论操作，本条未继续表达副本体验，不把祖先观点算给当前发言。')
add('abyss','320921530544','related','roster_build','','strategy_advice','偶尔给教官的作用','父评论问行秋的作用，本条解释配装辅助价值；有明确玩法内容，但未陈述本人困难。')

add('theater','315730024865','irrelevant','','','off_mode','打个深渊打个n4','当前正文明确谈深渊和N4，没有可读的本期剧诗体验；父评论只有角色图，不能据标题补成剧诗反馈。',flags='cross_mode;ancestor_image_unread',limits=True)
add('theater','319275768640','unknown','','','ambiguous','最快的一次越狱','文字含快速完成与不明过程，但“越狱”具体对应内容尚不能确认，图片未读；保留不明，不直接编码为剧诗太简单或机制不清。',sentiment='unknown',flags='image_unread;slang_unresolved',limits=True)
add('theater','316956178209','related','buff_and_route','','strategy_advice','冻结祝福这套路是真稳','本期冻结路线评价可识别；卡第7幕、角色池不足明确是“上回”，不算本期第一手困难。夹带账号交易平台名称，标疑似推广，不能据此认定真人或广告账号。',sentiment='positive',flags='suspected_commercial_content;retrospective_experience',conditions='冻结祝福、水冰双元素；旧经历另标',outcome='当前部分声称路线稳定',problem='retrospective_only')
add('theater','320847911728','irrelevant','','','content_request','该更10月的深渊了','催更另一个副本内容，不是本期剧诗体验反馈。',flags='cross_mode')
add('theater','320816262192','irrelevant','','','platform_meta','防吞评','涉及评论发布，不是游戏内界面或副本技术问题。')
add('theater','315621236001','related','roster_build;damage_threshold','roster_build;damage_threshold','firsthand_report','我领了也打不过','父评论明确说领瑞希命座再打剧诗；本条自述领取后仍未能通关，但不能从中推定失败机制。',problem='current_reported',sentiment='negative',conditions='领取命座后',outcome='自述仍打不过',problem_themes='damage_threshold')
add('theater','319283906368','unknown','','','ambiguous','[脱单doge]','根评论只有表情，无可恢复的具体指向；不自动当作正向反馈或无关项。',sentiment='unknown',limits=True)
add('theater','319846622624','unknown','','','ambiguous','[巧克甜恋_挠挠]','根评论只有表情，无法核定与玩法的相关性或评价。',sentiment='unknown',limits=True)
add('theater','319448744784','related','roster_build','','strategy_advice','借主c会更好','沿祖先可确定是借用角色和配队讨论；本条为建议，不把父评论借角色使用时机的问题继承为本人的受阻。',flags='ancestor_image_unread',limits=True,action='建议借主C')
add('theater','315713207649','related','mechanic_understanding','','mechanism_tip','第9关有个自挂火得','提供关卡元素机制提示；没有自述困难，不据视频标题“满地找火”给本条补出负面体验。',conditions='第9关；自挂火',action='提示可利用的机制')

add('stygian','315522586593','related','roster_build;other_current_experience','roster_build;other_current_experience','firsthand_report','n5过了','本人与求配队根评论作者一致，自述调整一三间配队后N5通过；这条是通关结果，不自动等于仍有难度问题。',flags='ancestor_image_unread',limits=True,difficulty='N5_explicit',action='调整一三间角色组合',outcome='自述N5通关')
add('stygian','315958262449','irrelevant','','','social_or_meta','继续懒下去退游吧','针对他人未养角色的调侃，当前文字未给出本期幽境表现或体验；不能编码成养成成本太高。',flags='ancestor_image_unread',limits=True)
add('stygian','320159850736','related','roster_build;damage_threshold;reward_motivation','','expectation_or_intention','这期N5总算可以拿到羽毛了','基于视频预期自己的配置能通关并取得奖励；“可以”尚不能确认为已打通或已领取。',sentiment='positive',difficulty='N5_explicit',conditions='自称满命魈',outcome='预期获得羽毛；未核定已实现')
add('stygian','317352475521','related','roster_build','roster_build','own_account_condition','无了','父评论问是否还有其他主C，本条作者与配置求助根作者一致，回答没有其他选择；账号条件可识别，但没有明确说已经打不过。',flags='ancestor_image_unread',limits=True,conditions='自述没有其他主C',problem='none_explicit')
add('stygian','320978295120','irrelevant','','','social_or_meta','狠狠清算当初的那些区','文字是角色舆论立场表达，未说明本期玩法过程或评价；不凭相关视频标题补内容。')
add('stygian','315582970401','related','roster_build','','evaluation_or_comparison','龙王依旧强势','在明确本期幽境攻略视频下评价角色表现，文字已足够识别主题；未读图片，不记录面板、成绩或本人通关，也不等同对副本整体满意。',sentiment='positive',flags='image_unread;sentiment_targets_character',limits=True)
add('stygian','320355184160','irrelevant','','','retrospective_off_mode','入坑时第一个up是魈','描述早期打狼经历，非本期幽境；“12分钟”不能作为本期副本耗时证据。',flags='retrospective_experience;cross_mode')
add('stygian','320986117472','related','roster_build','','configuration_data','面板如下','作为本期实录作者的配置补充，“面板”足够识别配置主题；图片未读，所以不填具体数值、难度或成绩。',flags='image_unread',limits=True)
add('stygian','319241551296','related','roster_build;damage_threshold','roster_build;damage_threshold','help_request','我打不过这老头','当前自述通关受阻并说明只有某角色，属于本期求助；原因仍待配置和操作核验。',problem='current_reported',sentiment='negative',conditions='自称只有法尔伽',outcome='自述打不过本期敌人',problem_themes='damage_threshold')
add('stygian','317369229617','irrelevant','','','social_or_meta','恨比爱长久吗','泛角色立场调侃，不构成本期副本体验证据。')

add('abyss','320983359392','irrelevant','','','social_or_meta','鸣潮纯纯路边','父正文缺失，但本条自身是泛跨游戏评价，未陈述任何本期深渊体验；按可读正文判无关，仍保留缺父限制，不推测上文。',flags='missing_ancestor;cross_game_meta',limits=True)


THEMES=[
 ('roster_build','角色池、配队与养成条件','角色覆盖、练度、命座装备、角色替换、借用、配队功能及本期角色表现。','只出现角色名的粉圈争论；未指向本期的旧经历。','317372849121;319448744784;317352475521'),
 ('damage_threshold','通关门槛与难易感受','明确打不过、输出不足、通关难易或对难度的预期；需区分预期与已发生。','单纯报通关不自动编码为困难；不据标题给评论补难度。','317372849121;315621236001;319241551296'),
 ('mechanic_understanding','机制信息与理解','机制触发、克制、说明、可利用条件与机制理解；中性提示也可编码。','只推荐角色而未谈机制；评论区发布异常。','315713207649'),
 ('operation_control','操作与控制体验','走位、连招、聚怪、锁定、容错或操作执行的明确描述。','祖先提到操作但当前仅安抚或玩梗；仅从攻略失败推定机制错误。',''),
 ('encounter_timing','敌人与战斗时序','位移、转阶段、无敌、动画、刷新、战斗时间限制造成的体验。','未说明来源的难；旧大世界打狼耗时。',''),
 ('buff_and_route','增益与路线决策','祝福、圣牌、选取/获取增益、角色出战与关卡路线等策略；只有明确随机时才记录随机问题。','角色养成配置单独归roster；选择不当不自动认定系统故障。','316956178209'),
 ('retry_time_cost','重试与流程成本','反复重开、准备切队、单次与累计耗时、失败恢复成本。','仅说打不过但未谈重试或时间；旧期耗时。',''),
 ('reward_motivation','奖励与参与动机','奖励目标、兑现预期、领取、参与或放弃动机。','视频投币点赞感谢；尚未领取不能写成已领取。','320159850736'),
 ('co_op_social','联机与互助体验','匹配、队友协作、互助过程、角色借用的社交可得性。','单纯借主C配队建议先归roster；辱骂或粉圈立场不自动归联机。',''),
 ('technical_interface','游戏性能与界面','本期副本中的卡顿、崩溃、输入或界面可用性。','防吞评、B站加载、平台删评；这些不是游戏内故障。',''),
 ('other_current_experience','其他本期体验','明确与本期玩法相关但上述主题未覆盖的体验与通关结果。','完全无语义表情用unknown；已可判断无关的聊天用irrelevant。','315522586593')]


if __name__=='__main__':
    s=Study('正式采集_小样本v1_20261018')
    queue=s.frozen('small_snapshot_coding_pilot_queue_001.json')
    frame=s.frozen('small_snapshot_frame_001.json');draw=s.frozen('small_snapshot_supplement_draw_001.json')
    material=read_json(s.path/'small_snapshot_coding_pilot_material_001.json')
    materials={(r['mode'],r['id']):r for r in material['items']}
    expected={(r['mode'],r['id']) for r in queue['selected']+queue['diagnostics']}
    assert len(LABELS)==len(expected)==len({(r['mode'],r['id']) for r in LABELS})
    assert {(r['mode'],r['id']) for r in LABELS}==expected
    known={x[0] for x in THEMES}
    for row in LABELS:
        topics=set(filter(None,row['themes'].split(';')))
        assert topics<=known
        assert set(filter(None,row['self_experience_themes'].split(';')))<=topics
        assert set(filter(None,row['problem_themes'].split(';')))<=topics
        assert row['relevance']=='related' or not topics
        assert row['evidence'] in materials[(row['mode'],row['id'])]['text']
        assert row['final']=='no' and row['review_kind']=='ai_proposal'
    result_name='small_snapshot_coding_pilot_result_001.json'
    if (s.path/result_name).exists():
        print(json.dumps(s.frozen(result_name)['summary'],ensure_ascii=False));raise SystemExit(0)
    master_before=master_hashes(s)
    coding_path=s.path/'small_snapshot_supplement_coding.csv';coding=read_csv(coding_path)
    assert len(coding)==600 and not any(r.get('final')=='yes' for r in coding)
    before=small.seal(s,'small_snapshot_coding_before_pilot_001.json',dict(rows=coding,draw_hash=digest(draw)))
    codebook=dict(version='snapshot-codebook-v0.1-AI-DRAFT',status='AI_PROPOSAL_NOT_HUMAN_APPROVED',
        reviewer='Codex_AI',unit='one_selected_comment_ID; ancestors_disambiguate_without_inheriting_their_claims',
        relevance_rules=dict(related='可读正文及必要祖先明确指向目标副本本期玩法、配置、攻略、结果或评价；策略讨论可相关但与本人经历分开。',
            irrelevant='可判断为跨副本、旧大世界经历、平台发评、催更、社交/粉圈而无本期玩法内容。',
            unknown='无法判断指向、纯表情缺语境或必要图片/上文不可读；不得按视频标题补出体验。'),
        context_rules='核对祖先、自述者身份、指向的玩法和期次；不把父评论说法继承为当前作者观点。图片未读不填图中数值，文字足够时可判主题。',
        uncertainty_rules='相关性不明与已知相关但主题不明分开；不明不补抽。缺父不自动等于不明，正文足够可正常判断。',
        first_person_rules='明确自述本人实际对局、操作、结果或账号条件才记self；预期、建议、他人经历及旧期经历不冒充本期实战。自述仅为评论主张，不代表事实已核实。',
        problem_rules='themes表示话题，不自动表示问题。仅本期明确受阻/不满用current_reported及problem_themes；建议、角色强弱、预期奖励与旧期卡点不能直接变成本期问题。',
        commercial_rules='疑似推广单独标记，不凭一个平台名称判机器人。含可识别相关文字可记相关，但不把推广自述采信为真实第一手证据；后续报告排除此标记的敏感性。',
        sentiment_rules='仅按当前发言可识别的评价记录；角色强度赞许注明目标，不解释为副本整体满意；不从表情或通关结果自动推定态度。',
        themes=[dict(id=k,label=label,definition=inc,include=inc,exclude=exc,observed_pilot_IDs=list(filter(None,examples.split(';')))) for k,label,inc,exc,examples in THEMES],
        method_sources=['https://doi.org/10.1177/1525822X980100020301','https://aapor.org/standards-and-ethics/disclosure-standards/'],
        all_codes_AI_initial_only=True,intercoder_reliability_measured=False,thematic_saturation_claimed=False)
    cb=small.seal(s,'small_snapshot_codebook_proposal_001.json',dict(codebook=codebook,queue_hash=digest(queue)))
    proposal=small.seal(s,'small_snapshot_coding_pilot_proposals_001.json',dict(rows=LABELS,codebook_proposal_hash=digest(cb),
        draw_hash=digest(draw),queue_hash=digest(queue),human_final_count=0))
    by={(r['mode'],r['id']):r for r in LABELS}
    for row in coding:
        if (row['mode'],row['id']) in by:
            source=by[(row['mode'],row['id'])]
            row.update({k:source[k] for k in small.CFIELDS if k in source})
            row['notes']='AI试编码，待人工核定；problem_status='+source['problem_status']+'；flags='+source['content_flags']
    write_csv(coding_path,coding,small.CFIELDS)
    review=[]
    for row in LABELS:
        item=materials[row['mode'],row['id']]
        review.append(dict(mode=row['mode'],id=row['id'],role=item['role'],bvid=item['bvid'],text=item['text'],
            parent_context=' | '.join(a['text'] if a['available'] else '[正文缺失]' for a in item['ancestors']),
            ai_relevance=row['relevance'],ai_themes=row['themes'],ai_self_themes=row['self_experience_themes'],
            ai_problem_status=row['problem_status'],ai_problem_themes=row['problem_themes'],ai_reason=row['reason'],ai_flags=row['content_flags'],
            human_relevance='',human_themes='',human_self_themes='',human_problem_status='',human_notes='',reviewer='',final='no'))
    write_csv(s.path/'small_snapshot_coding_pilot_review_001.csv',review,list(review[0]))
    pilot_keys={(r['mode'],r['id']) for r in queue['selected']}
    pilot=[r for r in LABELS if (r['mode'],r['id']) in pilot_keys]
    summary=dict(pilot_rows=len(pilot),diagnostic_rows=len(LABELS)-len(pilot),AI_proposals=len(LABELS),human_final=0,
        pilot_relevance_counts=dict(Counter(r['relevance'] for r in pilot)),
        per_mode={m:dict(Counter(r['relevance'] for r in pilot if r['mode']==m)) for m in ('abyss','theater','stygian')},
        primary_coding_pending_without_proposal=sum(r.get('relevance')=='pending' for r in coding),
        retained_sample_rows=len(coding),population_proportions_computed=False,AI_accuracy_or_agreement_not_measured=True)
    assert master_hashes(s)==master_before
    assert s.frozen('small_snapshot_supplement_draw_001.json')==draw
    assert {(r['mode'],r['id']) for r in coding}=={(r['mode'],r['id']) for r in before['rows']}
    assert all(r['final']=='no' for r in coding)
    result=small.seal(s,result_name,dict(summary=summary,proposal_hash=digest(proposal),codebook_proposal_hash=digest(cb),
        draw_hash=digest(draw),master_file_sha256=master_before,only_mutable_coding_worktable_updated=True))
    print(json.dumps(result['summary'],ensure_ascii=False))
