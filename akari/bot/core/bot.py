import discord
from discord.ext import commands
from typing import List, Set, Dict, Optional, Callable, Any
import importlib
from pathlib import Path
import datetime
import logging
import sys
import traceback
from akari.bot.core.events import EventHandler
from akari.config.settings import Settings
from functools import wraps
from akari.bot.utils.error_handler import ErrorHandler
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

# =====================
# akari.bot.core.bot
# =====================

"""
MyBot: Discord Bot 主体类

- 支持插件与命令模块自动加载
- 事件注册与统一错误处理
- 命令/命令组注册装饰器
- 运行状态统计

Attributes:
    settings (Settings): 配置对象
    logger (logging.Logger): 日志记录器
    debug_mode (bool): 是否为调试模式
    ...
"""

class MyBot(commands.Bot):
    def __init__(
        self,
        command_prefix: Optional[str] = None,
        intents: Optional[discord.Intents] = None,
        logger: Optional[logging.Logger] = None,
        debug_mode: bool = False
    ):
        """
        初始化 MyBot 实例。

        Args:
            command_prefix (Optional[str]): 命令前缀，若为 None 则从配置读取。
            intents (Optional[discord.Intents]): Discord 事件意图。
            logger (Optional[logging.Logger]): 日志记录器。
            debug_mode (bool): 是否启用调试模式。

        主要完成配置加载、日志系统初始化、事件处理器注册等。
        """
        # 加载配置
        self.settings = Settings.get()
        
        # 设置日志
        self.logger = logger or logging.getLogger("akari")
        if not self.logger.handlers:
            # 添加控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)  # 明确指定输出到stdout
            console_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            
            # 添加文件处理器
            file_handler = logging.FileHandler('bot.log', encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
            
            # 根据调试模式设置日志级别
            self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

        # 初始化 bot
        intents = intents or discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=command_prefix or self.settings.command_prefix,
            intents=intents
        )
        
        # 状态跟踪
        self._command_modules: List[str] = []
        self._plugin_modules: List[str] = []
        self._registered_commands: Set[str] = set()
        self.start_time = datetime.datetime.now()
        self.event_handler = EventHandler(self)
        self._events_registered = False
        self.debug_mode = debug_mode

        # 注册错误处理器
        self.tree.on_error = self.on_app_command_error
        self.add_listener(ErrorHandler.on_command_error, 'on_command_error')

    async def setup_hook(self) -> None:
        """
        Bot 启动时的初始化钩子。

        - 加载命令模块和插件
        - 注册事件处理器
        - 记录初始化日志
        Raises:
            Exception: 初始化失败时抛出
        """
        self.logger.info("正在初始化 bot...")
        
        try:
            # 加载模块
            await self.load_command_modules()
            await self.load_plugins()
            
            # 注册事件处理器
            if not self._events_registered:
                self.add_listener(self.event_handler.on_ready, "on_ready")
                self.add_listener(self.event_handler.on_message, "on_message")
                self.add_listener(self.event_handler.on_error, "on_error")
                self._events_registered = True
                self.logger.info("✅ 事件处理器注册成功")
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            if self.debug_mode:
                self.logger.debug(f"错误堆栈:\n{traceback.format_exc()}")
            raise

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """
        处理应用命令（斜杠命令）错误。

        Args:
            interaction (discord.Interaction): Discord 交互对象。
            error (Exception): 发生的异常。
        """
        error_type = type(error).__name__
        error_msg = str(error)
        error_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        
        # 记录错误
        self.logger.error(f"应用命令错误: {error_type}: {error_msg}")
        if self.debug_mode:
            self.logger.debug(f"错误堆栈:\n{error_trace}")
        
        # 发送错误消息
        embed_data = EmbedData(
            title="❌ 命令执行错误",
            description=f"执行命令时发生错误:\n```py\n{error_type}: {error_msg}```",
            color=EmbedBuilder.THEME.danger,
            fields=[
                {
                    "name": "命令信息",
                    "value": f"命令: `{interaction.command.name if interaction.command else 'Unknown'}`\n用户: {interaction.user}\n频道: {interaction.channel}",
                    "inline": False
                }
            ]
        )
        
        # 在调试模式下添加堆栈跟踪
        if self.debug_mode:
            embed_data.fields.append({
                "name": "错误堆栈",
                "value": f"```py\n{error_trace[:1000]}```",
                "inline": False
            })
        
        try:
            await interaction.response.send_message(
                embed=EmbedBuilder.create(embed_data),
                ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                embed=EmbedBuilder.create(embed_data),
                ephemeral=True
            )

    async def load_command_modules(self) -> None:
        """
        加载 akari.bot.commands 目录下的所有命令模块。
        每个模块需实现 async def setup(bot) 方法。
        加载成功后记录日志。
        """
        commands_dir = Path(__file__).parent.parent / "commands"
        for file in commands_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"akari.bot.commands.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "setup"):
                    await module.setup(self)
                    self._command_modules.append(module_name)
                    self.logger.info(f"✅ 已加载命令模块: {module_name}")
            except Exception as e:
                self.logger.error(f"❌ 加载命令模块 {module_name} 失败: {e}")
                if self.debug_mode:
                    self.logger.debug(f"错误堆栈:\n{traceback.format_exc()}")

    async def load_plugins(self) -> None:
        """
        加载 akari.plugins 目录下的所有插件。
        每个插件需实现 async def setup(bot) 方法。
        加载成功后记录日志。
        """
        plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        for file in plugins_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"akari.plugins.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "setup"):
                    await module.setup(self)
                    self._plugin_modules.append(module_name)
                    self.logger.info(f"✅ 已加载插件: {module_name}")
            except Exception as e:
                self.logger.error(f"❌ 加载插件 {module_name} 失败: {e}")
                if self.debug_mode:
                    self.logger.debug(f"错误堆栈:\n{traceback.format_exc()}")

    async def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载指定插件。

        Args:
            plugin_name (str): 插件名（不含 akari.plugins. 前缀）
        Returns:
            bool: 是否成功
        """
        try:
            await self.reload_extension(f"akari.plugins.{plugin_name}")
            self.logger.info(f"🔄 已重新加载插件: {plugin_name}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 重新加载插件 {plugin_name} 失败: {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载指定插件。

        Args:
            plugin_name (str): 插件名（不含 akari.plugins. 前缀）
        Returns:
            bool: 是否成功
        """
        try:
            await self.unload_extension(f"akari.plugins.{plugin_name}")
            self._plugin_modules.remove(f"akari.plugins.{plugin_name}")
            self.logger.info(f"❌ 已卸载插件: {plugin_name}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 卸载插件 {plugin_name} 失败: {e}")
            return False

    def register_command(self, cmd: commands.Command):
        """
        注册单个命令到 Bot。

        Args:
            cmd (commands.Command): 命令对象
        Returns:
            commands.Command: 注册后的命令对象
        """
        if cmd.name not in self._registered_commands:
            self._registered_commands.add(cmd.name)
            self.add_command(cmd)
            self.logger.info(f"✅ 已注册命令: {cmd.name}")
        return cmd

    def register_command_group(self, group: commands.Group):
        """
        注册命令组到 Bot。

        Args:
            group (commands.Group): 命令组对象
        Returns:
            commands.Group: 注册后的命令组对象
        """
        if group.name not in self._registered_commands:
            self._registered_commands.add(group.name)
            self.add_command(group)
            self.logger.info(f"✅ 已注册命令组: {group.name}")
        return group

    def command(self, **kwargs):
        """
        命令装饰器，自动注册命令。
        用法同 discord.ext.commands.command。
        Returns:
            Callable: 装饰器
        """
        def decorator(func: Callable) -> commands.Command:
            @wraps(func)
            async def wrapper(cog_instance, ctx, *args, **kw):
                return await func(cog_instance, ctx, *args, **kw)
            cmd = commands.command(**kwargs)(wrapper)
            return self.register_command(cmd)
        return decorator

    def group(self, **kwargs):
        """
        命令组装饰器，自动注册命令组。
        用法同 discord.ext.commands.group。
        Returns:
            Callable: 装饰器
        """
        def decorator(func: Callable) -> commands.Group:
            @wraps(func)
            async def wrapper(cog_instance, ctx, *args, **kw):
                return await func(cog_instance, ctx, *args, **kw)
            group = commands.group(**kwargs)(wrapper)
            return self.register_command_group(group)
        return decorator

    def get_uptime(self) -> str:
        """
        获取 Bot 运行时长。
        Returns:
            str: 形如 "X天 X小时 X分钟 X秒"
        """
        delta = datetime.datetime.now() - self.start_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}天 {hours}小时 {minutes}分钟 {seconds}秒"

    def get_command_count(self) -> int:
        """
        获取已注册命令数量。
        Returns:
            int: 命令数量
        """
        return len(self.commands)

    def get_plugin_count(self) -> int:
        """
        获取已加载插件数量。
        Returns:
            int: 插件数量
        """
        return len(self._plugin_modules)

    def get_guild_count(self) -> int:
        """
        获取 Bot 所在服务器数量。
        Returns:
            int: 服务器数量
        """
        return len(self.guilds)

    def get_user_count(self) -> int:
        """
        获取 Bot 可见的用户数量（去重）。
        Returns:
            int: 用户数量
        """
        return len(set(self.get_all_members())) 