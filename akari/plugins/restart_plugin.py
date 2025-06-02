from akari.bot.commands import command
import discord

# 你可以根据需要修改为你的 Discord 用户ID 或角色ID
ADMIN_USER_IDS = {123456789012345678}  # 替换为你的管理员ID

def setup(bot):
    @bot.register_command
    @command(name="restart", description="重启机器人（仅限管理员）")
    async def restart(ctx):
        author_id = getattr(ctx.author, 'id', None)
        if author_id not in ADMIN_USER_IDS:
            await ctx.reply("你没有权限重启机器人！")
            return
        await ctx.reply("机器人即将重启……")
        await ctx.bot.close()  # 优雅关闭，外部守护进程会自动重启 