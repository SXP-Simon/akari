import discord
from discord.ext import commands
import os
import asyncio
import shutil
import datetime
import re
import browser_cookie3
from typing import List

import jmcomic

from .config import MangaDownloaderConfig
from .service import MangaDownloaderService
from akari.bot.utils.error_handler import debug_command

class MangaDownloaderPlugin(commands.Cog):
    """
    禁漫漫画下载与转发插件
    """
    def __init__(self, bot):
        self.bot = bot
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.option_path = os.path.join(self.current_dir, 'option.yml')
        self.download_dir = None # Initialize to None
        self.option = None # Initialize to None
        self.client = None # Initialize to None
        self.service = None # Initialize to None
        self.cleanup_task = None # Initialize to None

        # 加载配置和初始化 JM 客户端
        try:
            self.option = MangaDownloaderConfig.load(self.option_path)
            # Use jmcomic's actual download directory from the option
            # The option's dir_rule.base_dir is the directory where jmcomic saves files
            self.download_dir = self.option.dir_rule.base_dir
            os.makedirs(self.download_dir, exist_ok=True)

            self.client = self.option.new_jm_client()
            self.bot.logger.info(f"JM漫画插件初始化成功，下载目录: {self.download_dir}")

            # 自动设置浏览器 Cookie
            self._set_browser_cookies()
            
            # 初始化服务
            self.service = MangaDownloaderService(self.option, self.client, self.download_dir, self.bot.logger)
            
            # 启动定时清理任务
            self.cleanup_task = self.bot.loop.create_task(self.service.start_cleanup_scheduler())

        except Exception as e:
            self.bot.logger.error(f"JM漫画插件初始化失败: {e}")
            # self.option, self.client, self.service remain None if initialization fails

    def _set_browser_cookies(self):
        """
        从浏览器中提取 Cookie 并设置到 JM 客户端
        """
        if not self.option or not self.client:
            self.bot.logger.warning("JMOption 或 JMClient 未初始化，无法设置浏览器 Cookie。")
            return

        try:
            browser = self.option.plugins.get('after_init', [{}])[0].get('kwargs', {}).get('browser', 'chrome')
            domain = self.option.plugins.get('after_init', [{}])[0].get('kwargs', {}).get('domain', '18comic.vip')

            if browser == 'chrome':
                cookies = browser_cookie3.chrome(domain_name=domain)
            elif browser == 'firefox':
                cookies = browser_cookie3.firefox(domain_name=domain)
            else:
                self.bot.logger.warning(f"不支持的浏览器类型: {browser}")
                return

            for cookie in cookies:
                self.client.set_cookie(cookie.name, cookie.value, domain=cookie.domain)
            self.bot.logger.info("成功设置浏览器 Cookie")
        except Exception as e:
            self.bot.logger.error(f"设置浏览器 Cookie 失败: {e}")

    @commands.group(name="manga", invoke_without_command=True)
    async def manga_group(self, ctx):
        """
        提供漫画下载相关功能的命令组。
        
        **可用子命令：**
        - `!manga download <album_id>`：下载整本漫画并发送。
        - `!manga chapter <album_id> <chapter_id>`：下载指定章节并发送。
        - `!manga search <keyword>`：搜索漫画。
        - `!manga clean`：手动清理下载目录。
        
        **示例：**
        - `!manga download 123456`
        - `!manga chapter 123456 1`
        - `!manga search 史莱姆`
        - `!manga clean`
        """
        embed = discord.Embed(
            title="📚 Manga 下载帮助",
            description=""":
**可用子命令：**
- `!manga download <album_id>`：下载整本漫画并发送。
- `!manga chapter <album_id> <chapter_id>`：下载指定章节并发送。
- `!manga search <keyword>`：搜索漫画。
- `!manga clean`：手动清理下载目录。

**示例：**
- `!manga download 123456`
- `!manga chapter 123456 1`
- `!manga search 史莱姆`
- `!manga clean`
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text="如有疑问请联系Bot管理员。")
        await ctx.send(embed=embed)

    @manga_group.command(name="search")
    @debug_command
    async def search_manga(self, ctx, *, keyword: str):
        """搜索漫画"""
        if not self.client:
            embed_error = discord.Embed(
                title="❌ 插件未初始化",
                description="漫画下载插件未正确初始化，请联系管理员检查日志。",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed_error)
            return

        embed_loading = discord.Embed(
            title="🔍 开始搜索漫画",
            description=f"正在搜索漫画：`{keyword}`，请稍候...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed_loading)

        try:
            search_result = self.client.search_album(keyword)
            if not search_result or not search_result.data:
                embed_not_found = discord.Embed(
                    title="❌ 未找到漫画",
                    description=f"未找到与 “{keyword}” 相关的漫画。",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed_not_found)
                return

            # 格式化搜索结果
            result_message = self._format_search_results(search_result.data)
            embed_success = discord.Embed(
                title="✅ 搜索完成",
                description=f"为您找到以下漫画：\n{result_message}",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_success)

        except Exception as e:
            self.bot.logger.error(f"搜索漫画时出错: {e}")
            embed_error = discord.Embed(
                title="⚠️ 搜索出错",
                description=f"搜索漫画时出错: {str(e)}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed_error)

    def _format_search_results(self, albums: List[jmcomic.JmAlbumDetail]):
        """格式化搜索结果"""
        formatted_results = []
        for album in albums[:5]:  # 只显示前5个结果，避免消息过长
            formatted_results.append(f"ID: {album.album_id} - 《{album.name}》")
        return "\n".join(formatted_results)

    @manga_group.command(name="download")
    @debug_command
    async def download_and_send_album_command(self, ctx, album_id: str):
        """
        下载整本漫画并发送
        """
        if not self.service:
            embed_error = discord.Embed(
                title="❌ 插件未初始化",
                description="漫画下载插件未正确初始化，请联系管理员检查日志。",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed_error)
            return

        embed_loading = discord.Embed(
            title="📥 开始下载漫画",
            description=f"正在下载漫画 ID：`{album_id}`，请稍候...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed_loading)

        try:
            album_detail, all_photos = await self.service._download_album(album_id)
            if not album_detail or not all_photos:
                embed_fail = discord.Embed(
                    title="❌ 下载失败",
                    description=f"下载漫画 {album_id} 失败。",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed_fail)
                return
            
            embed_info = discord.Embed(
                title="📚 漫画下载完成",
                description=f"漫画《{album_detail.name}》下载完成，共 {len(all_photos)} 个章节，即将开始发送...",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_info)
            
            # 发送整个漫画的图片
            await self.service.send_album_images(ctx, album_id, album_detail.name)

            embed_success = discord.Embed(
                title="✅ 发送完成",
                description=f"漫画 ID：`{album_id}` 已成功发送。",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_success)

        except Exception as e:
            self.bot.logger.error(f"下载并发送漫画时出错: {e}")
            embed_error = discord.Embed(
                title="⚠️ 操作出错",
                description=f"下载并发送漫画时出错: {str(e)}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed_error)

    @manga_group.command(name="chapter")
    @debug_command
    async def download_and_send_chapter_command(self, ctx, photo_id: str):
        """
        下载指定章节并发送
        """
        if not self.service:
            embed_error = discord.Embed(
                title="❌ 插件未初始化",
                description="漫画下载插件未正确初始化，请联系管理员检查日志。",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed_error)
            return

        embed_loading = discord.Embed(
            title="📥 开始下载章节",
            description=f"正在下载章节 ID：`{photo_id}`，请稍候...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed_loading)

        try:
            photo = await self.service._download_photo(photo_id)
            if not photo:
                embed_fail = discord.Embed(
                    title="❌ 下载失败",
                    description=f"下载章节 {photo_id} 失败。",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed_fail)
                return

            embed_info = discord.Embed(
                title="📚 章节下载完成",
                description=f"章节《{photo.title}》下载完成，共 {len(photo.image_list)} 张图片，即将开始发送...",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_info)

            await self.service.send_photo_images(ctx, photo, photo.title)

            embed_success = discord.Embed(
                title="✅ 发送完成",
                description=f"章节 ID：`{photo_id}` 已成功发送。",
                color=discord.Color.green()
            )
            await message.edit(embed=embed_success)

        except Exception as e:
            self.bot.logger.error(f"下载并发送章节时出错: {e}")
            embed_error = discord.Embed(
                title="⚠️ 操作出错",
                description=f"下载并发送章节时出错: {str(e)}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed_error)

    @manga_group.command(name="clean")
    @debug_command
    async def manual_cleanup(self, ctx):
        """
        手动清理下载目录
        """
        if not self.service:
            embed_error = discord.Embed(
                title="❌ 插件未初始化",
                description="漫画下载插件未正确初始化，请联系管理员检查日志。",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed_error)
            return

        embed_loading = discord.Embed(
            title="🧹 开始清理",
            description="正在清理漫画下载目录，请稍候...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed_loading)

        try:
            result = await self.service.cleanup_comic_files()
            if result:
                embed_success = discord.Embed(
                    title="✅ 清理完成",
                    description="漫画下载目录已成功清理！所有漫画文件已被删除。",
                    color=discord.Color.green()
                )
            else:
                embed_success = discord.Embed(
                    title="❌ 清理失败",
                    description="漫画下载目录清理失败，请检查日志。",
                    color=discord.Color.red()
                )
            await message.edit(embed=embed_success)
        except Exception as e:
            self.bot.logger.error(f"手动清理出错: {e}")
            embed_error = discord.Embed(
                title="⚠️ 清理出错",
                description=f"清理时出错: {str(e)}",
                color=discord.Color.red()
            )
            await message.edit(embed=embed_error)

async def setup(bot):
    """
    注册漫画下载插件
    """
    await bot.add_cog(MangaDownloaderPlugin(bot)) 