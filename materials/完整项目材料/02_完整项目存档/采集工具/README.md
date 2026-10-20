# B站本期高难副本评论采集与抽样工具

**当前使用2026-10-18小样本版：每副本随机20条合格视频×每视频最多10条原始窗口发言，三副本合计最多600条。**固定深度检索、权重、视频聚类区间、盲复核及停止规则见项目`17_缩减样本正式方案_20261018.md`；命令与表格见[小样本使用说明](小样本使用说明.md)。入口为`run_small.py`，研究目录`正式采集_小样本v1_20261018`，实收状态见项目18号执行记录。目标不等于已取得的样本。

103项合成测试通过。主检索54/54、审计A/B各18/18已完成，冻结1573个不同候选、1634条视频×副本记录及一次随机顺序。资格审核正在按随机前缀分批执行，已核数量以研究目录执行状态.json及各批用户确认文件为准；尚未锁定最终视频名单、抽取正式评论或生成反馈比例。项目19号起各批文件保留提案及核定进展；第四批20条材料见项目22号文件，含可回查首帧。

以下保留旧大样本工具与历史说明，仅适用于原v1—v6目录；旧`run.py`不能对小样本目录运行400条算法。

交付日期：2026-10-17。实现规格为项目文件12、13及用户确认的16号边界修订；用户已授权编写脚本。采集与抽样主体使用Python 3.12标准库；可选正常扫码登录助手使用`qrcode`包。

**旧大样本停止记录：73项合成测试通过；用户正常扫码登录已核验并保存本机会话，真实日期正反边界检查通过。v6按用户确认的2026-09-01视频发布下限重新检索，首项查询分箱期间再次遇到B站访问校验并停止；0/54主组合完整，尚无正式视频库、完整评论框或随机样本。** 最新实测见项目`15_正式采集执行记录_20261017.md`，发布期范围见`16_视频发布期边界修订_v2.md`。

`研究数据_待核/`是脚本首次交付时的191个历史入口。当前执行目录`正式采集_v6_20261017/`；v1—v5均作为旧执行及失败证据保留。工作表中的候选入口不是合格视频或评论样本；旧正文试采和本轮接口核验均未直接并入正式分母。

最新v6共有2147个不同候选视频、2154行视频×副本记录；640行按明确发布日期排除，1514行仍待核。包含保留的旧候选，不能把这些数量当作本期合格视频数。详见该目录`执行状态.json`。凭证可用与批量接口可枚举是不同检查，提供或重新登录会话不保证解除访问校验；当前没有继续重试。

## 入口与文件

- `run.py`：命令行入口，先写`--study`，再写子命令。
- `observer/core.py`：配置、字符串ID、冻结校验、随机生成器、Wilson区间。
- `observer/collect.py`：只读HTTP、最少字段归档、检索、全根/全线程分页、去重与失败记录。
- `observer/web_api.py`：正常公开网页会话、WBI传输签名及根评论时间游标。
- `observer/research.py`：建库检查点、原始清单冻结、定性队列、主统计、审计与敏感性分析。
- `tests/test_observer.py`：纯合成夹具；不代表采集到真实评论。
- `验收结果.json`：最近一次离线验收的运行数、结果及源码哈希。
- `试跑_20261017/smoke.json`及`events.jsonl`：真实只读连通试跑记录，失败不计入样本。

脚本不会发评论、点赞或修改B站内容。没有浏览器Cookie提取、风控绕过、代理轮换或验证码自动处理。WBI仅按普通网页传输协议签名。现有浏览器已登录，不意味着Python会自动取得该会话。

## 运行与离线验收

在PowerShell中执行：

```powershell
Set-Location 'LOCAL_USER_HOME\Desktop\cx原神产品运营\B站高难副本社区观察_20261017\采集工具'
python -X utf8 tests/run_checks.py
python -X utf8 run.py --help
$studyPath = '.\正式采集_v6_20261017'
python -X utf8 run.py --study $studyPath status
```

新研究目录必须不存在，防止覆盖已有冻结版本：

```powershell
python -X utf8 run.py --study '.\新研究目录' init
```

成功退出码为0，门槛失败/访问失败为2，中断为130。正式批处理应检查退出码。`STOPPED`不能解释成“已经采完”。

## 先核定配置

编辑研究目录内`config.json`：

1. 为三个模式填`period_id/start/characteristics/evidence/verified_by`。`start`必须带时区，如`+08:00`；须核定国服实际开放时刻，不能把候选日期直接补为零点。模板没有替你填写未核实的期次。
2. 填三个模式共用的`T0`（键名`t0`），必须已经到达。记录`confirmed_by/confirmation_record`，后续不能边抓边延长窗口。
3. 保留全部90个查询组合：54个主查询，A、B各18个。关键词和排序逐字来自方案。新增词/日期过滤须在执行前登记；已冻结配置变更需建新目录并记录原因。

```powershell
python -X utf8 run.py --study $studyPath validate
```

`http.max_pages`是防止程序失控的上限，触及它始终算未完成。当前按1000结果/50页警戒。已实现触顶区间按整数秒二分、叶区间完整分页和无缺口覆盖检查，但**本轮日期参数未通过负向边界验证，暂不可用于正式执行**。日期分箱需`verified_status=passed_positive_and_negative_boundary_checks`及证据哈希；不得为通过门槛手填这一状态。正向首页恰好都在范围内不够。修正普通接口契约后须登记新版本，保留失败版本，不能简单调大上限或标为成功。

## 检索、审核和冻结视频库

主检索与两组封存审计依次执行，中间必须核验候选并建立检查点：

```powershell
python -X utf8 run.py --study $studyPath discover --group main
python -X utf8 run.py --study $studyPath enrich
# 编辑 video_review.csv，核定所有候选的纳入/排除与本期内容证据
python -X utf8 run.py --study $studyPath checkpoint --group main
python -X utf8 run.py --study $studyPath discover --group audit_a
python -X utf8 run.py --study $studyPath enrich
# 再审核新增候选
python -X utf8 run.py --study $studyPath checkpoint --group audit_a
python -X utf8 run.py --study $studyPath discover --group audit_b
python -X utf8 run.py --study $studyPath enrich
# 再审核新增候选
python -X utf8 run.py --study $studyPath checkpoint --group audit_b
python -X utf8 run.py --study $studyPath paths-template
```

`video_review.csv`一行一个BVID×副本：

| 字段 | 填写规则 |
| --- | --- |
| `mode` | `abyss/theater/stygian` |
| `decision` | `pending/include/exclude`；不删除不相关命中，填exclude与理由 |
| `period_evidence` | 视频本身讲本期的证据，如00:32敌阵画面及期次标识；标题不足以替代 |
| `aid/primary_up/coauthors` | 平台公开ID字符串，协作者用分号分隔 |
| `published_at` | Unix秒时间戳；`enrich`正常返回后填入；必须不晚于T0 |
| `content_type` | 主类`guide/record/discussion`；其他内容可填其他类，不因此排除 |
| `tags` | 正常页面公开标签，用分号分隔；确实无标签填`<none>`，不要用空值冒充查过 |
| `reason/reviewer` | 每行必须有；待核项不进入正式库 |
| `relations/config_evidence/outcome/notes` | 素材引用、协作、配置、自述结果及待核事项 |

`enrich`只补公开元数据，不判断期次。旧35条来源的角色不继承，播放量、UP数量和攻略比例不影响纳入。原来15条名单之外的合格来源全部保留。

标签和UP投稿列表路径由`paths-template`按纳入来源生成。**本版自动化检索覆盖关键词API，标签/投稿列表需正常页面人工分页核验，未实现其自动翻页。** 在`paths.csv`登记终点、证据和核验人；新增视频通过下列方式回填，再统一审核。新UP/标签会生成新的待核路径，需要处理到完整结束。

```powershell
python -X utf8 run.py --study $studyPath import-candidates --file '.\新增来源.csv' --path-id '实际paths.csv中的path_id'
python -X utf8 run.py --study $studyPath enrich
python -X utf8 run.py --study $studyPath paths-template
# 所有发现路径、入排与待核项处理完成后
python -X utf8 run.py --study $studyPath freeze-videos
```

新增来源CSV至少有`bvid,mode`；或使用原候选的`bvid,副本`列。该命令只导入候选。路径`status=complete`须有实际证据；模板生成不算执行。无法处理的路径应保留pending/failed，正式冻结会失败。

审计B及其后的路径仍新增合格视频时，脚本仍保留所有新增，`coverage_stable=false`。可以按明确列出来源的冻结库继续研究，但不能宣称“检索充分/全站覆盖”。

## 评论全量清单与独立核验

```powershell
python -X utf8 run.py --study $studyPath collect
```

正常网页适配器按时间游标枚举根，直到明确`cursor.is_end`；有回复的根逐页枚举完整回复并确认空末页，不因根在窗口前而跳过。根声明0回复的线程单列，并与根+回复全域返回数量一起核对。程序终点仍需独立页面核验。线程预览不作为完整回复。置顶重复保留观测、实体只存一条；同文不同ID、同作者多次发言全部保留。

`comments.jsonl`保存原文、ID、根/父关系、创建时刻、作者匿名ID与角色；`observations.jsonl`保存每次返回位置。`cache/`保留成功响应的研究字段及原始字节哈希，普通用户的昵称、IP、性别和会员信息不落盘。图片/附件元数据在缓存，规范清单保留存在与可读性标记；不会自动读取图片并推断情感。配置中不保存账号密码或认证头。

`events.jsonl`记录每个请求、页码、ID与失败原因。相同研究目录和配置重跑会复用成功缓存，失败请求不缓存；不会默默把旧页刷新到新时点。若数量变化、排序漂移或需要新时点的完整抓取，请建立新采集版本，保留旧版本。实际可见性只对应所记录抓取区间。

完成程序枚举后，还须编辑`collection_review.csv`：

- `status=accepted`：核对`count_semantics_evidence`，确证接口count是根/回复哪一口径。
- 填页面显示的`ui_count/ui_count_scope`与差额解释`reconciliation`；页面全历史总数不是窗口根数。
- `pagination_evidence/reviewer`记录正常末页、回复完整与独立页面核验。数量碰巧相等不能单独判为完整。

```powershell
python -X utf8 run.py --study $studyPath freeze-comments
python -X utf8 run.py --study $studyPath coverage-audit
```

任何视频缺页、回复不全、ID异常、正文缺失、父发言丢失、重复页、数量漂移或未完成核验都会阻止冻结。`comment_frame.json`内嵌正文快照、各副本窗口ID、仅语境ID、冻结哈希和抓取区间。窗口外祖先不进统计分母；同一发言涉及多个模式可进入各自域，域内一次。

## 定性探索、预留验证与代码本

```powershell
python -X utf8 run.py --study $studyPath qual-init
# 填 qual_holdout.csv，预留每副本至少3名未读主UP的视频及理由
python -X utf8 run.py --study $studyPath qual-reserve
python -X utf8 run.py --study $studyPath qual-queue --mode abyss --bvid '实际BVID' --role development
```

`qual_screening.csv`是独立的相关性工作表。按`qual_queue_*.csv`的随机顺序核验，填`related/irrelevant/unknown`及证据，`final=yes`；重跑同一qual-queue按原序推进到最多30条相关发言或穷尽。上下文在冻结清单按ID回查，另记为语境，不补入概率分母。

`qual_batches.csv`按实际阅读顺序记录：`role=base/development/validation/new_information`，`bvids`分号分隔，新增问题/条件/反例填非负整数；没有未解决缺口时`unresolved_gaps=none`。需人工写证据与定稿。基础至少6名UP、尽量各两条攻略/实录/讨论；每追加批至少3名新UP，连续3批无实质新增后方可打开预留验证来源。

```powershell
python -X utf8 run.py --study $studyPath qual-queue --mode abyss --bvid '已预留且此前未读的实际BVID' --role validation
python -X utf8 run.py --study $studyPath qual-status
```

验证至少3名未用于开发的UP。新信息重置充分性；再预留全新的来源登记新reserve版本。后续主统计发现实质新信息，也应补`new_information`批次。程序检查批次结构与来源复用，**新问题/条件/反例的实质判断由人完成**。库太小、某类不存在或达不到三批时，保留“未验证”；本版未自动实现有限库全量主题普查的替代验收，不应伪造额外批次。

探索后编辑`codebook.json`，不能只沿用试采五类封闭分类。格式示例：

```json
{
  "version": "你核定的版本",
  "relevance_rules": "完整写明本期相关、不相关和不明的规则",
  "context_rules": "短句、图片、祖先缺失和多副本的判断规则",
  "themes": [
    {"id":"你定义的主题ID", "definition":"定义", "include":"纳入例子", "exclude":"排除例子"},
    {"id":"other_current_experience", "definition":"其他本期体验", "include":"例子", "exclude":"例子"}
  ],
  "examples": "混合表达、正向、低互动及难度未知的例子",
  "reviewer": "人工核定人",
  "exploration_review": {"status":"limited", "evidence":"探索证据位置和局限；只有结构验收通过才能填completed", "reviewer":"人工核定人"}
}
```

`limited`允许冻结预定义指标，主题充分性仍单独不通过；不会因代码本填了一个状态就自动声称充分。

## 正式随机队列、400条主样本与固定200条原始审计

```powershell
python -X utf8 run.py --study $studyPath freeze-codebook
python -X utf8 run.py --study $studyPath draw
python -X utf8 run.py --study $studyPath export
```

`draw`只运行一次。代码本与清单先冻结，后生成256位新种子；记录生成器、源码版本、各用途独立随机流与全排列。采用HMAC-SHA256计数流、拒绝取模和Fisher–Yates，不依赖Python随机库版本。`draw.json`和`.sha256`可重放，不能删掉重抽至观点/来源均衡。

按`main_queue.csv`处理`screening.csv`。每副本随机排列所有原始窗口ID，依次相关性定稿，到400条`related`停止；待核项阻止向后越过。`irrelevant/unknown`保留原因，不手工补选。如果穷尽仍不足400，则全部合格域普查，不跨期凑数。`export`可反复重建，不更换种子。

`raw_audit_queue.csv`与`raw_audit_review.csv`是各副本另外固定200条**未经过相关性筛选**的审计，不足200全取。应独立核验相关性、语境、日期和角色，并填`role_checked/date_checked=yes`。可以与主样本重合，不能因为不相关而补足200条相关。总体相关率用这份审计，不能用“400/主筛查扫描数”。

正式编码字段：`themes/self_experience_themes`用分号分隔的冻结主题ID；前者是提及，后者是本人经历，二者分开统计；没有主题可留空。`experience_kind`区分本人、转述、求助、推测、解释等；`sentiment`可为正向、负向、混合、中性/不明。`context_status`记录语境核查状态。所有主统计记录须人工定稿。

```powershell
python -X utf8 run.py --study $studyPath lock-selection
```

该命令保存当时完整筛查快照及接受顺序，再从每副本主样本随机抽最多100条盲复核。`coding_blind_v1_material.csv`只提供正文和语境ID，不显示原主题；在`coding_blind_v1.csv`填复核码、复核人、`review_kind`、是否需要修正`corrected=yes/no`、裁决依据`resolution`与定稿。

`review_kind`须如实写`human_ai_agreement/same_person_blind_recode/independent_human_coders`等，不能把人机或同人重码写成两个人工独立编码。随机复核与额外定向稀有正例分开。

固定规则下纠错：改工作表后运行`revise-selection --reason '具体误判与影响范围'`。它沿用原种子、原顺序，新增不可覆盖的修订文件和新盲复核文件；旧快照、旧复核仍保存。若改变目标总体或相关性规则，应新建方案/研究版本，不能冒充普通纠错。新主题先作为探索发现，另行登记确认性验证。

## 估计与验收输出

```powershell
python -X utf8 run.py --study $studyPath estimates --draft
# 原始审计、相关性风险、随机盲复核及裁决都完成后
python -X utf8 run.py --study $studyPath estimates
```

- 逐副本、逐主题给出分母、数量、比例和单项名义95% Wilson近似区间。400条为主域约±5个百分点设计；不保证子组、多主题联合覆盖、漏检和误码误差。
- 穷尽合格域的普查不附加库内抽样误差，漏采、漏检、误判风险仍单列。
- 同时给出根/回复、排除视频作者、删除最大贡献UP/最大线程、时间三等分的敏感性结果。变化超过5个百分点只触发复查，不自动判为偏差；新分母/子组精度不沿用主域保证。
- 固定原始审计中，“相关或不明”的不明占比95%上界须≤5%；不足以支持判断仍不通过。全原始域审计普查则按已知域比例判断。
- 随机盲复核一致率≥90%、修正率≤5%，未裁决分歧会阻止发布。代码报告的是一致性与流程阈值，不是真实准确率。
- 没完成审计或复核只输出`estimates_DRAFT.*`。`estimates_current.json`表明最近一次运行状态，旧文件不是自动更新的结论；改输入后必须重跑验收。数据结果内含相应输入哈希。
- 定性充分性、检索覆盖稳定性与统计发布门槛分别报告，不合成一个“代表性已证明”。不生成三副本混合总占比，也不写成独立玩家比例。

Wilson方法参见[NIST手册](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)。有限总体精确超几何区间未实现；本版不套用临时聚类设计效应。

## 实际接口验证和续采边界

保留的旧HTTP适配器使用普通view、search/type及页码根接口。配置`adapter=web_wbi_v1`后使用正常网页会话及`wbi/view`、`wbi/search/type`、`reply/wbi/main`和`reply/reply`。这些不是本项目取得服务承诺的稳定接口。当前已核验一条小来源的完整根/回复；大来源仅验证了有后续游标的首屏，不能称全域采集通过。

接口恢复普通可访问后，用新隔离目录运行`smoke --bvid 实际小视频`，核对页面中的根/回复/置顶结构和分页数量口径，再决定适配器是否需要调整。本版不会自行换风控通道。401/403/412/429、API非零、非JSON或`code=0`但data含`v_voucher`的访问校验立即停止，不并发重试；旧校验缓存也拒绝。仅普通网络错误/5xx有限退避重试。更改访问会话或采集时点应使用新目录，避免混合受限缓存和完整清单。

如使用者自行提供合法可用的Netscape格式会话文件，可以仅在本机设置`BILI_COOKIE_FILE`环境变量；工具不要求上传它、不提取浏览器凭证、不把Cookie写入配置、日志或响应缓存。认证过期/限制仍按失败报告，不承诺提供凭证就一定可全量枚举。

### 本机正常扫码登录

`local_bili_login.py`使用B站官方登录页前端实际调用的二维码生成/状态查询端点，不读取右侧浏览器的资料。用户在手机B站App扫码并确认，程序核验`nav.isLogin=true`后，将B站Cookie保存成Netscape文件。普通网页登录会话本身具有账户权限，本项目采集代码只发出读取请求。登录接口来源见`扫码登录接口来源.json`。

```powershell
python -X utf8 local_bili_login.py --output 'LOCAL_USER_HOME\AppData\Local\bili\cookies.txt' --control 'LOCAL_USER_HOME\AppData\Local\bili\login_status.json' --lib 'LOCAL_USER_HOME\AppData\Local\bili\helper_lib'
```

本机使用PyPI的`qrcode`包生成图片；`--lib`为可选依赖目录。二维码只在内存和绑定`127.0.0.1`的临时页面中提供，页面不提供Cookie读取接口。二维码约3分钟内需确认；不会自动循环生成新会话。文件写入前限制为当前Windows用户可读写，已有文件拒绝覆盖；状态文件只写入状态、目标路径和数量，不含Cookie或二维码密钥。重新登录需要显式选择新的文件名。

2026-10-17用户正常扫码登录后，实际核验通过：5个B站Cookie、有效登录、Netscape文件重新加载成功。未提取或解密浏览器存储。新日期边界契约见`登录后契约核验_20261017/日期边界契约.json`：0为不限日期标记，正式分箱从Unix秒1开始；近期命中、远古空区间、单秒包含和相邻秒排除通过。空区间明确返回`numResults=0,numPages=0`时可以省略`result`；非零响应缺少列表仍失败。

普通搜索实际还出现了页间部分重叠和总数变化。当前正式v5对这些区间继续按已核验日期边界二分，而非把异常父区间算作完成；只有正常分页结束、唯一数与返回总数一致的叶区间可计入完成覆盖。父区间命中、失败与拆分原因全部保留；单秒仍异常、日期越界、访问失败或超过请求上限仍停止并拒绝冻结。没有增加视频配额或按观点删减来源。

CSV用于审核和查看，**ID列导入Excel时必须设为文本**，否则表格软件可能把长ID变成浮点数。JSON/JSONL和冻结文件始终保存字符串ID，是程序主依据。CSV对公式开头字符作显示转义，原文在JSONL中保留。不要分享`.private.json`或认证文件；发布报告使用匿名评论者ID即可。

## 已知需要人工或后续适配的部分

视频本期归属、标签/UP列表完整路径、图评语境、实质主题新增和编码裁决仍需实际审核。真实登录与日期边界契约已通过，正式检索和全根/回复分页另行验收；不能据此声称已获得正式样本或验证了样本代表性。
