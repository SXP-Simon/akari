"""Galgame 缓存管理模块

本模块提供了图片和API响应的缓存管理功能。
使用LRU缓存策略和文件系统缓存。

Classes:
    ImageCache: 图片缓存管理器
    APICache: API响应缓存管理器

Functions:
    cleanup_cache: 清理过期缓存
    start_cache_cleanup: 启动缓存清理任务
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
import logging
from typing import Optional, Dict, Any, NamedTuple
import json
import aiofiles
import hashlib
import shutil
import time
import os

from .models import GameInfo, DeveloperInfo, SearchResult
from .utils import get_temp_dir

logger = logging.getLogger(__name__)

class CacheStats(NamedTuple):
    """缓存统计信息"""
    size: int  # 当前条目数
    hits: int  # 命中次数
    misses: int  # 未命中次数
    size_bytes: int  # 占用空间(字节)

class ImageCache:
    """图片缓存管理器
    
    管理下载的游戏封面图片缓存。
    使用文件系统存储，支持自动清理过期文件。
    
    Attributes:
        cache_dir: 缓存目录
        max_age: 缓存最大保存时间
        max_size: 最大缓存大小(MB)
        stats: 缓存统计信息
    """
    
    def __init__(
        self,
        cache_dir: Path | str,
        max_age: int = 7,
        max_size: int = 100  # MB
    ) -> None:
        """初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
            max_age: 缓存保存天数
            max_size: 最大缓存大小(MB)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = max_age * 24 * 60 * 60  # 转换为秒
        self.max_size = max_size * 1024 * 1024  # 转换为字节
        self._hits = 0
        self._misses = 0
        
    def get_cache_path(self, url: str) -> Path:
        """获取缓存文件路径
        
        Args:
            url: 图片URL
            
        Returns:
            Path: 缓存文件路径
        """
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.jpg"
        
    async def get(self, url: str) -> Optional[Path]:
        """获取缓存的图片
        
        Args:
            url: 图片URL
            
        Returns:
            Optional[Path]: 缓存文件路径，不存在则返回None
        """
        cache_path = self.get_cache_path(url)
        if not cache_path.exists():
            self._misses += 1
            return None
            
        # 检查是否过期
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(seconds=self.max_age):
            await self.remove(url)
            self._misses += 1
            return None
            
        self._hits += 1
        return cache_path
        
    async def put(self, url: str, data: bytes) -> Path:
        """缓存图片数据
        
        Args:
            url: 图片URL
            data: 图片二进制数据
            
        Returns:
            Path: 缓存文件路径
        """
        # 检查缓存大小
        current_size = await self.get_size()
        if current_size + len(data) > self.max_size:
            await self.cleanup(required_space=len(data))
            
        cache_path = self.get_cache_path(url)
        async with aiofiles.open(cache_path, "wb") as f:
            await f.write(data)
        return cache_path
        
    async def remove(self, url: str) -> None:
        """删除缓存的图片
        
        Args:
            url: 图片URL
        """
        cache_path = self.get_cache_path(url)
        try:
            cache_path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"删除缓存文件失败: {str(e)}")
            
    async def cleanup(self, required_space: int = 0) -> None:
        """清理过期的缓存文件
        
        Args:
            required_space: 需要释放的空间(字节)
        """
        try:
            # 获取所有缓存文件
            cache_files = list(self.cache_dir.glob("*"))
            if not cache_files:
                return
                
            # 按访问时间排序
            cache_files.sort(key=lambda x: x.stat().st_atime)
            
            # 当前时间
            now = time.time()
            
            # 缓存总大小
            total_size = sum(f.stat().st_size for f in cache_files)
            
            for file in cache_files:
                # 文件太旧了
                if now - file.stat().st_atime > self.max_age:
                    file.unlink()
                    total_size -= file.stat().st_size
                    continue
                    
                # 缓存总大小超出限制
                if total_size > self.max_size:
                    file.unlink()
                    total_size -= file.stat().st_size
                    continue
                    
                # 剩余文件都是最近使用的，且总大小在限制内
                break
                
        except Exception as e:
            logger.error(f"清理缓存失败: {str(e)}")
            
    async def get_size(self) -> int:
        """获取当前缓存大小
        
        Returns:
            int: 缓存大小(字节)
        """
        total = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file():
                total += file.stat().st_size
        return total
        
    @property
    def stats(self) -> CacheStats:
        """获取缓存统计信息
        
        Returns:
            CacheStats: 统计信息
        """
        return CacheStats(
            size=len(list(self.cache_dir.glob("*.jpg"))),
            hits=self._hits,
            misses=self._misses,
            size_bytes=sum(f.stat().st_size for f in self.cache_dir.glob("*.jpg"))
        )
        
class APICache:
    """API响应缓存管理器
    
    管理API响应的内存缓存。
    使用LRU策略，支持TTL过期。
    
    Attributes:
        ttl: 缓存生存时间
        maxsize: LRU缓存最大条目数
        stats: 缓存统计信息
    """
    
    def __init__(self, ttl: int = 3600, maxsize: int = 128) -> None:
        """初始化缓存管理器
        
        Args:
            ttl: 缓存生存时间(秒)
            maxsize: 最大缓存条目数
        """
        self.ttl = ttl
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0
        
    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            str: 缓存键
        """
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return hashlib.md5(":".join(key_parts).encode()).hexdigest()
        
    def get(self, *args, **kwargs) -> Optional[Any]:
        """获取缓存的响应
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Optional[Any]: 缓存的响应，不存在或过期则返回None
        """
        key = self._make_key(*args, **kwargs)
        if key not in self._cache:
            self._misses += 1
            return None
            
        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl):
            del self._cache[key]
            self._misses += 1
            return None
            
        self._hits += 1
        return value
        
    def put(self, value: Any, *args, **kwargs) -> None:
        """缓存响应
        
        Args:
            value: 要缓存的响应
            *args: 位置参数
            **kwargs: 关键字参数
        """
        key = self._make_key(*args, **kwargs)
        
        # 如果缓存已满，删除最旧的条目
        if len(self._cache) >= self._maxsize:
            oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
            del self._cache[oldest_key]
            
        self._cache[key] = (value, datetime.now())
        
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        
    @property
    def stats(self) -> CacheStats:
        """获取缓存统计信息
        
        Returns:
            CacheStats: 统计信息
        """
        return CacheStats(
            size=len(self._cache),
            hits=self._hits,
            misses=self._misses,
            size_bytes=sum(len(str(v[0]).encode()) for v in self._cache.values())
        )
        
async def cleanup_cache(cache_dir: Path) -> None:
    """清理所有类型的缓存
    
    Args:
        cache_dir: 缓存根目录
    """
    try:
        # 清理图片缓存
        image_cache = ImageCache(cache_dir / "images")
        await image_cache.cleanup()
        
        # 清理其他可能的缓存文件
        for file in cache_dir.glob("*.tmp"):
            try:
                file.unlink()
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}")
                
        # 记录清理结果
        stats = image_cache.stats
        logger.info(
            f"缓存清理完成 - "
            f"文件数: {stats.size}, "
            f"大小: {stats.size_bytes/1024/1024:.1f}MB, "
            f"命中率: {stats.hits/(stats.hits+stats.misses)*100:.1f}%"
        )
        
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")
        
async def start_cache_cleanup(
    cache_dir: Path | str,
    interval: int = 3600
) -> None:
    """启动缓存清理任务
    
    Args:
        cache_dir: 缓存根目录
        interval: 清理间隔(秒)
    """
    cache_dir = Path(cache_dir)
    
    # 图片缓存目录
    image_cache_dir = cache_dir / "images" 
    image_cache = ImageCache(image_cache_dir)
    
    # 临时目录
    temp_dir = get_temp_dir()
    
    while True:
        try:
            # 清理图片缓存
            await image_cache.cleanup()
            
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                temp_dir.mkdir(parents=True)
                
            logger.info("缓存清理完成")
            
        except Exception as e:
            logger.error(f"缓存清理失败: {str(e)}")
            
        await asyncio.sleep(interval) 