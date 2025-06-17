import asyncio
import logging
import sys
import traceback
import argparse
from akari.bot.core.bot import MyBot
from akari.config.settings import Settings

def setup_logging(debug_mode: bool = False) -> logging.Logger:
    """设置日志记录"""
    logger = logging.getLogger("akari")
    
    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 设置日志级别
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    logger.addHandler(console_handler)
    
    # 添加文件处理器
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # 文件始终记录DEBUG级别
    logger.addHandler(file_handler)
    
    return logger

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Discord Bot')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       default='INFO' if not '--debug' in sys.argv else 'DEBUG',
                       help='设置日志级别')
    return parser.parse_args()

async def main():
    """主函数"""
    # 解析命令行参数
    args = parse_args()
    debug_mode = args.debug
    
    # 设置日志
    logger = setup_logging(debug_mode)
    if debug_mode:
        logger.debug("调试模式已启用")
    
    # 启动机器人
    try:
        settings = Settings.get()
        bot = MyBot(debug_mode=debug_mode, logger=logger)
        
        logger.info("正在启动 Discord Bot...")
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
        await bot.close()
    except Exception as e:
        logger.error(f"启动失败: {e}")
        if debug_mode:
            logger.debug(f"错误堆栈:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")

"""
akari 启动入口。

- 支持命令行参数（debug/log-level）
- 日志系统初始化（控制台+文件）
- 启动 Discord Bot 主流程
- 统一异常处理
""" 