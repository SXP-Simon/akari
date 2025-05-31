import asyncio
from akari.config.settings import Settings
import google.generativeai as genai
from akari.bot.commands import command

def setup(bot):
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
                await ctx.reply(response.text)
            except Exception as e:
                await ctx.reply(f"Gemini插件出错: {str(e)}") 