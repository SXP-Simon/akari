import os

class MagnetPreviewConfig:
    API_URL = os.getenv("MAGNET_API_URL", "https://pics.magnetq.com/")
    MAX_IMAGES = int(os.getenv("MAGNET_MAX_IMAGES", 3))
    CACHE_DIR = os.getenv("MAGNET_CACHE_DIR", "data/magnet_preview_cache") 

# 预编译正则表达式提高性能
# _MAGNET_PATTERN = re.compile(r"^magnet:\?xt=urn:btih:[\w\d]{40}.*")
# _REFERER_OPTIONS = [
#     "https://beta.magnet.pics/",
#     "https://tmp.nulla.top/",
#     "https://pics.magnetq.com/"
# ]
