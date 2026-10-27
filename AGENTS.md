# 原神高难副本社区观察

本仓库保存固定来源的研究、可回查材料和可离线阅读的网页报告。
先读 [PROJECT_STATUS.md](PROJECT_STATUS.md)，方法见 [METHODS.md](METHODS.md)，不要从历史交接说明推断现役状态。

## 目录与技术

- `report/报告.md` 是现役正文，`analysis/content-20261024/` 是现役内容判断与统计。
- `web/` 为模板、CSS、JavaScript；`docs/` 为生成的静态网站和CSV下载。
- `scripts/` 使用Python标准库与Node；Markdown渲染依赖锁定版本的marked。
- `materials/` 的4,642个文件是公开历史证据；`publication/` 记录来源、脱敏和公开哈希。
- 通用采集工具另在bili-community-observer维护，本仓库只复现这份研究。

## 工作边界

- 除非当前用户明确要求，不重采、不换源、不重抽、不重做语义判断。
- 原始数据、标签002、历史响应和旧版本证据不覆盖；有新增分析时另存并说明版本。
- 30条用户认可校准属于旧主题编码；已取消的第二批30条独立核验不恢复。新内容编码由AI完成且无独立准确率检验。
- 发言、匿名作者与玩家总体分开；旧主题分母与新内容分母分开；点赞不能代表赞同人数。
- 报告聚焦反馈、态度与期待；不恢复已删除的“展示的项目能力”、独立民族志说明或浅层运营动作。
- 公开文件不含个人本机路径、联系方式、Cookie和私钥；视频URL与匿名研究标识可保留。
- 不修改宿主生成记忆、全局规则或同级项目；项目事实在PROJECT_STATUS.md维护。
- 删除、移动档案或清场须先呈现清单，待用户看完汇报后明确确认。

## 离线复算与交付

在仓库根目录执行：

```bash
python -X utf8 scripts/analyze_content.py
python -X utf8 scripts/validate_content.py
npm ci --ignore-scripts
npm run render
python -X utf8 scripts/build_site.py
python -X utf8 scripts/update_public_manifest.py
python -X utf8 scripts/validate_project.py
```

没有正文或渲染改动时不必重装依赖。`docs/index.html`可直接打开。
更新文档后校验链接与公开哈希；更新正文后核对生成结果和下载稿。上面命令不访问B站。
已保存的语义判断是汇总器输入，复算通过不表示判断准确率已得到验证。
当前研究已经交付；后续按用户的新任务继续，没有默认待重采或补人审事项。
