# 原神高难副本社区观察

**社区具体说了什么，涉及多少位作者？**

对6,526条B站发言逐条分析，研究深境螺旋、幻想真境剧诗与幽境危战的难度评价、具体卡点和投入取舍。2026年10月25日修订版增加内容分布、作者去重与来源敏感性分析。

[网页报告](https://chenergou847.github.io/genshin-community-research/) · [研究正文](report/报告.md) · [逐条内容编码](analysis/content-20261024/逐条内容编码.csv) · [观点分布](analysis/content-20261024/观点分布.csv) · [完整材料目录](materials/00_材料总目录.md)

| 研究规模 | 口径 |
| --- | --- |
| 固定视频来源 | 60条，三个副本各20条 |
| 已存评论正文 | 9,593个唯一ID |
| 全量内容复读 | 6,526条发言，4,469位匿名作者 |
| 纳入内容分析 | 5,163条；深渊1,156、剧诗1,124、幽境2,883 |
| 新增编码 | AI逐条阅读及同轮复核，未做独立准确率检验 |

## 主要发现

- **深渊的轻松更多得到认可。** 404条判断轻松，37位作者明确赞许这种体验，1位明确嫌缺乏挑战。
- **剧诗的负担落在前段与重来。** 89条批评开幕或试用角色，涉及72位作者；48条表达重开或流程疲惫。另有52条认可玩法乐趣。
- **幽境主要在讨论配置与复现。** 393条涉及资源、配置要求和投入取舍，370条比较配置与表现或追问复现条件；65条表达多队需要同一角色或希望角色分身。

正文同时列出发言条数、比例、去重作者和视频来源。作者评价表分为仅认可、仅不满、两种都表达过、未明确评价或不明，避免把重复发言当作更多人。

## 阅读与回查

1. [研究正文](report/报告.md)与[网页报告](https://chenergou847.github.io/genshin-community-research/)：发现、数量、15条原文证据与已存上文。
2. [内容分析目录](analysis/content-20261024/README.md)：编码定义、批次、复核、明细、作者及观点分布。
3. [方法与执行记录](METHODS.md)：检索、来源资格、观察窗口、人机分工和复算步骤。
4. [全流程证据索引](materials/01_全流程证据索引.md)、[研究时间线](materials/02_研究过程时间线.md)：历版方案、232／600条历史阶段、采集、修复与冻结标签。
5. [公开副本说明](PUBLICATION.md)：匿名标识、隐私处理与文件哈希。

## 仓库结构

```text
report/报告.md                 当前研究正文
docs/index.html               GitHub Pages 网页报告
docs/data/                    网页可下载的明细与统计CSV
web/                          模板、样式与交互
analysis/content-20261024/     新增内容编码、定义、复核和统计
scripts/                      离线汇总、渲染与核验
materials/                    4,642个历史材料文件
publication/                  公开副本来源、隐私处理与哈希清单
```

## 本地阅读与复算

打开`docs/index.html`即可阅读，页面不依赖外部字体或图表库。原视频和GitHub材料链接需要联网。

```bash
python scripts/analyze_content.py
python scripts/validate_content.py
python scripts/build_site.py
python scripts/validate_project.py
```

修改正文后，运行`npm ci --ignore-scripts`与`npm run render`更新网页模板，再构建页面。详细步骤见[METHODS.md](METHODS.md)。这些操作只处理既有材料。

[自动发布工作流](.github/workflows/pages.yml)会复算编码、核验内容及作者统计、重建网页并比对已提交的生成文件，通过材料与公开文件校验后部署。通用的采集、编码和交付工作流见独立的[bili-community-observer工具与Skill](https://github.com/chenergou847/bili-community-observer)。

研究描述固定来源下出现的发言和作者，未进行玩家总体抽样。来源集中、未读附图、缺失上文及AI编码验证范围见[正文第7节](report/报告.md)。原采集主档和标签002保留在`materials/`，新增内容分析单独保存。
