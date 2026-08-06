from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from time import perf_counter

from app.api.health import router as health_router
from app.api.tts import router as tts_router
from app.api.voice import router as voice_router
from app.api.asr import router as asr_router
from common.config import settings
from common.logger import logger

def create_app() -> FastAPI:
    app = FastAPI(title="Echoes-AI", version="0.2.0")
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all for dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health_router)
    # Use unversioned routes for internal calls
    app.include_router(tts_router)
    # Register Voice Router (for reference audio management)
    app.include_router(voice_router, prefix="/internal")
    # Register ASR Router (for audio transcription)
    app.include_router(asr_router, prefix="/internal") 

    @app.middleware("http")
    async def request_log_middleware(request, call_next):
        path = request.url.path
        should_log = (
            path.startswith("/tts/")
            or path.startswith("/internal/voice/")
            or path.startswith("/internal/asr/")
        )
        start = perf_counter()
        response = await call_next(request)
        if should_log:
            cost_ms = (perf_counter() - start) * 1000
            logger.info(
                f"HTTP {request.method} {path} -> {response.status_code} "
                f"({cost_ms:.1f}ms), x_internal={request.headers.get('x-internal')}, "
                f"x_user_id={request.headers.get('x-user-id')}"
            )
        return response

    @app.on_event("startup")
    async def startup_event():
        print(f"Starting Echoes-AI on port {settings.PORT}")
        print(f"JAVA_API_URL={os.environ.get('JAVA_API_URL', 'http://localhost:18083')}")
        
        # Initialize CosyVoice model
        print("Initializing CosyVoice model...")
        try:
            from workers.tts.cosyvoice_worker import cosyvoice_worker
            cosyvoice_worker.initialize()
            print("CosyVoice model initialized successfully")
        except Exception as e:
            print(f"Failed to initialize CosyVoice model: {e}")
            raise
        
        # Start Training Task Consumer (in background thread)
        print("Starting Training Task Consumer...")
        try:
            import threading
            from mq.consumer import TrainingTaskConsumer
            
            def run_consumer():
                consumer = TrainingTaskConsumer(
                    redis_host="localhost",
                    redis_port=6379,
                    stream_key="voice-training-tasks",
                    group_name="voice-training-group",
                    consumer_name="echoes-ai-consumer",
                    java_api_base=os.environ.get("JAVA_API_URL", "http://localhost:18083")
                )
                consumer.start(blocking=True)
            
            consumer_thread = threading.Thread(target=run_consumer, daemon=True)
            consumer_thread.start()
            print("Training Task Consumer started successfully")
        except Exception as e:
            print(f"Failed to start Training Task Consumer: {e}")
            # Don't raise, consumer failure shouldn't block the service

    return app

app = create_app()
