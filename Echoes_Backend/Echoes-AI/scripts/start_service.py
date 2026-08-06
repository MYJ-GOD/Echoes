#!/usr/bin/env python3
"""
Echoes-AI Service Launcher
Supports both development and conda environment startup
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import socket
import urllib.parse
import urllib.request
import json
try:
    import requests
except Exception:
    requests = None

def setup_environment():
    """Setup environment variables for Echoes-AI"""
    # Offline + No Proxy
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1,0.0.0.0'
    print("Set OFFLINE + NO PROXY mode")

    # Set CosyVoice paths
    project_root = Path(__file__).resolve().parent.parent

    # Check if running in conda environment
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', '')
    if conda_env == 'cosyvoice2':
        print(f"Running in conda environment: {conda_env}")
    else:
        print(f"Warning: Not running in cosyvoice2 conda environment (current: {conda_env})")
        print("Please activate: conda activate cosyvoice2")

    # Set environment variables
    env_vars = {
        'COSYVOICE_REPO_DIR': str(project_root / '..' / 'third_party' / 'CosyVoice'),
        'ECHOES_MODELS_DIR': 'D:\\Echoes\\models',
        'COSYVOICE_MODEL_SUBDIR': 'cosyvoice2-0.5b',
        # Internal Java Voice service base URL (direct service, not gateway)
        'JAVA_API_URL': 'http://127.0.0.1:18083',
        'TTS_SAMPLE_RATE': '24000',
        'PORT': '18085',
        'LOG_LEVEL': 'INFO',
        # Database
        'MYSQL_HOST': 'localhost',
        'MYSQL_PORT': '3306',
        'MYSQL_DATABASE': 'echoes',
        'MYSQL_USER': 'root',
        'MYSQL_PASSWORD': 'root',
        # Redis
        'REDIS_HOST': 'localhost',
        'REDIS_PORT': '6379',
        # OSS
        'OSS_ENDPOINT': 'oss-cn-beijing.aliyuncs.com',
        'OSS_ACCESS_KEY_ID': 'your-aliyun-access-key-id',
        'OSS_ACCESS_KEY_SECRET': 'your-aliyun-access-key-secret',
        'OSS_BUCKET_NAME': 'echoes-sim'
    }

    # Set environment variables
    for key, value in env_vars.items():
        if key == 'JAVA_API_URL':
            # Always force Java internal callback base to voice service, avoid inheriting gateway URL.
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)
        print(f"Set {key}={os.environ[key]}")

def start_service():
    """Start the Echoes-AI service"""
    print("Starting Echoes-AI Service...")

    # Setup environment
    setup_environment()
    # Attempt to register this Echoes-AI instance to Nacos for service discovery.
    # This helps Java services discover echoes-ai via Nacos.
    def _get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def register_to_nacos(service_name=None, port=18085, cluster="DEFAULT"):
        # Allow service name override via env var, default to 'echoes-ai' to match Java client
        if not service_name:
            service_name = os.environ.get("NACOS_SERVICE_NAME", "echoes-ai")

        nacos_addr = os.environ.get("NACOS_SERVER_ADDR", "localhost:8848")
        if nacos_addr.startswith("http://") or nacos_addr.startswith("https://"):
            base = nacos_addr.rstrip("/")
        else:
            base = ("http://" + nacos_addr).rstrip("/")

        namespace = os.environ.get("NACOS_NAMESPACE", "").strip()
        ip = os.environ.get("ECHOES_AI_BIND_IP") or _get_local_ip()

        # 1. Register Instance
        reg_url = f"{base}/nacos/v1/ns/instance"
        params = {
            "serviceName": service_name,
            "ip": ip,
            "port": str(port),
            "clusterName": cluster,
            "enabled": "true",
            "ephemeral": "true"
        }
        if namespace:
            params["namespaceId"] = namespace

        try:
            print(f"Registering to Nacos: {reg_url}")
            if requests:
                resp = requests.post(reg_url, params=params, timeout=5)
                if resp.status_code not in (200, 204):
                    print(f"❌ Nacos registration failed: {resp.text}")
                    return False
            else:
                urllib.request.urlopen(f"{reg_url}?{urllib.parse.urlencode(params)}", timeout=5)
            
            print(f"✅ Registered to Nacos: {service_name} -> {ip}:{port}")
        except Exception as e:
            print(f"Exception during Nacos registration: {e}")
            return False

        # 2. Start Heartbeat Loop (Send Beat to /beat endpoint)
        import threading
        import time

        def heartbeat_loop():
            beat_url = f"{base}/nacos/v1/ns/instance/beat"
            beat_info = {
                "cluster": cluster,
                "ip": ip,
                "port": port,
                "serviceName": service_name
            }
            beat_params = {
                "serviceName": service_name,
                "beat": json.dumps(beat_info)
            }
            if namespace:
                beat_params["namespaceId"] = namespace

            while True:
                time.sleep(5)
                try:
                    if requests:
                        requests.put(beat_url, params=beat_params, timeout=3)
                    else:
                        data = urllib.parse.urlencode(beat_params).encode()
                        req = urllib.request.Request(beat_url, data=data, method='PUT')
                        urllib.request.urlopen(req, timeout=3)
                except Exception:
                    # Silent fail on heartbeat to avoid log spam
                    pass

        t = threading.Thread(target=heartbeat_loop, daemon=True)
        t.start()
        print("❤️ Heartbeat thread started (sending beats to /nacos/v1/ns/instance/beat)")
        return True

    if not register_to_nacos():
        print("Warning: Failed to register to Nacos.")

    # Change to project root
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    # Start uvicorn
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', os.environ.get('PORT', '18085'),
    ]
    # Default to stable mode for streaming endpoints; enable only when explicitly requested.
    if os.environ.get("UVICORN_RELOAD", "0") == "1":
        cmd.append("--reload")

    print(f"Running command: {' '.join(cmd)}")
    print(f"Working directory: {os.getcwd()}")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nService stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"Service failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Echoes-AI Service Launcher')
    parser.add_argument('--check-env', action='store_true', help='Only check environment setup')

    args = parser.parse_args()

    if args.check_env:
        setup_environment()
        print("Environment check complete")
    else:
        start_service()
