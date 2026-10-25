# ADR-011：打包分体策略（split-binary）

- 状态：**已定**（2026-10-25；依据阶段 0 PyInstaller 探测）
- 影响范围：阶段 3 打包/分发、模型管理器（7.3）、首启引导、CI（7.2）
- 输入：`docs/benchmarks/probe-pyinstaller.md`（2026-10-22，T-8G 本机）

## 决策

采用 **split-binary**：

1. **安装包内置**
   - Tauri 主程序 + Vue 前端（目标 < 50MB）。
   - Python sidecar 基础运行时：PyInstaller **ONEDIR**，**不含 torch / CUDA / 模型权重**。
   - 实测 mock 形态 ONEDIR **34.9MB / 152 文件**，hello→boot→ready→turn 全链可运行。
2. **运行时下载**
   - torch + CUDA 运行时包（CPU 轮子或 CUDA 轮子，按硬件档位）。
   - ASR / TTS / 嵌入 / LLM 模型权重（含 Ollama 模型复用扫描）。
   - 下载由模型管理器负责：清单、多源、断点续传、sha256、失败换源、缓存扫描（7.3）。
3. **形态**
   - sidecar 用 **ONEDIR**：补丁可热替换单文件、无 onefile 首次解压延迟。
   - onefile 仅作为备选记录（18MB 压缩，但冷启动解压对「点名即语音」不利）。
4. **CI 边界**
   - CI 只跑 CPU 安全面 + schema/transport/状态机；CUDA torch 与真引擎冒烟仍走本机 `gpu_smoke.py`（7.2）。
5. **体积目标**
   - 基础安装包 ≤ **400MB**（母文档 6/阶段 3 v1.3 修正）。
   - torch/CUDA 与模型权重不计入基础包，独立版本化。

## 理由

- 探测显示基础运行时只有 ~35MB；体积大头是 torch（GB 级）与模型（数 GB），塞进安装器会让更新、回滚、下载失败恢复都变差。
- sidecar 与模型解耦后，主程序补丁不需要重下模型；模型换源/换档也不触发安装器重装。
- ONEDIR 的启动路径确定，避免 onefile 解压抖动进入 ADR-012 的冷启动预算。
- 离线红线不变：运行时不联网补救；下载只发生在部署/首启引导，完成后全离线（7.3/16.1）。

## 后果

- 必须实现模型管理器与首启引导（否则干净机装完不可用）。
- 壳侧 spawn 必须解析两种形态：dev `.venv/python -m` 与安装包内 `sidecar/echoes-sidecar.exe`。
- 安装器需要把 sidecar ONEDIR 作为 resource 打入；版本与 sidecar 二进制同源。
- 失败路径要明确：磁盘满/校验失败/下载中断 → 可重试，不静默降级（14.1）。
- 跨平台矩阵按 7.2；Windows 必做，macOS/Linux 可选。

## 备选方案（未采纳）

- **单体安装包（含 torch）**：1.5–2.5GB，更新与回滚成本高；与「主程序小步更新」冲突。
- **onefile sidecar**：体积更小，但首次启动解压延迟不可控；作为备选保留。
- **conda/嵌入式 Python 运行时**：与 ADR-014（uv + miniconda base 3.13）及 15.1 锁口径冲突。

## 后续动作

1. sidecar PyInstaller ONEDIR spec + 构建脚本（mock 优先，真引擎按运行时下载）。
2. 模型清单/manifest + 管理器（多源、sha256、缓存、Ollama 复用）。
3. Tauri bundle resource + spawn 解析 + 首启硬件检测/档位推荐/下载引导。
4. CI 打包矩阵（CPU 面）与安装包体积检查。
