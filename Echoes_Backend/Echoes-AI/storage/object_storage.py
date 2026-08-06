"""
对象存储模块
提供本地文件系统存储（用于开发/测试环境）
生产环境可替换为 OSS/S3 实现
"""
import os
import shutil
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# 存储根目录
STORAGE_ROOT = Path("D:/Echoes/models/storage")

# Java API 地址（用于获取签名 URL）
JAVA_API_URL = os.environ.get("JAVA_API_URL", "http://localhost:18083")


def init_storage():
    """初始化存储目录"""
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


init_storage()


def _get_signed_url_from_java(storage_key: str) -> Optional[str]:
    """
    从 Java 服务获取 OSS 签名 URL
    
    Args:
        storage_key: OSS 存储路径
        
    Returns:
        签名 URL 或 None
    """
    try:
        url = f"{JAVA_API_URL}/internal/voice/assets/ref/signed?storage_key={storage_key}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("url")
    except Exception as e:
        print(f"Failed to get signed URL from Java: {e}")
    return None


def download_file(storage_key: str, local_path: str) -> str:
    """
    下载文件到本地
    支持从 OSS 下载或从本地复制
    
    Args:
        storage_key: 存储键（OSS 路径如 voice_refs/xxx.wav 或本地路径）
        local_path: 本地目标路径
        
    Returns:
        本地文件路径
    """
    # 如果 storage_key 是本地绝对路径，直接返回
    if os.path.isabs(storage_key) and os.path.exists(storage_key):
        return storage_key
    
    # 如果 storage_key 是本地相对路径
    source_path = STORAGE_ROOT / storage_key
    if source_path.exists():
        # 确保目标目录存在
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        # 复制文件
        shutil.copy2(source_path, local_path)
        return local_path
    
    # 如果是 OSS 路径（以 voice_refs/ 或 voice_models/ 开头），尝试从 OSS 下载
    if storage_key.startswith("voice_refs/") or storage_key.startswith("voice_models/"):
        # 尝试从 Java 获取签名 URL
        signed_url = _get_signed_url_from_java(storage_key)
        if signed_url:
            try:
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                response = requests.get(signed_url, timeout=60)
                if response.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(response.content)
                    print(f"Downloaded from OSS: {storage_key} -> {local_path}")
                    return local_path
            except Exception as e:
                print(f"Failed to download from OSS: {e}")
        
        # 无法获取签名 URL，下载失败
        raise Exception(f"Failed to download from OSS: cannot get signed URL for {storage_key}")
    
    raise FileNotFoundError(f"Storage key not found: {storage_key}")


def upload_file(local_path: str, storage_key: str) -> str:
    """
    上传本地文件到存储
    支持上传到 OSS 或本地存储
    
    Args:
        local_path: 本地文件路径
        storage_key: 目标存储键
        
    Returns:
        存储键
    """
    source_path = Path(local_path)
    
    if not source_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")
    
    # 上传到本地存储
    dest_path = STORAGE_ROOT / storage_key
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    print(f"Uploaded to local: {local_path} -> {dest_path}")
    return storage_key


def get_presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    """
    获取预签名 URL（本地环境直接返回文件路径）
    
    Args:
        storage_key: 存储键
        expires_in: 过期时间（秒）
        
    Returns:
        URL 或本地文件路径
    """
    # 本地环境返回本地文件 URL
    file_path = STORAGE_ROOT / storage_key
    
    if not file_path.exists():
        # 尝试直接作为本地路径
        if os.path.exists(storage_key):
            file_path = Path(storage_key)
    
    # 返回 file:// URL
    return f"file:///{file_path.as_posix()}"


def delete_file(storage_key: str) -> bool:
    """
    删除存储的文件
    
    Args:
        storage_key: 存储键
        
    Returns:
        是否删除成功
    """
    file_path = STORAGE_ROOT / storage_key
    
    if file_path.exists():
        file_path.unlink()
        return True
    return False


def file_exists(storage_key: str) -> bool:
    """
    检查文件是否存在
    
    Args:
        storage_key: 存储键
        
    Returns:
        文件是否存在
    """
    file_path = STORAGE_ROOT / storage_key
    return file_path.exists()

