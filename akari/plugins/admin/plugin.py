from .models import AdminConfig
from .manager import AdminManager
from .decorators import admin_required, super_admin_required
import discord
from discord.ext import commands
from akari.bot.utils.embeds import EmbedBuilder

class Admin(commands.Cog):
    """管理员权限控制插件"""
    def __init__(self, bot):
        self.bot = bot
        self.admin_manager = AdminManager()

    @commands.group(name="admin")
    @super_admin_required()
    async def admin(self, ctx):
        """管理员管理命令组"""
        if ctx.invoked_subcommand is None:
            commands_dict = {
                "/admin add <用户ID> [--super]": "添加管理员，可选指定为超级管理员",
                "/admin remove <用户ID>": "移除管理员",
                "/admin role add <角色ID>": "添加管理员角色",
                "/admin role remove <角色ID>": "移除管理员角色",
                "/admin list": "查看当前管理员列表"
            }
            await ctx.send(embed=EmbedBuilder.menu(
                title="管理员管理",
                description="使用以下命令管理管理员：",
                commands=commands_dict
            ))

    @admin.command(name="add")
    async def add_admin(self, ctx, user_id: int, *, flags: str = ""):
        """添加管理员"""
        is_super = "--super" in flags.lower()
        if self.admin_manager.add_admin(user_id, is_super):
            await ctx.send(embed=EmbedBuilder.success(
                title="添加成功",
                description=f"已添加{'超级' if is_super else ''}管理员 <@{user_id}>"
            ))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description="该用户已经是管理员"
            ))

    @admin.command(name="remove")
    async def remove_admin(self, ctx, user_id: int):
        """移除管理员"""
        if self.admin_manager.remove_admin(user_id):
            await ctx.send(embed=EmbedBuilder.success(
                title="移除成功",
                description=f"已移除管理员 <@{user_id}>"
            ))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="移除失败",
                description="该用户不是管理员"
            ))

    @admin.group(name="role")
    async def admin_role(self, ctx):
        """管理员角色管理"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @admin_role.command(name="add")
    async def add_admin_role(self, ctx, role_id: int):
        """添加管理员角色"""
        if self.admin_manager.add_admin_role(role_id):
            await ctx.send(embed=EmbedBuilder.success(
                title="添加成功",
                description=f"已添加管理员角色 <@&{role_id}>"
            ))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description="该角色已经是管理员角色"
            ))

    @admin_role.command(name="remove")
    async def remove_admin_role(self, ctx, role_id: int):
        """移除管理员角色"""
        if self.admin_manager.remove_admin_role(role_id):
            await ctx.send(embed=EmbedBuilder.success(
                title="移除成功",
                description=f"已移除管理员角色 <@&{role_id}>"
            ))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="移除失败",
                description="该角色不是管理员角色"
            ))

    @admin.command(name="list")
    async def list_admins(self, ctx):
        """查看管理员列表"""
        config = self.admin_manager.config
        # 获取超级管理员信息
        super_admins = []
        for user_id in config.super_admin_users:
            user = ctx.guild.get_member(user_id)
            if user:
                super_admins.append(f"<@{user_id}> ({user.name})")
            else:
                super_admins.append(f"<@{user_id}> (未知用户)")
        # 获取普通管理员信息
        admins = []
        for user_id in config.admin_users:
            if user_id not in config.super_admin_users:  # 避免重复显示超级管理员
                user = ctx.guild.get_member(user_id)
                if user:
                    admins.append(f"<@{user_id}> ({user.name})")
                else:
                    admins.append(f"<@{user_id}> (未知用户)")
        # 获取管理员角色信息
        admin_roles = []
        for role_id in config.admin_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                admin_roles.append(f"<@&{role_id}> ({role.name})")
            else:
                admin_roles.append(f"<@&{role_id}> (未知角色)")
        # 构建显示信息
        fields = []
        if super_admins:
            fields.append(("超级管理员", "\n".join(super_admins), False))
        if admins:
            fields.append(("普通管理员", "\n".join(admins), False))
        if admin_roles:
            fields.append(("管理员角色", "\n".join(admin_roles), False))
        if not fields:
            fields.append(("提示", "当前没有设置任何管理员", False))
        await ctx.send(embed=EmbedBuilder.info(
            title="管理员列表",
            description="当前服务器管理员配置：",
            fields=fields
        ))

async def setup(bot):
    await bot.add_cog(Admin(bot)) 