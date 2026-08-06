"""
qdrant_service 单元测试

聚焦保护本次修复的核心逻辑：upsert_chunks 的 point ID 必须由
chunk_id 确定性推导，而非每次从 0 开始编号（否则多次写入会互相覆盖）。

本环境（base conda）未安装 qdrant_client / numpy 等重依赖，也未启用
pytest-asyncio。因此测试通过以下方式保持可运行且真实：
  1. 在 import 前用 sys.modules 注入 qdrant_client / numpy 的轻量替身；
  2. 用 importlib 直接从文件加载 qdrant_service.py，绕过 app.services.__init__
     的重依赖链；
  3. 异步用例用 asyncio.run() 手动驱动，不依赖任何异步插件。

这样测试真正执行到 upsert_chunks 本身——若有人把 id 改回 enumerate 索引，
test_upsert_uses_chunk_id_hash_not_index 会立即失败。
"""
import asyncio
import hashlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

# ---------------------------------------------------------------------------
# 在导入目标模块前，注入缺失重依赖的轻量替身
# ---------------------------------------------------------------------------

class _FakePointStruct:
    """替身 PointStruct：忠实保存 id/vector/payload 供断言。"""

    def __init__(self, id, vector, payload):  # noqa: A002 - 对齐真实 API 参数名
        self.id = id
        self.vector = vector
        self.payload = payload


def _install_fake_dependencies() -> None:
    # qdrant_client 包
    qc = types.ModuleType("qdrant_client")
    qc.QdrantClient = object
    qc.AsyncQdrantClient = object

    qc_http = types.ModuleType("qdrant_client.http")
    qc_models = types.ModuleType("qdrant_client.http.models")
    qc_models.PointStruct = _FakePointStruct
    qc_models.SparseVector = object
    qc_models.FilterSelector = object
    qc_http.models = qc_models

    sys.modules.setdefault("qdrant_client", qc)
    sys.modules.setdefault("qdrant_client.http", qc_http)
    sys.modules.setdefault("qdrant_client.http.models", qc_models)

    # numpy（qdrant_service 顶部 import numpy，但本文件用不到其功能）
    sys.modules.setdefault("numpy", types.ModuleType("numpy"))

    # app.config.settings —— 只需一个带 COLLECTION_KNOWLEDGE 的对象
    app_pkg = sys.modules.setdefault("app", types.ModuleType("app"))
    app_pkg.__path__ = []  # 标记为包
    app_config = types.ModuleType("app.config")

    class _Settings:
        COLLECTION_KNOWLEDGE = "knowledge_chunks"
        COLLECTION_CONVERSATION = "conversation_history"

    app_config.settings = _Settings()
    sys.modules.setdefault("app.config", app_config)


def _load_qdrant_service():
    _install_fake_dependencies()
    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "qdrant_service.py"
    spec = importlib.util.spec_from_file_location("_qdrant_service_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_qdrant_service = _load_qdrant_service()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _expected_point_id(chunk_id: str) -> int:
    return int(hashlib.md5(chunk_id.encode()).hexdigest()[:16], 16) % (2**63)


def _make_chunk(chunk_id: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc_001",
        "kb_id": "kb_test",
        "content": f"content of {chunk_id}",
        "chunk_index": 0,
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_upsert_uses_chunk_id_hash_not_index():
    """
    核心回归守卫：真正调用 upsert_chunks，断言传给 client 的 point ID
    等于 chunk_id 的哈希——而不是 enumerate 索引（0,1,2...）。
    若有人把修复改回 id=i，本用例失败。
    """
    async def run():
        mock_client = types.SimpleNamespace(upsert=AsyncMock(return_value=None))
        _qdrant_service.get_async_client = lambda: mock_client

        chunks = [_make_chunk("chunk_x"), _make_chunk("chunk_y")]
        vectors = [[0.1] * 4, [0.2] * 4]
        await _qdrant_service.upsert_chunks(chunks, vectors)

        mock_client.upsert.assert_awaited_once()
        points = mock_client.upsert.call_args.kwargs["points"]
        point_ids = {p.id for p in points}

        expected = {_expected_point_id("chunk_x"), _expected_point_id("chunk_y")}
        assert point_ids == expected, f"point ID 应为 chunk_id 哈希；实际={point_ids}"

        # 反向断言：绝不能是 enumerate 索引
        assert point_ids != {0, 1}, "point ID 退化为 enumerate 索引 —— 修复被回退！"

    asyncio.run(run())


def test_upsert_two_batches_no_id_collision():
    """
    两批不同 chunk 分别写入，point ID 集合不重叠——保证第二次写入
    不会覆盖第一次的数据点。
    """
    async def run():
        mock_client = types.SimpleNamespace(upsert=AsyncMock(return_value=None))
        _qdrant_service.get_async_client = lambda: mock_client

        await _qdrant_service.upsert_chunks(
            [_make_chunk(f"a_{i}") for i in range(5)], [[0.1] * 4] * 5
        )
        batch1 = {p.id for p in mock_client.upsert.call_args.kwargs["points"]}

        await _qdrant_service.upsert_chunks(
            [_make_chunk(f"b_{i}") for i in range(5)], [[0.2] * 4] * 5
        )
        batch2 = {p.id for p in mock_client.upsert.call_args.kwargs["points"]}

        assert not (batch1 & batch2), f"两批 point ID 碰撞：{batch1 & batch2}"

    asyncio.run(run())


def test_point_id_deterministic_and_in_range():
    """同一 chunk_id 结果稳定，且落在 Qdrant 接受的 int64 范围内。"""
    async def run():
        captured = []

        async def fake_upsert(**kwargs):
            captured.append(kwargs["points"])

        mock_client = types.SimpleNamespace(upsert=fake_upsert)
        _qdrant_service.get_async_client = lambda: mock_client

        chunk = _make_chunk("stable_chunk")
        await _qdrant_service.upsert_chunks([chunk], [[0.1] * 4])
        await _qdrant_service.upsert_chunks([chunk], [[0.1] * 4])

        id_first = captured[0][0].id
        id_second = captured[1][0].id
        assert id_first == id_second, "同一 chunk_id 两次写入 point ID 必须一致"
        assert 0 <= id_first < 2**63

    asyncio.run(run())
