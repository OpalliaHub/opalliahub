# JobCompass 软件需求与设计规格

版本：**2.1.0**；修订：2026-11-19。本文描述当前代码与验收条件，不等同于已完成全部运行环境验收。新增推荐证据见 [RESUME_VERIFICATION.md](RESUME_VERIFICATION.md)，本轮云服务与 GitHub 的实际结果见 [CLOUD_VERIFICATION.md](CLOUD_VERIFICATION.md)，既有研究功能证据见 [V2_VERIFICATION.md](V2_VERIFICATION.md)。v1.3 的课程映射、验证报告及 2026-09-30 Word/PDF/PPT 保留为历史材料；此前缺失的原始大作业 DOCX 尚未重新核对，不能据此宣称全部课堂提交已完成。

## 目标、运行模式与非目标

平台面向人力资源/职业研究访客及求职者。默认进入「研究总览」，通过真实招聘广告样本进行多维统计、职业比较和词语提及趋势分析；个人工具保留简历匹配、投递跟进和学习路线。桌面结构为左侧平台与图表、右侧跨导航常驻 DeepSeek 对话；窄屏使用平台/对话切换。布局与导出最终验收单独记录。

本地模式仍通过 `main.py` 在回环地址运行，保存个人持久数据。公开模式使用同一业务应用与受控 HTTP 边界，访客无需注册或登录，通过随机 cookie 获得私有临时工作空间。共享岗位目录与只读研究索引可供访客分析；简历、备注、导入、AI 输出、结果文件和任务状态不得跨会话泄漏。

范围包含本地与匿名公开部署，不包含用户账户/跨设备同步、自动投递、登录站点反爬绕过、OCR、招聘决策、真实技能认证、薪资标准化、因果推断或本地 LLM 训练。本轮原生 Python/systemd/Nginx 云服务已通过受信 IP 地址 HTTPS 健康检查；使用域名或受信 IP 证书都必须保留精确 HTTPS origin/Host 约束。Docker 镜像未构建，研究库迁移与云端业务验收的状态单独记录。单进程匿名状态设计不支持直接多 worker 或横向扩容。

## 保留需求 FR01–FR20

| ID | 功能与验收条件 | 实现与验证入口 |
| --- | --- | --- |
| FR01 | 简历 30–40,000 字符；无效输入不覆盖旧记录 | `resume.parse_resume`、`Application.post`、`test_core.py` |
| FR02 | TXT/MD/DOCX/文字 PDF，上传上限 5 MB | `resume.extract_file`、`test_core.py` |
| FR03 | 规范技能、学历、经验与原文证据 | `resume.py`、`test_core.py` |
| FR04 | 固定公开 API 来源隔离、缓存与有限重试 | `sources.collect_api`、`test_core.py` |
| FR05 | CSV/JSON/JSON-LD/手动岗位规范化 | `sources.py`、`test_core.py` |
| FR06 | 排名分、有效分项权重、缺失技能和条件覆盖率 | `matching.py`、`test_core.py` |
| FR07 | 岗位检索、来源/地区筛选及分页 | `static/app.js` |
| FR08 | 投递状态与备注持久化 | `storage.py`、`test_core.py` |
| FR09 | AI 简历优势、润色与岗位解读，校验输出并防旧结果覆盖新简历 | `ai.py`、`server.py`、`test_http.py` |
| FR10 | AI/采集使用有界后台任务，不阻塞 HTTP 请求线程 | `Tasks`、`test_task_queue.py` |
| FR11 | 岗位 CSV 导出，中和公式前缀 | `server.csv_export`、`test_core.py` |
| FR12 | JobsDB 快照、清洗清单与可复现 benchmark | `benchmark.py`、`test_benchmark.py` |
| FR13 | 误开本地 HTML 时提示通过服务访问 | `static/index.html` 与启动脚本 |
| FR14 | 平台内更新 JobsDB，限量、间隔、进度、取消与状态保留 | `jobsdb.py`、`test_jobsdb.py` |
| FR15 | 纵向原库只读，精简索引、队列与可复现研究结果 | `research.py`、`test_research.py` |
| FR16 | 深度研究单计划编译：自然语言生成受限 JSON，可预览后手动执行 | `research_ai.plan_command`、`validate_plan`、`test_research.py` |
| FR17 | 技能成长的标题筛选、去重、过期排除、频次和样例证据 | `learning.py`、`test_learning.py` |
| FR18 | 简历缺口与递归先修路线，拒绝循环依赖 | `PrerequisiteGraph`、`test_learning.py` |
| FR19 | 最近 50 次投递状态/备注修改持久撤销重做，新分支清空重做 | `Store.application_history`、`test_history.py` |
| FR20 | 受限多步研究助手：最多 1–4 个逻辑模型回合，四类聚合工具、取消与轨迹 | `research_agent.py`、`test_research_agent.py` |

FR16 的预览/确认仅属于保留的单计划深度研究入口。**它不是 v2 首页所有 AI 操作的统一流程。** FR20 仍要求该功能的发送授权，界面默认三回合；每回合可能包含最多三次瞬态 HTTP 尝试，不代表费用上限。

## v2 新增功能需求

| ID | 功能与验收条件 | 实现与验证入口 |
| --- | --- | --- |
| FR21 | 真正的 SQLite OLAP：1–2 个合法维度、4 项指标、参数化筛选、精确下钻与稳定排序；最多显示 100 组 | `olap.py`、`test_olap.py` |
| FR22 | 自然语言→受限统计指令→自动执行→图表结果；无需人工复制或确认 JSON；无效/不支持请求不执行 | `analytics_ai.py`、`test_analytics_ai.py` |
| FR23 | 后续命令使用前次查询和有界总量；不发送原始行或隐藏文本筛选值；实际继承/替换口径可检查 | `analytics_ai._safe_context`、`_instruction`、`test_analytics_ai.py` |
| FR24 | 折线/多序列职业比较、柱状、热力图、统计表、点击下钻与 CSV/JSON/PNG 导出；缺口保持空值 | `static/analytics.js`、`UI_V2.md`、`V2_VERIFICATION.md` |
| FR25 | 所有访客产品功能免登录；匿名浏览器有隔离的简历、偏好、备注、导入、历史、研究结果和任务 | `public.py`、`web.py`、`test_public.py`、`test_public_http.py` |
| FR26 | 共享目录与只读研究索引供分析；公开访客不能连接任意服务器路径或重建共享索引 | `SessionStore`、`WebGateway`、`Research`、公共边界测试 |
| FR27 | 默认首页为研究总览，左平台/右常驻对话；轻量状态和目录先加载，个人工具延迟读取全量岗位状态 | `index.html`、`app.js`、`analytics.js`、最终界面验收 |
| FR28 | 公开自定义网页采集默认禁用；管理员可配置精确主机白名单，初始 URL/robots/重定向均受限 | 公共采集边界与相关 HTTP 测试；最终配置见 `DEPLOYMENT.md` |
| FR29 | 可部署的共享 HTTP/WSGI 入口、单 worker 运行模型、健康检查与 TLS 反向代理配置 | `web.py`、`wsgi.py`、`Dockerfile`、`deploy/`、`test_wsgi.py`；真实部署另行验收 |

### v2.1 简历优势与个性化推荐

| ID | 功能与验收条件 | 实现与验证入口 |
| --- | --- | --- |
| FR30 | 从已保存简历生成有原文依据的优势卡片，区分实践证据、词语提及与待确认项；不把否定或学习意愿当成已掌握技能 | `recommendations.analyze_strengths`、`test_recommendations.py` |
| FR31 | 在已有解释性排名基础上加入实践证据与目标职位信号；返回分项、有效权重、覆盖度、推荐理由及差距 | `recommendations.build_recommendations`；准确公式与边界见 `RESUME_MATCHING.md` |
| FR32 | 排除已过期职位、规范化链接去重、显式示例开关，支持目标职位、最低分、数量与严格地区选项 | 严格参数验证与推荐测试；来源时效不能等同在线招聘确认 |
| FR33 | 私有后台推荐使用本次简历/偏好/岗位快照；输入变化使结果过期，收藏备注不作为分数信号 | `server.recommendation_snapshot_token`、独立集成测试及前端 revision guard |

`POST /api/recommendations` 仅使用当前访客已保存简历与偏好，接收结构化筛选选项并返回任务 ID。计算不调用 DeepSeek，也不自动向第三方传输简历；原有 DeepSeek 优势解读和润色入口保持独立的发送授权。公共模式另设推荐并发额度（默认 3 个，环境变量 JOBCOMPASS_RECOMMEND_ACTIVE），在复制岗位集前准入，每 IP 每小时 30 次、全局 300 次，不占 AI 调用额度。推荐结果只保存在当前访客后台任务和页面内存，不写共享数据库。新个性化分数和保留的岗位检索基础分数明确区分，均不是录用概率。

### OLAP 指令

`validate_query` 只接受 `dataset`、`dimensions`、`measure`、`concept`、`filters`、`exact_filters`、`dedup`、`limit`、`sort`。数据集为 `research` 或 `current`；维度从 `month/quarter/year/sector/location` 选一或二个且不能重复；指标为 `ads/employers/mentions/share_pct`；探针从现有词典选择；去重为 `id/family`；分组显示上限 1–100；排序为 `label/value_desc`。

普通筛选复用 `validate_plan` 与参数化 `_selection`，包括职位/公司/地区/类别子串、日期、观察截止日及两个研究开关。精确筛选限定为维度名和字面值，支持对当前未显示的维度下钻。family 去重先保留全局首次观察的雇主正文族，再应用过滤；时间筛选不能使后续重复广告重新出现。

每组返回所选维度及 `ads/employers/mentions/share_pct/value`。`totals` 独立从完整筛选记录计算，不受显示上限影响，不能由分组百分比平均或去重雇主数相加代替。零分母比例为 `null`；缺失/非法日期进入 `Unknown`；不存在的月份或交叉组合不填零。二维 pivot 只覆盖已显示组，截断可能导致空格，须与 `metadata.truncated` 一起解释。

目录只对选中数据集计算完整统计和最多 50 项/维度的 facets；未选数据集可仅返回可用状态及廉价的索引计数。`_current(include_mask=False)` 只供目录省略词语扫描，正常分析必须使用完整 mask。研究索引不可用时，显式 research 查询报错，不静默换库。

### 自动命令与图表

`compile_and_run(command,dataset,olap,context=None)` 接收 1–1,500 字符问题。模型响应必须是 `{query,chart,explanation}`；query 明确数据集、维度、指标，其他字段经类型/白名单验证。数据集不可更换。图表只接受 bar/line/heatmap/table 和有界标题；折线需要恰好一个时间维度，可再加 sector/location 形成多序列，服务器将时间维度排在前；热力图需要两个维度。

受限指令通过验证后直接执行一次，不另设手动批准环节。不支持的意图可以返回 `query=null, chart=null` 及原因，服务器拒绝执行，不替换成另一种分析。生成的口径说明与建议标题仍属于模型推断。主图、聊天结果及导出统计标题由验证后的 query 维度、指标与必要探针生成；模型建议标题仅在高级信息中标注展示，不能把 ads 图误写为 Python 提及。

上下文只接受前次 query 或 `{query,totals}`。服务器向模型发送允许的结构、日期/布尔条件、白名单类别和有界数字，拒绝原始 rows；隐藏文本筛选保留在服务器。新指令省略 filters/exact_filters 时分别继承旧字段，显式提供时整体替换，空对象清除。模型生成的代码、路径或任意 SQL 永不执行。

## 非功能需求

| ID | 可验证条件 | 实现与证据 |
| --- | --- | --- |
| NFR01 | 无 AI/外网时已有数据和核心个人工具可用 | 标准库规则、SQLite、手动 OLAP |
| NFR02 | 本地模式只监听回环；共享边界校验 Host/Origin 与写入标记 | `main.py`、`WebGateway`、HTTP 测试 |
| NFR03 | 密钥不进入前端、日志或交付包 | 后端配置、打包白名单、测试 |
| NFR04 | 可复现离线验证，真实联网检查单列 | unittest、质量脚本、CI 配置 |
| NFR05 | 状态与撤销历史在事务内串行修改；本地重启保持记录 | SQLite `BEGIN IMMEDIATE`、历史测试 |
| NFR06 | 重要新行为有真实测试先行、属性/变异和集成证据 | `tests/`、`scripts/`、版本验证记录 |
| NFR07 | 样本来源、分母、断档与人工建议清晰区分 | metadata、结果说明和 UI |
| NFR08 | 排名只缓存最后完整输入，失效与深复制正确 | `ranking_cache.py`、缓存测试 |
| NFR09 | 仅 HTTP 429/502/503/504 有界重试，最多三次；不自动修复无效模型输出 | `retry.py`、重试测试 |
| NFR10 | 公共会话私有隔离、忙任务保留、闲置清理、重启旧凭据失效 | `SessionManager`、跨会话与生命周期测试 |
| NFR11 | 公开配置强制 HTTPS origin、明确 Host 和受信代理；cookie 为 Secure/HttpOnly/SameSite=Strict | `PublicConfig`、代理配置、公共 HTTP 测试；真实 TLS 与续期演练见 `CLOUD_VERIFICATION.md`，最终业务检查单列 |
| NFR12 | 请求/会话创建/AI 任务有容量及速率边界；任务完成/失败释放并发位 | 限额器、任务队列、公共集成测试 |
| NFR13 | 公共状态/错误不暴露服务器路径，结果和任务 ID 不跨会话访问 | sanitize、私有 registry/result_root、公共测试 |
| NFR14 | 生产采用一个进程、共享后台池；禁止直接增加 worker 破坏会话/配额一致性 | WSGI、文件锁、部署配置和测试 |
| NFR15 | 界面真实空状态/错误、转义模型与来源文本、响应式布局、导出口径清楚 | 本地图表资源、静态检查与最终浏览器记录 |

## 架构与数据流

本地 `ThreadingHTTPServer` 和生产 WSGI 适配器共用 `WebGateway`。它处理请求体上限、Host/Origin、路由、公开配额、匿名会话与通用错误边界。`Application` 负责业务功能，`Store` 以独立 SQLite 连接、外键与 WAL 保存数据。后台任务池有界，公开访客复用同一执行池，但各自持有任务状态及结果 ID。

本地应用使用自己的 Store。公共 `SessionStore` 读取共享岗位并去掉共享投递状态/备注，再叠加私有岗位与修改；简历、偏好和研究队列只从私有库读取。共享岗位首次被个人操作时保留原 ID 复制到私有库，避免破坏外键。公共访客不能写共享研究配置，JobsDB 尝试冷却由共享库协调。

研究原始数据库以 read-only SQLite 连接，应用构建/使用派生索引。公开模式将 `index_root` 与访客 `result_root` 分开：所有人可读运营方提供的索引，生成的结果 JSON 及队列归各自会话。任意源路径选择和索引构建属于运营维护，不是匿名 HTTP 功能。

匿名 cookie 是持有者凭据而非身份认证；复制 cookie 可能访问同一临时空间。默认闲置 TTL 一小时、最多 32 活跃会话；活跃请求/后台任务阻止过早删除。清理在请求及后台维护中进行；服务器停止时不能执行清理，重启后旧 token 失效并清理本系统旧目录。公开私有数据不承诺跨重启保存，也不承诺磁盘安全擦除。

新建会话默认每 IP 每小时 12 次、全局每小时 120 次，有效 cookie 复用不消耗新建额度。POST 和重型 GET（state/catalog/export/research-status）共享默认每 IP 每分钟 120 次、全局每分钟 1,200 次与 16 个活跃位；AI另有每 IP 每小时 10 次、全局每小时 100 次与 3 个活跃任务位。额度按入场计数，不因清除 cookie 或任务结束而退款，也不是供应商费用预算。

公开网页采集使用 `JOBCOMPASS_PAGE_HOSTS` 精确域名白名单，默认空；拒绝通配符、完整 URL、凭据与非 HTTPS/443。初始 URL、robots 与所有重定向都验证同一白名单及公网 DNS 地址，且不继承环境代理；同主机共享 15 秒尝试冷却。该实现不是 IP 固定的 DNS 连接机制，管理员应只批准受信站点及必要跳转域名。本地个人模式保留原有公网 HTTPS 采集。

生产环境必须在 TLS 代理后运行。应用检查 HTTPS 配置与来源，但不自行签发证书。转发客户端 IP 只信任明确的代理 peer；不能接受任意用户提供的转发头。生产入口只允许单 worker；多副本需要另外设计共享会话、限额和任务基础设施。

## 数据、匹配与 AI 保留语义

`jobs` 保存岗位属性、来源、时间和过期状态；`applications` 保存个人状态/备注；`settings` 保存简历、画像、偏好与派生状态；`collection_runs` 保存采集记录；`application_history` 保存最多 50 次前后快照和已应用标记。公共模式在隔离的私有库中保存相同类型的个人记录。

岗位 ID 沿用来源与 URL（或来源/标题/公司/地区）的稳定哈希，不任意合并不同来源。新本地库默认载入授权的历史 JobsDB 快照，`--demo` 才使用虚构样例。公开新访客不复制全部数据库或继承运营方的个人设置。上传文件在内存解析；数据库本身未加密。

匹配公式不变：技能加权 F1 45%、文本 TF-IDF 余弦 25%、经验 15%、地区 10%、学历 5%；不可识别条件不计入有效权重分母。沟通/英语技能质量权重较低。分数是可解释排序，不是录用概率；追加语料可能改变 IDF 和既有分数。技能成长仅说明简历是否出现技能，以及人工学习依赖建议。

简历 AI 仍仅使用已保存简历，在功能授权后有限脱敏发送；旧请求完成时须核对简历仍一致后才写回。分析 AI 只接收命令和允许的结构/聚合，不自动获得个人简历、原始广告或本机路径。所有模型文本均需以非可执行内容显示。

## 接口摘要

| 路由 | 行为 |
| --- | --- |
| `GET /api/health` | 轻量健康状态；不分配访客会话 |
| `GET /api/status` | 版本、部署方式、AI 可用状态；不下载全岗位正文 |
| `GET /api/analytics/catalog?dataset=...` | 有界目录和所选数据集统计 |
| `POST /api/analytics/query` | 受限 OLAP 查询，同步结果 |
| `POST /api/analytics/command` | 编译并自动执行，返回后台任务 ID |
| `GET /api/state` | 当前应用/访客个人状态与岗位视图，首次进入相关工具时加载 |
| `GET /api/tasks/{id}` | 当前访客任务状态；别人的 ID 不可访问 |
| `POST /api/tasks/cancel` | 对支持取消的任务设置协作停止标志 |
| `POST /api/resume*`、`/api/preferences`、`/api/ai` | 保留的简历/偏好/个人 AI 功能 |
| `POST /api/application`、`/api/application/history` | 投递记录与撤销/重做 |
| `POST /api/collect*`、`/api/jobsdb/update`、`/api/import`、`/api/job` | 固定来源更新、受限网页采集、个人导入/手动岗位 |
| `POST /api/research/{run,plan,explain,agent,cohort}` | 保留的深度研究、计划、解释与多步助手 |
| `GET /api/research/status`、`/api/research/result/{id}` | 当前会话可访问的研究元信息与结果导出 |
| `POST /api/research/{connect,build}` | 本地/运营维护；公开入口拒绝 |
| `POST /api/learning` | target 最多 100 字符、limit 1–20 的技能成长分析 |

写请求要求 `X-JobCompass: 1`、合法 Host/Origin 且不来自跨站请求，JSON body 最大 7 MB。无效输入返回 400，边界拒绝 403，未知资源 404，额度/并发受限返回相应错误与可用的重试信息。模型/采集失败保存在当前任务，不把错误当成成功图表。公开异常需去掉基础设施路径。

## 验收场景与证据边界

1. 研究样本两组分别 3 条/1 条、提及 1 条/1 条时，总提及率是 50%，不是两组比例的算术平均；同雇主出现在两组时总体只计一次。
2. 设置 limit=1 只减少显示组，不改变 totals/total_groups。缺失、非法日期保留在 Unknown；空队列比例 null；二维缺口与真实观测零可区分。
3. “比较不同职业类别的季度 Python 提及率”生成季度×类别折线，时间维度归到第一位；执行后的实际筛选与查询对用户可见。
4. 后续“改成按月”保留未显式替换的私有筛选，但模型请求不包含隐藏的标题/公司/地区值。传 raw rows、代码、越权数据集或未知字段时不执行。
5. 两个独立浏览器无需登录，都可分析共享数据并使用个人功能；A 的简历、备注、私有导入、任务和结果不能由 B 的 cookie/ID 请求获得。运营库个人记录也不能继承给访客。
6. 正常匿名写请求可用，错误 Host/Origin、跨站写入、任意源路径维护、未授权公共网页主机均被拒绝。清理 cookie 不重置同一 IP 的配额。
7. 会话在活跃任务期间不删除；闲置到期可清理；重启后旧凭据不能恢复私有数据。单进程文件锁阻止另一个 worker 共享 registry。
8. Python 3.12 的 HTMLParser 在末尾裸 `R&D` 文本上必须完成解析收尾；该部署兼容回归由实际 red/green 记录验证，不误报快照输入错误。

上述是验收条件，不能把有测试文件等同于全部人工验收。当前 v2.1 本地 Python 3.8/3.12 各通过 342 项测试，质量门禁含 8 个 doctest 和 5 个指定变异；GitHub 五个环境各通过同一套 342 项，云端 Python 3.12.16 也通过 342 项（13.321 秒）。实际运行和证据边界见 [CLOUD_VERIFICATION.md](CLOUD_VERIFICATION.md) 与 [RESUME_VERIFICATION.md](RESUME_VERIFICATION.md)。历史 v2.0 的 306 项、v1.3 的 223 项和中间轮次 283 项保持原始记录。Docker 镜像未构建；公网健康、续期演练、源码打包、研究库迁移和业务验收分别记录，不相互代替。
