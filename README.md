# JobCompass 2.1 · 人力资源与职业研究平台

JobCompass 以 JobsDB 招聘广告样本为基础，提供多维统计、职业与技能趋势、自然语言数据查询，以及简历匹配、投递管理和学习路线。**默认首页是「研究总览」**：左侧使用平台与图表，右侧常驻 DeepSeek 对话；输入问题后，模型生成受限统计指令，服务器验证并自动执行，再更新真实图表，无需复制或手动批准 JSON。

当前代码版本为 **2.1.0**。本地运行与匿名公开模式均已写入代码；正式云服务器、域名和 TLS 部署仍待提供环境并验收。本仓库页面不是已上线的平台。Python 3.8.10 与 3.12 各通过 342 项离线测试；新增推荐的浏览器、隔离和性能记录见 [v2.1 验证](docs/RESUME_VERIFICATION.md)。此前 OLAP、导出与本机 Gunicorn smoke 保留在 [v2.0 验证记录](docs/V2_VERIFICATION.md)。

**Group 11** · OU JUNHANG · ZHANG XIQIAN · JIANG YIFAN · CAI SHANGHENG · GUO ZHENGKUN
INT6181 Applied Programming with Python 课程项目。

## v2.1：从简历优势到岗位推荐

进入「简历分析」，导入或粘贴简历，填写求职偏好和可选目标职位，点击 **提炼优势并推荐岗位**。平台保存当前输入，在后台生成原文证据卡片和个性化岗位列表；每项推荐都显示分项、推荐理由与技能差距。已过期岗位和重复链接被排除，历史快照会保留时效提示。

这条流程无需发送简历给大模型。需要 DeepSeek 补充表达或解读时，可继续使用独立授权的 AI 按钮。原「岗位检索」保留基础匹配算法，新推荐页增加实践证据和目标职位信号；两者分数明确标识，不能作为录用概率。算法、测试与限制见 [优势与推荐说明](docs/RESUME_MATCHING.md)。

## 快速启动

本项目需要 Python 服务。不要直接打开 `jobcompass/static/index.html`；它不能代替后端。已有本机环境可双击 `启动JobCompass.command`，或在项目目录运行：

```bash
.venv/bin/python main.py
```

然后访问 **http://127.0.0.1:8765/**。终端按 Ctrl+C 停止；已有服务时直接打开网页。更换端口可用 `python main.py --port 8766`。

首次安装使用 Python 3.8 或以上：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
python main.py
```

Windows 可使用 `py -m venv .venv`，随后运行 `.venv\Scripts\python -m pip install -r requirements.txt` 与 `.venv\Scripts\python main.py`；仅在 `.env` 不存在时复制配置模板。公开会话服务需要 Linux/macOS 文件锁，Windows 保留个人本地模式。

离线解析、规则匹配、SQLite 和已有数据分析使用标准库；PDF 解析需要 `pypdf`，HTTPS 证书辅助使用 `certifi`。DeepSeek 未配置时，手动 OLAP、已有数据、匹配和投递功能仍可用。ECharts 随项目本地提供，不依赖 CDN。

## 从研究到个人工具

1. 在「研究总览」选择数据集、维度与指标。月份、季度、年份、职业类别、地区可以组合为一维或二维分析；研究索引未就绪时使用当前岗位样本。
2. 在右侧 DeepSeek 对话输入问题，例如“比较不同职业类别的季度 Python 全文提及率，用多条折线展示”。验证通过后自动查询，左侧显示实际执行口径、图表和统计表；对话支持继续修改上一次分析。
3. 点击图表或表格分组下钻；使用面包屑撤销精确筛选。可导出当前结果的 CSV、JSON 和 PNG。缺失日期/组合不会补造成零需求。
4. 「深度研究」保留纵向队列、两期比较、修订证据和回测诊断。这里原有的单计划预览/手动执行流程仍保留；它与首页的新自动执行入口是不同功能。
5. 「岗位检索」「简历分析」「投递管理」「技能成长」继续提供简历上传、解释性匹配、状态备注、撤销/重做与递归学习建议。投递状态是记录，程序不会自动发送申请。
6. 「数据管理」支持平台内更新 JobsDB、固定公开 API、授权文件导入与手动岗位。公开模式下这些个人变更保存在自己的临时访客空间，共享研究数据由服务器维护。

桌面界面采用左平台、右对话；窄屏切换平台/对话视图。最新布局和导出按钮的实际浏览器验收见 [界面说明](docs/UI_V2.md) 与 [v2 验证记录](docs/V2_VERIFICATION.md)。

## 多维分析的统计口径

| 项目 | 实际含义 |
| --- | --- |
| 广告数 | 筛选、去重后的样本广告，不是招聘人数 |
| 雇主标签数 | 归一化显示标签的去重数，不是已核实的法人数量 |
| 提及广告数 / 提及率 | 固定词语探针在广告全文中出现的记录数及其占比，不等于强制技能要求 |
| 总体指标 | 独立从全部筛选记录计算，不累加分组中的去重雇主，也不简单平均分组百分比 |
| 分组上限 | 单次显示最多 100 组；截断不改变总体分母 |
| 空值与缺口 | 零样本提及率为 `null`；缺失/非法日期进入 `Unknown`，未观察组合保留空缺 |

详细字段、SQL 边界、热力图、自动执行与测试证据见 [OLAP 说明](docs/OLAP.md)。研究广告是便利样本，不代表香港整体劳动力市场；跨期类别覆盖与抓取断档会影响解释。不能据此宣称因果、录用概率或未进行的显著性检验。

## 两种运行模式

| 模式 | 数据与访问方式 |
| --- | --- |
| 本地个人模式 | `python main.py` 默认只监听回环地址；自己的简历、备注和分析记录保存在本机数据库 |
| 公开访客模式 | 访客无需注册/登录；每个浏览器通过随机安全 cookie 获得隔离的临时工作空间，共享岗位目录与只读研究索引 |

公开模式中的简历、偏好、AI 草稿、个人导入、投递备注、撤销历史、结果文件和任务 ID 均归当前匿名会话。默认闲置期限一小时；运行中的请求/任务暂缓清理。进程重启使旧访客凭据失效，需保留的结果应及时导出。它不是账户系统或跨设备持久同步服务，也不是磁盘加密方案。

公开入口必须配置明确的 **HTTPS origin、Host 白名单和受信代理**；TLS 由反向代理提供，后端监听保留在代理后面。访问者不能通过 HTTP 连接任意服务器数据库路径或重建共享索引。任意网页采集在公开模式默认关闭，仅可由管理员用 `JOBCOMPASS_PAGE_HOSTS` 配置精确主机白名单开放；初始地址、robots 与每次重定向均校验。固定 JobsDB/API 接入与文件导入继续可用。免登录不等于无限量：访客创建、请求和 AI 任务有容量/速率限制。

生产入口是 `jobcompass.wsgi:application`，另有 `requirements-server.txt`、Docker/Compose、Caddy/Nginx 模板及研究索引维护脚本。当前设计只允许 **一个 Gunicorn worker**，默认八个 HTTP 线程，后台任务共享有界线程池；不能直接扩成多个副本。部署步骤与环境变量见 [公开部署准备](docs/DEPLOYMENT.md)。本机没有 Docker，因此没有把镜像配置写成“已经构建成功”，也没有声称云站点已上线。

## DeepSeek 与隐私

在本机 `.env` 或服务器运行环境设置 `DEEPSEEK_API_KEY`，可用 `DEEPSEEK_MODEL` 指定模型；当前默认 `deepseek-flash`。API 名称、Tracking ID 不作为模型名或认证字段。密钥由后端读取，不发送到浏览器，也不应进入 Git 或交付包。更改配置后重启。

首页命令会发送你输入的问题及受限的上次查询结构/数字总量。不会自动附加岗位原文、简历或服务器路径；标题、公司、位置等上下文文本筛选值保留在服务器，不发给模型。不要把不想发送的私人文字直接写进问题。模型只生成经过校验的数据指令和图表配置，不运行模型生成的 Python、SQL、Shell 或 JavaScript。

简历 AI 功能仍有独立的发送授权，会发送已保存且有限脱敏的简历。邮箱、部分电话/证件号遮盖不是完整匿名化；姓名和项目经历可能仍存在。公开 AI 配额按访客来源/IP 与全局容量约束，不是精确费用上限。瞬态 HTTP 重试和多步研究助手可能产生多次供应商请求；见 [API 可靠性边界](docs/AI_RELIABILITY.md)。本项目未训练或微调本地 LLM。

## 数据与保留功能

JobsDB 是主要来源，平台内可直接更新岗位列表和详情；默认 50 条、最多 200 条，包含间隔、取消、过期标记和保留个人状态的更新逻辑。Remotive、Arbeitnow、CSV/JSON/HTML 导入与手动录入作为补充。没有实现登录态抓包、验证码绕过或 BOSS/猎聘等受限接口。数据有效性、签证、地域和薪资仍需在原站核实。

源码随附 2026-09-28 的历史 JobsDB 快照：6,939 条输入中 6,910 条通过校验，应用默认排除当时已过期的两条后导入 6,908 条。它是研究快照，不是当前在线招聘承诺。大型纵向原始研究库、个人数据库、OneDrive 压缩包均不公开打包。新电脑可直接分析随附快照，也可以由管理员配置自己的纵向研究库。

匹配分数保持技能 F1 45%、TF-IDF 文本 25%、经验 15%、地区 10%、学历 5% 的基础权重，缺失条件重新归一化。分数是排序指标，不是录用概率。技能成长的先修图是人工编写的学习建议，不是雇主要求。更多内容见 [JobsDB 接入](docs/JOBSDB_INTEGRATION.md)、[benchmark](docs/BENCHMARK.md)、[学习路线](docs/LEARNING_PLANNER.md) 和 [排名缓存](docs/RANKING_CACHE.md)。

## 验证与交付

```bash
python -m unittest discover -v
python scripts/quality_gate.py --mutations
python scripts/coverage_report.py
python scripts/package_project.py --group 11
```

离线测试不访问招聘网站、不调用付费 AI。真实联网验证单独记录，不放入 CI。当前单条 DeepSeek 命令自动执行的实测在 [analytics_live_check.json](docs/analytics_live_check.json)，只证明该次调用与本机查询成功，不代表所有问题的理解准确率。

已观察到 Python 3.8.10 和 3.12 各 306 项测试通过、8 个 doctest 通过、5 个指定变异被测试检出，以及真实单 worker/八线程 Gunicorn smoke 通过。日志、双栏/窄屏/导出交互和最终交付包状态统一见 [V2_VERIFICATION.md](docs/V2_VERIFICATION.md)。旧版 223 项或中间轮次 283 项不能替代这些 v2 证据。配置好的 GitHub Actions 不等于远端已运行；本文不声称本轮 GitHub 已更新、Docker 已构建或云服务已部署。

可用的 CLI 示例：

```bash
python main.py --no-browser
python main.py --collect JobsDB --keyword Python --limit 20
python main.py --match data/demo_resume.txt --db /tmp/jobcompass-demo.db
python main.py --demo --db /tmp/jobcompass-only-demo.db --port 8766 --no-browser
```

`--match` 会保存简历到指定数据库；演示请使用临时库。`--demo` 的虚构岗位用于匹配演示，研究聚合会排除演示数据，因此纯示例库的研究首页可能没有可统计记录。

## 代码与文档导航

| 路径 | 职责 |
| --- | --- |
| `main.py` | 本地 GUI 服务、采集及匹配 CLI |
| `jobcompass/server.py` | 业务应用、任务队列、功能接口 |
| `jobcompass/web.py` / `public.py` / `wsgi.py` | HTTP 边界、匿名隔离、配额和生产适配 |
| `jobcompass/olap.py` / `analytics_ai.py` | 多维统计与自然命令自动执行 |
| `jobcompass/research.py` / `research_agent.py` | 纵向研究与有预算的多步助手 |
| `jobcompass/resume.py` / `matching.py` / `learning.py` | 简历、排名和技能路线 |
| `jobcompass/static/` | 平台界面、常驻对话、本地图表资源 |
| `tests/` / `scripts/` | 自动化验证、质量门禁、评估及打包 |
| `deploy/` / `Dockerfile` / `compose.yaml` | 生产配置与维护模板，尚需目标环境验收 |
| `docs/SPECIFICATION.md` | 当前 v2 功能需求与边界 |
| `docs/V2_VERIFICATION.md` | 当前证据、未完成的外部验证及版本状态 |

## 历史版本与课程材料

v1.3 的课程增强工作继续保留：[课程映射](docs/COURSE_COVERAGE.md)、[v1.3 验证](docs/COURSE_VERIFICATION.md)、[v1.3 演示补充](docs/COURSE_DEMO_V1_3.md)、[质量流程](docs/QUALITY_WORKFLOW.md)。v1.2 研究室和 v1.1 JobsDB 直连说明分别见 [研究室文档](docs/RESEARCH_WORKBENCH.md) 与 [接入文档](docs/JOBSDB_INTEGRATION.md)。这些记录适用于各自版本，未改写成 v2 验收结果。

原有 Word/PDF/PPT 保留为 **2026-09-30 课堂材料**，本轮没有重新生成：[英文 Proposal](docs/submission/Group11_Project_Proposal.docx)、[项目报告](docs/submission/Group11_Project_Report.docx)、[Presentation](docs/submission/group11_presentation.pptx)、[演示说明](docs/submission/Group11_Demo_Guide.docx)、[个人报告参考](docs/submission/Group11_Individual_Report_Draft.pdf)。原大作业 DOCX 在此前指定路径缺失，历史页数/时长要求尚未重新核对原件，见 [提交清单](docs/COURSE_CHECKLIST.md)。

项目由 AI 根据用户需求生成、调试与测试。成员报告应如实补充本人实际阅读、修改、验证、评审与演示经历，不虚构人工贡献、课堂操作或提交记录。
