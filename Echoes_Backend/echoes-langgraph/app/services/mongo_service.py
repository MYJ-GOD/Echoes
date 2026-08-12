"""
MongoDB 服务（双写备份 + 静态画像持久化）

- 对话记忆：Qdrant 存向量检索，MongoDB 存原始 JSON 备份（可回溯/审计）
- 静态画像：长期不变的用户设定，锁死在 MongoDB，注入 System Prompt 顶层
- 动态上下文：短期状态走滑动窗口，不落 MongoDB
"""
import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_mongo_client = None


def get_mongo_db():
    """获取 MongoDB 数据库实例（motor 异步客户端，懒加载）"""
    global _mongo_client
    if _mongo_client is None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
            logger.info("MongoDB 客户端已初始化: %s", settings.MONGODB_URI)
        except Exception as e:
            logger.warning("MongoDB 客户端初始化失败: %s", e)
            return None
    return _mongo_client[settings.MONGODB_DB]


async def save_memory_backup(user_id: str, entry: Dict[str, Any], point_id: str = "") -> bool:
    """双写：对话记忆原始 JSON 备份到 MongoDB（Qdrant 存向量，Mongo 存全量）"""
    db = get_mongo_db()
    if db is None:
        return False
    try:
        doc = {**entry, "user_id": user_id, "qdrant_point_id": point_id}
        await db[settings.MONGODB_COLLECTION_MEMORY].insert_one(doc)
        return True
    except Exception as e:
        logger.warning("MongoDB 记忆备份失败（不阻断主流程）: %s", e)
        return False


async def get_static_profile(user_id: str) -> Dict[str, Any]:
    """读取静态画像（长期不变的用户设定，注入 System Prompt 顶层）"""
    db = get_mongo_db()
    if db is None or not user_id:
        return {}
    try:
        doc = await db[settings.MONGODB_COLLECTION_STATIC_PROFILE].find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
            return doc
        return {}
    except Exception as e:
        logger.warning("读取静态画像失败: %s", e)
        return {}


async def update_static_profile(user_id: str, updates: Dict[str, Any]) -> bool:
    """更新静态画像（如用户姓名、长期偏好、关系设定等长期不变信息）"""
    db = get_mongo_db()
    if db is None or not user_id:
        return False
    try:
        await db[settings.MONGODB_COLLECTION_STATIC_PROFILE].update_one(
            {"user_id": user_id},
            {"$set": {**updates, "user_id": user_id}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning("更新静态画像失败: %s", e)
        return False
