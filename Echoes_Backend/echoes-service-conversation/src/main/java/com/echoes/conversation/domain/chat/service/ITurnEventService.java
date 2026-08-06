package com.echoes.conversation.domain.chat.service;

/**
 * Turn event persistence service (for seq generation and event buffering).
 * Provides minimal API to append events and make them available for resume/replay.
 */
public interface ITurnEventService {

    /**
     * Append an event to the turn's event buffer and return the serialized event JSON.
     *
     * @param sessionId       conversation/session id (string form)
     * @param turnId          turn id provided by client
     * @param type            event type (message.delta/message.final/audio_chunk/error/end/etc)
     * @param data            event data (will be serialized)
     * @param traceId         trace id for diagnostics
     * @param protocolVersion protocol version
     * @return serialized event JSON (ready to be sent as SSE data:)
     */
    String appendEvent(String sessionId, String turnId, String type, Object data, String traceId, String protocolVersion);
}


