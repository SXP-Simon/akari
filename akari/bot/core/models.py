from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from discord import Message, Member, User, Guild, DMChannel

class CommandContext(BaseModel):
    """
    命令上下文数据模型。

    Attributes:
        message (Message): Discord 消息对象。
        args (List[str]): 命令参数列表。
        kwargs (Dict[str, Any]): 关键字参数。
        prefix (str): 命令前缀。
        command_name (str): 命令名称。
        author (Member | User): 命令发起者。
        guild (Optional[Guild]): 所在服务器。
    """
    message: Message
    args: List[str] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    prefix: str
    command_name: str
    author: Member | User
    guild: Optional[Guild] = None
    
    class Config:
        arbitrary_types_allowed = True

class EventData(BaseModel):
    """
    事件基础数据模型。

    Attributes:
        event_type (str): 事件类型。
        timestamp (datetime): 事件时间戳。
        processed (bool): 是否已处理。
    """
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    processed: bool = False
    
    class Config:
        arbitrary_types_allowed = True

class MessageEventData(EventData):
    """
    消息事件数据模型。

    Attributes:
        message_id (int): 消息ID。
        author_id (int): 作者ID。
        content (str): 消息内容。
        is_dm (bool): 是否为私信。
        mentions_bot (bool): 是否提及Bot。
    """
    message_id: int
    author_id: int
    content: str
    is_dm: bool
    mentions_bot: bool = False
    
    @classmethod
    def from_message(cls, message: Message, mentions_bot: bool = False):
        """
        从 Discord 消息对象创建 MessageEventData。

        Args:
            message (Message): Discord 消息对象。
            mentions_bot (bool): 是否提及Bot。
        Returns:
            MessageEventData: 消息事件数据实例。
        """
        return cls(
            event_type="message",
            message_id=message.id,
            author_id=message.author.id,
            content=message.content,
            is_dm=isinstance(message.channel, DMChannel),
            mentions_bot=mentions_bot
        )

class CommandData(BaseModel):
    """
    命令元数据模型。

    Attributes:
        name (str): 命令名称。
        description (str): 命令描述。
        aliases (List[str]): 命令别名。
        usage (Optional[str]): 用法说明。
        cooldown (Optional[int]): 冷却时间（秒）。
        permissions (List[str]): 权限要求。
        is_group (bool): 是否为命令组。
    """
    name: str
    description: str
    aliases: List[str] = Field(default_factory=list)
    usage: Optional[str] = None
    cooldown: Optional[int] = None
    permissions: List[str] = Field(default_factory=list)
    is_group: bool = False
    
    class Config:
        allow_mutation = False 