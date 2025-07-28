import discord
from discord.ext import commands
from .service import MagnetPreviewService
from .utils import is_magnet, format_file_size
import os

class MagnetPreviewPlugin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = MagnetPreviewService()

    @commands.command(name="magnet")
    async def magnet(self, ctx, *, link: str):
        """预览磁力链接信息"""
        if not is_magnet(link):
            await ctx.send("⚠️ 请输入有效的磁力链接！")
            return
        result = await self.service.get_preview(link)
        if not result or result.get("error"):
            await ctx.send(f"⚠️ 解析失败: {result.get('name', 'API无响应') if result else 'API无响应'}")
            return
        embed = self._build_embed(result)
        await ctx.send(embed=embed)
        # 发送截图
        screenshots = result.get("screenshots", [])
        for s in screenshots[:self.service.max_images]:
            url = s["screenshot"] if isinstance(s, dict) else s
            await ctx.send(url)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        for word in message.content.split():
            if is_magnet(word):
                ctx = await self.bot.get_context(message)
                await self.magnet(ctx, link=word)
                break

    def _build_embed(self, info: dict) -> discord.Embed:
        file_type_map = {
            'folder': '📁 文件夹',
            'video': '🎥 视频',
            'image': '🖼 图片',
            'text': '📄 文本',
            'audio': '🎵 音频',
            'archive': '📦 压缩包',
            'document': '📑 文档',
            'unknown': '❓ 其他'
        }
        embed = discord.Embed(title=info.get("name", "未知磁力资源"), description="磁力链接预览", color=0x3498db)
        embed.add_field(name="类型", value=file_type_map.get(info.get("file_type", "unknown"), "❓ 其他"), inline=True)
        embed.add_field(name="大小", value=format_file_size(info.get("size", 0)), inline=True)
        embed.add_field(name="文件数", value=str(info.get("count", 0)), inline=True)
        if info.get("screenshots"):
            first_img = info["screenshots"][0]
            url = first_img["screenshot"] if isinstance(first_img, dict) else first_img
            embed.set_image(url=url)
        return embed

async def setup(bot):
    await bot.add_cog(MagnetPreviewPlugin(bot)) 