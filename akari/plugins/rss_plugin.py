import discord
from discord.ext import commands, tasks
import aiohttp
import time
import re
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from bs4 import BeautifulSoup
from lxml import etree
from urllib.parse import urlparse
import logging
from datetime import datetime
import asyncio
import traceback
from ..bot.utils import EmbedBuilder

# =====================
# akari.plugins.rss_plugin
# =====================

"""
RssPlugin: RSS 订阅与推送插件

- 支持 RSS 源订阅、管理与推送
- Discord 命令集成
- 数据持久化与定时任务

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

@dataclass
class RSSConfig:
    """RSS配置"""
    title_max_length: int = 30
    description_max_length: int = 500
    max_items_per_poll: int = 3
    check_interval: int = 5
    is_hide_url: bool = False
    pic_config: Dict[str, Union[bool, int]] = None

    def __post_init__(self):
        if self.pic_config is None:
            self.pic_config = {
                "is_read_pic": True,
                "is_adjust_pic": False,
                "max_pic_item": 3
            }

@dataclass
class RSSItem:
    chan_title: str
    title: str
    link: str
    description: str
    pubDate: str
    pubDate_timestamp: int
    pic_urls: List[str]

    def __str__(self):
        return f"{self.title} - {self.link} - {self.description} - {self.pubDate}"

class RSSError(Exception):
    """RSS错误基类"""
    pass

class RSSNetworkError(RSSError):
    """RSS网络错误"""
    pass

class RSSParseError(RSSError):
    """RSS解析错误"""
    pass

class RSSFeed:
    def __init__(self, url: str, channel_id: int, cron_expr: str = "*/5 * * * *"):
        self.url = url
        self.channel_id = channel_id
        self.cron_expr = cron_expr
        self.last_update = int(time.time())
        self.latest_link = ""
        self.error_count = 0
        self.last_error = None
        self.last_success = int(time.time())

class RSSManager:
    def __init__(self, config_path: str = "data/rss/rss_data.json"):
        self.config_path = config_path
        self.feeds = {}
        self.load_data()

    def load_data(self):
        """从数据文件中加载数据"""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            self.save_data()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for url, info in data.items():
                    if url == "settings":
                        continue
                    self.feeds[url] = {}
                    for channel_id, feed_data in info.get("subscribers", {}).items():
                        channel_id = int(channel_id)
                        self.feeds[url][channel_id] = RSSFeed(
                            url=url,
                            channel_id=channel_id,
                            cron_expr=feed_data.get("cron_expr", "*/5 * * * *")
                        )
                        self.feeds[url][channel_id].last_update = feed_data.get("last_update", int(time.time()))
                        self.feeds[url][channel_id].latest_link = feed_data.get("latest_link", "")
                        self.feeds[url][channel_id].error_count = feed_data.get("error_count", 0)
                        self.feeds[url][channel_id].last_error = feed_data.get("last_error")
                        self.feeds[url][channel_id].last_success = feed_data.get("last_success", int(time.time()))
        except Exception as e:
            logging.error(f"加载RSS数据失败: {str(e)}")
            self.feeds = {}

    def save_data(self):
        """保存数据到数据文件"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            data = {}
            for url, channels in self.feeds.items():
                data[url] = {
                    "subscribers": {},
                    "info": {}  # 用于存储频道信息
                }
                for channel_id, feed in channels.items():
                    data[url]["subscribers"][str(channel_id)] = {
                        "cron_expr": feed.cron_expr,
                        "last_update": feed.last_update,
                        "latest_link": feed.latest_link,
                        "error_count": feed.error_count,
                        "last_error": feed.last_error,
                        "last_success": feed.last_success
                    }
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存RSS数据失败: {str(e)}")

    def add_feed(self, url: str, channel_id: int, cron_expr: str) -> bool:
        """添加新的订阅"""
        if url not in self.feeds:
            self.feeds[url] = {}
        
        if channel_id in self.feeds[url]:
            return False
        
        self.feeds[url][channel_id] = RSSFeed(url, channel_id, cron_expr)
        self.save_data()
        return True

    def remove_feed(self, url: str, channel_id: int) -> bool:
        """移除订阅"""
        if url not in self.feeds or channel_id not in self.feeds[url]:
            return False
        
        del self.feeds[url][channel_id]
        if not self.feeds[url]:
            del self.feeds[url]
        self.save_data()
        return True

    def get_channel_feeds(self, channel_id: int) -> List[RSSFeed]:
        """获取频道的所有订阅"""
        result = []
        for url, channels in self.feeds.items():
            if channel_id in channels:
                result.append(channels[channel_id])
        return result

class RSS(commands.Cog):
    """RSS订阅插件"""
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(f"discord.{self.__class__.__name__}")
        self.config_path = "data/rss/rss_config.json"
        self.rss_manager = RSSManager()
        
        # 加载或创建默认配置
        self.config = self._load_or_create_config()
        
        # 创建RSS检查任务
        self._setup_rss_task()

    def _load_or_create_config(self):
        """加载或创建默认配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return RSSConfig(
                        title_max_length=data.get("title_max_length", 30),
                        description_max_length=data.get("description_max_length", 500),
                        max_items_per_poll=data.get("max_items_per_poll", 3),
                        check_interval=data.get("check_interval", 5),
                        is_hide_url=data.get("is_hide_url", False),
                        pic_config=data.get("pic_config", None)
                    )
            else:
                config = RSSConfig()
                self._save_config(config)
                return config
        except Exception as e:
            self.logger.error(f"加载RSS配置失败: {str(e)}")
            return RSSConfig()

    def _save_config(self, config: RSSConfig):
        """保存配置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            data = {
                "title_max_length": config.title_max_length,
                "description_max_length": config.description_max_length,
                "max_items_per_poll": config.max_items_per_poll,
                "check_interval": config.check_interval,
                "is_hide_url": config.is_hide_url,
                "pic_config": config.pic_config
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存RSS配置失败: {str(e)}")

    def _setup_rss_task(self):
        """设置RSS检查任务"""
        interval = self.config.check_interval
        
        @tasks.loop(minutes=interval)
        async def check_rss_updates():
            """定期检查RSS更新"""
            for url, channels in self.rss_manager.feeds.items():
                for channel_id, feed in channels.items():
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if not channel:
                            self.logger.warning(f"找不到频道 {channel_id}，跳过RSS检查: {url}")
                            continue

                        items = await self.fetch_rss_items(
                            url,
                            after_timestamp=feed.last_update,
                            after_link=feed.latest_link
                        )

                        if not items:
                            continue

                        for item in items:
                            embed = await self._create_rss_embed(item)
                            try:
                                await channel.send(embed=embed)
                            except discord.HTTPException as e:
                                self.logger.error(f"发送RSS消息失败 {url} -> {channel_id}: {str(e)}")
                                continue

                        feed.last_update = max(feed.last_update, max((item.pubDate_timestamp for item in items), default=feed.last_update))
                        if items:
                            feed.latest_link = items[0].link
                        
                        # 更新成功状态
                        feed.error_count = 0
                        feed.last_error = None
                        feed.last_success = int(time.time())
                        self.rss_manager.save_data()

                    except Exception as e:
                        feed.error_count += 1
                        feed.last_error = f"{str(e)}\n{traceback.format_exc()}"
                        self.logger.error(f"检查RSS更新失败 {url} -> {channel_id}: {str(e)}\n{traceback.format_exc()}")
                        self.rss_manager.save_data()

                        # 如果连续失败次数过多，发送警告
                        if feed.error_count >= 3:
                            try:
                                embed = EmbedBuilder.error(
                                    title="RSS订阅异常",
                                    description=f"订阅源 `{url}` 已连续 {feed.error_count} 次更新失败\n"
                                              f"最后一次错误: {str(e)}\n"
                                              f"如果问题持续存在，建议使用 `!rss remove {url}` 取消订阅"
                                )
                                await channel.send(embed=embed)
                            except:
                                pass

        @check_rss_updates.before_loop
        async def before_check():
            await self.bot.wait_until_ready()

        self.check_rss_updates = check_rss_updates
        self.check_rss_updates.start()

    async def _create_rss_embed(self, item: RSSItem) -> discord.Embed:
        """创建RSS消息的Embed"""
        description = item.description
        if len(description) > self.config.description_max_length:
            description = description[:self.config.description_max_length] + "..."

        # 添加RSS源名称作为前缀
        title_prefix = f"[{item.chan_title}] " if item.chan_title else ""
        title = title_prefix + item.title[:self.config.title_max_length]

        embed = EmbedBuilder.info(
            title=title,
            description=description
        )

        if not self.config.is_hide_url:
            embed.url = item.link

        embed.timestamp = datetime.fromtimestamp(item.pubDate_timestamp) if item.pubDate_timestamp else discord.utils.utcnow()
        
        if item.pic_urls and self.config.pic_config["is_read_pic"]:
            max_pics = self.config.pic_config["max_pic_item"]
            for i, pic_url in enumerate(item.pic_urls[:max_pics]):
                if i == 0:
                    embed.set_image(url=pic_url)
                else:
                    # 对于额外的图片，添加到字段中
                    embed.add_field(name=f"附图 {i+1}", value=pic_url, inline=False)

        return embed

    def cog_unload(self):
        """插件卸载时的清理工作"""
        if self.check_rss_updates.is_running():
            self.check_rss_updates.cancel()

    async def parse_rss_feed(self, url: str) -> Optional[tuple[str, str]]:
        """解析RSS频道信息"""
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    text = await resp.text()
                    root = etree.fromstring(text.encode('utf-8'))
                    nsmap = root.nsmap.copy() if hasattr(root, 'nsmap') else {}
                    if None in nsmap:
                        nsmap['atom'] = nsmap.pop(None)
                    # 尝试不同的 XPath 路径来查找标题和描述，优先考虑命名空间
                    title = None
                    description = None
                    # 标题
                    for path in ["//channel/title", "//feed/title", "//atom:title", "//title"]:
                        elements = root.xpath(path, namespaces=nsmap) if 'atom' in path else root.xpath(path)
                        if elements and getattr(elements[0], 'text', None):
                            title = elements[0].text.strip()
                            break
                    # 描述
                    for path in ["//channel/description", "//feed/subtitle", "//feed/description", "//atom:subtitle", "//description"]:
                        elements = root.xpath(path, namespaces=nsmap) if 'atom' in path else root.xpath(path)
                        if elements and getattr(elements[0], 'text', None):
                            description = elements[0].text.strip()
                            break
                    if not title:
                        title = "未知频道"
                    if not description:
                        description = "无描述"
                    return title, description
        except Exception as e:
            self.logger.error(f"解析RSS频道失败: {url} - {str(e)}")
            return None

    async def fetch_rss_items(
        self,
        url: str,
        after_timestamp: int = 0,
        after_link: str = "",
        num: int = None
    ) -> List[RSSItem]:
        """从站点拉取RSS信息，自动兼容RSS与Atom格式"""
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        self.logger.error(f"无法获取RSS内容: {url}")
                        return []
                    text = await resp.text()
                    root = etree.fromstring(text.encode('utf-8'))
                    nsmap = root.nsmap.copy() if hasattr(root, 'nsmap') else {}
                    if None in nsmap:
                        nsmap['atom'] = nsmap.pop(None)
                    # 1. 支持Atom //entry
                    items = root.xpath("//item")
                    is_atom = False
                    if not items:
                        items = root.xpath("//atom:entry", namespaces=nsmap)
                        is_atom = True if items else False
                    if not items:
                        items = root.xpath("//entry")
                        is_atom = True if items else is_atom
                    if not items:
                        self.logger.error(f"未找到RSS/Atom条目: {url}")
                        return []
                    max_items = num if num is not None else self.config.max_items_per_poll
                    rss_items = []
                    for item in items:
                        try:
                            # 标题
                            title = None
                            for title_path in (["title", ".//title"] if not is_atom else ["atom:title", "title"]):
                                title_elements = item.xpath(title_path, namespaces=nsmap) if 'atom' in title_path else item.xpath(title_path)
                                if title_elements and (getattr(title_elements[0], 'text', None) or isinstance(title_elements[0], str)):
                                    title = title_elements[0].text.strip() if hasattr(title_elements[0], 'text') and title_elements[0].text else str(title_elements[0]).strip()
                                    break
                            if not title:
                                continue
                            if len(title) > self.config.title_max_length:
                                title = title[:self.config.title_max_length] + "..."
                            # 链接
                            link = None
                            if not is_atom:
                                for link_path in ["link", ".//link", ".//link/@href"]:
                                    link_elements = item.xpath(link_path)
                                    if link_elements:
                                        link = link_elements[0] if isinstance(link_elements[0], str) else link_elements[0].text
                                        if link:
                                            link = link.strip()
                                            break
                            else:
                                link_elements = item.xpath("atom:link/@href", namespaces=nsmap)
                                if not link_elements:
                                    link_elements = item.xpath("link/@href")
                                if link_elements:
                                    link = link_elements[0].strip()
                                else:
                                    link_elements = item.xpath("atom:link", namespaces=nsmap)
                                    if not link_elements:
                                        link_elements = item.xpath("link")
                                    if link_elements and hasattr(link_elements[0], 'text') and link_elements[0].text:
                                        link = link_elements[0].text.strip()
                            if not link:
                                continue
                            if not re.match(r"^https?://", link):
                                link = self.get_root_url(url) + link
                            # 描述
                            description = None
                            if not is_atom:
                                for desc_path in ["description", ".//description", "content", ".//content", "summary", ".//summary"]:
                                    desc_elements = item.xpath(desc_path)
                                    if desc_elements and getattr(desc_elements[0], 'text', None):
                                        description = desc_elements[0].text
                                        break
                            else:
                                for desc_path in ["atom:summary", "atom:content", "summary", "content"]:
                                    desc_elements = item.xpath(desc_path, namespaces=nsmap) if 'atom' in desc_path else item.xpath(desc_path)
                                    if desc_elements and (getattr(desc_elements[0], 'text', None) or isinstance(desc_elements[0], str)):
                                        description = desc_elements[0].text if hasattr(desc_elements[0], 'text') and desc_elements[0].text else str(desc_elements[0])
                                        break
                            if not description:
                                description = "无描述"
                            pic_urls = self.extract_images(description)
                            description = self.strip_html(description)
                            if len(description) > self.config.description_max_length:
                                description = description[:self.config.description_max_length] + "..."
                            # 频道标题
                            chan_title = ""
                            for chan_title_path in ["//channel/title", "//feed/title", "//atom:title"]:
                                chan_elements = root.xpath(chan_title_path, namespaces=nsmap) if 'atom' in chan_title_path else root.xpath(chan_title_path)
                                if chan_elements and getattr(chan_elements[0], 'text', None):
                                    chan_title = chan_elements[0].text.strip()
                                    break
                            # 时间
                            pub_date = ""
                            pub_date_timestamp = 0
                            if not is_atom:
                                date_paths = ["pubDate", ".//pubDate", "published", ".//published", "updated", ".//updated"]
                            else:
                                date_paths = ["atom:updated", "atom:published", "updated", "published"]
                            for date_path in date_paths:
                                date_elements = item.xpath(date_path, namespaces=nsmap) if 'atom' in date_path else item.xpath(date_path)
                                if date_elements and (getattr(date_elements[0], 'text', None) or isinstance(date_elements[0], str)):
                                    pub_date = date_elements[0].text.strip() if hasattr(date_elements[0], 'text') and date_elements[0].text else str(date_elements[0]).strip()
                                    try:
                                        date_formats = [
                                            "%a, %d %b %Y %H:%M:%S %z",
                                            "%Y-%m-%dT%H:%M:%S%z",
                                            "%Y-%m-%dT%H:%M:%SZ",
                                            "%Y-%m-%d %H:%M:%S"
                                        ]
                                        for date_format in date_formats:
                                            try:
                                                dt = pub_date
                                                if "GMT" in dt:
                                                    dt = dt.replace("GMT", "+0000")
                                                if "Z" in dt:
                                                    dt = dt.replace("Z", "+0000")
                                                pub_date_parsed = time.strptime(dt, date_format)
                                                pub_date_timestamp = int(time.mktime(pub_date_parsed))
                                                break
                                            except ValueError:
                                                continue
                                        if pub_date_timestamp == 0:
                                            pub_date_timestamp = int(time.time())
                                        break
                                    except:
                                        pub_date_timestamp = int(time.time())
                                    break
                            if pub_date_timestamp > after_timestamp or (pub_date_timestamp == 0 and link != after_link):
                                rss_items.append(
                                    RSSItem(
                                        chan_title=chan_title,
                                        title=title,
                                        link=link,
                                        description=description,
                                        pubDate=pub_date,
                                        pubDate_timestamp=pub_date_timestamp,
                                        pic_urls=pic_urls
                                    )
                                )
                                if max_items > 0 and len(rss_items) >= max_items:
                                    break
                            else:
                                break
                        except Exception as e:
                            self.logger.error(f"解析RSS/Atom条目失败: {url} - {str(e)}")
                            continue
                    return rss_items
        except Exception as e:
            self.logger.error(f"获取RSS内容失败: {url} - {str(e)}\n{traceback.format_exc()}")
            return []

    def strip_html(self, html: str) -> str:
        """移除HTML标签"""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        return re.sub(r"\n+", "\n", text)

    def extract_images(self, html: str) -> List[str]:
        """提取HTML中的图片URL"""
        soup = BeautifulSoup(html, "html.parser")
        return [img.get('src') for img in soup.find_all('img') if img.get('src')]

    def get_root_url(self, url: str) -> str:
        """获取URL的根域名"""
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    @commands.group(name="rss", invoke_without_command=True)
    async def rss(self, ctx):
        """RSS订阅管理"""
        if ctx.invoked_subcommand is None:
            commands = {
                "!rss add <url> [cron]": "添加RSS订阅，可选指定检查间隔",
                "!rss remove <url>": "移除RSS订阅",
                "!rss list": "查看当前频道的RSS订阅列表",
                "!rss info <url>": "查看RSS订阅详细信息",
                "!rss test <url>": "测试RSS订阅源",
                "!rss config": "查看和修改RSS配置"
            }
            await ctx.send(embed=EmbedBuilder.menu(
                title="RSS订阅管理",
                description="使用以下命令管理RSS订阅：",
                commands=commands
            ))

    @rss.command(name="add")
    async def add_feed(self, ctx, url: str, cron: str = "*/5 * * * *"):
        """添加RSS订阅
        用法：!rss add <url> [cron表达式]
        例如：!rss add https://rsshub.app/cngal/weekly
        """
        try:
            # 测试RSS源是否可用
            feed_info = await self.parse_rss_feed(url)
            if not feed_info:
                await ctx.send(embed=EmbedBuilder.error(
                    title="添加失败",
                    description="无法获取RSS源信息，请检查URL是否正确"
                ))
                return

            title, description = feed_info
            if self.rss_manager.add_feed(url, ctx.channel.id, cron):
                embed = EmbedBuilder.success(
                    title="RSS订阅添加成功",
                    description=f"**频道:** {title}\n**描述:** {description}\n**检查间隔:** {cron}"
                )
                # 添加测试获取
                try:
                    items = await self.fetch_rss_items(url, num=1)
                    if items:
                        embed.add_field(
                            name="最新文章",
                            value=f"**{items[0].title}**\n{items[0].description[:100]}...",
                            inline=False
                        )
                except Exception as e:
                    embed.add_field(
                        name="警告",
                        value=f"获取最新文章失败: {str(e)}",
                        inline=False
                    )
                await ctx.send(embed=embed)
            else:
                await ctx.send(embed=EmbedBuilder.warning(
                    title="添加失败",
                    description="该RSS源已经订阅"
                ))
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description=f"发生错误: {str(e)}"
            ))

    @rss.command(name="remove")
    async def remove_feed(self, ctx, url: str):
        """移除RSS订阅
        用法：!rss remove <url>
        例如：!rss remove https://rsshub.app/cngal/weekly
        """
        if self.rss_manager.remove_feed(url, ctx.channel.id):
            await ctx.send(embed=EmbedBuilder.success(
                title="RSS订阅已移除"
            ))
        else:
            await ctx.send(embed=EmbedBuilder.error(
                title="移除失败",
                description="未找到该RSS订阅"
            ))

    @rss.command(name="list")
    async def list_feeds(self, ctx):
        """列出当前频道的RSS订阅
        用法：!rss list
        """
        feeds = self.rss_manager.get_channel_feeds(ctx.channel.id)
        if not feeds:
            await ctx.send(embed=EmbedBuilder.info(
                title="RSS订阅列表",
                description="📭 当前频道没有RSS订阅"
            ))
            return

        fields = []
        for feed in feeds:
            feed_info = await self.parse_rss_feed(feed.url)
            title = feed_info[0] if feed_info else "未知频道"
            
            status = "✅ 正常"
            if feed.error_count > 0:
                status = f"⚠️ 异常 ({feed.error_count}次失败)"
            
            field_value = (
                f"**URL:** {feed.url}\n"
                f"**更新间隔:** {feed.cron_expr}\n"
                f"**状态:** {status}\n"
                f"**最后更新:** <t:{feed.last_update}:R>"
            )
            
            if feed.last_error:
                field_value += f"\n**最后错误:** ```{feed.last_error[:200]}...```" if len(feed.last_error) > 200 else f"\n**最后错误:** ```{feed.last_error}```"
            
            fields.append((title, field_value, False))

        embed = EmbedBuilder.stats(
            title="RSS订阅列表",
            description=f"当前频道共有 {len(feeds)} 个订阅：",
            author=ctx.author
        )
        
        # 逐个添加字段
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
            
        await ctx.send(embed=embed)

    @rss.command(name="info")
    async def feed_info(self, ctx, url: str):
        """查看RSS订阅详细信息
        用法：!rss info <url>
        例如：!rss info https://rsshub.app/cngal/weekly
        """
        feed = None
        for channel_feeds in self.rss_manager.feeds.get(url, {}).values():
            feed = channel_feeds
            break

        if not feed:
            await ctx.send(embed=EmbedBuilder.error(
                title="获取失败",
                description="未找到该RSS订阅"
            ))
            return

        try:
            items = await self.fetch_rss_items(url, num=3)
            feed_info = await self.parse_rss_feed(url)
            
            embed = EmbedBuilder.info(
                title=feed_info[0] if feed_info else "RSS订阅信息",
                description=feed_info[1] if feed_info else "无描述"
            )
            
            # 添加基本信息
            embed.add_field(
                name="基本信息",
                value=(
                    f"**URL:** {url}\n"
                    f"**更新间隔:** {feed.cron_expr}\n"
                    f"**最后更新:** <t:{feed.last_update}:R>\n"
                    f"**状态:** {'✅ 正常' if feed.error_count == 0 else f'⚠️ 异常 ({feed.error_count}次失败)'}"
                ),
                inline=False
            )
            
            # 添加最新文章（带链接）
            if items:
                latest_items = "\n\n".join(
                    f"**[{item.title}]({item.link})**\n{item.description[:100]}..." 
                    for item in items
                )
                embed.add_field(
                    name="最新文章",
                    value=latest_items,
                    inline=False
                )
            
            # 添加错误信息
            if feed.last_error:
                embed.add_field(
                    name="最后错误信息",
                    value=f"```{feed.last_error[:500]}...```" if len(feed.last_error) > 500 else f"```{feed.last_error}```",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="获取失败",
                description=f"获取RSS信息时发生错误: {str(e)}"
            ))

    @rss.command(name="test")
    async def test_feed(self, ctx, url: str):
        """测试RSS订阅源
        用法：!rss test <url>
        例如：!rss test https://rsshub.app/cngal/weekly
        """
        try:
            feed_info = await self.parse_rss_feed(url)
            if not feed_info:
                await ctx.send(embed=EmbedBuilder.error(
                    title="测试失败",
                    description="无法获取RSS源信息，请检查URL是否正确"
                ))
                return

            title, description = feed_info
            items = await self.fetch_rss_items(url, num=3)
            
            embed = EmbedBuilder.success(
                title="RSS源测试成功",
                description=f"**频道:** {title}\n**描述:** {description}"
            )
            
            if items:
                latest_items = "\n\n".join(
                    f"**[{item.title}]({item.link})**\n{item.description[:100]}..." 
                    for item in items
                )
                embed.add_field(
                    name="最新文章",
                    value=latest_items,
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="测试失败",
                description=f"测试RSS源时发生错误: {str(e)}\n{traceback.format_exc()}"
            ))

    @rss.group(name="config")
    @commands.has_permissions(administrator=True)
    async def rss_config(self, ctx):
        """RSS配置管理（需要管理员权限）
        用法：!rss config
        """
        if ctx.invoked_subcommand is None:
            current_config = {
                "检查间隔": f"{self.config.check_interval} 分钟",
                "标题最大长度": f"{self.config.title_max_length} 字符",
                "描述最大长度": f"{self.config.description_max_length} 字符",
                "单次获取最大条目数": str(self.config.max_items_per_poll),
                "隐藏链接": str(self.config.is_hide_url),
                "图片设置": (
                    f"读取图片: {self.config.pic_config['is_read_pic']}\n"
                    f"防和谐处理: {self.config.pic_config['is_adjust_pic']}\n"
                    f"最大图片数: {self.config.pic_config['max_pic_item']}"
                )
            }
            
            fields = [(k, v, True) for k, v in current_config.items()]
            await ctx.send(embed=EmbedBuilder.info(
                title="RSS 当前配置",
                description="使用 `!rss config set <配置项> <值>` 修改配置",
                fields=fields
            ))

    @rss_config.command(name="set")
    async def set_config(self, ctx, key: str, value: str):
        """设置RSS配置项
        用法：!rss config set <配置项> <值>
        例如：!rss config set check_interval 10
        """
        key = key.lower()
        try:
            if key == "check_interval":
                interval = int(value)
                if interval < 1:
                    raise ValueError("检查间隔必须大于0")
                
                # 更新配置
                self.config.check_interval = interval
                self._save_config(self.config)
                
                # 重新创建任务
                if self.check_rss_updates.is_running():
                    self.check_rss_updates.cancel()
                self._setup_rss_task()
                
                await ctx.send(embed=EmbedBuilder.success(
                    title="更新成功",
                    description=f"RSS检查间隔已更新为 {interval} 分钟"
                ))
            elif key in ["title_max_length", "description_max_length", "max_items_per_poll"]:
                val = int(value)
                if val < 1:
                    raise ValueError(f"{key} 必须大于0")
                setattr(self.config, key, val)
                self._save_config(self.config)
                await ctx.send(embed=EmbedBuilder.success(
                    title="更新成功",
                    description=f"{key} 已更新为 {val}"
                ))
            elif key == "is_hide_url":
                val = value.lower() in ["true", "1", "yes", "y"]
                self.config.is_hide_url = val
                self._save_config(self.config)
                await ctx.send(embed=EmbedBuilder.success(
                    title="更新成功",
                    description=f"隐藏链接已{'开启' if val else '关闭'}"
                ))
            elif key.startswith("pic_"):
                pic_key = key[4:]  # 移除 "pic_" 前缀
                if pic_key not in self.config.pic_config:
                    raise ValueError(f"无效的图片配置项: {pic_key}")
                
                if pic_key in ["is_read_pic", "is_adjust_pic"]:
                    val = value.lower() in ["true", "1", "yes", "y"]
                else:  # max_pic_item
                    val = int(value)
                    if val < 1:
                        raise ValueError("最大图片数必须大于0")
                
                self.config.pic_config[pic_key] = val
                self._save_config(self.config)
                await ctx.send(embed=EmbedBuilder.success(
                    title="更新成功",
                    description=f"图片配置 {pic_key} 已更新为 {val}"
                ))
            else:
                await ctx.send(embed=EmbedBuilder.error(
                    title="无效的配置项",
                    description=(
                        "可用的配置项：\n"
                        "- check_interval\n"
                        "- title_max_length\n"
                        "- description_max_length\n"
                        "- max_items_per_poll\n"
                        "- is_hide_url\n"
                        "- pic_is_read_pic\n"
                        "- pic_is_adjust_pic\n"
                        "- pic_max_pic_item"
                    )
                ))
        except ValueError as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="配置更新失败",
                description=str(e)
            ))
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="配置更新失败",
                description=f"发生错误: {str(e)}"
            ))

async def setup(bot):
    """加载插件时调用的初始化函数"""
    await bot.add_cog(RSS(bot)) 