import discord
from discord.ext import commands
import sys
import os
import asyncio
from .admin.decorators import super_admin_required
from ..bot.utils import EmbedBuilder

# =====================
# akari.plugins.restart_plugin
# =====================

"""
RestartPlugin: 智能重启插件

- 自动检测运行环境（Docker/Systemd/其他）
- 根据环境选择适当的重启方式
- 支持自定义容器/服务名称
- 完善的错误处理和日志记录
"""

class RestartPlugin(commands.Cog):
    """智能重启插件 - 自动适配不同运行环境"""

    def __init__(self, bot):
        self.bot = bot
        self.restarting = False
        self.container_name = "akari-bot"  # 默认Docker容器名
        self.service_name = "akari.service"  # 默认systemd服务名
        self.runtime_env = self.detect_runtime_environment()

    def detect_runtime_environment(self):
        """检测当前运行环境"""
        # 检查是否在Docker容器中运行
        if os.path.exists('/.dockerenv'):
            return 'docker'
        # 检查cgroup信息（另一种Docker检测方式）
        try:
            with open('/proc/self/cgroup', 'r') as f:
                if 'docker' in f.read():
                    return 'docker'
        except:
            pass
        
        # 检查是否为systemd管理
        if os.path.exists('/run/systemd/system'):
            return 'systemd'
        
        # 默认情况
        return 'unknown'

    async def restart_in_docker(self):
        """在Docker环境中重启"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "restart", self.container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode == 0, stderr.decode().strip()
        except Exception as e:
            return False, str(e)

    async def restart_with_systemd(self):
        """在systemd环境中重启"""
        try:
            process = await asyncio.create_subprocess_exec(
                "sudo", "systemctl", "restart", self.service_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return process.returncode == 0, stderr.decode().strip()
        except Exception as e:
            return False, str(e)

    async def restart_bot(self):
        """根据运行环境执行适当的重启操作"""
        if self.runtime_env == 'docker':
            self.bot.logger.info("检测到Docker环境，使用docker restart")
            return await self.restart_in_docker()
        elif self.runtime_env == 'systemd':
            self.bot.logger.info("检测到systemd环境，使用systemctl restart")
            return await self.restart_with_systemd()
        else:
            error_msg = "无法确定运行环境，不支持自动重启"
            self.bot.logger.error(error_msg)
            return False, error_msg

    @commands.command(name="restart", description="重启机器人（仅限超级管理员）")
    @super_admin_required()
    async def restart(self, ctx):
        """智能重启机器人命令"""
        if self.restarting:
            await ctx.reply(embed=EmbedBuilder.warning(
                title="重启中",
                description="机器人正在重启中，请稍候..."
            ))
            return

        try:
            self.restarting = True
            # 发送重启通知
            notice = await ctx.send(embed=EmbedBuilder.info(
                title="重启通知",
                description=f"检测到运行环境: {self.runtime_env}\n机器人将在3秒后重启..."
            ))
            
            # 等待3秒，让消息发送完成
            await asyncio.sleep(3)
            
            # 尝试重启
            success, message = await self.restart_bot()
            if success:
                result_embed = EmbedBuilder.success(
                    title="重启成功",
                    description=f"机器人已成功重启！\n方式: {self.runtime_env}"
                )
            else:
                result_embed = EmbedBuilder.error(
                    title="重启失败",
                    description=f"重启过程中出现错误：\n{message}"
                )
            
            # 尝试编辑原始通知消息
            try:
                await notice.edit(embed=result_embed)
            except:
                await ctx.send(embed=result_embed)
                
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="重启失败",
                description=f"重启过程中出现意外错误：{str(e)}"
            ))
        finally:
            self.restarting = False

async def setup(bot):
    """插件加载入口"""
    await bot.add_cog(RestartPlugin(bot))
