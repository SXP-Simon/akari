import io
import re
import asyncio
import aiohttp
from discord import File, Attachment, Member, Message, User
from akari.bot.commands import command
from meme_generator import get_meme, get_meme_keys, get_memes
from meme_generator.exception import MemeGeneratorException, NoSuchMeme
from meme_generator.utils import render_meme_list

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
    @bot.register_command
    @command(name="memehelp", description="meme命令帮助")
    async def memehelp(ctx):
        await ctx.reply(
            "用法：!meme 模板名 [@用户1 @用户2 ...] 文本1 文本2 ...（可带图片附件/图片URL/key=value参数）\n"
            "示例：!meme doge 你好世界\n"
            "示例：!meme doge @某人 你好世界（用@某人的头像）\n"
            "用 !memetpls 查看所有模板\n"
            "用 !meme详情 模板名 查看参数"
        )

    @bot.register_command
    @command(name="memetpls", description="列出可用表情包模板")
    async def memetpls(ctx):
        ls_num = 10
        keys = get_meme_keys()
        text = "可用模板：" + "、".join(keys[:ls_num]) + (" ..." if len(keys) > ls_num else "")
        try:
            meme_list = [(meme, None) for meme in get_memes()[:ls_num]]
            image_io = render_meme_list(meme_list=meme_list, text_template="{index}.{keywords}", add_category_icon=True)
            buf = io.BytesIO(image_io.getvalue())
            await ctx.send(text, file=File(buf, filename="meme_list.png"))
        except Exception:
            await ctx.reply(text)
        await ctx.reply("完整表情包模板列表请见：https://github.com/MemeCrafters/meme-generator/wiki/%E8%A1%A8%E6%83%85%E5%88%97%E8%A1%A8 \n (包含所有关键词、参数和预览)")

    @bot.register_command
    @command(name="meme详情", description="查看指定meme模板参数")
    async def meme_detail(ctx, template: str):
        try:
            meme = get_meme(template)
        except NoSuchMeme:
            await ctx.reply(f"没有找到模板：{template}")
            return
        params_type = meme.params_type
        info = f"名称：{meme.key}\n"
        if meme.keywords:
            info += f"别名：{meme.keywords}\n"
        if params_type.max_images > 0:
            if params_type.min_images == params_type.max_images:
                info += f"所需图片：{params_type.min_images}张\n"
            else:
                info += f"所需图片：{params_type.min_images}~{params_type.max_images}张\n"
        if params_type.max_texts > 0:
            if params_type.min_texts == params_type.max_texts:
                info += f"所需文本：{params_type.min_texts}段\n"
            else:
                info += f"所需文本：{params_type.min_texts}~{params_type.max_texts}段\n"
        if params_type.default_texts:
            info += f"默认文本：{params_type.default_texts}\n"
        if meme.tags:
            info += f"标签：{list(meme.tags)}\n"
        args_type = getattr(params_type, "args_type", None)
        if args_type:
            info += "其它参数(格式: key=value)：\n"
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
                info += part + "\n"
        # 生成预览
        try:
            preview = meme.generate_preview().getvalue()
            buf = io.BytesIO(preview)
            await ctx.send(info, file=File(buf, filename=f"{template}_preview.png"))
        except Exception:
            await ctx.reply(info)

    @bot.register_command
    @command(name="memeblacklist", description="查看禁用的meme模板")
    async def memeblacklist(ctx):
        if MEME_DISABLED_LIST:
            await ctx.reply("当前禁用的模板：" + "、".join(MEME_DISABLED_LIST))
        else:
            await ctx.reply("当前没有禁用的模板。")

    @bot.register_command
    @command(name="禁用meme", description="禁用某个meme模板")
    async def disable_meme(ctx, template: str):
        MEME_DISABLED_LIST.add(template)
        await ctx.reply(f"已禁用模板：{template}")

    @bot.register_command
    @command(name="启用meme", description="启用某个meme模板")
    async def enable_meme(ctx, template: str):
        if template in MEME_DISABLED_LIST:
            MEME_DISABLED_LIST.remove(template)
            await ctx.reply(f"已启用模板：{template}")
        else:
            await ctx.reply(f"模板 {template} 未被禁用")

    @bot.register_command
    @command(name="meme", description="生成表情包：!meme 模板名 [@用户1 @用户2 ...] 文本1 文本2 ...（可带图片/图片URL/key=value）")
    async def meme(ctx, template: str, *args: str):
        if template in MEME_DISABLED_LIST:
            await ctx.reply(f"模板 {template} 已被禁用")
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
            await ctx.reply(f"没有找到模板：{template}，可用模板：{'、'.join(get_meme_keys()[:10])} ...")
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
        # 补全文本，优先用@用户的用户名
        all_names = mention_names + texts
        if len(all_names) < params_type.min_texts:
            all_names += params_type.default_texts[:params_type.min_texts - len(all_names)]
        all_names = all_names[:params_type.max_texts]
        # 生成表情
        try:
            img_bytes = await ctx.bot.loop.run_in_executor(
                None, lambda: meme(images=all_images, texts=all_names, args=options)
            )
            img_bytes.seek(0)
            await ctx.send(file=File(img_bytes, filename=f"{template}.png"))
        except MemeGeneratorException as e:
            await ctx.reply(f"生成表情包失败: {e}")
        except Exception as e:
            await ctx.reply(f"未知错误: {e}") 