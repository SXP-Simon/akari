import os
import json
from .models import AdminConfig

class AdminManager:
    """管理员管理器"""
    def __init__(self, config_path: str = "data/admin/admin_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> AdminConfig:
        """加载管理员配置"""
        if not os.path.exists(self.config_path):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            default_config = {
                "admin_users": [],
                "admin_roles": [],
                "super_admin_users": []
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return AdminConfig(set(), set(), set())

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AdminConfig(
            set(data.get("admin_users", [])),
            set(data.get("admin_roles", [])),
            set(data.get("super_admin_users", []))
        )

    def save_config(self):
        """保存管理员配置"""
        data = {
            "admin_users": list(self.config.admin_users),
            "admin_roles": list(self.config.admin_roles),
            "super_admin_users": list(self.config.super_admin_users)
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_admin(self, member) -> bool:
        return (
            member.id in self.config.admin_users or
            any(role.id in self.config.admin_roles for role in getattr(member, "roles", [])) or
            member.id in self.config.super_admin_users
        )

    def is_super_admin(self, member) -> bool:
        return member.id in self.config.super_admin_users

    def add_admin(self, user_id: int, is_super: bool = False) -> bool:
        if is_super:
            if user_id in self.config.super_admin_users:
                return False
            self.config.super_admin_users.add(user_id)
        else:
            if user_id in self.config.admin_users:
                return False
            self.config.admin_users.add(user_id)
        self.save_config()
        return True

    def remove_admin(self, user_id: int, is_super: bool = False) -> bool:
        if is_super:
            if user_id not in self.config.super_admin_users:
                return False
            self.config.super_admin_users.remove(user_id)
        else:
            if user_id not in self.config.admin_users:
                return False
            self.config.admin_users.remove(user_id)
        self.save_config()
        return True 