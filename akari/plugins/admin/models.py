from dataclasses import dataclass
from typing import Set

@dataclass
class AdminConfig:
    """管理员配置"""
    admin_users: Set[int]  # 管理员用户ID集合
    admin_roles: Set[int]  # 管理员角色ID集合
    super_admin_users: Set[int]  # 超级管理员用户ID集合 