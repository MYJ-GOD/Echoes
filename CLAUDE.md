# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

```
Echoes/
├── Echoes_Backend/     # Java microservices + Python AI services (has its own git repo)
├── Echoes_Frontend/    # Vue 3 + Vite frontend
└── models/             # Local AI model weights (CosyVoice2, embeddings, etc.)
```

---

## Commands

### Infrastructure (start first)

```bash
cd Echoes_Backend

# Start all infra (MySQL, Redis, MongoDB, Nacos, Qdrant, LangGraph)
docker-compose up -d

# Start only core infra (skip LangGraph)
docker-compose up -d mysql redis mongodb nacos qdrant
```

Nacos UI: http://localhost:8848/nacos (default user/pass: nacos/nacos)

### Java Backend (`Echoes_Backend/`)

```bash
# Build all modules, skip tests
mvn clean package -DskipTests

# Run a specific service
mvn spring-boot:run -pl echoes-service-conversation

# Test a specific module
mvn test -pl echoes-service-conversation

# Test all modules
mvn test
```

### Python — Echoes-AI TTS/ASR service

```bash
# Windows one-click (sets up conda env, env vars, starts on port 8000)
cd Echoes_Backend/Echoes-AI
./run_echoes_ai.bat

# Manual
conda activate cosyvoice2
cd Echoes_Backend/Echoes-AI
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Python — LangGraph RAG service

```bash
cd Echoes_Backend/echoes-langgraph

# Local dev
python -m venv venv && venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8088

# Or via Docker (included in docker-compose.yaml)
docker-compose up -d langgraph-service
```

### Frontend (`Echoes_Frontend/`)

```bash
cd Echoes_Frontend
pnpm install
pnpm dev          # port 5173, proxies /api → localhost:18080
pnpm build
pnpm typecheck    # vue-tsc --noEmit
```

---

## Architecture Overview

### Service Map

| Service | Lang | Port | Role |
|---|---|---|---|
| `echoes-service-gateway` | Java | 18080 | Spring Cloud Gateway — sole external ingress |
| `echoes-service-user` | Java | 18081 | Auth, JWT, user management |
| `echoes-service-conversation` | Java | 18082 | SSE orchestration, turn/session management |
| `echoes-service-voice` | Java | 18083 | Voice asset CRUD, TTS job dispatch |
| `echoes-service-admin` | Java | 18084 | Admin operations |
| `echoes-service-rag` | Java | 18086 | RAG integration (proxies to LangGraph) |
| `Echoes-AI` | Python | 8000 | CosyVoice2 TTS, ASR execution |
| `echoes-langgraph` | Python | 8088 | LangGraph RAG (Qdrant + bge-m3 embeddings) |

External client → Gateway (18080) → Java services → Python services (internal only)

### Configuration

All Java services load configuration from **Nacos** at startup. The local `application.yml` in each service contains only the Nacos connection address. Actual service config (ports, DB credentials, feature flags) lives in `Echoes_Backend/init/nacos-yaml/`. The file naming convention is `Echoes--<service>.yaml` (double dash = no environment suffix → applies to all profiles).

`application.yaml` in that folder is the shared config loaded by every service.

### Java Service Internal Structure

Each Java service follows the same package layout under `com.echoes.<service-name>/`:
- `domain/` — entities, mappers, service interfaces, and DTOs grouped by business domain
- `config/` — Spring beans, security, and framework configuration
- `common/` — service-local utilities (not the shared module)

`echoes-service-common` is a shared library with: `annotation/`, `aspect/`, `context/` (e.g. user context propagation), `entity/`, `enumeration/`, `exception/`, `util/`.

### Python Echoes-AI Structure

```
Echoes-AI/
├── app/
│   ├── api/          # FastAPI routers: tts, voice, asr, health
│   └── main.py       # App factory, router registration
├── orchestrator/     # Conversation pipeline: planner, router, retriever, generator, safety
├── workers/
│   ├── llm/          # LLM call workers
│   ├── tts/          # CosyVoice2 TTS workers
│   └── asr/          # ASR workers
├── streaming/        # SSE + WebSocket buffer utilities
├── common/           # Shared config, logger
└── data/voice_assets/  # Voice reference audio (.pt model files)
```

The `orchestrator/` is the internal pipeline coordinator (not exposed to frontend). The `app/api/` layer only handles TTS, ASR, and voice reference endpoints.

### LangGraph RAG Structure

```
echoes-langgraph/app/
├── graph/            # LangGraph workflow: nodes, state, workflow definition
├── services/         # Retrieval, reranking, embedding services
├── models/           # Pydantic request/response schemas
└── api/              # FastAPI routes: /search, /rag/chat, /rag/chat/stream
```

Uses Qdrant for vector storage with two collections: `knowledge_chunks` and `conversation_history`.

---

## Key Architectural Constraints

These are enforced project rules from `docs/Echoes_Architecture.md`:

**Single external streaming endpoint — never add another:**
```
POST /conversation/chat-stream
```

**Layer responsibilities:**
- Java is the **only** external-facing layer. Python never exposes SSE to the frontend.
- Python services handle only LLM/TTS/ASR execution. They don't maintain cross-turn session state and don't make routing decisions.
- `seq` (SSE event sequence number) is **only** generated by the conversation service (Java). Never in Python.

**`turn_id` is the idempotency authority:**
- Must be generated by the **client** (UUIDv7/ULID/Snowflake recommended).
- Must not change on retry.
- Server must not generate a fallback `turn_id`.

**URL versioning:** External URLs never include version numbers (`/v1/`, `/v2/`). Versioning is done via `schema_version` / `protocol_version` fields in the payload.

**Internal routing:** All internal service-to-service calls must carry `X-INTERNAL=1`. The gateway hard-blocks `/internal/**` and `/voice/**` routes from external clients.

**Required trace headers** (must propagate end-to-end):
`X-TRACE-ID`, `X-SESSION-ID`, `X-TURN-ID`, `X-USER-ID`

**Voice asset constraint:** When a conversation has a bound `voiceAssetId`, the TTS pipeline must use that voice. Silent fallback to default voice is forbidden — return a `VOICE_NOT_AVAILABLE` error event instead.
