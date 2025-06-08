import io
import re
import asyncio
import aiohttp
from discord import File, Attachment, Member, Message, User
from discord.ext import commands
from meme_generator import get_meme, get_meme_keys, get_memes
from meme_generator.exception import MemeGeneratorException, NoSuchMeme
from meme_generator.utils import render_meme_list
from akari.bot.utils import EmbedBuilder
import imghdr  # 添加imghdr模块用于检测图片格式
import os

# 可选：禁用/启用/黑名单功能
MEME_DISABLED_LIST = set()

# 获取用户头像（discord.py）
async def get_avatar(member: Member | User) -> bytes | None:
    if member.avatar:
        avatar_url = member.avatar.url
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    return await resp.read()
        except Exception:
            return None
    return None

async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.read()
    except Exception:
        return None

def parse_key_value_args(args):
    options = {}
    texts = []
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            options[k] = v
        else:
            texts.append(arg)
    return texts, options

def detect_image_format(img_bytes: io.BytesIO) -> str:
    """检测图片格式并返回对应的文件扩展名"""
    # 保存当前位置
    current_pos = img_bytes.tell()
    # 将指针移到开头
    img_bytes.seek(0)
    # 读取前几个字节来检测格式
    header = img_bytes.read(8)
    # 恢复指针位置
    img_bytes.seek(current_pos)
    
    # GIF格式检测
    if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
        return 'gif'
    # PNG格式检测
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    # JPEG格式检测
    elif header.startswith(b'\xff\xd8'):
        return 'jpg'
    # 默认返回png
    return 'png'

def find_template_by_name_or_keyword(template_name: str) -> str:
    """通过模板名或关键词查找模板"""
    try:
        # 先尝试直接获取模板
        meme = get_meme(template_name)
        return meme.key
    except NoSuchMeme:
        # 如果直接获取失败，遍历所有模板检查关键词
        for key in get_meme_keys():
            meme = get_meme(key)
            if meme.keywords:
                # 处理keywords可能是字符串或列表的情况
                if isinstance(meme.keywords, str):
                    keywords = meme.keywords.split(',')
                elif isinstance(meme.keywords, (list, tuple)):
                    keywords = meme.keywords
                else:
                    continue
                    
                # 检查模板名是否在关键词中
                if template_name in keywords or any(k.strip() == template_name for k in keywords):
                    return key
        # 如果都没找到，抛出异常
        raise NoSuchMeme(template_name)

class MemePlugin(commands.Cog):
    """表情包生成器插件"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="meme", description="表情包生成器（输入 !meme help 查看详细用法）", invoke_without_command=True)
    async def meme_group(self, ctx):
        """表情包生成器命令组"""
        if ctx.invoked_subcommand is None:
            await self.show_help(ctx)

    @meme_group.command(name="help", description="meme命令帮助", hidden=True)
    async def meme_help(self, ctx):
        """显示meme命令帮助"""
        await self.show_help(ctx)

    @meme_group.command(name="templates", aliases=["tpls", "list"], description="列出可用表情包模板", hidden=True)
    async def meme_templates(self, ctx):
        """列出可用表情包模板"""
        await self.list_templates(ctx)

    @meme_group.command(name="detail", aliases=["info", "详情"], description="查看指定meme模板参数", hidden=True)
    async def meme_detail(self, ctx, template: str):
        """查看指定meme模板详情"""
        await self.show_template_detail(ctx, template)

    @meme_group.command(name="blacklist", description="查看禁用的meme模板", hidden=True)
    async def meme_blacklist(self, ctx):
        """查看禁用的meme模板"""
        await self.show_blacklist(ctx)

    @meme_group.command(name="disable", aliases=["禁用"], description="禁用某个meme模板", hidden=True)
    async def disable_meme(self, ctx, template: str):
        """禁用meme模板"""
        await self.disable_template(ctx, template)

    @meme_group.command(name="enable", aliases=["启用"], description="启用某个meme模板", hidden=True)
    async def enable_meme(self, ctx, template: str):
        """启用meme模板"""
        await self.enable_template(ctx, template)

    @meme_group.command(name="generate", aliases=["gen", "创建"], description="生成表情包", hidden=True)
    async def generate_meme(self, ctx, template: str, *args: str):
        """生成表情包"""
        await self.generate(ctx, template, *args)

    @commands.command(name="memegen", aliases=["表情包"], description="生成表情包：!memegen 模板名 [文本1 文本2 ...] [@用户1 @用户2 ...]...（可带图片/图片URL/key=value）", hidden=True)
    async def meme_direct(self, ctx, template: str = None, *args: str):
        """直接生成表情包（兼容性命令）"""
        if template is None:
            await self.show_help(ctx)
        else:
            await self.generate(ctx, template, *args)
    
    @commands.command(name="memehelp", description="meme命令帮助", hidden=True)
    async def memehelp_direct(self, ctx):
        """显示meme命令帮助（兼容性命令）"""
        await self.show_help(ctx)

    @commands.command(name="memetpls", description="列出可用表情包模板", hidden=True)
    async def memetpls_direct(self, ctx):
        """列出可用表情包模板（兼容性命令）"""
        await self.list_templates(ctx)

    async def show_help(self, ctx):
        """显示meme命令帮助"""
        embed = EmbedBuilder.info(
            title="表情包生成器帮助",
            description="使用简单的命令生成各种表情包"
        )
        
        embed.add_field(
            name="基本用法",
            value=(
                "```\n"
                "!meme generate 模板名 [文本1 文本2 ...] [@用户1 @用户2 ...] ...\n"
                "```\n"
                "可带图片附件/图片URL/key=value参数"
            ),
            inline=False
        )
        
        embed.add_field(
            name="示例",
            value=(
                "● `!meme generate doge 你好世界`\n"
                "● `!meme generate doge @某人 你好世界`（用@某人的头像）"
            ),
            inline=False
        )
        
        embed.add_field(
            name="可用子命令",
            value=(
                "● `!meme templates` - 查看所有模板\n"
                "● `!meme detail <模板名>` - 查看参数详情\n"
                "● `!meme blacklist` - 查看禁用模板\n"
                "● `!meme disable/enable <模板名>` - 禁用/启用模板"
            ),
            inline=False
        )
        
        embed.add_field(
            name="兼容性命令",
            value=(
                "● `!memegen <模板名> [参数]` - 直接生成表情包\n"
                "● `!memehelp` - 显示帮助\n"
                "● `!memetpls` - 查看模板列表"
            ),
            inline=False
        )
        
        await ctx.reply(embed=embed)

    async def list_templates(self, ctx):
        """列出可用表情包模板"""
        keys = get_meme_keys()
        total_memes = len(keys)
        
        # 创建主Embed
        main_embed = EmbedBuilder.create(
            title="📸 表情包模板列表",
            description=f"当前共有 {total_memes} 个可用模板",
            color_key="special"
        )

        # 生成markdown内容
        markdown_content = [
            "# 表情包模板列表\n",
            f"当前共有 {total_memes} 个可用模板\n",
            "\n## 模板列表\n"
        ]
        
        # 按类别组织模板
        categories = {}
        for i, key in enumerate(keys, 1):
            meme = get_meme(key)
            # 获取模板类别，如果没有则归类为"其他"
            category = next(iter(meme.tags), "其他") if meme.tags else "其他"
            
            if category not in categories:
                categories[category] = []
            
            template_info = f"{i}. **{key}**"
            if meme.keywords:
                template_info += f" (别名: {meme.keywords})"
            categories[category].append(template_info)

        # 将分类信息写入markdown
        for category, templates in sorted(categories.items()):
            markdown_content.append(f"\n### {category}\n")
            markdown_content.extend(f"{template}\n" for template in templates)
        
        # 添加使用说明
        markdown_content.extend([
            "\n## 使用说明\n",
            "- 使用 `!meme detail <模板名>` 查看具体模板的详细信息和参数\n",
            "- 使用 `!meme generate <模板名> [文本]` 生成表情包\n",
            "- 更多帮助请使用 `!meme help` 命令\n"
        ])
        
        # 写入文件
        try:
            # 使用UTF-8-SIG编码（带BOM），确保Windows下正确显示中文
            os.makedirs("data/meme", exist_ok=True)  # 确保目录存在
            markdown_file_path = "data/meme/meme_templates.md"
            with open(markdown_file_path, "w", encoding="utf-8-sig") as f:
                f.writelines(markdown_content)
            
            # 发送文件
            await ctx.send(
                embed=main_embed,
                file=File(markdown_file_path, filename="表情包模板列表.md")
            )
            
        except Exception as e:
            print(f"生成模板列表文件失败: {e}")
            # 如果文件操作失败，直接在Discord中显示
            content = "".join(markdown_content)
            # 分段发送，避免超过长度限制
            while content:
                # Discord消息限制为2000字符
                if len(content) <= 1900:
                    await ctx.send(f"```markdown\n{content}\n```")
                    break
                else:
                    # 找到合适的分割点
                    split_point = content[:1900].rfind("\n")
                    if split_point == -1:
                        split_point = 1900
                    await ctx.send(f"```markdown\n{content[:split_point]}\n```")
                    content = content[split_point:]

    async def show_template_detail(self, ctx, template: str):
        """查看指定meme模板详情"""
        try:
            # 使用find_template_by_name_or_keyword函数来支持中文模板名
            template_key = find_template_by_name_or_keyword(template)
            meme = get_meme(template_key)
        except NoSuchMeme:
            embed = EmbedBuilder.error("未找到模板", f"没有找到模板：{template}")
            await ctx.reply(embed=embed)
            return
        
        params_type = meme.params_type
        
        # 创建详情Embed
        embed = EmbedBuilder.create(
            title=f"模板详情：{template_key}",
            description=f"关于 {template_key} 模板的详细参数",
            color_key="info"
        )
        
        # 模板基本信息
        basic_info = ""
        if meme.keywords:
            if isinstance(meme.keywords, str):
                basic_info += f"别名：{meme.keywords}\n"
            elif isinstance(meme.keywords, (list, tuple)):
                basic_info += f"别名：{', '.join(meme.keywords)}\n"
        if params_type.max_images > 0:
            if params_type.min_images == params_type.max_images:
                basic_info += f"所需图片：{params_type.min_images}张\n"
            else:
                basic_info += f"所需图片：{params_type.min_images}~{params_type.max_images}张\n"
        if params_type.max_texts > 0:
            if params_type.min_texts == params_type.max_texts:
                basic_info += f"所需文本：{params_type.min_texts}段\n"
            else:
                basic_info += f"所需文本：{params_type.min_texts}~{params_type.max_texts}段\n"
        if params_type.default_texts:
            basic_info += f"默认文本：{params_type.default_texts}\n"
        if meme.tags:
            basic_info += f"标签：{list(meme.tags)}\n"
            
        if basic_info:
            embed.add_field(name="基本信息", value=basic_info, inline=False)
        
        # 参数详情
        args_type = getattr(params_type, "args_type", None)
        if args_type:
            params_info = ""
            for opt in args_type.parser_options:
                flags = [n for n in opt.names if n.startswith('--')]
                names_str = ", ".join(flags)
                part = f"  {names_str}"
                default_val = getattr(opt, "default", None)
                if default_val is not None:
                    part += f" (默认={default_val})"
                help_text = getattr(opt, "help_text", None)
                if help_text:
                    part += f" ： {help_text}"
                params_info += part + "\n"
            
            if params_info:
                embed.add_field(
                    name="可用参数 (格式: key=value)",
                    value=f"```\n{params_info}\n```",
                    inline=False
                )
        
        # 添加使用示例
        example = f"!meme generate {template} 文本(可选) @xxx"
        embed.add_field(name="使用示例", value=f"```\n{example}\n```", inline=False)
        
        # 生成预览
        try:
            preview = meme.generate_preview().getvalue()
            buf = io.BytesIO(preview)
            
            # 检测图片格式
            img_format = detect_image_format(buf)
            
            await ctx.send(embed=embed, file=File(buf, filename=f"{template_key}_preview.{img_format}"))
        except Exception as e:
            # 无法生成预览图时，至少发送文本
            print(f"生成预览图失败: {e}")  # 添加错误日志
            await ctx.reply(embed=embed)

    async def show_blacklist(self, ctx):
        """查看禁用的meme模板"""
        if MEME_DISABLED_LIST:
            embed = EmbedBuilder.warning(
                title="已禁用的模板", 
                description="以下模板已被禁用，无法使用"
            )
            embed.add_field(
                name="禁用列表",
                value="、".join(MEME_DISABLED_LIST),
                inline=False
            )
        else:
            embed = EmbedBuilder.success(
                title="无禁用模板",
                description="当前没有禁用的模板，所有模板均可使用"
            )
        
        await ctx.reply(embed=embed)

    async def disable_template(self, ctx, template: str):
        """禁用meme模板"""
        try:
            # 使用find_template_by_name_or_keyword函数来支持中文模板名
            template_key = find_template_by_name_or_keyword(template)
            MEME_DISABLED_LIST.add(template_key)
            
            embed = EmbedBuilder.success(
                title="模板已禁用",
                description=f"已成功禁用模板：`{template_key}`"
            )
            await ctx.reply(embed=embed)
        except NoSuchMeme:
            embed = EmbedBuilder.error(
                title="模板不存在",
                description=f"无法禁用不存在的模板：`{template}`"
            )
            await ctx.reply(embed=embed)

    async def enable_template(self, ctx, template: str):
        """启用meme模板"""
        try:
            # 使用find_template_by_name_or_keyword函数来支持中文模板名
            template_key = find_template_by_name_or_keyword(template)
            if template_key in MEME_DISABLED_LIST:
                MEME_DISABLED_LIST.remove(template_key)
                embed = EmbedBuilder.success(
                    title="模板已启用",
                    description=f"已成功启用模板：`{template_key}`"
                )
            else:
                embed = EmbedBuilder.info(
                    title="模板未被禁用",
                    description=f"模板 `{template_key}` 未被禁用，无需启用"
                )
            await ctx.reply(embed=embed)
        except NoSuchMeme:
            embed = EmbedBuilder.error(
                title="模板不存在",
                description=f"无法启用不存在的模板：`{template}`"
            )
            await ctx.reply(embed=embed)

    async def generate(self, ctx, template: str, *args: str):
        """生成表情包"""
        try:
            # 使用find_template_by_name_or_keyword函数来支持中文模板名
            template_key = find_template_by_name_or_keyword(template)
            if template_key in MEME_DISABLED_LIST:
                embed = EmbedBuilder.warning(
                    title="模板已禁用",
                    description=f"模板 `{template_key}` 已被禁用，无法使用"
                )
                await ctx.reply(embed=embed)
                return
        except NoSuchMeme:
            # 获取所有模板的关键词信息
            template_info = []
            for key in get_meme_keys()[:10]:
                meme = get_meme(key)
                info = f"`{key}`"
                if meme.keywords:
                    if isinstance(meme.keywords, str):
                        info += f" (别名: {meme.keywords})"
                    elif isinstance(meme.keywords, (list, tuple)):
                        info += f" (别名: {', '.join(meme.keywords)})"
                template_info.append(info)
            
            embed = EmbedBuilder.error(
                title="模板不存在", 
                description=f"没有找到模板：`{template}`\n可用模板：\n" + "\n".join(template_info) + "\n..."
            )
            await ctx.reply(embed=embed)
            return
        
        # 收集图片参数（支持消息附件和URL）
        images = []
        
        # 1. 附件图片
        for attachment in getattr(ctx.message, "attachments", []):
            if isinstance(attachment, Attachment):
                img_bytes = await attachment.read()
                images.append(img_bytes)
                
        # 2. 识别@用户
        mentions = getattr(ctx.message, "mentions", [])
        mention_avatars = []
        mention_names = []
        for user in mentions:
            avatar = await get_avatar(user)
            if avatar:
                mention_avatars.append(avatar)
                # 优先用display_name，没有就用name
                name = getattr(user, 'display_name', None) or getattr(user, 'name', None) or str(user.id)
                mention_names.append(name)
                
        # 3. 识别文本参数中的图片URL
        url_pattern = re.compile(r'^(http|https)://.*\\.(jpg|jpeg|png|gif)$', re.IGNORECASE)
        texts, options = parse_key_value_args(args)
        url_texts = []
        for t in texts[:]:
            if url_pattern.match(t):
                img_bytes = await download_image(t)
                if img_bytes:
                    images.append(img_bytes)
                    url_texts.append(t)
        texts = [t for t in texts if t not in url_texts]
        
        # 获取模板
        meme = get_meme(template_key)
        params_type = meme.params_type
        
        # 优先用@用户头像
        all_images = mention_avatars + images
        
        # 不足时补自己头像
        if len(all_images) < params_type.max_images and hasattr(ctx, "author"):
            avatar = await get_avatar(ctx.author)
            if avatar:
                all_images.append(avatar)
        all_images = all_images[:params_type.max_images]
        
        # 补全文本，优先使用用户输入的文本，如果文本不足再用@用户名补充
        all_names = texts
        if len(all_names) < params_type.min_texts:
            all_names.extend(mention_names)
        if len(all_names) < params_type.min_texts:
            all_names.extend(params_type.default_texts[:params_type.min_texts - len(all_names)])
        all_names = all_names[:params_type.max_texts]
        
        # 生成表情包
        try:
            img_bytes = await ctx.bot.loop.run_in_executor(
                None, lambda: meme(images=all_images, texts=all_names, args=options)
            )
            img_bytes.seek(0)
            
            # 检测图片格式
            img_format = detect_image_format(img_bytes)
            
            # 创建生成结果的Embed
            embed = EmbedBuilder.create(
                title=f"表情包：{template_key}",
                color_key="success"
            )
            embed.set_author(
                name=f"{ctx.author.display_name} 生成的表情包",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            
            # 使用Discord内置显示图片而不是嵌入到Embed中
            await ctx.send(embed=embed, file=File(img_bytes, filename=f"{template_key}.{img_format}"))
            
        except MemeGeneratorException as e:
            embed = EmbedBuilder.error(
                title="生成失败",
                description=f"生成表情包失败: {e}"
            )
            await ctx.reply(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                title="未知错误",
                description=f"生成过程中出现未知错误: {e}"
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    """加载表情包生成器插件"""
    await bot.add_cog(MemePlugin(bot)) 