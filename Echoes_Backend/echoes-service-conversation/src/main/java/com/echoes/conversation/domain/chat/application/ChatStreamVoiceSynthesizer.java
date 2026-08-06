package com.echoes.conversation.domain.chat.application;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;

/**
 * 流式聊天语音合成器
 * 负责语音合成调用和音频数据处理
 */
@Slf4j
@Component
public class ChatStreamVoiceSynthesizer {

    /**
     * 从流式块组装 WAV 文件
     */
    public byte[] assembleWavFromChunks(List<byte[]> chunks, int sampleRate) {
        if (chunks == null || chunks.isEmpty()) return null;
        try {
            ByteArrayOutputStream pcmOut = new ByteArrayOutputStream();
            for (byte[] chunk : chunks) {
                if (chunk == null || chunk.length == 0) continue;
                // detect WAV header ("RIFF")
                if (chunk.length >= 12 && chunk[0] == 'R' && chunk[1] == 'I' && chunk[2] == 'F' && chunk[3] == 'F') {
                    // find "data" subchunk
                    int dataIdx = -1;
                    for (int i = 12; i + 8 <= chunk.length; i++) {
                        if (chunk[i] == 'd' && chunk[i+1] == 'a' && chunk[i+2] == 't' && chunk[i+3] == 'a') {
                            dataIdx = i;
                            break;
                        }
                    }
                    if (dataIdx >= 0 && dataIdx + 8 <= chunk.length) {
                        int sizeOff = dataIdx + 4;
                        int available = chunk.length - (dataIdx + 8);
                        // read 4-byte little-endian size
                        int declaredSize = ByteBuffer.wrap(chunk, sizeOff, 4).order(ByteOrder.LITTLE_ENDIAN).getInt();
                        int copyLen = Math.min(declaredSize, available);
                        if (copyLen > 0) {
                            pcmOut.write(chunk, dataIdx + 8, copyLen);
                        }
                    } else {
                        // couldn't find data subchunk; as fallback copy whole chunk after header (from 12)
                        if (chunk.length > 12) pcmOut.write(chunk, 12, chunk.length - 12);
                    }
                } else {
                    // treat as raw PCM chunk
                    pcmOut.write(chunk);
                }
            }
            byte[] pcmData = pcmOut.toByteArray();
            if (pcmData == null || pcmData.length == 0) return null;

            // Ensure even byte count for WAV data
            if ((pcmData.length & 1) == 1) {
                pcmOut.write(0);
                pcmData = pcmOut.toByteArray();
            }

            int numChannels = 1;
            int bitsPerSample = 16;
            int byteRate = sampleRate * numChannels * bitsPerSample / 8;
            int blockAlign = numChannels * bitsPerSample / 8;
            int dataSize = pcmData.length;
            int riffChunkSize = 36 + dataSize;

            ByteArrayOutputStream wavOut = new ByteArrayOutputStream();
            // RIFF header
            wavOut.write(new byte[] {'R','I','F','F'});
            wavOut.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(riffChunkSize).array());
            wavOut.write(new byte[] {'W','A','V','E'});
            // fmt subchunk
            wavOut.write(new byte[] {'f','m','t',' '});
            wavOut.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(16).array());
            wavOut.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort((short)1).array());
            wavOut.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort((short)numChannels).array());
            wavOut.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(sampleRate).array());
            wavOut.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(byteRate).array());
            wavOut.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort((short)blockAlign).array());
            wavOut.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort((short)bitsPerSample).array());
            // data subchunk
            wavOut.write(new byte[] {'d','a','t','a'});
            wavOut.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(dataSize).array());
            wavOut.write(pcmData);

            return wavOut.toByteArray();
        } catch (IOException e) {
            log.debug("assembleWavFromChunks IO error: {}", e.getMessage());
            return null;
        }
    }
}
