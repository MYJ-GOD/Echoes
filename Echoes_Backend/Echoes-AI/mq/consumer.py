"""
训练任务消费者
从 Redis Streams 消费训练任务消息并执行训练

职责边界：
- 只负责从消息队列消费任务并执行
- 不直接面向前端，只通过 Redis Streams 接收任务
- 不维护会话状态，每次任务独立
- 结果通过回调回流至 Java 层
"""
import asyncio
import json
import logging
import os
import re
import signal
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common.config import settings
from common.logger import logger
from mq.redis_streams import RedisStreamsClient
from jobs.voice_training_job import run_training, TrainingResult

# 消息过期时间（5分钟）
MESSAGE_EXPIRE_MINUTES = 5


@dataclass
class TrainingTaskMessage:
    """训练任务消息"""
    message_id: str
    task_id: str
    voice_asset_id: str
    ref_id: str
    storage_key: str  # OSS 存储路径
    user_id: str
    model_version: int = 1
    prompt: str = ""
    create_time: str = ""
    priority: int = 5
    message_type: str = "START_TRAINING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messageId": self.message_id,
            "taskId": self.task_id,
            "voiceAssetId": self.voice_asset_id,
            "refId": self.ref_id,
            "storageKey": self.storage_key,
            "userId": self.user_id,
            "modelVersion": self.model_version,
            "prompt": self.prompt,
            "createTime": self.create_time,
            "priority": self.priority,
            "messageType": self.message_type
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingTaskMessage":
        return cls(
            message_id=data.get("messageId", ""),
            task_id=data.get("taskId", ""),
            voice_asset_id=data.get("voiceAssetId", ""),
            ref_id=data.get("refId", ""),
            storage_key=data.get("storageKey", ""),
            user_id=data.get("userId", ""),
            model_version=int(data.get("modelVersion", 1)),
            prompt=data.get("prompt", ""),
            create_time=data.get("createTime", ""),
            priority=int(data.get("priority", 5)),
            message_type=data.get("messageType", "START_TRAINING")
        )


class TrainingTaskConsumer:
    """
    训练任务消费者

    职责：
    - 从 Redis Streams 消费训练任务
    - 调用 VoiceTrainingJob 执行训练
    - 回调 Java 服务更新进度和状态

    不负责：
    - 用户认证 (由 Java 层负责)
    - 权限验证 (由 Java 层负责)
    - 会话管理 (由 Java 层负责)
    - 直接面向前端 (永不对外暴露)
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        stream_key: str = "voice-training-tasks",
        group_name: str = "voice-training-group",
        consumer_name: str = "echoes-ai-consumer",
        java_api_base: str = os.environ.get("JAVA_API_URL", "http://localhost:18083")
    ):
        """
        初始化消费者

        Args:
            redis_host: Redis主机
            redis_port: Redis端口
            stream_key: Stream键名
            group_name: 消费者组名称
            consumer_name: 消费者名称
            java_api_base: Java服务API基础地址
        """
        self.redis_client = RedisStreamsClient(
            host=redis_host,
            port=redis_port,
            stream_key=stream_key,
            group_name=group_name,
            consumer_name=consumer_name
        )
        self.java_api_base = java_api_base
        self.running = False
        self._task: Optional[asyncio.Task] = None

    def start(self, blocking: bool = True):
        """
        启动消费者

        Args:
            blocking: 是否阻塞运行
        """
        logger.info(
            f"启动训练任务消费者... stream={self.redis_client.stream_key}, "
            f"group={self.redis_client.group_name}, consumer={self.redis_client.consumer_name}, "
            f"java_api_base={self.java_api_base}"
        )

        # 创建消费者组
        self.redis_client.create_consumer_group()

        if blocking:
            self._run_sync()
        else:
            self._task = asyncio.create_task(self._run_async())

    def stop(self):
        """停止消费者"""
        logger.info("停止训练任务消费者...")
        self.running = False
        if self._task:
            self._task.cancel()

    def _run_sync(self):
        """同步运行消费者"""
        self.running = True

        # 创建停止事件，用于线程间通信
        stop_event = threading.Event()

        # 检查是否在主线程
        # signal.signal() 只能在主线程中使用
        is_main_thread = threading.current_thread() == threading.main_thread()

        if is_main_thread:
            # 在主线程中，设置信号处理
            def signal_handler(sig, frame):
                logger.info("收到停止信号")
                self.running = False
                stop_event.set()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            # 在非主线程中，通过 stop_event 来通知停止
            # 注册 atexit 回调以便在程序退出时设置事件
            import atexit
            def cleanup():
                if self.running:
                    logger.info("程序退出，停止消费者")
                    self.running = False
                    stop_event.set()
            atexit.register(cleanup)

        try:
            while self.running and not stop_event.is_set():
                try:
                    messages = self.redis_client.read_messages(count=1, block_ms=5000)
                    for message_id, data in messages:
                        self._process_message(message_id, data)
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    continue
        except KeyboardInterrupt:
            logger.info("收到键盘中断")
        finally:
            self.redis_client.close()

    async def _run_async(self):
        """异步运行消费者"""
        self.running = True

        try:
            while self.running:
                try:
                    messages = await asyncio.to_thread(
                        self.redis_client.read_messages,
                        count=1,
                        block_ms=5000
                    )
                    for message_id, data in messages:
                        await self._process_message_async(message_id, data)
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    await asyncio.sleep(1)
        finally:
            self.redis_client.close()

    @staticmethod
    def _parse_message_time(raw_time: str) -> datetime:
        """
        兼容解析 Java 侧时间字符串。
        Java LocalDateTime 可能带 9 位小数秒，在部分 Python 运行时需要先截断到 6 位。
        """
        value = (raw_time or "").strip()
        if not value:
            raise ValueError("empty createTime")

        value = value.replace("Z", "+00:00")
        match = re.match(r"^(.+T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})?$", value)
        if match and match.group(2):
            frac = match.group(2)[1:]
            value = f"{match.group(1)}.{frac[:6]}{match.group(3) or ''}"

        return datetime.fromisoformat(value)

    def _process_message(self, message_id: str, data: Dict[str, str]):
        """
        同步处理消息

        Args:
            message_id: 消息ID
            data: 消息数据
        """
        try:
            # 解析消息
            task_message = TrainingTaskMessage.from_dict(data)
            logger.info(f"收到训练任务: taskId={task_message.task_id}, type={task_message.message_type}")

            # 检查消息是否过期
            if task_message.create_time:
                try:
                    create_time = self._parse_message_time(task_message.create_time)
                    # 移除时区信息进行比较（如果是带时区的）
                    if create_time.tzinfo:
                        create_time = create_time.replace(tzinfo=None)
                    now = datetime.now()
                    age_minutes = (now - create_time).total_seconds() / 60

                    if age_minutes > MESSAGE_EXPIRE_MINUTES:
                        logger.warning(
                            f"消息已过期: taskId={task_message.task_id}, "
                            f"创建时间={task_message.create_time}, "
                            f"已过期时间={age_minutes:.1f}分钟"
                        )
                        # 确认并丢弃过期消息
                        self.redis_client.acknowledge_message(message_id)
                        logger.info(f"过期消息已丢弃: id={message_id}")
                        return
                except Exception as e:
                    logger.warning(
                        f"解析消息时间失败: createTime={task_message.create_time}, error={e}, 继续处理消息"
                    )

            # 根据消息类型处理
            if task_message.message_type == "START_TRAINING":
                self._handle_start_training(task_message)
            elif task_message.message_type == "CANCEL_TRAINING":
                self._handle_cancel_training(task_message)
            elif task_message.message_type == "RETRY_TRAINING":
                self._handle_retry_training(task_message)
            else:
                logger.warning(f"未知的消息类型: {task_message.message_type}")

            # 确认消息
            self.redis_client.acknowledge_message(message_id)
            logger.info(f"消息已确认: id={message_id}")

        except Exception as e:
            logger.error(f"处理消息失败: messageId={message_id}, error={e}")
            # 不确认消息，让它留在待处理队列中
            raise

    async def _process_message_async(self, message_id: str, data: Dict[str, str]):
        """异步处理消息"""
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_message, message_id, data)

    def _handle_start_training(self, task: TrainingTaskMessage):
        """
        处理开始训练任务

        Args:
            task: 训练任务消息
        """
        logger.info(f"开始训练: taskId={task.task_id}, voiceAssetId={task.voice_asset_id}")

        try:
            # 更新任务状态为训练中
            self._callback_progress(task.task_id, 0, "开始训练")

            # 定义进度回调
            def progress_callback(progress: float, message: str):
                self._callback_progress(task.task_id, progress, message)

            # 执行训练任务
            result = run_training(
                task_id=task.task_id,
                ref_id=task.ref_id,
                storage_key=task.storage_key,
                voice_asset_id=task.voice_asset_id,
                user_id=task.user_id,
                model_version=task.model_version,
                prompt=task.prompt,
                progress_callback=progress_callback
            )

            # 根据结果回调
            if result.success:
                self._callback_success(
                    task_id=task.task_id,
                    voice_model_id=result.voice_model_id,
                    voice_id_external=result.voice_id_external,
                    similarity_score=result.similarity_score,
                    model_path=result.model_path
                )
                logger.info(f"训练完成: taskId={task.task_id}")
            else:
                self._callback_failed(task.task_id, result.error_message or "未知错误")

        except Exception as e:
            logger.error(f"训练失败: taskId={task.task_id}, error={e}")
            self._callback_failed(task.task_id, str(e))

    def _handle_cancel_training(self, task: TrainingTaskMessage):
        """
        处理取消训练任务

        Args:
            task: 训练任务消息
        """
        logger.info(f"取消训练: taskId={task.task_id}")
        # 取消逻辑由消费者控制，标记任务为已取消
        self._callback_failed(task.task_id, "任务已取消")

    def _handle_retry_training(self, task: TrainingTaskMessage):
        """
        处理重试训练任务

        Args:
            task: 训练任务消息
        """
        logger.info(f"重试训练: taskId={task.task_id}")
        self._handle_start_training(task)

    def _callback_progress(self, task_id: str, progress: float, message: str):
        """
        回调进度更新

        Args:
            task_id: 任务ID
            progress: 进度 (0-100)
            message: 状态消息
        """
        try:
            import requests
            url = f"{self.java_api_base}/internal/voice/callback/progress/{task_id}"
            payload = {
                "progress": progress,
                "message": message
            }

            response = requests.post(
                url,
                json=payload,
                headers={
                    "X-Internal-Source": "echoes-ai",
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.debug(f"进度回调成功: taskId={task_id}, progress={progress}")
            else:
                logger.warning(f"进度回调失败: taskId={task_id}, status={response.status_code}")

        except Exception as e:
            logger.error(f"进度回调异常: taskId={task_id}, error={e}")

    def _callback_success(
        self,
        task_id: str,
        voice_model_id: str,
        voice_id_external: str,
        similarity_score: float,
        model_path: str
    ):
        """
        回调训练成功

        Args:
            task_id: 任务ID
            voice_model_id: 声纹模型ID
            voice_id_external: 外部语音ID
            similarity_score: 相似度评分
            model_path: 模型存储路径
        """
        try:
            import requests
            url = f"{self.java_api_base}/internal/voice/callback/complete/success/{task_id}"
            payload = {
                "voiceModelId": voice_model_id,
                "voiceIdExternal": voice_id_external,
                "similarityScore": similarity_score,
                "modelPath": model_path
            }

            response = requests.post(
                url,
                json=payload,
                headers={
                    "X-Internal-Source": "echoes-ai",
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY
                },
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"成功回调成功: taskId={task_id}")
            else:
                logger.warning(f"成功回调失败: taskId={task_id}, status={response.status_code}")

        except Exception as e:
            logger.error(f"成功回调异常: taskId={task_id}, error={e}")

    def _callback_failed(self, task_id: str, error_message: str):
        """
        回调训练失败

        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        try:
            import requests
            url = f"{self.java_api_base}/internal/voice/callback/complete/failed/{task_id}"
            payload = {
                "errorMessage": error_message
            }

            response = requests.post(
                url,
                json=payload,
                headers={
                    "X-Internal-Source": "echoes-ai",
                    "X-Internal-Api-Key": settings.INTERNAL_API_KEY
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"失败回调成功: taskId={task_id}")
            else:
                logger.warning(f"失败回调失败: taskId={task_id}, status={response.status_code}")

        except Exception as e:
            logger.error(f"失败回调异常: taskId={task_id}, error={e}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="训练任务消费者")
    parser.add_argument("--redis-host", default="localhost", help="Redis主机")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis端口")
    parser.add_argument("--stream-key", default="voice-training-tasks", help="Stream键名")
    parser.add_argument("--java-api", default="http://localhost:8082", help="Java API基础地址")

    args = parser.parse_args()

    consumer = TrainingTaskConsumer(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        stream_key=args.stream_key,
        java_api_base=args.java_api
    )

    consumer.start(blocking=True)


if __name__ == "__main__":
    main()
