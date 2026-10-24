# Echoes（桌面重构版）

「双击打开 → 克隆一个声音 → 语音闲聊，它记得你是谁。」

- **唯一执行依据（母文档，含冻结契约与 v1.4 变更记录）**：[docs/architecture.md](docs/architecture.md)
- 仓库结构总览见母文档 §3.3；开发顺序见母文档 §12；提交约定（Conventional Commits）见母文档 §15.4。
- ADR 决策目录：[docs/decisions/](docs/decisions/)；阶段 -1 与阶段 0 基准产物：[docs/benchmarks/](docs/benchmarks/)。

## 快速开始（当前阶段：阶段 0 功能完成，阶段 1 进行中）

依赖清单**唯一来源** = `sidecar/pyproject.toml`；锁文件 `sidecar/uv.lock` 入库，依赖变更必须同步更新锁。

> **规范运行环境 = `sidecar/.venv`**（uv 管理，含 torch 2.7.1+cu126 / transformers / sqlite-vec）。
> 仓库根的 `.venv` 是早期骨架测试环境（无 torch），**不要用于真路或四闸复跑**。

```powershell
# 首次 / 依赖变更后（仓库根）
cd sidecar
uv sync --extra dev

# 四闸（cwd = sidecar）
.venv\Scripts\pytest.exe -m "not heavy"
.venv\Scripts\ruff.exe check .
.venv\Scripts\mypy.exe
.venv\Scripts\lint-imports.exe

# sidecar 组合根（mock 全链；真路去掉 mock 参数）
.venv\Scripts\python.exe -m echoes_sidecar.main --llm mock --asr mock --tts mock --ws auto

# 13.3 记忆抽取评测（scripted=管线自检；ollama=真门禁）
.venv\Scripts\python.exe scripts\eval_memory.py --provider scripted

# 壳（仓库根）
$env:ECHOES_SIDECAR_MOCK="1"; npm run tauri dev   # 全 mock
npm run tauri dev                                  # 真路：Ollama + whisper + CosyVoice2
```

记忆默认 `--memory auto`（mock LLM 或 bge 权重缺失时自动关闭）；真门禁需 Ollama + `qwen3:8b`。

进度与剩余工作见 [PROGRESS.md](PROGRESS.md)；阶段 0 验收逐条见 [docs/acceptance/stage0.md](docs/acceptance/stage0.md)。
