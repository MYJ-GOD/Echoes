# PyInstaller 体积探测（阶段 0 第一周；ADR-011 输入）

- 日期：2026-10-22；机器：RTX 4060 Laptop（T-8G 档，tier_matrix）
- PyInstaller：6.x（venv 内 `pyinstaller` CLI）；入口 = bootstrap 复刻
  `python -m echoes_sidecar.main`（`import serve` + `asyncio.run`；
  main.py 无 main() 函数可直调，bootstrap 是探测专属、不入库）。
- 形态：**mock 引擎**（torch/模型权重不在场）→ 测的是 7.1 所称
  「sidecar 基础运行时」体积基线。

## 结果

| 形态 | 体积 | 文件数 | 可运行性 |
| --- | --- | --- | --- |
| `--onedir` | **34.9 MB** | 152 | ✅ EXIT=0；hello（protocol 1.0）→ booting → ready；user_text 全链 turn（assistant_text/timing 正常） |
| `--onefile` | **17.8 MB** | 1 | ✅ EXIT=0；同链路（loader 启动后行为一致） |

复现命令（仓库根）：

```powershell
.venv\Scripts\pyinstaller --noconfirm --onedir --name echoes-sidecar-probe `
  --paths sidecar --workpath tmp\probe-work --distpath tmp\probe-dist tmp\probe\bootstrap.py
```

## 解读与倾向（供 ADR-011 定稿）

1. **基础运行时基线 ≈ 35 MB**（onedir）/ 18 MB（onefile，压缩）。加上壳安装包
   （文档 7.1：Tauri 主程序 + Vue < 50MB）方向可行；真实去重空间在 torch/CUDA 与
   faster-whisper/CosyVoice2 大体量依赖 → 按 7.1 走**运行时下载**，不进安装器。
2. **形态倾向 `--onedir`**：sidecar 二进制随安装器内置、随补丁热替换友好、
   无首次解析压延迟；onefile 的解压延迟对「点名即语音陪伴」的冷启动目标不利，
   可作为 ADR-011 备选形态记录。
3. 后续增量探测（第二周起）：挂真实 provider（Ollama HTTP 客户端）后行应基本不变；
   挂 faster-whisper/CosyVoice2 后体积增幅只进运行时下载清单，禁入安装器
   （7.1 split-binary 的边界条款）。

## 结论

- PyInstaller 打包 sidecar（pydantic/asyncio 全链）**可行**，mock 形态即测即验。
- onedir ≈ 35 MB 基线数据已回填 ADR-011 待定稿字段；探测命令与 bootstrap 口径如上可复现。
