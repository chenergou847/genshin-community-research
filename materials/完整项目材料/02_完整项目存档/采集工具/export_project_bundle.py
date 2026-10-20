"""Export a self-contained research handoff without credentials or dependency links."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import json
import os
import shutil

PROJECT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT.parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def export_files(source, destination, excluded):
    """Copy regular files only; skip secrets by name without opening them."""
    pairs = []
    for base, dirs, names in os.walk(source, followlinks=False):
        for name in list(dirs):
            path = Path(base) / name
            if name in {'node_modules', '__pycache__', '.git', '.pytest_cache'} or path.is_symlink() or path.is_junction():
                excluded.append({'path': str(path.relative_to(PROJECT)), 'reason': 'dependency_link_or_runtime_cache'})
                dirs.remove(name)
        for name in names:
            path = Path(base) / name
            lower = name.lower()
            if (lower == '.private.json' or lower == '.env' or lower.startswith('.env.')
                    or lower in {'cookies.txt', 'cookie.txt'} or path.suffix.lower() in {'.pyc', '.pem', '.key', '.pfx'}):
                excluded.append({'path': str(path.relative_to(PROJECT)), 'reason': 'credential_private_key_or_bytecode_not_opened'})
                continue
            if path.is_symlink():
                excluded.append({'path': str(path.relative_to(PROJECT)), 'reason': 'file_link'})
                continue
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            pairs.append((path, target))
    return pairs


def main():
    root = WORKSPACE / 'B站社区观察_完整交接包_20261019'
    if root.exists():
        raise SystemExit('导出目录已存在；请保留已校验的导出，不自动覆盖。')
    root.mkdir()
    study = PROJECT / '采集工具' / '正式采集_小样本v1_20261018'
    output = PROJECT / '全量编码_20261019'
    data = read(output / '编码分析数据.json')
    rows = data['rows']
    assert len(rows) == len({r['id'] for r in rows}) == 6526
    assert Counter(r['relevance'] for r in rows) == {'related': 4698, 'irrelevant': 1666, 'unknown': 162}
    assert sum(bool(r['problem_themes']) for r in rows) == 706
    assert sum(r['like'] for r in rows) == 26488
    config = read(study / 'config.json')
    at = datetime.now(timezone.utc).isoformat()

    # Record the latest human request before snapshotting the project.
    pending = {
        'status': 'PENDING_NOT_IMPLEMENTED',
        'authority': 'latest_direct_user_messages_in_this_chat',
        'requested_changes': [
            '重写数据范围与完成状态，解释关键词视频检索、随机筛选、评论采集、窗口过滤与脚本分工及实际落实。',
            '删除独立的借鉴网络民族志的语境解释部分，仅在实际方法上借鉴。',
            '删除从观察到可验证的运营动作及文中浅层问题对应动作。',
            '研究重点改为社区有哪些反馈、有哪些态度、玩家想要怎样的高难副本。'
        ],
        'work_done': '已核对检索和采集记录、读取部分态度及偏好证据；报告正文尚未重写。',
        'latest_user_instruction': '把已有成果全部导出到一个文件夹，便于新对话接续。'
    }
    state = read(study / '执行状态.json')
    state['report_revision'] = pending
    state['export_handoff'] = {'folder': str(root), 'snapshot_at': at, 'status': 'PROJECT_SNAPSHOT_PREPARED'}
    write(study / '执行状态.json', state)
    record = PROJECT / '50_项目导出与接续_20261019.md'
    record.write_text(
        '# 项目导出与接续\n\n'
        f'用户要求将已有成果集中导出，目录：`{root}`。从该目录的`00_从这里开始.md`进入。\n\n'
        '已完成6,526条窗口正文编码与初版分析报告；30条人审校准、其余AI编码，独立核验已获用户豁免。'
        '原始已存正文9,593条、固定60条视频和时间窗不变。\n\n'
        '最新报告修改尚未实施：补全收集规则与脚本分工；删除独立民族志解释和运营动作；'
        '分析聚焦社区反馈、态度与高难副本期待。用户随后优先要求导出，本次没有把重写伪称完成。\n\n'
        '导出保存现有交付、全部研究阶段文件、已存响应与正文、脚本及测试。'
        '不导出Cookie、匿名化私钥、依赖链接和编译缓存；不改动正文、标签或旧样本。'
        '导出目录中另有SHA256清单和独立核验脚本。原项目仍保留。\n', encoding='utf-8')
    task = PROJECT / '00_任务定义.md'
    entry = ('> 最新接续：已按用户要求导出至`B站社区观察_完整交接包_20261019`。'
             '报告初稿已交付，最新的反馈／态度／期待导向重写尚未实施。'
             '见[50号接续记录](50_项目导出与接续_20261019.md)，不要把旧阶段的待人审状态当作当前要求。\n\n')
    prior = task.read_text(encoding='utf-8')
    if not prior.startswith('> 最新接续：'):
        task.write_text(entry + prior, encoding='utf-8')

    excluded = []
    pairs = export_files(PROJECT, root / '02_完整项目存档', excluded)
    # A short entry folder avoids navigating thousands of historical files.
    quick = root / '01_当前交付'
    quick.mkdir()
    for source in output.iterdir():
        if source.is_file() and not source.is_symlink():
            target = quick / source.name
            shutil.copy2(source, target)
            pairs.append((source, target))
    jd = WORKSPACE / '产品运营实习生jd.docx'
    supporting = root / '03_岗位与接续资料'
    supporting.mkdir()
    if jd.exists():
        target = supporting / jd.name
        shutil.copy2(jd, target)
        pairs.append((jd, target))

    opening = '''# 从这里开始：B站高难副本社区观察

本目录是当前成果的本地完整快照。**下一步是修改报告，采集和6,526条编码不需要重新做。**

## 先看这三个入口

1. [项目接续说明](03_岗位与接续资料/项目接续说明.md)：当前状态、最新需求、方法与文件定位，供新对话接手。
2. [现有分析报告](01_当前交付/04_社区观察分析报告.md)：现有初稿；你刚提出的报告修改尚未实施。
3. [全量编码明细](01_当前交付/全量编码明细.csv)：6,526条；[分析数据与分层结果](01_当前交付/编码分析数据.json)是可直接重做报告的输入。

## 当前完成情况

| 环节 | 实际结果 |
| --- | --- |
| 视频检索 | 固定关键词搜索视频；193页已保存响应，3,798个返回位置，1,573个不同候选视频 |
| 视频资格 | 沿随机顺序核验79条，纳入60条、排除19条；其余候选没有全部人工核验 |
| 评论保存 | 9,593个唯一已存正文ID，3,251根＋6,342回复；原完整性门槛没有整体通过 |
| 当前分析语料 | 原窗口内6,526条，2,288根＋4,238回复；全部已编码 |
| 编码结果 | 4,698相关、1,666无关、162不明；706条本人受阻／不满表达 |
| 人工与AI | 30条用户认可校准，其余6,496条AI编码；独立核验已由用户取消 |
| 报告 | 初稿已交付；最新一轮重写待完成 |

## 文件夹怎么用

- `01_当前交付`：当前报告、完整CSV、分析JSON、校准和校验记录，供直接阅读。
- `02_完整项目存档`：原项目目录结构，含所有历史方案、研究记录、已存数据、响应缓存、证据、脚本与测试。
- `03_岗位与接续资料`：原始岗位JD、最新接续说明、脚本说明、检索规则和下一对话提示词。
- `文件清单_SHA256.csv`、`导出校验.json`、`验证导出.py`：导出完整性与可重验凭据。

旧232／600条结果仅作历史，当前报告使用6,526条全量编码。旧文件中的“待核验”“下一步采集”等历史状态，不覆盖本说明。

原项目保留。Cookie、匿名化私钥、node_modules依赖链接及Python编译缓存未导出；研究正文、响应证据和分析结果保留。该目录可离线阅读、继续分析；重新运行在线采集涉及原本机会话与私钥，本次没有重启任何采集。
'''
    (root / '00_从这里开始.md').write_text(opening, encoding='utf-8')
    handoff = '''# 项目接续说明（以此为最新状态）

## 目标和用户最新要求

本项目结合产品运营实习岗位JD，观察《原神》近期深境螺旋、幻想真境剧诗、幽境危战的B站社区讨论。现阶段报告要回答：**社区对高难副本有哪些反馈、有怎样的态度、玩家想要怎样的高难副本。**

最近用户对初稿明确提出：

> 1. 数据范围与完成状态并没有讲清楚是怎么收集数据的，我想要你讲清楚具体的收集规则和落实情况（比如先靠关键词检索视频），甚至可以简单介绍一下脚本分工。4. 借鉴网络民族志的语境解释部分可以不要了，我只是说在方法论上借鉴。6. 从观察到可验证的运营动作这个部分很突兀，缺乏分析，而且这些所谓的对应问题运营动作很不专业，不如不要。报告的目的是识别“社区对高难副本有哪些意反馈、有怎样的态度、玩家想要什么样的高难副本”，而不是浅层次的问题-对应动作。

随后用户优先要求：

> 这样吧，你把已有的成果全部导出到一个文件夹，省得这个对话太长了一直需要压缩。

**因此：导出是本次交付，报告重写仍待执行。不要把原报告中用户要求删除的部分视为已获认可。** 已调查数据来源和若干态度证据，没有改写报告正文，也没有新一轮采集或编码。

## 已确认的边界，不再重复询问

- 固定三个本期副本、60条视频和原时间窗；不换来源、不重抽、不因为零评论或“不够有料”而补视频。
- 视频本身须明确讨论本期；窗口前的旧期攻略、抽卡视频顺带抱怨、未找到本期段落的长回放排除。比较视频若实质讨论本期可纳入。
- 根评论和楼中楼都进入分析，单位是一条发言ID，不是一个玩家。一个作者多次发言仍是多条。
- 原来要求缺父即停，后经用户批准改为：保留可读回复，语境不足记不明，不删除、不补抽。缺失是否由删除引起未证实。
- 原采集总数／分页等未通过项保留；最终推断对象显式缩小为固定60条来源中**已经规范化保存的窗口正文**。
- 用户后来授权对全部6,526条编码，先认可30条校准；之后明确取消第二批30条独立人审，允许其余由AI作项目编码。不要再停下来要求核验CSV或补做已豁免的人审。
- 点赞与关注度指标必须解释，不能将高赞理解为同意人数，也不能把角色赞许当副本满意度。
- 借鉴网络民族志的语境敏感、线程阅读与反例意识即可；没有长期沉浸日志、访谈或实测，不声称做完完整网络民族志。

## 收集规则与实际落实

先搜索视频，再筛视频，再采集这些视频的评论；**没有直接全站搜索评论**。

1. 视频发布范围：北京时间2026-09-01 00:00至2026-10-17 23:09。预先固定18个主关键词，各用综合／最新／最多播放，最多前3页，每页20条；另有A/B两组补充检索，各6词×3排序，只取第1页。具体词表和执行数见同目录《检索规则与脚本分工.md》。旧早期版本的无界检索候选未自动混入当前框。
2. 主检索54组合、157页、3,118个返回位置；A组18组合18页320位置；B组18组合18页360位置。三组共193页3,798位置。按不同BVID累计去重：主检索1,381条，A新增100，B新增92，合计1,573个不同视频；按BVID×副本另记1,634行（673／463／498）。候选并不等于合格视频。
3. 冻结后各副本一次随机全排列，沿前缀核验，直到各20条合格。深渊核验26条、剧诗28条、幽境25条，共79条，60纳入19排除。AI提供标题、简介及实际画面／片段证据，用户分8批核定。1,494个其余不同候选没有全部人工定资格，不能声称只有60条合格，也不能计算合格总体覆盖率。60／1573≈3.8%仅是对候选数的比值。
4. 使用本机会话向B站常规网页结构化接口请求根评论及每根楼中楼，保存经处理的响应、正文、ID、根父关系、日期、点赞快照、作者匿名ID与分页证据；不是靠截图OCR，也不是只摘前排热评。浏览器主要用于视频资格、页面计数及异常核验。Cookie不在导出包内。
5. 60条都尝试过采集，标准化主档保存9,593个唯一正文（3,251根、6,342回复）。独立严格审核没有全部通过；旧审核表45通过、15待核／受阻，不能称拿齐所有可见评论。未恢复父正文、计数差额、时点变化和页面不可用继续留档。
6. 按各玩法窗口筛出6,526条：深渊1,451、剧诗879、幽境4,196。33条视频有窗口正文（9／10／14），其余27条在此已存窗口档为0，仍保留。观察起点：深渊10月16日04:00、剧诗10月1日04:00、幽境9月30日10:00；共同截止10月17日23:09，北京时间。小时由用户确认。
7. 曾从该保存框抽232条，再保留原样本补到600；后来用户选择全量编码6,526条。旧抽样文件保留历史，当前不再用N/m扩张权重或旧600条统计替代全量结果。

## 当前数据与结论口径

| 副本 | 窗口条数 | 相关 | 不相关 | 不明 | 本人问题表达 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 深渊 | 1451 | 1155 | 247 | 49 | 84 |
| 剧诗 | 879 | 697 | 143 | 39 | 211 |
| 幽境 | 4196 | 2846 | 1276 | 74 | 411 |
| 合计 | 6526 | 4698 | 1666 | 162 | 706 |

706条含本人本期受阻或不满，非706个失败玩家。问题后来解决仍可保留曾受阻的自述。主题允许重叠；“谈某主题”与“本人在此受阻”是两个指标。不要只用负面问题表概括全部社区态度。

主指标：等权1，一条发言计一次。探索性关注度：`w=1+min(log10(1+like),2)`，范围1—3；主题加权关注度为该主题权重和／该副本全部相关发言权重和。原赞数保留；该公式是编码后加入的探索性选择，非抽样权重或代表性修正。

点赞6,526条均非缺失，合计26,488；4,516条0赞（69.2%）；前10条合计6,763赞（25.5%）。快照为10月18日12:50—23:25，晚于评论窗口截止，不能确定每个赞发生时间。没有曝光量、点赞者ID或统一时长，不估计赞同人数或点赞率。

深渊80.6%窗口发言来自BV1AQJU6hE93；剧诗89.5%来自BV1fuYP6tEva；幽境最大来源BV1B7a16gEXr占25.7%。删除最大来源后相关分母只剩108／37／2228。深渊、剧诗的主题普遍性尤其受来源集中限制。不同窗口和参与者构成，不按问题占比给三个副本排质量高低。

20条窗口发言受缺失祖先影响，981条本条附图未读。相关性不明不计为“没问题”；文本足够可正常编码，必须依赖缺失语境时保留不明。没有独立准确率／一致率或主题饱和度验证。全量只对已存集合，不推断全B站95%±10个百分点。

## 接着改报告时可用的分析线索

这些是已读材料的线索，继续核对原文与上文后写入；**没有新增态度分类的比例统计**。现有sentiment字段评价对象混合，不能把其正面率当玩法满意度。

- 深渊：角色适配与环境红利是正面体验来源，也有主动降配仍觉得太简单者；与具体敌人／机制卡关并存。semantic_index 510（轻松拿奖的肯定）、1045（主动上难度仍碾过）、1172（换队后通过）、1192（后来才理解能量条）、331（具体间打得不舒服）。
- 剧诗：规划本身有趣，与抽不到角色、难以回转和累计重开成本可以同时存在。1731明确说“趣味性比幽境强”，同时说重开代价太高；1705认可每月挑战；1787低练度仍觉得有意思。1277区分结算12分钟和实际大量重开。1249为290赞回复，区分满花与拿主要奖励；1301上文围绕“满原石是否必须满花”展开，有主动停止凹分的态度。1437不满随机复活边角角色，与1440／1445因复活主C顺利通过构成反例。1449同一人在不同账号上的体验不同，别当作固定玩家类型。
- 幽境：难度不只是伤害值，还涉及三队资源、元素与排轴复现、抽卡偏好和投入是否值得。3480提出N6是高投入／高技巧人群空间（119赞）；3487不愿为N6改变XP抽卡和投入；3500接受能打多少算多少；3511说明XP与养成规划可兼顾；3526零氪长期攒资源后首次通过，3529反驳必须氪金／绝活的绝对说法。这些在同一线程，不能当成多来源共识。
- 比较标准：3816争论“1金”未涵盖四星命座和武器成本，属比较观点，不是自述失败。5735和根评论讨论照攻略复现失败；不能未经实验诊断机制BUG。
- 角色赞许与需求可同时存在：4517（69赞）明确说木偶和薇都抢一个辅助；4635（325赞）“抽三只能不能拆成三个”主要是夸张玩梗，未算实际受阻。不能用高赞直接量化真实资源痛点人群。

可围绕挑战目标、可理解／可掌握的困难、规划的乐趣与试错成本、角色选择和积累回报、比较条件、参与取舍展开；明确区分玩家直接表达的偏好与研究推断，保留反例。不要再拼成“问题—运营动作”表。

## 数据和代码入口

在`02_完整项目存档`下：

- `全量编码_20261019/编码分析数据.json`：最方便的报告输入，含rows、statistics、themes、modes；全文、semantic_index、ID、点赞、上下文ID、主题和问题主题都有。
- `采集工具/正式采集_小样本v1_20261018/full_corpus_labels_final_002.json`、`full_corpus_analysis_002.json`：当前冻结版本；001为历史。
- 同目录`small_snapshot_frame_001.json`：9,593条规范化正文及窗口清单，按id查原文和父链。
- `small_video_selection.json`：固定60条来源和资格依据；`config.json`、`small_discovery_*.json`、`small_candidate_frame.json`、`small_video_draw.json`：检索、冻结与随机顺序证据。
- `full_corpus_semantic_amendments_002.json`：原判与修订；`full_corpus_human_calibration_001.json`：30条确认；`full_corpus_validation_waiver_001.json`：用户取消独立核验。预留holdout未用，不需为改报告揭盲或生成准确率。
- `49_全量编码定稿与分析口径_20261019.md`：上次交付口径；`50_项目导出与接续_20261019.md`：本次接续。
- `17号`为历史抽样方案，`28／29号`锁定，`37／38／39号`说明缺口与变通；`40号`旧摘要已经过时，不按它重新要求600条人审。

`全量编码_20261019/04_社区观察分析报告.md`及`采集工具/write_full_corpus_report.py`目前都含旧初稿。修改报告时同步更新生成脚本或明确新的正文来源，避免再运行旧脚本覆盖。不要无必要重跑`finalize_full_corpus.py`（可能覆盖已校验CSV及阶段状态）或采集脚本。保留原数据、CSV及标签；仅报告修订不必重做编码。

## 协作方式

用户要求关键目标明确后持续执行到交付，不反复确认，不因阶段结束停下来等“继续”。若必须改变目标、范围或关键质量标准才问一个核心问题。普通修订、保存、核对、汇报自行完成。不伪造采集完整性、人工核验、游戏机制或代表性。没有真正持续运行时不要声称在后台工作。

当前没有要求新增检索、扩样、重采、重新编码或恢复已取消的独立人审。新对话先读此说明、现有报告和分析JSON的必要部分即可，不必把4千多文件全部读入上下文。
'''
    (supporting / '项目接续说明.md').write_text(handoff, encoding='utf-8')

    rules = ['# 检索规则与脚本分工\n',
        '本文用于解释已经实施的数据链路，不是新的采集授权。所有路径相对于`02_完整项目存档/采集工具`。\n',
        '## 关键词与预算\n',
        '主检索每词×综合／最新／最多播放，各最多3页；A/B每词×同三排序，各仅第1页；每页20条。日期和纳排见《项目接续说明》。\n',
        '| 组 | 副本 | 固定关键词 |\n| --- | --- | --- |']
    labels = {'abyss': '深渊', 'theater': '剧诗', 'stygian': '幽境'}
    for group in ['main', 'audit_a', 'audit_b']:
        for mode in labels:
            keywords = list(dict.fromkeys(q['keyword'] for q in config['queries'] if q['group'] == group and q['mode'] == mode))
            rules.append('| ' + group + ' | ' + labels[mode] + ' | ' + '；'.join(keywords) + ' |')
    rules += ['\n执行：主54组合157页3118位置、A18组合18页320位置、B18组合18页360位置，均已封存；关键词排序请求正常终点可少于页数上限。去重后1573个不同视频、1634条视频×副本候选。\n',
        '## 实际脚本职责\n',
        '| 脚本／模块 | 实际工作 | 当前状态／定位 |\n| --- | --- | --- |',
        '| register_small_study.py | 登记时间窗、检索词、固定预算与抽样参数 | 已登记；不是采集结果 |',
        '| execute_small_discovery.py、observer/small.py | 执行固定视频搜索；保存请求与返回路径；按BVID×副本冻结候选，生成一次随机顺序 | 主/A/B全部完成；1573个不同候选 |',
        '| prepare_*_video_review.py、run_small.py及审核记录 | 准备随机前缀候选的元数据／画面证据，保存用户资格裁决，锁定来源 | 共79核验、60纳入、19排除 |',
        '| execute_locked_collection.py、observer/collect.py、observer/web_api.py | 调用网页结构化评论接口，逐页读根与楼中楼，规范化保存正文／ID／点赞／关系，留存失败和续采检查点 | 60条均尝试；9593个唯一正文保存，完整性未全部通过 |',
        '| audit_collection_integrity.py、diagnose_comment_repair.py、recapture_problem_video.py、verify_collection_gaps.py | 核验分页、线程和总数、父链及独立页面；针对异常核对 | 保存未解决项，未冒称恢复父正文 |',
        '| register_missing_context_amendment.py、observer/context_policy.py | 登记用户同意的缺父处理变化，保留语境缺口 | 不删回复；语境不足记不明 |',
        '| build_captured_snapshot_sample.py、build_snapshot_supplement.py | 从已保存窗口框抽232条，再保留旧样本增补到600条 | 历史样本；非当前6526条全量分析分母 |',
        '| prepare_full_corpus_calibration.py、full_corpus_coding.py、normalize_annotations.py | 准备30条校准，建立全量工作队列，记录AI逐批语义判断与证据，校验注释格式 | 6526条已处理；代码记录判断，不是仅靠关键词自动判定 |',
        '| finalize_full_corpus.py | 汇合批次、保留修订，冻结最终标签002，计算主题／问题／关注度／分层敏感性并导出 | 已完成；不需为改报告重跑 |',
        '| write_full_corpus_report.py | 由全量结果写报告、语境备忘录和口径说明 | 当前仍生成旧初稿；下一步应同步修订 |',
        '| 全量编码_20261019/validate_tables.mjs | 用表格工具导入和校验CSV，再保留精确日期字符串导出 | 导出和逐行核对已经完成 |',
        '| export_project_bundle.py | 复制研究成果、建立最新接续说明并逐文件哈希核验 | 本次导出；不请求网络和会话 |',
        '\n## 依赖与原始档保护\n',
        '离线阅读Markdown、CSV、JSON不需要登录。采样和统计的Python代码主要使用标准库，表格导出脚本依赖@oai/artifact-tool。node_modules为本机依赖链接，未作为成果复制；原始匿名化私钥不进入此包。报告分析可直接使用已经保存的匿名ID。未经必要性核对，不重跑在线接口或重建匿名身份。\n',
        '原本机Python：`LOCAL_USER_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`。导出验证脚本只需Python标准库；转移机器后用其本地Python即可。\n']
    (supporting / '检索规则与脚本分工.md').write_text('\n'.join(rules) + '\n', encoding='utf-8')
    (supporting / '下一对话直接发送.txt').write_text(
        f'请继续这个B站高难副本社区观察项目。先读取 `{root / "00_从这里开始.md"}` 和其中的《项目接续说明》，再查看现有报告及必要分析数据。'
        '当前6526条编码已完成，不重采、不重抽，也不重新要求我核验CSV或已取消的30条独立核验。'
        '请完成说明中保存的报告修改：讲清收集规则、实际落实与脚本分工；删除独立民族志说明和浅层运营动作；'
        '把分析重点放在社区反馈、态度、玩家期待怎样的高难副本。直接执行到修订报告交付，保留原始数据和口径限制。\n', encoding='utf-8')
    write(supporting / '接续状态.json', {
        'created_at': at, 'source_project': str(PROJECT), 'export_folder': str(root),
        'current_coding_version': 'full_corpus_labels_final_002.json', 'saved_raw_bodies': 9593,
        'in_window_coded': 6526, 'relevance': dict(Counter(r['relevance'] for r in rows)),
        'human_calibration_n': 30, 'AI_coded_n': 6496, 'independent_validation_waived': True,
        'strict_collection_gate_passed': False, 'report_revision': pending,
        'no_network_requests_in_export': True, 'cookie_contents_not_read': True,
        'keys_excluded_without_opening': True
    })
    verify_code = '''"""Check this export using only Python's standard library."""
from pathlib import Path
import csv,hashlib,json
p=Path(__file__).resolve().parent
bad=[];count=0
with (p/'文件清单_SHA256.csv').open(encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f):
        x=p/row['relative_path'];count+=1
        if not x.is_file():bad.append(row['relative_path']+':missing');continue
        h=hashlib.sha256(x.read_bytes()).hexdigest()
        if x.stat().st_size!=int(row['bytes']) or h!=row['sha256']:bad.append(row['relative_path']+':mismatch')
print(json.dumps({'checked':count,'passed':not bad,'failures':bad},ensure_ascii=True))
raise SystemExit(1 if bad else 0)
'''
    (root / '验证导出.py').write_text(verify_code, encoding='utf-8')

    # Verify all copies against source bytes; never modify copied research data.
    mismatches = []
    for source, target in pairs:
        if sha(source) != sha(target):
            mismatches.append(str(target.relative_to(root)))
    if mismatches:
        raise RuntimeError(f'Copy mismatches: {mismatches}')
    private = list(root.rglob('.private.json'))
    assert not private
    entries = []
    for target in sorted(root.rglob('*')):
        if target.is_file():
            entries.append({'relative_path': target.relative_to(root).as_posix(), 'bytes': target.stat().st_size, 'sha256': sha(target)})
    with (root / '文件清单_SHA256.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['relative_path', 'bytes', 'sha256'])
        writer.writeheader(); writer.writerows(entries)
    result = {'at': at, 'source': str(PROJECT), 'destination': str(root),
              'copied_files_checked_against_source': len(pairs), 'copy_mismatches': mismatches,
              'manifest_files': len(entries), 'manifest_bytes': sum(r['bytes'] for r in entries),
              'manifest_sha256': sha(root / '文件清单_SHA256.csv'), 'excluded': excluded,
              'excluded_private_files_opened': False, 'network_requests': 0,
              'report_revision_complete': False, 'export_complete': True,
              'note': '清单不含清单自身与导出校验.json；其余所有导出文件逐一列入。'}
    write(root / '导出校验.json', result)
    print(json.dumps({k: result[k] for k in ['destination', 'copied_files_checked_against_source', 'manifest_files', 'manifest_bytes', 'copy_mismatches', 'export_complete']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
