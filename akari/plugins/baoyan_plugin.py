import json
import os
import time
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set
import discord
from discord.ext import commands, tasks
from akari.bot.commands import command, group

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
    
    @bot.register_command
    @group(name="baoyan", description="计算机保研信息查询")
    async def baoyan(ctx):
        if ctx.invoked_subcommand is None:
            commands_list = [
                "list - 列出保研项目",
                "search - 搜索保研项目",
                "upcoming - 查看即将截止的项目",
                "detail - 查看项目详情",
                "tags - 查看所有可用标签",
                "sources - 查看所有数据源",
                "update - 更新保研数据"
            ]
            await ctx.reply(f"计算机保研信息查询命令，使用方式:\n" + "\n".join([f"!baoyan {cmd}" for cmd in commands_list]))
    
    @baoyan.command(name="list", description="列出保研项目")
    async def list_programs(ctx, tag: str = None):
        """列出保研项目
        
        参数:
            tag: 筛选标签，可选，多个标签用逗号分隔
        """
        await plugin.list_programs(ctx, tag)
    
    @baoyan.command(name="search", description="搜索保研项目")
    async def search_programs(ctx, *, keyword: str):
        """搜索项目
        
        参数:
            keyword: 搜索关键词
        """
        await plugin.search_programs(ctx, keyword)
    
    @baoyan.command(name="upcoming", description="查看即将截止的项目")
    async def list_upcoming(ctx, tag: str = None):
        """列出30天内即将截止的项目
        
        参数:
            tag: 筛选标签，可选，多个标签用逗号分隔
        """
        await plugin.list_upcoming(ctx, tag)
    
    @baoyan.command(name="detail", description="查看项目详情")
    async def program_detail(ctx, *, name: str):
        """查看项目详细信息
        
        参数:
            name: 项目名称或学校名称关键词
        """
        await plugin.program_detail(ctx, name)
    
    @baoyan.command(name="tags", description="查看所有可用标签")
    async def list_tags(ctx):
        """列出数据源中的所有标签"""
        await plugin.list_tags(ctx)
    
    @baoyan.command(name="sources", description="查看所有数据源")
    async def list_sources(ctx):
        """列出所有可用的数据源"""
        await plugin.list_sources(ctx)
    
    @baoyan.command(name="update", description="更新保研数据")
    @commands.has_permissions(administrator=True)
    async def manual_update(ctx):
        """手动更新数据源（需要管理员权限）"""
        await plugin.manual_update(ctx)

    # 启动更新任务
    plugin.start_tasks()
    
    # 确保插件被卸载时停止任务
    bot.add_listener(plugin.on_unload, "on_unload")

class BaoyanPlugin:
    """计算机保研信息插件"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # 数据源和配置
        self.data_sources = {}
        self.default_source = None
        self.last_update_time = 0
        
        # 已知项目ID集合，用于检测新增项目
        self.known_programs = set()
        self.known_programs_file = os.path.join(DATA_DIR, "known_programs.json")
        
        # 初始加载数据
        self.load_data_sources()
        self.load_known_programs()
        
        # 更新和通知任务
        self.update_task = None
        self.notification_task = None
    
    def start_tasks(self):
        """启动后台任务"""
        self.auto_update_data.start()
        self.check_notifications.start()
    
    async def on_unload(self):
        """插件卸载时清理资源"""
        if self.update_task and not self.update_task.is_being_cancelled():
            self.update_task.cancel()
        if self.notification_task and not self.notification_task.is_being_cancelled():
            self.notification_task.cancel()
        self.save_known_programs()
    
    @tasks.loop(minutes=UPDATE_INTERVAL)
    async def auto_update_data(self):
        """自动更新数据的后台任务"""
        try:
            print(f"[保研插件] 正在自动更新保研信息数据...")
            await self.update_data_from_remote()
        except Exception as e:
            print(f"[保研插件] 自动更新保研信息数据出错: {e}")
    
    @tasks.loop(seconds=NOTIFICATION_INTERVAL)
    async def check_notifications(self):
        """定期检查并发送通知的后台任务"""
        try:
            print("[保研插件] 开始检查新增保研信息...")
            # 获取所有数据源的项目
            all_programs = []
            for source, programs in self.data_sources.items():
                all_programs.extend(programs)
            
            # 检查新增的项目
            await self.check_new_programs(all_programs)
            print("[保研插件] 保研信息检查完成")
        except Exception as e:
            print(f"[保研插件] 通知检查任务出错: {e}")
    
    async def check_new_programs(self, programs):
        """检查新增项目并发送通知到通知频道"""
        # 只在有新项目时发送通知
        new_programs = []
        
        # 生成当前所有项目的ID集合
        current_program_ids = set()
        
        for program in programs:
            # 生成唯一项目ID
            program_id = self.generate_program_id(program)
            current_program_ids.add(program_id)
            
            # 检查是否是新项目
            if program_id not in self.known_programs:
                new_programs.append(program)
        
        # 更新已知项目列表并保存
        self.known_programs = current_program_ids
        self.save_known_programs()
        
        # 如果有新项目，发送通知
        if new_programs:
            # 获取通知频道
            notification_channel_id = self.get_notification_channel_id()
            if notification_channel_id:
                channel = self.bot.get_channel(notification_channel_id)
                if channel:
                    message = "📢 **有新增的保研项目！**\n\n"
                    
                    for i, program in enumerate(new_programs[:MAX_DISPLAY_ITEMS], 1):
                        message += f"{i}. **{program.get('name', '')} - {program.get('institute', '')}**\n"
                        message += f"描述: {program.get('description', '')}\n"
                        message += f"截止日期: {self.format_time_remaining(program.get('deadline', ''))}\n"
                        message += f"[官方网站]({program.get('website', '')})\n\n"
                    
                    if len(new_programs) > MAX_DISPLAY_ITEMS:
                        message += f"\n...等共 {len(new_programs)} 个新项目。请使用 `!baoyan list` 查看更多。"
                    
                    try:
                        await channel.send(message)
                    except Exception as e:
                        print(f"[保研插件] 发送新项目通知失败: {e}")
    
    def get_notification_channel_id(self):
        """获取通知频道ID，可以从配置文件加载"""
        # 这里可以从配置文件加载，暂时返回None
        # 如果没有配置通知频道，就不发送通知
        return None
    
    def generate_program_id(self, program):
        """生成项目的唯一ID"""
        # 使用名称、机构和描述的组合作为唯一标识
        return f"{program.get('name', '')}:{program.get('institute', '')}:{program.get('description', '')}"
    
    def load_known_programs(self):
        """从文件加载已知项目ID"""
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
        """保存已知项目ID到文件"""
        try:
            with open(self.known_programs_file, "w", encoding="utf-8") as f:
                json.dump(list(self.known_programs), f, ensure_ascii=False, indent=4)
            print("[保研插件] 已知项目ID已保存")
        except Exception as e:
            print(f"[保研插件] 保存已知项目ID出错: {e}")
    
    def load_data_sources(self):
        """加载本地缓存的数据源"""
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
            # 首次加载，尝试从远程获取
            print("[保研插件] 本地缓存不存在，将尝试从远程获取数据")
            # 这里不要使用create_task，因为可能在初始化函数中还没有事件循环
    
    async def update_data_from_remote(self):
        """从远程更新数据"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(REMOTE_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 保存到本地缓存
                        data_file = os.path.join(DATA_DIR, "sources.json")
                        with open(data_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                        
                        # 更新内存中的数据
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
        """获取符合条件的保研项目"""
        source = self.default_source
        if source not in self.data_sources:
            return []
        
        programs = self.data_sources[source]
        result = []
        
        # 处理逗号分隔的多个标签
        tags = []
        tag = str(tag) if tag else None
        if tag:
            tags = [t.strip() for t in tag.split(",") if t.strip()]
        
        for program in programs:
            # 按标签筛选
            if tags:
                # 只要匹配其中一个标签即可
                if not any(t in program.get("tags", []) for t in tags):
                    continue
            
            result.append(program)
        
        return result
    
    def format_time_remaining(self, deadline_str: str) -> str:
        """格式化剩余时间"""
        if not deadline_str:
            return "未知"
        
        try:
            # 确保使用北京时间
            tz_bj = timezone(timedelta(hours=8))
            now = datetime.now(tz_bj)
            
            # 解析日期字符串并添加时区信息（如果没有）
            deadline = None
            if "Z" in deadline_str:
                # UTC时间
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            elif "+" in deadline_str or "-" in deadline_str and "T" in deadline_str:
                # 已经包含时区信息的ISO格式
                deadline = datetime.fromisoformat(deadline_str)
            else:
                # 没有时区信息，假设是北京时间
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
        """解析截止日期字符串为datetime对象"""
        try:
            tz_bj = timezone(timedelta(hours=8))
            
            if "Z" in deadline_str:
                # UTC时间
                return datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            elif "+" in deadline_str or "-" in deadline_str and "T" in deadline_str:
                # 已经包含时区信息的ISO格式
                return datetime.fromisoformat(deadline_str)
            else:
                # 没有时区信息，假设是北京时间
                deadline = datetime.fromisoformat(deadline_str)
                return deadline.replace(tzinfo=tz_bj)
        except:
            return None
    
    def get_program_timestamp(self, deadline_str: str) -> float:
        """获取项目截止日期的时间戳，用于排序"""
        if not deadline_str:
            return float("inf")  # 没有截止日期的放在最后
        
        try:
            # 解析日期字符串并添加时区信息（如果没有）
            deadline = self.parse_deadline(deadline_str)
            if deadline:
                return deadline.timestamp()
            return float("inf")
        except Exception as e:
            print(f"[保研插件] 获取时间戳出错: {e}")
            return float("inf")  # 出错的放在最后
    
    async def list_programs(self, ctx, tag: str = None):
        """列出保研项目"""
        source = self.default_source
        if source not in self.data_sources:
            await ctx.reply(f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源")
            return
        
        programs = self.get_programs(tag)
        
        if not programs:
            await ctx.reply("没有找到符合条件的保研项目")
            return
        
        # 使用嵌入消息格式输出，避免超过字符限制
        embed = discord.Embed(
            title="保研项目列表",
            description=f"数据源: {source}" + (f"\n标签筛选: {tag}" if tag else ""),
            color=0x3498db
        )
        
        # 显示数量限制
        display_limit = MAX_DISPLAY_ITEMS
        
        for i, program in enumerate(programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            
            value = f"描述: {program.get('description', '')}\n"
            value += f"截止日期: {deadline}\n"
            value += f"[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            
            embed.add_field(name=name, value=value, inline=False)
        
        await ctx.reply(embed=embed)
        
        if len(programs) > display_limit:
            await ctx.reply(f"共找到 {len(programs)} 个项目，仅显示前 {display_limit} 个。请使用更具体的标签筛选。")
    
    async def search_programs(self, ctx, keyword: str):
        """搜索项目（模糊搜索学校和机构名称）"""
        source = self.default_source
        if source not in self.data_sources:
            await ctx.reply(f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源")
            return
        
        if not keyword:
            await ctx.reply("请提供搜索关键词")
            return
        
        # 转换为小写以进行不区分大小写的搜索
        keyword = keyword.lower()
        matching_programs = []
        
        # 在学校名称、机构名称和描述中搜索关键词
        for program in self.data_sources[source]:
            if (
                keyword in program.get("name", "").lower()
                or keyword in program.get("institute", "").lower()
                or keyword in program.get("description", "").lower()
            ):
                matching_programs.append(program)
        
        if not matching_programs:
            await ctx.reply(f"没有找到包含关键词 '{keyword}' 的项目")
            return
        
        # 使用嵌入消息格式输出
        embed = discord.Embed(
            title=f"搜索结果: '{keyword}'",
            description=f"数据源: {source}\n找到 {len(matching_programs)} 个匹配项目",
            color=0x3498db
        )
        
        # 显示数量限制
        display_limit = MAX_DISPLAY_ITEMS
        
        for i, program in enumerate(matching_programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            
            value = f"描述: {program.get('description', '')}\n"
            value += f"截止日期: {deadline}\n"
            value += f"[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            
            embed.add_field(name=name, value=value, inline=False)
        
        await ctx.reply(embed=embed)
        
        if len(matching_programs) > display_limit:
            await ctx.reply(f"共找到 {len(matching_programs)} 个匹配项目，仅显示前 {display_limit} 个。请尝试使用更具体的关键词。")
    
    async def list_upcoming(self, ctx, tag: str = None):
        """列出30天内即将截止的项目"""
        source = self.default_source
        days = 30  # 固定为30天
        
        if source not in self.data_sources:
            await ctx.reply(f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源")
            return
        
        # 使用北京时间
        tz_bj = timezone(timedelta(hours=8))
        now = datetime.now(tz_bj)
        deadline_ts = now.timestamp() + days * 86400
        
        # 处理逗号分隔的多个标签
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
                
                # 解析日期
                deadline = self.parse_deadline(deadline_str)
                if not deadline:
                    continue
                
                # 如果指定了标签，进行筛选
                if tags:
                    # 只要匹配其中一个标签即可
                    if not any(t in program.get("tags", []) for t in tags):
                        continue
                
                # 检查是否在时间范围内
                program_deadline_ts = deadline.timestamp()
                if now.timestamp() <= program_deadline_ts <= deadline_ts:
                    upcoming_programs.append(program)
            except Exception as e:
                print(f"[保研插件] 处理截止日期时出错: {e}, deadline_str={program.get('deadline', '')}")
        
        # 按截止日期升序排序
        upcoming_programs.sort(key=lambda x: self.get_program_timestamp(x["deadline"]))
        
        if not upcoming_programs:
            await ctx.reply(f"未找到 {days} 天内即将截止的项目" + (f"（标签：{tag}）" if tag else ""))
            return
        
        # 使用嵌入消息格式输出
        embed = discord.Embed(
            title=f"{days}天内即将截止的项目",
            description=f"数据源: {source}" + (f"\n标签筛选: {tag}" if tag else ""),
            color=0xe74c3c  # 红色表示紧急
        )
        
        # 显示数量限制
        display_limit = MAX_DISPLAY_ITEMS
        
        for i, program in enumerate(upcoming_programs[:display_limit], 1):
            name = f"{i}. {program.get('name', '')} - {program.get('institute', '')}"
            deadline = self.format_time_remaining(program.get('deadline', ''))
            tags = "、".join(program.get('tags', []))
            
            value = f"描述: {program.get('description', '')}\n"
            value += f"截止日期: {deadline}\n"
            value += f"[官方网站]({program.get('website', '')})"
            if tags:
                value += f"\n标签: {tags}"
            
            embed.add_field(name=name, value=value, inline=False)
        
        await ctx.reply(embed=embed)
        
        if len(upcoming_programs) > display_limit:
            await ctx.reply(f"共找到 {len(upcoming_programs)} 个即将截止的项目，仅显示前 {display_limit} 个。")
    
    async def program_detail(self, ctx, name: str):
        """查看项目详细信息"""
        source = self.default_source
        if source not in self.data_sources:
            await ctx.reply(f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源")
            return
        
        matching_programs = []
        for program in self.data_sources[source]:
            if (
                name.lower() in program.get("name", "").lower()
                or name.lower() in program.get("institute", "").lower()
            ):
                matching_programs.append(program)
        
        if not matching_programs:
            await ctx.reply(f"没有找到包含关键词 '{name}' 的项目")
            return
        
        if len(matching_programs) > 1:
            embed = discord.Embed(
                title="多个匹配项目",
                description=f"找到 {len(matching_programs)} 个匹配项目，请提供更具体的关键词:",
                color=0xf39c12
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
        
        # 只有一个匹配项目，显示详细信息
        program = matching_programs[0]
        deadline_display = self.format_time_remaining(program.get("deadline", ""))
        tags_display = "、".join(program.get("tags", []))
        
        embed = discord.Embed(
            title=f"{program.get('name', '')} - {program.get('institute', '')}",
            description=program.get('description', ''),
            color=0x2ecc71,
            url=program.get('website', '')
        )
        
        embed.add_field(name="截止日期", value=f"{program.get('deadline', '')} ({deadline_display})", inline=False)
        embed.add_field(name="官方网站", value=program.get('website', '无'), inline=False)
        if tags_display:
            embed.add_field(name="标签", value=tags_display, inline=False)
        
        await ctx.reply(embed=embed)
    
    async def list_tags(self, ctx):
        """列出数据源中的所有标签"""
        source = self.default_source
        if source not in self.data_sources:
            await ctx.reply(f"当前数据源 '{source}' 不存在，请使用 !baoyan sources 查看可用的数据源")
            return
        
        all_tags = set()
        for program in self.data_sources[source]:
            if "tags" in program:
                all_tags.update(program["tags"])
        
        if not all_tags:
            await ctx.reply(f"数据源 '{source}' 中没有定义标签")
            return
        
        embed = discord.Embed(
            title=f"数据源 '{source}' 中的所有标签",
            description="使用这些标签可以筛选保研项目",
            color=0x9b59b6
        )
        
        # 将标签分组显示，每组最多20个
        tag_list = sorted(all_tags)
        groups = [tag_list[i:i+20] for i in range(0, len(tag_list), 20)]
        
        for i, group in enumerate(groups, 1):
            embed.add_field(name=f"标签组 {i}", value=", ".join(group), inline=False)
        
        await ctx.reply(embed=embed)
    
    async def list_sources(self, ctx):
        """列出所有可用的数据源"""
        if not self.data_sources:
            await ctx.reply("当前没有可用的数据源")
            return
        
        embed = discord.Embed(
            title="可用的数据源",
            description=f"当前默认数据源: {self.default_source}",
            color=0x1abc9c
        )
        
        for source, programs in self.data_sources.items():
            embed.add_field(
                name=source, 
                value=f"包含 {len(programs)} 个项目", 
                inline=True
            )
        
        await ctx.reply(embed=embed)
    
    async def manual_update(self, ctx):
        """手动更新数据源"""
        await ctx.reply("正在更新保研信息数据，请稍候...")
        success = await self.update_data_from_remote()
        
        if success:
            await ctx.reply("保研信息数据更新成功！")
        else:
            await ctx.reply("保研信息数据更新失败，请稍后再试或检查网络连接。") 