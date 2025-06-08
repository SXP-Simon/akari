import asyncio
from akari.config.settings import Settings
import google.generativeai as genai
from akari.bot.commands import command
from akari.bot.utils import EmbedBuilder

async def setup(bot):
    """插件加载入口"""
    genai.configure(api_key=Settings.GOOGLE_AI_KEY)
    ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    @bot.register_command
    @command(name="askai", description="向Gemini AI提问（插件版）")
    async def askai(ctx, *, question: str):
        async with ctx.typing():
            try:
                full_prompt = f"{Settings.BOT_PERSONA}\n用户: {question}"
                response = await asyncio.to_thread(
                    ai_model.generate_content,
                    full_prompt
                )
                
                # 创建美观的Embed而不是直接发送文本
                embed = EmbedBuilder.create(
                    title="🤖 AI回复",
                    color_key="special"
                )
                embed.set_author(
                    name=bot.user.name, 
                    icon_url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
                )
                
                # 处理AI回复，检查是否过长
                ai_response = response.text
                if len(ai_response) > 4000:  # Discord embed描述上限
                    # 截断过长的回复并提示
                    ai_response = ai_response[:3900] + "...\n(回复过长，已截断部分内容)"
                
                # 添加用户提问信息
                embed.add_field(
                    name="📝 您的问题", 
                    value=question[:1000] + ("..." if len(question) > 1000 else ""),
                    inline=False
                )
                
                # 设置AI回复内容
                embed.description = ai_response
                embed.set_footer(text=f"回复给: {ctx.author.display_name}")
                
                # 发送响应
                await ctx.reply(embed=embed)
                
            except Exception as e:
                error_embed = EmbedBuilder.error(
                    title="AI响应出错",
                    description=f"处理您的请求时出现问题: ```{str(e)}```"
                )
                await ctx.reply(embed=error_embed) 