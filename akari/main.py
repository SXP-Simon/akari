#!/usr/bin/env python3
"""
akari 备用启动入口。

- 日志系统初始化
- 配置加载与校验
- Discord Bot 启动主流程
- 统一异常处理
"""
import logging
import sys
from pathlib import Path
import discord
from akari.config.settings import Settings
from akari.bot.core.bot import MyBot

def setup_logging() -> logging.Logger:
    """设置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    return logging.getLogger("akari")

def main() -> None:
    """主函数"""
    # 设置日志
    logger = setup_logging()
    logger.info("正在启动 Discord Bot...")
    
    try:
        # 加载并验证配置
        settings = Settings.get()
        Settings.validate()
        
        # 设置意图
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        # 创建并运行bot
        bot = MyBot(intents=intents)
        bot.run(settings.discord_token)
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
