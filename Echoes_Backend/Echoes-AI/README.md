# Echoes-AI

CosyVoice2 TTS/ASR 服务。提供语音合成、声音克隆、语音识别。

## 技术

- TTS：CosyVoice2（FunAudioLLM）
- ASR：Paraformer
- 框架：FastAPI + uvicorn

## 启动

```bash
# 一键启动（Windows）
./run_echoes_ai.bat

# 或手动
conda activate cosyvoice2
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 前置

CosyVoice2 权重和源码不入仓，需手动下载：
- 权重：`../../models/CosyVoice2-0.5B`（~5GB）
- 源码：`../../third_party/CosyVoice`

详见 [../../models/README.md](../../models/README.md)。

## 主要端点

- `GET /health` - 健康检查
- `POST /tts/inference/synthesize-text` - 文本合成
- `POST /tts/inference/synthesize-stream` - 流式合成
- `POST /internal/voice/ref/upload` - 上传参考音频
- `POST /internal/voice/asr` - 语音识别

完整端点见代码 `app/api/`。

## 环境变量

复制 `.env.example` 为 `.env`：

| 变量 | 说明 |
|---|---|
| `COSYVOICE_MODEL_DIR` | CosyVoice2 权重路径 |
| `HF_HOME` | HuggingFace 缓存（避免 C 盘） |
| `HF_ENDPOINT` | HF 镜像（可选） |

## 依赖

需先安装 CosyVoice2 conda 环境：

```bash
cd ../../third_party/CosyVoice
conda env create -f environment.yaml
conda activate cosyvoice2

cd ../../Echoes_Backend/Echoes-AI
pip install -r requirements.txt
```
