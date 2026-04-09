## [ERR-20260410-001] pytest

**Logged**: 2026-04-10T00:29:57.4305936+08:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
PowerShell 环境中直接执行 `pytest` 失败，因为命令未加入 PATH。

### Error
```text
pytest : The term 'pytest' is not recognized as the name of a cmdlet, function, script file, or operable program.
```

### Context
- Command/operation attempted: `pytest`
- Input or parameters used: 在 `backend/` 目录直接执行测试
- Environment details: 项目使用本地虚拟环境 `.venv`，但当前会话未将 `pytest` 暴露到全局 PATH

### Suggested Fix
优先使用项目虚拟环境解释器执行测试，例如 `..\\.venv\\Scripts\\python.exe -m pytest`，避免依赖全局 PATH。

### Metadata
- Reproducible: yes
- Related Files: D:\Project\个人项目\股票分析\backend

### Resolution
- **Resolved**: 2026-04-10T00:31:10+08:00
- **Commit/PR**: N/A
- **Notes**: 改用 `..\\.venv\\Scripts\\python.exe -m pytest` 成功执行测试，后续在该项目中优先使用虚拟环境解释器运行 pytest。

---
