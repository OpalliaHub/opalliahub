# v2 实现与验收记录

当前源码为 **2.1.1**。此次 JobsDB V7 适配包括会话复用、有界分页与重试、跨访客共享冷却、明确停止原因，以及本批关键词筛选范围说明；实际测试、真实联网及 GitHub/云端更新结果以 [JOBSDB_V7_VERIFICATION.md](JOBSDB_V7_VERIFICATION.md) 为准，不能沿用旧版测试数量或云端成功记录。

此前 v2.1.0 的简历优势与岗位推荐验证见 [RESUME_VERIFICATION.md](RESUME_VERIFICATION.md)；2026-11-19 已观察的原生云服务、公网 HTTPS、完整研究迁移、公开 API/真实 AI、Safari 图表操作、GitHub 五环境 CI 及临时部署访问清理见 [CLOUD_VERIFICATION.md](CLOUD_VERIFICATION.md)。该记录中的 **342 项**属于当时 v2.1.0 的实际测试，不是 v2.1.1 的新计数；当时未重新进行云端窄屏/导出测试。以下保留 2026-11-18 v2.0 的原始验收及其当时未部署状态，不将历史 **306 项**或旧状态冒充当前结果。

版本：2.0.0；记录日期：2026-11-18。本文记录已观察证据与剩余验收。**双 Python 版本各 306 项测试、质量门禁、真实本机 Gunicorn smoke，以及桌面/窄屏对话和三种导出均已验证**。历史证据保留其原始运行范围。

## 本轮范围

- 默认首页改为职业/人力资源「研究总览」，保留岗位、简历、投递、技能成长和深度研究。
- 左侧平台、右侧跨页面常驻 DeepSeek 对话；窄屏平台/对话切换。代码实现与最终交互验收分别记录。
- 真实 SQLite OLAP、总体分母、季度等维度、多序列趋势、热力图与精确下钻。
- 自然问题→受限指令→自动查询→真实图表，不增加手动批准步骤；保留旧深度研究的单计划预览路径。
- 免登录公共访客空间、个人数据/任务/结果隔离、来源/配额边界、只读共享索引。
- 共用 HTTP 边界与生产 WSGI、Docker/Compose/TLS 代理部署准备。

## 已观察到的局部证据

| 检查 | 已观察结果 | 证据与限定 |
| --- | --- | --- |
| 版本标识 | `jobcompass.__version__` 为 2.0.0 | 代码版本不等于部署版本 |
| OLAP/自动命令专用测试 | 37 项通过：22 OLAP + 15 编译器测试 | 本机历史联合回归日志；含真实 SQLite 与模拟模型，不代表完整应用总数 |
| 研究模块与上述功能联合回归 | 64 项通过 | 本机历史研究回归日志；发生在最终公开模式/界面集成收尾之前 |
| 真正的 DeepSeek 自动执行 | 一条“按来源标示月份统计当前平台岗位广告数并画折线”命令成功编译并执行 | [analytics_live_check.json](analytics_live_check.json)；当时 7,277 条广告、19 个分组、模型 deepseek-flash；不外推其他问题的准确率 |
| 目录启动优化 | 研究所选目录 10.6712 s → 1.0379 s；当前所选目录 0.5087 s | [之前](evidence/v2/catalog-before.json)、[之后](evidence/v2/catalog-after.json)；251,042 研究广告/7,277 当前广告；未加应用缓存，未清空操作系统缓存，非云性能承诺 |
| 真实测试先行 | 保留缺失模块、非法日期分组、职业多序列折线、目录误扫描等实际失败及修复 | [OLAP red](evidence/v2/olap-red.txt)、[AI red](evidence/v2/analytics-ai-red.txt)；不倒填开发历史 |
| Python 3.12 快照兼容 | 修复 HTMLParser EOF 未 close 导致末尾裸 `R&D` 缓冲；重新验证 6,910 条有效快照，随后 fresh DB 导入 6,908 条 | [parser red](evidence/v2/parser-red.txt)、[parser green](evidence/v2/parser-green.txt) 与 Gunicorn smoke；这是部署兼容修复，不是新数据质量结论 |
| 新对话实际职业比较 | 主代理观察到季度 × 职业类别命令自动返回 136,380 条样本、36 组和三条折线 | [浏览器验收](evidence/v2/ui-check.json) 与截图已归档；仅证明所测指令 |
| 模型标题偏差 | 该次模型把 ads 图建议标题写成 Python 提及；现从实际 query 生成主图、聊天结果与导出统计标题 | 模型建议标题仅留在高级信息；说明真实模型仍可能误述，不能把建议文字当作统计事实 |

## 集成结果与剩余验收

| 项目 | 状态 | 证据与范围 |
| --- | --- | --- |
| 完整 unittest discover | **Python 3.8.10 与 3.12 各 306 项通过** | [Python 3.8 日志](evidence/v2/unittest-python38.txt)、[Python 3.12 日志](evidence/v2/tests-v2-python312.txt)；同一套测试分环境运行，不相加为 612 个不同测试 |
| 静态、doctest、属性、变异与质量门禁 | **Python 3.8.10 完整 quality_gate --mutations 通过** | [门禁报告](evidence/v2/quality_gate.json)：54 个 Python 文件语法无误、源扫描无发现；[8 个 doctest](evidence/v2/doctest.txt) 通过；[5/5 指定变异](evidence/v2/mutations.json) 被检出，仅代表选定故障集 |
| 公共会话隔离与生命周期 | **42 项公共相关测试通过，包含在 306 项内** | [公共边界](evidence/v2/public_boundary_green.txt)、[会话入场](evidence/v2/session_admission_green.txt)；不重复计数，覆盖私有状态/任务/结果、运营库隔离、TTL、忙任务与重启边界 |
| 公共源/请求/配额边界 | 已落地并经公共相关测试验证 | `JOBCOMPASS_PAGE_HOSTS` 默认空，robots/每次跳转校验；会话创建 12/IP/小时、120 全局/小时；请求和 AI 配额另行控制。真实云代理尚未验收 |
| 实际 Gunicorn smoke | **Python 3.12 + Gunicorn 27.0.1 通过** | [实际进程记录](evidence/v2/gunicorn-smoke.json)：1 worker/8 threads、fresh DB 6,908 条、匿名公开模式、Secure/HttpOnly cookie、运营简历排除、错误 Origin 拒绝、18 个 OLAP 月份组。使用 `--no-control-socket`，同选项已进入 Docker CMD；本机 smoke 不是 Docker/TLS/云测试 |
| 桌面左平台/右常驻对话 | **1440 × 1000 浏览器验证通过** | 两轮真实 DeepSeek 指令先比较季度/职业类别广告数，再改 Python 提及率，保留筛选；136,380 广告/36 组。跨技能成长页面聊天保留，控制台无警告/错误。[桌面对话](screenshots/v2-desktop-chat.jpg)、[OLAP 视图](screenshots/v2-olap-chat.jpg) |
| 窄屏平台/对话切换 | **390 × 844 浏览器验证通过** | 平台→对话→平台切换正常，输入区可见；DOM 可视宽度和滚动宽度均 390，无水平溢出；临时视口测试后恢复。[窄屏截图](screenshots/v2-mobile-chat.jpg) |
| 图表与导出 | **三类导出实际下载并核对** | CSV 36 行、JSON 36 组且 query/totals 一致；PNG 1676 × 840 可读。实际点击分组得到季度/职业类别 exact_filters 与月份下钻，重置恢复全样本；折线/热力切换正常。[导出核对](evidence/v2/ui-exports.json)、[PNG](screenshots/v2-export-chart.png) |
| 新版交付包 | **最终 184 个文件的白名单检查与凭据扫描通过** | 当时的 v2.0 归档（本机保留）；最终 SHA 单独记录在 `dist/package-verification-v2.json`。原门禁报告保留其当时 157 个成员的候选包 SHA；v1.3 归档保留。 |
| GitHub 更新/远端 CI | 未在本文确认 | 实际远端 URL、commit 与 Actions 记录；配置工作流不能记成运行成功 |

## 本机无法完成或尚无目标环境的项目

- **Docker 镜像未构建。** 当前电脑未提供 Docker；现有 Dockerfile、Compose 和健康检查只是可审查的部署配置。
- Caddy/Nginx 配置未代表真实 TLS 已生效。实际域名、证书、代理来源 IP、DNS 与云服务器信息尚待提供和验收。
- 云站点尚无本文验证的上线地址，不将 GitHub 仓库链接称为可直接使用的平台。
- 单 worker、内存/CPU/会话/AI 默认配额是设计与配置边界，不是已通过云压力测试的容量保证。
- 匿名 workspace 是临时会话数据，不承诺跨重启恢复、跨设备同步、数据库加密或磁盘安全擦除。

## 结果解释与版本保留

OLAP 统计为广告样本和固定词语探针；不把提及率写成真实技能要求、整体劳动力需求或因果影响。模型生成的解释与标题仍需核对，单条供应商请求成功不证明所有自然语言都被正确理解。总体指标不依赖当前图表显示上限，缺失时段和组合不补零。

历史验证日志保持原始版本；本记录不代表独立人工评审或人类标注。

交付包校验和由 `dist/package-verification-v2.json` 单独记录，避免把校验清单自包含进同一个压缩包。保留尚未完成的 Docker/云端项目；本文没有声明 GitHub 更新、远端 CI 或云站点上线。
