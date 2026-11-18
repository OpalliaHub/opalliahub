# AI 辅助代码审查记录

审查对象：本项目初始实现及 2026-09-30 研究数据与启动指引修订。审查由生成代码的同一 AI 进行，不构成独立第三方审计。后续小组成员应结合源码及测试亲自复核。

| 问题 | 修改或处理 | 验证 |
|---|---|---|
| Java 误命中 JavaScript，Go 误命中 Google | 英文词边界规则 | test_word_boundaries |
| 3–5 年被理解为 5 年 | 经验范围采用下界 | test_experience |
| 远程岗位被视为任何地点 | 保留居住地限制 | test_remote_restrictions |
| 只有英语／沟通的无关岗位分数偏高 | 技能改为加权 F1，通用技能权重 0.2 | test_generic_skill_does_not_dominate |
| 未知要求被当作满足 | 排除未知分项，显示覆盖率 | test_missing_weight |
| 更新岗位覆盖投递进度 | 单独的 applications 表及外键 | test_preserve_application |
| 错误导入出现部分写入 | 整批校验再事务写入 | test_import_transaction |
| CSV 公式注入 | 危险前缀加单引号 | test_export_formula_escape |
| UI 显示不可信岗位 HTML | 服务端清理 + 前端转义 | plain 单测与浏览器检查 |
| 本机服务被外部页面写入 | 回环绑定、Host／Origin、自定义头、CSP | HTTPTests |
| API 密钥出现在前端 | 只返回 configured 和 model | test_no_key_exposed、test_env_not_served |
| AI 输出空值、数组类型异常 | 模式特定 schema 校验并报错 | test_ai_schema、test_ai_malformed |
| 旧简历的 AI 结果污染新简历 | 保存前比较请求时原文 | server.Application 的 run_ai |
| 长网络操作阻塞 UI | 后台线程池与轮询 | 浏览器真实 AI 润色检查 |
| 本机 Fake-IP DNS 阻止官方 API | 官方固定主机单独策略；通用网页保持公开地址检查 | 两源 + DeepSeek 真实请求 |
| 缓存零岗位时错误显示成功 | 明确返回上次尝试无数据和下次时间间隔 | source cache behavior |

仍需考虑的限制：通用网页抓取的 DNS 校验不是完整网络隔离；本机数据库未加密；英文技能词典覆盖有限；没有真实标注招聘评估集；相同 URL 的跨来源记录未自动合并；历史下线岗位需要回原站核查；AI 可能错误润色，因此保留原文和人工核实提示。

运行证据见 tests、docs/evaluation.json 与 docs/live_check.json。未执行云端 CI、渗透测试或独立人工同行评审，不应在报告中声称已完成这些工作。

## 后续修订核对

- JobsDB 档案过滤 macOS 元数据、限制大小、校验必需字段、按 ID 去重并输出清单。
- 研究快照保留 6,910 条有效记录，应用显式导入 6,908 条未在快照时标记过期的记录。
- 重复导入保留投递备注；错误批次不写入数据库。7 项新增 benchmark 测试纳入总计 71 项测试。
- 直接打开 HTML 导致绝对资源路径失效：改为相对路径并提供启动指引；已在 Safari 验证 HTTP 入口及真实样式加载。本次工具策略不允许直接访问 file URL，未声称完成文件模式浏览器验证。
- GitHub 当前是 ZIP 发布，不能将 ZIP 内的 Actions 配置描述为已经执行的 CI。
# v1.3 AI-assisted review — 2026-11-18

Reviewed learning.py and storage.py independently from their implementation agent. Checked: recursive cycle rejection, immutable cached prerequisites, per-job denominators, real/demo and expiry boundaries; atomic history updates, no-op saves, redo branch invalidation, migration, 50-entry limit and concurrent edits. No blocking finding in these reviewed paths. Tests and browser verification provide complementary evidence; this is an AI review, not a completed student peer review.

Ranking cache retains only one result, fingerprints all inputs and returns independent copies. Clearing the resume also releases the cache. Focused static analysis checks mutable defaults, bare except, direct eval/exec and wildcard imports. Remaining engineering risks and intentional scope are tracked in TECHNICAL_DEBT.md; actual GitHub Actions runs and peer sign-off are not asserted.

The following record is historical and keeps its original scope and counts.
