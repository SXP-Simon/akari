from discord.ext import commands

def admin_required():
    """管理员权限检查装饰器"""
    async def predicate(ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage("此命令只能在服务器中使用")
        admin_manager = ctx.bot.get_cog("Admin").admin_manager
        if not admin_manager.is_admin(ctx.author):
            raise commands.MissingPermissions(["管理员权限"])
        return True
    return commands.check(predicate)

def super_admin_required():
    """超级管理员权限检查装饰器"""
    async def predicate(ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage("此命令只能在服务器中使用")
        admin_manager = ctx.bot.get_cog("Admin").admin_manager
        if not admin_manager.is_super_admin(ctx.author):
            raise commands.MissingPermissions(["超级管理员权限"])
        return True
    return commands.check(predicate) 