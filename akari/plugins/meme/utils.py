import aiohttp
import io
from discord import Member, User

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
    current_pos = img_bytes.tell()
    img_bytes.seek(0)
    header = img_bytes.read(8)
    img_bytes.seek(current_pos)
    if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
        return 'gif'
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    elif header.startswith(b'\xff\xd8'):
        return 'jpg'
    return 'png' 