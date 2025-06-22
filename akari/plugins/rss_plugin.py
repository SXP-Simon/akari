import discord
from discord.ext import commands, tasks
import aiohttp
import time
import re
import json
import os
import ssl
import asyncio
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
import html

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
    verify_ssl: bool = True  # 新增：是否验证SSL证书

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
    source_type: str = "RSS"  # RSS 或 Atom
    author: str = ""
    categories: List[str] = None
    icon_url: str = ""
    content: str = ""  # 完整内容
    summary: str = ""  # 摘要

    def __post_init__(self):
        if self.categories is None:
            self.categories = []

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
                        self.feeds[url][channel_id].last_update = feed_data.get(
                            "last_update", int(time.time()))
                        self.feeds[url][channel_id].latest_link = feed_data.get(
                            "latest_link", "")
                        self.feeds[url][channel_id].error_count = feed_data.get(
                            "error_count", 0)
                        self.feeds[url][channel_id].last_error = feed_data.get(
                            "last_error")
                        self.feeds[url][channel_id].last_success = feed_data.get(
                            "last_success", int(time.time()))
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

        # 设置SSL上下文
        self.ssl_context = self._create_ssl_context()

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
                        description_max_length=data.get(
                            "description_max_length", 500),
                        max_items_per_poll=data.get("max_items_per_poll", 3),
                        check_interval=data.get("check_interval", 5),
                        is_hide_url=data.get("is_hide_url", False),
                        pic_config=data.get("pic_config", None),
                        verify_ssl=data.get("verify_ssl", True)  # 新增：SSL验证配置
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
                "pic_config": config.pic_config,
                "verify_ssl": config.verify_ssl  # 新增：SSL验证配置
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存RSS配置失败: {str(e)}")

    def _create_ssl_context(self) -> ssl.SSLContext:
        """创建SSL上下文"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        return ssl_context

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
                            self.logger.warning(
                                f"找不到频道 {channel_id}，跳过RSS检查: {url}")
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
                                self.logger.error(
                                    f"发送RSS消息失败 {url} -> {channel_id}: {str(e)}")
                                continue

                        feed.last_update = max(feed.last_update, max(
                            (item.pubDate_timestamp for item in items), default=feed.last_update))
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
                        self.logger.error(
                            f"检查RSS更新失败 {url} -> {channel_id}: {str(e)}\n{traceback.format_exc()}")
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
        # 处理描述
        description = self.clean_html(item.description)
        logging.info(f"description: {description}")
        if len(description) > self.config.description_max_length:
            description = description[:self.config.description_max_length] + "..."

        # 根据源类型设置不同的颜色和图标
        if "github.com" in item.link:
            color = 0x24292e  # GitHub深色
            icon_url = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
            title = f"🔔 {item.title}"
        else:
            color = 0xFFA500  # RSS橙色
            icon_url = None
            title = item.title

        # 创建嵌入消息
        embed = discord.Embed(
            title=title,
            url=item.link if not self.config.is_hide_url else None,
            description=description,
            color=color,
            timestamp=datetime.fromtimestamp(
                item.pubDate_timestamp) if item.pubDate_timestamp else discord.utils.utcnow()
        )

        # 添加来源信息
        if icon_url:
            embed.set_author(name=item.chan_title, icon_url=icon_url)
        else:
            embed.set_author(name=item.chan_title)

        # 添加图片
        if item.pic_urls and self.config.pic_config["is_read_pic"]:
            max_pics = self.config.pic_config["max_pic_item"]
            for i, pic_url in enumerate(item.pic_urls[:max_pics]):
                if i == 0:
                    embed.set_image(url=pic_url)
                else:
                    embed.add_field(
                        name=f"附图 {i+1}",
                        value=f"[查看图片]({pic_url})",
                        inline=True
                    )

        return embed

    def _format_error(self, error: Exception) -> str:
        """格式化错误信息"""
        if isinstance(error, aiohttp.ClientError):
            return f"网络错误: {str(error)}\n建议检查网络连接或稍后重试"
        elif isinstance(error, etree.XMLSyntaxError):
            return f"XML解析错误: {str(error)}\n源格式可能不正确"
        elif isinstance(error, RSSNetworkError):
            if "SSL" in str(error):
                return f"{str(error)}\n可以尝试使用 `!rss config set verify_ssl false` 关闭SSL验证"
            return str(error)
        elif isinstance(error, RSSParseError):
            return f"解析错误: {str(error)}\n源内容可能不是有效的RSS/Atom格式"
        else:
            return f"未知错误: {str(error)}"

    async def _handle_feed_error(self, ctx, url: str, error: Exception):
        """处理Feed错误"""
        error_msg = self._format_error(error)

        embed = EmbedBuilder.error(
            title="RSS处理失败",
            description=f"处理RSS源时发生错误:\n```{error_msg}```"
        )

        embed.add_field(
            name="源信息",
            value=f"**URL:** {url}",
            inline=False
        )

        if isinstance(error, RSSNetworkError) and "SSL" in str(error):
            embed.add_field(
                name="建议操作",
                value="1. 检查URL是否正确\n2. 尝试关闭SSL验证: `!rss config set verify_ssl false`\n3. 等待几分钟后重试",
                inline=False
            )
        elif isinstance(error, RSSParseError):
            embed.add_field(
                name="建议操作",
                value="1. 检查URL是否为有效的RSS/Atom源\n2. 在浏览器中打开URL检查内容\n3. 使用 `!rss test <url>` 测试源",
                inline=False
            )

        await ctx.send(embed=embed)

    def cog_unload(self):
        """插件卸载时的清理工作"""
        if self.check_rss_updates.is_running():
            self.check_rss_updates.cancel()

    def _normalize_url(self, url: str) -> str:
        """规范化URL"""
        # 处理GitHub URL
        if "github.com" in url:
            # 移除末尾的斜杠
            url = url.rstrip("/")

            # 处理用户活动feed
            if url.endswith(".atom"):
                return url

            # 处理仓库feed
            if not url.endswith("/releases.atom"):
                # 检查是否是仓库URL
                parts = url.split("/")
                if len(parts) >= 5 and parts[2] == "github.com":
                    # 添加releases.atom
                    return f"{url}/releases.atom"

        return url

    def _handle_ssl_error(self, error: Exception) -> str:
        """处理SSL错误"""
        error_str = str(error)
        if "CERTIFICATE_VERIFY_FAILED" in error_str:
            return "SSL证书验证失败，可能是自签名证书或证书过期"
        elif "WRONG_VERSION_NUMBER" in error_str:
            return "SSL版本不匹配，服务器可能不支持安全连接"
        elif "DECRYPTION_FAILED_OR_BAD_RECORD_MAC" in error_str:
            return "SSL解密失败，可能是网络问题或代理设置导致"
        else:
            return f"SSL错误: {error_str}"

    async def parse_rss_feed(self, url: str) -> Optional[tuple[str, str]]:
        """解析RSS频道信息"""
        try:
            # 规范化URL
            url = self._normalize_url(url)

            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/atom+xml,application/xml,application/rss+xml,text/xml;q=0.9,*/*;q=0.8"
            }

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        self.logger.error(
                            f"获取RSS源失败: {url}, 状态码: {resp.status}")
                        return None

                    try:
                        text = await resp.text()
                    except UnicodeDecodeError:
                        # 如果UTF-8解码失败，尝试其他编码
                        content = await resp.read()
                        for encoding in ['utf-8', 'gbk', 'gb2312', 'iso-8859-1']:
                            try:
                                text = content.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            self.logger.error(f"无法解码RSS内容: {url}")
                            return None

                    try:
                        root = etree.fromstring(text.encode('utf-8'))
                    except etree.XMLSyntaxError as e:
                        # 尝试修复常见的XML问题
                        text = text.replace('&', '&amp;')
                        try:
                            root = etree.fromstring(text.encode('utf-8'))
                        except etree.XMLSyntaxError:
                            self.logger.error(
                                f"解析RSS XML失败: {url}, 错误: {str(e)}")
                            return None

                    # 获取所有命名空间
                    namespaces = {}
                    for key, value in root.nsmap.items():
                        if key is not None:
                            namespaces[key] = value
                        else:
                            # 处理默认命名空间
                            namespaces['default'] = value

                    # 检测feed类型
                    is_atom = root.tag.endswith('feed')

                    # 根据feed类型选择不同的XPath
                    if is_atom:
                        title_paths = [
                            "//default:title/text()",
                            "//atom:title/text()",
                            "//title/text()"
                        ]
                        desc_paths = [
                            "//default:subtitle/text()",
                            "//atom:subtitle/text()",
                            "//default:summary/text()",
                            "//atom:summary/text()"
                        ]
                    else:
                        title_paths = [
                            "//channel/title/text()",
                            "//default:title/text()",
                            "//title/text()"
                        ]
                        desc_paths = [
                            "//channel/description/text()",
                            "//default:description/text()",
                            "//description/text()"
                        ]

                    # 尝试获取标题
                    title = None
                    for xpath in title_paths:
                        try:
                            titles = root.xpath(xpath, namespaces=namespaces)
                            if titles:
                                title = titles[0].strip()
                            break
                        except:
                            continue

                    # 尝试获取描述
                    description = None
                    for xpath in desc_paths:
                        try:
                            descs = root.xpath(xpath, namespaces=namespaces)
                            if descs:
                                description = descs[0].strip()
                            break
                        except:
                            continue

                    if not title:
                        title = "未知频道"
                    if not description:
                        description = "无描述"

                    return title, description

        except aiohttp.ClientError as e:
            self.logger.error(f"获取RSS源网络错误: {url} - {str(e)}")
            raise RSSNetworkError(f"网络错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"解析RSS源失败: {url} - {str(e)}")
            raise RSSParseError(f"解析错误: {str(e)}")

    async def fetch_rss_items(
        self,
        url: str,
        after_timestamp: int = 0,
        after_link: str = "",
        num: int = None
    ) -> List[RSSItem]:
        """从站点拉取RSS信息"""
        try:
            # 规范化URL
            url = self._normalize_url(url)

            # 配置SSL上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # 配置连接器和超时
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            timeout = aiohttp.ClientTimeout(total=30)

            # 设置请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/atom+xml,application/xml,application/rss+xml,text/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "close"  # 避免保持连接
            }

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers,
                trust_env=True
            ) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        self.logger.error(
                            f"获取RSS源失败: {url}, 状态码: {resp.status}")
                        return []

                    try:
                        text = await resp.text()
                        # 尝试修复常见的XML问题
                        text = text.replace('xmlns=""', '')  # 移除空的命名空间声明
                        # 移除空的前缀命名空间
                        text = re.sub(r'xmlns:([a-zA-Z0-9]+)=""', '', text)

                        # 解析XML
                        parser = etree.XMLParser(recover=True)  # 启用恢复模式
                        root = etree.fromstring(
                            text.encode('utf-8'), parser=parser)
                    except Exception as e:
                        self.logger.error(f"解析RSS内容失败: {url} - {str(e)}")
                        return []

                    # 获取所有命名空间
                    namespaces = {}
                    for key, value in root.nsmap.items():
                        if key is None:
                            namespaces['default'] = value
                            namespaces['atom'] = value  # 为Atom格式添加显式命名空间
                        else:
                            namespaces[key] = value

                    # 检测feed类型
                    is_atom = 'http://www.w3.org/2005/Atom' in root.nsmap.values()

                    # 根据feed类型选择不同的XPath
                    if is_atom:
                        items = root.xpath(
                            "//entry | //atom:entry", namespaces=namespaces)
                        chan_title = self._get_feed_title(
                            root, namespaces, is_atom)
                        if "github.com" in url:
                            # 为GitHub源添加额外信息
                            repo_info = self._get_github_repo_info(
                                root, namespaces)
                            if repo_info:
                                chan_title = f"GitHub - {repo_info}"
                    else:
                        items = root.xpath("//item", namespaces=namespaces)
                        chan_title = self._get_feed_title(
                            root, namespaces, is_atom)

                    if not items:
                        self.logger.error(f"未找到RSS/Atom条目: {url}")
                        return []

                    max_items = num if num is not None else self.config.max_items_per_poll
                    rss_items = []

                    for item in items:
                        try:
                            # 根据feed类型获取信息
                            if is_atom:
                                title = self._get_text(
                                    item, ["title", "atom:title"], namespaces)
                                link = self._get_link(item, namespaces)
                                content = self._get_text(item, [
                                    "content", "atom:content",
                                    "summary", "atom:summary"
                                ], namespaces)
                                updated = self._get_text(item, [
                                    "updated", "atom:updated",
                                    "published", "atom:published"
                                ], namespaces)
                            else:
                                title = self._get_text(
                                    item, ["title"], namespaces)
                                link = self._get_text(
                                    item, ["link"], namespaces)
                                content = self._get_text(
                                    item, ["description"], namespaces)
                                updated = self._get_text(
                                    item, ["pubDate"], namespaces)

                            if not title or not link:
                                continue

                            if not content:
                                content = "无描述"

                            # 处理日期
                            pub_date_timestamp = self._parse_date(updated)

                            # 提取图片
                            pic_urls = self.extract_images(content)

                            # 清理描述文本
                            description = self.strip_html(content)

                            if pub_date_timestamp > after_timestamp or (pub_date_timestamp == 0 and link != after_link):
                                rss_items.append(
                                    RSSItem(
                                        chan_title=chan_title,
                                        title=title,
                                        link=link,
                                        description=description,
                                        pubDate=updated or "",
                                        pubDate_timestamp=pub_date_timestamp,
                                        pic_urls=pic_urls
                                    )
                                )

                                if max_items > 0 and len(rss_items) >= max_items:
                                    break

                        except Exception as e:
                            self.logger.error(f"解析RSS条目失败: {url} - {str(e)}")
                            continue

                    return rss_items

        except Exception as e:
            self.logger.error(
                f"获取RSS内容失败: {url} - {str(e)}\n{traceback.format_exc()}")
            return []

    def _get_feed_title(self, root, namespaces: dict, is_atom: bool) -> str:
        """获取Feed标题"""
        if is_atom:
            for xpath in ["//title", "//atom:title"]:
                title = self._get_text(root, [xpath], namespaces)
                if title:
                    return title
        else:
            for xpath in ["//channel/title", "//title"]:
                title = self._get_text(root, [xpath], namespaces)
                if title:
                    return title
        return "未知频道"

    def _get_github_repo_info(self, root, namespaces: dict) -> Optional[str]:
        """获取GitHub仓库信息"""
        try:
            # 获取仓库名称
            repo_name = self._get_text(root, ["//title"], namespaces)
            if repo_name:
                repo_name = repo_name.replace(" - Atom", "").strip()

            # 获取仓库描述
            description = self._get_text(
                root, ["//subtitle", "//atom:subtitle"], namespaces)

            if repo_name:
                if description:
                    return f"{repo_name} - {description}"
                return repo_name
            return None
        except:
            return None

    def _get_text(self, element, paths: List[str], namespaces: dict) -> Optional[str]:
        """获取XML元素的文本内容"""
        for path in paths:
            try:
                elements = element.xpath(path, namespaces=namespaces)
                if elements and elements[0].text:
                    return elements[0].text.strip()
            except:
                continue
        return None

    def _get_link(self, element, namespaces: dict) -> Optional[str]:
        """获取Atom feed中的链接"""
        # 首先尝试获取link元素的href属性
        for path in ["default:link/@href", "atom:link/@href", "link/@href"]:
            try:
                hrefs = element.xpath(path, namespaces=namespaces)
                if hrefs:
                    return hrefs[0].strip()
            except:
                continue

        # 如果没有找到href属性，尝试获取link元素的文本内容
        for path in ["default:link/text()", "atom:link/text()", "link/text()"]:
            try:
                links = element.xpath(path, namespaces=namespaces)
                if links:
                    return links[0].strip()
            except:
                continue

        return None

    def _parse_date(self, date_str: Optional[str]) -> int:
        """解析日期字符串为时间戳"""
        if not date_str:
            return 0

        date_formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RSS标准格式
            "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",        # ISO 8601 UTC
            "%Y-%m-%d %H:%M:%S",         # 简单格式
            "%a, %d %b %Y %H:%M:%S GMT",  # 另一种RSS格式
            "%Y-%m-%dT%H:%M:%S.%f%z",    # 带毫秒的ISO 8601
            "%Y-%m-%dT%H:%M:%S.%fZ"      # 带毫秒的ISO 8601 UTC
        ]

        # 预处理日期字符串
        date_str = date_str.strip()
        if "GMT" in date_str:
            date_str = date_str.replace("GMT", "+0000")
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+0000"

        # 尝试不同的日期格式
        for date_format in date_formats:
            try:
                parsed_time = time.strptime(date_str, date_format)
                return int(time.mktime(parsed_time))
            except ValueError:
                continue

        return int(time.time())

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

    def clean_html(self,html_content):
        """清理 HTML 标签并转换实体字符"""
        if not html_content:
            return ""
        # 转换 HTML 实体字符
        unescaped = html.unescape(html_content)
        # 移除 HTML 标签
        soup = BeautifulSoup(unescaped, "html.parser")
        # 获取纯文本内容
        text = soup.get_text()
        # 处理多余的空白字符
        cleaned_text = " ".join(text.split())
        return cleaned_text

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
        """添加RSS订阅"""
        try:
            # 规范化URL
            url = self._normalize_url(url)

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
                # 创建成功提示
                embed = EmbedBuilder.success(
                    title="RSS订阅添加成功",
                    description=f"**{title}**\n{description}"
                )

                # 添加订阅设置
                cron_desc = self._format_cron(cron)
                embed.add_field(
                    name="订阅设置",
                    value=f"**检查间隔:** {cron_desc}\n**URL:** {url}",
                    inline=False
                )

                # 尝试获取最新文章
                try:
                    items = await self.fetch_rss_items(url, num=1)
                    if items:
                        item = items[0]
                        embed.add_field(
                            name="最新文章",
                            value=f"**[{item.title}]({item.link})**\n{item.description[:100]}...",
                            inline=False
                        )
                except Exception as e:
                    self.logger.error(f"获取最新文章失败: {url} - {str(e)}")

                await ctx.send(embed=embed)
            else:
                await ctx.send(embed=EmbedBuilder.warning(
                    title="添加失败",
                    description="该RSS源已经订阅"
                ))
        except RSSNetworkError as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description=f"网络错误: {str(e)}\n如果是SSL错误，请尝试使用 `!rss config set verify_ssl false` 关闭SSL验证"
            ))
        except RSSParseError as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description=f"解析错误: {str(e)}"
            ))
        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="添加失败",
                description=f"发生错误: {str(e)}\n{traceback.format_exc()}"
            ))

    def _format_cron(self, cron: str) -> str:
        """格式化cron表达式为友好显示"""
        parts = cron.split()
        if len(parts) == 5 and parts[0].startswith("*/"):
            try:
                minutes = int(parts[0][2:])
                if minutes == 1:
                    return "每分钟"
                return f"每{minutes}分钟"
            except:
                pass
        return cron

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
                field_value += f"\n**最后错误:** ```{feed.last_error[:200]}...```" if len(
                    feed.last_error) > 200 else f"\n**最后错误:** ```{feed.last_error}```"

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
            feed_info = await self.parse_rss_feed(url)
            if not feed_info:
                await ctx.send(embed=EmbedBuilder.error(
                    title="获取失败",
                    description="无法获取RSS源信息"
                ))
                return

            title, description = feed_info
            embed = EmbedBuilder.info(
                title=title,
                description=description
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

            # 尝试获取最新文章
            try:
                items = await self.fetch_rss_items(url, num=3)
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
            except Exception as e:
                embed.add_field(
                    name="警告",
                    value=f"获取最新文章失败: {str(e)}",
                    inline=False
                )

            # 添加错误信息
            if feed.last_error:
                embed.add_field(
                    name="最后错误信息",
                    value=f"```{feed.last_error[:500]}...```" if len(
                        feed.last_error) > 500 else f"```{feed.last_error}```",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(embed=EmbedBuilder.error(
                title="获取失败",
                description=f"获取RSS信息时发生错误: {str(e)}\n{traceback.format_exc()}"
            ))

    @rss.command(name="test")
    async def test_feed(self, ctx, url: str):
        """测试RSS订阅源"""
        try:
            # 规范化URL
            url = self._normalize_url(url)

            # 测试RSS源
            feed_info = await self.parse_rss_feed(url)
            if not feed_info:
                await ctx.send(embed=EmbedBuilder.error(
                    title="测试失败",
                    description="无法获取RSS源信息，请检查URL是否正确"
                ))
                return

            title, description = feed_info
            logging.info(f"title: {title}, description: {description}")
            # 创建测试结果嵌入消息
            embed = EmbedBuilder.success(
                title="RSS源测试成功",
                description=f"**{title}**\n{description}"
            )

            # 获取最新文章
            try:
                items = await self.fetch_rss_items(url, num=3)
                if items:
                    latest_items = []
                    for i, item in enumerate(items, 1):
                        latest_items.append(
                            f"**{i}. [{item.title}]({item.link})**\n"
                            f"{self.clean_html(item.description)[:100]}..."
                        )

                    embed.add_field(
                        name="最新文章",
                        value="\n\n".join(latest_items),
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name="警告",
                    value=f"获取最新文章失败: {self._format_error(e)}",
                    inline=False
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await self._handle_feed_error(ctx, url, e)

    @rss.group(name="config")
    @commands.has_permissions(administrator=True)
    async def rss_config(self, ctx):
        """RSS配置管理（需要管理员权限）"""
        if ctx.invoked_subcommand is None:
            current_config = {
                "检查间隔": f"{self.config.check_interval} 分钟",
                "标题最大长度": f"{self.config.title_max_length} 字符",
                "描述最大长度": f"{self.config.description_max_length} 字符",
                "单次获取最大条目数": str(self.config.max_items_per_poll),
                "隐藏链接": str(self.config.is_hide_url),
                "SSL验证": str(self.ssl_context.verify_mode == ssl.CERT_REQUIRED),
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
        """设置RSS配置项"""
        key = key.lower()
        try:
            if key == "verify_ssl":
                val = value.lower() in ["true", "1", "yes", "y"]
                self.ssl_context.verify_mode = ssl.CERT_REQUIRED if val else ssl.CERT_NONE
                await ctx.send(embed=EmbedBuilder.success(
                    title="更新成功",
                    description=f"SSL验证已{'开启' if val else '关闭'}"
                ))
            elif key == "check_interval":
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
                        "- verify_ssl (true/false)\n"
                        "- check_interval (分钟)\n"
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

    async def _create_info_embed(self, feed_info: tuple[str, str], url: str) -> discord.Embed:
        """创建RSS信息的Embed

        Args:
            feed_info: (标题, 描述)的元组
            url: RSS源URL
        """
        title, description = feed_info
        embed = EmbedBuilder.info(
            title="RSS源信息",
            description=f"**频道:** {title}\n**描述:** {description}"
        )

        # 尝试获取最新文章
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

        return embed


async def setup(bot):
    """加载插件时调用的初始化函数"""
    await bot.add_cog(RSS(bot))
