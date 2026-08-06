package com.echoes.conversation.common.util;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.echoes.utils.UuidUtils;

import java.io.IOException;
import java.util.UUID;

public class LenientUUIDDeserializer extends JsonDeserializer<UUID> {

    @Override
    public UUID deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
        String value = p.getValueAsString();
        try {
            return UuidUtils.parseLenient(value);
        } catch (IllegalArgumentException e) {
            throw new IOException("Invalid UUID format: " + value, e);
        }
    }
}
