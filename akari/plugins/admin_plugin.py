import discord
from discord.ext import commands
import json
import os
from typing import Set, Dict, Optional
from dataclasses import dataclass
from ..bot.utils import EmbedBuilder

# =====================
# akari.plugins.admin_plugin
# =====================

"""
AdminPlugin: 管理员工具插件

- 支持服务器管理、用户管理等操作
- Discord 命令集成
- 权限控制与日志

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

@dataclass
class AdminConfig:
    """管理员配置"""
    admin_users: Set[int]  # 管理员用户ID集合
    admin_roles: Set[int]  # 管理员角色ID集合
    super_admin_users: Set[int]  # 超级管理员用户ID集合

class AdminManager:
    """管理员管理器"""
    def __init__(self, config_path: str = "data/admin/admin_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> AdminConfig:
        """加载管理员配置"""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            default_config = {
                "admin_users": [],
                "admin_roles": [],
                "super_admin_users": []
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return AdminConfig(set(), set(), set())

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return AdminConfig(
                admin_users=set(data.get("admin_users", [])),
                admin_roles=set(data.get("admin_roles", [])),
                super_admin_users=set(data.get("super_admin_users", []))
            )

    def save_config(self):
        """保存管理员配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "admin_users": list(self.config.admin_users),
            "admin_roles": list(self.config.admin_roles),
            "super_admin_users": list(self.config.super_admin_users)
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_admin(self, member: discord.Member) -> bool:
        """检查用户是否为管理员"""
        # 检查用户ID
        if member.id in self.config.admin_users:
            return True
        # 检查用户角色
        if any(role.id in self.config.admin_roles for role in member.roles):
            return True
        return False

    def is_super_admin(self, member: discord.Member) -> bool:
        """检查用户是否为超级管理员"""
        return member.id in self.config.super_admin_users

    def add_admin(self, user_id: int, is_super: bool = False) -> bool:
        """添加管理员"""
        if is_super:
            self.config.super_admin_users.add(user_id)
        else:
            self.config.admin_users.add(user_id)
        self.save_config()
        return True

    def remove_admin(self, user_id: int) -> bool:
        """移除管理员"""
        if user_id in self.config.super_admin_users:
            self.config.super_admin_users.remove(user_id)
        if user_id in self.config.admin_users:
            self.config.admin_users.remove(user_id)
        self.save_config()
        return True

    def add_admin_role(self, role_id: int) -> bool:
        """添加管理员角色"""
        self.config.admin_roles.add(role_id)
        self.save_config()
        return True

    def remove_admin_role(self, role_id: int) -> bool:
        """移除管理员角色"""
        if role_id in self.config.admin_roles:
            self.config.admin_roles.remove(role_id)
            self.save_config()
            return True
        return False

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
            commands = {
                "/admin add <用户ID> [--super]": "添加管理员，可选指定为超级管理员",
                "/admin remove <用户ID>": "移除管理员",
                "/admin role add <角色ID>": "添加管理员角色",
                "/admin role remove <角色ID>": "移除管理员角色",
                "/admin list": "查看当前管理员列表"
            }
            await ctx.send(embed=EmbedBuilder.menu(
                title="管理员管理",
                description="使用以下命令管理管理员：",
                commands=commands
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