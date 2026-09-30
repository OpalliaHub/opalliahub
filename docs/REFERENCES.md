# 参考资料与依赖声明

本项目按用户提出的功能需求由 AI 原创生成，并使用公开技术文档核实接口。没有复制其他课程小组或开源应用的业务代码。以下依赖与文档应在课堂展示及报告中保留引用。

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

TF-IDF、余弦相似度与 F1 为通用信息检索／评估方法，本项目使用标准库自行实现，没有训练自定义大模型。各权重为课程项目设计选择，尚未基于真实招聘结果校准。

AI 使用披露：Codex 协助规格设计、业务代码、测试、UI、代码审查与文档；DeepSeek 作为程序运行时的可选简历顾问。实测只发送虚构简历。生成内容需要小组成员理解、复核并据实说明贡献。
