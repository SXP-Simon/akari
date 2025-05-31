import discord
from discord.ext import commands
from typing import List
import importlib
from pathlib import Path

class MyBot(commands.Bot):
    def __init__(self, command_prefix: str = "!", intents: discord.Intents = None):
        intents = intents or discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self._command_modules: List[str] = []

    async def setup_hook(self) -> None:
        await self.load_command_modules()
        await self.load_plugins()

    async def load_command_modules(self) -> None:
        commands_dir = Path(__file__).parent / "commands"
        for file in commands_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"mybot2.bot.commands.{file.stem}"
            module = importlib.import_module(module_name)
            if hasattr(module, "setup"):
                await module.setup(self)
                self._command_modules.append(module_name)
                print(f"Loaded command module: {module_name}")

    async def load_plugins(self) -> None:
        plugins_dir = Path(__file__).parent.parent / "plugins"
        for file in plugins_dir.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue
            module_name = f"mybot2.plugins.{file.stem}"
            module = importlib.import_module(module_name)
            if hasattr(module, "setup"):
                module.setup(self)
                print(f"Loaded plugin: {module_name}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def on_message(self, message):
        # 忽略自己
        if message.author == self.user:
            return

        # 支持 @机器人 方式唤醒
        if self.user.mentioned_in(message):
            # 去掉 @机器人 前缀，提取命令
            content = message.content.replace(self.user.mention, "").strip()
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
                await self._reply_ai(message)
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
            from mybot2.config.settings import Settings
            import google.generativeai as genai
            genai.configure(api_key=Settings.GOOGLE_AI_KEY)
            ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
            prompt_content = content_override if content_override is not None else message.content.strip()
            prompt = f"{Settings.BOT_PERSONA}\n用户: {prompt_content}"
            await message.channel.typing().__aenter__()
            import asyncio
            response = await asyncio.to_thread(ai_model.generate_content, prompt)
            # 日志输出
            user_info = f"{message.author} (ID: {message.author.id})"
            channel_info = f"DM" if isinstance(message.channel, discord.DMChannel) else f"Guild: {getattr(message.guild, 'name', 'N/A')} | Channel: {getattr(message.channel, 'name', 'N/A')}"
            print("------ Discord 对话日志 ------")
            print(f"用户: {user_info}")
            print(f"位置: {channel_info}")
            print(f"用户消息: {prompt_content}")
            print(f"AI回复: {response.text}")
            print("-----------------------------")
            await message.reply(response.text)
        except Exception as e:
            await message.reply(f"AI自动回复出错: {str(e)}")

    def register_command(self, cmd: commands.Command):
        self.add_command(cmd)
        return cmd

    def register_command_group(self, group: commands.Group):
        self.add_command(group)
        return group 