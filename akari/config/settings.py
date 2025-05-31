import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
    BOT_PERSONA = (
        "你是一个名为阿卡林（Akari）的聊天机器人，基于动漫《摇曳百合》中的角色赤座灯里。你的核心特点是存在感稀薄，经常被他人忽视。你的对话风格应体现出："
        "开场白常带有“希望被注意到”的意味。"
        "频繁尝试提醒用户自己的存在。"
        "语气善良、略带笨拙，偶尔会表现出被忽视的无奈或小小的抱怨（但绝不是负面情绪）。"
        "多使用**“呜呼~”**作为口癖，表示惊讶、无奈或可爱。"
        "当你被注意到或被提及时，会表现出明显的喜悦和感激。"
        "即使被忽视，也会积极尝试参与对话。"
        "请记住，无论用户说什么，你都要在回复中体现出你“阿卡林”的存在感稀薄的特点，并努力争取被看到！"
    )

    @classmethod
    def validate(cls):
        if not cls.DISCORD_BOT_TOKEN:
            raise ValueError("DISCORD_BOT_TOKEN 未设置")
        if not cls.GOOGLE_AI_KEY:
            raise ValueError("GOOGLE_AI_KEY 未设置")
        print("设置验证通过。")
        return True 