package com.echoes.conversation.config;

import com.echoes.utils.UuidUtils;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.data.convert.ReadingConverter;
import org.springframework.data.convert.WritingConverter;
import org.springframework.data.mongodb.core.convert.MongoCustomConversions;

import java.util.Arrays;
import java.util.UUID;

@Configuration
@ConditionalOnClass(MongoCustomConversions.class)
public class MongoConfig {

    @WritingConverter
    static class UuidToStringConverter implements Converter<UUID, String> {
        @Override
        public String convert(UUID source) {
            return source == null ? null : source.toString();
        }
    }

    @ReadingConverter
    static class StringToUuidConverter implements Converter<String, UUID> {
        @Override
        public UUID convert(String source) {
            if (source == null || source.isEmpty()) {
                return null;
            }
            try {
                return UuidUtils.parseLenient(source);
            } catch (Exception ex) {
                return null;
            }
        }
    }

    @Bean
    public Converter<UUID, String> uuidToStringConverter() {
        return new UuidToStringConverter();
    }

    @Bean
    public Converter<String, UUID> stringToUuidConverter() {
        return new StringToUuidConverter();
    }

    @Bean
    public MongoCustomConversions mongoCustomConversions() {
        return new MongoCustomConversions(Arrays.asList(
                new UuidToStringConverter(),
                new StringToUuidConverter()
        ));
    }
}


