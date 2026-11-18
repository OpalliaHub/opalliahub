# INT6181 Group 11 课堂作业清单

修订日期：2026-09-30。成员：OU JUNHANG、ZHANG XIQIAN、JIANG YIFAN、CAI SHANGHENG、GUO ZHENGKUN。学号待成员补充。

## 本次同步的交付物

| 文件 | 用途与状态 |
|---|---|
| `group11_project.zip` | 源码、测试、README、演示数据、清洗后的研究快照及文档；入口为 `main.py` |
| `group11_presentation.pptx` | 5 页英文课堂演示，按 5 分钟安排；每页含英文演讲者备注 |
| `Group11_Project_Proposal.docx` | 英文提案，已更新小组、研究数据及当前实现范围 |
| `Group11_Project_Report.docx` | 英文项目报告，解释架构、匹配算法、benchmark、测试及局限 |
| `Group11_Demo_Guide.docx` | 5 分钟英文逐页讲稿、15 分钟视频操作流程、启动方式及答问 |
| `Group11_Individual_Report_Draft.docx` / `.pdf` | 超过 600 词的个人报告参考草稿；实际贡献与学习内容必须由各成员分别修订 |
| `group11_course_submission.zip` | 上述文件的集中下载包；应按 Moodle 栏目分别提交需要的文件 |

正式文稿副本位于 `docs/submission/`。可编辑文字源在 `docs/PROJECT_PROPOSAL.md`、`docs/PROJECT_REPORT.md`、`docs/DEMO_SCRIPT.md` 和 `docs/INDIVIDUAL_REPORT_DRAFT.md`。

## 评分要求对应

| 评分维度 | 权重 | 本项目证据 |
|---|---|---|
| Originality and practicality | 10% | 多源简历匹配需求、可解释岗位比较、应用进度管理 |
| Usability | 10% | 中文 GUI、输入反馈、背景任务、离线示例、正确的服务启动入口 |
| Technical depth and difficulty | 55% | 函数／类／模块、HTTP、SQLite、正则、文件解析、算法、线程池、规格、测试、审查和 benchmark |
| Group presentation | 20% | 五页 PPT、五分钟讲稿、十五分钟视频脚本；视频与课堂展示需成员亲自完成 |
| Individual report | 5% | 每人至少 600 词 PDF；参考草稿不等于已完成的个人贡献报告 |

## 已核对的事实

- JobsDB 2026-09-28 研究档案：6,939 条输入、29 条无效、6,910 条有效研究记录；应用排除 2 条已过期记录，导入 6,908 条。
- 独立课堂数据库含 6,908 条 JobsDB 岗位加 12 条虚构样例，共 6,920 条。已有数据库可能包含其他来源，不能用总数替代 benchmark 样本数。
- 当前本地测试为 71 项通过；结果在 `docs/test_results.txt`。
- 6,910 条记录完整排序的历史三次耗时为 4.0517、4.0059、4.0634 秒，中位数 4.0517 秒。仅为特定环境下的排序耗时。
- 研究数据没有人工相关性标签，因此不宣称真实数据准确率、召回率或 NDCG。12 条合成样例的结果只用于样例验证。
- 正确入口是先启动 `main.py` 或 macOS 启动器，再打开 `http://127.0.0.1:8765/`。GitHub 仅提供下载，不运行这个本地服务。
- PPT 中表格和权重图保持可编辑。文档和幻灯片均经过渲染检查。
- 源码包不含 `.env`、API 密钥、个人数据库、虚拟环境或原始 OneDrive 档案。只包含选定的清洗研究快照。

## 成员仍须完成

补充五位成员学号并确定 Moodle 联系提交人；各成员阅读、验证项目，分别写出真实贡献和学习经历；亲自录制 15 分钟视频，排练并进行 5 分钟课堂展示，完成同学互评及 Moodle 提交。个人报告必须分别修改，不能把共同草稿直接当作五人的独立贡献声明。材料已披露 AI 辅助实现、测试、审查和写作。

源码重新打包命令：`python scripts/package_project.py --group 11`。后续修改文稿源时，也应更新 Word/PDF/PPT 副本及课堂集中包。
