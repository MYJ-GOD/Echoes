package com.echoes.conversation.domain.chat.converter;

import com.echoes.conversation.domain.chat.enums.SessionStatus;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

import java.util.stream.Stream;

/**
 * SessionStatus 枚举转换器
 * 将数据库中的小写字符串（如 "active"）转换为枚举（如 SessionStatus.ACTIVE）
 * 
 * @author echoes
 */
@Converter(autoApply = true)
public class SessionStatusConverter implements AttributeConverter<SessionStatus, String> {

    @Override
    public String convertToDatabaseColumn(SessionStatus status) {
        if (status == null) {
            return null;
        }
        // 写入数据库时，使用枚举的 code 字段（小写）
        return status.getCode();
    }

    @Override
    public SessionStatus convertToEntityAttribute(String code) {
        if (code == null || code.isEmpty()) {
            return null;
        }
        // 从数据库读取时，根据 code 字段匹配枚举
        return Stream.of(SessionStatus.values())
                .filter(status -> status.getCode().equalsIgnoreCase(code))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unknown SessionStatus code: " + code));
    }
}

