# Echoes-AI — CosyVoice2 TTS/ASR 服务

基于 **CosyVoice2** 的语音合成（TTS）与自动语音识别（ASR）服务，提供声音克隆、多音色语音合成和语音识别能力。

---

## 功能

- **语音合成（TTS）**：支持文本合成、流式合成、零样本声音克隆
- **语音识别（ASR）**：Paraformer 模型，中英文识别
- **声音资产管理**：上传参考音频、查询声音资产（内部接口）

---

## 技术栈

- **TTS 引擎**：CosyVoice2（阿里达摩院 FunAudioLLM 项目）
- **ASR 引擎**：Paraformer（阿里达摩院）
- **Web 框架**：FastAPI + uvicorn
- **异步队列**：asyncio + ThreadPoolExecutor（TTS 计算密集）
- **模型框架**：PyTorch + transformers

---

## 前置准备

### 1. 下载模型权重

CosyVoice2 权重和源码不入仓库，参考 **[../../models/README.md](../../models/README.md)** 下载：
- CosyVoice2 模型权重（~5GB）
- `third_party/CosyVoice` 源码（从 FunAudioLLM 仓库 clone）

### 2. 环境要求

- Python 3.10+
- CUDA 11.8+（推荐，CPU 模式可运行但慢）
- conda 环境管理

---

## 快速启动

### 方式 1：一键启动脚本（Windows 推荐）

```bash
./run_echoes_ai.bat
```

脚本自动：
1. 激活 conda 环境（cosyvoice2）
2. 设置环境变量（模型路径、HF 镜像）
3. 启动 uvicorn 服务（端口 8000）

### 方式 2：手动启动

```bash
# 激活 CosyVoice2 环境
conda activate cosyvoice2

# 设置环境变量（可选）
export HF_HOME=../../models/huggingface
export HF_ENDPOINT=https://hf-mirror.com  # HF 镜像加速

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 首次启动注意

- ASR 模型（Paraformer）首次调用时自动下载（~1GB）
- 可通过 `HF_ENDPOINT` 使用镜像加速

---

## 环境变量配置

复制 `.env.example` 为 `.env` 并配置：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `COSYVOICE_MODEL_DIR` | CosyVoice2 模型权重目录 | `../../models/CosyVoice2-0.5B` |
| `DEFAULT_VOICE_NAME` | 默认音色名称 | `中文女` |
| `HF_HOME` | HuggingFace 模型缓存 | `../../models/huggingface` |
| `HF_ENDPOINT` | HF 镜像地址 | `https://hf-mirror.com` |

---

## API 端点

### 健康检查
```
GET /health
GET /healthz
```

### TTS 语音合成

#### 文本合成（非流式）
```
POST /tts/inference/synthesize-text
Content-Type: application/json

{
  "text": "你好，世界",
  "voice_name": "中文女",
  "speed": 1.0
}
```
响应：`audio/wav` 音频流

#### 流式合成
```
POST /tts/inference/synthesize-stream
Content-Type: application/json

{
  "text": "长文本...",
  "voice_name": "中文女"
}
```
响应：流式音频数据（分块返回）

### 声音资产管理（内部接口）

#### 上传参考音频
```
POST /internal/voice/ref/upload
Content-Type: multipart/form-data

file: <音频文件>
name: "音色名称"
description: "音色描述"
```

#### 查询声音资产
```
GET /internal/voice/ref/{ref_id}
```

### ASR 语音识别（内部接口）
```
POST /internal/voice/asr
Content-Type: multipart/form-data

file: <音频文件>
```

响应：
```json
{
  "text": "识别的文本内容",
  "duration": 2.5
}
```

---

## 目录结构

```
Echoes-AI/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── api/
│   │   ├── tts.py           # TTS 端点（/tts）
│   │   ├── asr.py           # ASR 端点（/internal/voice/asr）
│   │   ├── voice.py         # 声音资产管理（/internal/voice）
│   │   ├── jobs.py          # 任务查询
│   │   └── health.py        # 健康检查
│   ├── deps.py              # 依赖注入
│   └── schemas.py           # Pydantic 数据模型
├── run_echoes_ai.bat        # Windows 启动脚本
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板
└── README.md
```

---

## 依赖安装

CosyVoice2 依赖特殊（需 conda 环境），参考官方仓库：
```bash
# clone CosyVoice 源码到 third_party/
cd ../../third_party
git clone https://github.com/FunAudioLLM/CosyVoice.git

# 创建 conda 环境
cd CosyVoice
conda env create -f environment.yaml
conda activate cosyvoice2

# 安装 Echoes-AI 依赖
cd ../../Echoes_Backend/Echoes-AI
pip install -r requirements.txt
```

---

## 内部服务说明

Echoes-AI 为**内部服务**，通过 `echoes-service-voice` Java 服务调用：
- `/tts/*` 端点：Java 服务直接调用
- `/internal/voice/*` 端点：内部鉴权（需 `X-INTERNAL` header）

外部客户端通过 Gateway → Java 服务 → Echoes-AI 访问，不直接暴露 8000 端口。

---

## 性能优化

- **GPU 加速**：CUDA 11.8+ + PyTorch GPU 版本，TTS 推理提速 5-10x
- **流式合成**：长文本使用 `/inference/synthesize-stream` 降低首字延迟
- **模型量化**：可选 INT8 量化降低显存占用（需手动配置）

---

## 已知限制

1. **CosyVoice2 模型不入仓**：权重文件过大（~5GB），需手动下载
2. **CPU 模式慢**：实时合成需 GPU，CPU 约慢 8-15 倍
3. **声音克隆质量**：受参考音频质量影响，建议使用 16kHz+ 无噪声录音

---

## 常见问题

**Q: 启动报 `No module named 'cosyvoice'`？**  
A: 确认 `third_party/CosyVoice` 已 clone，且 conda 环境已激活。

**Q: TTS 合成速度慢？**  
A: 确认 PyTorch 使用 GPU（`torch.cuda.is_available()` 应返回 `True`）。

**Q: ASR 识别准确率低？**  
A: 确保音频采样率 16kHz，降噪处理，中英文混合场景建议使用专门模型。

---

## License

遵循 CosyVoice 的 Apache-2.0 许可。
