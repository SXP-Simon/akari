from typing import Optional
import psutil
import platform
import time
from datetime import datetime
from discord.ext import commands
from ..core.commands import CommandBase
from ..utils.embeds import EmbedBuilder, EmbedData

class UtilityCommands(commands.Cog):
    """
    实用工具命令。
    包含服务器状态、机器人信息等常用工具命令。
    """
    
    def __init__(self, bot):
        """
        初始化UtilityCommands。
        Args:
            bot: Discord Bot实例。
        """
        self.bot = bot

    @commands.command(
        name="serverstatus",
        description="显示服务器状态",
        aliases=["stats", "zt"]
    )
    async def serverstatus_command(self, ctx):
        """
        显示服务器状态信息。
        Args:
            ctx: 命令上下文。
        """
        # 获取系统信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 创建状态Embed
        embed_data = EmbedData(
            title="📊 服务器状态",
            description="系统资源使用情况",
            color=EmbedBuilder.THEME.primary
        )
        
        if ctx.author:
            embed_data.author = {
                "name": ctx.author.display_name,
                "icon_url": str(ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            }
        
        # CPU信息
        cpu_info = (
            f"使用率: {cpu_percent}%\n"
            f"核心数: {psutil.cpu_count(logical=True)}个 (物理: {psutil.cpu_count(logical=False)}个)"
        )
        embed_data.fields.append({
            "name": "🖥️ CPU",
            "value": cpu_info,
            "inline": True
        })
        
        # 内存信息
        mem_info = (
            f"使用率: {memory.percent}%\n"
            f"已用: {memory.used / (1024**3):.2f} GB\n"
            f"总量: {memory.total / (1024**3):.2f} GB"
        )
        embed_data.fields.append({
            "name": "💾 内存",
            "value": mem_info,
            "inline": True
        })
        
        # 磁盘信息
        disk_info = (
            f"使用率: {disk.percent}%\n"
            f"已用: {disk.used / (1024**3):.2f} GB\n"
            f"总量: {disk.total / (1024**3):.2f} GB"
        )
        embed_data.fields.append({
            "name": "💿 磁盘",
            "value": disk_info,
            "inline": True
        })
        
        # 系统信息
        sys_info = (
            f"平台: {platform.system()} {platform.release()}\n"
            f"Python: {platform.python_version()}"
        )
        embed_data.fields.append({
            "name": "🔧 系统",
            "value": sys_info,
            "inline": False
        })
        
        # 运行时信息
        uptime = time.time() - psutil.boot_time()
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_info = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"
        embed_data.fields.append({
            "name": "⏱️ 运行时间",
            "value": uptime_info,
            "inline": False
        })
        
        await ctx.message.reply(embed=EmbedBuilder.create(embed_data))

    @commands.command(
        name="info",
        description="显示机器人信息",
        aliases=["about", "bot"]
    )
    async def info_command(self, ctx):
        """
        显示机器人详细信息。
        Args:
            ctx: 命令上下文。
        """
        bot = ctx.bot
        embed_data = EmbedData(
            title="ℹ️ 机器人信息",
            description="一个功能丰富的Discord机器人助手",
            color=EmbedBuilder.THEME.info,
            footer_text=f"启动于 {datetime.fromtimestamp(psutil.Process().create_time()).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 基本信息
        embed_data.fields.extend([
            {
                "name": "名称",
                "value": bot.user.name,
                "inline": True
            },
            {
                "name": "ID",
                "value": str(bot.user.id),
                "inline": True
            },
            {
                "name": "版本",
                "value": "1.0.0",
                "inline": True
            }
        ])
        
        # 统计信息
        embed_data.fields.extend([
            {
                "name": "服务器数",
                "value": str(len(bot.guilds)),
                "inline": True
            },
            {
                "name": "用户数",
                "value": str(len(set(bot.get_all_members()))),
                "inline": True
            },
            {
                "name": "命令数",
                "value": str(len(bot.commands)),
                "inline": True
            }
        ])
        
        # 系统信息
        embed_data.fields.append({
            "name": "环境",
            "value": f"Python {platform.python_version()}\n{platform.system()} {platform.release()}",
            "inline": False
        })
        
        embed = EmbedBuilder.create(embed_data)
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
        await ctx.message.reply(embed=embed)

def create_progress_bar(value: float, max_value: float, length: int = 10) -> str:
    """
    创建进度条字符串。
    Args:
        value (float): 当前值。
        max_value (float): 最大值。
        length (int): 进度条长度。
    Returns:
        str: 进度条字符串。
    """
    filled = int(value / max_value * length)
    empty = length - filled
    return f"{'█' * filled}{'░' * empty}"

async def setup(bot):
    """
    注册UtilityCommands到Bot。
    Args:
        bot: Discord Bot实例。
    """
    await bot.add_cog(UtilityCommands(bot)) 