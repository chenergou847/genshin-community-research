"""离线整理完整材料、建立全过程目录并逐文件校验；不改源档，不采集或重编码。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import csv
import hashlib
import io
import json
import os
import re
import shutil

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / 'B站社区观察_完整交接包_20261019'
ORIGIN = WORKSPACE / 'B站高难副本社区观察_20261017'
PAYLOAD = ROOT / '完整项目材料'
A = '完整项目材料/02_完整项目存档/'
S = A + '采集工具/正式采集_小样本v1_20261018/'
C = '完整项目材料/01_当前交付/'
R = '完整项目材料/04_报告修订_20261019/'
H = '完整项目材料/03_岗位与接续资料/'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(base):
    files, skipped = {}, []
    for here, dirs, names in os.walk(base, followlinks=False):
        for name in dirs[:]:
            p = Path(here) / name
            if name in {'node_modules', '__pycache__', '.git', '.pytest_cache'} or p.is_symlink() or p.is_junction():
                skipped.append({'path': p.relative_to(base).as_posix(), 'reason': '依赖链接、运行缓存或版本库'} )
                dirs.remove(name)
        for name in names:
            p = Path(here) / name
            low = name.lower()
            if (p.is_symlink() or low in {'.private.json', '.env', '.session.json', 'cookies.txt', 'cookie.txt'}
                    or low.startswith('.env.') or p.suffix.lower() in {'.pyc', '.pyo', '.pem', '.key', '.pfx'}):
                skipped.append({'path': p.relative_to(base).as_posix(), 'reason': '凭据、私钥或编译缓存；未读取内容'})
                continue
            files[p.relative_to(base).as_posix()] = p
    return files, skipped


def write(name, text):
    (ROOT / name).write_text(text, encoding='utf-8', newline='\n')


def link(label, path):
    assert (ROOT / path).exists(), path
    return f'[{label}]({path})'


def classify(name):
    if '/04_报告修订_20261019/' in name:
        return '11 报告修订与交付', '修订来源、引文父链、旧稿备份或哈希核对', '最新修订及其历史凭据'
    if '/01_当前交付/' in name:
        return '10 当前成果与分析', '当前报告、全量编码、主题汇总或交付校验', '当前；旧语境备忘录仅作历史'
    if '/03_岗位与接续资料/' in name:
        return '01 任务与接续', '岗位背景、项目边界、检索规则或当前状态', '当前接续；JD为背景'
    if '/review_evidence/' in name or 'small_video_review' in name or 'small_video_draw' in name or 'small_video_selection' in name:
        return '04 视频资格与来源锁定', '视频审核提案、确认、画面证据、随机顺序或60条来源', '冻结来源；历史批次并存'
    if '/cache/' in name or '/cache_captures/' in name:
        return '05 已存接口响应证据', '经处理的请求响应缓存；需结合查询或采集记录定位', '历史响应快照，不等于评论全量保证'
    if 'small_discovery' in name or 'small_candidate_frame' in name:
        return '03 固定视频检索与候选', '检索请求、进度、失败快照、响应索引或冻结候选', '以冻结main／audit_a／audit_b为当前框'
    if any(s in name for s in ['small_snapshot_frame_001', 'small_comments.jsonl', 'small_observations.jsonl']):
        return '06 原正文与窗口清单', '规范化正文、观察记录及当前窗口集合的来源', '当前保存框；完整性限制保留'
    if any(s in name for s in ['small_repair', 'small_integrity', 'small_gap_', 'small_context', 'small_dialog_',
                                'small_collection', 'collection_evidence', 'small_online_', 'small_independent_page']):
        return '07 采集异常与规则变更', '分页、计数、父链、修复尝试、失败状态或用户规则变更', '未通过项仍保留'
    if 'full_corpus_' in name:
        return '09 全量编码与人机分工', '代码本、工作队列、校准、AI批次、修订、最终标签或豁免', '最终002为现行；holdout未用'
    if 'small_snapshot_' in name or '/交付_20261019/' in name:
        return '08 历史232／600条阶段', '历史样本、增补、试编码、AI复核、审核界面或探索分析', '历史；不替代当前6,526条分母'
    if '/全量编码_20261019/' in name:
        return '10 当前成果与分析', '当前完整编码、主题汇总、分析及版本历史', '当前002口径；历史版本保留'
    if '/tests/' in name or name.endswith(('.py', '.mjs')) or '/observer/' in name:
        return '12 脚本与技术复核', '程序实现、模块、测试代码或导出工具', '保留代码不等于本次重新运行过测试'
    if '/02_完整项目存档/' in name:
        leaf = Path(name).name
        m = re.match(r'(\d\d)_', leaf)
        if m:
            n = int(m[1])
            stage = ('02 早期探索与范围演进' if n <= 11 else '02 方案与范围演进' if n <= 18 else
                     '04 视频资格与来源锁定' if n <= 29 else '07 采集异常与规则变更' if n <= 38 else
                     '08 历史232／600条阶段' if n <= 47 else '09 全量编码与人机分工' if n <= 49 else '11 报告交接')
            return stage, '按阶段留存的研究说明与执行记录', '历史过程记录，以最新接续及报告为准'
        return '02 早期探索与历次采集', '早期数据、截图、工作簿、采集版本或接口试验', '完整保存历史，不混入当前分母'
    return '13 归档目录与完整性', '目录、来源、哈希清单或导出校验', '归档凭据，非语义准确率证明'


STAGES = [
    ('1. 任务缘起与早期探索', '证明项目从岗位背景、任务定义和观察口径出发，经历初始检索与样本取舍；早期结果不能当作当前统计。', [
        (H+'产品运营实习生jd.docx', '岗位JD：项目用途背景'),
        (A+'00_任务定义.md', '任务定义：研究问题与初始范围'),
        (A+'01_观察口径.md', '初始观察口径'),
        (A+'04_参与与决策记录.md', '参与及决策的项目内留档'),
        (A+'数据/', '早期检索、读取、覆盖和取舍数据'),
        (A+'编码/', '早期反馈证据和问题归纳'),
        (A+'outputs/', '早期工作簿、预览图与工具输出'),
        (A+'证据截图/', '早期页面／视频截图')]),
    ('2. 方案、日期边界与工具准备', '证明采集和选择规则如何登记、范围如何修订，以及有哪些工具实现和验收记录。方案文件证明约定，不单独证明执行完成。', [
        (A+'12_本期评论双轨抽样方案_v1.md', '早期双轨方案'),
        (A+'13_评论采集与抽样数据要求_v1.md', '字段和采集要求'),
        (A+'14_采集工具交付与验收.md', '工具交付与当时验收记录'),
        (A+'16_视频发布期边界修订_v2.md', '视频日期边界调整'),
        (A+'17_缩减样本正式方案_20261018.md', '固定有限检索与来源方案'),
        (S+'config.json', '实际登记的关键词、排序、页数和时间参数'),
        (S+'registration.json', '登记记录'),
        (A+'采集工具/observer/', '采集、检索、规则与统计模块'),
        (A+'采集工具/tests/', '技术测试代码；本次归档未重跑测试')]),
    ('3. 关键词视频检索与候选冻结', '证明先检索视频再取评论，固定主／A／B预算的请求及返回，保存了193页、3,798个返回位置、1,573个不同候选。不能证明全站检索覆盖率。', [
        (H+'检索规则与脚本分工.md', '30个关键词、规则与实际脚本职责'),
        (S+'small_discovery_main.json', '主检索54组合、157页、3,118位置'),
        (S+'small_discovery_audit_a.json', '补充A：18组合、18页、320位置'),
        (S+'small_discovery_audit_b.json', '补充B：18组合、18页、360位置'),
        (S+'small_candidate_frame.json', '冻结候选：1,634个视频×副本行／1,573个不同视频'),
        (S+'cache/', '3,093个混合用途的已存接口响应文件；通过记录中的响应路径／哈希定位')]),
    ('4. 随机来源顺序、八批资格核验与锁定', '证明候选冻结后产生一次随机顺序，并沿前缀核验79条、纳入60条、排除19条。用户确认文件属于项目内记录；没有把其余候选当作已审核。', [
        (S+'small_video_draw.json', '随机种子与全排列顺序'),
        (S+'small_video_review.csv', '逐条视频资格裁决与依据'),
        (S+'small_video_review_batch_001_proposal.json', '第1批AI提案；第2—8批同类文件均保留'),
        (S+'small_video_review_batch_001_confirmation.json', '第1批用户确认记录；第2—8批同类文件均保留'),
        (S+'small_video_review_batch_008_confirmation.json', '第8批确认记录'),
        (S+'review_evidence/', '65个审核画面／证据文件，按第4—8批分组'),
        (S+'small_video_selection.json', '最终60条来源及资格证据'),
        (A+'29_正式入选视频清单_20261018.md', '便于阅读的锁定来源表')]),
    ('5. 评论获取、响应与正文规范化', '证明60条来源被尝试、根与回复均有获取记录，保存9,593个唯一正文；已处理响应不是平台原始服务器备份，也不证明所有可见评论均已拿齐。', [
        (A+'28_视频样本锁定与评论采集_20261018.md', '锁定来源与采集说明'),
        (S+'events.jsonl', '该研究目录事件记录'),
        (S+'small_collection.json', '来源级采集状态及哈希'),
        (S+'small_collection_execution_latest.json', '采集执行汇总与失败原因'),
        (S+'small_comments.jsonl', '已保存的规范化正文、ID、父链、时间和点赞'),
        (S+'small_observations.jsonl', '配套观察记录'),
        (S+'cache_captures/', '460个异常核验／续采等阶段响应文件'),
        (S+'collection_evidence/', '零评论来源的页面截图证据')]),
    ('6. 失败、修复尝试与缺父处理变更', '证明异常曾被发现、保存和处理，而非在结果中隐去。严格审核45通过、15待核／受阻，整体门槛未通过；保留可读回复的后续规则没有恢复丢失正文。', [
        (A+'30_评论父节点缺失与处理规则待核_20261018.md', '初次父链问题说明'),
        (A+'32_两项评论完整性异常修复核验_20261018.md', '局部修复与核对记录'),
        (A+'34_保留失败状态并续采剩余来源_20261018.md', '失败保留及继续其余来源的处理'),
        (A+'37_审批恢复后完整性复核结果_20261019.md', '后续完整性复核结果'),
        (S+'small_integrity_audit_010.json', '技术完整性审计'),
        (S+'small_collection_review.csv', '独立审核状态，不得解释为全部通过'),
        (S+'small_context_rule_decision_001.json', '原缺父即停规则'),
        (S+'small_context_rule_decision_002.json', '用户同意保留可读回复、语境不足记不明的变更记录'),
        (S+'small_context_disposition_015.json', '缺失语境处置清单'),
        (A+'38_缺失父正文处理规则修订_20261019.md', '变更说明；全部small_repair／gap等历史文件也在原目录')]),
    ('7. 窗口框与232／600条历史阶段', '证明由已存正文按原窗口建立清单，曾抽232条再增补至600条，并保留试编码、AI复核与审核入口。当前最终报告没有沿用这些抽样分母或扩张权重。', [
        (S+'small_snapshot_frame_001.json', '9,593条正文及6,526条窗口集合的主入口'),
        (S+'small_snapshot_registration_001.json', '保存框范围与抽样登记'),
        (S+'small_snapshot_draw_001.json', '原232条抽取记录'),
        (S+'small_snapshot_supplement_registration_001.json', '保留旧样本并增补的登记'),
        (S+'small_snapshot_supplement_draw_001.json', '增补到600条的抽取记录'),
        (A+'39_快照范围抽样执行结果_20261019.md', '232条阶段结果'),
        (A+'41_保留原232条的增补抽样结果_20261019.md', '600条阶段结果'),
        (A+'交付_20261019/', '600条旧审核HTML、CSV与问题卡片'),
        (S+'small_snapshot_codebook_proposal_001.json', '旧阶段代码本草案')]),
    ('8. 全量编码登记、30条校准与取消独立核验', '证明转为全量编码的边界、人机分工和用户确认／取消核验的项目内记录。30条校准不是独立准确率检验，预留holdout没有作为测试使用。', [
        (A+'48_全量编码与30加30人机协作审核_20261019.md', '全量工作安排历史；其第二批核验要求后被取消'),
        (S+'full_corpus_review_registration_001.json', '全量处理及审核安排登记'),
        (S+'full_corpus_codebook_001.json', '全量代码本'),
        (S+'full_corpus_calibration_packet_001.json', '首批30条校准材料'),
        (S+'full_corpus_human_calibration_001.json', '用户“全部认可”及30条确认记录'),
        (S+'full_corpus_validation_waiver_001.json', '取消CSV复核／独立核验并授权继续AI编码的记录'),
        (C+'01_首批30条校准.md', '便于阅读的30条校准'),
        (S+'full_corpus_work_queue_001.json', '全量队列'),
        (S+'full_corpus_semantic_queue_001.json', '语义工作队列；各批full_corpus_semantic_batch文件均已保留')]),
    ('9. 编码修订、最终标签与分析', '证明逐批判断、修改留痕、最终标签002、主题与问题区分、权重和敏感性结果。结构和算术校验不能证明语义准确率。', [
        (S+'full_corpus_initial_labels_001.json', '原始汇总判断'),
        (S+'full_corpus_semantic_amendments_002.json', '原判与最终修订记录'),
        (S+'full_corpus_labels_final_002.json', '现行6,526条最终标签'),
        (S+'full_corpus_analysis_002.json', '现行统计、关注度及敏感性数据'),
        (C+'全量编码明细.csv', '可直接查看的全量编码明细'),
        (C+'分副本主题与关注度.csv', '66项主题／本人问题汇总'),
        (C+'编码分析数据.json', '全文、编码、统计、来源与敏感性结果'),
        (C+'05_数据与口径校验.md', '既有数据结构与口径检查'),
        (A+'49_全量编码定稿与分析口径_20261019.md', '全量定稿口径记录')]),
    ('10. 报告各版、引文父链与最新修订', '证明报告如何由初稿改为反馈／态度／期待导向，保留旧稿、新正文来源与证据。本轮未重新编码，也没有补造满意度或态度比例。', [
        (A+'06_社区观察报告_初版.md', '最早报告'),
        (A+'46_社区观察整合报告_AI探索稿_20261019.md', '600条阶段探索稿'),
        (R+'历史原稿/04_社区观察分析报告_修订前.md', '全量初稿备份'),
        (C+'04_社区观察分析报告.md', '当前最新报告：2026-10-20修订'),
        (R+'报告正文模板.md', '现行报告的可编辑来源'),
        (R+'报告引用摘录.json', '18处连续引文登记'),
        (R+'已核对评论及父链.json', '26条证据及必要可读父链'),
        (R+'生成修订报告.py', '仅生成报告的新入口'),
        (R+'修订说明与校验.md', '修订内容、验证和限制'),
        (R+'修订完整性校验.json', '4,600个其他已有文件不变等修订检查')]),
    ('11. 脚本、历史采集版本与技术附件', '证明有哪些实现、试验和技术材料。保留旧代码供追溯，不表示旧脚本应重跑；重新在线采集仍依赖未归档的本机会话。', [
        (A+'采集工具/README.md', '工具说明'),
        (A+'采集工具/', '全部采集、审核、修复、抽样、编码、定稿和导出脚本'),
        (A+'采集工具/接口核验_20261017_2300/', '接口与日期筛选的历史核验'),
        (A+'采集工具/登录后契约核验_20261017/', '登录后接口核验记录，不含登录凭据'),
        (A+'采集工具/正式采集_v1_20261017/', '早期正式采集版本；v2—v6也完整保留'),
        (A+'采集工具/正式采集_v6_20261017/', '早期第6版采集目录'),
        (A+'脚本/', '早期分析与工作簿构建脚本'),
        (A+'scripts/', '早期扩检与样本优化脚本')]),
    ('12. 导出、接续与本次整理核验', '证明历史导出、修订时点和本次复制的文件一致性。SHA256证明归档前后字节一致，不能独立证明原始内容、通关自述或研究结论的真实性。', [
        (H+'项目接续说明.md', '最新边界、完成状态与历史来由'),
        (H+'接续状态.json', '当前结构化状态'),
        ('完整项目材料/文件清单_SHA256.csv', '原始导出时点文件清单'),
        ('完整项目材料/导出校验.json', '原始导出结果及排除项'),
        (R+'修订前文件哈希.json', '修订前4,608个已有文件哈希'),
        (R+'修订后文件清单_SHA256.csv', '修订后的历史清单'),
        ('07_来源对照与版本差异.json', '本次原项目、交接包及旧版备份的对照'),
        ('05_归档核验结果.json', '本次复制及源档未变核验'),
        ('04_全部文件清单_SHA256.csv', '本档逐文件目录、用途与哈希'),
        ('06_复核材料完整性.py', '离线重验脚本')]),
]


VERIFIER = '''"""仅核对本档逐文件字节、哈希与新增／缺失，不联网、不修改研究材料。"""
from pathlib import Path
import csv, hashlib, json

def main():
    root = Path(__file__).resolve().parent
    manifest = root / '04_全部文件清单_SHA256.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    bad, missing, expected = [], [], set()
    for row in rows:
        name = row['相对路径']; p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()):
            raise SystemExit('清单包含目录外路径')
        expected.add(name)
        if not p.is_file():
            missing.append(name); continue
        h = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''):
                h.update(block)
        if p.stat().st_size != int(row['字节数']) or h.hexdigest() != row['SHA256']:
            bad.append(name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest}
    extra = sorted(actual-expected)
    result = {'status': 'PASS' if not (bad or missing or extra) else 'FAIL',
              'checked_files': len(rows), 'mismatches': bad, 'missing': missing, 'extra': extra}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)

if __name__ == '__main__':
    main()
'''


def main():
    before, bundle_excluded = inventory(SOURCE)
    origin, origin_excluded = inventory(ORIGIN)
    assert not bundle_excluded, bundle_excluded
    hashes = {n: sha(p) for n, p in before.items()}
    archive_prefix = '02_完整项目存档/'
    archived = {n[len(archive_prefix):]: p for n,p in before.items() if n.startswith(archive_prefix)}
    missing_origin = sorted(set(origin)-set(archived))
    assert not missing_origin, missing_origin
    version_changes = []
    origin_hashes = {}
    for name, src in origin.items():
        origin_hashes[name] = sha(src)
        if origin_hashes[name] != hashes[archive_prefix+name]:
            backups = {'全量编码_20261019/04_社区观察分析报告.md': '04_报告修订_20261019/历史原稿/04_社区观察分析报告_修订前.md',
                       '采集工具/write_full_corpus_report.py': '04_报告修订_20261019/历史原稿/write_full_corpus_report_修订前.py'}
            assert name in backups, name
            backup = backups[name]
            assert hashes[backup] == origin_hashes[name]
            version_changes.append({'origin_path': name, 'current_archive_sha256': hashes[archive_prefix+name],
                                    'original_version_sha256': origin_hashes[name], 'original_version_backup': backup})
    copied = []
    for name, src in before.items():
        target = PAYLOAD / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == hashes[name], f'已存在异版文件，停止覆盖：{target}'
        else:
            shutil.copy2(src, target)
        assert sha(target) == hashes[name], name
        copied.append({'source_relative_path': name, 'destination_relative_path': '完整项目材料/'+name,
                       'bytes': src.stat().st_size, 'sha256': hashes[name]})
    data = json.loads((PAYLOAD/'01_当前交付/编码分析数据.json').read_text(encoding='utf-8-sig'))
    assert len(data['rows']) == len({r['id'] for r in data['rows']}) == 6526
    assert Counter(r['relevance'] for r in data['rows']) == {'related':4698, 'irrelevant':1666, 'unknown':162}
    assert sum(bool(r['problem_themes']) for r in data['rows']) == 706
    assert json.loads((PAYLOAD/'03_岗位与接续资料/接续状态.json').read_text(encoding='utf-8'))['report_revision']['status']=='COMPLETED'
    source_unchanged = all(sha(p)==hashes[n] for n,p in before.items())
    assert source_unchanged
    origin_unchanged = all(sha(p)==origin_hashes[n] for n,p in origin.items())
    assert origin_unchanged
    at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    provenance = {'created_at_bjt': at, 'source_bundle':str(SOURCE), 'origin_project':str(ORIGIN),
        'eligible_origin_files':len(origin),'archive_project_files':len(archived),'missing_origin_files':missing_origin,
        'version_changes':version_changes,'excluded_original_items':origin_excluded,
        'exclusion_contents_read':False,'all_source_file_copy_records':copied}
    write('07_来源对照与版本差异.json',json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    write('06_复核材料完整性.py',VERIFIER)
    result = {'status':'PASS','created_at_bjt':at,'copied_material_files':len(copied),
        'copied_material_bytes':sum(x['bytes'] for x in copied),'origin_eligible_files_covered':len(origin),
        'missing_origin_material_files':[], 'copy_hash_mismatches':[], 'source_bundle_unchanged':source_unchanged,
        'original_project_unchanged':origin_unchanged,'version_differences_explained_and_backed_up':version_changes,
        'coded_rows_unchanged':6526,'independent_human_validation_remains_waived':True,
        'network_requests':0,'collection_or_sampling_or_recoding_run':False,
        'scope':'项目内已保存研究材料及过程记录；不声称恢复未保存内容或包含完整原始聊天导出',
        'manifest':'04_全部文件清单_SHA256.csv','manifest_excludes_only_itself':True}
    write('05_归档核验结果.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for reserved in ['04_全部文件清单_SHA256.csv','03_材料目录树.txt']:
        if not (ROOT/reserved).exists():
            write(reserved,'')

    evidence = ['# 全流程证据索引\n',
        '本索引按“做了什么—凭什么追溯”组织材料。完整原目录保留在`完整项目材料`中，未移动内部文件，避免破坏相对链接、响应路径和脚本依赖。全部文件另见逐文件清单和目录树。\n',
        '当前口径：固定60条来源；已存9,593个唯一正文；原窗口6,526条全量编码，4,698相关、1,666无关、162不明；706条本人问题表达。30条用户认可校准，其余6,496条为AI编码，独立核验已取消。当前报告为2026年10月20日修订版。\n']
    for title, meaning, paths in STAGES:
        evidence.extend([f'## {title}\n',meaning+'\n','| 材料入口 | 材料作用 |','| --- | --- |'])
        for path, role in paths:
            evidence.append('| '+link(Path(path.rstrip('/')).name,path)+' | '+role+' |')
        evidence.append('')
    evidence.extend(['## 如何从结论反查证据\n',
        '1. 从当前报告定位证据编号或主题表。\n2. 在`编码分析数据.json`按`semantic_index`或评论ID找正文、标签、BVID、根／父ID。\n3. 在`small_snapshot_frame_001.json`找原规范化正文和父链，结合`small_comments.jsonl`、`small_observations.jsonl`与缓存路径／响应哈希追溯采集。\n4. 由BVID回到`small_video_selection.json`、对应审核确认和`small_video_draw.json`；再回到冻结候选及检索响应。\n5. 若结论受缺父、计数差额、来源集中或编码验证不足影响，同时查异常与限制记录，不以哈希一致替代研究质量判断。\n',
        '## 没有伪造补齐的材料\n',
        '本档未新增采集、抽样、编码、访谈、验号、游戏实测或独立人审；没有恢复缺失父正文，也没有导出完整原始聊天记录。确认与授权以项目文件中保存的用户原话及登记为依据，属于过程留档。Cookie、匿名化私钥、依赖链接和编译缓存不属于研究证据，按原导出边界排除；具体路径列在来源对照文件中，未读取凭据内容。\n'])
    write('01_全流程证据索引.md','\n'.join(evidence))

    timeline = ['# 研究过程时间线与历史版本目录\n',
        '按既有00—50号研究记录排序，不把文件修改时间当作事件发生时间。2026年10月17—19日各步骤以文件标题与记录正文为准，10月20日完成报告修订及本次材料整理。旧状态在其时点有效，当前状态以最新接续和全量报告为准。\n',
        '| 编号 | 既有研究记录 | 所属过程 |','| --- | --- | --- |']
    numbered = sorted(p for p in (PAYLOAD/'02_完整项目存档').iterdir() if p.is_file() and re.match(r'^\d\d_',p.name))
    assert len(numbered)==51,len(numbered)
    for p in numbered:
        rel=p.relative_to(ROOT).as_posix()
        timeline.append(f'| {p.name[:2]} | {link(p.stem,rel)} | {classify(rel)[0]} |')
    timeline.extend(['','## 后续收尾材料\n',
        '- '+link('原完整导出与接续','完整项目材料/00_从这里开始.md'),
        '- '+link('10月20日报告修订记录',R+'修订说明与校验.md'),
        '- '+link('本次全链条归档核验','05_归档核验结果.json'),
        '\n早期初稿、旧232／600条结果、未使用核验预留项、失败记录均保留供追溯，不作为重新执行的待办；最新报告不包含已删除的独立民族志章节或运营动作表。\n'])
    write('02_研究过程时间线.md','\n'.join(timeline))

    groups=[]
    for name in ['01_当前交付','02_完整项目存档','03_岗位与接续资料','04_报告修订_20261019']:
        ps=[p for n,p in before.items() if n.startswith(name+'/')]
        groups.append((name,len(ps),sum(p.stat().st_size for p in ps)))
    opening=['# B站社区观察：全链条材料总目录\n',
        '整理日期：2026年10月20日。这里集中保存本项目从需求与早期探索，到方案、检索、资格核验、评论采集、异常处理、历史抽样、全量编码、分析、报告修订和归档校验的**全部现有研究材料**。原项目和原交接包均未改动。\n',
        f'本次从最新交接包复制**{len(copied):,}个材料文件，约{sum(x["bytes"] for x in copied)/1_000_000:.1f} MB**；与原项目另行对照的{len(origin):,}个可归档文件均已覆盖。原项目相较当前存档仅报告和生成脚本为旧版，两个旧版均有一致备份，过程详见来源对照。\n',
        '## 建议阅读顺序\n',
        '1. '+link('当前修订报告',C+'04_社区观察分析报告.md')+'：先看本项目最终回答了什么。',
        '2. '+link('全流程证据索引','01_全流程证据索引.md')+'：按12个阶段查看材料及其证明范围。',
        '3. '+link('研究过程时间线','02_研究过程时间线.md')+'：查看00—50号研究记录、范围变化与历史版本。',
        '4. '+link('完整材料目录树','03_材料目录树.txt')+'：列出全部目录和文件，便于按名称寻找。',
        '5. '+link('全部文件清单与SHA256','04_全部文件清单_SHA256.csv')+'：逐文件列出阶段、路径、大小、用途、时效和校验值。\n',
        '## 文件夹里有什么\n', '| 目录 | 文件数 | 大小 | 主要内容 |','| --- | ---: | ---: | --- |']
    meanings={'01_当前交付':'当前报告、6,526条编码CSV、主题关注度、完整分析JSON、30条校准和校验记录',
        '02_完整项目存档':'51份阶段研究记录；所有历史方案、候选、截图、响应缓存、正文、审核、抽样、编码批次、分析、脚本与测试',
        '03_岗位与接续资料':'岗位JD、最新接续说明、结构化状态、完整检索词与脚本分工',
        '04_报告修订_20261019':'10月20日修订的模板、18处引文、26条证据与父链、生成器、旧稿备份和哈希核对；文件夹名承接原批次日期'}
    for name,n,size in groups:
        opening.append(f'| {link(name,"完整项目材料/"+name+"/")} | {n:,} | {size/1_000_000:.1f} MB | {meanings[name]} |')
    opening.extend(['','`完整项目材料`根目录另外保留旧导出入口、清单、验证脚本及结果，均属于当时时点的凭据。所有文件都在总清单中，不只列精选材料。\n',
        '## 本次整理新增的文件\n',
        '- `00_材料总目录.md`：本入口。',
        '- `01_全流程证据索引.md`：12个阶段的关键材料、用途及证据边界。',
        '- `02_研究过程时间线.md`：51份研究记录与后续报告修订。',
        '- `03_材料目录树.txt`：完整文件层级。',
        '- `04_全部文件清单_SHA256.csv`：逐文件目录与校验值，清单自身除外。',
        '- `05_归档核验结果.json`：复制匹配、源档未变和当前数据状态检查结果。',
        '- `06_复核材料完整性.py`：用Python标准库离线重验文件、哈希和新增／缺失。',
        '- `07_来源对照与版本差异.json`：原项目对照、排除项、两个旧版备份及4,625条逐文件复制来源。',
        '- `08_整理归档脚本.py`：本次复制、建目录和核验的实现。\n',
        '## 当前成果与使用边界\n',
        '固定三个副本各20条来源，已存9,593个唯一正文，原窗口6,526条全部编码；4,698相关、1,666无关、162不明，706条为本人受阻或不满表达。30条由用户认可校准，其余6,496条AI编码，用户取消的独立核验未恢复。当前报告以反馈、态度及高难副本期待为主，已删除独立民族志说明与浅层运营动作。\n',
        '全过程材料也包括失败和限制：严格评论完整性门槛未整体通过；深渊和剧诗来源集中；20条窗口发言受缺失祖先影响，981条附图未读；没有独立语义准确率或人际一致率。条数不是玩家人数，点赞不是赞同人数。旧232／600条结果只供历史追溯。\n',
        '本档证明的是项目内已经保存的研究过程及文件一致性，不声称包含完整原始聊天导出或补齐未保存材料。Cookie、匿名化私钥、依赖链接和运行缓存按原边界排除，研究正文、响应证据、代码及校验均保留。\n',
        '## 怎样重验完整性\n',
        '在本文件夹打开PowerShell，执行：\n\n```powershell\npython .\\06_复核材料完整性.py\n```\n',
        '该脚本只读研究材料并输出检查结果。`status: PASS`表示清单内各文件字节与哈希一致、没有缺失或未登记新增；它不验证研究结论或编码准确率。原导出和修订的旧清单仍按其时点解释，不能要求其覆盖后续新增的目录。\n'])
    write('00_材料总目录.md','\n'.join(opening))

    # 预留清单名称，使根目录的总目录和证据索引可在建清单前检查链接。
    manifest=ROOT/'04_全部文件清单_SHA256.csv'
    if not manifest.exists():manifest.write_text('',encoding='utf-8')
    tree=ROOT/'03_材料目录树.txt'
    if not tree.exists():tree.write_text('',encoding='utf-8')
    for md in ['00_材料总目录.md','01_全流程证据索引.md','02_研究过程时间线.md']:
        for path in re.findall(r'\[[^\]]*\]\(([^)]+)\)',(ROOT/md).read_text(encoding='utf-8')):
            assert (ROOT/path).exists(),(md,path)
    tree_lines=[ROOT.name+'/', '全部目录与文件；MB按十进制计量，历史版本和失败材料保留。', '']
    def walk_tree(base,prefix=''):
        children=sorted(base.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold()))
        for i,p in enumerate(children):
            last=i==len(children)-1
            tree_lines.append(prefix+('└── ' if last else '├── ')+p.name+('/' if p.is_dir() else ''))
            if p.is_dir():walk_tree(p,prefix+('    ' if last else '│   '))
    walk_tree(ROOT)
    write('03_材料目录树.txt','\n'.join(tree_lines)+'\n')
    buf=io.StringIO(newline='');writer=csv.writer(buf)
    writer.writerow(['阶段','相对路径','字节数','SHA256','材料作用','当前与历史口径'])
    entries=sorted(p for p in ROOT.rglob('*') if p.is_file() and p!=manifest)
    for p in entries:
        rel=p.relative_to(ROOT).as_posix();stage,role,period=classify(rel)
        writer.writerow([stage,rel,p.stat().st_size,sha(p),role,period])
    manifest.write_text(buf.getvalue(),encoding='utf-8-sig',newline='')
    assert all(sha(p)==hashes[n] for n,p in before.items())
    print(json.dumps({'status':'PASS','destination':str(ROOT),'copied_material_files':len(copied),
        'copied_material_bytes':sum(x['bytes'] for x in copied),'origin_files_covered':len(origin),
        'manifest_entries':len(entries),'total_files':len(entries)+1,'source_changed':False,
        'exclusions':len(origin_excluded),'version_differences_backed_up':len(version_changes)},ensure_ascii=False))


if __name__=='__main__':
    main()
