from typing import Optional, Callable, Any, Type, TypeVar, get_type_hints
from dataclasses import dataclass, field
from discord.ext import commands
from pydantic import BaseModel, create_model
import inspect
from .models import CommandContext

T = TypeVar('T', bound=BaseModel)

@dataclass
class CommandInfo:
    """
    命令信息元数据。

    Attributes:
        name (str): 命令名称。
        description (str): 命令描述。
        usage (Optional[str]): 用法说明。
        aliases (list[str]): 命令别名。
        cooldown (Optional[int]): 冷却时间（秒）。
        enabled (bool): 是否启用。
        permissions (list[str]): 权限要求。
    """
    name: str
    description: str
    usage: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    cooldown: Optional[int] = None
    enabled: bool = True
    permissions: list[str] = field(default_factory=list)

class CommandBase:
    """
    命令基类。
    封装命令上下文和参数校验。
    """
    
    def __init__(self, ctx: CommandContext):
        """
        初始化命令基类。
        Args:
            ctx (CommandContext): 命令上下文。
        """
        self.ctx = ctx
        
    @classmethod
    def create_params_model(cls, func: Callable) -> Type[BaseModel]:
        """
        从函数参数创建Pydantic模型。
        Args:
            func (Callable): 命令处理函数。
        Returns:
            Type[BaseModel]: 参数校验模型。
        """
        hints = get_type_hints(func)
        fields = {}
        
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            if name == 'self' or name == 'ctx':
                continue
                
            annotation = hints.get(name, Any)
            default = ... if param.default == param.empty else param.default
            fields[name] = (annotation, default)
            
        return create_model(f"{func.__name__}Params", **fields)
        
    @classmethod
    def command(
        cls,
        name: str,
        description: str,
        usage: Optional[str] = None,
        aliases: Optional[list[str]] = None,
        cooldown: Optional[int] = None,
        permissions: Optional[list[str]] = None
    ) -> Callable:
        """
        命令装饰器。
        Args:
            name (str): 命令名称。
            description (str): 命令描述。
            usage (Optional[str]): 用法说明。
            aliases (Optional[list[str]]): 命令别名。
            cooldown (Optional[int]): 冷却时间（秒）。
            permissions (Optional[list[str]]): 权限要求。
        Returns:
            Callable: 装饰器。
        """
        def decorator(func: Callable) -> Callable:
            cmd_info = CommandInfo(
                name=name,
                description=description,
                usage=usage,
                aliases=aliases or [],
                cooldown=cooldown,
                permissions=permissions or []
            )
            
            # 创建参数验证模型
            params_model = cls.create_params_model(func)
            
            async def wrapper(self: CommandBase, *args: Any, **kwargs: Any) -> Any:
                # 验证参数
                try:
                    params = params_model(**kwargs)
                except Exception as e:
                    await self.ctx.message.reply(f"参数错误: {str(e)}")
                    return
                    
                # 执行命令
                return await func(self, **params.dict())
                
            wrapper.__command_info__ = cmd_info
            return wrapper
            
        return decorator

class CommandRegistry:
    """
    命令注册器。
    负责注册、查找和管理所有命令。
    """
    
    _commands: dict[str, tuple[Type[CommandBase], CommandInfo]] = {}
    
    @classmethod
    def register(cls, command_cls: Type[CommandBase]) -> None:
        """
        注册命令类。
        Args:
            command_cls (Type[CommandBase]): 命令类。
        """
        for name, method in inspect.getmembers(command_cls):
            if hasattr(method, '__command_info__'):
                info: CommandInfo = method.__command_info__
                cls._commands[info.name] = (command_cls, info)
                
                # 注册别名
                for alias in info.aliases:
                    if alias not in cls._commands:
                        cls._commands[alias] = (command_cls, info)
    
    @classmethod
    def get_command(cls, name: str) -> Optional[tuple[Type[CommandBase], CommandInfo]]:
        """
        获取命令。
        Args:
            name (str): 命令名称或别名。
        Returns:
            Optional[tuple[Type[CommandBase], CommandInfo]]: 命令类和元数据。
        """
        return cls._commands.get(name)
    
    @classmethod
    def get_all_commands(cls) -> dict[str, tuple[Type[CommandBase], CommandInfo]]:
        """
        获取所有命令。
        Returns:
            dict[str, tuple[Type[CommandBase], CommandInfo]]: 所有命令映射。
        """
        return cls._commands.copy() 