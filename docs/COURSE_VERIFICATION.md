# v1.3 课程增强版实测记录

日期：2026-11-18。环境：本机 Apple M2、16 GB 内存，核心 Python 3.8.10。项目版本 1.3.0。源码实际实现、验证证据和课堂需本人完成的事项分开记录。

## 本轮交付

- 技能成长页面：岗位频次、技能画像差距、原岗位证据、递归先修关系与循环检测。
- 最近50次投递状态及备注的持久撤销重做，事务保护并发修改，支持重启和新分支。
- 完整输入指纹的单项排名缓存，深复制隔离、并发去重、输入变化失效。
- 受限分步研究助手：最多3轮界面模型调用、聚合结果反馈、四类只读工具、执行轨迹、重复计划停止和取消。
- DeepSeek 瞬态错误重试，严格限状态码、尝试次数和退避调度；未将重试预算称为费用上限。
- 测试先行记录、doctest、固定随机种子不变量、静态检查、隔离变异检查、源码包审计、多系统/多版本 CI 配置与审查模板。
- 11份课程资料的53组主题映射、当前SRS、技术债台账、调试与演示补充、可选VS Code调试配置。

## 可复现实测

| 检查 | 实际结果 | 证据 |
|---|---|---|
| `python scripts/quality_gate.py --mutations` | 完整本地门禁通过 | evidence/quality_gate.json |
| unittest 全套 | 223 项通过 | test_results.txt；evidence/unittest-final.txt |
| 可执行文档示例 | 8 项通过 | evidence/doctest-final.txt |
| 五项指定变异 | 5/5 被测试捕获，原源码哈希不变 | evidence/mutation_report.json |
| 有限 AST 静态检查 | 27个产品/脚本Python文件，0项发现 | evidence/static-checks-final.txt |
| JavaScript 语法 | app.js、research.js、learning.js 均可解析 | Node `--check` 本轮实际执行 |
| 行执行统计 | 已生成各模块逐行信息 | evidence/coverage_summary.txt |
| 浏览器验收 | 虚构简历→学习路线；记录→撤销→重做均观察到正确状态 | screenshots/v13-learning.jpg、v13-history.jpg |
| 排名缓存 | 1200条合成岗位：未缓存中位201.321ms，命中52.661ms，约3.82倍 | evidence/ranking-cache-benchmark.json |

行统计使用标准库trace，只记录主线程，不包含HTTP或后台工作线程，不是分支覆盖。五项变异是手选故障，不是全项目变异覆盖。缓存基准不包括HTTP与SQLite，冷缓存有复制/哈希开销。全部自动化测试为离线模拟，没有为本轮测试调用真实DeepSeek或重新抓取网站。

## 真实测试先行证据

evidence 中保留 history-red/green、learning-red、cache-red、agent-red、tdd_red/green、tdd_doctest_red/green、retry_tdd_red/green。红灯记录产生于相应功能尚未实现或故意测试stub阶段，不是事后伪造。最终绿灯由全套测试覆盖。已有功能的历史开发顺序没有被追溯改写成TDD。

## 包与数据边界

最终源代码包由 `scripts/package_project.py --group 11` 生成，并再次做路径、CRC、私有文件与密钥模式检查。最终校验结果存放在 dist/package-verification.json，避免把压缩包自身哈希递归写进它自己。包不包含 .env、个人数据库、简历/投递历史、原始研究库或虚拟环境；仍附此前选定的清洗研究快照。

## 未声称完成的事项

GitHub Actions 配置已完成，但本轮未观察到远端运行；源码若仍只装在仓库ZIP中，工作流必须展开到仓库根目录才会执行。本轮未上传GitHub。旧Word/PDF/PPT仍是9月30日课堂版，新规格和演示补充可用于修订，不能称旧附件已同步全部v1.3内容。原大作业DOCX在原路径缺失，历史评分/时长要求尚未对原件复核。

成员仍需实际阅读和走读代码、亲自演示/录视频、开展人工互评、独立填写真实个人贡献并提交Moodle。课件中的语音/图像端点、完整Transformer训练和外部IDE使用不伪称为当前平台能力。按用户最新决定，已取消本地LLM微调，临时训练环境已移除，没有下载模型权重或开始训练。
