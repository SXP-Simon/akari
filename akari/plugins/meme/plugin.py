import io
import os
from discord.ext import commands
from akari.bot.utils import EmbedBuilder, EmbedData
from .manager import MemeManager
from .utils import get_avatar, download_image, parse_key_value_args, detect_image_format
from meme_generator import get_meme, get_meme_keys
from meme_generator.exception import MemeGeneratorException, NoSuchMeme
from meme_generator.utils import render_meme_list
from discord import File

meme_manager = MemeManager()

class MemePlugin(commands.Cog):
    """表情包生成器插件"""
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="meme", description="表情包生成器", invoke_without_command=True)
    async def meme_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.show_help(ctx)

    @meme_group.command(name="help", description="显示meme命令帮助")
    async def meme_help(self, ctx):
        await self.show_help(ctx)

    @meme_group.command(name="templates", aliases=["tpls", "list"], description="列出可用表情包模板")
    async def meme_templates(self, ctx):
        await self._generate_and_send_md(ctx)

    @meme_group.command(name="detail", aliases=["info", "详情"], description="查看指定meme模板参数")
    async def meme_detail(self, ctx, template: str):
        await self.show_template_detail(ctx, template)

    @meme_group.command(name="blacklist", description="查看禁用的meme模板")
    async def meme_blacklist(self, ctx):
        await self.show_blacklist(ctx)

    @meme_group.command(name="disable", aliases=["禁用"], description="禁用某个meme模板")
    async def disable_meme(self, ctx, template: str):
        await self.disable_template(ctx, template)

    @meme_group.command(name="enable", aliases=["启用"], description="启用某个meme模板")
    async def enable_meme(self, ctx, template: str):
        await self.enable_template(ctx, template)

    @meme_group.command(name="generate", aliases=["gen", "创建"], description="生成表情包")
    async def generate_meme(self, ctx, template: str, *, args: str = ""):
        args_list = args.split() if args else []
        await self.generate(ctx, template, *args_list)

    @meme_group.command(name="memegen", aliases=["表情包"], description="生成表情包")
    async def meme_direct(self, ctx, template: str = None, *, args: str = ""):
        if template is None:
            await self.show_help(ctx)
        else:
            args_list = args.split() if args else []
            await self.generate(ctx, template, *args_list)

    @commands.command(name="memehelp", description="meme命令帮助", hidden=True)
    async def memehelp_direct(self, ctx):
        await self.show_help(ctx)

    @commands.command(name="memetpls", description="列出可用表情包模板", hidden=True)
    async def memetpls_direct(self, ctx):
        await self._generate_and_send_md(ctx)

    async def _generate_and_send_md(self, ctx):
        # 收集所有可用模板，写入 meme_templates.md
        keys = get_meme_keys()
        total_memes = len(keys)
        markdown_content = [
            "# 表情包模板列表\n",
            f"当前共有 {total_memes} 个可用模板\n",
            "\n## 模板列表\n"
        ]
        categories = {}
        for i, key in enumerate(keys, 1):
            meme = get_meme(key)
            category = next(iter(meme.tags), "其他") if getattr(meme, 'tags', None) else "其他"
            if category not in categories:
                categories[category] = []
            template_info = f"{i}. **{key}**"
            if getattr(meme, 'keywords', None):
                template_info += f" (别名: {meme.keywords})"
            categories[category].append(template_info)
        for category, templates in sorted(categories.items()):
            markdown_content.append(f"\n### {category}\n")
            markdown_content.extend(f"{template}\n" for template in templates)
        markdown_content.extend([
            "\n## 使用说明\n",
            "- 使用 `!meme detail <模板名>` 查看具体模板的详细信息和参数\n",
            "- 使用 `!meme generate <模板名> [文本]` 生成表情包\n",
            "- 更多帮助请使用 `!meme help` 命令\n"
        ])
        import os
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "meme_templates.md")
        with open(file_path, "w", encoding="utf-8-sig") as f:
            f.writelines(markdown_content)
        from discord import File
        await ctx.reply(file=File(file_path, filename="meme_templates.md"))

    async def show_help(self, ctx):
        embed = EmbedBuilder.create(EmbedData(
            title="表情包生成器帮助",
            description="使用简单的命令生成各种表情包",
            color=EmbedBuilder.THEME.info
        ))
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

    async def show_template_detail(self, ctx, template: str):
        try:
            key = meme_manager.find_template_by_name_or_keyword(template)
            meme = get_meme(key)
        except NoSuchMeme:
            embed = EmbedBuilder.create(EmbedData(
                title="未找到模板",
                description=f"没有找到模板：{template}",
                color=EmbedBuilder.THEME.error
            ))
            await ctx.reply(embed=embed)
            return
        params_type = getattr(meme, 'params_type', None)
        # 兼容 desc/description 字段
        desc = getattr(meme, 'desc', None) or getattr(meme, 'description', None) or "无描述"
        embed = EmbedBuilder.create(EmbedData(
            title=f"模板详情：{key}",
            description=desc,
            color=EmbedBuilder.THEME.info
        ))
        # 基本信息
        basic_info = ""
        if getattr(meme, 'keywords', None):
            if isinstance(meme.keywords, str):
                basic_info += f"别名：{meme.keywords}\n"
            elif isinstance(meme.keywords, (list, tuple)):
                basic_info += f"别名：{', '.join(meme.keywords)}\n"
        if params_type:
            if getattr(params_type, 'max_images', 0) > 0:
                if params_type.min_images == params_type.max_images:
                    basic_info += f"所需图片：{params_type.min_images}张\n"
                else:
                    basic_info += f"所需图片：{params_type.min_images}~{params_type.max_images}张\n"
            if getattr(params_type, 'max_texts', 0) > 0:
                if params_type.min_texts == params_type.max_texts:
                    basic_info += f"所需文本：{params_type.min_texts}段\n"
                else:
                    basic_info += f"所需文本：{params_type.min_texts}~{params_type.max_texts}段\n"
            if getattr(params_type, 'default_texts', None):
                basic_info += f"默认文本：{params_type.default_texts}\n"
        if getattr(meme, 'tags', None):
            basic_info += f"标签：{list(meme.tags)}\n"
        if basic_info:
            embed.add_field(name="基本信息", value=basic_info, inline=False)
        # 参数详情
        args_type = getattr(params_type, "args_type", None) if params_type else None
        if args_type:
            params_info = ""
            for opt in getattr(args_type, "parser_options", []):
                flags = [n for n in getattr(opt, "names", []) if n.startswith('--')]
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
        # 使用示例
        example = f"!meme generate {template} 文本(可选) @xxx"
        embed.add_field(name="使用示例", value=f"```\n{example}\n```", inline=False)
        # 生成预览图
        preview_file = None
        try:
            if hasattr(meme, 'generate_preview'):
                preview_bytes = meme.generate_preview().getvalue()
                import io
                buf = io.BytesIO(preview_bytes)
                buf.seek(0)
                img_format = detect_image_format(buf)
                from discord import File
                preview_file = File(buf, filename=f"{key}_preview.{img_format}")
        except Exception as e:
            # 生成预览失败，忽略
            pass
        if preview_file:
            await ctx.reply(embed=embed, file=preview_file)
        else:
            await ctx.reply(embed=embed)

    async def show_blacklist(self, ctx):
        if not meme_manager.disabled_list:
            await ctx.reply("当前没有禁用的模板。")
            return
        await ctx.reply("已禁用模板: " + ", ".join(meme_manager.disabled_list))

    async def disable_template(self, ctx, template: str):
        try:
            key = meme_manager.find_template_by_name_or_keyword(template)
            meme_manager.disable(key)
            await ctx.reply(f"已禁用模板: {key}")
        except NoSuchMeme:
            await ctx.reply(f"未找到模板: {template}")

    async def enable_template(self, ctx, template: str):
        try:
            key = meme_manager.find_template_by_name_or_keyword(template)
            meme_manager.enable(key)
            await ctx.reply(f"已启用模板: {key}")
        except NoSuchMeme:
            await ctx.reply(f"未找到模板: {template}")

    async def generate(self, ctx, template: str, *args: str):
        try:
            key = meme_manager.find_template_by_name_or_keyword(template)
            if meme_manager.is_disabled(key):
                await ctx.reply(f"该模板已被禁用: {key}")
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
            embed = EmbedBuilder.create(EmbedData(
                title="模板不存在",
                description=f"没有找到模板：`{template}`\n可用模板：\n" + "\n".join(template_info) + "\n...",
                color=EmbedBuilder.THEME.error
            ))
            await ctx.reply(embed=embed)
            return
        # 收集图片参数（支持消息附件和URL）
        images = []
        # 1. 附件图片
        for attachment in getattr(ctx.message, "attachments", []):
            if hasattr(attachment, 'read'):
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
                name = getattr(user, 'display_name', None) or getattr(user, 'name', None) or str(user.id)
                mention_names.append(name)
        # 3. 识别文本参数中的图片URL
        import re
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
        meme = get_meme(key)
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
            img_format = detect_image_format(img_bytes)
            embed = EmbedBuilder.create(EmbedData(
                title=f"表情包：{key}",
                color=EmbedBuilder.THEME.success
            ))
            embed.set_author(
                name=f"{ctx.author.display_name} 生成的表情包",
                icon_url=ctx.author.avatar.url if getattr(ctx.author, 'avatar', None) else ctx.author.default_avatar.url
            )
            await ctx.send(embed=embed, file=File(img_bytes, filename=f"{key}.{img_format}"))
        except MemeGeneratorException as e:
            embed = EmbedBuilder.create(EmbedData(
                title="生成失败",
                description=f"生成表情包失败: {e}",
                color=EmbedBuilder.THEME.error
            ))
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = EmbedBuilder.create(EmbedData(
                title="未知错误",
                description=f"生成过程中出现未知错误: {e}",
                color=EmbedBuilder.THEME.error
            ))
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(MemePlugin(bot))