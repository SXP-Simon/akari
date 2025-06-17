import discord
from discord.ext import commands
import traceback
import sys
from typing import Dict, Optional
from collections import defaultdict
import time
import asyncio
from .models import MessageEventData, CommandContext
from .decorators import CommandRegistry
from akari.bot.utils.embeds import EmbedBuilder
from akari.bot.services.ai_service import AIService

# =====================
# akari.bot.core.events
# =====================

"""
EventHandler: 事件处理器

- 统一处理 on_ready/on_message/on_error 等事件
- 命令分发与冷却机制
- 消息缓存与清理
- 错误处理与反馈

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

class EventHandler:
    def __init__(self, bot: commands.Bot):
        """
        初始化事件处理器。

        Args:
            bot (commands.Bot): 关联的 Bot 实例。
        """
        self.bot = bot
        self._message_cache: Dict[int, MessageEventData] = {}
        self._command_cooldowns = defaultdict(dict)  # user_id -> {command_name: last_used_time}
        self._lock = asyncio.Lock()
        
    async def _process_command(self, message: discord.Message, content: str) -> bool:
        """
        处理消息中的命令。

        Args:
            message (discord.Message): Discord 消息对象。
            content (str): 消息内容。
        Returns:
            bool: 是否成功处理命令。
        """
        if not content.startswith(self.bot.command_prefix):
            return False
            
        cmd_name = content[len(self.bot.command_prefix):].split()[0]
        cmd_data = CommandRegistry.get_command(cmd_name)
        
        if not cmd_data:
            return False
            
        func, metadata = cmd_data
        
        # 检查冷却时间
        if metadata.cooldown:
            user_cooldowns = self._command_cooldowns[message.author.id]
            last_used = user_cooldowns.get(cmd_name, 0)
            if time.time() - last_used < metadata.cooldown:
                await message.reply(
                    embed=EmbedBuilder.warning(
                        title="命令冷却中",
                        description=f"请等待 {metadata.cooldown - int(time.time() - last_used)} 秒后再试"
                    )
                )
                return True
                
        # 创建上下文
        ctx = CommandContext(
            message=message,
            args=content[len(self.bot.command_prefix + cmd_name):].strip().split(),
            prefix=self.bot.command_prefix,
            command_name=cmd_name,
            author=message.author,
            guild=message.guild if not isinstance(message.channel, discord.DMChannel) else None
        )
        
        try:
            await func(ctx)
            if metadata.cooldown:
                self._command_cooldowns[message.author.id][cmd_name] = time.time()
            return True
        except Exception as e:
            await self._handle_command_error(ctx, e)
            return True
            
    async def _handle_command_error(self, ctx: CommandContext, error: Exception):
        """
        统一的命令错误处理。

        Args:
            ctx (CommandContext): 命令上下文。
            error (Exception): 发生的异常。
        """
        error_trace = traceback.format_exc()
        print(f"[COMMAND ERROR] 命令执行异常：{error}")
        print(error_trace)
        
        try:
            if isinstance(error, commands.MissingPermissions):
                embed = EmbedBuilder.error(
                    title="权限不足",
                    description="您没有执行此命令的权限"
                )
            else:
                embed = EmbedBuilder.error(
                    title="命令执行错误",
                    description=f"执行命令时发生错误：```py\n{str(error)[:1000]}```"
                )
                
            await ctx.message.reply(embed=embed)
        except Exception as e:
            print(f"发送错误消息时出错: {e}")
            
    async def on_ready(self):
        """
        Bot 就绪事件处理。
        设置 Bot 状态并输出登录信息。
        """
        print(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        print("------")
        try:
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.playing,
                    name=f"使用 {self.bot.command_prefix}help 获取帮助"
                ),
                status=discord.Status.online
            )
        except Exception as e:
            print(f"设置状态时出错: {e}")
            
    async def on_message(self, message: discord.Message):
        """
        消息事件处理。
        - 忽略自身消息
        - 处理命令和私聊
        - 缓存消息，清理过期缓存
        Args:
            message (discord.Message): Discord 消息对象。
        """
        # 忽略自己的消息
        if message.author == self.bot.user:
            return
            
        # 使用锁确保消息处理的原子性
        async with self._lock:
            # 检查消息是否已处理
            if message.id in self._message_cache:
                return
                
            # 记录消息
            mentions_bot = self.bot.user.mentioned_in(message)
            event_data = MessageEventData.from_message(message, mentions_bot)
            self._message_cache[message.id] = event_data
            
            # 清理旧缓存
            self._cleanup_old_cache()
            
        # 处理命令
        content = message.content
        if mentions_bot:
            # 移除@提及
            content = content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
            # 直接调用AI回复，无论content是否为空
            ai_service = AIService(self.bot)
            embed = await ai_service.generate_response(message, prompt=content if content else None)
            await message.reply(embed=embed)
            return
            
        # 尝试处理命令
        if await self._process_command(message, content):
            return
            
        # 处理私聊消息
        if isinstance(message.channel, discord.DMChannel) and not content.startswith(self.bot.command_prefix):
            ai_service = AIService(self.bot)
            embed = await ai_service.generate_response(message, prompt=content if content else None)
            await message.reply(embed=embed)
            return
            
    def _cleanup_old_cache(self, max_age: int = 300):
        """
        清理过期的消息缓存。
        Args:
            max_age (int): 最大缓存时间（秒）。
        """
        current_time = time.time()
        self._message_cache = {
            msg_id: data
            for msg_id, data in self._message_cache.items()
            if (current_time - data.timestamp.timestamp()) < max_age
        }
        
    async def on_error(self, event_method: str, *args, **kwargs):
        """
        错误事件处理。
        捕获并反馈事件处理中的异常。
        Args:
            event_method (str): 事件方法名。
            *args: 事件参数。
            **kwargs: 事件关键字参数。
        """
        error_trace = traceback.format_exc()
        print(f"[ERROR] 事件 {event_method} 发生异常：")
        print(error_trace)
        
        try:
            if args and hasattr(args[0], "channel"):
                error_embed = EmbedBuilder.error(
                    title="系统错误",
                    description="处理事件时发生意外错误"
                )
                error_embed.add_field(
                    name="错误详情",
                    value=f"```py\n{str(sys.exc_info()[1])[:1000]}```"
                )
                await args[0].channel.send(embed=error_embed)
        except Exception:
            pass 