import os
import json
import random
import aiohttp
import redis
from .config import MagnetPreviewConfig
from .utils import is_magnet
import logging
import hashlib

logger = logging.getLogger(__name__)

REFERER_OPTIONS = [
    "https://beta.magnet.pics/",
    "https://tmp.nulla.top/",
    "https://pics.magnetq.com/"
]

class MagnetPreviewService:
    def __init__(self):
        self.api_url = MagnetPreviewConfig.API_URL
        self.max_images = MagnetPreviewConfig.MAX_IMAGES
        self.cache_dir = MagnetPreviewConfig.CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

        # 初始化 Redis 连接
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=True
        )
        self.check_redis_connection()

    def check_redis_connection(self):
        try:
            self.redis.ping()
            logger.info("Redis is running")
        except redis.ConnectionError:
            logger.error("Redis is not running. Please start Redis.")
            raise

    def _cache_key(self, link: str) -> str:
        return f"magnet_preview:{hashlib.sha256(link.encode()).hexdigest()}"

    async def get_preview(self, link: str) -> dict | None:
        if not is_magnet(link):
            return None

        cache_key = self._cache_key(link)

        # 检查 Redis 缓存
        try:
            cached_result = self.redis.get(cache_key)
            if cached_result:
                logger.info("Cache hit for magnet link", extra={"link": link})
                return json.loads(cached_result)
        except redis.RedisError as e:
            logger.error("Redis error while fetching cache", extra={"error": str(e)})

        # 如果缓存未命中，调用 API
        result = await self._fetch_preview(link)
        if result:
            try:
                self.redis.setex(cache_key, 86400, json.dumps(result))  # 缓存 24 小时
            except redis.RedisError as e:
                logger.error("Redis error while setting cache", extra={"error": str(e)})

        return result

    async def _fetch_preview(self, link: str) -> dict | None:
        referer_url = random.choice(REFERER_OPTIONS)
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": referer_url
        }
        params = {"url": link}
        api_url = self.api_url.rstrip("/") + "/api/v1/link"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params, ssl=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        if self._validate_api_response(data):
                            return data
                        else:
                            logger.error("API response validation failed", extra={"response": data})
                    else:
                        logger.error("API request failed", extra={"status": response.status, "url": api_url})
        except Exception as e:
            logger.exception("Error fetching magnet preview", exc_info=e)
        return None

    def _validate_api_response(self, data: dict) -> bool:
        return all(key in data for key in {"type", "file_type", "name", "size", "count", "screenshots"})