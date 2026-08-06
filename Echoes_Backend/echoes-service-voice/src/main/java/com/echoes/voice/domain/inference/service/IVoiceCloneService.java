package com.echoes.voice.domain.inference.service;

import com.echoes.voice.domain.inference.entity.dto.ChatRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.CloneRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRefRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRequestDTO;
import com.echoes.voice.domain.inference.entity.vo.ChatResponseVO;
import com.echoes.voice.domain.inference.entity.vo.CloneResponseVO;
import com.echoes.voice.domain.inference.entity.vo.SynthesizeResponseVO;
import com.fasterxml.jackson.databind.JsonNode;
import reactor.core.publisher.Flux;

import java.io.File;

/**
 * 语音克隆服务接口
 */
public interface IVoiceCloneService {

    /**
     * 语音克隆（返回JSON格式，包含base64音频数据）
     * 
     * @param request 克隆请求
     * @return 克隆响应
     */
    CloneResponseVO cloneSimple(CloneRequestDTO request);

    /**
     * 语音克隆（返回WAV音频文件）
     * 
     * @param request 克隆请求
     * @return WAV音频字节数组
     */
    byte[] clone(CloneRequestDTO request);

    /**
     * 使用指定音色合成语音（JSON格式）
     * 
     * @param request 合成请求
     * @return 合成响应
     */
    SynthesizeResponseVO synthesizeText(SynthesizeRequestDTO request, String traceId, String sessionId, String turnId);

    /**
     * 使用 refId 合成语音
     *
     * @param request 合成请求
     * @return 合成响应
     */
    SynthesizeResponseVO synthesizeTextWithRefId(SynthesizeRefRequestDTO request, String traceId, String sessionId, String turnId);

    /**
     * 使用指定音色合成语音（文件上传方式）
     * 
     * @param voiceName 音色名称
     * @param ttsText 要合成的文本
     * @return WAV音频字节数组
     */
    byte[] synthesize(String voiceName, String ttsText);

    /**
     * 流式语音合成
     * 接收文本流（SSE格式），实时生成语音并流式返回（SSE格式）
     * 
     * @param voiceName 音色名称
     * @param textStream 文本流（SSE格式，每行格式：data: {"type":"text","data":"文本内容"}\n\n）
     * @return 音频流（SSE格式，每行格式：data: {"type":"audio_chunk","audio":"base64音频","sample_rate":24000}\n\n）
     * @throws com.echoes.voice.common.exception.VoiceServiceException 当参数验证失败或语音合成失败时抛出
     */
    Flux<String> synthesizeStream(String voiceName, Flux<String> textStream);

    /**
     * Streaming TTS with end-to-end tracing headers.
     */
    Flux<String> synthesizeStream(String voiceName, Flux<String> textStream, String traceId, String sessionId, String turnId);

    /**
     * 流式语音合成（原子文本）
     *
     * @param voiceName 音色名称
     * @param text      文本内容
     * @return 音频流
     */
    Flux<String> synthesizeStream(String voiceName, String text, String traceId, String sessionId, String turnId);

    /**
     * 识别音频文件中的文本
     * 
     * @param audioFile 音频文件
     * @return 识别结果JSON
     */
    JsonNode recognizeAudio(File audioFile);

    /**
     * 列出参考音频
     * 
     * @return 参考音频列表JSON
     */
    JsonNode listReferenceAudios();

    /**
     * 列出所有音色
     * 
     * @return 音色列表JSON
     */
    JsonNode listVoices();
}
