# A股 LLM 股票分析网站 MVP 开发计划完整说明

## 1. 项目概述
本项目目标是开发一个基于 LLM 的 A 股股票行情分析网站。用户输入股票代码后，系统结合本地历史数据、实时行情、财务数据、新闻公告和大盘/板块信息，调用多个 AI Agent 分角色分析，并由总结 Agent 输出辅助决策型结论。

项目定位：
- 单用户 MVP
- 本机运行
- 面向 A 股单股分析
- 输出辅助决策结论，不构成投资建议

## 2. 建设目标
### 2.1 业务目标
- 建立单股智能分析闭环
- 建立本地化数据同步与管理能力
- 建立分析结果留存、回看和日志追踪能力
- 为后续迭代的多股对比、自选池、自动同步预留架构空间

### 2.2 成功标准
| 指标 | 成功标准 |
| --- | --- |
| 单次分析成功率 | >= 85% |
| 报告生成时间 | 快速档 <= 2 分钟，标准档 <= 5 分钟，深度档 <= 8 分钟 |
| 历史报告可追溯性 | 100% 可查看任务、Agent 报告、提示词快照、日志 |
| 数据源可用性校验 | 支持 Tushare、AKShare、BaoStock 连接测试 |
| 手动同步能力 | 支持基本信息、历史数据、财务数据、新闻数据手动同步 |

## 3. 产品范围
### 3.1 本期范围
- 左侧固定菜单 + 右侧内容区布局
- 单股分析
- 历史分析记录
- 系统设置
- 日志查看
- 数据源管理
- 多 Agent 并行分析
- 本地数据仓与本地配置文件
- 手动同步任务与同步日志

### 3.2 本期不做
- 用户登录与权限
- 多人协作
- 自动定时同步
- 股票组合分析
- 自选股管理
- 回测
- 策略交易
- 报告导出 PDF
- 推送通知

## 4. 页面与模块设计
### 4.1 页面结构
左侧固定菜单：
- 单股分析
- 历史分析记录
- 系统设置
- 日志
- 数据源

右侧内容区：
- 根据当前菜单显示对应页面内容
- 页面切换不影响左侧菜单结构
- 任务详情和报告详情在右侧主区域内展开

### 4.2 模块说明
#### 单股分析
- 输入股票代码
- 选择分析深度：快速 / 标准 / 深度
- 选择分析团队角色：
  - 市场分析师
  - 基本面分析师
  - 新闻分析师
  - 大盘分析师
  - 板块分析师
- 点击“开始智能分析”后进入分析队列
- 排队完成后开始取数、分发 Agent、汇总总结、落库并展示报告

#### 历史分析记录
- 显示历史任务列表
- 支持按股票代码、时间范围、状态筛选
- 查看最终报告和各 Agent 子报告
- 查看任务日志、提示词快照、数据摘要

#### 系统设置
- 数据源配置：Tushare、AKShare、BaoStock
- 大模型连接配置：OpenAI、Anthropic
- 提示词模板配置：5 个角色 Prompt + 1 个总结 Prompt
- 配置存储到本机 `config/local_settings.toml`

#### 日志
- 操作日志
- 系统日志
- 支持按任务 ID、模块、级别、时间范围筛选

#### 数据源
- 数据源状态校验
- 基本信息同步
- 历史数据同步
- 财务数据同步
- 新闻数据同步
- 所有同步均为手动触发

## 5. 核心业务流程
### 5.1 分析流程
1. 用户提交单股分析任务
2. 系统写入分析队列
3. Worker 按顺序取任务
4. 按分析深度拼装数据包
5. 优先从本地库读取数据，缺口再实时补拉
6. 将不同数据包发送给不同角色 Agent
7. 各 Agent 返回结构化结果
8. 总结 Agent 汇总结果生成最终结论
9. 保存任务、子报告、总结报告、日志、提示词快照
10. 页面展示结构化分析报告

### 5.2 数据同步流程
1. 用户在数据源页面选择同步类型
2. 系统校验配置与参数
3. 写入同步队列
4. Worker 执行对应同步任务
5. 数据标准化后写入本地 DuckDB
6. 记录同步日志与结果摘要

## 6. 技术架构
| 层级 | 技术选型 | 作用 |
| --- | --- | --- |
| 前端 | Vue3 + TypeScript + Vite + Pinia + Element Plus + ECharts | 页面展示、状态管理、图表、配置操作 |
| 后端 API | FastAPI | 提供 REST API、配置管理、任务查询 |
| 后台任务 | FastAPI Worker / 独立进程 | 分析队列、同步队列、Agent 调度 |
| 元数据存储 | SQLite | 任务、报告、日志、快照 |
| 数据仓 | DuckDB | 行情、财务、新闻、公告、指数、板块 |
| 配置文件 | TOML | 本机密钥和连接配置 |
| 数据源适配层 | Tushare / AKShare / BaoStock Adapter | 屏蔽多源差异 |
| 模型适配层 | OpenAI / Anthropic Adapter | LLM 调用统一封装 |

## 7. 数据与接口设计
### 7.1 核心数据表
SQLite：
- analysis_tasks
- analysis_agent_runs
- analysis_reports
- sync_jobs
- prompt_snapshots
- operation_logs
- system_logs

DuckDB：
- symbol_master
- company_profile
- daily_quotes
- realtime_quote_cache
- financial_reports
- news_items
- announcements
- index_daily
- sector_daily

### 7.2 核心接口
- `POST /api/analysis/tasks`
- `GET /api/analysis/tasks`
- `GET /api/analysis/tasks/{id}`
- `GET /api/analysis/tasks/{id}/report`
- `POST /api/sync/jobs`
- `GET /api/sync/jobs`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/settings/test-connection`
- `GET /api/logs`
- `GET /api/data-sources/status`

## 8. 关键规则
### 8.1 分析深度规则
- 快速：60 个交易日行情 + 最近 1 期财务摘要 + 最近 10 条新闻公告
- 标准：180 个交易日行情 + 12 个季度财务摘要 + 最近 30 条新闻公告
- 深度：365 个交易日行情 + 5 年年报与 12 个季度财务 + 最近 50 条新闻公告 + 一次总结复核

### 8.2 数据源策略
- 按系统设置优先级自动选主源
- 主源失败自动回退备源
- 数据源不支持某类数据时直接跳过
- 优先本地库，缺失或过期再补拉

### 8.3 任务状态规则
- queued
- running
- completed
- completed_with_warnings
- failed
- cancelled

## 9. 开发阶段规划
| 阶段 | 周期 | 目标产出 | 截至 2026-04-09 完成度 |
| --- | --- | --- | --- |
| 阶段 0 | 3 天 | 项目初始化、目录规划、接口约定、基础 UI 框架 | ✅ 100% — 目录骨架、接口草案、基础路由布局全部完成 |
| 阶段 1 | 5 天 | 系统设置页、配置读写、本地配置文件能力 | ✅ 100% — 3 Tab 设置页、TOML 读写、连接测试入口均已交付 |
| 阶段 2 | 6 天 | 数据源适配器、手动同步、DuckDB 基础数据仓 | ⏳ ~50% — DuckDB 10 表+upsert 已建，同步闭环已通（fixture 数据），真实适配器未实现 |
| 阶段 3 | 7 天 | 分析任务队列、Worker、Agent 编排、Prompt 快照 | ⏳ ~40% — 队列状态机+Worker+报告落库闭环已通（模拟引擎），LLM 编排未实现 |
| 阶段 4 | 5 天 | 报告页、历史记录、日志查询、图表展示 | ✅ 100%（UI 层） — 报告仪表板、历史详情、日志筛选三页完整，待填充真实数据 |
| 阶段 5 | 4 天 | 联调、测试、异常处理、发布说明 | ❌ 未开始 |

## 10. 项目审计与改进建议（2026-04-09）

基于对后端 ~1800 行 Python 和前端 ~1200 行 TypeScript/Vue 代码的全量审计，总结以下发现和建议。

### 10.1 架构层优化（建议纳入 v0.1.0）

| 编号 | 问题 | 当前现状 | 建议方案 |
| --- | --- | --- | --- |
| A-01 | 缺少全局异常处理 | `main.py` 无 `exception_handler`，未捕获异常返回 500 裸响应 | 添加 FastAPI `@app.exception_handler(Exception)` 返回统一 JSON 格式 `{code, message, detail}` |
| A-02 | CORS 过于开放 | `allow_origins=["*"]` | 限制为 `["http://127.0.0.1:5173", "http://localhost:5173"]` |
| A-03 | SQLite 并发写入风险 | 默认 journal 模式，多个 BackgroundTasks 可能锁冲突 | `database.py` 初始化时执行 `PRAGMA journal_mode=WAL` |
| A-04 | DuckDB 连接无复用 | `market_store.py` 每次操作 `duckdb.connect()` | 引入 `@contextmanager` 上下文管理器，单进程内复用连接 |
| A-05 | 配置缓存不刷新 | `load_settings()` 仅 `on_startup` 调用，PUT 后进程内仍为旧值 | `PUT /api/settings` 成功后调用 `reload_settings()` 刷新模块级缓存 |
| A-06 | 任务无超时保护 | `process_analysis_task` / `process_sync_job` 无 timeout | 包裹 `asyncio.wait_for(..., timeout=300)` 并在超时时标记 failed |

### 10.2 后端代码质量（建议纳入 v0.1.0）

| 编号 | 问题 | 建议 |
| --- | --- | --- |
| B-01 | 连接测试为硬编码 | `test_connection` 对 LLM 返回 `True`，应改为对 `base_url` 发 HEAD 请求验证可达性 |
| B-02 | DuckDB 缺查询函数 | 补齐面向分析引擎的读取函数：`get_daily_quotes(symbol, days)` / `get_financials(symbol, quarters)` / `get_news(symbol, count)` |
| B-03 | 股票代码后端校验不足 | API 层应对 symbol 做 6 位数字 + 可选后缀 (.SH/.SZ) 的正则校验 |
| B-04 | 日志写入同步 | `add_operation_log` / `add_system_log` 为同步 SQLite 写入，高频调用可能拖慢请求，建议使用队列缓冲 |

### 10.3 前端体验优化（v0.1.0 ~ v0.2.0）

| 编号 | 问题 | 建议 |
| --- | --- | --- |
| C-01 | 加载状态缺失 | HistoryView / LogsView / DataSourcesView 加载时无 loading 动画，应添加骨架屏或 `v-loading` |
| C-02 | 轮询请求未取消 | `SingleStockAnalysisView` 的 `pollTimer` 在 `onBeforeUnmount` 清除 interval，但未用 `AbortController` 取消进行中 fetch |
| C-03 | 报告重复加载 | 切换队列任务时重复调用 `getAnalysisReport`，应在组件内用 Map 缓存已加载报告 |
| C-04 | 同步按钮无防重复 | 数据源页连续点击同步按钮可创建重复任务，应加 debounce 或 loading 态 |
| C-05 | Store 利用不足 | workspace store 仅 4 个统计数字，tasks / reports 状态未纳入 Pinia 维护，导致组件间数据不共享 |

### 10.4 扩展建议（建议纳入 v0.2.0 候选）

| 编号 | 建议 | 说明 |
| --- | --- | --- |
| D-01 | 股票代码搜索自动补全 | 输入框增加 from DuckDB `symbol_master` 的自动补全 |
| D-02 | 分析进度可视化 | 展示当前哪个 Agent 正在执行，而非仅显示 `running` |
| D-03 | 提示词版本管理 | `prompt_snapshots` 已有基础，补充 diff 对比和一键回滚 |
| D-04 | 数据质量仪表板 | 数据源页增加各表行数、最新日期、数据覆盖率统计 |
| D-05 | 分析成本预估 | 提交任务前根据深度+角色数预估 token 消耗和费用 |
| D-06 | 页面加载骨架屏 | 列表页加载时显示骨架占位提升感知速度 |
| D-07 | 防重复同步按钮 | 同步按钮点击后进入 loading 态，防止重复提交 |

### 10.5 安全评估摘要

| 风险项 | 当前状态 | 严重度 | 处理建议 |
| --- | --- | --- | --- |
| CORS 全开放 | `allow_origins=["*"]` | 高 | v0.1.0 收紧（A-02） |
| SQL 注入 | 使用参数化查询，风险低 | 低 | 保持现状 |
| 密钥明文存储 | `local_settings.toml` 存储 API Key | 中 | 单机 MVP 可接受，v0.2.0 考虑本地加密 |
| 无速率限制 | 所有 API 无限流 | 中 | 单机 MVP 可接受，v0.2.0 考虑 slowapi |
| 无认证授权 | 无用户认证 | 低 | 单机模式设计意图，v0.3.0 考虑 |

总工期建议：`30 个自然日左右`

## 10. 验收标准
- 菜单和页面结构完整可用
- 单股分析可成功提交、排队、执行、出报告
- 至少支持 2 个 LLM Provider 配置
- 至少支持 3 个数据源连接测试
- 所有 Agent 报告和总结报告可落库回看
- 所有手动同步任务可执行并产生日志
- 历史记录和日志页面能定位到具体任务
- 全站有明确免责声明

## 11. 风险与应对
| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 数据源接口不稳定 | 影响同步与分析 | 主备源回退 + 状态校验 + 失败重试 |
| LLM 输出不稳定 | 报告质量波动 | 固定结构化输出 + Prompt 版本化 + 最终总结校验 |
| 本机环境差异 | 启动失败或依赖冲突 | 明确 Python/Node 版本和启动脚本 |
| 数据标准化复杂 | 多源字段不一致 | 统一标准模型与适配器层 |
| 分析耗时偏长 | 用户体验下降 | 队列可视化 + 深度分级 + 本地缓存 |

## 12. 结论
第一版以“单股分析闭环跑通”为唯一核心目标。只要任务提交、数据拉取、Agent 分析、总结落库、历史回看、日志追踪这 6 个环节完整闭环，就视为 MVP 达标。
