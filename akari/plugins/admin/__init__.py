"""管理员插件

提供管理员命令，用于管理机器人、服务器和用户。
支持权限控制、日志记录和系统维护。

Commands:
    !admin help - 显示管理员命令帮助
    !admin reload - 重新加载插件
    !admin shutdown - 关闭机器人
"""

from .plugin import setup

__all__ = ["setup"] 