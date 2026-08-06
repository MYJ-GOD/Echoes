# models/ 模型与声音数据说明

> ⚠️ 本目录**不纳入版本控制**，所有内容需要你手动准备。
> 其中包含私人语音数据（生物特征），请勿上传到任何公开仓库或网盘。

## 目录结构

| 目录 | 内容 | 来源 |
|---|---|---|
| `cosyvoice2-0.5b/` | CosyVoice2 语音合成模型权重（约 4.8GB） | 需要下载，见下方 |
| `voice_refs/` | 语音克隆参考音频 `.wav` + 声音特征 `.pt` | 本地私人数据 |
| `storage/` | 运行时生成的声音嵌入 / 声音模型 | 本地私人数据 |
| `tmp/` | 运行时临时文件 | 自动生成 |

## 下载 CosyVoice2 权重

创建目录并下载模型（二选一）：

```bash
mkdir -p models/cosyvoice2-0.5b
```

**ModelScope**（国内推荐，速度快）：

```bash
git lfs install
git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git models/cosyvoice2-0.5b
```

**Hugging Face**：

```bash
git lfs install
git clone https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B models/cosyvoice2-0.5b
```

## 配套第三方源码

`Echoes_Backend/third_party/CosyVoice` 同样不入仓，需要单独 clone：

```bash
mkdir -p Echoes_Backend/third_party
git clone https://github.com/FunAudioLLM/CosyVoice.git Echoes_Backend/third_party/CosyVoice
```

> 环境变量 `ECHOES_MODELS_DIR`（默认 `D:\Echoes\models`）和
> `COSYVOICE_REPO_DIR`（默认 `.../third_party/CosyVoice`）指向上述两个目录。
