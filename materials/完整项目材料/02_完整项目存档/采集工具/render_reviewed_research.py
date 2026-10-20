"""Evidence extraction and clearly qualified reports for the reviewed snapshot."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from observer.core import digest, read_csv, write_csv, write_json, NAMES
from observer import small
from observer.snapshot_sample import master_hashes
from review_snapshot_labels import data, S, public_text

THEME_LABELS={
    'roster_build':'角色池、配队与养成条件','damage_threshold':'通关门槛与难易感受',
    'mechanic_understanding':'机制信息与理解','operation_control':'操作与控制',
    'encounter_timing':'敌人与战斗时序','buff_and_route':'增益、出战及获取/路线决策',
    'retry_time_cost':'重试与流程成本','reward_motivation':'奖励与参与动机',
    'co_op_social':'联机、借角与互助','technical_interface':'游戏性能与界面',
    'other_current_experience':'其他本期体验'}

CARDS=[
 dict(id='P1',name='深渊：处理机制前提不清，难以解释失败',modes=['abyss'],cases=[82,93,129,130,142,184],counter=[147,161,183],
      condition='遇到元素盾、冻结/挂冰条件或阶段机制，需要把反应体系和敌人状态对应起来。',
      impact='有发言自述一早上重试、当时未想到解法，或同一反应队在不同半间均遇盾受阻。',
      interpretation='值得核对信息是否便于转成操作判断；不能把“没理解”直接解释为机制错误，也不能据此排除练度因素。',
      operation='制作本期敌人“现象→所需条件→可替代角色/操作→不生效时先查什么”FAQ，附失败与成功片段，先经实测核对。',
      validation='用可比配置回放核对敌方状态、元素附着和操作；再观察新/回归玩家能否正确说明触发条件及失败原因。',
      priority='先做机制问答与反馈分诊',limitation='核心机制疑问集中在一个大来源；两条来自同作者同线程，不能当独立验证。'),
 dict(id='P2',name='剧诗：想保留的角色与实际可用时点错位',modes=['theater'],cases=[224,231,236,239,242,267,270,279,291,304,308,312,338,375],counter=[239,323,375],
      condition='要兼顾前关可通关、后关元素/队伍需求、借角次数和角色抽取/复活。',
      impact='出现最后关无冰、借来的角色始终没抽到、雷队友争用，以及中途重开的自述。',
      interpretation='角色池宽度、主动规划和抽取结果可能共同作用；目前不能把全部重开归咎随机，也未核验抽取概率。',
      operation='提供终局需求提示与“建议保留的元素/主C/队友”规划模板；FAQ先说明借角何时锁定、回溯能改什么，避免未经核验的概率说法。',
      validation='记录每幕可用角色、选择、剩余出战次数、回溯和失败原因；比较“总池不足”“留人决策失误”“获取时点不合”三种情况。',
      priority='先做出战规划与借角/回溯说明',limitation='这些细节全部来自同一个剧诗视频，且有同线程互动，不能证明跨UP普遍存在。'),
 dict(id='P3',name='剧诗：奖励已拿到，满花或集牌仍带来较高重试成本',modes=['theater'],cases=[226,227,231,258,272,275,277,294,307,312,327,330,344,346,350,360],counter=[239,240,289,340,354],
      condition='玩家目标可能是原石、满花、理想终局队或不重复的牌；这些目标不能混成一个通关目标。',
      impact='有人拿满原石后放弃更高目标，也有人为角色顺序、满花或新牌持续重开数小时。',
      interpretation='反馈更像目标层次与额外投入的取舍；耗时自述不等于平均时长，跨日也不等于连续游玩。',
      operation='把攻略按“拿主要奖励 / 满花 / 集牌或挑战偏好”分层，说明额外要求和可选性；为高成本玩家提供停止点和回溯检查项。',
      validation='分别测量目标识别正确率、达到各目标的耗时/重开数、停止原因和主观负担，同时保留“重开仍有趣”的玩家。',
      priority='先改目标分级表达，后验证流程改动',limitation='直接耗时自述集中在同一来源；这是选定评论中的表述，不是玩法平均完成时长。'),
 dict(id='P4',name='幽境：挂雷、转盾和破机制的条件难以核对',modes=['stygian'],cases=[405,441,449,463,464],counter=[441,445,446,492],
      condition='玩家期待技能挂元素或转盾，但当前敌人状态、伤害/命中条件与角色技能触发前提可能不同。',
      impact='出现“不索敌”“不转伤害盾”的提问；也有跟攻略过关后仍不能解释组合差异的自述。',
      interpretation='存在可追踪的理解或反馈线索；现有评论不能证明索敌系统有BUG，也不能据此确定哪条前提未满足。',
      operation='将这些反馈分为“技能是否触发—是否命中—是否附着—敌方是否接受机制”几个排查节点，建立带前提的FAQ与反馈模板。',
      validation='收集带敌人状态和技能触发画面的短回放，按固定组合复现；核对难度、技能触发前提与机制提示，再确认是否需研发排查。',
      priority='优先收集可复现回放并核查机制解释',limitation='跨两个来源有相似疑问，但没有同条件实测；“相似表述”不等于同一故障。'),
 dict(id='P5',name='幽境：攻略复现受配装、能量和敌人动作影响',modes=['stygian'],cases=[560,589,593,597],counter=[560,571,492],
      condition='需要重复循环或特定轴，玩家自述充能、元素底和站位与预期不一致。',
      impact='详细案例包含风场、敌人后跳、额外E吃球和多轮轴失配；另有人反复调装备或十小时尝试后才完成。',
      interpretation='先比对完整配置与操作前提，再讨论容错或机制问题；自称“一样的配置”不能视作已经验证等同。',
      operation='攻略附上等级/命座/武器及精炼/套装/充能/队友配置/能量来源/起手状态/站位/关键动作检查表；把理想轴与可容错替代轴分开。',
      validation='对照同一配置与不同充能、站位、敌方动作的回放；记录每轮能量、技能命中和失败节点，先验证可复现性。',
      priority='先做攻略前提表与排错回放',limitation='完整“风场+后跳+充能”组合只有一个详细案例，不能称为普遍缺陷；其他案例只是相关线索。'),
 dict(id='P6',name='多副本：关键辅助在多队之间争用',modes=['abyss','theater','stygian'],cases=[10,105,224,267,555],counter=[183,323,445,553],
      condition='需要同时组多队，玩家希望同一辅助服务不同主C/反应体系。',
      impact='出现“拆成两份/三份”、两队争一个雷队友等表述；有人通过替代配置完成，有人只能舍弃原组合。',
      interpretation='是配队资源分配约束的证据，尚不能推出该角色必抽、所有队伍必须绑定或应该直接降低难度。',
      operation='补充按“缺关键辅助/缺后台元素/缺主C”区分的替代队伍矩阵，说明最低前提及牺牲项；避免一句“随便过”代替可比配置。',
      validation='用明确角色池分层核对替代队是否能达到相同目标，统计可行队数量和首次独立配队成功情况。',
      priority='和机制/攻略内容一起处理',limitation='跨副本有不同来源，但各窗口与评论主题不同，不能合并成全体玩家的争用比例。'),
 dict(id='E1',name='拓展观察：寻求代打后的沟通不适',modes=['theater'],cases=[293],counter=[],
      condition='玩家因早关烦躁寻求代打，对方持续评价其账号选择。',
      impact='玩家自述不舒服并拉黑对方。',interpretation='这是帮助过程中的沟通线索，不是游戏内联机机制缺陷。',
      operation='若运营互助栏目，可设定尊重账号选择、先确认目标与配置、避免羞辱性归因的沟通模板。',
      validation='核对双方上下文并寻找更多独立案例；当前不能推断代打群体行为。',priority='补充记录，暂不列核心产品改动',limitation='只有一名作者的单次自述，证据很弱。')]

def pc(x):return '—' if x is None else f'{100*x:.1f}%'
def interval(x):return '—' if x is None else f'{100*x[0]:.1f}%—{100*x[1]:.1f}%'

def main():
    f,draw,L,v,original=data();review=S.frozen('small_snapshot_ai_review_001.json');est=S.frozen('small_snapshot_AI_exploratory_estimates_001.json')
    rows=review['rows'];byk={k:r for k,r in enumerate(rows,1)};byid={r['id']:r for r in rows}
    materials={(r['mode'],r['id']):r for r in read_csv(S.path/'small_snapshot_supplement_main_material.csv')}
    notes={}
    for line in Path('problem_case_notes_001.txt').read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():continue
        k,condition,impact,coping,outcome,limits=line.split('|');k=int(k);assert k not in notes
        notes[k]=dict(condition=condition,impact=impact,coping=coping,outcome=outcome,limits=limits)
    expected={k for k,r in byk.items() if r['problem_status']=='current_reported'}
    assert set(notes)==expected and len(notes)==76
    cases=[]
    for k,detail in notes.items():
        r=byk[k];raw=L[r['id']];meta=materials[r['mode'],r['id']]
        cases.append(dict(index=k,mode=r['mode'],副本=NAMES[r['mode']],id=r['id'],bvid=r['bvid'],url=meta['url'],text=public_text(raw['text']),
            problem_themes=r['problem_themes'],root_id=raw['root_id'],sample_weight=meta['relative_weight'],
            **detail,coding_status='AI_REVIEWED_PROVISIONAL',mechanics_verified=False,human_final=False))
    caseobj=dict(review_hash=digest(review),rows=cases,unit='utterance_not_independent_incident',extraction='explicit_per_ID_AI_reading; unspecified fields remain unspecified',human_reviewed=False)
    casefile='small_snapshot_problem_cases_AI_001.json'
    if not (S.path/casefile).exists():small.seal(S,casefile,caseobj)
    else:assert S.frozen(casefile)['rows']==cases
    write_csv(S.path/'small_snapshot_problem_cases_AI_001.csv',cases,list(cases[0]))
    cardrows=[]
    for c in CARDS:
        selected=[byk[k] for k in c['cases']]
        assert all(k in expected for k in c['cases'])
        raw=[L[r['id']] for r in selected]
        c.update(evidence_IDs=[r['id'] for r in selected],counterexample_IDs=[byk[k]['id'] for k in c['counter']],
            evidence_utterances=len(selected),different_videos=len({r['bvid'] for r in selected}),
            different_authors=len({r['author_id'] for r in raw}),different_threads=len({(r['bvid'],r['root_id']) for r in raw}),
            prevalence_estimated_for_this_card=False,human_confirmed=False,mechanism_causality_verified=False)
        cardrows.append(c)
    cards_name='small_snapshot_problem_cards_AI_001.json'
    if not (S.path/cards_name).exists():small.seal(S,cards_name,dict(review_hash=digest(review),cards=cardrows,categories_not_new_exhaustive_statistical_codes=True))
    else:assert S.frozen(cards_name)['cards']==cardrows
    P=S.path.parent.parent
    reltable='\n'.join(f"| {NAMES[m]} | {d['label_counts'].get('related',0)} / {d['label_counts'].get('irrelevant',0)} / {d['label_counts'].get('unknown',0)} | {pc(d['weighted_label_shares'].get('related',0))} | {pc(d['weighted_label_shares'].get('unknown',0))} |" for m,d in est['domains'].items())
    anytable='\n'.join(f"| {NAMES[m]} | {d['metrics']['reported_problem_any']['sample_positive']} / {d['metrics']['reported_problem_any']['sample_known_denominator']} | {pc(d['metrics']['reported_problem_any']['proportion'])} | {interval(d['metrics']['reported_problem_any']['interval95'])} | {interval(d['metrics']['reported_problem_any']['unknown_extreme_scenario_bounds'])} |" for m,d in est['domains'].items())
    def themetable(field):
        body=[]
        for t,label in THEME_LABELS.items():
            entries=[]
            for m in NAMES:
                x=est['domains'][m]['metrics'][field+'.'+t]
                entries.append('未观测到，不推断为0' if x['sample_positive']==0 else pc(x['proportion'])+('†' if x['sparse_support_flag'] else ''))
            body.append('| '+label+' | '+' | '.join(entries)+' |')
        return '\n'.join(body)
    sensnames={'audience_only':'仅观众发言','roots_only':'仅根评论','replies_only':'仅楼中楼','exclude_largest_source':'去除窗口正文最多的视频','exclude_largest_uploader':'去除相关估计贡献最大的UP','exclude_largest_thread':'去除相关贡献最大的线程','exclude_suspected_commercial':'去除疑似推广','text_without_own_or_ancestor_image':'仅不含未读图限制的发言','allow_ambiguous_mixed_video_role_discussion':'将混合视频的含混角色讨论判为相关'}
    senstable='\n'.join('| '+label+' | '+' | '.join(pc(est['domains'][m]['sensitivity'][key]['reported_problem_any']['proportion']) for m in NAMES)+' |' for key,label in sensnames.items())
    source_table='\n'.join(f"| {NAMES[m]} | {pc(d['largest_source_frame_share'])} | {pc(d['largest_related_source_share'])} | {pc(d['largest_related_thread_share'])} |" for m,d in est['domains'].items())
    report44=f'''# 标签AI复核与加权反馈比例（探索版）

日期：2026-10-19，北京时间。用户要求“核验标签，再提炼问题、计算反馈比例”后，已逐条复读600条正文、重点复查语境，修订30条，提取76条明确受阻/不满候选，并完成加权计算与敏感性分析。**这是同一AI的第二轮复核，不是人工或独立编码者核验；未测量分类准确率。**原人工定稿门槛仍保留，以下是条件于AI标签的探索估计，不是最终经人工审核的统计结论。

可复用任务描述：在原600个ID、原时间窗和最终权重不变的前提下，核查相关性、期次、副本、本人经历与问题归因；保留不明，提取问题情境/影响/应对/结果，并估计固定60来源、已保存窗口发言中的主题与明确受阻表述比例，同时报告区间、不明影响和来源依赖。

## 最先需要知道的结果

- 已判相关的讨论主要涉及配队、角色池和养成；相关讨论包含建议、比较、账号条件和实际经历，不能全叫“体验问题”。
- 明确受阻表述在已判相关且受阻状态可判断的发言中，估计占深渊10.1%、剧诗26.0%、幽境21.6%。**分母是发言，不是玩家，也不是所有实际挑战次数。**
- 剧诗增益/出战/获取受阻及重试成本值得核查；幽境机制状态和攻略复现条件有具体可追溯案例。问题卡与反例见[45号问题分析](45_体验问题证据与改进验证_20261019.md)。
- 剧诗来源集中、不明较多；不据三个点估计给副本体验排好坏。范围始终是原60条视频的6526条已保存窗口正文，不能推广到所有合格候选、全B站评论或全体玩家。

## 标签复核改了什么

原初判432相关/128无关/40不明，修订后417相关/125无关/58不明。原31条试编码也纳入本轮复核，保留历史提案不覆盖。新增不明不是新采到的评论，而是收紧既定证据边界。

| 副本 | 抽中发言：相关/无关/不明 | 全部窗口正文中“已判相关”估计 | 全部窗口正文中“不明”估计 |
| --- | ---: | ---: | ---: |
{reltable}

主要修订：混合副本视频中无法定位到幽境的角色讨论转为不明；泛夸赞统一保留对象不明；“之前”不等于已证实上期；配装或持有情况不自动算本期卡关；“红温”不自动算操作故障；“极限”不自动算耗时；两条含混情绪的受阻状态单独记不明。所有修改有旧值、新值与理由。

本轮按口径逐条复核不是独立重编码。570条未修改不能解释为95%准确率或一致率，30条修改也不能解释为分类错误率。

## 明确受阻表述比例

定义：本条明确自述本期受阻或不满，包括后来已解决的卡点；单纯问配置、给建议、推测未来、一般设计批评不算本人受阻。76条候选为深渊15、剧诗37、幽境24。另有2条已判相关但受阻方向不明（深渊/幽境各1），不会强记“没问题”。

| 副本 | 样本中受阻/可判断相关发言 | 加权估计 | 名义约95%抽样区间 | 不明归属极端情景范围 |
| --- | ---: | ---: | --- | --- |
{anytable}

第四列只反映给定标签、给定保存框下的抽样误差；第五列将所有相关性/受阻状态不明发言分别作最有利与最不利归属，是情景范围，**没有并入抽样误差，不是另一个95%区间**。两列均不补回未保存、被删或未检出的评论。

上述主要指标的近似区间最大单侧偏离点估计均在10个百分点内；这不等于整个项目达到“总误差±10个百分点”。稀疏主题、不明、误分类和覆盖遗漏仍存在。

## 讨论主题：不等于负面问题

分母：相关且主题可判定的发言，采用最终N/m权重。同一发言可多主题，合计不要求100%。以下点估计的完整区间、支持条数和不明情景范围见数据表。

| 讨论主题 | 深渊 | 剧诗 | 幽境 |
| --- | ---: | ---: | ---: |
{themetable('themes')}

†观察到的阳性或互补支持不足5条，标为稀疏，不据看似窄的近似区间宣称精度达标。零条只表示样本未观测到；非全查时返回保守0—100%区间，不宣称该问题不存在。

## 本人受阻涉及的主题

分母：相关且受阻状态可判断的发言；这是“发言包含某类受阻”的比例，不是“该角色/机制实际失败率”。多标签可重叠。比如剧诗增益类同时包含选角、出战规划和获取新牌，不能把14.0%缩写成纯粹的“随机抽角卡关率”。

| 受阻主题 | 深渊 | 剧诗 | 幽境 |
| --- | ---: | ---: | ---: |
{themetable('problem_themes')}

## 来源集中与敏感性

| 副本 | 最大视频占窗口框正文 | 最大视频占已判相关的加权估计 | 最大线程占已判相关的加权估计 |
| --- | ---: | ---: | ---: |
{source_table}

这里不能通过每个视频等权来“修好”集中度：目标是固定保存框中的发言比例，源视频本身就拥有大量正文。改成等视频权重会换研究对象。必须如实呈现集中，并另列改变子域后的结果。

下表都是“明确受阻表述”点估计。移除来源/UP、只看根或回复等会改变子域；它们是诊断，不是替换主估计或挑选更喜欢的数字。

| 敏感性情景 | 深渊 | 剧诗 | 幽境 |
| --- | ---: | ---: | ---: |
{senstable}

剧诗移除最大来源后约13.8%，主估计约26.0%，显示问题强度对该来源明显依赖。幽境根评论与楼中楼差别很大；根评论更常提问/求助、回复更常给建议是可检验的内容解释，当前尚未完成单独检验，不能写成确定原因。全部留一来源结果也已输出，不以此证明代表性。

## 计算口径与检查

每视频为固定层，层内无放回随机抽发言；权重w=N/m。主题/受阻比例是加权分子A除以相应的加权已知分母D。抽样方差用层内残差e=y−p·d的有限总体校正：`Σ[N²(1−m/N)s²(e)/m]/D²`。已全取的小来源不增加抽样误差。分层加权与有限总体校正依据[Statistics Canada分层抽样公式](https://www150.statcan.gc.ca/n1/pub/12-001-x/2019002/article/00006/02-eng.htm)。

区间在logit尺度采用Taylor方差及保守t临界值后转回比例尺度；参考[survey作者文档的比例区间方法](https://r-survey.r-forge.r-project.org/pkgdown/docs/reference/svyciprop.html)，此处用自行实现的残差方差和Satterthwaite自由度，并未调用R包。区间是逐指标近似，非所有主题联合95%保证。端点、零方差和稀疏支持另作保守标记。

不明情景：`[A/(D+U),(A+U)/(D+U)]`，U为相关性不明或本指标状态不明的加权量，不重复计数。剔除UP/线程或只看根评论时，样本单位仍在原层，以子域指标0处理；不重新计算N/m或缩短原抽样量。估计抽样误差须考虑实际设计，不能把600当简单随机样本直接套公式，见[Statistics Canada抽样误差说明](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch6/sampling-echantillonage/5214807-eng.htm)。

新增8项数值检查通过，含有限总体穷举验证加权均值与方差、子域零值保留、全取小层、零命中保守处理和不明分母。另核对600个ID、每副本200条、旧232条、最终权重和主档哈希不变。它们验证计算，不验证语义正确率或全站覆盖。

## 文件入口与当前状态

- [复核后600条标签](采集工具/正式采集_小样本v1_20261018/small_snapshot_ai_reviewed_coding_001.csv)、[30条修改轨迹](采集工具/正式采集_小样本v1_20261018/small_snapshot_ai_review_changes_001.json)。
- [全部24项指标×3副本的估计与区间](采集工具/正式采集_小样本v1_20261018/small_snapshot_AI_exploratory_estimates_001.csv)、[含留一来源结果的JSON](采集工具/正式采集_小样本v1_20261018/small_snapshot_AI_exploratory_estimates_001.json)、[敏感性数据](采集工具/正式采集_小样本v1_20261018/small_snapshot_AI_sensitivity_001.csv)。
- [76条问题候选的情境、影响、应对与结果](采集工具/正式采集_小样本v1_20261018/small_snapshot_problem_cases_AI_001.csv)、[45号问题分析与验证建议](45_体验问题证据与改进验证_20261019.md)。

AI复核、问题提炼与条件性比例计算已完成。人工定稿0，独立复核0，评论图片未读取，准确率/主题饱和度未验证。正式对外表达应保留“探索版、固定保存范围、评论比例”及上述主要局限，不写成全体玩家调查或已验证游戏缺陷。
'''
    (P/'44_标签AI复核与加权比例_20261019.md').write_text(report44,encoding='utf-8')
    card_sections=[]
    for c in cardrows:
        evidence=[]
        for k in c['cases'][:4]:
            r=byk[k];text=public_text(L[r['id']]['text']);text=text[:110]+('…' if len(text)>110 else '')
            evidence.append(f"- [{r['id']}](https://www.bilibili.com/video/{r['bvid']}/)：{text}")
        counter=[]
        for k in c['counter']:
            r=byk[k];text=public_text(L[r['id']]['text']);text=text[:100]+('…' if len(text)>100 else '')
            counter.append(f"[{r['id']}](https://www.bilibili.com/video/{r['bvid']}/)：{text}")
        card_sections.append(f"""## {c['id']} {c['name']}

**支持范围：**{c['evidence_utterances']}条发言、{c['different_authors']}名可区分作者、{c['different_videos']}条视频、{c['different_threads']}个根线程。这是选出的证据量，不是独立事件数或该问题发生率。

发生情境：{c['condition']}

直接影响：{c['impact']}

可追溯例证：

{chr(10).join(evidence)}

解释与边界：{c['interpretation']}

建议动作：{c['operation']}

验证方式：{c['validation']}

正向/反例：{'；'.join(counter) if counter else '本组未选到可直接配对的反例，不能因此认定没有。'}

证据局限：{c['limitation']}

处理顺序：{c['priority']}。这是基于可行动性与证据清晰度的建议，不是按总体发生率排序。
""")
    report45='''# 近期高难副本体验问题：证据、解释与验证（AI探索版）

日期：2026-10-19，北京时间。基于600条固定抽样发言的AI二次复核，保留76条本人明确受阻/不满候选，提炼6组主要线索和1项拓展观察。具体机制、因果和建议效果均未实测；人工与独立编码者均未定稿。

可复用任务描述：围绕深渊、剧诗和幽境的本期体验，把玩家原话、研究者解释和待验证原因分开；为每组问题说明发生条件、实际影响、既有应对、正向反例、证据集中度与下一步验证，使运营反馈能用于分诊和形成可检验的改进假设。

## 可交付的核心判断

优先改进的信息和内容方向有三项：机制前提与失败排查、剧诗出战/回溯/借角规划、攻略复现的完整配置和操作条件。它们都能从具体评论追溯，但目前不能据此认定需要直接降低数值、取消随机或修复BUG。

配队讨论占比较高，不能把“谈角色”写成“抱怨养成”；本人受阻表述与一般设计批评分开。后者仍保留在复核标签中，例如剧诗分散刷怪、幽境高配置门槛，但因未明确本人经历，未强塞入76条第一手受阻候选。

加权比例与名义区间见[44号统计报告](44_标签AI复核与加权比例_20261019.md)。下列问题卡不是新增的互斥分类，也未为每张卡估计发生率；可交叉引用同一条评论，不可把证据量相加当作人数。

'''+'\n'.join(card_sections)+'''
## 推荐的运营产出与验证次序

1. 先完成本期“机制前提与排错FAQ”以及“攻略配置/操作前提表”。把玩家说的现象、可能原因和已核实解法分栏；没有复现的写“待核”。
2. 为剧诗提供按目标分级的内容：拿主要奖励、满花、集牌/自选挑战分别说明；配套出战保留、借角时点和回溯作用的示例。先核查规则，不把评论里的概率或经验当官方机制。
3. 选择可提供回放且配置可核对的案例，先分清理解缺口、配装/角色条件、操作时序、敌人动作与实际异常，再形成给策划/研发的问题单。若做界面提示或流程改动，应先验证现有提示在哪一步未被理解。
4. 核对正向与反例：无攻略一次通过、替代角色通过、回溯有效、重开仍感有趣。改进目标是减少不必要的困惑和失控成本，不能先假设所有玩家追求相同目标。

以上是拟议动作和验证要求，没有实际招募玩家、做对照实验、向研发发单或上线改动，也没有已经降低流失/提高通关率的数据。作品集中可以写已完成检索、抽样、AI辅助编码、权重估计和证据分析；不能写成真实业务落地成果。

## 证据可用到什么程度

- 剧诗的选角和长时重试细节主要来自同一视频。来源集中说明需要保留外推边界，不能用同一个评论区的多人相似表达代替跨社区验证。
- 一个作者可连续解释同一次失败，根评论与楼中楼不等于独立事件。各卡列出作者和线程数以帮助识别重复，但作者数也不等于独立真实玩家人数。
- 问题不明原因不删，已解决的成本也不删；没有写出的配置、结果、失败次数统一记未说明。未读图片不补成绩。
- 76条逐条提取表及全部例证ID见[问题候选证据表](采集工具/正式采集_小样本v1_20261018/small_snapshot_problem_cases_AI_001.csv)；[问题卡结构数据](采集工具/正式采集_小样本v1_20261018/small_snapshot_problem_cards_AI_001.json)保留每组完整支持和反例。
'''
    (P/'45_体验问题证据与改进验证_20261019.md').write_text(report45,encoding='utf-8')
    diffflat=[]
    for x in review['changes']:
        diffflat.append(dict(index=x['k'],mode=x['mode'],id=x['id'],reason=x['reason'],changes=json.dumps(x['changes'],ensure_ascii=False)))
    write_csv(S.path/'small_snapshot_ai_review_changes_001.csv',diffflat,list(diffflat[0]))
    current=read_csv(S.path/'small_snapshot_ai_reviewed_coding_001.csv')
    assert len(current)==600 and all(r['final']=='no' for r in current)
    state=__import__('observer.core',fromlist=['read_json']).read_json(S.path/'执行状态.json')
    state.update(stage='AI_REVIEW_AND_EXPLORATORY_ANALYSIS_COMPLETE_HUMAN_FINAL_PENDING',current_research_record='44_标签AI复核与加权比例_20261019.md',
        coding_AI_review_completed=True,coding_completed=False,feedback_proportions_computed=True,
        feedback_proportions_status='AI_REVIEWED_EXPLORATORY_NOT_HUMAN_FINAL',formal_human_estimates_computed=False,
        analysis=dict(reviewed_rows=600,amended_rows=30,related=417,irrelevant=125,unknown=58,reported_problem_cases=76,
            main_problem_cards=6,exploratory_observation_cards=1,numerical_tests_passed=8,independent_coding_validation=False,
            estimates_file='small_snapshot_AI_exploratory_estimates_001.json',problem_record='45_体验问题证据与改进验证_20261019.md'))
    write_json(S.path/'执行状态.json',state)
    assert master_hashes(S)==review['master_hashes']
    checks=dict(sample_IDs_unchanged=True,weights_unchanged=True,all_76_problem_cases_have_explicit_extraction=True,
        all_case_conditions_actions_outcomes_mark_unspecified_when_unread=True,case_cards_have_source_author_thread_counts=True,
        raw_master_hashes_unchanged=True,human_final_count=0,independent_semantic_validation=False,numerical_tests_passed=8)
    name='small_snapshot_AI_analysis_completion_001.json'
    paths=[P/'44_标签AI复核与加权比例_20261019.md',P/'45_体验问题证据与改进验证_20261019.md',S.path/'small_snapshot_problem_cases_AI_001.csv',S.path/'small_snapshot_ai_reviewed_coding_001.csv',S.path/'small_snapshot_AI_exploratory_estimates_001.csv']
    if not (S.path/name).exists():small.seal(S,name,dict(checks=checks,review_hash=digest(review),estimates_hash=digest(est),output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
    print(json.dumps(dict(checks=checks,cards=[{k:c[k] for k in ('id','evidence_utterances','different_videos','different_authors','different_threads')} for c in cardrows]),ensure_ascii=False))

if __name__=='__main__':main()
