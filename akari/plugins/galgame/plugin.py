"""Galgame Discord插件

本插件提供了查询Galgame信息的功能。
使用月幕Gal API获取游戏数据。

Commands:
    !gal search: 精确搜索游戏
    !gal info: 查看游戏详细信息
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import aiohttp
import ssl
import certifi
import discord
from discord.ext import commands
import functools
import time
import io
import os
from urllib.parse import quote

from .models import GameInfo, DeveloperInfo, SearchResult, Config
from .exceptions import GalGameError, APIError, NoGameFound, ImageError, ConfigError
from .cache import ImageCache, APICache, start_cache_cleanup
from .utils import (
    get_temp_dir,
    download_image,
    convert_image,
    fuzzy_search,
    validate_config,
    format_game_info,
    retry_async
)

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "similarity": 70,
    "cache_dir": "cache",
    "token_refresh_interval": 60,
    "max_retries": 3,
    "api": {
        "base_url": "https://api.ymgal.games",
        "timeout": 30,
        "user_agent": "DiscordBot/1.0"
    },
    "image": {
        "max_size_bytes": 5242880,
        "formats": ["jpg", "png", "webp"],
        "default_format": "jpg"
    },
    "search": {
        "max_results": 10,
        "min_similarity": 50,
        "fuzzy_timeout": 10
    },
    "cache": {
        "image_max_age_days": 7,
        "image_max_size_mb": 100,
        "api_ttl_seconds": 3600,
        "api_max_entries": 128
    },
    "cooldown": {
        "search": {
            "rate": 1,
            "per": 5
        },
        "fuzzy": {
            "rate": 1,
            "per": 10
        },
        "info": {
            "rate": 1,
            "per": 5
        }
    }
}

def log_command(func):
    """命令日志装饰器"""
    @functools.wraps(func)
    async def wrapper(self, ctx: commands.Context, *args, **kwargs):
        start_time = time.time()
        command_name = ctx.command.name
        
        logger.info(
            f"执行命令 {command_name} - "
            f"用户: {ctx.author} ({ctx.author.id}), "
            f"参数: args={args}, kwargs={kwargs}"
        )
        
        try:
            result = await func(self, ctx, *args, **kwargs)
            elapsed = time.time() - start_time
            
            logger.info(
                f"命令 {command_name} 执行完成 - "
                f"耗时: {elapsed:.2f}秒"
            )
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"命令 {command_name} 执行失败 - "
                f"耗时: {elapsed:.2f}秒, "
                f"错误: {str(e)}"
            )
            raise
            
    return wrapper

class GalGame(commands.Cog):
    """Galgame查询插件
    
    提供游戏搜索和信息查询功能。
    
    Attributes:
        bot: Discord机器人实例
        config: 插件配置
        session: aiohttp会话
        data_dir: 数据目录
    """
    
    def __init__(self, bot: commands.Bot) -> None:
        """初始化插件
        
        Args:
            bot: Discord机器人实例
        """
        self.bot = bot
        self.data_dir = self._init_data_dir()
        self.config = self._load_config()
        
        # API配置
        self.api_base = "https://www.ymgal.games"
        self.client_id = "ymgal"
        self.client_secret = "luna0327"
        self._token = None
        self._token_expires = 0
        
        # 配置SSL上下文
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # 创建带SSL配置的session
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            force_close=True,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,
            limit=10
        )
        
        # 创建session并配置headers
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Accept': 'application/json;charset=utf-8',
                'User-Agent': self.config.api.user_agent,
                'version': '1'
            }
        )
        
        # 初始化缓存
        cache_dir = self.data_dir / self.config.cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建图片缓存目录
        image_cache_dir = cache_dir / "images"
        image_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化缓存管理器
        self.image_cache = ImageCache(
            cache_dir=image_cache_dir,
            max_age=self.config.cache.image_max_age_days,
            max_size=self.config.cache.image_max_size_mb
        )
        
        self.api_cache = APICache(
            ttl=self.config.cache.api_ttl_seconds,
            maxsize=self.config.cache.api_max_entries
        )
        
        # 启动缓存清理任务
        asyncio.create_task(
            start_cache_cleanup(cache_dir, self.config.token_refresh_interval * 60)
        )
        
        logger.info(
            f"插件初始化完成 - "
            f"数据目录: {self.data_dir}, "
            f"缓存目录: {cache_dir}, "
            f"配置: {self.config.model_dump()}"
        )
        
    def _init_data_dir(self) -> Path:
        """初始化数据目录
        
        Returns:
            Path: 数据目录路径
        """
        # 获取插件数据目录
        data_dir = Path("data/galgame")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建配置文件
        config_file = data_dir / "config.json"
        if not config_file.exists():
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        
        return data_dir
        
    def _load_config(self) -> Config:
        """加载配置
        
        Returns:
            Config: 配置对象
            
        Raises:
            ConfigError: 加载或验证配置失败
        """
        try:
            config_file = self.data_dir / "config.json"
            with open(config_file, encoding="utf-8") as f:
                config = json.load(f)
            
            return validate_config(config)
            
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            logger.info("使用默认配置")
            return validate_config(DEFAULT_CONFIG)
            
    async def cog_unload(self) -> None:
        """插件卸载时的清理"""
        await self.session.close()
        logger.info("插件已卸载")
        
    @commands.group(name="gal")
    async def gal(self, ctx: commands.Context) -> None:
        """Galgame查询命令组"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Galgame 查询帮助",
                description="""
**可用子命令：**
- `/gal search <游戏名>`：精确查询游戏信息
- `/gal info <游戏ID>`：查看游戏详细信息

示例：
- `/gal search 千恋万花`
- `/gal info 22374`
                """,
                color=discord.Color.blue()
            )
            embed.set_footer(text="Powered by 月幕Gal API | 如有疑问请联系Bot管理员")
            await ctx.send(embed=embed)
            
    @gal.command()
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @log_command
    async def search(self, ctx: commands.Context, *, name: str) -> None:
        """精确搜索游戏
        
        Args:
            ctx: 命令上下文
            name: 游戏名称
        """
        try:
            # 发送等待消息
            embed_loading = discord.Embed(
                title="🔍 正在搜索游戏信息...",
                description=f"关键词：`{name}`\n请稍候...",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed_loading)
            # 搜索游戏
            game = await self.search_game(name)
            # 获取开发商信息
            developer_id = game.get("developerId")
            if developer_id:
                path = f"/open/archive?orgId={developer_id}"
                try:
                    dev_result = await self._api_request("GET", path)
                    if dev_result["code"] == 0:
                        developer = dev_result["data"]["org"]
                    else:
                        developer = None
                except Exception:
                    developer = None
            else:
                developer = None
            # 创建游戏信息
            game_info = GameInfo(
                id=game.get("gid"),
                name=game.get("name", "未知"),
                cnname=game.get("chineseName"),
                mainimg=game.get("mainImg"),
                release_date=game.get("releaseDate"),
                restricted=game.get("restricted", False),
                have_chinese=game.get("haveChinese", False),
                introduction=game.get("introduction", "暂无简介"),
                tags=game.get("tags", [])
            )
            if developer:
                dev_info = DeveloperInfo(
                    id=developer_id,
                    name=developer.get("name", "未知"),
                    chinese_name=developer.get("chineseName"),
                    introduction=developer.get("introduction")
                )
            else:
                dev_info = None
            # 下载并转换封面图片
            if game_info.mainimg:
                try:
                    image_data = await download_image(game_info.mainimg)
                    image_data = await convert_image(image_data)
                except ImageError as e:
                    logger.error(f"处理图片失败: {str(e)}")
                    image_data = None
            else:
                image_data = None
            # 创建嵌入消息
            embed = discord.Embed(
                title=f"🎮 {game_info.name}",
                description=format_game_info(game_info, dev_info),
                color=discord.Color.green()
            )
            embed.add_field(name="游戏ID", value=f"`{game_info.id}`", inline=True)
            if game_info.cnname and game_info.cnname != game_info.name:
                embed.add_field(name="中文名", value=game_info.cnname, inline=True)
            if game_info.release_date:
                embed.add_field(name="发行日期", value=str(game_info.release_date), inline=True)
            if game_info.tags:
                embed.add_field(name="标签", value=", ".join(game_info.tags), inline=False)
            if image_data:
                file = discord.File(io.BytesIO(image_data), "cover.jpg")
                embed.set_image(url="attachment://cover.jpg")
                await message.delete()
                await ctx.send(embed=embed, file=file)
            else:
                await message.edit(content=None, embed=embed)
            logger.info(
                f"搜索成功 - "
                f"游戏: {game_info.name} ({game_info.id}), "
                f"开发商: {dev_info.name if dev_info else 'N/A'}"
            )
        except NoGameFound as e:
            embed = discord.Embed(
                title="❌ 未找到游戏",
                description=f"没有找到与 `{name}` 相关的游戏。\n\n请尝试：\n- 检查关键词拼写\n- 使用更完整或更准确的游戏名\n- 直接用日文原名/英文名\n",
                color=discord.Color.red()
            )
            embed.set_footer(text="如有疑问可联系Bot管理员。")
            await message.edit(content=None, embed=embed)
            logger.info(f"未找到游戏 - 关键词: {name}")
        except Exception as e:
            embed = discord.Embed(
                title="⚠️ 搜索失败",
                description=f"搜索过程中出现错误：{str(e)}",
                color=discord.Color.orange()
            )
            await message.edit(content=None, embed=embed)
            logger.error(f"搜索游戏失败: {str(e)}")
            
    @gal.command()
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    @log_command
    async def info(self, ctx: commands.Context, id: int) -> None:
        """查看游戏详细信息
        
        Args:
            ctx: 命令上下文
            id: 游戏ID
        """
        try:
            embed_loading = discord.Embed(
                title="ℹ️ 正在获取游戏详细信息...",
                description=f"游戏ID：`{id}`\n请稍候...",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed_loading)
            # 获取游戏信息
            async with self.session.get(
                f"https://api.ymgal.games/game/{id}"
            ) as resp:
                if resp.status != 200:
                    raise APIError(f"API请求失败: HTTP {resp.status}")
                data = await resp.json()
                if not data["success"]:
                    raise APIError(data["message"], data["code"])
                game_info = GameInfo(**data["data"]["game"])
                developer = DeveloperInfo(**data["data"]["developer"])
            # 下载并转换封面图片
            image_data = await download_image(game_info.mainimg, self.session)
            image_data = await convert_image(image_data)
            # 创建嵌入消息
            embed = discord.Embed(
                title=f"📖 {game_info.name} 详细信息",
                description=game_info.introduction or "暂无简介",
                color=discord.Color.purple()
            )
            embed.add_field(name="游戏ID", value=f"`{game_info.id}`", inline=True)
            if game_info.cnname and game_info.cnname != game_info.name:
                embed.add_field(name="中文名", value=game_info.cnname, inline=True)
            if game_info.release_date:
                embed.add_field(name="发行日期", value=str(game_info.release_date), inline=True)
            if game_info.tags:
                embed.add_field(name="标签", value=", ".join(game_info.tags), inline=False)
            if developer:
                embed.add_field(name="开发商", value=developer.name, inline=True)
            if image_data:
                file = discord.File(io.BytesIO(image_data), "cover.jpg")
                embed.set_image(url="attachment://cover.jpg")
                await message.delete()
                await ctx.send(embed=embed, file=file)
            else:
                await message.edit(content=None, embed=embed)
            logger.info(
                f"获取游戏信息成功 - "
                f"游戏: {game_info.name} ({game_info.id}), "
                f"开发商: {developer.name if developer else 'N/A'}"
            )
        except Exception as e:
            embed = discord.Embed(
                title="⚠️ 获取信息失败",
                description=f"获取游戏详细信息时出错：{str(e)}",
                color=discord.Color.orange()
            )
            await message.edit(content=None, embed=embed)
            logger.error(f"获取游戏信息失败: {str(e)}")
            
    @search.error
    @info.error
    async def command_error(self, ctx: commands.Context, error: Exception) -> None:
        """命令错误处理
        
        Args:
            ctx: 命令上下文
            error: 异常对象
        """
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ 命令冷却中",
                description=f"请在 {error.retry_after:.1f} 秒后重试。",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"命令执行出错: {str(error)}")
            embed = discord.Embed(
                title="❌ 命令执行失败",
                description=f"{str(error)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            
    async def get_token(self) -> str:
        """获取API访问令牌
        
        Returns:
            str: 访问令牌
        """
        now = time.time()
        if self._token and now < self._token_expires:
            return self._token
            
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "public"
        }
        
        async with self.session.post(f"{self.api_base}/oauth/token", data=data) as resp:
            if resp.status != 200:
                raise APIError(f"获取token失败: HTTP {resp.status}")
            result = await resp.json()
            self._token = result["access_token"]
            self._token_expires = now + result.get("expires_in", 3600)
            return self._token
            
    async def _api_request(self, method: str, path: str, **kwargs) -> Any:
        """发送API请求
        
        Args:
            method: 请求方法
            path: API路径
            **kwargs: 请求参数
            
        Returns:
            Any: API响应数据
        """
        token = await self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.api_base}{path}"
        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status != 200:
                raise APIError(f"API请求失败: HTTP {resp.status}")
            return await resp.json()
            
    async def search_game(self, name: str, fuzzy: bool = False) -> Dict[str, Any]:
        """搜索游戏
        
        Args:
            name: 游戏名称
            fuzzy: 是否模糊搜索
            
        Returns:
            Dict[str, Any]: 游戏信息
        """
        mode = "list" if fuzzy else "accurate"
        path = f"/open/archive/search-game?mode={mode}&keyword={quote(name)}&similarity={self.config.similarity}"
        
        try:
            result = await self._api_request("GET", path)
            if result["code"] != 0:
                if result["code"] == 614:
                    raise NoGameFound("未找到游戏，请尝试使用游戏原名或模糊搜索")
                raise APIError(f"API错误: {result['code']}")
                
            if fuzzy:
                games = result.get("data", {}).get("result", [])
                if not games:
                    raise NoGameFound("未找到匹配的游戏")
                return games[0]
            
            return result["data"]["game"]
            
        except aiohttp.ClientError as e:
            logger.error(f"API请求失败: {e}")
            raise APIError("API连接失败，请稍后重试")

async def setup(bot: commands.Bot) -> None:
    """加载插件
    
    Args:
        bot: Discord机器人实例
    """
    await bot.add_cog(GalGame(bot)) 