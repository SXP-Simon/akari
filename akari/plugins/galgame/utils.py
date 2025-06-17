"""月幕Gal API工具模块

本模块提供了与月幕Gal API交互的工具类和函数。
包含API封装、图片处理和异常处理等功能。

Classes:
    GalGameError: Galgame API异常基类
    NoGameFound: 游戏未找到异常
    NoOaIDFound: 开发商ID未找到异常
    NoGidFound: 游戏ID未找到异常
    VagueFoundError: 模糊搜索异常
    YMGalAPI: 月幕Gal API封装类

Functions:
    download_and_convert_image: 下载并转换图片格式
    init_cache: 初始化缓存目录

Typical usage example:
    api = YMGalAPI()
    token = await api.get_token()
    headers = await api.get_headers(token)
    game_info = await api.search_game(headers, "游戏名")
"""

from __future__ import annotations

import aiohttp
import os
import aiofiles
from PIL import Image
import logging
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import quote
import re
from pathlib import Path
import io
from datetime import datetime
import functools
import json

from .models import GameInfo, DeveloperInfo, Config
from .exceptions import GalGameError, APIError, NoGameFound, ImageError, ConfigError

logger = logging.getLogger(__name__)

def get_temp_dir() -> Path:
    """获取临时目录路径
    
    Returns:
        Path: 临时目录路径
    """
    temp_dir = Path("data/galgame/cache/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

TEMP_DIR = get_temp_dir()

async def init_cache(cache_dir: Path | str) -> Tuple[Path, Path]:
    """初始化缓存目录
    
    Args:
        cache_dir: 缓存根目录路径
        
    Returns:
        Tuple[Path, Path]: 图片缓存目录和临时目录的路径
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建图片缓存目录
    image_cache_dir = cache_dir / "images"
    image_cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建临时目录
    temp_dir = get_temp_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    return image_cache_dir, temp_dir

class GalGameError(Exception):
    """Galgame API基础异常类
    
    所有Galgame相关异常的基类。
    继承自Exception，提供基础的异常处理功能。
    """
    pass

class NoGameFound(GalGameError):
    """游戏未找到异常
    
    当通过精确搜索无法找到指定游戏时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    pass

class NoOaIDFound(GalGameError):
    """开发商ID未找到异常
    
    当无法获取游戏开发商信息时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    pass

class NoGidFound(GalGameError):
    """游戏ID未找到异常
    
    当模糊搜索无法找到任何匹配游戏时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    pass

class VagueFoundError(GalGameError):
    """模糊搜索异常
    
    当模糊搜索过程中发生错误时抛出此异常。
    
    Attributes:
        message: 错误描述信息
    """
    pass

class YMGalAPI:
    """月幕Gal API封装类
    
    提供与月幕Gal API交互的方法封装。
    包括token获取、游戏搜索、开发商信息查询等功能。
    
    Attributes:
        api: API基础URL
        cid: 客户端ID
        c_secret: 客户端密钥
    """
    
    def __init__(self) -> None:
        """初始化API客户端
        
        设置API基础URL和认证信息。
        """
        self.api: str = "https://www.ymgal.games"
        self.cid: str = "ymgal"
        self.c_secret: str = "luna0327"
        
    async def get_token(self) -> str:
        """获取访问令牌
        
        通过客户端凭证获取API访问令牌。
        
        Returns:
            str: API访问令牌
            
        Raises:
            GalGameError: 获取token失败时抛出
        """
        token_url = f"{self.api}/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.cid,
            "client_secret": self.c_secret,
            "scope": "public"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data) as response:
                    result = await response.json()
                    if "access_token" not in result:
                        raise GalGameError("获取token失败")
                    return result["access_token"]
        except Exception as e:
            raise GalGameError(f"获取token时发生错误: {str(e)}")
                
    async def get_headers(self, token: str) -> Dict[str, str]:
        """生成请求头
        
        Args:
            token: API访问令牌
            
        Returns:
            Dict[str, str]: 包含认证信息的请求头
        """
        return {
            "Accept": "application/json;charset=utf-8",
            "Authorization": f"Bearer {token}",
            "version": "1"
        }
        
    async def search_game(
        self, 
        headers: Dict[str, str], 
        keyword: str, 
        similarity: int = 70
    ) -> Dict[str, Any]:
        """精确搜索游戏
        
        Args:
            headers: 请求头
            keyword: 游戏名关键词
            similarity: 相似度阈值(0-100)
            
        Returns:
            Dict[str, Any]: 游戏信息字典
            
        Raises:
            NoGameFound: 未找到匹配的游戏
            GalGameError: API调用失败
        """
        encoded_keyword = quote(keyword)
        url = f"{self.api}/open/archive/search-game?mode=accurate&keyword={encoded_keyword}&similarity={similarity}"
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                res = await response.json()
                code = res["code"]
                
                if code == 0:
                    game_data = res.get("data", {}).get("game", {})
                    result = {
                        "id": game_data.get("gid"),
                        "oaid": game_data.get("developerId"),
                        "mainimg": game_data.get("mainImg"),
                        "name": game_data.get("name"),
                        "rd": game_data.get("releaseDate"),
                        "rest": game_data.get("restricted"),
                        "hc": game_data.get("haveChinese"),
                        "cnname": game_data.get("chineseName"),
                        "intro": game_data.get("introduction")
                    }
                    return {"if_oainfo": False, "result": result}
                elif code == 614:
                    raise NoGameFound(
                        "找不到游戏，请尝试:\n"
                        "1. 使用游戏原名（全名+标点+大小写）\n"
                        "2. 使用模糊搜索命令"
                    )
                else:
                    raise GalGameError(f"API返回错误，代码: {code}")
                    
    async def search_developer(
        self, 
        headers: Dict[str, str],
        gid: int,
        info: Optional[Dict[str, Any]] = None,
        if_oainfo: bool = True
    ) -> Dict[str, Any]:
        """搜索开发商信息
        
        Args:
            headers: 请求头
            gid: 开发商ID
            info: 游戏信息字典(用于合并结果)
            if_oainfo: 是否只返回开发商信息
            
        Returns:
            Dict[str, Any]: 开发商信息或合并后的游戏信息
            
        Raises:
            NoOaIDFound: 未找到开发商信息
        """
        url = f"{self.api}/open/archive?orgId={gid}"
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                res = await response.json()
                code = res["code"]
                
                if code == 0:
                    org_data = res.get("data", {}).get("org", {})
                    if if_oainfo:
                        return {
                            "oaname": org_data.get("name"),
                            "oacn": org_data.get("chineseName"),
                            "istro": org_data.get("introduction"),
                            "country": org_data.get("country")
                        }
                    else:
                        oa = {
                            "oaname": org_data.get("name"),
                            "oacn": org_data.get("chineseName")
                        }
                        result = info | oa
                        del result["oaid"]
                        return result
                else:
                    raise NoOaIDFound(f"获取开发商信息失败，代码: {code}")
                    
    async def vague_search(
        self, 
        headers: Dict[str, str],
        keyword: str,
        page: int = 1,
        size: int = 10
    ) -> str:
        """模糊搜索游戏
        
        Args:
            headers: 请求头
            keyword: 搜索关键词
            page: 页码
            size: 每页结果数
            
        Returns:
            str: 最匹配游戏的名称
            
        Raises:
            NoGidFound: 未找到任何匹配的游戏
            VagueFoundError: 搜索过程发生错误
        """
        encoded_keyword = quote(keyword)
        url = f"{self.api}/open/archive/search-game?mode=list&keyword={encoded_keyword}&pageNum={page}&pageSize={size}"
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                res = await response.json()
                code = res["code"]
                
                if code == 0:
                    results = res.get("data", {}).get("result", [])
                    if results:
                        return results[0].get("name")
                    raise NoGidFound("未找到相关游戏，请尝试其他关键词")
                else:
                    raise VagueFoundError(f"模糊搜索失败，代码: {code}")
                    
    def format_info(self, info: Dict[str, Any]) -> str:
        """格式化游戏信息
        
        将游戏信息格式化为可读的文本格式。
        
        Args:
            info: 游戏信息字典
            
        Returns:
            str: 格式化后的游戏信息文本
        """
        # 处理简介段落
        paragraphs = info["intro"].split("\n")
        if len(paragraphs) < 2:
            paragraphs = info["intro"].split("\n\n")
            
        formatted_paragraphs = []
        for p in paragraphs:
            clean_p = re.sub(r"\s+", "", p.strip())
            if clean_p:
                formatted_paragraphs.append(f"{'':>7}{clean_p}")
                
        intro = "\n".join(formatted_paragraphs)
        
        return (
            f"游戏名：{info['name']}（{info['cnname']}）\n"
            f"会社：{info.get('oaname', 'N/A')}（{info.get('oacn', 'N/A')}）\n"
            f"限制级：{'是' if info['rest'] else '否'}\n"
            f"已有汉化：{'是' if info['hc'] else '否'}\n"
            f"发售日期：{info['rd']}\n\n"
            f"简介：\n{intro}"
        )

async def download_and_convert_image(
    url: str,
    temp_dir: Path = TEMP_DIR,
    output_format: str = "jpeg"
) -> str:
    """下载并转换图片格式
    
    从URL下载图片并转换为指定格式。
    
    Args:
        url: 图片URL
        temp_dir: 临时文件目录
        output_format: 输出格式
        
    Returns:
        str: 转换后的图片文件路径
        
    Raises:
        GalGameError: 下载或转换过程发生错误
    """
    filepath = temp_dir / f"main_{Path(url).name}"
    
    try:
        # 下载图片
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise GalGameError(f"下载图片失败，状态码: {response.status}")
                    
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(await response.read())
                    
        # 转换格式
        output_path = temp_dir / f"change_{Path(url).stem}.jpg"
        with Image.open(filepath) as img:
            if output_format == "jpeg":
                img = img.convert("RGB")
            img.save(output_path, format=output_format.upper())
            
        return str(output_path)
        
    except Exception as e:
        raise GalGameError(f"处理图片失败: {str(e)}")
        
    finally:
        # 清理临时文件
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}")

async def download_image(url: str) -> bytes:
    """下载图片

    Args:
        url: 图片URL

    Returns:
        bytes: 图片二进制数据

    Raises:
        ImageError: 下载或保存图片失败
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise ImageError(f"下载图片失败: HTTP {resp.status}")
                    
                data = await resp.read()
                
                # 验证图片格式
                try:
                    Image.open(io.BytesIO(data))
                except Exception as e:
                    raise ImageError(f"无效的图片格式: {str(e)}")
                    
                return data
                    
    except Exception as e:
        logger.error(f"下载图片失败: {str(e)}")
        raise ImageError(f"下载图片失败: {str(e)}")

async def convert_image(image_data: bytes, format: str = "jpg") -> bytes:
    """转换图片格式

    Args:
        image_data: 图片二进制数据
        format: 目标格式

    Returns:
        bytes: 转换后的图片二进制数据

    Raises:
        ImageError: 转换图片失败
    """
    try:
        # 从二进制数据创建图片对象
        img = Image.open(io.BytesIO(image_data))
        
        # 转换为RGB模式
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 标准化格式名称
        format = format.upper()
        if format == "JPG":
            format = "JPEG"
            
        # 保存为目标格式
        output = io.BytesIO()
        img.save(output, format=format)
        return output.getvalue()
            
    except Exception as e:
        logger.error(f"转换图片失败: {str(e)}")
        raise ImageError(f"转换图片失败: {str(e)}")

def fuzzy_search(
    query: str,
    candidates: List[str],
    min_similarity: int = 50
) -> List[str]:
    """模糊搜索
    
    Args:
        query: 搜索关键词
        candidates: 候选列表
        min_similarity: 最小相似度
        
    Returns:
        List[str]: 匹配结果列表
    """
    results = []
    
    # 转换为小写进行比较
    query = query.lower()
    
    for candidate in candidates:
        # 计算相似度
        similarity = _calculate_similarity(query, candidate.lower())
        
        # 添加到结果列表
        if similarity >= min_similarity:
            results.append(candidate)
            
    return results

def _calculate_similarity(s1: str, s2: str) -> int:
    """计算字符串相似度
    
    使用Levenshtein距离计算相似度。
    
    Args:
        s1: 字符串1
        s2: 字符串2
        
    Returns:
        int: 相似度(0-100)
    """
    # 计算Levenshtein距离
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(
                    dp[i - 1][j] + 1,    # 删除
                    dp[i][j - 1] + 1,    # 插入
                    dp[i - 1][j - 1] + 1 # 替换
                )
                
    # 计算相似度
    max_len = max(m, n)
    if max_len == 0:
        return 100
    else:
        distance = dp[m][n]
        similarity = (1 - distance / max_len) * 100
        return int(similarity)

def validate_config(config: Dict[str, Any]) -> Config:
    """验证配置
    
    Args:
        config: 配置字典
        
    Returns:
        Config: 配置对象
        
    Raises:
        ConfigError: 配置验证失败
    """
    try:
        # 验证配置
        config_obj = Config.model_validate(config)
        
        # 验证缓存目录
        if not config_obj.cache_dir:
            raise ConfigError("缓存目录不能为空")
            
        # 验证API配置
        if not config_obj.api.base_url:
            raise ConfigError("API基础URL不能为空")
            
        if config_obj.api.timeout < 1:
            raise ConfigError("API超时时间必须大于0")
            
        # 验证图片配置
        if not config_obj.image.formats:
            raise ConfigError("图片格式列表不能为空")
            
        if config_obj.image.default_format not in config_obj.image.formats:
            raise ConfigError("默认图片格式必须在支持的格式列表中")
            
        # 验证搜索配置
        if config_obj.search.max_results < 1:
            raise ConfigError("最大结果数必须大于0")
            
        if not 0 <= config_obj.search.min_similarity <= 100:
            raise ConfigError("最小相似度必须在0-100之间")
            
        # 验证缓存配置
        if config_obj.cache.image_max_age_days < 1:
            raise ConfigError("图片缓存最大保存天数必须大于0")
            
        if config_obj.cache.image_max_size_mb < 1:
            raise ConfigError("图片缓存最大大小必须大于0")
            
        if config_obj.cache.api_ttl_seconds < 1:
            raise ConfigError("API缓存生存时间必须大于0")
            
        if config_obj.cache.api_max_entries < 1:
            raise ConfigError("API缓存最大条目数必须大于0")
            
        # 验证冷却配置
        for rule in [config_obj.cooldown.search, config_obj.cooldown.fuzzy, config_obj.cooldown.info]:
            if rule.rate < 1:
                raise ConfigError("冷却规则次数必须大于0")
                
            if rule.per < 1:
                raise ConfigError("冷却规则时间必须大于0")
                
        return config_obj
        
    except Exception as e:
        logger.error(f"配置验证失败: {str(e)}")
        raise ConfigError(f"配置验证失败: {str(e)}")

def format_game_info(game_info: GameInfo, developer_info: Optional[DeveloperInfo] = None) -> str:
    """格式化游戏信息

    Args:
        game_info: 游戏信息
        developer_info: 开发商信息

    Returns:
        str: 格式化后的信息文本
    """
    info = []
    
    # 添加中文名
    if game_info.cnname:
        info.append(f"中文名：{game_info.cnname}")
        
    # 添加发售日期
    if game_info.release_date:
        info.append(f"发售日期：{game_info.release_date}")
        
    # 添加开发商信息
    if developer_info:
        dev_name = developer_info.chinese_name or developer_info.name
        info.append(f"开发商：{dev_name}")
        
    # 添加游戏特性
    features = []
    if game_info.have_chinese:
        features.append("含中文")
    if game_info.restricted:
        features.append("含限制级内容")
    if features:
        info.append("特性：" + "、".join(features))
        
    # 添加简介
    if game_info.introduction:
        info.append(f"\n简介：{game_info.introduction}")
        
    return "\n".join(info)

def retry_async(
    max_retries: int = 3,
    exceptions: Tuple[Exception, ...] = (Exception,)
):
    """异步重试装饰器
    
    Args:
        max_retries: 最大重试次数
        exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    logger.warning(
                        f"第{i + 1}次重试失败: {str(e)}, "
                        f"剩余重试次数: {max_retries - i - 1}"
                    )
                    
            logger.error(f"重试{max_retries}次后仍然失败: {str(last_error)}")
            raise last_error
            
        return wrapper
    return decorator 