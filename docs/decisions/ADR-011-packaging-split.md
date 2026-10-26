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

## 实施补充：运行时档案（2026-10-26）

**结论**：运行时不是「运行时 pip 解析」，而是**按档位预构建的 zip 档案**（CI/构建机产出），
用户机只做「下载 → 校验 → 解压 → 激活」。理由：冻结进程里跑 pip 依赖解析不可控
（证书、构建隔离、`sys.executable`、断点续传都要另造），而 zip 路径与模型管理器同构。

**目录布局**（`~/.cache/echoes/runtime/`，`ECHOES_RUNTIME_DIR` 可覆盖）：:

    active                      # 当前档位（纯文本）
    <profile>/runtime.json      # 安装清单：python/platform/installed_at/bundle_sha256
    <profile>/site-packages/    # 档案解压结果

**档位**：`cpu`（pytorch/whl/cpu）与 `cuda126`（pytorch/whl/cu126），依赖清单随包
（`echoes_sidecar/runtime_manifest.json`），与 `pyproject.toml` 的重依赖有测试守卫防漂移。

**启动注入**（`echoes_sidecar.runtime.inject()`，组合根 `serve()` 第一句）：

1. 冻结形态（`sys.frozen`）或 `ECHOES_RUNTIME_INJECT=1` 才注入；dev `.venv` 不注入。
2. 档位优先级：`ECHOES_RUNTIME_PROFILE` > `active` 指针 > 唯一已装 > 最近安装。
3. `sys.path.insert(0, site-packages)`（必须压过 ONEDIR 自带的 numpy），再
   `importlib.invalidate_caches()`，最后登记 DLL 目录：`site-packages`、`torch/lib`、
   `nvidia/*/bin`、`*.libs`，并前置到 `PATH`（`os.add_dll_directory` 句柄常驻）。
4. Python 主次版本不符则跳过注入并告警（ABI 不兼容），由引擎报 `MODEL_NOT_LOADED`。

**档案约定**：zip 根目录含 `site-packages/`（推荐）或内容即 site-packages；解压前做
zip-slip 校验，装失败不动旧档（`os.replace` 交换 + 回滚），`install` 写完 `active` 指针。

**验证**：单测 20 例（清单/档位/注入/zip-slip/原子换档/sha 失败保留旧档）；冻结 exe
（87.5MB）在有档位时打印 `[runtime] injected profile=…`、无档位时安静跳过。

**未完成**：档案托管地址（`bundles[].url` 仍为空）与真 torch 档位构建，归
「首启引导 + CI」；档案未上传前，`runtime_manager.py install` 会提示用 `--from-bundle`。

另外补上了一处冻结缺件：vendored `cosyvoice2` 源码此前没进 ONEDIR，而
`_ensure_vendor_boot()` 按 `_MEIPASS/vendor/cosyvoice2` 解析——现在随包（2.1MB），
否则即便装上 torch，真 TTS 也会在 `import cosyvoice` 处失败。

## 实施补充：档案构建与冻结踩坑（2026-10-26）

**档案怎么来**：`sidecar/scripts/build_runtime_bundle.py`

1. 从 `runtime_manifest.json` 取该档 requirements（含 `--index-url`/`--extra-index-url`）；
2. `uv pip install --target <staging>/site-packages`（允许纯 Python sdist：`antlr4-python3-runtime`
   只有源码包；`--index-strategy unsafe-best-match` 让镜像能补主索引缺的版本）；
3. 以 `site-packages/` 为根打 zip，算 sha256，输出可直接回填 manifest 的 JSON。
4. 本机验证：`runtime_manager.py install cpu --url file:///…zip`（`file://` 已支持，
   离线/内网部署同样走这条路）。

**整合与实测**：cpu 档案 **681MB**（解压 2.35GB，116 个包）；`uv` 首次下载约 1 分钟，
打包约 5–6 分钟。装进 `~/.cache/echoes/runtime/cpu` 后，冻结 exe 的 `torch.__file__`
指向该目录；满载（whisper + CosyVoice2 同时加载）时 ASR 70s / TTS 89s 就绪，单独加载
ASR 1s、TTS 23s。

**冻结版三个必踩的坑**（都已修，且只有真跑才现形）：

1. **stdlib 动态 import**：ONEDIR 不含 torch，PyInstaller 看不到 torch 内部的 import。
   实测缺 `timeit` → `pickletools` → `http.cookies`。现在由一次真实 warmup 生成
   `scripts/stdlib_hidden_imports.txt`（271 个模块），构建时统一 `--hidden-import`。
2. **`python3.dll`**：`tokenizers` 这类 `Py_LIMITED_API` 扩展链接的是 `python3.dll`，
   而 PyInstaller 只带 `python313.dll`；dev 有 base Python 的 `python3.dll` 在 PATH 上，
   所以只在安装包现形。构建脚本现在把它 `--add-binary` 进 `_internal`。
3. **PYZ 里的残缺副本会盖住运行时**：PyInstaller 静态分析把 `rich`（经 pydantic/mypy
   钩子）带进 PYZ，但只带被追踪到的模块——`rich.tree` 缺失，CosyVoice2 直接报
   `ModuleNotFoundError`。`sys.path` 插队没用，因为 FrozenImporter 在 `meta_path` 最前。
   处理：① 把纯开发依赖（`rich`/`pygments`/`mypy`）排除出 ONEDIR，`rich` 改为运行时
   正经依赖（已进 `pyproject` 与档案）；② 注入时插一个 `_RuntimeFinder`，顶层模块先在
   运行时目录找，找不到再落回包内。

**端到端证据**（冻结 exe + `ECHOES_RUNTIME_DIR` 指向档案解压目录）：

    [runtime] injected profile=cpu site=…\runtime\cpu\site-packages
    [2s]  hello {asr: false, tts: false, llm: true}   # --asr whisper --tts cosyvoice2
    [70s] hello {asr: true,  tts: false, llm: true}
    [89s] hello {asr: true,  tts: true,  llm: true}

**仍未做**：档案托管地址（`bundles[].url` 空）、CUDA 档位实建、CI。
