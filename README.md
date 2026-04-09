# A股 LLM 股票分析网站

基于 `FastAPI + Vue 3 + TypeScript` 的本地优先 A 股智能分析后台。当前版本已完成项目骨架、核心页面壳子、本地配置读写、分析任务与同步任务 API、历史记录与日志展示的基础能力。

## 目录结构

```text
.
├─ backend/                # FastAPI 后端
├─ config/                 # 本机配置文件
├─ data/                   # SQLite / DuckDB 运行数据
├─ docs/                   # 产品与研发文档
└─ frontend/               # Vue 3 前端
```

## 后端启动

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --app-dir backend
```

后端默认地址：`http://127.0.0.1:8000`

## 前端启动

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:5173`

## 当前已搭建内容

- 左侧固定菜单 + 右侧工作区布局
- 单股分析页与分析提交表单
- 历史分析记录页与报告详情预览
- 系统设置页与本地 TOML 配置读写
- 日志页与任务日志列表
- 数据源状态页与手动同步任务入口
- SQLite 持久化任务、报告、日志、同步作业
- 模拟分析引擎与后台异步任务处理

## 下一步建议

- 接入真实的 Tushare / AKShare / BaoStock 适配器
- 将模拟分析引擎替换为真实多 Agent 编排
- 引入 DuckDB 历史行情仓和标准化同步管道
- 为报告页接入真实行情与财务数据图表
