"""数据目录解析与可写性自检（母文档 5.3 / 14.3）。

目录布局（5.3）：业务数据落 `%LOCALAPPDATA%\\Echoes\\`——`db\\`（SQLite + WAL）、
`assets\\`（音色样本与克隆产物，5.1 的相对路径仅相对此目录解析）、`logs\\`；
模型权重与 torch/CUDA 运行时归 `~/.cache/echoes/`（7.1/7.3，不在本模块职责内）。

`ECHOES_DATA_DIR` 覆盖根目录（测试、便携部署）；解析只发生在组合根（3.2 组装归组合根）。
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from echoes_sidecar.core.errors import EchoesError, ErrorCode

ENV_DATA_DIR = "ECHOES_DATA_DIR"
APP_DIR_NAME = "Echoes"
DB_FILENAME = "echoes.db"


@dataclass(frozen=True)
class DataPaths:
    """数据目录三件套（5.3）：db / assets / logs 同级于 root 下。"""

    root: Path
    db_dir: Path
    assets_dir: Path
    logs_dir: Path

    @property
    def db_file(self) -> Path:
        """SQLite 主库路径（WAL 伴生文件由 SQLite 自管）。"""
        return self.db_dir / DB_FILENAME


def default_root() -> Path:
    """默认根目录：env 覆盖 → %LOCALAPPDATA%\\Echoes → 类 Unix 回退。"""
    override = os.environ.get(ENV_DATA_DIR, "").strip()
    if override:
        return Path(override).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    return Path.home() / ".local" / "share" / "echoes"


def resolve(root: Path | None = None) -> DataPaths:
    """由根目录派生子目录（不建目录、不探测，纯函数）。"""
    base = root if root is not None else default_root()
    return DataPaths(
        root=base,
        db_dir=base / "db",
        assets_dir=base / "assets",
        logs_dir=base / "logs",
    )


def ensure_writable(paths: DataPaths) -> None:
    """建目录 + 落盘探测（5.3/14.3）：失败报 STORAGE_ERROR，不静默降级。"""
    for directory in (paths.db_dir, paths.assets_dir, paths.logs_dir):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=directory, prefix=".probe-", suffix=".tmp", delete=True
            ):
                pass
        except OSError as exc:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"数据目录不可写：{directory}（{exc}）；"
                "请检查磁盘空间、权限或改用 ECHOES_DATA_DIR 指向可写目录",
            ) from exc


def path_risk_note(path: Path) -> str | None:
    """路径风险自检（5.3）：返回风险描述或 None，供组合根打日志引导排查。

    Windows 上非 ASCII / 含空格的用户目录是 PyInstaller + torch 的历史多发故障区，
    但不作为硬失败——中文用户名是主流场景，报错比告警更伤（3.2 报错而非降级
    针对的是「数据正确性」，不是「路径长相」）。
    """
    text = str(path)
    risks: list[str] = []
    if not text.isascii():
        risks.append("含非 ASCII 字符")
    if " " in text:
        risks.append("含空格")
    return "、".join(risks) if risks else None
