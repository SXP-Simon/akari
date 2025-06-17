"""
akari.plugins

插件包目录，包含所有机器人插件。
每个插件都应该实现 async def setup(bot) 方法。

插件开发指南:
1. 每个插件应该是一个独立的Python模块或包
2. 插件必须实现 async def setup(bot) 方法
3. 插件应该继承 commands.Cog 类
4. 插件应该有完整的文档字符串
5. 插件应该处理自己的异常
6. 插件应该在卸载时清理资源
"""

__all__ = []  # 动态添加已加载的插件 