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
| 阶段 2 | 6 天 | 数据源适配器、手动同步、DuckDB 基础数据仓 | ✅ 100% — AKShare/Tushare/BaoStock 真实适配器已实现，同步闭环支持真实接口+fixture 双路回退 |
| 阶段 3 | 7 天 | 分析任务队列、Worker、Agent 编排、Prompt 快照 | ✅ 100% — 真实 LLM 多 Agent 并行分析引擎（OpenAI/Anthropic）落地，无 LLM 时自动降级模拟引擎 |
| 阶段 4 | 5 天 | 报告页、历史记录、日志查询、图表展示 | ✅ 100%（UI 层） — 报告仪表板、历史详情、日志筛选三页完整，待填充真实数据 |
| 阶段 5 | 4 天 | 联调、测试、异常处理、发布说明 | ✅ 100% — 38 项 pytest 冒烟测试通过、Schema 修复、前端 fetch abort 修复、lifespan 迁移、README/启动指南完善 |

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
---

## 13. 全面代码审计与改进建议（2026-04-10 深度审计）

基于对后端 ~3500 行 Python（含适配器、LLM Provider）和前端 ~2000 行 TypeScript/Vue 代码的逐文件深度审计，按类别、优先级整理以下发现和建议。

### 13.1 后端代码质量问题

#### 严重问题（建议 v0.2.0 立即修复）

| 编号 | 问题 | 文件 | 描述 | 建议方案 |
| --- | --- | --- | --- | --- |
| BE-01 | 新闻查询 N+1 | `market_store.py` | `get_news()` 返回个股+全市场（`__MARKET__`）新闻，数据量膨胀 | 增加 `LIMIT` 参数，按发布时间降序后截断；对 `__MARKET__` 新闻做独立缓存 |
| BE-02 | 队列位置竞态条件 | `repository.py` | `create_task()` 中 `queue_position` 通过 `COUNT(*)` 计算后插入，并发下可能重复 | 使用 `BEGIN IMMEDIATE` 事务或 `INSERT ... SELECT COUNT(*)` 原子化 |
| BE-03 | Tushare Token 全局污染 | `tushare_adapter.py` | `ts.set_token()` 修改全局状态，多实例会互相覆盖 | 改用 `tushare.pro_api(token=...)` 直接传参，避免全局 `set_token` |
| BE-04 | LLM 线程无法终止 | `analysis_engine.py` | `worker.join(timeout=300)` 后若线程仍存活，无法杀死，持续泄漏资源 | 改用 `asyncio.wait_for()` + `httpx.AsyncClient(timeout=...)` 替代线程封装 |
| BE-05 | JSON 提取正则脆弱 | `analysis_engine.py` | `_parse_agent_response()` 用正则匹配 ` ```json...``` `，嵌套 JSON 和格式偏差会失败 | 添加多级回退：先正则提取 → 再直接 `json.loads()` 整体 → 再提取第一个 `{...}` 块 |
| BE-06 | 密钥硬编码在配置文件 | `config/local_settings.toml` | 含真实 Tushare Token 和 API Key，可能被 Git 提交 | 确保 `.gitignore` 包含 `local_settings.toml`，添加环境变量覆盖支持（`TUSHARE_TOKEN`、`OPENAI_API_KEY`） |

#### 中等问题（建议 v0.2.0 ~ v0.3.0）

| 编号 | 问题 | 文件 | 描述 | 建议方案 |
| --- | --- | --- | --- | --- |
| BE-07 | DuckDB TOCTOU 竞态 | `market_store.py` | `_get_shared_connection()` 锁外检查后才加锁创建连接 | 将检查移入锁内，使用 double-check locking 模式 |
| BE-08 | 错误处理过度吞并 | 各适配器 | 所有 `except Exception` 均静默返回空列表，不区分网络错误、授权失败、数据不存在 | 按异常类型分级处理：`ConnectionError` → 报连接失败；`AuthenticationError` → 报 Token 无效 |
| BE-09 | 数据删除无恢复机制 | `stocks.py` | `DELETE /{symbol}/data` 硬删除，无软删除/回收站 | 添加 `deleted_at` 软删除列，或在删除前自动备份到临时表 |
| BE-10 | CSV 导出无 BOM | `stocks.py` | Windows Excel 打开 UTF-8 CSV 中文乱码 | 响应体前追加 UTF-8 BOM（`\xef\xbb\xbf`） |
| BE-11 | 无 API 速率限制 | `main.py` | 所有接口无限流保护 | 引入 `slowapi` 中间件，按 IP 限制（如 60 req/min） |
| BE-12 | 大盘指数硬编码 | `analysis_engine.py` | 沪深300 代码 `000300.SH` 和上证 `000001.SH` 硬编码 | 移入 `config/local_settings.toml` 的 `[analysis]` section，支持用户自定义 |
| BE-13 | 分页大偏移性能差 | `stocks.py` | 使用 `OFFSET` 分页，page 值极大时扫描全表 | 对高页码场景改用 keyset pagination（基于 `trade_date` 游标） |

#### 架构耦合问题

| 编号 | 问题 | 描述 | 建议方案 |
| --- | --- | --- | --- |
| BE-14 | LLM/适配器工厂硬编码 | `_get_llm_provider()` 和 `_create_adapter()` 均用 if-elif 选择实现类 | 改为注册表模式：`LLM_REGISTRY = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}` |
| BE-15 | Agent 类型定义分散 | `schemas.py`、`analysis_engine.py`、`demo_engine.py` 各自定义 Agent 标签 | 统一移入 `models/schemas.py` 的 `AGENT_LABELS` 常量 |
| BE-16 | 数据类型列表重复 | `stocks.py` 的 `_VALID_DATA_TYPES` vs `market_store.py` 的 `_DATA_TYPE_TABLE` | 统一为一处定义，其他模块引用 |
| BE-17 | 无依赖注入 | LLM Provider / Adapter 直接 import + 实例化，Mock 测试困难 | 引入 FastAPI `Depends()` 注入或简单工厂，便于测试替换 |

### 13.2 前端代码质量问题

#### 高优先级（建议 v0.2.0 立即修复）

| 编号 | 问题 | 文件 | 描述 | 建议方案 |
| --- | --- | --- | --- | --- |
| FE-01 | API 错误处理不统一 | `client.ts` | 无法区分 4xx/5xx/网络错误，所有错误均为 `throw new Error(text)` | 引入错误分类：`ApiError`（含 status code）、`NetworkError`、`TimeoutError`，全局拦截并 `ElMessage` |
| FE-02 | SettingsView 空指针 | `SettingsView.vue` | `settings.data_sources` 在 `settings` 为 null 时会报错 | 模板中统一使用 `settings?.data_sources ?? {}` 安全访问 |
| FE-03 | 路由无懒加载 | `router/index.ts` | 所有视图组件同步导入，影响首屏加载 | 改为 `() => import("../views/XXXView.vue")` 动态导入 |
| FE-04 | Element Plus 全量导入 | `main.ts` | `import ElementPlus from "element-plus"` 全量注册，打包体积 ~300KB | 改为按需导入：`import { ElButton, ElTable, ... } from "element-plus"` 配合 `unplugin-vue-components` |
| FE-05 | 缺少 404 路由 | `router/index.ts` | 访问不存在路径无 fallback | 添加 `{ path: "/:pathMatch(.*)*", component: NotFoundView }` |

#### 中等优先级

| 编号 | 问题 | 描述 | 建议方案 |
| --- | --- | --- | --- |
| FE-06 | Store 利用不足 | `workspace store` 仅存储 4 个统计数字，分析任务/日志/数据源状态未纳入 Pinia | 新增 `analysisStore`、`logStore`，实现跨页面数据共享和缓存 |
| FE-07 | 缺少 composables 抽象 | 重复的 `async loadXXX() { loading=true; try{...} finally{loading=false} }` 出现 6+ 次 | 提取 `useAsync(fn)` composable；提取 `usePolling(fn, interval)` composable |
| FE-08 | 常量定义分散 | Agent 标签映射、状态标签映射在多个组件中重复 | 新增 `src/utils/constants.ts` 统一管理 |
| FE-09 | 缺少请求超时控制 | `client.ts` 的 `fetch` 调用无超时限制 | 在 `request()` 中添加 `AbortController` + `setTimeout` 超时取消（默认 30s） |
| FE-10 | SyncJobsDrawer 轮询竞态 | `watch(autoRefresh)` 未同时监听 `props.visible`，visible 变 false 后可能继续轮询 | 改为 `watch([autoRefresh, () => props.visible], ...)` 双重守卫 |

### 13.3 前端样式美化建议

#### 13.3.1 暗色模式支持（建议 v0.2.0）

当前仅支持亮色模式（`color-scheme: light`），建议新增系统跟随暗色模式：

```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a1a;
    --paper: rgba(30, 30, 30, 0.8);
    --ink: #f4ecdf;
    --muted: #aaa;
    --accent: #ff7a3d;
    --border: rgba(255, 255, 255, 0.1);
    --sidebar: linear-gradient(180deg, #0a0a0a, #1a1a1a);
  }
}
```

#### 13.3.2 页面过渡动画（建议 v0.2.0）

当前页面切换无过渡效果，建议在 `App.vue` 的 `<RouterView>` 包裹 `<Transition>`：

```vue
<RouterView v-slot="{ Component }">
  <Transition name="fade-slide" mode="out-in">
    <component :is="Component" />
  </Transition>
</RouterView>
```

对应 CSS：
```css
.fade-slide-enter-active, .fade-slide-leave-active { transition: all 250ms ease; }
.fade-slide-enter-from { opacity: 0; transform: translateX(12px); }
.fade-slide-leave-to { opacity: 0; transform: translateX(-12px); }
```

#### 13.3.3 视觉层级优化（建议 v0.2.0）

当前所有 `.panel` 卡片样式相同，缺少层级区分。建议引入三级面板：

| 层级 | 用途 | 样式特征 |
| --- | --- | --- |
| `.panel--primary` | 主要信息（报告、分析结果） | 不透明白底 + 大阴影 |
| `.panel--secondary` | 辅助信息（列表、历史） | 半透明 + 无阴影 |
| `.panel--tertiary` | 次要信息（侧边统计） | 透明底 + 虚线边框 |

#### 13.3.4 骨架屏加载（建议 v0.2.0）

当前仅使用 Element Plus 的 `v-loading` 遮罩，体验生硬。建议为列表页引入骨架屏（shimmer 动画）：

```css
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}
.skeleton-card {
  height: 80px; border-radius: 16px;
  background: linear-gradient(90deg, #f0f0f0 0%, #fff 50%, #f0f0f0 100%);
  background-size: 1000px 100%;
  animation: shimmer 1.8s infinite;
}
```

#### 13.3.5 微交互增强

| 元素 | 当前状态 | 建议 |
| --- | --- | --- |
| StatusBadge | 静态展示 | 添加 `running` 状态的脉冲动画 `animation: pulse 2s infinite` |
| 导航项 hover | 仅 `translateX(4px)` | 增加背景渐显 + 左侧 accent 色条指示器 |
| 表格行 hover | 无效果 | 添加 `background` 行高亮 + 微弱 `translateY(-1px)` 浮起 |
| 空状态 | 仅文字"暂无数据" | 添加 SVG 插图 + 引导文案 + CTA 按钮 |
| 按钮点击 | 无反馈 | 添加 `transform: scale(0.97)` 按压效果 |
| 图表卡片 | 静态矩形 | hover 时 `box-shadow` 增强 + 轻微放大 |

#### 13.3.6 响应式改进

| 问题 | 当前 | 建议 |
| --- | --- | --- |
| 缺少平板断点 | 三个断点 1440/1180/720px | 增加 768px（iPad）和 1024px（iPad Pro）断点 |
| 小屏侧边栏 | 720px 以下改为 1fr 单列 | 改为 `position: fixed` 抽屉式侧边栏，默认收起 |
| 超大屏幕 | 无上限 | 2560px 以上添加 `max-width` 居中，防止内容过宽 |

#### 13.3.7 可访问性（a11y）

| 问题 | 描述 | 建议 |
| --- | --- | --- |
| 缺少 ARIA | 导航缺 `aria-label`，活动项缺 `aria-current` | `<nav aria-label="主导航">` + `:aria-current="isActive ? 'page' : undefined"` |
| 颜色对比度不足 | `--muted: #53645f` 在浅色背景上对比度 < 4.5:1 | 调深至 `#3d4e49`（WCAG AA 合规） |
| 图表不可访问 | ECharts 图表无文本替代 | 为 PricePulseChart 添加 `aria-label="价格走势图"` + 隐藏数据表 |
| 仅靠颜色区分状态 | StatusBadge 靠颜色标识可用/异常 | 同时使用图标标识：✓ 可用、⚠ 警告、✕ 异常 |
| 键盘导航不完整 | Drawer 无焦点陷阱、无 Escape 关闭 | 使用 Element Plus 内置焦点管理或自定义 `useFocusTrap` |

### 13.4 性能优化建议

| 编号 | 问题 | 影响 | 建议方案 | 目标版本 |
| --- | --- | --- | --- | --- |
| PF-01 | 前端包体积 ~1.2MB（未压缩） | 首屏加载慢 | 路由懒加载 + Element Plus 按需导入 + ECharts tree-shaking | v0.2.0 |
| PF-02 | DuckDB 全量 fetchall | 大数据量时内存溢出 | CSV 导出改用 Arrow streaming；分页查询改用 fetchmany | v0.2.0 |
| PF-03 | 日志/历史列表无虚拟滚动 | 大数据集渲染卡顿 | 长列表引入 `el-table-v2`（Element Plus 虚拟化表格）或 `vue-virtual-scroller` | v0.2.0 |
| PF-04 | SyncJobsDrawer 2s 轮询 | 频率过高，无条件渲染 | 根据任务状态动态调频：running 时 3s，idle 时 10s，completed 时停止 | v0.2.0 |
| PF-05 | SQLite 无索引优化 | 日志/任务查询线性扫描 | 为 `operation_logs(task_id)` / `analysis_tasks(status, created_at)` 添加索引 | v0.2.0 |
| PF-06 | LLM 并发无流控 | 多任务并发时 API 限流 | 引入 `asyncio.Semaphore` 限制同时 LLM 调用数（建议 ≤ 3） | v0.3.0 |

### 13.5 扩展功能建议

| 编号 | 功能 | 描述 | 优先级 | 目标版本 |
| --- | --- | --- | --- | --- |
| EX-01 | SSE/WebSocket 实时推送 | 替代前端轮询，分析任务状态和 Agent 进度实时推送 | P2 | v0.2.0 |
| EX-02 | 多 LLM Provider 并行对比 | 同一分析任务同时调用 OpenAI 和 Anthropic，对比结论差异 | P3 | v0.3.0 |
| EX-03 | 数据源健康监控面板 | 定期探测各数据源连接状态，展示可用性时间线 | P2 | v0.2.0 |
| EX-04 | Prompt Playground | 在线编辑和测试 Prompt，即时预览 LLM 输出效果 | P3 | v0.3.0 |
| EX-05 | 分析报告导出 | 支持导出 Markdown / PDF / HTML 格式的结构化报告 | P2 | v0.2.0 |
| EX-06 | 环境变量覆盖机制 | 支持 `TUSHARE_TOKEN`、`OPENAI_API_KEY` 等环境变量覆盖 TOML 配置 | P1 | v0.2.0 |
| EX-07 | 国际化基础设施 | 前端引入 `vue-i18n`，抽取所有硬编码中文为 locale key | P3 | v0.3.0+ |
| EX-08 | 错误追踪集成 | 后端集成 Sentry 或等价方案，前端异常自动上报 | P3 | v0.3.0+ |

### 13.6 安全加固建议

| 编号 | 问题 | 当前状态 | 严重度 | 建议方案 |
| --- | --- | --- | --- | --- |
| SEC-01 | 密钥存储 | `local_settings.toml` 含明文 API Key | 高 | `.gitignore` 确认含 `local_settings.toml`；支持环境变量覆盖；日志脱敏 |
| SEC-02 | CORS allow_methods | `allow_methods=["*"]` 过宽 | 中 | 收紧为 `["GET", "POST", "PUT", "DELETE", "OPTIONS"]` |
| SEC-03 | 符号输入验证 | `normalize_symbol()` 未校验是否为 6 位数字 | 中 | 添加正则 `^[036]\d{5}(\.(SH\|SZ))?$` 验证 |
| SEC-04 | 日志中密钥泄露 | 异常 traceback 可能含 Token | 中 | 日志 formatter 中增加密钥过滤器 |
| SEC-05 | 无请求体大小限制 | POST 请求无 body size 限制 | 低 | 配置 Uvicorn `--limit-concurrency` 和 FastAPI 中间件限制请求体 |

### 13.7 综合评分

| 维度 | 后端 | 前端 | 综合 |
| --- | --- | --- | --- |
| 架构清晰度 | ⭐⭐⭐⭐ | ⭐⭐⭐☆ | 3.5/5 |
| 代码质量 | ⭐⭐⭐☆ | ⭐⭐⭐⭐ | 3.5/5 |
| 错误处理 | ⭐⭐⭐☆ | ⭐⭐☆☆ | 2.5/5 |
| 可测试性 | ⭐⭐☆☆ | ⭐⭐☆☆ | 2/5 |
| 安全性 | ⭐⭐⭐☆ | ⭐⭐⭐☆ | 3/5 |
| 性能 | ⭐⭐⭐☆ | ⭐⭐☆☆ | 2.5/5 |
| UI/UX 设计 | — | ⭐⭐⭐⭐ | 4/5 |
| 可维护性 | ⭐⭐⭐☆ | ⭐⭐⭐☆ | 3/5 |

**总体结论**：MVP 级别可发布，设计品味优秀。进入 v0.2.0 阶段应重点修复 BE-01~BE-06 和 FE-01~FE-05 的高优问题，同时落地暗色模式、页面过渡、骨架屏等样式提升。