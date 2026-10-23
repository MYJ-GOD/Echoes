# ADR-014: CosyVoice2 搬运的环境与 vendored 决策

日期：2026-10-22　状态：已采纳　关联：15.1 / 7.1 / 7.3 / ADR-011

## 问题

CosyVoice2（0.5B 级 TTS）搬进 sidecar 的环境形态三问：裸装 or Docker？pynini 依赖链在 Windows 的处置？vendored 范围与 torch 版本锚点如何与 15.1 兼容？

## 侦察证据（上游 FunAudioLLM/CosyVoice，main HEAD `074ca6d` 2026-05-26）

AST 全包扫描 + 消费子树精扫（数据点）：

1. **pynini/WeTextProcessing/pyopencc 在整个 `cosyvoice/` 包内零命中**——上游 2026-05 已把文本正则化换成 `regex`+`inflect`+`wetext`+自写规则。Windows pip 装不上的历史痛点（WeTextProcessing #328、index-tts #28 等）对本项目**已不存在**。
2. **`ttsfrd`（阿里闭源前端，modelscope 发布）为 try/except 可选优化**：初始化需要 `pretrained_models/CosyVoice-ttsfrd/resource` 权重目录；缺省走 fallback 前端（wetext/inflect）。本决策**不下载 ttsfrd 资源**（checksum 面外、闭源轮子、fallback 够用）——7.3 权重下载边界内只拉主模型。
3. **`vllm` 仅在 vllm serving 分支**（`online_feature` 条件内）；`tensorrt` 仅在 `load_trt` 加速路径函数体局部 import——推理主链不触。
4. **`third_party/Matcha-TTS` 是 v2 推理主路硬依赖**：`flow/decoder.py`、`flow/flow_matching.py`、`hifigan/hifigan.py` 直接 `from matcha... import`（上游靠 example 层 `sys.path.append` 加载，cosyvoice 包内零 sys.path 注入）。matcha 消费面仅 3 组件 + hifigan：`conformer/diffusers/einops/torch` 为其第三方 import 面。
5. `deepspeed×/tensorboard/gradio/fastapi/grpcio/pyarrow/pyworld/librosa×` 只在训练/webui/数据管线文件出现，不在 inference import 闭包。

## 决策

1. **环境形态：Windows 裸装 + uv 项目锁（15.1 遵循）**。Docker/WSL 不进基准与交付；仅可作为替代路线评估期的临时 playground，产出不进 tier_matrix（其 GPU/延迟/显存行为与交付形态不同源）。
2. **pynini 处置预案作废**：无需 conda-forge pynini 特例、无需 `--no-deps` 裁剪——纯 uv 裸路径直接成立（ADR-011 相关探讨弧线就此收束）。
3. **vendored 范围**（= 2, 两处源码，走 12.2 登记）：
   - `cosyvoice/` 包 ← main `074ca6d`
   - `third_party/Matcha-TTS` 子模块 pin ← parent gitlink `dd9105b3`（非 matcha 仓 HEAD；以 parent pin 为准才是上游测试面）
   - 落位 `sidecar/vendor/cosyvoice2/`（上源样代码 + license 文件），sidecar boot 注入 `sys.path`（等价上游 example 惯例）；vendored 目录加入 ruff/mypy/import-linter 排除（上游 vanilla 不改，不参与本仓契约）。
4. **依赖子集而非上游 requirements 全集**：torch/torchaudio（版本见 6）、onnxruntime（win32 wheel）、numpy/scipy、hyperpyyaml+omegaconf、transformers、tiktoken、conformer、diffusers、einops、x-transformers、inflect/regex/wetext、modelscope、tqdm、openai-whisper（== 锁）。训练/部署面（deepspeed、tensorboard、gradio、fastapi、grpcio、pyarrow、pyworld、librosa、vllm、tensorrt）**不进 sidecar venv**；缺失面由运行时 `import` 冒烟显式揭出补齐（报错而非降级）。
5. **torch 版本决策**：先试 **torch 2.7.x + cu126**（满足 15.1 「CUDA 12.6 轮子」字面）；若 vendored 代码在 2.7 冒烟失败则回退上游 requirements 锚 `torch==2.3.1+cu121`，并按 12.2 修订 15.1 行。cosyvoice inference 的 torch API 面（SDPA/matmul/conv）在 2.3→2.7 语义稳定，风险可控。
6. **权重下载（7.3 边界内）**：modelscope（国内通路，`iic/CosyVoice2-0.5B`）运行时下载，不进安装器（ADR-011 同弧线）；HF mirror fallback（hf-mirror）作侧路。

## 后续验收

- vendored 完成后入库 commit 必须与本章 hash 至一一对应可回溯（源码 per-file 与上游 diff = 0）。
- 首装冒烟：`import cosyvoice.cli.cosyvoice` + CosyVoice2 类实例化（权重下载后）延迟/显存实测回填 tier_matrix。
- 三件失败不降级原则贯穿：权重下载失败、模块缺失、CUDA 装载失败均必爆 error（3.4.1 语义）。

## 实施修订记录（12.2 同步）

2026-10-22 实施第一笔（vendored `ca869fb` + uv 迁移）中探明并修订：

1. **Python 锚 3.11.x → 3.13.x**：仓库既有 venv 实为 miniconda base 3.13.5——15.1 的 3.11 是纸面锚；92 tests / heavy 冒烟的全部真机证据链出自该解释器，torch 2.7.x 官方 cp313 轮子在位。pyproject 收紧 `requires-python = ">=3.13"`、mypy `python_version = "3.13"`；15.1 Python 行同步。
2. **onnxruntime 1.18.0 → 1.31.0**：上游锚无 cp313 轮子；CosyVoice 使用面仅 `InferenceSession`（speech tokenizer），高版本向前兼容。
3. **openai-whisper 20231117 → 20250625**：20231117 的 setup.py 在 py3.13 下 build 必炸——PEP 667 的 `locals()` 独立快照使 `exec()` 后 `locals()["__version__"]` 取值 KeyError；sdist 里 `whisper/version.py` 存在，病灶在 setup.py 本身；20250625 已修。
4. **tiktoken 补声明（==0.14.0）**：上游 requirements 漏声明而 `cosyvoice/tokenizer` 代码必需。
5. **whisper build env 补丁**：uv `tool.uv.extra-build-dependencies: openai-whisper = ["setuptools<81"]`——setuptools ≥81 移除 pkg_resources 模块，whisper setup.py 顶层 import 它。
6. **uv 状态**：`uv.lock`（104 packages）随仓库入库；venv = `sidecar/.venv`（直引 miniconda base 3.13.5）+ `.python-version = 3.13`；默认 index 走国内镜像（UV_DEFAULT_INDEX 注入），torch 单独经 `tool.uv.sources` 显式映射 pytorch-cu126 官方源。

2026-10-22 冒烟轮补充修订（首跑实测揭出）：

7. **onnxruntime CPU → onnxruntime-gpu==1.22.0**：CPU 版无 CUDA EP，flow/tokenizer 面 RTF 卡 2.1-2.5；1.31.0 是 CUDA 13 build（依赖 cublasLt64_13.dll），与 torch 2.7.1+cu126 生态错配必然静默 fallback；1.22.0 为 CUDA 12 era 终版，经 `os.add_dll_directory(torch/lib)` 注入 torch 自带 cudnn/cublas DLL 后 CUDA EP 激活。**该 DLL 注入是 sidecar boot 的必备动作**（已入 gpu_smoke.py，引擎落位时固化）。
8. **依赖子集补缺口（matcha 包级触发链侦察盲区）**：`matcha.utils.__init__` 的聚合 import 以及 `cosyvoice2.yaml` 的 `!name` 例化面把以下训练面依赖带回运行时链——`hydra-core==1.3.2`、`lightning==2.2.4`（pytorch-lightning 2.6.6 随 wheel）、`gdown==5.1.0`、`wget==3.2`、`matplotlib`（3.7.5 无 cp313 轮子，升最新）、`librosa==0.10.2`、`pyarrow==18.1.0`、`pyworld`（0.3.4 无 cp313，升 **0.3.5**）——另 `scipy==1.18.1`（hifigan 顶层）、`setuptools<81`（运行时需 pkg_resources，uv venv 默认无 setuptools 且 ≥81 已剥离该模块）。
9. **wetext fst 数据的首次联网面**：wetext 首跑经 modelscope SDK 拉取 fst 正则化数据（`pengzhendong/wetext`，落 `~/.cache/modelscope/hub/`）——一次性预取后离线可用；**部署面必须由 7.3 模型管理器 bootstrap 预取**（离线红线 ①：首次联网缺口在，运行期不能触发）。
10. **wetext 运行期零网深化（spawn 冒烟假死实证）**：L3 端到端 spawn 冒烟中 `CosyVoiceFrontEnd` 构造 100% 卡死 >300s。受控单变量探针定位：wetext 构造走 `snapshot_download` **联网路径**（非 local_files_only）——modelscope 1.20 匿名 API 限频 403（错误体「请求太频繁」），且在 `stdin=PIPE` 的 spawn 进程形态下重试级联放大成载入期假死（PIPE 50.2s 才退 / DEVNULL 10s 硬炸，直跑形态近秒过——纯环境态差异）。另 vendored frontend 裸 `except` 会把 Normalizer 构造失败吞成 silent no-frontend 文本面（正则化无声消失，违 3.4.1）。**运行时对策（引擎侧，不动 vendored）**：载入时把 wetext `snapshot_download` 钉成 `local_files_only=True`（modelscope 1.20 语义=零网络读缓存）+ 四个 en/zh tn fst **预校验**（缺件 = boot 显式报错 MODEL_NOT_LOADED，补齐归属修订 9 的 bootstrap）；缓存缺件即直跑态也不可靠，预校验双保险覆盖。
11. **主线程预热（loader-lock × OpenBLAS 死锁规避）**：修订 10 修复后 L3 仍偶发假死且卡点更早——faulthandler 栈锁定：**非主线程首次初始化 OpenBLAS 家族 C 扩展（numpy/scipy）** 时，若进程内存在其它阻塞线程（stdin reader），`LoadLibrary` loader lock 与扩展线程池初始化可互锁（`create_module` 处悬挂；受控实验：主线程预载 numpy + reader 默认池的组合稳定通关，worker 首次初始化组合稳定挂死）。对策（组合根，不动 4.5 契约）：首发 hello/booting/ready 写出后、gate 任务创建前，**主线程同步预热真实引擎依赖链**——新 `preload()`：numpy/scipy/torch/wetext/vendored cosyvoice 全 import + CUDA context 建立（Whisper 同款 import 面）；warmup worker 只做权重物化（torch.load，不再触发 C 扩展初始化）。mock 形态零成本；预热失败只记 stderr（warmup 报错不降级链保底，3.4.1）。**L3 端到端复验**：`create_subprocess_exec` + stdin=PIPE 形态 t≈19s 第二发 hello tts:true、t≈26s turn SUCCESS（WS 0x02 三帧 seq 单调、末帧 is_final）——R20 记录。
