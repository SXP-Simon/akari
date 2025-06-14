from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from discord.ext import commands

T = TypeVar('T', bound=BaseModel)

class ServiceConfig(BaseModel):
    """
    服务配置基类。

    Attributes:
        enabled (bool): 是否启用服务。
        允许动态扩展其它配置项。
    """
    enabled: bool = True
    
    class Config:
        extra = "allow"

class BaseService:
    """
    服务基类，提供依赖注入和配置管理。

    Attributes:
        bot (commands.Bot): 关联的Bot实例。
        _config (ServiceConfig): 服务配置。
    """
    
    def __init__(self, bot: commands.Bot, config: Optional[ServiceConfig] = None):
        """
        初始化服务基类。
        Args:
            bot (commands.Bot): 关联的Bot实例。
            config (Optional[ServiceConfig]): 服务配置。
        """
        self.bot = bot
        self._config = config or self.get_default_config()
        
    @classmethod
    def get_default_config(cls) -> ServiceConfig:
        """
        获取默认配置。
        Returns:
            ServiceConfig: 默认配置实例。
        """
        return ServiceConfig()
    
    @property
    def config(self) -> ServiceConfig:
        """
        获取服务配置。
        Returns:
            ServiceConfig: 当前服务配置。
        """
        return self._config
    
    @classmethod
    def create(cls, bot: commands.Bot, config: Optional[dict[str, Any]] = None):
        """
        创建服务实例。
        Args:
            bot (commands.Bot): 关联的Bot实例。
            config (Optional[dict]): 配置字典。
        Returns:
            BaseService: 服务实例。
        """
        config_model = cls.get_default_config()
        if config:
            config_model = type(config_model).parse_obj(config)
        return cls(bot, config_model)
    
    async def initialize(self) -> None:
        """
        初始化服务。
        可重写以实现自定义初始化逻辑。
        """
        pass
    
    async def cleanup(self) -> None:
        """
        清理服务资源。
        可重写以实现自定义清理逻辑。
        """
        pass 