import discord
from discord.ext import commands
import sys
import os
import asyncio
from .admin_plugin import super_admin_required
from ..bot.utils import EmbedBuilder

# =====================
# akari.plugins.restart_plugin
# =====================

"""
RestartPlugin: Bot 重启插件

- 支持通过命令安全重启 Bot
- Discord 命令集成
- 权限控制

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

class RestartPlugin(commands.Cog):
    """重启插件 - 提供机器人重启功能"""

    def __init__(self, bot):
        self.bot = bot
        self.restarting = False

    async def restart_bot(self):
        """执行重启操作"""
        try:
            # 执行 systemctl 命令停止服务
            await asyncio.create_subprocess_exec(
                "sudo", "systemctl", "stop", "akari.service"
            )


        except Exception as e:
            self.bot.logger.error(f"重启失败: {str(e)}")
            return False
        return True

    @commands.command(name="restart", description="重启机器人（仅限超级管理员）")
    @super_admin_required()
    async def restart(self, ctx):
        """重启机器人命令"""
        if self.restarting:
            await ctx.reply(embed=EmbedBuilder.warning(
                title="重启中",
                description="机器人正在重启中，请稍候..."
            ))
            return

        try:
            self.restarting = True
            # 发送重启通知
            await ctx.send(embed=EmbedBuilder.info(
                title="重启通知",
                description="机器人将在3秒后重启..."
            ))
            
            # 等待3秒，让消息发送完成
            await asyncio.sleep(6)
            
            # 尝试重启
            if await self.restart_bot():
                await ctx.send(embed=EmbedBuilder.success(
                    title="重启成功",
                    description="机器人已成功重启！"
                ))
            else:
                await ctx.send(embed=EmbedBuilder.error(
                    title="重启失败",
                    description="重启过程中出现错误，请检查日志。"
                ))
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="重启失败",
                description=f"重启过程中出现错误：{str(e)}"
            ))
        finally:
            self.restarting = False

async def setup(bot):
    """插件加载入口"""
    await bot.add_cog(RestartPlugin(bot))