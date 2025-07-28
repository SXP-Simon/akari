import os
import json
from dataclasses import dataclass
from typing import Optional
from akari.bot.services.base import ServiceConfig
from pydantic import BaseModel, Field

class EbooksConfig(BaseModel):
    """电子书插件配置"""
    enable_calibre: bool = Field(default=False, description="是否启用 Calibre 功能")
    calibre_web_url: Optional[str] = Field(default=None, description="Calibre-Web 的 URL 地址")
    enable_zlib: bool = Field(default=True, description="是否启用 Z-Library 功能")
    zlib_email: Optional[str] = Field(default="sxp20061207@163.com", description="Z-Library 的登录邮箱")
    zlib_password: Optional[str] = Field(default="Sxp20061207", description="Z-Library 的登录密码")
    zlib_url: str = Field(default="https://zlibrary.to", description="Z-Library 的 API 地址")

    @classmethod
    def load_from_file(cls, file_path: str) -> "EbooksConfig":
        """从 JSON 文件加载配置"""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    @classmethod
    def load_from_env(cls) -> "EbooksConfig":
        """从环境变量加载配置"""
        return cls(
            enable_calibre=os.getenv("ENABLE_CALIBRE", "False").lower() == "true",
            calibre_web_url=os.getenv("CALIBRE_WEB_URL", None),
            enable_zlib=os.getenv("ENABLE_ZLIB", "True").lower() == "true",
            zlib_email=os.getenv("ZLIB_EMAIL", ""),
            zlib_password=os.getenv("ZLIB_PASSWORD", ""),
            zlib_url=os.getenv("ZLIB_URL", "https://zlibrary.to")
        )

    @classmethod
    def load(cls, file_path: str = "data/ebooks_config.json") -> "EbooksConfig":
        """加载配置，优先从文件加载，其次从环境变量加载，最后使用默认值"""
        if os.path.exists(file_path):
            return cls.load_from_file(file_path)
        return cls.load_from_env()
