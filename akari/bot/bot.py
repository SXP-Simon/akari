import discord
from discord.ext import commands
from typing import List
import importlib
from pathlib import Path
import traceback
import datetime
import asyncio
import sys

# 添加工具引入
try:
    from akari.bot.utils import EmbedBuilder
except ImportError:
    print("未找到utils模块，请确保已创建")

class MyBot(commands.Bot):
    def __init__(self, command_prefix: str = "!", intents: discord.Intents = None):
        intents = intents or discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._command_modules: List[str] = []
        self._plugin_modules: List[str] = []  # 添加插件模块列表
        self.start_time = datetime.datetime.now()  # 添加启动时间记录

    async def setup_hook(self) -> None:
        """Bot启动时的初始化钩子"""
        await self.load_command_modules()
        await self.load_plugins()

    async def load_command_modules(self) -> None:
        """加载命令模块"""
        commands_dir = Path(__file__).parent / "commands"
        for file in commands_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"akari.bot.commands.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "setup"):
                    await module.setup(self)
                    self._command_modules.append(module_name)
                    print(f"✅ Loaded command module: {module_name}")
            except Exception as e:
                print(f"❌ Failed to load command module {module_name}: {e}")
                traceback.print_exc()

    async def load_plugins(self) -> None:
        """加载插件模块"""
        plugins_dir = Path(__file__).parent.parent / "plugins"
        for file in plugins_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"akari.plugins.{file.stem}"
            try:
                # 使用 load_extension 替代手动加载
                await self.load_extension(module_name)
                self._plugin_modules.append(module_name)
                print(f"✅ Loaded plugin: {module_name}")
            except Exception as e:
                print(f"❌ Failed to load plugin {module_name}: {e}")
                traceback.print_exc()

    async def reload_plugin(self, plugin_name: str) -> bool:
        """重新加载指定插件"""
        try:
            await self.reload_extension(f"akari.plugins.{plugin_name}")
            print(f"🔄 Reloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to reload plugin {plugin_name}: {e}")
            traceback.print_exc()
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """卸载指定插件"""
        try:
            await self.unload_extension(f"akari.plugins.{plugin_name}")
            self._plugin_modules.remove(f"akari.plugins.{plugin_name}")
            print(f"❌ Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            print(f"❌ Failed to unload plugin {plugin_name}: {e}")
            traceback.print_exc()
            return False

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        # 设置游戏状态
        try:
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.playing, name="使用 !allcmds 获取帮助"),
                status=discord.Status.online
            )
        except Exception as e:
            print(f"设置状态时出错: {e}")

    async def on_message(self, message):
        # 忽略自己
        if message.author == self.user:
            return

        # 支持 @机器人 方式唤醒
        if self.user.mentioned_in(message):
            # 去掉 @机器人 前缀，提取命令
            content = message.content.replace(f"<@{self.user.id}>", "").strip()
            content = content.replace(f"<@!{self.user.id}>", "").strip()
            
            if content:
                # 判断是否为命令（以前缀开头）
                if content.startswith(self.command_prefix):
                    message.content = content
                    await self.process_commands(message)
                else:
                    # 不是命令，直接AI回复
                    await self._reply_ai(message, content)
                return
            else:
                # 仅@机器人且无命令，自动AI回复
                await self._reply_ai(message, "你好")
                return
        # 私聊自动AI回复
        if isinstance(message.channel, discord.DMChannel):
            if message.content.startswith(self.command_prefix):
                await self.process_commands(message)
            else:
                await self._reply_ai(message)
            return
        # 其它情况交给命令分发器
        await self.process_commands(message)

    async def _reply_ai(self, message, content_override=None):
        try:
            # 显示正在输入状态
            async with message.channel.typing():
                from akari.config.settings import Settings
                import google.generativeai as genai
                genai.configure(api_key=Settings.GOOGLE_AI_KEY)
                ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
                prompt_content = content_override if content_override is not None else message.content.strip()
                prompt = f"{Settings.BOT_PERSONA}\n用户: {prompt_content}"
                
                # 创建美观的Embed
                embed = EmbedBuilder.create(
                    title="💬 Akari回复",
                    color_key="special"
                )
                embed.set_author(
                    name=self.user.name, 
                    icon_url=self.user.avatar.url if self.user.avatar else self.user.default_avatar.url
                )
                
                # 异步执行AI生成
                response = await asyncio.to_thread(ai_model.generate_content, prompt)
                
                # 日志输出
                user_info = f"{message.author} (ID: {message.author.id})"
                channel_info = f"DM" if isinstance(message.channel, discord.DMChannel) else f"Guild: {getattr(message.guild, 'name', 'N/A')} | Channel: {getattr(message.channel, 'name', 'N/A')}"
                print("------ Discord 对话日志 ------")
                print(f"用户: {user_info}")
                print(f"位置: {channel_info}")
                # 限制显示的内容长度
                prompt_log = prompt_content[:100] + "..." if len(prompt_content) > 100 else prompt_content
                response_log = response.text[:100] + "..." if len(response.text) > 100 else response.text
                print(f"用户消息: {prompt_log}")
                print(f"AI回复: {response_log}")
                print("-----------------------------")
                
                # 处理AI回复，检查是否过长
                ai_response = response.text
                if len(ai_response) > 4000:  # Discord embed描述上限
                    # 截断过长的回复并提示
                    ai_response = ai_response[:3900] + "...\n(回复过长，已截断部分内容)"
                
                # 添加用户提问信息
                embed.add_field(
                    name="📝 您的问题", 
                    value=prompt_content[:1000] + ("..." if len(prompt_content) > 1000 else ""),
                    inline=False
                )
                
                # 设置AI回复内容
                embed.description = ai_response
                embed.set_footer(text=f"回复给: {message.author.display_name}")
                
                # 发送响应
                await message.reply(embed=embed)
        except Exception as e:
            # 创建错误Embed
            try:
                error_embed = EmbedBuilder.error(
                    title="AI响应出错",
                    description=f"处理您的请求时出现问题: ```{str(e)}```"
                )
                await message.reply(embed=error_embed)
            except:
                # 如果创建Embed失败，则直接发送纯文本
                await message.reply(f"AI自动回复出错: {str(e)}")
            print(f"AI回复错误: {str(e)}")
            traceback.print_exc()

    def register_command(self, cmd: commands.Command):
        self.add_command(cmd)
        return cmd

    def register_command_group(self, group: commands.Group):
        self.add_command(group)
        return group

    async def on_error(self, event_method, *args, **kwargs):
        error_trace = traceback.format_exc()
        print(f"[ERROR] 事件 {event_method} 发生异常：")
        print(error_trace)
        
        # 尝试将错误发送到第一个参数的频道（如果是消息事件）
        try:
            if args and hasattr(args[0], "channel"):
                try:
                    # 使用美化的错误消息
                    error_embed = EmbedBuilder.error(
                        title="系统错误",
                        description="处理事件时发生意外错误"
                    )
                    error_embed.add_field(
                        name="错误详情", 
                        value=f"```py\n{str(sys.exc_info()[1])[:1000]}```"
                    )
                    await args[0].channel.send(embed=error_embed)
                except:
                    # 备用方案：发送普通消息
                    await args[0].channel.send(f"发生错误: {str(sys.exc_info()[1])}")
        except Exception:
            pass

    async def on_command_error(self, ctx, error):
        error_trace = traceback.format_exc()
        print(f"[COMMAND ERROR] 命令执行异常：{error}")
        print(error_trace)
        
        try:
            # 根据错误类型创建不同的错误消息
            if isinstance(error, commands.CommandNotFound):
                # 命令未找到
                embed = EmbedBuilder.warning(
                    title="命令不存在",
                    description=f"未找到命令 `{ctx.invoked_with}`。使用 `{self.command_prefix}help` 查看可用命令列表。"
                )
            elif isinstance(error, commands.MissingRequiredArgument):
                # 缺少必需参数
                embed = EmbedBuilder.warning(
                    title="缺少参数",
                    description=f"命令缺少必要参数: `{error.param.name}`"
                )
                # 添加命令帮助信息
                if ctx.command.help:
                    embed.add_field(name="命令帮助", value=ctx.command.help)
            elif isinstance(error, commands.BadArgument):
                # 参数类型错误
                embed = EmbedBuilder.warning(
                    title="参数错误",
                    description=f"提供的参数无效: {str(error)}"
                )
            elif isinstance(error, commands.CheckFailure):
                # 权限检查失败
                embed = EmbedBuilder.error(
                    title="权限不足",
                    description="您没有执行此命令的权限"
                )
            else:
                # 其他类型错误
                embed = EmbedBuilder.error(
                    title="命令执行出错",
                    description=f"执行 `{ctx.invoked_with}` 命令时发生错误: ```{str(error)}```"
                )
                
                # 对于开发者显示错误追踪（如果配置了开发者ID）
                if hasattr(ctx.author, 'id') and hasattr(self, 'developer_ids') and ctx.author.id in self.developer_ids:
                    error_text = error_trace[-1000:] if len(error_trace) > 1000 else error_trace
                    embed.add_field(name="错误追踪", value=f"```py\n{error_text}```")
            
            # 发送美化的错误信息
            await ctx.reply(embed=embed)
        except Exception as e:
            print(f"处理命令错误时出现新错误: {e}")
            try:
                # 备用方案：发送普通消息
                await ctx.send(f"命令执行出错: {str(error)}")
            except Exception:
                pass 