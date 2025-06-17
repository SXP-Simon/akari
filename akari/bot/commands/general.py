from discord.ext import commands
from discord import app_commands
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

class GeneralCommands(commands.Cog):
    """
    通用基础命令。
    包含延迟测试、帮助、状态等常用功能。
    """
    def __init__(self, bot):
        """
        初始化GeneralCommands。
        Args:
            bot: Discord Bot实例。
        """
        self.bot = bot

    @app_commands.command(name="ping", description="测试机器人延迟")
    async def ping(self, interaction):
        """
        测试机器人延迟。
        Args:
            interaction: Discord交互对象。
        """
        embed_data = EmbedData(
            title="🏓 Pong!",
            description=f"延迟: {round(self.bot.latency * 1000)}ms",
            color=EmbedBuilder.THEME.info
        )
        embed = EmbedBuilder.create(embed_data)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="显示帮助信息")
    async def help(self, interaction):
        """
        显示机器人帮助信息。
        Args:
            interaction: Discord交互对象。
        """
        embed_data = EmbedData(
            title="🤖 机器人帮助",
            description="这是一个多功能Discord机器人，支持以下功能：\n\n"
                       "• `/ping` - 测试机器人延迟\n"
                       "• `/help` - 显示此帮助信息\n"
                       "• `/botstatus` - 显示机器人状态\n"
                       "• `/meme` - 表情包生成器\n"
                       "• `/开箱` - CS:GO武器箱模拟器\n"
                       "• `/askai` - 与AI助手对话\n"
                       "• `/rss` - RSS订阅管理\n"
                       "• `/保研` - 保研信息查询\n",
            color=EmbedBuilder.THEME.info
        )
        embed = EmbedBuilder.create(embed_data)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botstatus", description="显示机器人状态")
    async def botstatus(self, interaction):
        """
        显示机器人运行状态。
        Args:
            interaction: Discord交互对象。
        """
        embed_data = EmbedData(
            title="📊 机器人状态",
            description=f"• 服务器数量: {len(self.bot.guilds)}\n"
                       f"• 延迟: {round(self.bot.latency * 1000)}ms\n"
                       f"• 已加载插件数: {len(self.bot.cogs)}",
            color=EmbedBuilder.THEME.success
        )
        embed = EmbedBuilder.create(embed_data)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    """
    注册GeneralCommands到Bot。
    Args:
        bot: Discord Bot实例。
    """
    await bot.add_cog(GeneralCommands(bot)) 