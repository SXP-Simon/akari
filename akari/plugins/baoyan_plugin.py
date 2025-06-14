import json
import os
import time
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set
import discord
from discord.ext import commands, tasks
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

# 数据存储目录
DATA_DIR = os.path.join("data", "baoyan")
# 远程数据源URL
REMOTE_URL = "https://ddl.csbaoyan.top/config/schools.json"
# 更新间隔（分钟）
UPDATE_INTERVAL = 30
# 显示限制（避免超过Discord消息长度限制）
MAX_DISPLAY_ITEMS = 10
# 通知检查间隔（秒）
NOTIFICATION_INTERVAL = 3600  # 1小时检查一次

def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)

def setup(bot):
    """插件初始化函数"""
    ensure_data_dir()
    plugin = BaoyanPlugin(bot)
    bot.add_cog(plugin)

# =====================
# akari.plugins.baoyan_plugin
# =====================

"""
BaoyanPlugin: 计算机保研信息插件

- 支持保研项目信息查询、搜索、标签筛选
- 自动/手动数据更新与通知
- 本地与远程数据源管理
- Discord 命令集成

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

class BaoyanPlugin(commands.Cog):
    """计算机保研信息插件"""
    def __init__(self, bot):
        self.bot = bot
        self.data_sources = {}
        self.default_source = None
        self.last_update_time = 0
        self.known_programs = set()
        self.known_programs_file = os.path.join(DATA_DIR, "known_programs.json")
        self.load_data_sources()
        self.load_known_programs()
        self.update_task = None
        self.notification_task = None
        self.start_tasks()

    @commands.group(name="baoyan", description="计算机保研信息查询（输入 !baoyan help 查看详细用法）", invoke_without_command=True)
    async def baoyan(self, ctx):
        """保研命令组"""
        embed = EmbedBuilder.create(EmbedData(
            title="计算机保研信息查询命令",
            description="输入 !baoyan help 查看详细用法",
            color=EmbedBuilder.THEME.special
        ))
        
        commands_dict = {
            "!baoyan list": "列出保研项目，可选标签",
            "!baoyan search <关键词>": "搜索项目，支持模糊匹配",
            "!baoyan upcoming": "列出30天内即将截止的项目",
            "!baoyan detail <名称>": "查看项目详细信息",
            "!baoyan tags": "查看所有可用标签",
            "!baoyan sources": "查看所有数据源",
            "!baoyan update": "更新保研数据（需管理员）"
        }
        
        for cmd, desc in commands_dict.items():
            embed.add_field(name=cmd, value=desc, inline=True)
        
        await ctx.reply(embed=embed)

    @baoyan.command(name="list", description="列出保研项目（可选标签筛选，多个标签用逗号分隔）")
    async def list_programs_cmd(self, ctx, tag: str = None):
        """列出保研项目（可选标签筛选）"""
        await self.list_programs(ctx, tag)

    @baoyan.command(name="search", description="搜索保研项目（关键词支持模糊匹配）")
    async def search_programs_cmd(self, ctx, *, keyword: str):
        """搜索保研项目（关键词支持模糊匹配）"""
        await self.search_programs(ctx, keyword)

    @baoyan.command(name="upcoming", description="查看30天内即将截止的项目（可选标签筛选）")
    async def list_upcoming_cmd(self, ctx, tag: str = None):
        """查看30天内即将截止的项目（可选标签筛选）"""
        await self.list_upcoming(ctx, tag)

    @baoyan.command(name="detail", description="查看项目详情（支持关键词）")
    async def program_detail_cmd(self, ctx, *, name: str):
        """查看项目详情（支持关键词）"""
        await self.program_detail(ctx, name)

    @baoyan.command(name="tags", description="查看所有可用标签")
    async def list_tags_cmd(self, ctx):
        """查看所有可用标签"""
        await self.list_tags(ctx)

    @baoyan.command(name="sources", description="查看所有数据源")
    async def list_sources_cmd(self, ctx):
        """查看所有数据源"""
        await self.list_sources(ctx)

    @baoyan.command(name="update", description="更新保研数据（需管理员权限）")
    @commands.has_permissions(administrator=True)
    async def manual_update_cmd(self, ctx):
        """更新保研数据（需管理员权限）"""
        await self.manual_update(ctx)

    def start_tasks(self):
        self.auto_update_data.start()
        self.check_notifications.start()
    async def on_unload(self):
        if self.update_task and not self.update_task.is_being_cancelled():
            self.update_task.cancel()
        if self.notification_task and not self.notification_task.is_being_cancelled():
            self.notification_task.cancel()
        self.save_known_programs()
    @tasks.loop(minutes=UPDATE_INTERVAL)
    async def auto_update_data(self):
        try:
            print(f"[保研插件] 正在自动更新保研信息数据...")
            await self.update_data_from_remote()
        except Exception as e:
            print(f"[保研插件] 自动更新保研信息数据出错: {e}")
    @tasks.loop(seconds=NOTIFICATION_INTERVAL)
    async def check_notifications(self):
        try:
            print("[保研插件] 开始检查新增保研信息...")
            all_programs = []
            for source, programs in self.data_sources.items():
                all_programs.extend(programs)
            await self.check_new_programs(all_programs)
            print("[保研插件] 保研信息检查完成")
        except Exception as e:
            print(f"[保研插件] 通知检查任务出错: {e}")
    async def check_new_programs(self, programs):
        new_programs = []
        current_program_ids = set()
        for program in programs:
            program_id = self.generate_program_id(program)
            current_program_ids.add(program_id)
            if program_id not in self.known_programs:
                new_programs.append(program)
        self.known_programs = current_program_ids
        self.save_known_programs()
        if new_programs:
            notification_channel_id = self.get_notification_channel_id()
            if notification_channel_id:
                channel = self.bot.get_channel(notification_channel_id)
                if channel:
                    embed = EmbedBuilder.info(
                        title="📢 有新增的保研项目！",
                        description=f"共 {len(new_programs)} 个新项目，使用 !baoyan list 查看全部。"
                    )
                    for i, program in enumerate(new_programs[:MAX_DISPLAY_ITEMS], 1):
                        value = f"描述: {program.get('description', '')}\n截止日期: {self.format_time_remaining(program.get('deadline', ''))}\n[官方网站]({program.get('website', '')})"
                        embed.add_field(name=f"{i}. {program.get('name', '')} - {program.get('institute', '')}", value=value, inline=False)
                    await channel.send(embed=embed)
    def get_notification_channel_id(self):
        return None
    def generate_program_id(self, program):
        return f"{program.get('name', '')}:{program.get('institute', '')}:{program.get('description', '')}"
    def load_known_programs(self):
        if os.path.exists(self.known_programs_file):
            try:
                with open(self.known_programs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.known_programs = set(data)
                print(f"[保研插件] 已加载 {len(self.known_programs)} 个已知项目ID")
            except Exception as e:
                print(f"[保研插件] 加载已知项目数据出错: {e}")
                self.known_programs = set()
        else:
            print("[保研插件] 已知项目数据文件不存在，将创建新的数据")
            self.known_programs = set()
            self.save_known_programs()
    def save_known_programs(self):
        try:
            with open(self.known_programs_file, "w", encoding="utf-8") as f:
                json.dump(list(self.known_programs), f, ensure_ascii=False, indent=4)
            print("[保研插件] 已知项目ID已保存")
        except Exception as e:
            print(f"[保研插件] 保存已知项目ID出错: {e}")
    def load_data_sources(self):
        data_file = os.path.join(DATA_DIR, "sources.json")
        if os.path.exists(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    self.data_sources = json.load(f)
                if self.data_sources:
                    self.default_source = next(iter(self.data_sources))
                self.last_update_time = os.path.getmtime(data_file)
                print(f"[保研插件] 从本地缓存加载保研信息数据成功，共 {len(self.data_sources)} 个数据源")
            except Exception as e:
                print(f"[保研插件] 从本地缓存加载数据源出错: {e}")
                self.data_sources = {}
        else:
            print("[保研插件] 本地缓存不存在，将尝试从远程获取数据")
    async def update_data_from_remote(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REMOTE_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        data_file = os.path.join(DATA_DIR, "sources.json")
                        with open(data_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                        self.data_sources = data
                        if self.data_sources and not self.default_source:
                            self.default_source = next(iter(self.data_sources))
                        self.last_update_time = time.time()
                        print("[保研插件] 保研信息数据更新成功")
                        return True
                    else:
                        print(f"[保研插件] 获取远程数据失败，状态码: {response.status}")
                        return False
        except Exception as e:
            print(f"[保研插件] 更新远程数据出错: {e}")
            return False
    def get_programs(self, tag: str = None) -> List[Dict]:
        source = self.default_source
        if source not in self.data_sources:
            return []
        programs = self.data_sources[source]
        result = []
        tags = []
        tag = str(tag) if tag else None
        if tag:
            tags = [t.strip() for t in tag.split(",") if t.strip()]
        for program in programs:
            if tags:
                if not any(t in program.get("tags", []) for t in tags):
                    continue
            result.append(program)
        return result
    def format_time_remaining(self, deadline_str: str) -> str:
        if not deadline_str:
            return "未知"
        try:
            tz_bj = timezone(timedelta(hours=8))
            now = datetime.now(tz_bj)
            deadline = None
            if "Z" in deadline_str:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            elif "+" in deadline_str or "-" in deadline_str and "T" in deadline_str:
                deadline = datetime.fromisoformat(deadline_str)
            else:
                deadline = datetime.fromisoformat(deadline_str)
                deadline = deadline.replace(tzinfo=tz_bj)
            if deadline < now:
                return "已截止"
            diff = deadline - now
            days = diff.days
            hours = diff.seconds // 3600
            if days > 0:
                return f"剩余 {days} 天 {hours} 小时"
            else:
                return f"剩余 {hours} 小时"
        except Exception as e:
            print(f"[保研插件] 格式化时间出错: {e}")
            return "未知"
    def parse_deadline(self, deadline_str):
        try:
            tz_bj = timezone(timedelta(hours=8))
            if "Z" in deadline_str:
                return datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            elif "+" in deadline_str or "-" in deadline_str and "T" in deadline_str:
                return datetime.fromisoformat(deadline_str)
            else:
                deadline = datetime.fromisoformat(deadline_str)
                return deadline.replace(tzinfo=tz_bj)
        except:
            return None
    def get_program_timestamp(self, deadline_str: str) -> float:
        if not deadline_str:
            return float("inf")
        try:
            deadline = self.parse_deadline(deadline_str)
            if deadline:
                return deadline.timestamp()
            return float("inf")
        except Exception as e:
            print(f"[保研插件] 获取时间戳出错: {e}")
            return float("inf")
    async def list_programs(self, ctx, tag: str = None):
        source = self.default_source
        if source not in self.data_sources:
            embed = EmbedBuilder.error(
                title="数据源不存在",
                description=f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        programs = self.get_programs(tag)
        if not programs:
            embed = EmbedBuilder.warning(
                title="无项目",
                description="没有找到符合条件的保研项目"
            )
            await ctx.reply(embed=embed)
            return
        embed = EmbedBuilder.create(EmbedData(
            title="保研项目列表",
            description=f"数据源: {source}" + (f"\n标签筛选: {tag}" if tag else ""),
            color=EmbedBuilder.THEME.primary
        ))
        display_limit = MAX_DISPLAY_ITEMS
        for i, program in enumerate(programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            value = f"描述: {program.get('description', '')}\n截止日期: {deadline}\n[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            embed.add_field(name=name, value=value, inline=False)
        await ctx.reply(embed=embed)
        if len(programs) > display_limit:
            embed = EmbedBuilder.info(
                title="项目过多",
                description=f"共找到 {len(programs)} 个项目，仅显示前 {display_limit} 个。请使用更具体的标签筛选。"
            )
            await ctx.reply(embed=embed)
    async def search_programs(self, ctx, keyword: str):
        source = self.default_source
        if source not in self.data_sources:
            embed = EmbedBuilder.error(
                title="数据源不存在",
                description=f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        if not keyword:
            embed = EmbedBuilder.warning(
                title="缺少关键词",
                description="请提供搜索关键词"
            )
            await ctx.reply(embed=embed)
            return
        keyword = keyword.lower()
        matching_programs = []
        for program in self.data_sources[source]:
            if (
                keyword in program.get("name", "").lower()
                or keyword in program.get("institute", "").lower()
                or keyword in program.get("description", "").lower()
            ):
                matching_programs.append(program)
        if not matching_programs:
            embed = EmbedBuilder.warning(
                title="无匹配项目",
                description=f"没有找到包含关键词 '{keyword}' 的项目"
            )
            await ctx.reply(embed=embed)
            return
        embed = EmbedBuilder.create(EmbedData(
            title=f"搜索结果: '{keyword}'",
            description=f"数据源: {source}\n找到 {len(matching_programs)} 个匹配项目",
            color=EmbedBuilder.THEME.primary
        ))
        display_limit = MAX_DISPLAY_ITEMS
        for i, program in enumerate(matching_programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            value = f"描述: {program.get('description', '')}\n截止日期: {deadline}\n[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            embed.add_field(name=name, value=value, inline=False)
        await ctx.reply(embed=embed)
        if len(matching_programs) > display_limit:
            embed = EmbedBuilder.info(
                title="匹配项目过多",
                description=f"共找到 {len(matching_programs)} 个匹配项目，仅显示前 {display_limit} 个。请尝试使用更具体的关键词。"
            )
            await ctx.reply(embed=embed)
    async def list_upcoming(self, ctx, tag: str = None):
        source = self.default_source
        days = 30
        if source not in self.data_sources:
            embed = EmbedBuilder.error(
                title="数据源不存在",
                description=f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        tz_bj = timezone(timedelta(hours=8))
        now = datetime.now(tz_bj)
        deadline_ts = now.timestamp() + days * 86400
        tags = []
        tag = str(tag) if tag else None
        if tag:
            tags = [t.strip() for t in tag.split(",") if t.strip()]
        upcoming_programs = []
        for program in self.data_sources[source]:
            try:
                deadline_str = program.get("deadline", "")
                if not deadline_str:
                    continue
                deadline = self.parse_deadline(deadline_str)
                if not deadline:
                    continue
                if tags:
                    if not any(t in program.get("tags", []) for t in tags):
                        continue
                program_deadline_ts = deadline.timestamp()
                if now.timestamp() <= program_deadline_ts <= deadline_ts:
                    upcoming_programs.append(program)
            except Exception as e:
                print(f"[保研插件] 处理截止日期时出错: {e}, deadline_str={program.get('deadline', '')}")
        upcoming_programs.sort(key=lambda x: self.get_program_timestamp(x["deadline"]))
        if not upcoming_programs:
            embed = EmbedBuilder.info(
                title="无即将截止项目",
                description=f"未找到 {days} 天内即将截止的项目" + (f"（标签：{tag}）" if tag else "")
            )
            await ctx.reply(embed=embed)
            return
        embed = EmbedBuilder.create(EmbedData(
            title=f"{days}天内即将截止的项目",
            description=f"数据源: {source}" + (f"\n标签筛选: {tag}" if tag else ""),
            color=EmbedBuilder.THEME.danger
        ))
        display_limit = MAX_DISPLAY_ITEMS
        for i, program in enumerate(upcoming_programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            value = f"描述: {program.get('description', '')}\n截止日期: {deadline}\n[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            embed.add_field(name=name, value=value, inline=False)
        await ctx.reply(embed=embed)
        if len(upcoming_programs) > display_limit:
            embed = EmbedBuilder.info(
                title="项目过多",
                description=f"共找到 {len(upcoming_programs)} 个即将截止的项目，仅显示前 {display_limit} 个。"
            )
            await ctx.reply(embed=embed)
    async def program_detail(self, ctx, name: str):
        source = self.default_source
        if source not in self.data_sources:
            embed = EmbedBuilder.error(
                title="数据源不存在",
                description=f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        matching_programs = []
        for program in self.data_sources[source]:
            if (
                name.lower() in program.get("name", "").lower()
                or name.lower() in program.get("institute", "").lower()
            ):
                matching_programs.append(program)
        if not matching_programs:
            embed = EmbedBuilder.warning(
                title="无匹配项目",
                description=f"没有找到包含关键词 '{name}' 的项目"
            )
            await ctx.reply(embed=embed)
            return
        if len(matching_programs) > 1:
            embed = EmbedBuilder.warning(
                title="多个匹配项目",
                description=f"找到 {len(matching_programs)} 个匹配项目，请提供更具体的关键词:"
            )
            for i, program in enumerate(matching_programs[:10], 1):
                embed.add_field(
                    name=f"{i}. {program['name']} - {program['institute']}",
                    value=program.get("description", "无描述"),
                    inline=False
                )
            if len(matching_programs) > 10:
                embed.set_footer(text=f"... 等 {len(matching_programs)} 个项目")
            await ctx.reply(embed=embed)
            return
        program = matching_programs[0]
        deadline_display = self.format_time_remaining(program.get("deadline", ""))
        tags_display = "、".join(program.get("tags", []))
        embed = EmbedBuilder.success(
            title=f"{program.get('name', '')} - {program.get('institute', '')}",
            description=program.get('description', ''),
        )
        embed.add_field(name="截止日期", value=f"{program.get('deadline', '')} ({deadline_display})", inline=False)
        embed.add_field(name="官方网站", value=program.get('website', '无'), inline=False)
        if tags_display:
            embed.add_field(name="标签", value=tags_display, inline=False)
        await ctx.reply(embed=embed)
    async def list_tags(self, ctx):
        source = self.default_source
        if source not in self.data_sources:
            embed = EmbedBuilder.error(
                title="数据源不存在",
                description=f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        all_tags = set()
        for program in self.data_sources[source]:
            if "tags" in program:
                all_tags.update(program["tags"])
        if not all_tags:
            embed = EmbedBuilder.warning(
                title="无标签",
                description=f"数据源 '{source}' 中没有定义标签"
            )
            await ctx.reply(embed=embed)
            return
        embed = EmbedBuilder.create(EmbedData(
            title=f"数据源 '{source}' 中的所有标签",
            description="使用这些标签可以筛选保研项目",
            color=EmbedBuilder.THEME.info
        ))
        tag_list = sorted(all_tags)
        groups = [tag_list[i:i+20] for i in range(0, len(tag_list), 20)]
        for i, group in enumerate(groups, 1):
            embed.add_field(name=f"标签组 {i}", value=", ".join(group), inline=False)
        await ctx.reply(embed=embed)
    async def list_sources(self, ctx):
        if not self.data_sources:
            embed = EmbedBuilder.warning(
                title="无数据源",
                description="当前没有可用的数据源"
            )
            await ctx.reply(embed=embed)
            return
        embed = EmbedBuilder.create(EmbedData(
            title="可用的数据源",
            description=f"当前默认数据源: {self.default_source}",
            color=EmbedBuilder.THEME.success
        ))
        for source, programs in self.data_sources.items():
            embed.add_field(
                name=source, 
                value=f"包含 {len(programs)} 个项目", 
                inline=True
            )
        await ctx.reply(embed=embed)
    async def manual_update(self, ctx):
        embed = EmbedBuilder.info(
            title="数据更新中",
            description="正在更新保研信息数据，请稍候..."
        )
        await ctx.reply(embed=embed)
        success = await self.update_data_from_remote()
        if success:
            embed = EmbedBuilder.success(
                title="更新成功",
                description="保研信息数据更新成功！"
            )
        else:
            embed = EmbedBuilder.error(
                title="更新失败",
                description="保研信息数据更新失败，请稍后再试或检查网络连接。"
            )
        await ctx.reply(embed=embed)

    async def show_project_list(self, ctx, projects, title, description=None):
        """显示项目列表"""
        embed = EmbedBuilder.create(EmbedData(
            title=title,
            description=description or "以下是符合条件的项目：",
            color=EmbedBuilder.THEME.info
        ))
        
        # 添加项目信息
        for project in projects:
            field_name = f"{project['school']} - {project['college']}"
            field_value = f"专业：{project['major']}\n"
            
            if project.get('direction'):
                field_value += f"方向：{project['direction']}\n"
                
            if project.get('quota'):
                field_value += f"名额：{project['quota']}\n"
                
            if project.get('requirements'):
                field_value += f"要求：{project['requirements']}\n"
                
            if project.get('deadline'):
                field_value += f"截止：{project['deadline']}\n"
                
            if project.get('url'):
                field_value += f"[详情链接]({project['url']})"
                
            embed.add_field(
                name=field_name,
                value=field_value,
                inline=False
            )
            
        await ctx.reply(embed=embed)

    async def show_school_list(self, ctx, schools):
        """显示学校列表"""
        embed = EmbedBuilder.create(EmbedData(
            title="学校列表",
            description="以下是所有收录的学校：",
            color=EmbedBuilder.THEME.info
        ))
        
        # 将学校按每行5个分组显示
        school_groups = [schools[i:i+5] for i in range(0, len(schools), 5)]
        for group in school_groups:
            embed.add_field(
                name="\u200b",  # 空字符
                value=" | ".join(group),
                inline=False
            )
            
        await ctx.reply(embed=embed)

    async def show_college_list(self, ctx, school, colleges):
        """显示学院列表"""
        embed = EmbedBuilder.create(EmbedData(
            title=f"{school} - 学院列表",
            description="以下是该学校收录的学院：",
            color=EmbedBuilder.THEME.info
        ))
        
        # 将学院按每行3个分组显示
        college_groups = [colleges[i:i+3] for i in range(0, len(colleges), 3)]
        for group in college_groups:
            embed.add_field(
                name="\u200b",  # 空字符
                value=" | ".join(group),
                inline=False
            )
            
        await ctx.reply(embed=embed)

    async def show_major_list(self, ctx, school, college, majors):
        """显示专业列表"""
        embed = EmbedBuilder.create(EmbedData(
            title=f"{school} - {college} - 专业列表",
            description="以下是该学院收录的专业：",
            color=EmbedBuilder.THEME.info
        ))
        
        # 将专业按每行2个分组显示
        major_groups = [majors[i:i+2] for i in range(0, len(majors), 2)]
        for group in major_groups:
            embed.add_field(
                name="\u200b",  # 空字符
                value=" | ".join(group),
                inline=False
            )
            
        await ctx.reply(embed=embed)

    async def show_error(self, ctx, message):
        """显示错误信息"""
        embed = EmbedBuilder.create(EmbedData(
            title="❌ 错误",
            description=message,
            color=EmbedBuilder.THEME.error
        ))
        await ctx.reply(embed=embed)

async def setup(bot):
    """初始化函数"""
    ensure_data_dir()
    await bot.add_cog(BaoyanPlugin(bot))