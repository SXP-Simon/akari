"""Galgame 信息查询插件

基于月幕Gal的API，提供Galgame信息查询功能。
支持精确查询和模糊搜索，展示游戏详细信息和封面图。

Commands:
    !gal search <游戏名> - 精确查询游戏信息
    !gal fuzzy <关键词> - 模糊搜索游戏
    !gal info <游戏ID> - 查看游戏详细信息
"""

from .plugin import setup

__all__ = ["setup"] 