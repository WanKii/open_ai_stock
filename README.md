# A股 LLM 股票分析网站

> **v0.1.0 MVP**  
> 基于 `FastAPI + Vue 3 + TypeScript` 的本地优先 A 股智能分析系统。  
> 支持多 Agent 并行分析，接入 OpenAI / Anthropic，大模型未配置时可降级为本地模拟分析；数据源支持 AKShare / Tushare / BaoStock。

## 目录结构

```text
.
├─ backend/                # FastAPI 后端（API、分析引擎、同步任务）
│  ├─ app/api/             # REST API
│  ├─ app/core/            # 配置、SQLite、DuckDB
│  ├─ app/services/        # 分析引擎、同步服务、数据源适配器、LLM Provider
│  └─ tests/               # pytest 测试
├─ config/                 # 本地 TOML 配置
├─ data/                   # SQLite 元数据 + DuckDB 市场数据
├─ docs/                   # 产品与研发文档
└─ frontend/               # Vue 3 前端
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+

### 后端启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

推荐启动方式是直接使用项目虚拟环境里的解释器：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8070
```

如果你已经激活了 `.venv`，也可以使用下面这条命令：

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8070
```

说明：

- 不建议直接使用全局 `python`（例如 `C:\Python312\python.exe`）启动。
- 全局解释器可能没有安装 `duckdb` 等依赖，会导致 `/api/stocks` 这类接口报错。

后端地址：`http://127.0.0.1:8070`  
API 文档：`http://127.0.0.1:8070/docs`

### 前端启动

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
| 个股分析 | 股票代码输入、分析深度选择、多角色分析、任务队列、报告展示 |
| 分析引擎 | 多 Agent 并行、总结 Agent 汇总、无 LLM 时自动降级 |
| 数据源 | AKShare / Tushare / BaoStock 适配、连接测试、手动同步 |
| 数据仓 | DuckDB 市场表 + SQLite 元数据表 |
| 历史记录 | 任务列表、报告详情、子 Agent 报告 |
| 系统设置 | 数据源配置、LLM 配置、Prompt 模板、TOML 持久化 |
| 日志 | 操作日志与系统日志查询 |
| 安全 | CORS、全局异常处理、SQLite WAL、任务超时保护 |

## 配置

如需自定义本地配置，可复制示例配置文件：

```powershell
Copy-Item config\local_settings.example.toml config\local_settings.toml
```

主要配置项：

- `data_sources.*`：数据源启用状态、优先级、Token 等
- `llm_providers.*`：模型、API Key、超时等
- `prompts.*`：各分析角色与总结角色的 Prompt 模板

未配置 LLM 时，系统会自动使用本地模拟分析流程。

## 免责声明

本系统输出内容仅作为基于公开数据与模型推理的辅助参考，不构成任何投资建议。
