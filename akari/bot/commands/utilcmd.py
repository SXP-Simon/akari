from discord.ext import commands
import discord
import psutil
import time
import asyncio
import platform

async def setup(bot):
    @commands.command(name="hello", description="打招呼")
    async def hello(ctx):
        await ctx.reply(f"你好, {ctx.author.mention}!")

    @commands.command(name="info", description="显示机器人信息")
    async def info(ctx):
        embed = discord.Embed(
            title="机器人信息",
            description="一个多功能Discord机器人",
            color=discord.Color.blue()
        )
        embed.add_field(name="开发者", value="Your Name")
        embed.add_field(name="版本", value="1.0.0")
        await ctx.send(embed=embed)

    @commands.command(name="zt", description="简易服务器状态")
    async def zt(ctx):
        async with ctx.typing():
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            sys_info = f"CPU使用: {cpu_usage}%\n内存使用: {memory_info.percent}%"
            await ctx.reply(f"```\n{sys_info}\n```")

    @commands.command(name="状态", description="详细服务器状态")
    async def status(ctx):
        async with ctx.typing():
            cpu_usage_str = await get_average_cpu_usage(samples=3, interval=0.2)
            memory_usage_str = get_memory_usage()
            disk_usage_str = get_disk_usage()
            net_info = psutil.net_io_counters()
            process_count = len(psutil.pids())
            net_connections = len(psutil.net_connections())
            sys_info = (
                f"CPU占用: {cpu_usage_str}\n"
                f"内存占用: {memory_usage_str}\n"
                f"磁盘占用: {disk_usage_str}\n"
                f"网络发送: {convert_to_readable(net_info.bytes_sent)}\n"
                f"网络接收: {convert_to_readable(net_info.bytes_recv)}\n"
                f"进程数量: {process_count}\n"
                f"连接数量: {net_connections}\n"
                f"系统: {platform.system()} {platform.release()}"
            )
            await ctx.reply(f"```\n{sys_info}\n```")

    @bot.register_command
    @commands.command(name="allcmds", aliases=["allcommands", "命令大全"], help="显示所有可用命令")
    async def allcmds_command(ctx):
        lines = ["**🤖 当前可用命令列表：**\n"]
        for cmd in bot.commands:
            if cmd.hidden:
                continue
            aliases = f"（别名: {', '.join(cmd.aliases)}）" if cmd.aliases else ""
            desc = cmd.help or "无描述"
            lines.append(f"`{bot.command_prefix}{cmd.name}` {aliases}\n→ {desc}")
        msg = "\n".join(lines)
        await ctx.send(msg)

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
        return f"{used_memory_gb:.2f}G/{total_memory_gb:.1f}G"

    def get_disk_usage(path="/"):
        disk_info = psutil.disk_usage(path)
        used_disk_gb = disk_info.used / (1024**3)
        total_disk_gb = disk_info.total / (1024**3)
        return f"{used_disk_gb:.2f}G/{total_disk_gb:.1f}G"

    def convert_to_readable(value):
        units = ["B", "KB", "MB", "GB"]
        unit_index = 0
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1
        return f"{value:.2f} {units[unit_index]}" 