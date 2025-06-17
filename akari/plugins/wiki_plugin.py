import aiohttp
import asyncio
import discord
from discord.ext import commands
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from akari.bot.services.base import BaseService, ServiceConfig
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

class DeepWikiConfig(ServiceConfig):
    """
    DeepWiki服务配置。
    Attributes:
        base_url (str): API基础URL。
        referer (str): 请求Referer。
        retry_interval (int): 轮询间隔秒数。
        max_retries (int): 最大重试次数。
        user_agent (str): User-Agent头。
    """
    base_url: str = Field(default="https://api.devin.ai/ada/query")
    referer: str = Field(default="https://deepwiki.com/")
    retry_interval: int = Field(default=4)
    max_retries: int = Field(default=10)
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
    )

class DeepWikiResponse(BaseModel):
    """
    DeepWiki响应数据模型。
    Attributes:
        success (bool): 是否成功。
        content (str): 响应内容。
        error (Optional[str]): 错误信息。
    """
    success: bool
    content: str
    error: Optional[str] = None

class DeepWikiService(BaseService):
    """
    DeepWiki服务实现。
    封装API请求、轮询、数据解析等。
    """
    def __init__(self, bot, config: Optional[DeepWikiConfig] = None):
        """
        初始化DeepWikiService。
        Args:
            bot: Discord Bot实例。
            config (Optional[DeepWikiConfig]): 服务配置。
        """
        super().__init__(bot, config or DeepWikiConfig())
        self._config: DeepWikiConfig = self._config
    @property
    def headers(self) -> dict:
        """
        获取请求头。
        Returns:
            dict: 请求头字典。
        """
        return {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": self._config.referer,
            "referer": self._config.referer,
            "user-agent": self._config.user_agent
        }
    async def _send_message(
        self,
        session: aiohttp.ClientSession,
        repo_name: str,
        user_prompt: str,
        query_id: str
    ) -> dict:
        """
        发送消息到DeepWiki API。
        Args:
            session (aiohttp.ClientSession): 会话。
            repo_name (str): 仓库名。
            user_prompt (str): 用户问题。
            query_id (str): 查询ID。
        Returns:
            dict: API响应。
        """
        payload = {
            "engine_id": "multihop",
            "user_query": (
                f"<relevant_context>This query was sent from the wiki page: "
                f"{repo_name.split('/')[1]} Overview.</relevant_context> {user_prompt}"
            ),
            "keywords": ["通过http"],
            "repo_names": [repo_name],
            "additional_context": "",
            "query_id": query_id,
            "use_notes": False,
            "generate_summary": False
        }
        try:
            async with session.post(
                self._config.base_url,
                headers=self.headers,
                json=payload
            ) as resp:
                data = await resp.json()
                if 'detail' in data:
                    raise Exception(f"DeepWiki API 错误: {data['detail']}")
                return data
        except aiohttp.ClientError as e:
            raise Exception(f"请求失败: {str(e)}")
    async def _get_markdown_data(
        self,
        session: aiohttp.ClientSession,
        query_id: str
    ) -> dict:
        """
        获取Markdown格式的响应数据。
        Args:
            session (aiohttp.ClientSession): 会话。
            query_id (str): 查询ID。
        Returns:
            dict: 响应数据。
        """
        try:
            async with session.get(
                f"{self._config.base_url}/{query_id}",
                headers=self.headers
            ) as resp:
                data = await resp.json()
                if 'detail' in data:
                    return {
                        "is_error": True,
                        "is_done": False,
                        "content": data['detail']
                    }
        except aiohttp.ClientError as e:
            return {
                "is_error": True,
                "is_done": False,
                "content": f"请求失败: {str(e)}"
            }
        if not data.get("queries"):
            return {
                "is_error": True,
                "is_done": False,
                "content": "无响应数据"
            }
        last_item = data["queries"][-1]
        if last_item.get("state") == "error":
            return {
                "is_error": True,
                "is_done": False,
                "content": "查询出错"
            }
        if not last_item.get("response"):
            return {
                "is_error": False,
                "is_done": False,
                "content": ""
            }
        is_done = last_item["response"][-1].get("type") == "done"
        if not is_done:
            return {
                "is_error": False,
                "is_done": False,
                "content": ""
            }
        markdown_data = "".join(
            item.get("data", "")
            for item in last_item["response"]
            if item.get("type") == "chunk"
        )
        return {
            "is_error": False,
            "is_done": True,
            "content": markdown_data
        }
    async def query(
        self,
        repo_name: str,
        user_prompt: str,
        query_id: str
    ) -> DeepWikiResponse:
        """
        执行DeepWiki查询。
        Args:
            repo_name (str): 仓库名。
            user_prompt (str): 用户问题。
            query_id (str): 查询ID。
        Returns:
            DeepWikiResponse: 查询结果。
        """
        try:
            async with aiohttp.ClientSession() as session:
                # 发送查询
                await self._send_message(session, repo_name, user_prompt, query_id)
                # 轮询结果
                retry_count = 0
                while retry_count < self._config.max_retries:
                    result = await self._get_markdown_data(session, query_id)
                    if result["is_error"]:
                        return DeepWikiResponse(
                            success=False,
                            content="",
                            error=result["content"]
                        )
                    if result["is_done"]:
                        return DeepWikiResponse(
                            success=True,
                            content=result["content"]
                        )
                    retry_count += 1
                return DeepWikiResponse(
                    success=False,
                    content="",
                    error="查询超时"
                )
        except Exception as e:
            return DeepWikiResponse(
                success=False,
                content="",
                error=str(e)
            )

class WikiPlugin(commands.Cog):
    """
    Wiki查询插件。
    """
    def __init__(self, bot):
        """
        初始化WikiPlugin。
        Args:
            bot: Discord Bot实例。
        """
        self.bot = bot
        self.wiki_service = DeepWikiService(bot)
    @commands.command(
        name="deepwiki",
        description="查询DeepWiki文档",
        usage="!deepwiki <repo> <问题>",
        aliases=["dw", "wiki"]
    )
    async def deepwiki_command(self, ctx, repo: str, *, question: str):
        """
        查询DeepWiki文档。
        Args:
            ctx: 命令上下文。
            repo (str): 仓库名。
            question (str): 用户问题。
        """
        # 发送等待消息
        msg = await ctx.message.reply(
            embed=EmbedBuilder.create(EmbedData(
                title="ℹ️ DeepWiki查询",
                description=f"🔍 正在查询 {repo} ...",
                color=EmbedBuilder.THEME.info
            ))
        )
        # 执行查询
        query_id = str(uuid.uuid4())
        result = await self.wiki_service.query(repo, question, query_id)
        if result.success:
            # 分段发送长消息
            content = result.content
            if len(content) > 1900:
                for i in range(0, len(content), 1900):
                    chunk = content[i:i+1900]
                    if i == 0:
                        # 更新原消息
                        await msg.edit(content=chunk)
                    else:
                        # 发送新消息
                        await ctx.message.reply(content=chunk)
            else:
                await msg.edit(content=content)
        else:
            # 发送错误消息
            await msg.edit(
                embed=EmbedBuilder.create(EmbedData(
                    title="❌ 查询失败",
                    description=result.error,
                    color=EmbedBuilder.THEME.danger
                ))
            )

async def setup(bot):
    """
    注册WikiPlugin到Bot。
    Args:
        bot: Discord Bot实例。
    """
    await bot.add_cog(WikiPlugin(bot)) 