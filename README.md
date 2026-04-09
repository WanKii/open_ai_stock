# A股 LLM 股票分析网站

> **v0.1.0 MVP** — 基于 `FastAPI + Vue 3 + TypeScript` 的本地优先 A 股智能分析系统。

支持多 Agent 并行分析（市场/基本面/新闻/大盘/板块），接入 OpenAI / Anthropic 大模型，无 LLM 配置时自动降级为本地模拟引擎。数据源支持 AKShare / Tushare / BaoStock 真实接口，失败时自动回退 fixture 数据。

## 目录结构

```text
.
├─ backend/                # FastAPI 后端（API + 分析引擎 + 数据同步）
│   ├─ app/api/            # REST API 路由
│   ├─ app/core/           # 配置、数据库、DuckDB 存储
│   ├─ app/services/       # 分析引擎、同步服务、多源适配器、LLM 提供者
│   └─ tests/              # pytest 冒烟测试（38 项）
├─ config/                 # 本机 TOML 配置文件
├─ data/                   # SQLite（元数据） + DuckDB（市场数据）
├─ docs/                   # 产品与研发文档
└─ frontend/               # Vue 3 + Element Plus + ECharts 前端
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 后端

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`  
API 文档：`http://127.0.0.1:8000/docs`

### 前端

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

### 运行测试

```powershell
cd backend
pip install pytest
python -m pytest tests/ -v
```

## 功能概览

| 模块 | 能力 |
|------|------|
| 单股分析 | 股票代码输入、分析深度三档、5 角色多选、任务队列、报告仪表板 |
| 分析引擎 | 多 Agent 并行（OpenAI/Anthropic）、总结 Agent 汇总、无 LLM 自动降级模拟 |
| 数据源 | AKShare/Tushare/BaoStock 真实适配器、优先级回退、连接测试、手动同步 |
| 数据仓 | DuckDB 10 张市场表 + SQLite 7 张元数据表 |
| 历史记录 | 任务列表筛选、报告详情展开、Agent 子报告 |
| 系统设置 | 数据源配置、LLM 连接、Prompt 模板、TOML 持久化、密钥屏蔽 |
| 日志 | 操作日志 + 系统日志、多条件筛选 |
| 安全 | CORS 收紧、全局异常处理、SQLite WAL、任务超时保护（300s） |

## 配置

复制示例配置文件并按需修改：

```powershell
Copy-Item config\local_settings.example.toml config\local_settings.toml
```

配置项说明：
- **数据源**：`data_sources.tushare` / `akshare` / `baostock` — 启用/禁用、Token、优先级
- **大模型**：`llm_providers.openai` / `anthropic` — API Key、模型、超时
- **Prompt**：`prompts.*` — 5 个角色 + 1 个总结 Prompt 模板

> 不配置 LLM 时，系统自动使用模拟引擎生成报告（约 1.2s）。

## 免责声明

本系统输出内容为基于公开数据与模型推理的辅助决策参考，**不构成任何投资建议**。
- 引入 DuckDB 历史行情仓和标准化同步管道
- 为报告页接入真实行情与财务数据图表
