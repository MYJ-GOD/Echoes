"""
Redis Streams 消息队列客户端
用于消费和产生训练任务消息
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import redis
from redis import Redis
from redis.commands.core import StreamCommands

logger = logging.getLogger(__name__)


class RedisStreamsClient:
    """
    Redis Streams 客户端
    支持消息的产生和消费
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        stream_key: str = "voice-training-tasks",
        group_name: str = "voice-training-group",
        consumer_name: str = "echoes-ai-consumer"
    ):
        """
        初始化Redis Streams客户端
        
        Args:
            host: Redis主机
            port: Redis端口
            db: 数据库编号
            password: 密码
            stream_key: Stream键名
            group_name: 消费者组名称
            consumer_name: 消费者名称
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.stream_key = stream_key
        self.group_name = group_name
        self.consumer_name = consumer_name
        
        self._client: Optional[Redis] = None
    
    @property
    def client(self) -> Redis:
        """获取Redis客户端"""
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
        return self._client
    
    def create_consumer_group(self) -> bool:
        """
        创建消费者组（如果不存在）
        
        Returns:
            是否成功创建（或已存在）
        """
        try:
            # 使用MKSTREAM选项，如果stream不存在则自动创建
            self.client.xgroup_create(
                self.stream_key,
                self.group_name,
                id="0",  # 从头开始读取
                mkstream=True
            )
            logger.info(f"创建消费者组成功: {self.group_name}")
            return True
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"消费者组已存在: {self.group_name}")
                return True
            logger.error(f"创建消费者组失败: {e}")
            raise
    
    def send_message(self, message: Dict[str, Any]) -> str:
        """
        发送消息到Stream
        
        Args:
            message: 消息内容（字典）
            
        Returns:
            消息ID
        """
        # 添加时间戳
        message["timestamp"] = datetime.now().isoformat()
        
        # 序列化复杂对象
        for key, value in message.items():
            if isinstance(value, (list, dict)):
                message[key] = json.dumps(value, ensure_ascii=False)
        
        message_id = self.client.xadd(self.stream_key, message)
        logger.info(f"发送消息成功: stream={self.stream_key}, id={message_id}")
        return message_id
    
    def read_messages(
        self,
        count: int = 1,
        block_ms: Optional[int] = None
    ) -> list:
        """
        读取消息（使用消费者组）
        
        Args:
            count: 每次读取的消息数量
            block_ms: 阻塞等待时间（毫秒），None表示非阻塞
            
        Returns:
            消息列表 [(message_id, data), ...]
        """
        try:
            if block_ms:
                result = self.client.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    {self.stream_key: ">"},
                    count=count,
                    block=block_ms
                )
            else:
                result = self.client.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    {self.stream_key: ">"},
                    count=count
                )
            
            messages = []
            if result:
                for stream_name, stream_messages in result:
                    for message_id, data in stream_messages:
                        messages.append((message_id, data))
                        logger.debug(f"读取消息: id={message_id}, data={data}")
            
            return messages
        
        except redis.exceptions.ResponseError as e:
            logger.error(f"读取消息失败: {e}")
            raise
    
    def acknowledge_message(self, message_id: str) -> int:
        """
        确认消息已处理
        
        Args:
            message_id: 消息ID
            
        Returns:
            确认的消息数量
        """
        result = self.client.xack(self.stream_key, self.group_name, message_id)
        logger.debug(f"确认消息: id={message_id}, result={result}")
        return result
    
    def claim_message(
        self,
        message_id: str,
        min_idle_ms: int = 30000,
        consumer_name: Optional[str] = None
    ) -> list:
        """
        认领未确认的消息（用于故障处理）
        
        Args:
            message_id: 消息ID
            min_idle_ms: 消息最小空闲时间（毫秒）
            consumer_name: 新的消费者名称
            
        Returns:
            认领的消息列表
        """
        consumer = consumer_name or self.consumer_name
        result = self.client.xclaim(
            self.stream_key,
            self.group_name,
            consumer,
            min_idle_ms,
            [message_id]
        )
        logger.info(f"认领消息: id={message_id}, consumer={consumer}")
        return result
    
    def get_stream_info(self) -> Dict[str, Any]:
        """
        获取Stream信息
        
        Returns:
            Stream信息字典
        """
        info = self.client.info("keyspace")
        stream_info = {
            "stream_key": self.stream_key,
            "group_name": self.group_name,
            "consumer_name": self.consumer_name,
            "length": 0,
            "pending": 0,
            "consumers": []
        }
        
        try:
            # 获取Stream长度
            stream_info["length"] = self.client.xlen(self.stream_key)
            
            # 获取待处理消息
            pending_info = self.client.xpending_range(
                self.stream_key,
                self.group_name,
                min="-",
                max="+",
                count=100
            )
            stream_info["pending"] = len(pending_info)
            
            # 获取消费者列表
            consumers = self.client.xinfo_consumers(self.stream_key, self.group_name)
            stream_info["consumers"] = [
                {"name": c["name"], "pending": c["pending"], "idle": c["idle"]}
                for c in consumers
            ]
            
        except redis.exceptions.ResponseError as e:
            logger.warning(f"获取Stream信息失败: {e}")
        
        return stream_info
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("关闭Redis连接")


# 便捷函数
def create_client(**kwargs) -> RedisStreamsClient:
    """创建Redis Streams客户端"""
    return RedisStreamsClient(**kwargs)

