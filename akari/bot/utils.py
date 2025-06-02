import discord
import datetime
from typing import Optional, Union, Dict, Any

# 定义常用颜色主题
COLORS = {
    "primary": 0x3498db,    # 蓝色
    "success": 0x2ecc71,    # 绿色
    "warning": 0xf39c12,    # 橙色
    "danger": 0xe74c3c,     # 红色
    "info": 0x9b59b6,       # 紫色
    "neutral": 0x34495e,    # 深灰色
    "special": 0x1abc9c     # 青绿色
}

class EmbedBuilder:
    """
    美化的Embed构建器，提供各种预设样式
    """
    @staticmethod
    def create(title: str, description: Optional[str] = None, 
               color_key: str = "primary", footer_text: Optional[str] = None,
               timestamp: bool = True) -> discord.Embed:
        """创建基础Embed"""
        color = COLORS.get(color_key, COLORS["primary"])
        embed = discord.Embed(
            title=title, 
            description=description, 
            color=color
        )
        if timestamp:
            embed.timestamp = datetime.datetime.now()
        if footer_text:
            embed.set_footer(text=footer_text)
        return embed
    
    @staticmethod
    def info(title: str, description: Optional[str] = None) -> discord.Embed:
        """信息型Embed"""
        return EmbedBuilder.create(
            title=f"ℹ️ {title}", 
            description=description, 
            color_key="info"
        )
    
    @staticmethod
    def success(title: str, description: Optional[str] = None) -> discord.Embed:
        """成功型Embed"""
        return EmbedBuilder.create(
            title=f"✅ {title}", 
            description=description, 
            color_key="success"
        )
    
    @staticmethod
    def warning(title: str, description: Optional[str] = None) -> discord.Embed:
        """警告型Embed"""
        return EmbedBuilder.create(
            title=f"⚠️ {title}", 
            description=description, 
            color_key="warning"
        )
    
    @staticmethod
    def error(title: str, description: Optional[str] = None) -> discord.Embed:
        """错误型Embed"""
        return EmbedBuilder.create(
            title=f"❌ {title}", 
            description=description, 
            color_key="danger"
        )
        
    @staticmethod
    def menu(title: str, description: Optional[str] = None, 
             commands: Dict[str, str] = None) -> discord.Embed:
        """菜单型Embed"""
        embed = EmbedBuilder.create(
            title=f"📋 {title}",
            description=description,
            color_key="special"
        )
        
        if commands:
            for cmd_name, cmd_desc in commands.items():
                embed.add_field(
                    name=f"`{cmd_name}`",
                    value=cmd_desc,
                    inline=False
                )
        
        return embed
    
    @staticmethod
    def stats(title: str, description: Optional[str] = None, 
              author: Optional[discord.Member] = None) -> discord.Embed:
        """统计型Embed"""
        embed = EmbedBuilder.create(
            title=f"📊 {title}",
            description=description,
            color_key="primary"
        )
        
        if author:
            embed.set_author(
                name=author.display_name,
                icon_url=author.avatar.url if author.avatar else author.default_avatar.url
            )
        
        return embed

def format_code_block(content: str, language: str = "") -> str:
    """格式化代码块"""
    return f"```{language}\n{content}\n```"

def truncate_text(text: str, max_length: int = 1000) -> str:
    """截断文本，避免超过Discord限制"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." 