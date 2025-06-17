from functools import wraps
from typing import Callable, Optional, List, Any
from discord.ext import commands
from .models import CommandData, CommandContext

class CommandRegistry:
    """
    命令注册表。
    负责注册、查找和管理所有基于装饰器的命令。
    """
    _commands: dict = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        aliases: List[str] = None,
        usage: Optional[str] = None,
        cooldown: Optional[int] = None,
        permissions: List[str] = None
    ) -> Callable:
        """
        注册命令。
        Args:
            name (str): 命令名称。
            description (str): 命令描述。
            aliases (List[str]): 命令别名。
            usage (Optional[str]): 用法说明。
            cooldown (Optional[int]): 冷却时间（秒）。
            permissions (List[str]): 权限要求。
        Returns:
            Callable: 装饰器。
        """
        def decorator(func: Callable) -> Callable:
            cmd_data = CommandData(
                name=name,
                description=description,
                aliases=aliases or [],
                usage=usage,
                cooldown=cooldown,
                permissions=permissions or []
            )
            
            @wraps(func)
            async def wrapper(ctx: CommandContext, *args: Any, **kwargs: Any) -> Any:
                return await func(ctx, *args, **kwargs)
            
            cls._commands[name] = (wrapper, cmd_data)
            return wrapper
        return decorator

    @classmethod
    def get_command(cls, name: str) -> Optional[tuple[Callable, CommandData]]:
        """
        获取命令。
        Args:
            name (str): 命令名称。
        Returns:
            Optional[tuple[Callable, CommandData]]: 命令处理函数和元数据。
        """
        return cls._commands.get(name)
    
    @classmethod
    def get_all_commands(cls) -> dict:
        """
        获取所有命令。
        Returns:
            dict: 所有命令映射。
        """
        return cls._commands.copy()

def command(
    name: str,
    description: str,
    aliases: List[str] = None,
    usage: Optional[str] = None,
    cooldown: Optional[int] = None,
    permissions: List[str] = None
) -> Callable:
    """
    FastAPI风格的命令装饰器。

    用法示例:
        @command(
            name="hello",
            description="Say hello to the bot",
            aliases=["hi", "hey"],
            usage="!hello [name]",
            cooldown=5,
            permissions=["send_messages"]
        )
        async def hello_command(ctx: CommandContext):
            await ctx.message.reply(f"Hello {ctx.author.name}!")
    Args:
        name (str): 命令名称。
        description (str): 命令描述。
        aliases (List[str]): 命令别名。
        usage (Optional[str]): 用法说明。
        cooldown (Optional[int]): 冷却时间（秒）。
        permissions (List[str]): 权限要求。
    Returns:
        Callable: 装饰器。
    """
    return CommandRegistry.register(
        name=name,
        description=description,
        aliases=aliases,
        usage=usage,
        cooldown=cooldown,
        permissions=permissions
    ) 

def group(
    name: str,
    description: str,
    aliases: List[str] = None,
    usage: Optional[str] = None,
    cooldown: Optional[int] = None,
    permissions: List[str] = None
) -> Callable:
    """
    FastAPI风格的命令组装饰器。
    Args:
        name (str): 命令组名称。
        description (str): 命令组描述。
        aliases (List[str]): 命令组别名。
        usage (Optional[str]): 用法说明。
        cooldown (Optional[int]): 冷却时间（秒）。
        permissions (List[str]): 权限要求。
    Returns:
        Callable: 装饰器。
    """
    return CommandRegistry.register_group(
        name=name,
        description=description,
        aliases=aliases,
        usage=usage,
        cooldown=cooldown,
        permissions=permissions
    )