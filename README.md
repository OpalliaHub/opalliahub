# JobCompass

**职业与人力资源研究平台 · Workforce and Career Research Platform**

[简体中文](#简体中文) · [English](#english) · [MIT License](LICENSE)

## 简体中文

JobCompass 将招聘广告样本转化为可查询、可解释的职业研究数据。平台提供多维分析、自然语言查询与动态图表，同时保留简历优势提炼、岗位推荐和投递管理。桌面采用左侧研究面板、右侧常驻 DeepSeek 对话的布局；小屏幕可切换平台与对话视图。当前界面使用中文。

### 主要功能

- **职业研究与 OLAP**：按月份、季度、年份、职业类别和地区组合分析广告数、雇主标签数及词语提及率；支持折线图、柱状图、热力图、表格、下钻及 CSV／JSON／PNG 导出。纵向研究工具提供队列、跨期比较与修订分析。
- **对话驱动分析**：DeepSeek 将问题转成有类型、受限制的查询计划。服务器校验后自动执行统计并更新图表，支持继续调整上一次分析。模型生成的 Python、Shell、JavaScript 或任意 SQL 不会执行。
- **JobsDB 平台内更新**：使用 GraphQL `JobSearchV7`，复用同批会话并按实际分页读取最新岗位。默认检查 50 条，最多 200 条详情及 20 个列表页；请求串行限速，网络故障和明确限流有界重试。遇到访问拒绝或验证页会停止并保留已完成结果。**关键词仅筛选本批岗位的标题、公司及正文，不是全站搜索。**
- **个人求职工具**：从简历提炼带原文依据的优势，生成有分项解释的岗位推荐，记录投递状态与备注，并提供技能缺口和学习建议。规则推荐无需发送简历给大模型；AI 润色与解读另有发送授权。

例如在右侧对话中输入：

> 按月份统计全部广告数，清除所有筛选，按广告 ID 去重，用折线图展示。

查询针对当前选中的数据集执行，图表展示实际查询口径和结果。

### 本地启动

需要 **Python 3.8+**。在项目目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
python main.py --no-browser
```

然后打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)。需要 Python 服务运行，不要直接打开静态 HTML。按 Ctrl+C 停止；可用 `--port 8766` 更换端口。

Windows 可用 `py -m venv .venv`，随后运行 `.venv\Scripts\python -m pip install -r requirements.txt` 与 `.venv\Scripts\python main.py`；仅在 `.env` 不存在时从模板复制。Windows 支持本地个人模式；公开会话服务需要 Linux／macOS 文件锁。

核心逻辑使用 Python 标准库与 SQLite；`requirements.txt` 提供 PDF 解析和证书辅助依赖。ECharts 随源码提供，不依赖 CDN。

要启用 DeepSeek，在本机 `.env` 中填写 `DEEPSEEK_API_KEY`，可选设置 `DEEPSEEK_MODEL`，然后重启服务。配置字段见 [.env.example](.env.example)。密钥只由后端读取；不要提交 `.env`。未配置 AI 时，手动分析、已有岗位、规则推荐和投递记录仍可使用。

### 数据、隐私与解释边界

随附历史 JobsDB 快照可用于初始运行，其采集日期和处理信息保留在数据清单中；历史记录不保证仍在招聘。更大的纵向研究库由运营者另行配置，只读访问。平台更新写入当前岗位工作空间，不自动改写历史研究库。Remotive、Arbeitnow、授权文件导入和手动录入可作为补充来源。

- 招聘广告是样本，不是整体劳动力市场或招聘人数。词语提及率不是强制技能要求；推荐分数不是录用概率；学习先修关系是人工编写的建议。
- 总体指标独立于分组显示上限计算；缺失记录和零分母保持明确空值。来源覆盖、采集断档及数据时效都会影响研究解释。
- 公开模式无需注册或登录，每个浏览器通过安全 Cookie 获得临时私有工作空间。简历、备注、个人导入、更新结果和任务互相隔离；共享研究索引只读。默认闲置一小时后清理，服务重启使旧会话失效，重要结果请及时导出。
- 分析 AI 接收你输入的命令，以及允许的查询结构和有限聚合数据；不会自动附加岗位原文、简历、结果明细或服务器路径。直接写进命令的文字会传给模型。简历 AI 在单独授权后发送有限脱敏的内容，脱敏不等于完全匿名。

原始研究档案、个人数据库、简历、运行密钥及服务器私有配置不包含在源码包中。本项目使用外部模型接口，没有训练或微调自有 LLM。

### 服务器部署

生产环境使用 **Python 3.12**、`requirements-server.txt` 和 `jobcompass.wsgi:application`。必须使用 **一个 Gunicorn worker**；会话、任务与配额协调当前不支持直接增加 worker 或副本。

通过 HTTPS 反向代理提供访问，配置精确的公开 Origin、Host 和受信代理；后端保持非公开监听。公开入口有请求、会话和 AI 配额，JobsDB 冷却跨访客共享。配置及原生／容器部署模板见 [部署指南](docs/DEPLOYMENT.md) 和 [deploy/](deploy/)。部署模板本身不代表已完成部署或容量验证。

### 开发与验证

```bash
python -m unittest discover -v
python scripts/quality_gate.py --mutations
python scripts/coverage_report.py
```

测试和 CI 使用虚构或模拟响应，不抓取招聘网站、不调用付费 AI。实际联网结果、版本验证范围与限制见 [JobsDB 更新验证](docs/JOBSDB_V7_VERIFICATION.md)。一次检查通过不保证第三方接口持续可用。

技术文档：[功能规格](docs/SPECIFICATION.md) · [OLAP 与查询边界](docs/OLAP.md) · [简历优势与推荐算法](docs/RESUME_MATCHING.md) · [部署指南](docs/DEPLOYMENT.md)。

### 许可

项目代码采用 [MIT License](LICENSE)。随附 ECharts 保留其 [Apache 2.0 许可](jobcompass/static/vendor/ECHARTS-LICENSE.txt)。招聘广告数据及其他第三方内容的权利归其原权利人，代码许可不自动授予第三方数据的再分发权。

## English

JobCompass turns recruitment advertisement samples into queryable, explainable workforce research data. It combines multidimensional analysis, natural-language queries and interactive charts with resume strengths, job recommendations and application tracking. The desktop layout places the research workspace on the left and a persistent DeepSeek conversation on the right; smaller screens can switch between them. The application interface is currently in Chinese.

### Features

- **Workforce research and OLAP**: combine month, quarter, year, occupational category and location to analyze advertisement counts, employer labels and term mention rates. Explore line charts, bar charts, heatmaps, tables and drill-downs; export CSV, JSON or PNG. Longitudinal tools support cohorts, period comparisons and revision analysis.
- **Conversation-driven analysis**: DeepSeek converts a request into a typed, restricted query plan. The server validates it, runs the analysis automatically and updates the charts. Follow-up commands can refine the previous analysis. Model-generated Python, shell commands, JavaScript and arbitrary SQL are never executed.
- **JobsDB updates inside the platform**: the GraphQL `JobSearchV7` adapter reuses one batch session and follows the server's pagination. It checks 50 listings by default, with limits of 200 details and 20 search pages. Requests are serial and paced; network failures and explicit rate limits receive bounded retries. Access refusals or verification pages stop the update while preserving completed results. **Keywords filter only the titles, companies and descriptions fetched in this batch; this is not a site-wide search.**
- **Personal job tools**: extract resume strengths supported by source text, produce explainable recommendations, track applications and notes, and explore skill gaps and learning suggestions. Rule-based recommendations do not send the resume to a model. AI rewriting and interpretation require separate sending consent.

Example command in the conversation panel:

> Group all advertisements by month, clear all filters, deduplicate by advertisement ID, and show a line chart.

The query runs against the selected dataset, and the platform displays the actual query scope and results.

### Run locally

Use **Python 3.8+**. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
python main.py --no-browser
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Keep the Python service running; opening the static HTML directly does not start the application. Press Ctrl+C to stop, or use `--port 8766` to choose another port.

On Windows, use `py -m venv .venv`, then `.venv\Scripts\python -m pip install -r requirements.txt` and `.venv\Scripts\python main.py`. Copy the environment template only if `.env` does not exist. Windows supports local personal mode; public sessions require Linux/macOS file locking.

The core uses the Python standard library and SQLite. `requirements.txt` adds PDF extraction and certificate support. ECharts is bundled locally rather than loaded from a CDN.

To enable DeepSeek, set `DEEPSEEK_API_KEY` in your local `.env`, optionally set `DEEPSEEK_MODEL`, and restart. See [.env.example](.env.example). Keys are read only by the backend; never commit `.env`. Manual analysis, existing data, rule-based recommendations and application tracking remain available without AI configuration.

### Data, privacy and interpretation

A bundled historical JobsDB snapshot supports initial use; its collection date and processing metadata remain in the data manifest. Historical advertisements are not a guarantee of current vacancies. Operators can separately configure a larger longitudinal research database for read-only access. Platform updates write to the current job workspace and do not rewrite the historical research database. Remotive, Arbeitnow, authorized file imports and manual entries are supplementary sources.

- Advertisements form a sample, not the entire labor market or a count of people being hired. Term mentions are not mandatory skill requirements, recommendation scores are not hiring probabilities, and learning prerequisites are authored suggestions.
- Overall metrics are computed independently of the displayed group limit. Missing observations and zero denominators remain explicit gaps. Source coverage, collection interruptions and freshness affect interpretation.
- Public mode requires no account or login. Secure cookies identify temporary private browser workspaces. Resumes, notes, personal imports, update results and tasks are isolated; the research index is shared read-only. Idle workspaces expire after one hour by default, and restarting the service invalidates old sessions. Export results you need to retain.
- Analytical AI receives the command you enter plus permitted query structure and bounded aggregates. It does not automatically receive raw advertisements, resumes, result rows or server paths. Text explicitly entered in a command is sent to the model. Resume AI sends partially redacted content only with separate consent; redaction is not complete anonymization.

Raw research archives, personal databases, resumes, runtime keys and private server configuration are excluded from source packages. This project uses an external model API; it does not train or fine-tune its own LLM.

### Deploy

Production uses **Python 3.12**, `requirements-server.txt` and `jobcompass.wsgi:application`. Run **one Gunicorn worker**. The current session, task and quota coordination does not support simply adding workers or replicas.

Expose the application through an HTTPS reverse proxy with an exact public Origin, allowed Host and explicitly trusted proxy configuration. Keep the backend listener private. Public requests, session creation and AI usage have admission limits; JobsDB cooldowns are shared across visitors. See the [deployment guide](docs/DEPLOYMENT.md) and [deploy/](deploy/) for native and container templates. A template is not evidence of a completed deployment or measured capacity.

### Develop and verify

```bash
python -m unittest discover -v
python scripts/quality_gate.py --mutations
python scripts/coverage_report.py
```

Tests and CI use fictional or mocked responses, with no recruitment-site crawling or paid AI calls. Actual network checks, verification scope and limitations are recorded in [JobsDB update verification](docs/JOBSDB_V7_VERIFICATION.md). A successful check does not guarantee continuing third-party API availability.

Technical documentation: [specification](docs/SPECIFICATION.md) · [OLAP and query boundaries](docs/OLAP.md) · [resume strengths and recommendation algorithm](docs/RESUME_MATCHING.md) · [deployment](docs/DEPLOYMENT.md).

### License

Project code is available under the [MIT License](LICENSE). Bundled ECharts retains its [Apache 2.0 license](jobcompass/static/vendor/ECHARTS-LICENSE.txt). Recruitment advertisements and other third-party content retain their original rights; the code license does not automatically grant redistribution rights for third-party data.
