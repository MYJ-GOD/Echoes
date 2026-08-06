package com.echoes.conversation.config;

import com.echoes.conversation.common.util.LenientUUIDDeserializer;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;

import java.io.IOException;
import java.util.UUID;

@Configuration
@ConditionalOnMissingBean(ObjectMapper.class)
public class ConversationJacksonConfig {

    @Bean(name = "conversationObjectMapper")
    public ObjectMapper conversationObjectMapper(Jackson2ObjectMapperBuilder builder) {
        ObjectMapper mapper = builder.createXmlMapper(false).build();

        // Ensure Java time module is registered
        mapper.registerModule(new JavaTimeModule());

        // Lenient UUID deserializer and stable serializer
        SimpleModule uuidModule = new SimpleModule();
        uuidModule.addDeserializer(UUID.class, new LenientUUIDDeserializer());
        uuidModule.addSerializer(UUID.class, new JsonSerializer<UUID>() {
            @Override
            public void serialize(UUID value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
                if (value == null) {
                    gen.writeNull();
                } else {
                    gen.writeString(value.toString());
                }
            }
        });
        mapper.registerModule(uuidModule);

        // Useful settings
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

        return mapper;
    }
}


