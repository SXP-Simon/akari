import aiohttp
import asyncio
import discord
from discord.ext import commands
import uuid

# logger 用 print 代替
class DeepWikiClient:
    def __init__(
        self,
        retry_interval: int = 4,
        max_retries: int = 10,
    ):
        self.base_url = "https://api.devin.ai/ada/query"
        self.referer = "https://deepwiki.com/"
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": self.referer,
            "referer": self.referer,
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        }

    async def _send_message(
        self,
        session: aiohttp.ClientSession,
        repo_name: str,
        user_prompt: str,
        query_id: str,
    ):
        payload = {
            "engine_id": "multihop",
            "user_query": f"<relevant_context>This query was sent from the wiki page: {repo_name.split('/')[1]} Overview.</relevant_context> {user_prompt}",
            "keywords": ["通过http"],
            "repo_names": [repo_name],
            "additional_context": "",
            "query_id": query_id,
            "use_notes": False,
            "generate_summary": False,
        }
        print("发送用户提示请求:", payload)
        try:
            async with session.post(
                self.base_url, headers=self.headers, json=payload
            ) as resp:
                resp_json = await resp.json()
                print("API返回内容:", resp_json)
                if 'detail' in resp_json:
                    raise Exception(f"DeepWiki API 错误: {resp_json['detail']}")
                return resp_json
        except aiohttp.ClientError as e:
            print("请求异常:", str(e))
            return {}

    async def _get_markdown_data(self, session: aiohttp.ClientSession, query_id: str):
        try:
            async with session.get(
                f"{self.base_url}/{query_id}", headers=self.headers
            ) as resp:
                data = await resp.json()
                print("查询结果:", data)
                if 'detail' in data:
                    return {"is_error": True, "is_done": False, "content": data['detail']}
        except aiohttp.ClientError as e:
            print("查询异常:", str(e))
            return {"is_error": True, "is_done": False, "content": ""}

        if not data.get("queries"):
            return {"is_error": True, "is_done": False, "content": ""}

        last_item = data["queries"][-1]

        if last_item.get("state") == "error":
            return {"is_error": True, "is_done": False, "content": ""}

        if not last_item.get("response"):
            return {"is_error": False, "is_done": False, "content": ""}

        is_done = last_item["response"][-1].get("type") == "done"
        if not is_done:
            return {"is_error": False, "is_done": False, "content": ""}

        markdown_data = "".join(
            item.get("data", "")
            for item in last_item["response"]
            if item.get("type") == "chunk"
        )

        return {"is_error": False, "is_done": True, "content": markdown_data}

    async def _polling_response(self, session: aiohttp.ClientSession, query_id: str):
        retry_count = 0
        while retry_count < self.max_retries:
            print(f"轮询中（第 {retry_count + 1}/{self.max_retries} 次）...")
            result = await self._get_markdown_data(session, query_id)
            if result["is_error"]:
                raise Exception(f"deepwiki 响应错误: {result.get('content', '')}")
            if result["is_done"]:
                print("已完成响应")
                return result
            await asyncio.sleep(self.retry_interval)
            retry_count += 1
        return {"is_done": False, "content": "", "error": "响应超时"}

    async def query(self, repo_name: str, user_prompt: str, query_id: str):
        print(f"开始查询: repo={repo_name}, prompt={user_prompt}, id={query_id}")
        try:
            async with aiohttp.ClientSession() as session:
                send_result = await self._send_message(
                    session, repo_name, user_prompt, query_id
                )
                if not send_result:
                    raise Exception("发送失败")
                print("消息已发送，开始轮询...")
                response = await self._polling_response(session, query_id)
                if not response.get("is_done"):
                    raise Exception("轮询超时")
                return {
                    "success": True,
                    "chat_results": response.get("content", ""),
                }
        except Exception as e:
            print("异常:", str(e))
            raise Exception("❌ DeepWiki 查询失败: " + str(e))

# Discord 命令实现
dwclient = DeepWikiClient()

class DeepWikiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="deepwiki", aliases=["dw"], help="DeepWiki 查询: !deepwiki <repo> <问题>")
    async def deepwik(self, ctx, repo: str, *, question: str):
        """DeepWiki 查询命令"""
        query_id = str(uuid.uuid4())
        await ctx.send(f"🔍 正在查询 DeepWiki: {repo} ...")
        try:
            result = await dwclient.query(repo, question, query_id)
            if result.get("success"):
                content = result.get("chat_results", "无结果")
                # Discord 消息长度限制
                if len(content) > 1900:
                    for i in range(0, len(content), 1900):
                        await ctx.send(content[i:i+1900])
                else:
                    await ctx.send(content)
            else:
                await ctx.send("❌ 查询失败")
        except Exception as e:
            await ctx.send(str(e))

async def setup(bot):
    await bot.add_cog(DeepWikiCog(bot)) 