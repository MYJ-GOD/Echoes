# Echoes（桌面重构版）

「双击打开 → 克隆一个声音 → 语音闲聊，它记得你是谁。」

- **唯一执行依据（母文档，含冻结契约与 v1.4 变更记录）**：[docs/architecture.md](docs/architecture.md)
- 仓库结构总览见母文档 §3.3；开发顺序见母文档 §12；提交约定（Conventional Commits）见母文档 §15.4。
- ADR 决策目录：[docs/decisions/](docs/decisions/)；阶段 -1 与阶段 0 基准产物：[docs/benchmarks/](docs/benchmarks/)。

## 快速开始（当前阶段：sidecar 冻结契约骨架）

依赖清单**唯一来源** = `sidecar/pyproject.toml`（`dependencies` + `dev` 组，15.1）；
以下命令与之同步维护。锁定文件（uv.lock）随阶段 0 的 15.1 依赖锁定引入，骨架期不预留。

```powershell
# 仓库根目录
python -m venv .venv
.venv\Scripts\python -m pip install pydantic "websockets>=12,<15" pytest pytest-asyncio ruff mypy import-linter

cd sidecar
..\.venv\Scripts\python -m pytest          # 13.2 契约测试 / 状态机守护 / Transport 一致性
..\.venv\Scripts\ruff check .              # lint（100 列）
..\.venv\Scripts\python -m mypy            # mypy strict（15.3 边界）
..\.venv\Scripts\lint-imports              # 15.2 依赖分层强制
..\.venv\Scripts\python -m echoes_sidecar.main   # 组合根运行（交互 / 管道；见 3.4）
```
