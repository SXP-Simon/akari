import discord
from discord.ext import commands
import time
import datetime
import platform
import psutil
import sys
from akari.bot.utils import EmbedBuilder, format_code_block

class SystemCommands(commands.Cog):
    """系统管理命令"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="system", description="系统管理命令")
    async def system(self, ctx):
        """系统管理命令组"""
        if ctx.invoked_subcommand is None:
            commands_dict = {
                "system status": "查看系统详细状态",
                "system ping": "测试机器人响应延迟",
                "system info": "显示机器人和系统信息",
                "system uptime": "显示机器人运行时间"
            }
            embed = EmbedBuilder.menu(
                title="系统管理中心",
                description="以下是所有可用的系统管理命令：",
                commands=commands_dict
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
            await ctx.reply(embed=embed)

    @system.command(name="status", description="显示系统详细状态")
    async def system_status(self, ctx):
        """显示系统详细状态"""
        async with ctx.typing():
            # 收集系统信息
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 创建Embed
            embed = EmbedBuilder.stats("系统状态监控")
            
            # CPU信息
            cpu_info = (
                f"使用率: {cpu_percent}%\n"
                f"核心数: {psutil.cpu_count(logical=True)}个 (物理: {psutil.cpu_count(logical=False)}个)\n"
            )
            embed.add_field(name="🖥️ CPU", value=cpu_info, inline=True)
            
            # 内存信息
            mem_info = (
                f"使用率: {memory.percent}%\n"
                f"已用: {memory.used / (1024**3):.2f} GB\n"
                f"总量: {memory.total / (1024**3):.2f} GB"
            )
            embed.add_field(name="💾 内存", value=mem_info, inline=True)
            
            # 磁盘信息
            disk_info = (
                f"使用率: {disk.percent}%\n"
                f"已用: {disk.used / (1024**3):.2f} GB\n"
                f"总量: {disk.total / (1024**3):.2f} GB"
            )
            embed.add_field(name="💿 磁盘", value=disk_info, inline=True)
            
            # 系统信息
            sys_info = (
                f"平台: {platform.system()} {platform.release()}\n"
                f"Python: {platform.python_version()}\n"
                f"Discord.py: {discord.__version__}"
            )
            embed.add_field(name="🔧 系统", value=sys_info, inline=False)
            
            # 进程信息
            proc = psutil.Process()
            proc_info = (
                f"PID: {proc.pid}\n"
                f"内存占用: {proc.memory_info().rss / (1024**2):.2f} MB\n"
                f"线程数: {proc.num_threads()}"
            )
            embed.add_field(name="⚙️ 进程", value=proc_info, inline=True)
            
            # 网络信息
            net = psutil.net_io_counters()
            net_info = (
                f"发送: {net.bytes_sent / (1024**2):.2f} MB\n"
                f"接收: {net.bytes_recv / (1024**2):.2f} MB"
            )
            embed.add_field(name="🌐 网络", value=net_info, inline=True)
            
            # 添加图标和页脚
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
            embed.set_footer(text=f"服务器时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.reply(embed=embed)

    @system.command(name="ping", description="测试机器人响应延迟")
    async def ping(self, ctx):
        """测试机器人响应延迟"""
        # 发送初始消息
        embed = EmbedBuilder.warning("延迟测试", description="正在计算延迟...")
        start = time.monotonic()
        msg = await ctx.reply(embed=embed)
        
        # 计算延迟
        end = time.monotonic()
        latency = round((end - start) * 1000)
        
        # 确定延迟等级和颜色
        if latency < 100:
            status = "极佳"
            color_key = "success"
            emoji = "🚀"
        elif latency < 200:
            status = "良好"
            color_key = "primary"
            emoji = "✅"
        elif latency < 500:
            status = "一般"
            color_key = "warning"
            emoji = "⚠️"
        else:
            status = "较差"
            color_key = "danger"
            emoji = "❌"
        
        # 创建新的Embed
        embed = EmbedBuilder.create(
            title=f"{emoji} 延迟测试结果", 
            color_key=color_key
        )
        
        embed.add_field(name="消息延迟", value=f"**{latency}ms** ({status})", inline=False)
        embed.add_field(name="API延迟", value=f"**{round(self.bot.latency * 1000)}ms**", inline=False)
        embed.set_footer(text="数值越低表示响应越快")
        
        await msg.edit(embed=embed)

    @system.command(name="info", description="显示机器人和系统信息")
    async def system_info(self, ctx):
        """显示机器人和系统信息"""
        embed = EmbedBuilder.info(
            title="机器人信息", 
            description=f"{self.bot.user.name} - 一个多功能Discord机器人"
        )
        
        # 机器人基本信息
        bot_info = (
            f"ID: {self.bot.user.id}\n"
            f"创建于: {self.bot.user.created_at.strftime('%Y-%m-%d')}\n"
            f"服务器数量: {len(self.bot.guilds)}\n"
            f"命令数量: {len(self.bot.commands)}"
        )
        embed.add_field(name="🤖 基本信息", value=bot_info, inline=True)
        
        # 环境信息
        env_info = (
            f"Python: {platform.python_version()}\n"
            f"Discord.py: {discord.__version__}\n"
            f"系统: {platform.system()} {platform.release()}"
        )
        embed.add_field(name="🔧 环境信息", value=env_info, inline=True)
        
        # 设置缩略图和页脚
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
        embed.set_footer(text=f"由 Akari 框架提供支持")
        
        await ctx.reply(embed=embed)

    @system.command(name="uptime", description="显示机器人运行时间")
    async def system_uptime(self, ctx):
        """显示机器人运行时间"""
        # 计算运行时间（这里假设bot启动时间已记录，如果没有，需要添加）
        # 这里使用进程启动时间作为替代
        proc = psutil.Process()
        bot_start_time = datetime.datetime.fromtimestamp(proc.create_time())
        uptime = datetime.datetime.now() - bot_start_time
        
        # 格式化运行时间
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}天 {hours}小时 {minutes}分钟 {seconds}秒"
        
        embed = EmbedBuilder.success(
            title="机器人运行时间",
            description=f"**{self.bot.user.name}** 已连续运行: **{uptime_str}**"
        )
        
        # 添加启动时间信息
        embed.add_field(
            name="启动时间", 
            value=bot_start_time.strftime("%Y-%m-%d %H:%M:%S"), 
            inline=False
        )
        
        # 添加图标
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)
        
        await ctx.reply(embed=embed)

async def setup(bot):
    """加载系统命令插件"""
    await bot.add_cog(SystemCommands(bot)) 