"""Render the actual AI pilot and its codebook for human review."""
from pathlib import Path
from collections import Counter
import re
from observer.core import Study, read_json, write_json, now


def display(value):
    value=re.sub(r'回复\s*@[^:：]+[:：]\s*','回复[用户]：',value)
    return value.replace('|','／').replace('\n',' ')


if __name__=='__main__':
    s=Study('正式采集_小样本v1_20261018');root=s.path.parent.parent
    result=s.frozen('small_snapshot_coding_pilot_result_001.json')
    proposal=s.frozen('small_snapshot_coding_pilot_proposals_001.json')
    cb=s.frozen('small_snapshot_codebook_proposal_001.json')['codebook']
    material=read_json(s.path/'small_snapshot_coding_pilot_material_001.json')['items']
    by={(r['mode'],r['id']):r for r in material}
    labels={t['id']:t['label'] for t in cb['themes']}
    names=dict(abyss='深渊',theater='剧诗',stygian='幽境')
    rel=dict(related='相关',irrelevant='不相关',unknown='不明')
    lines=['# 代码本草案与首轮试编码','',
        '日期：2026-10-19，北京时间。已进入编码阶段，完成每副本10条共30条试编码，另核对1条已抽中的缺父回复。全部为AI初判，人工定稿0条，未计算反馈比例。','',
        '可复用任务描述：不改变600条抽中ID与权重，先以多来源试编码完善相关性、本人经历、主题和问题证据边界；相关、不相关及不明均保留。AI提出可追溯初判，代码本和正式定稿保留人工核定，不将试读当作总体比例、饱和度或独立编码一致性验证。','',
        '## 已完成的材料','',
        '- [31条试编码与诊断审核表](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_pilot_review_001.csv)：原文、父链、AI判断、理由及空白人工裁决栏。',
        '- [代码本草案](采集工具/正式采集_小样本v1_20261018/small_snapshot_codebook_proposal_001.json)：定义、纳入、排除及已观察到的例证ID。',
        '- [当前600条编码工作表](采集工具/正式采集_小样本v1_20261018/small_snapshot_supplement_coding.csv)：31条已有AI初判，569条尚待初判，600条均final=no。',
        '- [试编码完整正文和上下文](采集工具/正式采集_小样本v1_20261018/small_snapshot_coding_pilot_material_001.json)。','',
        '## 如何选试编码材料','',
        '只从已经锁定的600条中选，不增加主样本。按固定种子的独立试编码随机流排来源，优先不同UP，每轮每来源取1条直到每副本10条；不足10个非空来源时进入下一轮。没有按负面、长短或主题挑选。另将唯一带缺失父链标记、且未进入试编码的已抽中回复作为专项诊断。','',
        '这是偏重来源多样性的代码本开发材料，抽取概率不等同主样本；不能用“16/30”估计600条或6526条中的相关反馈比例。','',
        '## 本轮AI初判数量','',
        '| 副本 | 相关 | 不相关 | 不明 | 合计 |','| --- | ---: | ---: | ---: | ---: |']
    for m in names:
        counts=result['summary']['per_mode'][m]
        lines.append(f"| {names[m]} | {counts.get('related',0)} | {counts.get('irrelevant',0)} | {counts.get('unknown',0)} | 10 |")
    lines+=['| 合计 | 16 | 11 | 3 | 30 |','',
        '额外1条缺父诊断初判不相关：自身内容为泛跨游戏评价，父正文缺失仍标记，但不据缺父自动改为不明。','',
        '## 建议采用的统一边界','',
        '1. **本期玩法相关讨论与第一手体验分开。**配队建议、机制提示、本期角色表现比较可相关，但不自动代表本人玩过、受阻或满意。',
        '2. **主题与问题分开。**“借主C会更好”是配置建议；“我领了也打不过”才包含本期自述受阻。问题原因仍需配置、手法与机制证据核验。',
        '3. **当前发言不继承祖先的全部观点。**祖先用于解释“无了”等指向；不能把别人的卡关、以前的经历或操作建议都记到本条作者。',
        '4. **期次与副本分开。**剧诗视频下只谈深渊/N4，以及幽境视频下追忆早年打狼，都不计为该目标副本本期反馈，不移动到另一域补数。',
        '5. **语义与媒体分开。**单纯表情、含混简称而缺必要图片的文字记不明；“面板如下”可识别配置主题，但图片未读就不填写具体面板。没有读取任何评论配图。',
        '6. **混合推广留标记。**含相关内容的疑似推广不自动删除，但不采信其中旧期经历或未验证自述为本期第一手证据；后续另做排除此标记的敏感性分析。不据一个网站名称认定机器人。',
        '7. **评价对象分开。**“角色强势”不等同“副本整体满意”，“可以拿奖励”不等同已通关或已领取。','',
        '## 主题草案','',
        '以下主题允许多选，名称本身不带负面含义。本轮未出现的主题保留为候选，不能据此宣称问题不存在。','',
        '| 代码 | 主题 | 纳入定义 | 排除边界 |','| --- | --- | --- | --- |']
    for t in cb['themes']:
        lines.append(f"| {t['id']} | {t['label']} | {t['include']} | {t['exclude']} |")
    lines+=['', '## 逐条试编码：均待人工核定','',
        'ID链接指向来源视频；完整祖先和未缩略原文见审核CSV／材料JSON。下表将@用户名缩略为[用户]，原始正文没有改写。','',
        '| 编号／副本 | 发言ID及原文 | AI相关性与主题 | AI理由 |','| --- | --- | --- | --- |']
    for i,row in enumerate(proposal['rows'],1):
        item=by[row['mode'],row['id']]
        quote=display(item['text']);quote=quote if len(quote)<=140 else quote[:140]+'…'
        topics='、'.join(labels[k] for k in filter(None,row['themes'].split(';'))) or '—'
        mark='；缺父专项诊断' if item['role']!='pilot' else ''
        lines.append(f"| {i}／{names[row['mode']]}{mark} | [{row['id']}](https://www.bilibili.com/video/{item['bvid']}/)：{quote} | {rel[row['relevance']]}；{topics} | {display(row['reason'])} |")
    lines+=['', '## 可进入后续核验的线索','',
        '- 深渊317372849121：“没输出不知道怎么过”。线索为输出门槛与配队适配，尚不能判断是养成、配置、操作还是机制信息造成。',
        '- 剧诗315621236001：“我领了也打不过”。线索为资源提升未转化为通关；单条评论没有给出角色池、关卡和手法，原因待核。',
        '- 幽境319241551296：“我打不过这老头”“我只有法尔伽”。线索为通关受阻与账号可选角色条件，自述未被独立验证。','',
        '这些只是试编码中的具体问题线索，不是已经确认的产品缺陷、普遍问题或发生率。也保留旧角色“又能玩了”、调整配队后N5通过、奖励预期等正向或结果材料，避免只寻找负面。','',
        '## 核验状态与接续','',
        '31条提案均已逐条读取本条及可用祖先；作者关系仅用于判断是否为同一自述者，不展示作者匿名ID。不读取或推测图片内容。已核对：31条ID都在既有600条中、证据短句来自本条原文、主题均在草案内、本人经历与问题主题是已编码主题的子集、全600条仍final=no。主档及抽样draw哈希未改。','',
        '没有独立人类编码者或第二位编码者完成本轮，因此不报告“编码准确率”“一致性通过”或主题饱和。175项此前离线测试是采样程序检查，不是本次语义编码质量验证。','',
        '原17号方案保留“人工核定并冻结代码本”和“主样本全部完成人工相关性及主题定稿；AI可以提供初判”的要求。39号修订改变了抽样与代码本先后次序，未将AI初判改成人工定稿。当前需核定本轮代码本边界，再继续剩余569条AI初判；任何规则修改留档并回查已试编码项，不换抽中ID。','',
        '代码条目按定义、纳入、排除和自然语言例证组织，参照[MacQueen等的代码本方法论文](https://doi.org/10.1177/1525822X980100020301)。本项目明确披露AI初判、分析单位、抽样范围与尚未完成的人类核验，与[AAPOR内容分析披露要求](https://aapor.org/standards-and-ethics/disclosure-standards/)一致；这不构成外部机构对本项目的认证。','',
        '机器记录：small_snapshot_coding_pilot_queue_001.json、small_snapshot_codebook_proposal_001.json、small_snapshot_coding_pilot_proposals_001.json、small_snapshot_coding_pilot_result_001.json及对应哈希。编码前600行留档于small_snapshot_coding_before_pilot_001.json。',
        '准备脚本prepare_snapshot_coding_pilot.py；人工阅读后AI标注记录脚本record_snapshot_coding_pilot.py；本页生成脚本render_snapshot_coding_pilot.py。没有新采集或后台任务。','']
    target=root/'42_代码本草案与首轮试编码_20261019.md'
    target.write_text('\n'.join(lines),encoding='utf-8')
    state_path=s.path/'执行状态.json';state=read_json(state_path)
    state.update(stage='CODING_PILOT_AI_PROPOSALS_READY_CODEBOOK_HUMAN_REVIEW_PENDING',
        current_research_record=target.name,coding_completed=False,feedback_proportions_computed=False,
        coding_pilot=dict(at=now(),report=target.name,codebook='small_snapshot_codebook_proposal_001.json',
            pilot_result='small_snapshot_coding_pilot_result_001.json',review='small_snapshot_coding_pilot_review_001.csv',
            **result['summary']))
    write_json(state_path,state)
    print(str(target))
