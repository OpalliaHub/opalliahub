# JobCompass 智能求职平台

INT6181 Applied Programming with Python 课程项目。Python 负责简历解析、公开岗位采集、SQLite 持久化、匹配算法、后台任务、HTTP 接口及 DeepSeek 调用；浏览器提供中文 GUI，同时提供 CLI。适合在个人电脑上单人使用。

**Group 11** · OU JUNHANG · ZHANG XIQIAN · JIANG YIFAN · CAI SHANGHENG · GUO ZHENGKUN

英文项目提案：[Group11 Project Proposal](docs/submission/Group11_Project_Proposal.docx)。

## 快速启动

完成下面的首次安装后，双击 `启动JobCompass.command`，或在此文件所在目录执行：

```bash
.venv/bin/python main.py
```

访问 <http://127.0.0.1:8765>。终端按 Ctrl+C 停止。如果已有服务在运行，直接访问网页即可。端口占用时使用 `python main.py --port 8766`。

在其他电脑首次运行（Python 3.8 或以上）：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Windows：`py -m venv .venv`，然后 `.venv\Scripts\python -m pip install -r requirements.txt` 和 `.venv\Scripts\python main.py`。用编辑器将 `.env.example` 复制为 `.env`。

**离线核心功能不依赖第三方库。** 未安装依赖时，`python3 main.py` 仍支持 TXT、DOCX、示例岗位、匹配和投递管理。PDF 需要 `pypdf`；HTTPS 证书问题可通过安装 `certifi` 解决。

## 一次完整使用流程

1. 首页点击「体验示例匹配」，或在「我的简历」粘贴自己的文字、上传 TXT／DOCX／文字型 PDF，点击「保存并分析」。示例简历与 12 条示例岗位均为虚构。
2. 填写求职地区和实际工作年限。地区以文本匹配，建议同时填写 `香港, Hong Kong, 深圳` 等中英文名称。
3. 在「数据工作台」同步 Remotive 和 Arbeitnow，或导入 CSV／JSON／HTML 文件、手动添加岗位。
4. 在「岗位发现」搜索、筛选来源／地区，选择「仅看真实来源」排除课程样例。点击岗位查看技能、文本、年限、地区和学历分项。
5. 将岗位收藏或标记为已投递／面试中／已录用／已结束，添加备注，在「投递看板」跟进。投递状态只是本地记录，程序不会自动发送申请。
6. 在「我的简历」勾选发送授权，点击「提炼我的优势」或「润色简历」。岗位详情也可以做 AI 解读。AI 请求使用已保存的简历，编辑后请先保存。润色结果可以下载为 TXT，不会覆盖原文。

## DeepSeek 配置

在 `.env` 中填写 `DEEPSEEK_API_KEY`，可用 `DEEPSEEK_MODEL` 指定模型。默认使用本次通过真实请求验证的 `deepseek-flash`。API 名称和 Tracking ID 是账户管理信息，不作为模型名称或认证字段。

密钥仅由 Python 后端读取，浏览器只能看到配置状态。`.env`、数据库、虚拟环境均排除在提交压缩包及 Git 之外。改动 `.env` 后重启服务。API 调用可能按供应商规则计费，程序每次按钮操作只发起一项任务，未配置、超时、余额不足或格式错误都会提示。

简历默认保存在本机 `data/jobcompass.db`。仅在主动授权 AI 操作后发送给 DeepSeek；发送前遮盖常见邮箱、内地手机号及身份证号，**不是完整匿名化**。姓名、项目和其他个人信息仍可能保留，请自行检查。界面「清除简历数据」删除当前可访问记录，不等于磁盘安全擦除。

## 数据来源与限制

| 方式 | 真实支持范围 | 行为 |
|---|---|---|
| Remotive | 公开远程岗位，可能限制居住地 | 固定官方 API，每次尝试间隔 6 小时，保留原站链接和署名 |
| Arbeitnow | 以欧洲为主的公开岗位 | 固定官方 API，每次尝试间隔 6 小时，保留原站链接和署名 |
| 网页采集 | 公开 HTTPS 页面中的 schema.org JobPosting JSON-LD | 校验公开网络地址，读取 robots.txt，同域至少间隔 15 秒 |
| CSV / JSON / HTML | 用户已有或获授权的数据 | 校验字段后整批写入，使用相同匹配流程 |
| 手动岗位 | 国内或其他平台可见的单条职位 | 粘贴岗位描述和原始链接 |

没有实现 BOSS直聘、猎聘、智联等平台的登录态抓包、验证码处理或受限接口采集。它们的岗位可通过授权导出或手动录入使用。网页若不含 JobPosting 或 robots.txt 不可读取，会明确失败。使用 Fake-IP 代理的本机，通用网页安全检查可能拒绝其保留网段地址；固定官方 API 适配器支持本机代理路由，HTTPS 证书校验始终开启。

历史岗位保留在本机；同步执行新增／更新，不自动删除已下线岗位。是否仍招聘、时区、居住地、签证和薪资必须在原站核实。不同币种与月薪／年薪只显示原文，不直接换算或比较。Remotive 的公开职位有约 24 小时延迟。公开数据不会随课程源码包分发。

## 匹配方法

总分为可用分项的加权平均，乘以 100。基础权重：技能契合 45%、TF-IDF 文本余弦相似度 25%、经验要求 15%、地区偏好 10%、学历 5%。条件缺失时该项不计入分母，详情显示有效权重与条件覆盖率。

技能项采用加权 F1：技能精确率衡量简历能力中有多少与岗位重合，技能召回率衡量岗位识别技能被覆盖多少；二者取调和平均。英语和沟通每项权重 0.2，其他词典技能每项 1。此设计避免仅凭一种通用技能把不相关岗位推到前列。算法仅处理词典识别的关键词，不等同于专业技能验证。

分数是可解释的排序指标，**不是录用概率**。语料新增时 TF-IDF 的 IDF 会变化，既有岗位分数也可能变化。规则无法可靠区分「了解」「熟练」「希望学习」和否定表达；AI 提供辅助解释，不修改基础匹配分。

## 测试与评估

```bash
python -m unittest discover -v
python scripts/evaluate.py
python -m compileall -q main.py jobcompass
```

自动化测试覆盖解析、评分、未知值、代理边界、导入、SQLite、AI 输出格式、HTTP、跨站请求及本地完整流程。单元测试不访问外网、不消耗 API 额度。

`scripts/evaluate.py` 使用 12 条人工构造、人工标注的示例岗位测量 Precision@4，并在 1,200 条复制样例上测量排序时间。该数据集只能证明样例行为，不代表真实招聘准确率。实测记录见 `docs/evaluation.json`。

手动网络冒烟测试：`python scripts/check_live.py`。它会采集真实岗位，并向 DeepSeek 发送虚构示例简历，产生一次真实 API 调用。结果写入 `docs/live_check.json`。不要把这项有外部副作用的测试放入 CI。

GitHub Actions 配置在 `.github/workflows/tests.yml`，准备对 Python 3.8、3.11、3.13 运行离线检查。当前只验证了本机 Python 3.8.10，尚未发布到 GitHub 或声称云端 CI 已通过。

## CLI 与目录

```bash
python main.py --no-browser
python main.py --collect Remotive
python main.py --match data/demo_resume.txt --db /tmp/jobcompass-demo.db
python scripts/package_project.py --group 11
```

`--match` 会将指定简历保存到所选数据库，建议评估时使用临时数据库。打包脚本默认生成 `dist/group11_project.zip`，明确白名单只包含源码、测试、演示数据和文档。

```text
main.py                    课程要求的入口
jobcompass/config.py        本地配置
jobcompass/resume.py        简历文件解析与证据提取
jobcompass/matching.py      技能 F1 与 TF-IDF 排序
jobcompass/sources.py       公开数据源及导入器
jobcompass/storage.py       SQLite 仓储
jobcompass/ai.py            DeepSeek 提示词与输出校验
jobcompass/server.py        HTTP、后台任务及业务接口
jobcompass/static/          中文响应式 GUI
data/                      虚构演示简历、岗位及 CSV 模板
tests/                     自动化测试
scripts/                   网络检查、评估、打包
docs/                      规格、审查、提交材料与演示说明
```

## 故障处理

- 端口占用：打开已经运行的平台，或用 `--port 8766`。
- API 认证或余额错误：检查 `.env`，在供应商控制台核实密钥／余额后重启。
- 网页采集失败：查看明确提示，改用 CSV／JSON、带结构化数据的 HTML 或手动录入。
- PDF 没有文字：扫描件暂不支持 OCR，请粘贴文字或先用其他工具 OCR。
- 岗位没有匹配分：先保存有效简历。修改简历未保存不会改变已有分析。
- 网络不可用：示例与已采集数据、评分、投递看板均可离线使用。
- 日志时间：数据库使用 UTC，界面按本机时区显示。

## 课程材料与引用

见 `docs/SPECIFICATION.md`、`docs/CODE_REVIEW.md`、`docs/DEMO_SCRIPT.md`、`docs/COURSE_CHECKLIST.md`、`docs/REFERENCES.md`。项目由 AI 按用户提出的需求生成、调试并测试；个人报告须如实记录本人后续实际阅读、验证、修改和演示贡献。
