from discord.ext import commands
import time

async def setup(bot):
    @commands.group(name="system", description="系统管理命令")
    async def system(ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply("可用子命令: status, ping")

    @system.command(name="status", description="显示系统状态")
    async def system_status(ctx):
        async with ctx.typing():
            status = "系统状态正常"
            await ctx.reply(f"```\n{status}\n```")

    @system.command(name="ping", description="测试机器人响应")
    async def ping(ctx):
        start = time.monotonic()
        msg = await ctx.reply("Pong!")
        end = time.monotonic()
        latency = round((end - start) * 1000)
        await msg.edit(content=f"Pong! 延迟: {latency}ms")

    bot.add_command(system) 