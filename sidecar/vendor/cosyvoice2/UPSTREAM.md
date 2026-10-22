# Vendored 上游锚（ADR-014）

本目录是上游原样拷贝（vanilla），**禁止手改**；需要补丁先走上游，或在本文件登记差异并经 ADR 修订。

| 目录 | 来源 | 锚 |
| --- | --- | --- |
| `cosyvoice/` | FunAudioLLM/CosyVoice main | commit `074ca6d`（2026-05-26） |
| `matcha/` | shivammehta25/Matcha-TTS | commit `dd9105b3`（CosyVoice 父仓 `third_party/Matcha-TTS` 子模块 pin，非 matcha 仓 HEAD） |

- 拷贝时排除 `.git`、`__pycache__`、`*.pyc`，其余原样；许可证见LICENSE.CosyVoice / LICENSE.Matcha。
- `matcha` 包的 `sys.path` 注入由 sidecar boot 完成（等价上游 example.py 惯例），不通过 pip 安装。
- vendored 目录不参与本仓质量闸：ruff exclude 已配置；mypy files 显式列表天然不含；import-linter root_package 天然不含；乱码扫描与翻译面只覆盖 `echoes_sidecar/` 与 `tests/`。
- CosyVoice2 权重不在此目录（7.3 运行时下载边界：modelscope `iic/CosyVoice2-0.5B`）。
