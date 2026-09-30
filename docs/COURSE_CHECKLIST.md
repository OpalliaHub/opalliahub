# INT6181 交付与评分对应

| 评分维度 | 权重 | 本项目证据 |
|---|---|---|
| Originality and practicality | 10% | 用户提出的多源简历匹配需求；单机运行、真实岗位、投递管理 |
| Usability | 10% | 中文 GUI、输入反馈、背景任务、离线示例、运行说明 |
| Technical depth and difficulty | 55% | 函数／类／模块、HTTP、SQLite、正则、文件解析、算法、线程池、规格、测试、AI 审查、CI 配置 |
| Group presentation | 20% | 五页讲义与 5 分钟要点；15 分钟演示脚本；视频需成员参与录制 |
| Individual report | 5% | 至少 600 词英文报告草稿和结构；需要每位成员以本人实际贡献修订 |

小组：Group 11。成员：OU JUNHANG、ZHANG XIQIAN、JIANG YIFAN、CAI SHANGHENG、GUO ZHENGKUN。

入口 `main.py` 与根目录 `README.md` 符合命名要求。使用 `python scripts/package_project.py --group 11` 生成 `group11_project.zip`。英文提案在 `docs/submission/Group11_Project_Proposal.docx`，演示文稿在 `docs/submission/group11_presentation.pptx`。

Proposal：JobCompass is a local Python application that combines resume extraction, public job data collection, explainable ranking and application tracking. It uses SQLite, a modular service layer, deterministic tests and an optional DeepSeek integration for evidence-based resume assistance. The project evaluates both offline behavior and real service connectivity, and documents limitations of synthetic evaluation and geographic data coverage.

提交前由小组完成：补充成员学号；验证各人的实际贡献；亲自录制 15 分钟视频并安排五分钟讲解；提交 Moodle 提案及作品；参加同学互评。AI 没有代表成员做出参与承诺、完成个人学习或参加互评。

源码包不包含真实 API 密钥、个人简历数据库、虚拟环境及采集到的第三方完整岗位数据。个人报告草稿带有明确待核实标记，不能不经修改当作本人贡献声明提交。
