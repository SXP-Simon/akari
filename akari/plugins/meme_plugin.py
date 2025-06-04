import io
import re
import asyncio
import aiohttp
from discord import File, Attachment, Member, Message, User
from akari.bot.commands import command, group
from meme_generator import get_meme, get_meme_keys, get_memes
from meme_generator.exception import MemeGeneratorException, NoSuchMeme
from meme_generator.utils import render_meme_list
from akari.bot.utils import EmbedBuilder

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

def setup(bot):
    meme_plugin = MemePlugin(bot)
    
    @bot.register_command
    @group(name="meme", description="表情包生成器（输入 !meme help 查看详细用法）")
    async def meme_group(ctx):
        """表情包生成器命令组"""
        if ctx.invoked_subcommand is None:
            await meme_plugin.show_help(ctx)

    @meme_group.command(name="help", description="meme命令帮助")
    async def meme_help(ctx):
        """显示meme命令帮助"""
        await meme_plugin.show_help(ctx)

    @meme_group.command(name="templates", aliases=["tpls", "list"], description="列出可用表情包模板")
    async def meme_templates(ctx):
        """列出可用表情包模板"""
        await meme_plugin.list_templates(ctx)

    @meme_group.command(name="detail", aliases=["info", "详情"], description="查看指定meme模板参数")
    async def meme_detail(ctx, template: str):
        """查看指定meme模板详情
        参数:
            template: 模板名称
        """
        await meme_plugin.show_template_detail(ctx, template)

    @meme_group.command(name="blacklist", description="查看禁用的meme模板")
    async def meme_blacklist(ctx):
        """查看禁用的meme模板"""
        await meme_plugin.show_blacklist(ctx)

    @meme_group.command(name="disable", aliases=["禁用"], description="禁用某个meme模板")
    async def disable_meme(ctx, template: str):
        """禁用meme模板
        参数:
            template: 要禁用的模板名称
        """
        await meme_plugin.disable_template(ctx, template)

    @meme_group.command(name="enable", aliases=["启用"], description="启用某个meme模板")
    async def enable_meme(ctx, template: str):
        """启用meme模板
        参数:
            template: 要启用的模板名称
        """
        await meme_plugin.enable_template(ctx, template)

    @meme_group.command(name="generate", aliases=["gen", "创建"], description="生成表情包")
    async def generate_meme(ctx, template: str, *args: str):
        """生成表情包
        参数:
            template: 模板名称
            args: 各种参数，可包含@用户、文本、key=value
        """
        await meme_plugin.generate(ctx, template, *args)

    # 修改兼容性命令名称，避免与命令组冲突
    @bot.register_command
    @command(name="memegen", aliases=["表情包"], description="生成表情包：!memegen 模板名 [文本1 文本2 ...] [@用户1 @用户2 ...]...（可带图片/图片URL/key=value）")
    async def meme_direct(ctx, template: str = None, *args: str):
        """直接生成表情包（兼容性命令）"""
        if template is None:
            await meme_plugin.show_help(ctx)
        else:
            await meme_plugin.generate(ctx, template, *args)
    
    @bot.register_command
    @command(name="memehelp", description="meme命令帮助")
    async def memehelp_direct(ctx):
        """显示meme命令帮助（兼容性命令）"""
        await meme_plugin.show_help(ctx)

    @bot.register_command
    @command(name="memetpls", description="列出可用表情包模板")
    async def memetpls_direct(ctx):
        """列出可用表情包模板（兼容性命令）"""
        await meme_plugin.list_templates(ctx)

class MemePlugin:
    """表情包生成器插件"""
    
    def __init__(self, bot):
        self.bot = bot
    
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
        ls_num = 10
        keys = get_meme_keys()
        
        embed = EmbedBuilder.create(
            title="📸 表情包模板列表",
            description="以下是常用的表情包模板",
            color_key="special"
        )
        
        # 添加部分模板名
        template_names = "、".join(keys[:ls_num]) + (" ..." if len(keys) > ls_num else "")
        embed.add_field(name="可用模板", value=template_names, inline=False)
        
        # 尝试获取预览图
        try:
            meme_list = [(meme, None) for meme in get_memes()[:ls_num]]
            image_io = render_meme_list(meme_list=meme_list, text_template="{index}.{keywords}", add_category_icon=True)
            buf = io.BytesIO(image_io.getvalue())
            
            # 添加快速链接
            embed.add_field(
                name="完整列表",
                value="完整表情包模板列表请见：[模板列表](https://github.com/MemeCrafters/meme-generator/wiki/%E8%A1%A8%E6%83%85%E5%88%97%E8%A1%A8) \n (包含所有关键词、参数和预览)",
                inline=False
            )
            
            await ctx.send(embed=embed, file=File(buf, filename="meme_list.png"))
        except Exception:
            # 无法生成预览图时，至少发送文本
            await ctx.reply(embed=embed)

    async def show_template_detail(self, ctx, template: str):
        """查看指定meme模板详情"""
        try:
            meme = get_meme(template)
        except NoSuchMeme:
            embed = EmbedBuilder.error("未找到模板", f"没有找到模板：{template}")
            await ctx.reply(embed=embed)
            return
        
        params_type = meme.params_type
        
        # 创建详情Embed
        embed = EmbedBuilder.create(
            title=f"模板详情：{meme.key}",
            description=f"关于 {meme.key} 模板的详细参数",
            color_key="info"
        )
        
        # 模板基本信息
        basic_info = ""
        if meme.keywords:
            basic_info += f"别名：{meme.keywords}\n"
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
            await ctx.send(embed=embed, file=File(buf, filename=f"{template}_preview.png"))
        except Exception:
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
            # 验证模板是否存在
            get_meme(template)
            MEME_DISABLED_LIST.add(template)
            
            embed = EmbedBuilder.success(
                title="模板已禁用",
                description=f"已成功禁用模板：`{template}`"
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
        if template in MEME_DISABLED_LIST:
            MEME_DISABLED_LIST.remove(template)
            embed = EmbedBuilder.success(
                title="模板已启用",
                description=f"已成功启用模板：`{template}`"
            )
        else:
            embed = EmbedBuilder.info(
                title="模板未被禁用",
                description=f"模板 `{template}` 未被禁用，无需启用"
            )
        
        await ctx.reply(embed=embed)

    async def generate(self, ctx, template: str, *args: str):
        """生成表情包"""
        if template in MEME_DISABLED_LIST:
            embed = EmbedBuilder.warning(
                title="模板已禁用",
                description=f"模板 `{template}` 已被禁用，无法使用"
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
        
        # 4. 自动补头像
        try:
            meme = get_meme(template)
        except NoSuchMeme:
            embed = EmbedBuilder.error(
                title="模板不存在", 
                description=f"没有找到模板：`{template}`\n可用模板：{'、'.join(get_meme_keys()[:10])}..."
            )
            await ctx.reply(embed=embed)
            return
        
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
            
            # 创建生成结果的Embed
            embed = EmbedBuilder.create(
                title=f"表情包：{template}",
                color_key="success"
            )
            embed.set_author(
                name=f"{ctx.author.display_name} 生成的表情包",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
            )
            
            # 使用Discord内置显示图片而不是嵌入到Embed中
            await ctx.send(embed=embed, file=File(img_bytes, filename=f"{template}.png"))
            
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