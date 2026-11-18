# 测试与调试实践记录（v1.3）

本记录区分本轮实际执行的验证和供成员亲自操作的调试步骤。日志位于本机 output，最终精选副本在 docs/evidence；不会虚构过去先写过的测试。

## 实际测试先行：投递历史

先写 tests/test_history.py，运行失败（Store 尚无 history_status/application_history，历史表不存在），日志 history-red.txt。再实现事务性历史栈，8 个用例通过，日志 history-green.txt。用例验证连续撤销/重做、删除恢复、分支失效、无变化保存、重启、上限、迁移和并发。已有测试不是本轮才写；不可把全项目开发过程称为严格 TDD。

一个容易漏掉的反例是「撤销收藏 → 再保存未收藏」：此时没有数据变化，必须保留重做分支。实现先比较快照内容，再删除旧分支。另一个反例是并发请求同时读取同一个前状态；BEGIN IMMEDIATE 将前状态读取、业务写入和历史写入放在同一事务。

## 自动化方法各自说明什么

- 单元测试：输入分区、边界、解析、评分、JSON 白名单和 SQLite 行为。
- doctest：可执行 API 文档样例；具体测试先行时间以质量门禁日志为准。
- 集成测试：临时回环 HTTP 服务上的真实请求、状态码、写入与 UI 资源；没有外部网络调用。
- 固定种子生成：test_properties.py 用 seed=6181 生成 80 组排名输入，检查有界、稳定排序、不修改输入；seed=11 生成60个未知计划字段，检查全部拒绝。可复现，但不声称穷举或完全模糊测试。
- 变异试验：在临时副本中引入指定故障，检查现有测试能否失败；分母仅限选定变异，不等于整个项目的变异覆盖率。
- 覆盖统计：`python scripts/coverage_report.py` 生成逐行 .cover 和 summary.txt。标准库 trace 只记录当前线程，不计 HTTP/后台工作线程；这是行执行信息，不是分支覆盖或正确性证明。

## 成员可亲自完成的断点实验

在 PyCharm/VS Code 为 Store.application 的 before/after 比较设置断点。用临时 demo 数据库依次收藏、修改备注、撤销、重做，观察局部变量和调用栈；不要用真实简历/备注截图。或执行：

```bash
python -m pdb -m unittest tests.test_history.HistoryTests.test_noop_preserves_redo
```

使用 `b jobcompass/storage.py:行号`（以当前文件实际行号为准）、`c`、`n`、`p before`、`p after` 观察控制流。此文提供步骤，未声称五位成员已使用断点工具。

## 性能定位

`python -m cProfile -s cumulative scripts/evaluate.py` 可定位合成语料的 TF-IDF 排名热点。该脚本会更新 docs/evaluation.json，请在评估副本执行，保留数据规模、运行环境和合成样本说明。排名缓存的实测另见 RANKING_CACHE.md；缓存命中不能代替算法准确率评估。

## CaseStudy5 的两类需求描述

宽泛提示示例：「做一个智能找工作平台。」它缺少数据、错误和评分含义边界。

正式需求示例：「FR19：最近50次状态与备注修改可撤销/重做，重启保留；无效输入零写入；新分支清除重做；并发操作应串行化。」对应8项测试和SQL事务，能被检查。

这是对两种描述的分析与本轮正式需求实践，不声称重新执行了两套模型对照实验。个人的初始提示、模型代码批评、Moodle三问反思和VeriVibe操作仍须本人完成并记录真实经历。
