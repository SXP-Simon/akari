from discord import Embed, Member
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class EmbedTheme(BaseModel):
    """
    Embed主题配置。

    Attributes:
        primary (int): 主色调。
        success (int): 成功色。
        warning (int): 警告色。
        danger (int): 错误色。
        error (int): 错误色（danger的别名）。
        info (int): 信息色。
        neutral (int): 中性色。
        special (int): 特殊色。
    """
    primary: int = Field(default=0x3498db)    # 蓝色
    success: int = Field(default=0x2ecc71)    # 绿色
    warning: int = Field(default=0xf39c12)    # 橙色
    danger: int = Field(default=0xe74c3c)     # 红色
    info: int = Field(default=0x9b59b6)       # 紫色
    neutral: int = Field(default=0x34495e)    # 深灰色
    special: int = Field(default=0x1abc9c)    # 青绿色

    @property
    def error(self) -> int:
        """错误色（danger的别名）"""
        return self.danger

    class Config:
        frozen = True

class EmbedData(BaseModel):
    """
    Embed数据模型。

    Attributes:
        title (str): 标题。
        description (Optional[str]): 描述。
        color (int): 颜色。
        footer_text (Optional[str]): 页脚文本。
        timestamp (bool): 是否显示时间戳。
        fields (list[dict]): 附加字段。
        author (Optional[dict]): 作者信息。
    """
    title: str
    description: Optional[str] = None
    color: int = Field(default=0x3498db)
    footer_text: Optional[str] = None
    timestamp: bool = True
    fields: list[dict[str, Any]] = Field(default_factory=list)
    author: Optional[dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True

class EmbedBuilder:
    """
    增强的Embed构建器。
    提供多种类型的Embed快捷创建方法。
    """
    
    THEME = EmbedTheme()
    
    @classmethod
    def create(cls, data: EmbedData) -> Embed:
        """
        从EmbedData创建Embed。
        Args:
            data (EmbedData): 数据模型。
        Returns:
            Embed: Discord Embed对象。
        """
        embed = Embed(
            title=data.title,
            description=data.description,
            color=data.color
        )
        
        if data.timestamp:
            embed.timestamp = datetime.now()
            
        if data.footer_text:
            embed.set_footer(text=data.footer_text)
            
        for field in data.fields:
            embed.add_field(**field)
            
        if data.author:
            embed.set_author(**data.author)
            
        return embed

    @classmethod
    def info(cls, title: str, description: Optional[str] = None) -> Embed:
        """
        信息型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
        Returns:
            Embed: 信息Embed。
        """
        return cls.create(EmbedData(
            title=f"ℹ️ {title}",
            description=description,
            color=cls.THEME.info
        ))

    @classmethod
    def success(cls, title: str, description: Optional[str] = None) -> Embed:
        """
        成功型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
        Returns:
            Embed: 成功Embed。
        """
        return cls.create(EmbedData(
            title=f"✅ {title}",
            description=description,
            color=cls.THEME.success
        ))

    @classmethod
    def warning(cls, title: str, description: Optional[str] = None) -> Embed:
        """
        警告型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
        Returns:
            Embed: 警告Embed。
        """
        return cls.create(EmbedData(
            title=f"⚠️ {title}",
            description=description,
            color=cls.THEME.warning
        ))

    @classmethod
    def error(cls, title: str, description: Optional[str] = None) -> Embed:
        """
        错误型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
        Returns:
            Embed: 错误Embed。
        """
        return cls.create(EmbedData(
            title=f"❌ {title}",
            description=description,
            color=cls.THEME.danger
        ))

    @classmethod
    def menu(cls, title: str, description: Optional[str] = None,
             commands: Optional[Dict[str, str]] = None) -> Embed:
        """
        菜单型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
            commands (Optional[Dict[str, str]]): 命令说明字典。
        Returns:
            Embed: 菜单Embed。
        """
        data = EmbedData(
            title=f"📋 {title}",
            description=description,
            color=cls.THEME.special
        )
        
        if commands:
            for cmd_name, cmd_desc in commands.items():
                data.fields.append({
                    "name": f"`{cmd_name}`",
                    "value": cmd_desc,
                    "inline": False
                })
        
        return cls.create(data)

    @classmethod
    def stats(cls, title: str, description: Optional[str] = None,
              author: Optional[Member] = None) -> Embed:
        """
        统计型Embed。
        Args:
            title (str): 标题。
            description (Optional[str]): 描述。
            author (Optional[Member]): 作者。
        Returns:
            Embed: 统计Embed。
        """
        data = EmbedData(
            title=f"📊 {title}",
            description=description,
            color=cls.THEME.primary
        )
        
        if author:
            data.author = {
                "name": author.display_name,
                "icon_url": str(author.avatar.url if author.avatar else author.default_avatar.url)
            }
        
        return cls.create(data)

def format_code_block(content: str, language: str = "") -> str:
    """
    格式化代码块。
    Args:
        content (str): 代码内容。
        language (str): 代码语言。
    Returns:
        str: 格式化后的代码块字符串。
    """
    return f"```{language}\n{content}\n```"

def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    截断文本，避免超过Discord限制。
    Args:
        text (str): 原始文本。
        max_length (int): 最大长度。
    Returns:
        str: 截断后的文本。
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..." 