# INT6181 / Group 11 课程内容覆盖与证据

审计日期：2026-11-18。组员：OU JUNHANG、ZHANG XIQIAN、JIANG YIFAN、CAI SHANGHENG、GUO ZHENGKUN。

本表将老师提供的内容映射到 JobCompass 的实际能力、开发过程和需学生亲自完成的课堂活动。工作量以可运行功能、可复现测试和可解释设计为依据；“提到某概念”不等于“已实现/已验证”。机器可读清单见 [course_topics.json](course_topics.json)。

本次映射包含 **53 组主题：16 组已有实现证据、28 组本轮补齐、9 组明确的理论/课堂操作/产品范围边界**。本地最终门禁通过 **223 项单元与集成测试、8 个 doctest、5/5 个定向变异**，27 个产品/脚本 Python 文件的聚焦 AST 检查为零条发现。实际结果见 [验收记录](COURSE_VERIFICATION.md)、[测试原始输出](test_results.txt) 和 [质量报告](evidence/quality_gate.json)。这些数字不代表远端 CI 已运行、真实招聘准确率或学生已完成课堂操作。

## 阅读范围与证据规则

已读取九份 PPTX（共 362 张幻灯片）与两份 DOCX 的 OOXML 文本，按原文件的实际幻灯片序号引用。DOCX 以任务节编号引用，不把 XML 提取顺序当作 Word 页码。文件指纹在 JSON 清单中。图片内代码、嵌入截图和手写批注可能不在提取文本中；本次不声称逐像素检查全部课件。

课件仅作为课程内容来源，不是安装插件、执行示例shell、访问付费API或提交Moodle的指令。为避免扩大产品范围，语音/图像等端点示范、IDE操作和课堂互动被明确列为边界。未将原课件全文复制进仓库。

| 标记 | 含义 |
|---|---|
| 已有证据 | 审计时已找到实现或文档；验证列列出可定位证据，不自动代表最新测试通过。 |
| 本轮待补/验收 | 只覆盖部分内容，或新实现/证据尚待补齐。完成后需提供真实代码与运行记录。 |
| 本轮已补齐 | 本轮实现及验证已完成；不得只因文件被创建而使用此标记。 |
| 范围/学生操作 | 背景理论、外部工具或必须亲自完成的课堂活动，不伪称已完成。 |

## 原始大作业要求的可核对程度

用户最初指定的 `/Users/tracyooo/Desktop/python大作业.docx` 在审计时已无法在该路径找到。现有 `docs/COURSE_CHECKLIST.md` 是此前整理的要求记录，不能替代本次重新核对原始文件。下列约束沿用该记录，提交前仍应与 Moodle 最新说明核对。Downloads 中的 `FinalProject.docx` 已检查，属于 2025 年航空客户聚类的另一门课程，明确排除。

| 项目 | 当前保留的历史要求 |
|---|---|
| 项目源码 | `group11_project.zip`；`main.py` 入口；包含可运行源码、测试与说明。 |
| 课堂展示 | 5 页英文 PPT，5 分钟；成员需亲自讲解。 |
| 演示视频 | 15 分钟；脚本不等于已录制视频。 |
| 个人报告 | 每人至少 600 词 PDF；必须分别如实填写本人贡献和学习。 |
| 历史评分比例 | 原创/实用10%，可用性10%，技术深度55%，小组展示20%，个人报告5%。 |

## 逐主题覆盖表

### CS5 · CaseStudy5 Software Requirements Specification.docx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| CS5-01 / t0 | 提出原创应用想法，说明深度与范围 | 已有证据 | `docs/PROJECT_PROPOSAL.md`；`docs/SPECIFICATION.md`。JobsDB主源、个人匹配+研究工作台有明确使用者与边界。 | 原作业要求个人先构思；不能将AI提案当作每人独立构思事实。 |
| CS5-02 / t1 | 自然语言提示生成版本并评估质量 | 范围/学生操作 | `docs/DEBUGGING_LAB.md`；`docs/PROJECT_PROPOSAL.md`。调试文档对比宽泛提示和可验证FR19，解释质量差异与缺失边界。 | 是本轮教学分析，未伪造历史prompt/初版，也未重新运行两套模型对照；原个人练习和Moodle提交仍需本人完成。 |
| CS5-03 / t2 | 正式SRS驱动代理实现与质量比较 | 本轮已补齐 | `docs/SPECIFICATION.md`；`AGENTS.md`；`docs/DEBUGGING_LAB.md`；`docs/QUALITY_WORKFLOW.md`。本轮以明确FR/NFR、先行测试、代理实现和失败反馈完善产品，保存真实过程与质量证据。 | 未宣称原CaseStudy5个人软件版本或Moodle提交已完成；/grill-me为来源列出的可选方法，未被本次调用。 |
| CS5-04 / t1/t2 submissions; t3 | 三题反思问卷与分项ZIP提交 | 范围/学生操作 | `docs/INDIVIDUAL_REPORT_DRAFT.md`。可提供真实反思问题和参考，不知道Moodle题目原文。 | 未进入Moodle提交，不能代答未给出的个人反思问卷。 |

### L02 · Lecture02 Review of Programming I.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| P1-01 / slides 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 | 变量、命名、int/float/bool/str/list/None、转换与异常 | 已有证据 | `jobcompass/research.py:validate_plan`；`jobcompass/jobsdb.py:options`；`jobcompass/resume.py:parse_resume`。tests/test_jobsdb.py:test_options_are_bounded; tests/test_core.py:ResumeTests | 显式拒绝 bool 冒充整数；Python float 有有限精度，不沿用课件第9页“任意精度浮点数”的不准确表述。 |
| P1-02 / slides 18, 19, 20, 21, 22, 23, 24, 25 | 输入输出、format/f-string、数字和宽度格式 | 已有证据 | `scripts/research.py:main`；`scripts/benchmark_jobsdb.py:main`；`jobcompass/matching.py:rank_jobs`。命令行参数、JSON输出及格式化说明已存在。 | Web输入取代交互式 input()；不声称已有逐项 input()/对齐格式课堂练习。 |
| P1-03 / slides 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 42, 43, 44, 45, 46, 47, 48 | 算术、赋值、比较、逻辑、优先级、括号与零分母 | 已有证据 | `jobcompass/matching.py:skill_fit`；`jobcompass/matching.py:text_scores`；`jobcompass/research.py:validate_plan`。tests/test_core.py:test_empty_corpus; test_missing_weight; test_bounds | 整除/取模/交换变量等语法例子可在学习练习中演示，不应为凑语法改写正确生产代码。 |
| P1-04 / slides 38, 39, 40, 41 | 浮点近似比较与 == / is 的区别 | 已有证据 | `tests/test_core.py:MatchingTests.test_same_text`；`jobcompass/matching.py:rank_jobs`。使用 assertAlmostEqual 检查余弦相似度；None 用 is None 判断。 | 类比讲解 math.isclose 与 assertAlmostEqual；不是招聘准确率检验。 |
| P1-05 / slides 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69 | 分支、truthiness、循环、range、嵌套、break/continue、迭代安全 | 已有证据 | `jobcompass/jobsdb.py:collect`；`jobcompass/matching.py:tokens`；`jobcompass/matching.py:text_scores`；`jobcompass/sources.py:parse_jsonld`。tests/test_jobsdb.py:JobsDBTests; tests/test_core.py:MatchingTests | 素数/星号三角是教学练习，业务对应是分页采集、去重和文本向量迭代。 |
| P1-06 / slides 60, 70, 71, 72 | 可变默认参数、共享引用、控制/数据流追踪 | 本轮已补齐 | `jobcompass/learning.py:PrerequisiteGraph`；`tests/test_learning.py:test_graph_copies_caller_data_and_unknown_nodes_are_terminal`；`tests/test_learning.py:test_inputs_are_not_mutated_and_missing_ids_have_stable_identity`。可变输入隔离、不可变缓存及缺省对象边界已有回归；最终223项单元/集成测试通过，见docs/test_results.txt。 | 数据流可用递归图与闭包逐步走读；Python Tutor/IDE课堂单步操作仍需成员亲自完成。 |

### L03 · Lecture03 Review of Programming II.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| P2-01 / slides 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18 | 函数定义/调用/参数/返回、作用域、嵌套函数与一致返回类型 | 已有证据 | `jobcompass/resume.py`；`jobcompass/sources.py:parse_jsonld.walk`；`jobcompass/server.py:Tasks.submit`。tests/test_core.py; tests/test_http.py | 局部作用域和闭包真实使用；避免把列表名等覆盖内建符号的反例作为正常代码。 |
| P2-02 / slides 19, 20, 21, 22 | 递归、基例和复杂度 | 本轮已补齐 | `jobcompass/learning.py:PrerequisiteGraph._ordered`；`jobcompass/sources.py:parse_jsonld.walk`；`tests/test_learning.py:PrerequisiteGraphTests`。递归先修图含循环检测、终止节点、共享先修去重；20项learning测试进入最终通过的223项测试套件。 | DFS复杂度O(V+E)，图映射最多128节点；原JSON-LD解析深度限制仍是独立维护事项。 |
| P2-03 / slides 23, 24, 25, 26, 27 | 高阶函数、装饰器、计时与缓存 | 本轮已补齐 | `jobcompass/learning.py:PrerequisiteGraph.prerequisites`；`jobcompass/storage.py:Store.connection`；`scripts/quality_gate.py:run_command`。@lru_cache(maxsize=256)真实复用不可变tuple，测试验证cache hit；@contextmanager管理事务连接；quality runner记录耗时。 | 实际缓存包括有界先修tuple缓存和单项排名缓存；没有为凑语法另造timeit装饰器，计时在质量门禁及benchmark中完成。 |
| P2-04 / slides 29, 30, 31, 32 | list 与 LIFO 栈、撤销/重做 | 本轮已补齐 | `jobcompass/storage.py:Store.application_history`；`jobcompass/storage.py:Store.history_status`；`jobcompass/learning.py:PrerequisiteGraph._ordered`；`tests/test_history.py`。持久化双栈以事务原子转移，最多50条，支持分支、no-op、重启及并发；history-red.txt/ history-green.txt保留真实8项RED/GREEN，集成HTTP往返通过。 | 列表append/pop体现递归活动栈；数据库双栈体现用户投递操作撤销/重做。 |
| P2-05 / slides 33, 34, 35, 73, 74, 75 | 别名、浅复制、深复制与对象独立性 | 本轮已补齐 | `jobcompass/learning.py:PrerequisiteGraph.__init__`；`jobcompass/learning.py:SkillGap.to_dict`；`jobcompass/research.py:validate_plan`；`tests/test_learning.py`；`jobcompass/ranking_cache.py:RankedJobsCache`；`tests/test_ranking_cache.py`。输入图复制与不可变缓存、frozen dataclass/asdict、排名缓存对输入/保留结果/返回值作deepcopy；相关测试检查修改输入和返回数据不污染后续结果。 | 浅复制与深复制在学习说明中分别解释，不能把浅复制当嵌套隔离。 |
| P2-06 / slides 36, 37, 38, 39, 40, 41, 42, 43, 44, 45 | tuple/set/dict、不可变性、集合运算、计数直方图 | 已有证据 | `jobcompass/storage.py:Store.upsert_jobs`；`jobcompass/matching.py:skill_fit`；`jobcompass/matching.py:text_scores`；`jobcompass/research.py:run`。tests/test_core.py:test_generic_skill_does_not_dominate; tests/test_research.py:test_skill_percentages_count_ads_once | Counter负责频次统计；集合交/差集用于技能解释。 |
| P2-07 / slides 46, 47, 48, 49, 50, 51, 52 | sorted/key/lambda、filter和一次性迭代器 | 已有证据 | `jobcompass/matching.py:rank_jobs`；`jobcompass/benchmark.py:convert_archive`。tests/test_core.py:test_deterministic; tests/test_benchmark.py | 生产代码使用列表推导过滤；显式 filter() 耗尽陷阱可在学习练习说明。 |
| P2-08 / slides 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65 | 类/对象、封装、__init__/self、实例状态 | 已有证据 | `jobcompass/storage.py:Store`；`jobcompass/server.py:Tasks`；`jobcompass/server.py:Application`；`jobcompass/research.py:Research`。tests/test_core.py:StorageTests; tests/test_jobsdb.py:test_task_progress_cancel_and_resume_state | 实例创建、方法调用及数据库持久化均为实际业务。 |
| P2-09 / slides 66, 67, 68, 69, 70 | classmethod/staticmethod/__str__ | 范围/学生操作 | `tests/test_http.py:HTTPTests.setUpClass`；`jobcompass/storage.py:Store._restore_application`；`jobcompass/learning.py:SkillGap`。classmethod用于测试服务夹具，staticmethod用于事务快照恢复；数据类的展示使用结构化JSON。 | 尚未单独实现自定义__str__；这一精确语法例子保留为课堂学习边界，不把生成的repr或JSON误称__str__，也不为覆盖语法堆砌产品代码。 |
| P2-10 / slides 71, 72 | 继承、方法重写、父类初始化 | 已有证据 | `jobcompass/sources.py:PlainText`；`jobcompass/sources.py:JsonLD`；`jobcompass/sources.py:SafeRedirect`；`tests/test_core.py:ResumeTests`。tests/test_core.py:test_plain; test_jsonld_graph; test_private_network | HTMLParser 与 HTTPRedirectHandler 的继承实际用于清洗和URL重定向限制。 |
| P2-11 / slides 76, 77, 78, 79, 80, 81, 82, 83, 84, 85 | 文件路径、读写模式、with、异常清理、流式读取 | 已有证据 | `jobcompass/benchmark.py:load_snapshot`；`jobcompass/benchmark.py:write_snapshot`；`jobcompass/resume.py:extract_file`；`jobcompass/storage.py:Store.connection`。tests/test_benchmark.py:test_gzip_is_reproducible_and_roundtrips; tests/test_core.py:test_corrupt_docx | 研究SQLite游标迭代避免载入所有正文；部分小文件按上限整体读取并非无条件流式。 |

### L04 · Lecture04 Generative AI in Programming.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| AI-01 / slides 3, 4, 5, 6, 7, 8, 9, 10 | 生成式AI/LLM/Transformer、编码解码、生成结果不等于事实 | 范围/学生操作 | `docs/PROJECT_REPORT.md`；`jobcompass/ai.py`；`jobcompass/research_ai.py`。可解释本地数字与模型叙述分离；必须在课堂说明架构背景。 | 本项目调用模型，不训练或实现Transformer，也不把token概率当事实置信度。 |
| AI-02 / slides 11, 12, 13, 14 | 提示词的指令、上下文、输入、输出约束 | 已有证据 | `jobcompass/ai.py:call_ai`；`jobcompass/research_ai.py:plan_command`；`jobcompass/research_ai.py:explain_result`。tests/test_core.py:test_ai_schema; tests/test_research.py:test_plan_response_is_validated | schema校验与allowed operations比只要求“输出JSON”更强。 |
| AI-03 / slides 15, 16, 17, 18, 24 | SRS、需求/约束/验收、分解与标准意识 | 本轮已补齐 | `docs/SPECIFICATION.md`；`docs/QUALITY_WORKFLOW.md`。v1.3 SRS新增FR14–19与NFR05–07，包含研究、受限AI计划、学习图和历史栈；具体验收场景关联测试文件。 | 采用SRS结构与可验证需求，不声称标准认证；旧快照数字仅是历史记录。 |
| AI-04 / slides 19, 20, 21, 22, 23, 24, 43, 44 | 编码与提示协作、计划先行、反馈循环、自治风险 | 本轮已补齐 | `AGENTS.md`；`docs/DEBUGGING_LAB.md`；`docs/QUALITY_WORKFLOW.md`；`tests/test_research.py:test_model_cannot_execute_code`。本轮保存测试先行证据、计划/实现/验证流程与工具边界；调试文档区分真实记录和未进行的学生操作。 | 未追溯编造早期开发步骤；个人阅读、课堂操作和学习反思不能由AI证明。 |
| AI-05 / slides 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38 | 编辑器AI Chat/补全、IntelliSense/LSP/Pylance | 范围/学生操作 | `docs/COURSE_COVERAGE.md`。属于开发工具与课堂操作，可对本仓库演示代码问答和补全评估。 | 未替用户安装或登录Copilot/VSCode；项目功能不能证明课堂工具操作已经完成。 |
| AI-06 / slides 35 | 静态检查与linting | 本轮已补齐 | `scripts/static_checks.py:lint_source`；`tests/test_static_checks.py`；`scripts/quality_gate.py`。聚焦AST规则检查可变默认参数、裸except、直接eval/exec、星号导入及语法错误；最终27个产品/脚本Python文件0条发现，另有规则回归测试。 | 这是聚焦lint，不是完整PEP8风格、不可达代码分析或类型检查；仍需代码评审与运行测试。 |
| AI-07 / slides 39, 40, 41, 42, 44, 45, 46, 47 | Agent模式/异步编码代理、AGENTS.md、计划与测试约定 | 本轮已补齐 | `AGENTS.md`；`docs/QUALITY_WORKFLOW.md`；`.github/pull_request_template.md`。仓库提供明确构建/测试命令、数据边界、变更流程、失败反馈和不得虚构证据的代理约定。 | 编辑器代理与异步代理是课堂概念；未声称已配置全部商业开发工具。 |

### L05 · Lecture05 Foundation of Coding Agents.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| AG-01 / slides 3, 4, 5, 6, 7, 8, 15, 16, 17, 18, 19, 20 | OpenAI兼容接口、模型能力、文本/Chat/Responses API | 已有证据 | `jobcompass/ai.py:call_ai`；`jobcompass/research_ai.py:_call`；`jobcompass/config.py`。现有DeepSeek chat/completions JSON请求、角色与token上限；离线mock校验格式。 | 只实现当前配置的文本聊天端点；models.list/completions/responses不是现有功能，不把mock通过当联网成功。 |
| AG-02 / slides 9, 10, 11, 12, 13, 14 | 语音生成/转录/翻译、图像生成、embedding与AI来源识别 | 范围/学生操作 | `docs/COURSE_COVERAGE.md`。能力边界说明：招聘统计主流程没有这些输入输出需求。 | 未启用这些端点或进行AI来源真实性鉴定；TF-IDF不是神经embedding。需额外供应商能力、成本与隐私评估方可扩展。 |
| AG-03 / slides 19 | 重试/指数退避、成本与上下文上限 | 本轮已补齐 | `jobcompass/retry.py:request_with_retry`；`jobcompass/ai.py:call_ai`；`jobcompass/research_ai.py:_call`；`tests/test_retry.py`；`docs/AI_RELIABILITY.md`。12项mock测试先红后绿：仅429/502/503/504最多3次，等待1/2秒，95秒调度窗口与剩余超时预算；两个AI适配器接入，JSON校验在重试之外。 | 不重试超时、认证/权限/余额或无效模型输出；95秒不是正在执行socket的硬墙钟取消；无真实付费请求验证，不承诺网关失败恰好计费一次。 |
| AG-04 / slides 22, 23, 24, 25 | 模型+harness、工具路由、权限与沙箱边界 | 已有证据 | `jobcompass/research.py:validate_plan`；`jobcompass/research.py:readonly`；`jobcompass/research_ai.py:plan_command`；`jobcompass/server.py:Application.post`。tests/test_research.py:test_model_cannot_execute_code; test_readonly_db_rejects_writes; test_sql_injection_is_literal_filter | JSON仅表达受限查询，不执行模型生成的Python/SQL/路径。 |
| AG-05 / slides 25, 26, 28, 29 | 多步agent循环、轨迹、上下文管理与停止条件 | 本轮已补齐 | `jobcompass/research_agent.py:run_agent`；`jobcompass/server.py:Application.post /api/research/agent`；`tests/test_research_agent.py`；`docs/RESEARCH_AGENT.md`；`docs/evidence/agent-red.txt`；`docs/evidence/agent-http-green.txt`。新增计划→校验→执行→聚合观察→继续/完成循环；仅overview/skills/trend/compare，固定数据集，1–4逻辑轮，重复计划/预算/取消/异常停止，逐步轨迹与结果ID可检查。agent+HTTP+retry联合53项实际通过。 | 每轮底层瞬态HTTP重试最多3次，4逻辑轮最多12次传输尝试，不是4次账单硬上限；取消为调用间协作式。仅发送受限聚合，不开放bash、原文或模型SQL；任务轨迹不冒充永久训练数据集。 |

### L06 · Lecture06 Testing and Debugging I.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| TEST-01 / slides 4, 5, 6, 7, 8, 10, 11 | 验证/确认、V模型与需求-测试对应 | 本轮已补齐 | `docs/SPECIFICATION.md`；`docs/QUALITY_WORKFLOW.md`；`tests/test_core.py`；`tests/test_http.py`；`tests/test_research.py`。规格描述功能与约束、具体新增验收场景和测试路径；质量流程另列缺陷风险、代表测试及验证手段。 | UI可用性、课堂展示和成员掌握程度需要人工验收；映射本身不是验收通过证明。 |
| TEST-02 / slides 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 | 功能需求与可量化非功能需求 | 本轮已补齐 | `docs/SPECIFICATION.md`；`scripts/benchmark_jobsdb.py`；`docs/benchmark_jobsdb.json`；`tests/test_history.py`；`tests/test_http.py`。已给出上传大小、文本长度、岗位/历史上限、回环边界、事务与持久化条件；业务边界和并发有测试。 | 性能历史数据有固定样本/环境边界，不将课件金融医疗例子的指标移植为本项目结果。 |
| TEST-03 / slides 9, 22, 23, 24, 25, 26, 27, 28 | TDD、doctest、批量/边界/异常样例 | 本轮已补齐 | `scripts/quality_gate.py:archive_relative`；`scripts/quality_gate.py:private_reason`；`tests/test_quality_gate.py`；`tests/test_learning.py`；`tests/test_history.py`。本轮新增history、learning和质量门禁保留实际测试先行记录；archive_relative另保留4个新doctest的先失败后实现序列，合计8例最终通过。 | 仅对有记录的本轮功能声明TDD；RED/GREEN见docs/evidence/tdd_*.txt及docs/evidence/，不能把既有全部实现标为测试先行。 |

### L07 · Lecture07 Testing and Debugging II.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| TEST-04 / slides 3, 4, 5, 6, 7, 8, 9, 10 | unittest fixture/case/suite/runner、断言与隔离 | 已有证据 | `tests/test_core.py:StorageTests`；`tests/test_http.py:HTTPTests`；`tests/test_research.py:ResearchTests`。setUp/tearDown临时目录、classmethod服务夹具、unittest discover。 | 测试数量和最近结果以本轮最终验证日志为准，不沿用旧71/120项数字。 |
| TEST-05 / slides 11, 12, 13, 14, 15, 16, 17 | IDE测试发现、目录与模式配置 | 本轮已补齐 | `.vscode/settings.json`；`.vscode/launch.json`；`docs/DEBUGGING_LAB.md`；`tests/__init__.py`。新增unittest发现目录/模式、Python基础类型分析配置、隔离demo与测试debug启动配置，PyCharm仍可按测试命令运行。 | 配置已提供；VSCode/Pylance/debugpy扩展的安装与学生实际测试发现、单步操作没有被伪称完成。 |
| TEST-06 / slides 18, 19, 20, 21 | AI测试辅助、mock、数据生成、覆盖率与缺陷报告 | 本轮已补齐 | `tests/test_properties.py`；`scripts/coverage_report.py`；`scripts/mutation_check.py`；`tests/test_jobsdb.py`；`tests/test_research.py:ResearchAITests`。固定种子80组评分不变量、60组未知计划字段；主线程trace行执行统计归档docs/evidence/coverage_summary.txt；5个定向变异全部被断言杀死，原源码指纹保持不变。 | trace不含后台线程且不是分支覆盖；5个变异不是全项目mutation coverage；固定随机样例不证明无漏洞。 |
| TEST-07 / slides 22, 23, 24, 25, 26, 27, 28, 29, 30, 31 | 断点、变量、调用栈、step in/over/out、条件断点 | 本轮已补齐 | `docs/DEBUGGING_LAB.md`；`jobcompass/storage.py:Store.application`；`tests/test_history.py:test_noop_preserves_redo`。新增pdb与IDE断点实验，明确观察before/after、局部变量、调用栈、继续与单步；给出可重复场景。 | 文档是可执行练习说明，尚未声称成员已完成断点、step in/over/out或条件断点操作。 |
| TEST-08 / slides 32, 33, 34 | AI辅助调试、保留测试、复现上下文和回归验证 | 本轮已补齐 | `docs/DEBUGGING_LAB.md`；`.github/ISSUE_TEMPLATE/bug_report.md`；`docs/QUALITY_WORKFLOW.md`。真实RED/GREEN记录、未变化保存仍保留redo的反例、并发事务原因及缺陷报告模板构成调试上下文。 | 禁止削弱断言来消除失败；未来真实故障应保留最小输入和失败栈，不能把教学变异说成生产事故。 |

### L08 · Lecture08 Technical Debt in Software.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| DEBT-01 / slides 3, 4, 5, 6, 7 | 技术债本金/利息/偿还、债务与普通功能待办的区别 | 本轮已补齐 | `docs/TECHNICAL_DEBT.md`。六项债务记录原始取舍、当前成本、偿还触发与验收；另列功能待办和人工相关性评估需求。 | 无语音或无新增数据源不是自动的技术债；状态open/partially repaid保持可见。 |
| DEBT-02 / slides 8, 9, 10, 11, 12 | 显式/隐式债务、优先级及业务-工程权衡 | 本轮已补齐 | `docs/TECHNICAL_DEBT.md`。按本地单用户范围给出优先级和拟定角色，区分接受的快指纹取舍与需改善的路由/UI维护成本。 | 角色不是已履职的学生姓名，课堂游戏和研究百分比不当作本项目测量。 |
| DEBT-03 / slides 13, 14, 15 | AI时代知识债、认知债、意图债 | 本轮已补齐 | `docs/TECHNICAL_DEBT.md`；`AGENTS.md`；`docs/SPECIFICATION.md`；`docs/COURSE_DEMO_V1_3.md`。明确TD06知识/意图债、理由与边界文档、代码走读和评审补偿动作，防止仅靠聊天记忆维护项目。 | 文档可降低知识债；五位成员实际理解与独立走读仍需本人完成。 |

### L09 · Lecture09 Continuous Integration  Deployment_v2.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| CI-01 / slides 4, 5, 6, 7, 8, 9, 10, 11 | CI测试目标/设计/执行/判定、频繁小步集成 | 本轮已补齐 | `.github/workflows/tests.yml`；`scripts/quality_gate.py`；`scripts/mutation_check.py`；`docs/QUALITY_WORKFLOW.md`；`docs/evidence/quality_gate.json`。workflow定义push/PR/manual、多Python与macOS矩阵、离线门禁和失败日志。最终本地门禁223项测试、8例doctest、5/5定向变异通过；docs/evidence/quality_gate.json记录实际命令。 | 配置存在不等于远端已运行；不在CI访问JobsDB或付费AI。 |
| CI-02 / slides 12, 13, 14, 15, 16, 17 | CD、可重复构建、环境安装与日志 | 本轮已补齐 | `.github/workflows/tests.yml`；`scripts/package_project.py`；`scripts/quality_gate.py:package_report`。delivery任务依赖矩阵全部通过，构建并检查同一源码ZIP后上传Actionsartifact；包检查有16项回归用例。最终本地包结构/CRC/排除项验证通过，远端执行仍未证实。 | 本地应用采取持续交付ZIP，没有自动部署公网服务；实际GitHubartifact仍需成功远端run。 |
| CI-03 / slides 18, 19, 20, 21 | 分支/PR、远端检查、失败日志和合并前验证 | 范围/学生操作 | `.github/workflows/tests.yml`。需将源码和workflow置于远端仓库根目录，再记录真实run链接/commit。 | 若GitHub只含ZIP，压缩包内workflow不会执行；远端运行和PR是否完成必须单独核实。 |

### L10 · Lecture10 Code with Quality  Modern Code Review_v2.pptx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| REVIEW-01 / slides 3, 4, 5, 6, 7, 8 | 独立代码审查、缺陷/替代设计/知识交流 | 本轮已补齐 | `docs/COURSE_COVERAGE.md (v1.3 AI复核记录)`；`jobcompass/learning.py`；`jobcompass/storage.py`；`tests/test_history.py`；`tests/test_learning.py`。课程审计AI代理在实现后只读复核学习图、分母、demo/过期边界、深拷贝和事务历史；未发现正常API路径的阻断性问题。 | 这是披露身份的AI复核，不是同学评审或第三方安全认证；真实独立学生评审记录仍留空。 |
| REVIEW-02 / slides 9, 10, 11, 12 | 作者走读、审查者理解代码与讨论 | 范围/学生操作 | `docs/DEMO_SCRIPT.md`。可用简历评分或研究分母做实际代码走读。 | 成员本人尚需进行讲解、提问和记录；不虚构时长/出席/签字。 |
| REVIEW-03 / slides 13, 14, 15, 16 | 正式检查、角色、控制/数据流/I/O/参数/返回/注释清单 | 本轮已补齐 | `docs/QUALITY_WORKFLOW.md`；`.github/pull_request_template.md`。提供author/moderator/三类reviewer角色、逻辑/控制流/I-O/维护检查项及留空评审记录。 | 流程与模板已提供，人员、日期、发现与签字必须等真实独立评审后填写。 |
| REVIEW-04 / slides 17, 18, 19, 20, 21, 22, 23, 24, 25 | 现代代码审查、变更diff、PR评论与AI评论 | 本轮已补齐 | `.github/pull_request_template.md`；`.github/ISSUE_TEMPLATE/bug_report.md`；`docs/QUALITY_WORKFLOW.md`。要求面向变更diff、关联需求与回归证据、回复发现和复审；AI生成实现/审查须披露。 | 未把模板视为已创建PR、已请求Copilot或已完成同学评审。 |

### T5 · Tutorial 5 Write Tests before Implementations.docx

| 编号 / 来源 | 课程主题 | 状态 | 项目证据与验证 | 边界 / 后续工作 |
|---|---|---|---|---|
| T5-01 / t0–t3 | Python/VSCode/VeriVibe VSIX安装、工作区和练习 | 范围/学生操作 | `docs/COURSE_COVERAGE.md`。说明仓库不依赖VeriVibe运行，成员可用其完成老师练习。 | 未安装VSIX；外部插件安装不等于项目功能，也不能宣称已完成。 |
| T5-02 / t4–t6 | 先写带精确输出的doctest，再实现，再运行 | 本轮已补齐 | `scripts/quality_gate.py:archive_relative`；`docs/evidence/tdd_doctest_red.txt`；`docs/evidence/tdd_doctest_green.txt`。新增archive_relative先写4个doctest与stub，实际RED为4失败；实现后与已有4例合计8/8通过。 | 这是本轮真实doctest-first子功能，不追溯声明全项目TDD；学生仍须亲自在VeriVibe侧栏完成老师指定练习。 |

## 演示与评估建议

1. 用同一份虚构简历演示解析、技能集合、加权评分、地区过滤和CSV导出，说明None与零分的区别。
2. 用JobsDB平台更新展示后台任务、限额、取消和失败保留；真实联网是否成功单独记录。
3. 用研究工作台展示只读原始库、筛选口径、分母、去重敏感性和冻结时间窗口；不能把全文提及当真实技能要求。
4. 用一条中文命令生成受限JSON计划，再展示校验、确定性执行、结果表和AI叙述边界；展示1–4轮受限代理的步骤轨迹、聚合观察和预算停止条件；区分逻辑轮与底层HTTP重试。
5. 展示一个真实新增函数的RED/GREEN、doctest、失败复现及修复，再说明CI日志与构建包。
6. 让成员从技术债清单选择一项解释成本/风险/偿还办法，并亲自进行一次小范围代码走读和独立审查。

## 不能由自动化替代的完成项

- 五位成员的学号、真实分工、亲自测试与学习反思。
- 课堂展示、视频录制、同伴提问和真实同行评审签字。
- Moodle最新要求核对、问卷与正式提交。
- GitHub远端CI结果、PR审查和联网API成功的独立证据；本地文件不证明这些已完成。

## v1.3 AI 复核记录

2026-11-18，课程审计代理对另一代理/主代理新增的 `learning.py`、`storage.py` 历史栈、对应 HTTP/UI 接入和测试进行了只读复核。检查重点是：技能按去重岗位计数且包括未识别技能的分母；真实/演示混合时不误回退；过期状态由服务层重算；先修图循环检测与不可变缓存；撤销/重做原子事务、无变化保存不删除重做、历史上限和重启保留。未在正常 API 使用路径发现阻断性问题。该结论限于所读代码与已有验证，不能证明不存在其他缺陷。

另外检查了排名缓存的完整输入指纹、返回值隔离和并发锁；建议清除简历时同步释放缓存中的派生匹配数据，主代理已在 `/api/resume/clear` 接入 `ranking_cache.clear()`。此建议属于数据生命周期改善，不是已发生的数据泄露报告。前 N 项技能统计包含已知技能，缺口数仅针对展示行，已在学习模块文档说明。

该复核由 AI 完成，未代表任何小组成员签字。学生仍须独立走读和提问，填写实际发现与复核结果。没有把模板或本记录冒充真人同行评审。

## 维护此清单

实现完成后同时更新Markdown和JSON：把对应 `implementation_pending` 改为 `implemented`，填入实际文件/符号和验证日志路径；保留范围边界。若仍未实现，继续保留待补标记。不要根据计划或愿望修改状态，也不要用总测试数替代逐需求证据。
