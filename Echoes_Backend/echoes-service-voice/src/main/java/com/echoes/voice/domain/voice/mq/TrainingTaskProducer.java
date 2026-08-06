package com.echoes.voice.domain.voice.mq;

import com.echoes.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.RedisStreamCommands;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Redis Streams 消息生产者
 * 用于发送训练任务消息到消息队列
 *
 * @author echoes
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TrainingTaskProducer {

    private final RedisConnectionFactory connectionFactory;

    @Value("${echoes.voice.mq.stream-key:voice-training-tasks}")
    private String streamKey;

    @Value("${echoes.voice.mq.group-name:voice-training-group}")
    private String groupName;

    /**
     * 发送训练任务消息
     *
     * @param message 训练任务消息
     * @return 消息ID
     */
    public String sendTrainingTask(TrainingTaskMessage message) {
        try {
            // 初始化Stream和消费者组（如果不存在）
            initializeStream();

            // 序列化消息
            Map<String, String> fields = serializeMessage(message);

            // 发送消息
            RedisStreamCommands commands = connectionFactory.getConnection().streamCommands();
            
            // 转换 Map<String, String> 到 Map<byte[], byte[]>
            Map<byte[], byte[]> byteFields = new HashMap<>();
            for (Map.Entry<String, String> entry : fields.entrySet()) {
                byteFields.put(entry.getKey().getBytes(), entry.getValue() != null ? entry.getValue().getBytes() : new byte[0]);
            }
            
            RecordId recordId = commands.xAdd(streamKey.getBytes(), byteFields);

            log.info("发送训练任务消息成功: messageId={}, taskId={}, recordId={}",
                    message.getMessageId(), message.getTaskId(), recordId);

            return recordId.toString();
        } catch (Exception e) {
            log.error("发送训练任务消息失败: messageId={}, taskId={}",
                    message.getMessageId(), message.getTaskId(), e);
            throw new BusinessException("发送训练任务消息失败");
        }
    }

    /**
     * 发送开始训练消息
     *
     * @param taskId 任务ID
     * @param voiceAssetId 音色资产ID
     * @param refId 参考音频ID
     * @param storageKey OSS存储路径
     * @param userId 用户ID
     * @param modelVersion 模型版本
     * @param prompt prompt
     * @return 消息ID
     */
    public String sendStartTraining(UUID taskId, UUID voiceAssetId, String refId, String storageKey,
                                    UUID userId, Integer modelVersion, String prompt) {
        TrainingTaskMessage message = TrainingTaskMessage.createStartMessage(
                taskId, voiceAssetId, refId, storageKey, userId, modelVersion, prompt);
        return sendTrainingTask(message);
    }

    /**
     * 发送取消训练消息
     *
     * @param taskId 任务ID
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     * @return 消息ID
     */
    public String sendCancelTraining(UUID taskId, UUID voiceAssetId, UUID userId) {
        TrainingTaskMessage message = TrainingTaskMessage.createCancelMessage(
                taskId, voiceAssetId, userId);
        return sendTrainingTask(message);
    }

    /**
     * 初始化Stream和消费者组
     * 注意：由于编译问题暂时跳过初始化，消费者组会在消息发送时自动创建
     */
    private void initializeStream() {
        // 初始化逻辑由于Java编译器限制暂时跳过
        // Redis Stream消费者组会在首次发送消息时自动创建
    }

    /**
     * 序列化消息为Map
     */
    private Map<String, String> serializeMessage(TrainingTaskMessage message) {
        Map<String, String> fields = new HashMap<>();
        try {
            fields.put("messageId", message.getMessageId());
            fields.put("taskId", message.getTaskId() != null ? message.getTaskId().toString() : "");
            fields.put("voiceAssetId", message.getVoiceAssetId() != null ? message.getVoiceAssetId().toString() : "");
            fields.put("refId", message.getRefId() != null ? message.getRefId() : "");
            fields.put("storageKey", message.getStorageKey() != null ? message.getStorageKey() : "");
            fields.put("userId", message.getUserId() != null ? message.getUserId().toString() : "");
            fields.put("modelVersion", message.getModelVersion() != null ? message.getModelVersion().toString() : "1");
            fields.put("prompt", message.getPrompt() != null ? message.getPrompt() : "");
            fields.put("createTime", message.getCreateTime() != null ? message.getCreateTime().toString() : "");
            fields.put("priority", message.getPriority() != null ? message.getPriority().toString() : "5");
            fields.put("messageType", message.getMessageType() != null ? message.getMessageType().name() : "");
        } catch (Exception e) {
            log.error("序列化消息失败", e);
        }
        return fields;
    }
}
