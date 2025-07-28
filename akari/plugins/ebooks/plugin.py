import discord
from discord.ext import commands
from .service import EbooksService
from akari.bot.utils.embeds import EmbedBuilder
from .models import SearchResult, Download
from .config import EbooksConfig  # 确保导入 EbooksConfig
import os  # 新增导入 os
import re

class EbooksPlugin(commands.Cog):
    """电子书插件"""
    def __init__(self, bot):
        self.bot = bot
        # 使用 EbooksConfig 的 load 方法加载配置
        self.ebooks_service = EbooksService(bot, config=EbooksConfig.load())

    @commands.group(name="ebooks", invoke_without_command=True)
    async def ebooks(self, ctx):
        """电子书命令组"""
        subcommands = [
            f"`{cmd.name}`: {cmd.help}" for cmd in self.ebooks.commands
        ]
        description = "\n".join(subcommands)
        await ctx.send(embed=EmbedBuilder.info(
            title="电子书插件",
            description=f"使用以下子命令:\n{description}"
        ))

    @ebooks.command(name="search")
    async def search(self, ctx, *, query: str):
        """搜索电子书，支持 tag:xxx 语法"""
        # 解析 tag:xxx
        tag_match = re.search(r'tag:([\w-]+)', query)
        tag = tag_match.group(1) if tag_match else None
        real_query = re.sub(r'tag:[\w-]+', '', query).strip()
        results = await self.ebooks_service.search_ebooks(real_query, tag=tag)

        if not results:
            await ctx.send(embed=EmbedBuilder.error(
                title="未找到电子书",
                description="请尝试其他关键词。"
            ))
            return

        for result in results[:5]:  # 仅显示前 5 个结果
            # 详细信息输出
            desc = (
                f"作者: {result.authors}\n"
                f"出版社: {result.publisher}\n"
                f"年份: {result.publish_date}\n"
                f"语言: {getattr(result.file_info, 'language', '未知')}\n"
                f"格式: {getattr(result.file_info, 'extension', '未知')}\n"
                f"ID: {result.id}"
            )
            # Z-Library 额外显示 hash
            if hasattr(result, 'hash') and result.hash:
                desc += f"\nHash: {result.hash}"
            # 简介
            if hasattr(result, 'description') and result.description:
                desc += f"\n简介: {result.description[:100]}"
            await ctx.send(embed=EmbedBuilder.info(
                title=result.title,
                description=desc
            ))

    @ebooks.command(name="download")
    async def download(self, ctx, book_id: str):
        """下载电子书"""
        download = await self.ebooks_service.download_ebooks(book_id)
        if not download:
            await ctx.send(embed=EmbedBuilder.error(
                title="下载失败",
                description="未能找到指定的电子书。"
            ))
            return

        # 发送文件给用户
        if hasattr(download, "file_path") and os.path.exists(download.file_path):
            await ctx.send(embed=EmbedBuilder.info(
                title=f"已下载: {download.title}",
                description=f"作者: {download.authors}\n文件大小: {download.file_info.size}\n格式: {download.file_info.extension}"
            ))
            await ctx.send(file=discord.File(download.file_path))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="发送失败",
                description="未能找到下载的文件。"
            ))

    @ebooks.command(name="help")
    async def help(self, ctx):
        """显示 ebooks 插件详细帮助信息"""
        help_msg = (
            "📚 **ebooks 插件使用指南**\n\n"
            "支持通过多平台（Calibre-Web、Liber3、Z-Library、archive.org、Anna's Archive）搜索、下载电子书。\n\n"
            "---\n"
            "🔧 **命令列表**:\n\n"
            "- `/ebooks search <关键词> [tag:标签]`：多平台搜索电子书，支持 tag 精确筛选（Anna's Archive）。\n"
            "- `/ebooks download <ID> [Hash]`：多平台下载电子书，Z-Library 需提供 Hash。\n"
            "- `/ebooks help`：显示本帮助信息。\n\n"
            "---\n"
            "🌐 **支持平台**:\n"
            "- Calibre-Web\n- Liber3\n- Z-Library\n- archive.org\n- Anna's Archive\n\n"
            "---\n"
            "📒 **注意事项**:\n"
            "- 下载指令要根据搜索结果，提供有效的 ID 和 Hash（如需）。\n"
            "- 推荐功能和更多高级用法请参考文档。\n"
        )
        await ctx.send(embed=EmbedBuilder.info(
            title="ebooks 帮助",
            description=help_msg
        ))

async def setup(bot):
    """注册电子书插件"""
    await bot.add_cog(EbooksPlugin(bot))
