"""表情包生成插件

基于 meme_generator 库，提供表情包生成功能。
支持多种模板、自定义文本和图片生成。

Commands:
    !meme help - 显示表情包命令帮助
    !meme templates - 列出可用表情包模板
    !meme detail <模板名> - 查看模板详细信息
    !meme generate <模板名> [文本] - 生成表情包
"""

from .plugin import setup

__all__ = ["setup"] 