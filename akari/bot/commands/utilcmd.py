from discord.ext import commands
import discord
import psutil
import time
import asyncio
import platform
from akari.bot.utils import EmbedBuilder, format_code_block, truncate_text

async def setup(bot):

    @bot.register_command
    @commands.command(name="hello", description="打招呼")
    async def hello(ctx):
        embed = EmbedBuilder.success(
            title="问候", 
            description=f"👋 你好，{ctx.author.mention}!"
        )
        embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.reply(embed=embed)

    @bot.register_command
    @commands.command(name="info", description="显示机器人信息")
    async def info(ctx):
        embed = EmbedBuilder.info(
            title="机器人信息",
            description="一个功能丰富的Discord机器人助手"
        )
        # 添加特色图标
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)
        
        # 基本信息
        embed.add_field(name="名称", value=bot.user.name, inline=True)
        embed.add_field(name="开发者", value="Akari 团队", inline=True)
        embed.add_field(name="版本", value="1.0.0", inline=True)
        
        # 系统信息
        embed.add_field(
            name="环境",
            value=f"Python {platform.python_version()}\nDiscord.py {discord.__version__}",
            inline=True
        )
        embed.add_field(
            name="服务器数",
            value=str(len(bot.guilds)),
            inline=True
        )
        embed.add_field(
            name="总用户数",
            value=str(len(set(bot.get_all_members()))),
            inline=True
        )
        
        # 设置页脚
        embed.set_footer(text="使用 !allcmds 获取更多帮助")
        
        await ctx.send(embed=embed)

    @bot.register_command
    @commands.command(name="zt", description="简易服务器状态")
    async def zt(ctx):
        async with ctx.typing():
            # 收集基础信息
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            
            # 创建简洁的Embed
            embed = EmbedBuilder.stats(
                title="服务器状态简报",
                description="核心系统指标概览",
                author=ctx.author
            )
            
            # 添加状态信息
            status_emoji = "✅" if cpu_usage < 80 and memory_info.percent < 80 else "⚠️"
            embed.add_field(
                name=f"{status_emoji} 系统状态",
                value="运行正常" if status_emoji == "✅" else "资源占用较高",
                inline=False
            )
            
            # 添加CPU和内存信息
            cpu_bar = create_progress_bar(cpu_usage, 100)
            mem_bar = create_progress_bar(memory_info.percent, 100)
            
            embed.add_field(name="CPU使用率", value=f"{cpu_usage}%\n{cpu_bar}", inline=True)
            embed.add_field(name="内存使用率", value=f"{memory_info.percent}%\n{mem_bar}", inline=True)
            
            await ctx.reply(embed=embed)

    @bot.register_command
    @commands.command(name="状态", description="详细服务器状态")
    async def status(ctx):
        async with ctx.typing():
            # 获取详细状态
            cpu_usage_str = await get_average_cpu_usage(samples=3, interval=0.2)
            memory_usage_str = get_memory_usage()
            disk_usage_str = get_disk_usage()
            net_info = psutil.net_io_counters()
            process_count = len(psutil.pids())
            net_connections = len(psutil.net_connections())
            
            # 创建详细Embed
            embed = EmbedBuilder.create(
                title="📊 服务器详细状态报告",
                description="以下是系统各项指标的详细统计",
                color_key="info"
            )
            
            # 系统基本信息
            embed.add_field(
                name="💻 系统信息",
                value=f"操作系统: {platform.system()} {platform.release()}\n"
                      f"版本: {platform.version()}\n"
                      f"架构: {platform.machine()}",
                inline=False
            )
            
            # 资源使用统计
            embed.add_field(name="🔄 CPU占用", value=cpu_usage_str, inline=True)
            embed.add_field(name="📊 内存占用", value=memory_usage_str, inline=True)
            embed.add_field(name="💽 磁盘占用", value=disk_usage_str, inline=True)
            
            # 网络和进程信息
            embed.add_field(
                name="📡 网络流量", 
                value=f"发送: {convert_to_readable(net_info.bytes_sent)}\n"
                      f"接收: {convert_to_readable(net_info.bytes_recv)}",
                inline=True
            )
            embed.add_field(
                name="⚙️ 进程信息", 
                value=f"进程数: {process_count}\n"
                      f"连接数: {net_connections}",
                inline=True
            )
            
            # 运行时信息
            uptime = time.time() - psutil.boot_time()
            days, remainder = divmod(uptime, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed.add_field(
                name="⏱️ 系统运行时间", 
                value=f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟",
                inline=False
            )
            
            # 添加页脚信息
            embed.set_footer(text=f"数据采集时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.reply(embed=embed)

    @bot.register_command
    @commands.command(name="allcmds", aliases=["allcommands", "命令大全"], help="显示所有可用命令")
    async def allcmds_command(ctx):
        # 创建漂亮的命令列表Embed
        embed = EmbedBuilder.menu(
            title="命令大全", 
            description="以下是所有可用的命令列表，按类别分组"
        )
        
        # 对命令按类别分组，如果没有类别的放在"通用"组
        commands_by_category = {}
        for cmd in sorted(bot.commands, key=lambda x: x.name):
            if cmd.hidden:
                continue
                
            # 尝试获取命令的类别
            category = getattr(cmd, "category", "通用")
            if category not in commands_by_category:
                commands_by_category[category] = []
            
            # 格式化命令信息
            aliases = f"（别名: {', '.join(cmd.aliases)}）" if cmd.aliases else ""
            desc = cmd.help or cmd.description or "无描述"
            cmd_text = f"`{bot.command_prefix}{cmd.name}` {aliases}\n→ {desc}"
            
            commands_by_category[category].append(cmd_text)
        
        # 添加每个类别的命令
        for category, cmds in sorted(commands_by_category.items()):
            # 如果命令太多，可能需要拆分
            if len("\n".join(cmds)) > 1024:  # Discord字段值长度限制
                chunks = []
                current_chunk = []
                current_length = 0
                
                for cmd in cmds:
                    if current_length + len(cmd) + 1 > 1024:  # +1 for newline
                        chunks.append(current_chunk)
                        current_chunk = [cmd]
                        current_length = len(cmd)
                    else:
                        current_chunk.append(cmd)
                        current_length += len(cmd) + 1
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 添加分块字段
                for i, chunk in enumerate(chunks):
                    field_name = f"{category} (Part {i+1}/{len(chunks)})"
                    embed.add_field(
                        name=field_name, 
                        value="\n".join(chunk),
                        inline=False
                    )
            else:
                # 添加单个字段
                embed.add_field(
                    name=category, 
                    value="\n".join(cmds),
                    inline=False
                )
        
        # 添加页脚提示
        embed.set_footer(text=f"使用 {bot.command_prefix}help [命令名] 获取详细帮助信息")
        
        await ctx.send(embed=embed)

    async def get_average_cpu_usage(samples=5, interval=0.5):
        total_usage = 0
        for _ in range(samples):
            cpu_usage = psutil.cpu_percent(interval=interval)
            total_usage += cpu_usage
            await asyncio.sleep(interval)
        average_usage = total_usage / samples
        return f"{average_usage:.2f}%"

    def get_memory_usage():
        memory_info = psutil.virtual_memory()
        used_memory_gb = memory_info.used / (1024**3)
        total_memory_gb = memory_info.total / (1024**3)
        return f"{used_memory_gb:.2f}G/{total_memory_gb:.1f}G ({memory_info.percent}%)"

    def get_disk_usage(path=None):
        # 自动判断平台
        if path is None:
            if platform.system() == "Windows":
                path = "C:\\"
            else:
                path = "/"
        try:
            disk_info = psutil.disk_usage(path)
            used_disk_gb = disk_info.used / (1024**3)
            total_disk_gb = disk_info.total / (1024**3)
            return f"{used_disk_gb:.2f}G/{total_disk_gb:.1f}G ({disk_info.percent}%)"
        except Exception as e:
            return f"无法获取磁盘信息: {e}"

    def convert_to_readable(value):
        units = ["B", "KB", "MB", "GB"]
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        return f"{value:.2f} {units[unit_index]}"
    
    def create_progress_bar(value, max_value, length=10):
        """创建可视化进度条"""
        filled_length = int(length * value / max_value)
        empty_length = length - filled_length
        
        if value < 60:
            bar_color = "🟢"  # 绿色
        elif value < 85:
            bar_color = "🟡"  # 黄色
        else:
            bar_color = "🔴"  # 红色
            
        bar = bar_color * filled_length + "⚪" * empty_length
        return bar 