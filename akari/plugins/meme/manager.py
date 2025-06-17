from meme_generator import get_meme, get_meme_keys
from meme_generator.exception import NoSuchMeme

class MemeManager:
    """表情包业务逻辑管理器"""
    def __init__(self):
        self.disabled_list = set()

    def disable(self, key: str):
        self.disabled_list.add(key)

    def enable(self, key: str):
        self.disabled_list.discard(key)

    def is_disabled(self, key: str) -> bool:
        return key in self.disabled_list

    def find_template_by_name_or_keyword(self, template_name: str) -> str:
        try:
            meme = get_meme(template_name)
            return meme.key
        except NoSuchMeme:
            for key in get_meme_keys():
                meme = get_meme(key)
                if meme.keywords:
                    if isinstance(meme.keywords, str):
                        keywords = meme.keywords.split(',')
                    elif isinstance(meme.keywords, (list, tuple)):
                        keywords = meme.keywords
                    else:
                        continue
                    if template_name in keywords or any(k.strip() == template_name for k in keywords):
                        return key
            raise NoSuchMeme(template_name) 