import re

MAGNET_PATTERN = re.compile(r"magnet:\?xt=urn:btih:[\w\d]{40}.*")

def is_magnet(link: str) -> bool:
    return bool(MAGNET_PATTERN.match(link))

def format_file_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = min(int((size_bytes or 1).bit_length() / 10), len(units) - 1)
    size = size_bytes / (1024 ** unit_index)
    return f"{size:.2f} {units[unit_index]}" 