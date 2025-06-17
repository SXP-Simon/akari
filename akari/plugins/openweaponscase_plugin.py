import random
import json
import os
import time
import discord
from discord.ext import commands
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

# 数据存储目录
PLUGIN_DIR = os.path.join('data', 'openweaponscase')
CASES_FILE = os.path.join(PLUGIN_DIR, 'cases.json')
HISTORY_FILE = os.path.join(PLUGIN_DIR, 'open_history.json')

# 修改后的磨损等级配置（名称, 概率, 最小磨损值, 最大磨损值）
WEAR_LEVELS = [
    ("崭新出厂", 0.03, 0.00, 0.07),    # 3% 概率
    ("略有磨损", 0.24, 0.07, 0.15),   # 24% 概率
    ("久经沙场", 0.33, 0.15, 0.45),   # 33% 概率
    ("破损不堪", 0.24, 0.30, 0.45),   # 24% 概率
    ("战痕累累", 0.16, 0.45, 1.00)    # 16% 概率
]

DOPPLER_WEAR_LEVELS = [
    ("崭新出厂", 0.03, 0.00, 0.87),    # 3% 概率
    ("略有磨损", 0.24, 0.07, 0.12),   # 24% 概率
]

QUALITY_PROBABILITY = {
    "军规级": 0.7992,  # 军规级
    "受限": 0.1598,   # 受限级
    "保密": 0.032,    # 保密级
    "隐秘": 0.0064,   # 隐秘级
    "非凡": 0.0026    # 金
}

# 不同品质对应的Discord颜色和图标
QUALITY_COLORS = {
    "军规级": 0x4b69ff,  # 蓝色
    "受限": 0x8847ff,    # 紫色
    "保密": 0xd32ce6,    # 粉色
    "隐秘": 0xeb4b4b,    # 红色
    "非凡": 0xffd700     # 金色
}

QUALITY_ICONS = {
    "军规级": "🔹",
    "受限": "🔮",
    "保密": "💠",
    "隐秘": "💎",
    "非凡": "⚜️"
}

def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(PLUGIN_DIR, exist_ok=True)

# =====================
# akari.plugins.openweaponscase_plugin
# =====================

"""
CSGOWeaponCasePlugin: CS:GO 武器箱开箱插件

- 支持武器箱模拟开箱、概率分布、库存管理
- Discord 命令集成
- 数据持久化与历史记录

Attributes:
    bot (commands.Bot): 关联的 Bot 实例
    ...
"""

class CSGOWeaponCasePlugin(commands.Cog):
    """CS:GO武器箱开箱插件"""
    
    def __init__(self, bot):
        self.bot = bot
        self.case_data = self._load_cases()
        self.open_history = self._load_history()
        self.max_display_count = 10  # 超过此数量时使用统计模式显示
    
    @commands.hybrid_group(name="开箱", description="CS:GO武器箱开箱模拟器", invoke_without_command=True)
    async def cscase(self, ctx):
        """CS:GO武器箱开箱命令"""
        commands_dict = {
            "list": "查看可用武器箱列表",
            "open [箱子名称] [数量]": "开启武器箱",
            "inventory": "查看物品库存",
            "purge": "清空库存数据"
        }
        
        embed = EmbedBuilder.create(EmbedData(
            title="🔫 CS:GO开箱系统",
            description="欢迎使用CS:GO武器箱开箱模拟器！",
            color=EmbedBuilder.THEME.special
        ))
        
        # 添加命令说明
        for cmd, desc in commands_dict.items():
            embed.add_field(
                name=f"!开箱 {cmd}",
                value=desc,
                inline=True
            )
            
        embed.set_footer(text="祝您开出稀有物品!")
        await ctx.reply(embed=embed)

    @cscase.command(name="list", aliases=["列表", "菜单"])
    async def cscase_list(self, ctx):
        """列出所有可用的武器箱"""
        await self.show_menu(ctx)

    @cscase.command(name="open", aliases=["开启"])
    async def cscase_open(self, ctx, *, args=None):
        """开启武器箱
        
        参数:
            args: 箱子名称 [次数]，例如：命运武器箱 10
        """
        if not args:
            await ctx.reply("❌ 请输入武器箱名称，例如：`!开箱 open 命运武器箱 1`")
            return
        
        await self.handle_open(ctx, args)

    @cscase.command(name="inventory", aliases=["库存"])
    async def cscase_inventory(self, ctx):
        """查看当前库存"""
        await self.show_inventory(ctx)

    @cscase.command(name="purge", aliases=["清空", "清除"])
    async def cscase_purge(self, ctx):
        """清空库存数据"""
        await self.handle_purge(ctx)
        
    @commands.command(name="开启武器箱", hidden=True)
    async def direct_open(self, ctx, *, args=None):
        """直接开箱命令"""
        if not args:
            await ctx.reply("❌ 请输入武器箱名称，例如：`!开启武器箱 命运武器箱 1`")
            return
        
        await self.handle_open(ctx, args)
    
    @commands.command(name="武器箱菜单", hidden=True)
    async def direct_menu(self, ctx):
        """查看武器箱菜单"""
        await self.show_menu(ctx)
        
    @commands.command(name="武器库存", hidden=True)
    async def direct_inventory(self, ctx):
        """查看当前库存"""
        await self.show_inventory(ctx)
        
    @commands.command(name="清空库存", hidden=True)
    async def direct_purge(self, ctx):
        """清空库存数据"""
        await self.handle_purge(ctx)

    def _load_cases(self):
        """加载并处理武器箱数据"""
        try:
            if not os.path.exists(CASES_FILE):
                print(f"[开箱插件] 找不到武器箱数据文件: {CASES_FILE}")
                return {}
            
            with open(CASES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._process_cases(data)
                print(f"[开箱插件] 已加载 {len(data)} 个武器箱数据")
                return data
        except Exception as e:
            print(f"[开箱插件] 数据加载失败: {str(e)}")
            return {}
    
    def _process_cases(self, data):
        """处理每个武器箱的概率分配"""
        for case_name, items in data.items():
            quality_counts = {}
            # 统计各品质物品数量
            for item in items:
                quality = item["rln"]
                quality_counts[quality] = quality_counts.get(quality, 0) + 1
            
            # 分配概率并添加probability字段
            for item in items:
                quality = item["rln"]
                total_prob = QUALITY_PROBABILITY.get(quality, 0)
                count = quality_counts.get(quality, 1)
                item["probability"] = total_prob / count
    
    def _load_history(self):
        """加载开箱历史记录"""
        if not os.path.exists(HISTORY_FILE):
            return {}
        
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                print(f"[开箱插件] 已加载 {len(history)} 条用户历史记录")
                return history
        except Exception as e:
            print(f"[开箱插件] 加载历史记录失败: {str(e)}")
            return {}
    
    def _save_history(self):
        """保存开箱记录"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.open_history, f, indent=2, ensure_ascii=False)
            print("[开箱插件] 已保存历史记录")
        except Exception as e:
            print(f"[开箱插件] 保存历史记录失败: {str(e)}")
    
    def _generate_item(self, case_name):
        """生成带磨损值的物品"""
        items = self.case_data[case_name]
        rand = random.random()
        cumulative = 0.0
        
        # 先选择物品品质
        for item in items:
            cumulative += item["probability"]
            if rand <= cumulative:
                # ===== 新增StatTrak判断 =====
                is_stattrak = False
                item_name = item["short_name"]
                # 排除手套类物品的StatTrak判断
                if "手套" not in item_name:
                    # 10%概率生成StatTrak
                    is_stattrak = random.random() < 0.1
                    # 处理物品名称
                    if is_stattrak:
                        item_name = f"StatTrak™ | {item_name}"
                
                # 根据概率分布选择磨损等级
                is_doppler = "多普勒" in item_name
                wear_config = DOPPLER_WEAR_LEVELS if is_doppler else WEAR_LEVELS                           
                
                # 根据配置选择磨损等级
                chosen_level = random.choices(
                    wear_config,
                    weights=[wl[1] for wl in wear_config],
                    k=1
                )[0]                
                
                # 在选定等级范围内生成磨损值
                wear_min = chosen_level[2]
                wear_max = chosen_level[3]
                wear = round(random.uniform(wear_min, wear_max), 8)
                
                return {
                    "name": item_name,
                    "quality": item["rln"],
                    "wear_value": wear,
                    "wear_level": chosen_level[0],
                    "template_id": random.randint(0, 999),
                    "img": item.get("img", "")
                }
        
        # 兜底逻辑（理论上不会执行到这里）
        last_item = items[-1]
        wear = round(random.uniform(0, 1), 8)
        return {
            "name": last_item["short_name"],
            "quality": last_item["rln"],
            "wear_value": wear,
            "wear_level": "战痕累累",
            "img": last_item.get("img", "")
        }
    
    def _record_history(self, user_id, item):
        """记录历史数据"""
        history_key = str(user_id)
        self.open_history.setdefault(history_key, {
            "total": 0,
            "red_count": 0,       # 隐秘物品总数
            "gold_count": 0,      # 非凡物品总数
            "other_stats": {      # 其他品质统计
                "军规级": 0,
                "受限": 0,
                "保密": 0
            },
            "items": [],          # 仅存储红/金物品详情
            "last_open": None
        })
        
        record = self.open_history[history_key]
        record["total"] += 1
        
        # 分类存储逻辑
        quality = item["quality"]
        if quality == "隐秘":
            record["red_count"] += 1
            record["items"].append({
                "name": item["name"],
                "wear_value": item["wear_value"],
                "template_id": item["template_id"],
                "time": time.time()
            })
        elif quality == "非凡":
            record["gold_count"] += 1
            record["items"].append({
                "name": item["name"],
                "wear_value": item["wear_value"],
                "template_id": item["template_id"],
                "time": time.time()
            })
        else:
            if quality in record["other_stats"]:
                record["other_stats"][quality] += 1
        
        record["last_open"] = time.time()
        self._save_history()

    def _parse_command(self, msg: str) -> tuple:
        """解析开箱指令格式"""
        parts = msg.strip().split()
        
        # 如果只有一个部分，默认开1箱
        if len(parts) == 1:
            return parts[0], 1
        
        # 尝试解析最后一部分为数字
        try:
            count = int(parts[-1])
            case_name = " ".join(parts[:-1])
            return case_name, min(count, 100)  # 限制最大开箱数
        except ValueError:
            # 如果最后一部分不是数字，尝试检查名称末尾的数字
            case_name = " ".join(parts)
            count_str = ""
            index = len(case_name) - 1
            
            while index >= 0 and case_name[index].isdigit():
                count_str = case_name[index] + count_str
                index -= 1
            
            if count_str:
                return case_name[:index+1].strip(), min(int(count_str), 100)
            else:
                return case_name, 1

    async def handle_open(self, ctx, args):
        """处理开箱请求"""
        case_name, count = self._parse_command(args)
        
        if not case_name:
            await ctx.reply("❌ 请输入武器箱名称")
            return
        
        if case_name not in self.case_data:
            await ctx.reply(f"❌ 未找到【{case_name}】武器箱")
            return
        
        user_id = str(ctx.author.id)
        nickname = ctx.author.display_name
        
        items_generated = []
        quality_stats = {"军规级": 0, "受限": 0, "保密": 0, "隐秘": 0, "非凡": 0}
        
        # 生成物品并记录
        for _ in range(count):
            item = self._generate_item(case_name)
            items_generated.append(item)
            self._record_history(user_id, item)
            quality = item["quality"]
            quality_stats[quality] += 1
        
        # 挑选稀有物品
        rare_items = [item for item in items_generated if item["quality"] in ["隐秘", "非凡"]]
        
        # 准备显示信息
        if count <= self.max_display_count:
            # 显示所有物品
            await self._display_all_items(ctx, case_name, count, nickname, items_generated)
        else:
            # 显示统计信息
            await self._display_summary(ctx, case_name, count, nickname, quality_stats, rare_items)

    async def _display_all_items(self, ctx, case_name, count, nickname, items):
        """显示所有物品详情"""
        embed = EmbedBuilder.create(EmbedData(
            title=f"⚡ 开箱结果",
            description=f"{nickname} 开启了 {count} 个【{case_name}】",
            color=EmbedBuilder.THEME.special
        ))
        
        # 设置用户头像
        embed.set_author(
            name=f"{nickname}的开箱",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        # 添加物品字段
        for i, item in enumerate(items, 1):
            quality = item["quality"]
            color = QUALITY_COLORS.get(quality, 0x808080)
            icon = QUALITY_ICONS.get(quality, "🔶")
            
            field_title = f"{i}. {icon} {item['name']}"
            field_value = (
                f"**品质**: {quality}\n"
                f"**磨损**: {item['wear_level']} ({item['wear_value']:.8f})\n"
                f"**编号**: #{item['template_id']}"
            )
            embed.add_field(name=field_title, value=field_value, inline=False)
            
            # 只显示第一个物品的图片
            if i == 1 and item.get("img"):
                embed.set_thumbnail(url=item["img"])
        
        # 添加库存信息
        history_key = str(ctx.author.id)
        total_items = self.open_history[history_key]['total']
        embed.set_footer(text=f"📦 当前库存：{total_items}件 | 使用 !开箱 inventory 查看库存")
        
        await ctx.reply(embed=embed)

    async def _display_summary(self, ctx, case_name, count, nickname, quality_stats, rare_items):
        """显示开箱统计摘要"""
        embed = EmbedBuilder.create(EmbedData(
            title=f"⚡ 开箱统计",
            description=f"{nickname} 开启了 {count} 个【{case_name}】",
            color=EmbedBuilder.THEME.special
        ))
        
        # 设置用户头像
        embed.set_author(
            name=f"{nickname}的开箱",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        # 显示统计信息
        stats_text = ""
        for quality in ["军规级", "受限", "保密", "隐秘", "非凡"]:
            if quality_stats[quality] > 0:
                icon = QUALITY_ICONS.get(quality, "🔶")
                percent = (quality_stats[quality] / count) * 100
                stats_text += f"{icon} **{quality}**: {quality_stats[quality]}件 ({percent:.1f}%)\n"
        
        embed.add_field(name="📊 物品统计", value=stats_text, inline=False)
        
        # 显示珍稀物品
        if rare_items:
            rare_items_text = ""
            for i, item in enumerate(rare_items[:10], 1):
                icon = QUALITY_ICONS.get(item["quality"], "🔶")
                rare_items_text += f"{i}. {icon} **{item['name']}** | {item['wear_level']} ({item['wear_value']:.8f})\n"
            
            if len(rare_items) > 10:
                rare_items_text += f"...等共 {len(rare_items)} 件稀有物品"
            
            embed.add_field(name="💎 稀有物品清单", value=rare_items_text, inline=False)
        
            # 使用第一个稀有物品的图片
            if rare_items[0].get("img"):
                embed.set_thumbnail(url=rare_items[0]["img"])
        
        # 添加库存信息
        history_key = str(ctx.author.id)
        total_items = self.open_history[history_key]['total']
        embed.set_footer(text=f"📦 当前库存：{total_items}件 | 使用 !开箱 inventory 查看库存")
        
        await ctx.reply(embed=embed)

    async def show_inventory(self, ctx):
        """显示用户库存"""
        user_id = str(ctx.author.id)
        inventory = self.open_history.get(user_id, {})
        
        if not inventory.get("total"):
            embed = EmbedBuilder.create(EmbedData(
                title="库存为空",
                description="你的库存中还没有任何物品",
                color=EmbedBuilder.THEME.warning
            ))
            await ctx.reply(embed=embed)
            return
        
        embed = EmbedBuilder.create(EmbedData(
            title=f"🧰 武器库存",
            description=f"{ctx.author.display_name} 的收藏品",
            color=EmbedBuilder.THEME.info
        ))
        
        # 添加用户头像
        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        )
        
        # 添加统计信息
        embed.add_field(
            name="📦 总库存", 
            value=f"{inventory['total']}件物品", 
            inline=False
        )
        
        # 普通物品统计
        normal_stats = ""
        for k, v in inventory['other_stats'].items():
            icon = QUALITY_ICONS.get(k, "🔶")
            if v > 0:
                normal_stats += f"{icon} {k}: {v}件\n"
        
        if normal_stats:
            embed.add_field(name="🔷 普通物品统计", value=normal_stats, inline=True)
        
        # 稀有物品统计
        rare_stats = ""
        if inventory["red_count"] > 0:
            rare_stats += f"{QUALITY_ICONS['隐秘']} 隐秘物品: {inventory['red_count']}件\n"
        if inventory["gold_count"] > 0:
            rare_stats += f"{QUALITY_ICONS['非凡']} 非凡物品: {inventory['gold_count']}件\n"
            
        if rare_stats:
            embed.add_field(name="💎 稀有物品统计", value=rare_stats, inline=True)
        
        # 隐秘物品展示
        if inventory["red_count"] > 0 or inventory["gold_count"] > 0:
            # 排序展示最近获得的稀有物品
            rare_items = sorted(
                inventory["items"], 
                key=lambda x: x.get("time", 0), 
                reverse=True
            )[:15]  # 最多显示15个
            
            rare_text = ""
            for i, item in enumerate(rare_items, 1):
                rare_text += f"{i}. **{item['name']}** | 磨损: {item['wear_value']:.8f}\n"
            
            total_rare = inventory["red_count"] + inventory["gold_count"]
            if len(rare_items) < total_rare:
                rare_text += f"...等共 {total_rare} 件稀有物品"
                
            embed.add_field(name="🏆 稀有物品详情", value=rare_text, inline=False)
        
        # 最后开箱时间
        if inventory.get("last_open"):
            last_open_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(inventory["last_open"]))
            embed.set_footer(text=f"⏰ 最后开箱时间：{last_open_time}")
        
        await ctx.reply(embed=embed)

    async def handle_purge(self, ctx):
        """处理清除库存"""
        user_id = str(ctx.author.id)
        if user_id in self.open_history:
            del self.open_history[user_id]
            self._save_history()
            embed = EmbedBuilder.create(EmbedData(
                title="库存已清空",
                description="您的所有物品已被清除",
                color=EmbedBuilder.THEME.success
            ))
            await ctx.reply(embed=embed)
        else:
            embed = EmbedBuilder.create(EmbedData(
                title="无库存",
                description="没有找到可清除的库存数据",
                color=EmbedBuilder.THEME.warning
            ))
            await ctx.reply(embed=embed)

    async def show_menu(self, ctx):
        """显示帮助菜单"""
        embed = EmbedBuilder.create(EmbedData(
            title="🔫 CS:GO开箱系统",
            description=(
                "欢迎使用CS:GO武器箱模拟器！以下是可用的命令和武器箱列表\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬▬"
            ),
            color=EmbedBuilder.THEME.warning
        ))
        
        # 添加使用方法字段
        usage_text = (
            "**单次开箱**：`!开箱 open [武器箱名称]`\n"
            "例如：`!开箱 open 命运武器箱`\n\n"
            "**批量开箱**：`!开箱 open [武器箱名称] [次数]`\n"
            "例如：`!开箱 open 命运武器箱 10`\n\n"
            "**查看库存**：`!开箱 inventory`\n"
            "**清空库存**：`!开箱 purge`"
        )
        embed.add_field(name="📖 使用方法", value=usage_text, inline=False)
        
        # 将武器箱列表分组显示
        case_names = list(self.case_data.keys())
        fields_needed = (len(case_names) + 14) // 15  # 每个字段最多显示15个箱子
        
        for i in range(fields_needed):
            start_idx = i * 15
            end_idx = min(start_idx + 15, len(case_names))
            field_cases = case_names[start_idx:end_idx]
            
            field_content = "\n".join([f"▫ {name}" for name in field_cases])
            field_name = f"📦 武器箱列表 ({start_idx+1}-{end_idx})"
            
            embed.add_field(name=field_name, value=field_content, inline=True)
        
        # 添加页脚
        embed.set_footer(text="祝您开出稀有物品！")
        
        await ctx.reply(embed=embed)

async def setup(bot):
    """插件加载入口"""
    ensure_data_dir()
    await bot.add_cog(CSGOWeaponCasePlugin(bot))