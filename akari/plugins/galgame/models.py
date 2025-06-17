"""数据模型模块

本模块定义了插件使用的数据模型。
使用Pydantic进行数据验证。

Classes:
    GameInfo: 游戏信息模型
    DeveloperInfo: 开发商信息模型
    SearchResult: 搜索结果模型
    Config: 插件配置模型
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

class GameInfo(BaseModel):
    """游戏信息模型
    
    Attributes:
        id: 游戏ID
        name: 游戏名称
        cnname: 中文名称
        introduction: 游戏简介
        mainimg: 封面图片URL
        tags: 标签列表
        rating: 评分
        release_date: 发行日期
        have_chinese: 是否有中文
        restricted: 是否有限制级内容
    """
    id: int = Field(..., description="游戏ID")
    name: str = Field(..., description="游戏名称")
    cnname: Optional[str] = Field(None, description="中文名称")
    introduction: Optional[str] = Field(None, description="游戏简介")
    mainimg: Optional[str] = Field(None, description="封面图片URL")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    rating: Optional[float] = Field(None, ge=0, le=10, description="评分")
    release_date: Optional[datetime] = Field(None, description="发行日期")
    have_chinese: bool = Field(False, description="是否有中文")
    restricted: bool = Field(False, description="是否有限制级内容")
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.strftime("%Y-%m-%d")
        }
    }
        
class DeveloperInfo(BaseModel):
    """开发商信息模型
    
    Attributes:
        id: 开发商ID
        name: 开发商名称
        chinese_name: 开发商中文名称
        introduction: 开发商简介
        website: 官网URL
    """
    id: int = Field(..., description="开发商ID")
    name: str = Field(..., description="开发商名称")
    chinese_name: Optional[str] = Field(None, description="开发商中文名称")
    introduction: Optional[str] = Field(None, description="开发商简介")
    website: Optional[str] = Field(None, description="官网URL")
    
class SearchResult(BaseModel):
    """搜索结果模型
    
    Attributes:
        games: 游戏列表
        total: 总数
        page: 当前页码
        pages: 总页数
    """
    games: List[GameInfo] = Field(default_factory=list, description="游戏列表")
    total: int = Field(0, ge=0, description="总数")
    page: int = Field(1, ge=1, description="当前页码")
    pages: int = Field(1, ge=1, description="总页数")
    
class APIConfig(BaseModel):
    """API配置模型
    
    Attributes:
        base_url: API基础URL
        timeout: 请求超时时间(秒)
        user_agent: User-Agent
    """
    base_url: str = Field("https://api.ymgal.games", description="API基础URL")
    timeout: int = Field(30, ge=1, description="请求超时时间(秒)")
    user_agent: str = Field("DiscordBot/1.0", description="User-Agent")
    
class ImageConfig(BaseModel):
    """图片配置模型
    
    Attributes:
        max_size_bytes: 最大图片大小(字节)
        formats: 支持的图片格式
        default_format: 默认图片格式
    """
    max_size_bytes: int = Field(5242880, ge=1, description="最大图片大小(字节)")
    formats: List[str] = Field(
        ["jpg", "png", "webp"],
        description="支持的图片格式"
    )
    default_format: str = Field("jpg", description="默认图片格式")
    
class SearchConfig(BaseModel):
    """搜索配置模型
    
    Attributes:
        max_results: 最大结果数
        min_similarity: 最小相似度
        fuzzy_timeout: 模糊搜索超时时间(秒)
    """
    max_results: int = Field(10, ge=1, description="最大结果数")
    min_similarity: int = Field(50, ge=0, le=100, description="最小相似度")
    fuzzy_timeout: int = Field(10, ge=1, description="模糊搜索超时时间(秒)")
    
class CacheConfig(BaseModel):
    """缓存配置模型
    
    Attributes:
        image_max_age_days: 图片缓存最大保存天数
        image_max_size_mb: 图片缓存最大大小(MB)
        api_ttl_seconds: API缓存生存时间(秒)
        api_max_entries: API缓存最大条目数
    """
    image_max_age_days: int = Field(7, ge=1, description="图片缓存最大保存天数")
    image_max_size_mb: int = Field(100, ge=1, description="图片缓存最大大小(MB)")
    api_ttl_seconds: int = Field(3600, ge=1, description="API缓存生存时间(秒)")
    api_max_entries: int = Field(128, ge=1, description="API缓存最大条目数")
    
class CooldownConfig(BaseModel):
    """冷却配置模型
    
    Attributes:
        search: 搜索命令冷却
        fuzzy: 模糊搜索命令冷却
        info: 信息查询命令冷却
    """
    class CooldownRule(BaseModel):
        """冷却规则"""
        rate: int = Field(1, ge=1, description="次数")
        per: int = Field(5, ge=1, description="时间(秒)")
        
    search: CooldownRule = Field(
        default_factory=lambda: CooldownConfig.CooldownRule(rate=1, per=5),
        description="搜索命令冷却"
    )
    fuzzy: CooldownRule = Field(
        default_factory=lambda: CooldownConfig.CooldownRule(rate=1, per=10),
        description="模糊搜索命令冷却"
    )
    info: CooldownRule = Field(
        default_factory=lambda: CooldownConfig.CooldownRule(rate=1, per=5),
        description="信息查询命令冷却"
    )
    
class Config(BaseModel):
    """插件配置模型
    
    Attributes:
        similarity: 搜索相似度阈值
        cache_dir: 缓存目录
        token_refresh_interval: token刷新间隔(分钟)
        max_retries: 最大重试次数
        api: API配置
        image: 图片配置
        search: 搜索配置
        cache: 缓存配置
        cooldown: 冷却配置
    """
    similarity: int = Field(70, ge=0, le=100, description="搜索相似度阈值")
    cache_dir: str = Field("cache", description="缓存目录")
    token_refresh_interval: int = Field(60, ge=1, description="token刷新间隔(分钟)")
    max_retries: int = Field(3, ge=1, description="最大重试次数")
    api: APIConfig = Field(default_factory=APIConfig, description="API配置")
    image: ImageConfig = Field(default_factory=ImageConfig, description="图片配置")
    search: SearchConfig = Field(default_factory=SearchConfig, description="搜索配置")
    cache: CacheConfig = Field(default_factory=CacheConfig, description="缓存配置")
    cooldown: CooldownConfig = Field(default_factory=CooldownConfig, description="冷却配置")
    
    model_config = {
        "validate_assignment": True,
        "validate_by_name": True,
        "json_encoders": {
            datetime: lambda v: v.strftime("%Y-%m-%d")
        }
    } 