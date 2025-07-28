"""Manga 下载插件

基于漫画网站的API，提供漫画下载功能。
支持按名称搜索漫画、下载章节、展示漫画封面等功能。

Commands:
    !manga search <漫画名> - 搜索漫画
    !manga download <漫画ID> <章节号> - 下载指定章节
    !manga info <漫画ID> - 查看漫画详细信息
"""

from .plugin import setup

__all__ = ["setup"] 