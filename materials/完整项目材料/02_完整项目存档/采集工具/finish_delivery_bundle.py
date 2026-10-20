"""Publish the local delivery index with explicit unmet human acceptance gates."""
import hashlib
import json
from pathlib import Path

from observer.core import read_json, write_json, now
from observer import small
from observer.snapshot_sample import master_hashes
from build_delivery_bundle import S, P, OUT, sha


def main():
    qc=read_json(S.path/'small_snapshot_delivery_qc_001.json')
    assert qc['javascript_syntax_checked'] and qc['invalid_export_cases_rejected']==7
    assert qc['human_results_completed']==0 and not qc['browser_visual_verification']
    manifest=read_json(S.path/'small_snapshot_human_review_portal_manifest_001.json')
    assert master_hashes(S)==manifest['raw_master_hashes']
    record='47_交付核验与人工接续_20261019.md'
    report=f'''# 交付核验与人工接续

2026-10-19。用户要求“一口气做完”后，已完成不依赖人工结果的报告整合、证据和统计附件整理，建立可离线使用的600条人工核验页及90条盲复核页。用户回复“我不知道在哪核验”，没有同意取消原人工验收标准。

## 可直接打开的材料

- [人工核验页](交付_20261019/01_600条人工核验.html)：在文件资源管理器中双击，以本机浏览器打开。原文、可用上文、时间、发言身份和AI标签都已装入；逐条点击确认才计为人工结果。
- [盲复核页](交付_20261019/02_90条盲复核.html)：每副本30条，文件不含逐项AI标签；不是新增90条主样本。
- [整合报告](46_社区观察整合报告_AI探索稿_20261019.md)：研究范围、采样数字、主要结果、问题线索、优化假设和质量限制。
- [交付说明](交付_20261019/00_交付入口.md)：审核操作、附件和接续方法。

## 已完成的验证

1. 600条主页面与90条重复核验页面的ID和副本匹配，90条均来自原600条；每副本30条，未重抽主样本。
2. 两份页面脚本通过Node语法检查，600条AI预填值通过前端标签约束与离线导入约束检查。测试夹具明确为AI测试数据，临时文件已清理，**没有写成实际人工结果**。
3. 部分导出仍判未完成；重复ID、未知ID、正文外证据、未核对语境、缺署名、错误样本哈希、受阻主题不一致共7类异常均被拒绝。
4. 原主档哈希和先前44/45号结果未变；417相关、125无关、58不明仍是当前AI标签口径。

这些检查验证数据和程序约束，不认证审核者身份，不验证分类准确率、覆盖率或游戏机制。

## 未完成及原因

- 人工主审核0/600，盲复核结果0/90。页面生成、AI自动填入或测试提交均不计入人工确认。
- 原17号人工定稿、一致性及裁决检查门槛未撤销，未用来源定性验证未完成；不能称原全流程验收通过。
- 90条复核ID是在AI分析后、人工结果前登记；按冻结种子与ID散列次序选择，不看标签。不能冒称研究开始前已封存。另一人编码与同人重编码分别报告，不自动称独立复核。
- 本机HTTP预览未连通，内置浏览器随后明确拒绝file协议；未尝试绕过，未完成浏览器视觉及实际下载/导入操作检查。页面是无外部依赖的本地HTML，需由用户以本机浏览器打开。预览服务已停止，不依赖后台服务。

## 用户需要的最小操作

先打开主核验页，填署名，读一条原文与上文；认可可“采用AI判断”，修改或保留不明也可以。勾选检查后“确认本条并下一条”，再导出JSON。可分次导入继续；完整主验收仍需全部600条，盲复核另行完成。把导出文件保存在项目目录并提供路径后，可继续校验、分歧裁决和人工版统计。

`validate_human_review.py <导出JSON路径>`只做只读验证，不改原始数据、标签或完成状态。600条主审核与90条复核分别导出，记录真实审核人及是否同人。

当前状态：**整合探索稿与核验入口已交付，原定人工验收等待实际填写。**没有采集、编码或监控后台任务。
'''
    (P/record).write_text(report,encoding='utf-8')
    state=read_json(S.path/'执行状态.json')
    state.update(stage='INTEGRATED_AI_REPORT_DELIVERED_HUMAN_REVIEW_REQUIRED',
        current_research_record='46_社区观察整合报告_AI探索稿_20261019.md',
        current_delivery_record=record,delivery_status='INTEGRATED_EXPLORATORY_DRAFT_NOT_HUMAN_FINAL',
        human_review_portal_ready=True,coding_completed=False,formal_human_estimates_computed=False,
        human_acceptance_waived=False,
        human_review=dict(main_expected=600,main_confirmed=0,blind_expected=90,blind_received=0,
            portal='交付_20261019/01_600条人工核验.html',
            blind_portal='交付_20261019/02_90条盲复核.html',
            registration='small_snapshot_human_review_registration_001.json',
            user_latest_reply='我不知道在哪核验',
            required_action='打开离线页，逐条确认后导出JSON并提供路径；不能由AI代签',
            unused_source_qualitative_validation_complete=False),
        delivery=dict(folder='交付_20261019',report='46_社区观察整合报告_AI探索稿_20261019.md',
            evidence_rows=76,metrics_rows=72,reviewed_AI_rows=600,
            numerical_checks_from_prior_stage=8,import_negative_cases_rejected=7,
            browser_visual_QA=False,background_tasks_running=False))
    write_json(S.path/'执行状态.json',state)
    update='''## 2026-10-19 当前入口：整合稿与离线人工核验页已交付

用户要求连续完成后，整合报告、600条人工核验页、90条不含AI标签的盲复核页、证据表和统计附件已生成。用户表示“不知道在哪核验”，未授权取消原人工要求。请打开[600条核验页](交付_20261019/01_600条人工核验.html)，以本机浏览器逐条确认并导出JSON；[交付说明](交付_20261019/00_交付入口.md)写明操作。

主审核仍0/600，复核结果0/90，原验收门槛保留。AI结果仍417相关、125无关、58不明；76条问题候选、6组线索及1单例，固定60来源/6526窗口正文范围不变。没有采集、编码或监控后台任务。

当前报告：[46号整合探索稿](46_社区观察整合报告_AI探索稿_20261019.md)；[47号交付检查与接续](47_交付核验与人工接续_20261019.md)。页面的脚本及导入约束已离线检查，浏览器视觉检查未完成；内置浏览器拒绝本地文件协议，不绕过，可双击文件在本机使用。未用来源定性验证仍未完成，不可声称原方案全流程通过。

---

'''
    for name in ['00_任务定义.md','40_上下文压缩与接续摘要_20261019.md']:
        path=P/name;text=path.read_text(encoding='utf-8-sig')
        if not text.startswith(update.splitlines()[0]):path.write_text(update+text,encoding='utf-8')
    files=[P/'46_社区观察整合报告_AI探索稿_20261019.md',P/record,*sorted(OUT.iterdir())]
    files=[p for p in files if p.is_file()]
    completion=dict(human_gate_unchanged=True,human_final_n=0,blind_result_n=0,
        integrated_AI_report_complete=True,original_research_acceptance_complete=False,
        qualitative_unused_source_validation_complete=False,
        raw_master_hashes=master_hashes(S),output_sha256={str(p.relative_to(P)):sha(p) for p in files},
        QC=qc,status='DELIVERY_READY_HUMAN_REVIEW_REQUIRED',
        latest_user_input='我不知道在哪核验',background_jobs_running=False)
    name='small_snapshot_delivery_completion_001.json'
    if not (S.path/name).exists():small.seal(S,name,completion)
    else:
        old=S.frozen(name)
        assert all(old[k]==v for k,v in completion.items()),'已有封存交付版本不同，请另立新版本'
    print(json.dumps(dict(files=len(files),output=str(OUT),status=completion['status'],
        AI_reviewed_n=600,human_final_n=0,blind_result_n=0,raw_unchanged=True),ensure_ascii=False))


if __name__=='__main__':main()
