package com.echoes.voice.domain.cache.service;

import com.echoes.voice.common.util.MinioUtil;
import com.echoes.voice.common.constants.VoiceConstants;
import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.repository.VoiceModelMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.io.InputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;

/**
 * 声纹模型文件缓存服务
 * 负责从 OSS 下载模型文件并缓存到本地，同时使用 Redis 缓存文件路径
 * 
 * 缓存策略：
 * 1. 优先检查 Redis 缓存中的本地文件路径
 * 2. 如果缓存未命中，从 MySQL 查询 OSS 路径
 * 3. 生成 OSS 签名 URL 并下载文件
 * 4. 保存到本地缓存目录并更新 Redis 缓存
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceModelCacheService {

  private final VoiceModelMapper voiceModelMapper;
  private final MinioUtil minioUtil;
  private final ReactiveRedisTemplate<String, String> redisTemplate;

  /**
   * 获取或加载模型文件（带缓存）
   * 
   * @param voiceId 声纹模型ID
   * @return Mono<String> 本地 .pt 文件路径
   */
  public Mono<String> getOrLoadModelFile(java.util.UUID voiceId) {
    if (voiceId == null) {
      return Mono.error(new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_NOT_FOUND, "声纹模型ID不能为空"));
    }

    String cacheKey = VoiceConstants.CACHE_MODEL_PREFIX + voiceId.toString();

    // 1. 先查 Redis 缓存
    return redisTemplate.opsForValue()
        .get(cacheKey)
        .flatMap(cachedPath -> {
          // 缓存命中，检查本地文件是否存在
          if (cachedPath != null && !cachedPath.trim().isEmpty()) {
            Path filePath = Paths.get(cachedPath);
            if (Files.exists(filePath) && Files.isRegularFile(filePath)) {
              log.debug("✅ 模型文件缓存命中: voiceId={}, path={}", voiceId, cachedPath);
              return Mono.just(cachedPath);
            } else {
              // 缓存中的路径无效，清除缓存
              log.warn("缓存路径无效，清除缓存: voiceId={}, path={}", voiceId, cachedPath);
              return redisTemplate.delete(cacheKey).then(Mono.empty());
            }
          }
          return Mono.empty();
        })
        .switchIfEmpty(
            // 2. 缓存未命中，从数据库查询并下载
            Mono.fromCallable(() -> {
              // 查询数据库
              VoiceModel model = voiceModelMapper.selectById(voiceId);
              if (model == null) {
                throw new VoiceServiceException(
                    VoiceErrorEnum.VOICE_MODEL_NOT_FOUND,
                    "声纹模型不存在: voiceId=" + voiceId);
              }

              String ossUrl = model.getModelStorageKey();
              if (ossUrl == null || ossUrl.trim().isEmpty()) {
                throw new VoiceServiceException(
                    VoiceErrorEnum.VOICE_MODEL_NOT_FOUND,
                    "声纹模型文件路径为空: voiceId=" + voiceId);
              }

              log.info("开始下载模型文件: voiceId={}, ossUrl={}", voiceId, ossUrl);

              // 3. 从 OSS URL 提取 objectName
              String objectName = minioUtil.extractObjectNameFromUrl(ossUrl);
              if (objectName == null) {
                throw new VoiceServiceException(
                    VoiceErrorEnum.VOICE_MODEL_NOT_FOUND,
                    "无法从 OSS URL 提取 objectName: " + ossUrl);
              }

              // 4. 生成签名 URL
              String presignedUrl = minioUtil.generatePresignedUrl(
                  objectName, VoiceConstants.OSS_PRESIGNED_URL_EXPIRATION_MINUTES);

              // 5. 下载文件
              byte[] fileBytes = downloadFromUrl(presignedUrl);

              // 6. 保存到本地缓存
              String localPath = saveToLocalCache(voiceId, fileBytes);

              // 7. 缓存到 Redis（异步，不阻塞）
              Duration cacheTtl = Duration.ofHours(VoiceConstants.MODEL_CACHE_TTL_HOURS);
              redisTemplate.opsForValue()
                  .set(cacheKey, localPath, cacheTtl)
                  .subscribe(
                      success -> log.debug("💾 模型文件已缓存到 Redis: voiceId={}, path={}", voiceId, localPath),
                      error -> log.error("缓存模型文件到 Redis 失败: voiceId={}", voiceId, error));

              return localPath;
            })
        );
  }

  /**
   * 从 URL 下载文件
   * 
   * @param url 文件 URL
   * @return 文件字节数组
   * @throws Exception 下载失败时抛出异常
   */
  private byte[] downloadFromUrl(String url) throws Exception {
    try {
      URI uri = new URI(url);
      try (InputStream inputStream = uri.toURL().openStream()) {
        return inputStream.readAllBytes();
      }
    } catch (Exception e) {
      log.error("从 URL 下载文件失败: url={}", url, e);
      throw new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_DOWNLOAD_FAILED,
          "下载模型文件失败: " + e.getMessage(), e);
    }
  }

  /**
   * 保存到本地缓存目录
   * 
   * @param voiceId 声纹模型ID
   * @param fileBytes 文件字节数组
   * @return 本地文件路径
   * @throws Exception 保存失败时抛出异常
   */
  private String saveToLocalCache(java.util.UUID voiceId, byte[] fileBytes) throws Exception {
    try {
      Path cacheDir = Paths.get(VoiceConstants.LOCAL_MODEL_CACHE_DIR);
      Files.createDirectories(cacheDir);

      String fileName = voiceId.toString() + VoiceConstants.OSS_MODEL_EXT_PT;
      Path filePath = cacheDir.resolve(fileName);

      Files.write(filePath, fileBytes);
      log.info("模型文件已保存到本地缓存: voiceId={}, path={}, size={} bytes", 
          voiceId, filePath, fileBytes.length);

      return filePath.toAbsolutePath().toString();
    } catch (Exception e) {
      log.error("保存模型文件到本地缓存失败: voiceId={}", voiceId, e);
      throw new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_SAVE_FAILED,
          "保存模型文件到本地缓存失败: " + e.getMessage(), e);
    }
  }

  /**
   * 清除指定模型的缓存
   * 
   * @param voiceId 声纹模型ID
   * @return Mono<Boolean> 是否清除成功
   */
  public Mono<Boolean> evictModelCache(java.util.UUID voiceId) {
    if (voiceId == null) {
      return Mono.just(false);
    }

    String cacheKey = VoiceConstants.CACHE_MODEL_PREFIX + voiceId.toString();

    // 清除 Redis 缓存
    return redisTemplate.delete(cacheKey)
        .map(count -> count > 0)
        .doOnSuccess(deleted -> {
          if (deleted) {
            log.debug("🗑️ 已清除模型 Redis 缓存: voiceId={}", voiceId);
          }
        })
        .flatMap(deleted -> {
          // 同时尝试删除本地文件
          try {
            Path cacheDir = Paths.get(VoiceConstants.LOCAL_MODEL_CACHE_DIR);
            String fileName = voiceId.toString() + VoiceConstants.OSS_MODEL_EXT_PT;
            Path filePath = cacheDir.resolve(fileName);
            
            if (Files.exists(filePath)) {
              Files.delete(filePath);
              log.debug("🗑️ 已删除本地模型文件: voiceId={}, path={}", voiceId, filePath);
            }
          } catch (Exception e) {
            log.warn("删除本地模型文件失败: voiceId={}", voiceId, e);
          }
          
          return Mono.just(deleted);
        });
  }

  /**
   * 根据 voiceName 获取或加载模型文件
   * 
   * @param userId 用户ID
   * @param voiceName 模型名称
   * @return Mono<String> 本地 .pt 文件路径
   */
  public Mono<String> getOrLoadModelFileByName(java.util.UUID userId, String voiceName) {
    if (userId == null || voiceName == null || voiceName.trim().isEmpty()) {
      return Mono.error(new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_NOT_FOUND, "用户ID或模型名称不能为空"));
    }

    // 先查询数据库获取 voiceId
    VoiceModel model = voiceModelMapper.selectByUserIdAndVoiceName(userId, voiceName);
    if (model == null) {
      return Mono.error(new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_NOT_FOUND,
          "声纹模型不存在: userId=" + userId + ", voiceName=" + voiceName));
    }

    return getOrLoadModelFile(model.getVoiceModelId());
  }

  /**
   * 根据 voiceAssetId 获取或加载模型文件
   *
   * @param voiceAssetId 音色资产ID
   * @return Mono<String> 本地 .pt 文件路径
   */
  public Mono<String> getOrLoadModelFileByAssetId(java.util.UUID voiceAssetId) {
    if (voiceAssetId == null) {
      return Mono.error(new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_NOT_FOUND, "voiceAssetId 不能为空"));
    }

    // 查询最新的成功模型
    VoiceModel model = voiceModelMapper.selectLatestSuccessByAssetId(voiceAssetId);
    if (model == null) {
      return Mono.error(new VoiceServiceException(
          VoiceErrorEnum.VOICE_MODEL_NOT_FOUND,
          "声纹模型不存在: voiceAssetId=" + voiceAssetId));
    }

    return getOrLoadModelFile(model.getVoiceModelId());
  }
}
