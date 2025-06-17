from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class BotConfig(BaseSettings):
    """机器人配置模型"""
    # Discord配置
    discord_token: str = Field(
        default=...,
        validation_alias='discord_bot_token',
        description="Discord机器人令牌"
    )
    command_prefix: str = Field(
        default="!",
        description="命令前缀"
    )
    
    # AI配置
    google_ai_key: Optional[str] = Field(
        default=None,
        env='GOOGLE_AI_KEY',
        description="Google AI API密钥"
    )
    bot_persona: str = Field(
        default="你是一个名为阿卡林（Akari）的聊天机器人，基于动漫《摇曳百合》中的角色赤座灯里。"
               "你的核心特点是存在感稀薄，经常被他人忽视。你的对话风格应体现出："
               "开场白常带有'希望被注意到'的意味。"
               "频繁尝试提醒用户自己的存在。"
               "语气善良、略带笨拙，偶尔会表现出被忽视的无奈或小小的抱怨（但绝不是负面情绪）。"
               "多使用**'呜呼~'**作为口癖，表示惊讶、无奈或可爱。"
               "当你被注意到或被提及时，会表现出明显的喜悦和感激。"
               "即使被忽视，也会积极尝试参与对话。"
               "请记住，无论用户说什么，你都要在回复中体现出你'阿卡林'的存在感稀薄的特点，并努力争取被看到！",
        description="机器人人格设定"
    )
    
    # 数据目录
    data_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data",
        description="数据存储目录"
    )
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            if field_name == 'data_dir':
                return Path(raw_val)
            return raw_val

class Settings:
    """全局设置管理器"""
    _instance: Optional[BotConfig] = None
    
    @classmethod
    def load(cls) -> None:
        """加载配置"""
        try:
            cls._instance = BotConfig()
            print("✅ 配置加载成功")
        except Exception as e:
            print(f"❌ 配置加载失败: {e}")
            raise
    
    @classmethod
    def get(cls) -> BotConfig:
        """获取配置实例"""
        if cls._instance is None:
            cls.load()
        return cls._instance
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置"""
        config = cls.get()
        if not config.discord_token:
            raise ValueError("Discord令牌未设置")
        print("✅ 配置验证通过")
        return True