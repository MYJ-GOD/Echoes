# 模型与运行时许可证清单（Echoes v2）

> 适用范围：`sidecar/echoes_sidecar/models/manifest.json` 里随应用安装/推荐下载的模型。
> 本清单是工程记录，不构成法律意见；对外分发前请按目标地区法规与各模型仓库的最新
> LICENSE 复核一次。

## 模型

| 模型 id | 仓库 | 许可证 | 分发方式 |
|---|---|---|---|
| `bge-small-zh-v1.5` | `BAAI/bge-small-zh-v1.5` | MIT | 运行时按需下载（ModelScope / HuggingFace） |
| `bge-reranker-base` | `BAAI/bge-reranker-base` | MIT | **可选**精排模型，显式安装才下载 |
| `faster-whisper-tiny` / `base` / `small` | `Systran/faster-whisper-*`（OpenAI Whisper 权重转换） | MIT | 运行时按需下载 |
| `cosyvoice2-0.5b` | `iic/CosyVoice2-0.5B` / `FunAudioLLM/CosyVoice2-0.5B` | Apache-2.0 | 运行时按需下载 |
| `qwen3:8b` | `Qwen/Qwen3-8B`（经 Ollama 分发） | Apache-2.0 | 由用户本机 Ollama 拉取，不随安装包分发 |

口径说明：

- **权重不随安装包分发**：安装包只带下载器与清单；模型在用户机器上按需拉取，许可证
  文本以模型仓库为准。
- **不默认打包 LGPL/AGPL/CC BY-NC 资产**：例如 `edge-tts`（LGPLv3）不作为默认链路、
  不随包分发（见开发计划 §3.1 合规注记）。
- **Ollama 模型**（`qwen3:8b`）由用户侧 Ollama 管理，卸载/更新走 `ollama`，不在
  Echoes 的「模型管理」里删除。

## 运行时依赖（摘要）

| 依赖 | 许可证 | 说明 |
|---|---|---|
| PyTorch | BSD-3-Clause | 运行时档案内，CPU/CUDA 两档 |
| faster-whisper | MIT | ASR 推理包装 |
| transformers | Apache-2.0 | 嵌入/重排 |
| sqlite-vec | MIT / Apache-2.0（双许可） | 向量索引扩展 |
| Tauri | MIT / Apache-2.0 | 桌面壳 |
| SQLite | Public Domain | 数据库 |

完整传递依赖清单以各运行时档案（`runtime_manifest.json`）与锁文件为准；发布前用
`pip-licenses` / `cargo-license` 生成 SBOM 附在 Release 页（待办，见开发计划 §7.9）。
