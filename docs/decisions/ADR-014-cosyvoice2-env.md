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
