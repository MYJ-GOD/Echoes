@echo off

REM ================================
REM Echoes-AI one-click launcher
REM ================================

REM --- Modify these paths as needed ---
set CONDA_HOME=D:\miniconda3
set ECHOES_ROOT=D:\Echoes\Echoes_Backend\Echoes-AI
set ECHOES_MODELS_DIR=D:\Echoes\models
REM Force Nacos registration IP to a reachable address (host LAN IP)
set ECHOES_AI_BIND_IP=127.0.0.1

REM Activate conda environment
call "%CONDA_HOME%\Scripts\activate.bat" cosyvoice2

REM Switch to Echoes-AI directory
cd /d "%ECHOES_ROOT%"

REM Set necessary environment variables
set ECHOES_MODELS_DIR=%ECHOES_MODELS_DIR%
REM Force internal Java API to voice service (18083), not gateway (18080)
set JAVA_API_URL=http://127.0.0.1:18083
set PYTHONUNBUFFERED=1
set UVICORN_RELOAD=0

REM Optional: set Nacos address if needed (uncomment and edit)
set NACOS_SERVER_ADDR=http://127.0.0.1:8848
REM Ensure service name matches what Java VoiceServiceWebClient expects
set NACOS_SERVICE_NAME=echoes-ai

REM Start service (FastAPI + Training Consumer will start automatically)
python scripts\start_service.py

pause


