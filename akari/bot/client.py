import discord
from discord.ext import commands
import logging
import ssl
import certifi
import aiohttp

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 配置SSL上下文
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        self.ssl_context.check_hostname = True
        self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # 配置aiohttp连接器
        self.connector = aiohttp.TCPConnector(
            ssl=self.ssl_context,
            force_close=True,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,
            limit=50
        )
        
        # 使用自定义连接器创建HTTP会话
        self.http.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
    
    async def setup_hook(self) -> None:
        """初始化钩子"""
        # 加载命令模块
        await self.load_extensions()
        
    async def load_extensions(self):
        """加载所有扩展"""
        # ... existing code ... 