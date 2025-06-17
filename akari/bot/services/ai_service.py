from typing import Optional
from pydantic import BaseModel, Field
import discord
from .base import BaseService, ServiceConfig
from ..utils.embeds import EmbedBuilder
import google.generativeai as genai
from akari.config.settings import Settings
import asyncio

class AIServiceConfig(ServiceConfig):
    """
    AI服务配置。

    Attributes:
        model (str): 使用的AI模型名。
        max_tokens (int): 最大token数。
        temperature (float): 采样温度。
        system_prompt (str): 系统提示词。
    """
    model: str = Field(default="gemini-1.5-flash")
    max_tokens: int = Field(default=1000)
    temperature: float = Field(default=0.7)
    system_prompt: str = Field(
        default="你是一个友好的AI助手，可以帮助用户解答问题。"
    )

class AIResponse(BaseModel):
    """
    AI响应数据模型。

    Attributes:
        content (str): AI回复内容。
        tokens_used (int): 消耗的token数。
        model (str): 使用的模型名。
    """
    content: str
    tokens_used: int
    model: str
    
    class Config:
        arbitrary_types_allowed = True

class AIService(BaseService):
    """
    AI服务实现。
    封装AI对话、配置、响应生成等。
    """
    
    def __init__(self, bot: discord.Client, config: Optional[AIServiceConfig] = None):
        """
        初始化AI服务。
        Args:
            bot (discord.Client): Discord客户端。
            config (Optional[AIServiceConfig]): AI服务配置。
        """
        super().__init__(bot, config or AIServiceConfig())
        self._config: AIServiceConfig = self._config  # Type hint
        settings = Settings.get()
        if not settings.google_ai_key:
            raise ValueError("Google AI API Key not configured")
        genai.configure(api_key=settings.google_ai_key)
        self.ai_model = genai.GenerativeModel(model_name=self._config.model)
        
    @classmethod
    def get_default_config(cls) -> AIServiceConfig:
        """
        获取默认AI服务配置。
        Returns:
            AIServiceConfig: 默认配置实例。
        """
        return AIServiceConfig()
        
    async def generate_response(
        self, 
        message: discord.Message,
        prompt: Optional[str] = None
    ) -> discord.Embed:
        """
        生成AI响应。
        Args:
            message (discord.Message): 用户消息。
            prompt (Optional[str]): 额外提示词。
        Returns:
            discord.Embed: AI回复的Embed消息。
        """
        try:
            persona = Settings.get().bot_persona
            user_prompt = prompt or "你好！"
            full_prompt = f"{persona}\n用户: {user_prompt}"
            response = await asyncio.to_thread(
                self.ai_model.generate_content,
                full_prompt
            )
            ai_response = response.text
            if len(ai_response) > 4000:
                ai_response = ai_response[:3900] + "...\n(回复过长，已截断部分内容)"
            embed = EmbedBuilder.info(
                title="AI回复",
                description=ai_response
            )
            embed.set_footer(text=f"回复给: {message.author.display_name}")
            return embed
        except Exception as e:
            return EmbedBuilder.error(
                title="AI响应失败",
                description=f"生成响应时发生错误: {str(e)}"
            )
            
    async def initialize(self) -> None:
        """
        初始化AI服务。
        可用于API密钥验证等。
        """
        # 这里可以进行API密钥验证等初始化操作
        pass 