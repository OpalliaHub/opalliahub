# 参考资料与依赖声明

本项目根据产品需求开发，使用公开技术文档核对接口，并参考维护者提供的 JobsDB 采集逻辑。以下资料说明实现依据及第三方依赖；引用不代表第三方对本项目的认可。

| 资料或依赖 | 用途 | 官方来源 |
|---|---|---|
| Python 标准库 | HTTP server、SQLite、unittest、线程池、文件与文本处理 | https://docs.python.org/3/ |
| pypdf | 文字型 PDF 简历提取，第三方 BSD 许可组件 | https://pypdf.readthedocs.io/ |
| certifi | 受信任 CA 证书包，MPL 2.0 | https://github.com/certifi/python-certifi |
| DeepSeek JSON Output | 模型接口、JSON 结构化响应 | https://api-docs.deepseek.com/guides/json_mode/ |
| Remotive API 官方仓库 | 数据字段、来源署名、24 小时延迟、请求限制 | https://github.com/remotive-com/remote-jobs-api |
| Arbeitnow API | 公开岗位数据和来源范围 | https://www.arbeitnow.com/blog/job-board-api |
| Arbeitnow Terms 第 11 节 | API 可用性与回链要求 | https://www.arbeitnow.com/terms |
| Schema.org JobPosting | 网页结构化岗位字段 | https://schema.org/JobPosting |

TF-IDF、余弦相似度与 F1 为通用信息检索／评估方法，本项目使用标准库自行实现，没有训练自定义大模型。各权重为本项目的设计选择，尚未基于真实招聘结果校准。

AI 使用披露：Codex 协助规格设计、业务代码、测试、UI、代码审查与文档；DeepSeek 在运行时提供可选的简历分析和受限研究指令编译。自动化简历测试使用虚构内容，联网检查范围以对应验证记录为准。贡献者应复核生成内容并如实说明实际贡献；AI 协助不等同于独立人工评审。

## User-provided research data

JobsDB snapshot `20260928112455_6939.zip` was supplied by the project maintainer; original postings retain individual links to https://hk.jobsdb.com/. Normalization and limitations are recorded in [BENCHMARK.md](BENCHMARK.md). Private cloud links, credentials and unrelated personal files are excluded. Current interface adaptation is documented in [JobsDB update verification](JOBSDB_V7_VERIFICATION.md).
