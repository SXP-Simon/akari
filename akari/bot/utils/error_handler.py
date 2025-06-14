import functools
import traceback
import logging
import sys
from typing import Optional, Callable, Any
from discord.ext import commands
from akari.bot.utils.embeds import EmbedBuilder, EmbedData

logger = logging.getLogger("akari")

def format_error(error: Exception, include_traceback: bool = False) -> str:
    """
    格式化错误信息。
    Args:
        error (Exception): 异常对象。
        include_traceback (bool): 是否包含堆栈信息。
    Returns:
        str: 格式化后的错误信息。
    """
    error_type = type(error).__name__
    error_msg = str(error)
    if include_traceback:
        error_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        return f"{error_type}: {error_msg}\n\n堆栈跟踪:\n{error_trace}"
    return f"{error_type}: {error_msg}"

def debug_command(func: Callable) -> Callable:
    """
    命令调试装饰器。
    用于包装命令函数，提供详细的错误信息和日志记录。
    用法示例:
        @commands.command()
        @debug_command
        async def my_command(self, ctx):
            ...
    Args:
        func (Callable): 命令处理函数。
    Returns:
        Callable: 包装后的函数。
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # 获取上下文对象
            ctx = next((arg for arg in args if isinstance(arg, commands.Context)), None)
            if not ctx:
                return await func(*args, **kwargs)
            
            # 记录命令调用
            logger.info(f"执行命令: {ctx.command} (用户: {ctx.author}, 服务器: {ctx.guild})")
            logger.debug(f"命令参数: args={args}, kwargs={kwargs}")
            
            # 执行命令
            return await func(*args, **kwargs)
            
        except Exception as e:
            # 获取详细的错误信息
            error_msg = format_error(e, include_traceback=True)
            
            # 记录错误到终端和日志文件
            logger.error("命令执行错误:")
            logger.error(error_msg)
            
            # 如果有上下文对象，发送错误消息到Discord
            if ctx:
                embed_data = EmbedData(
                    title="❌ 命令执行错误",
                    description=f"执行命令时发生错误:\n```py\n{format_error(e)}```",
                    color=EmbedBuilder.THEME.danger,
                    fields=[
                        {
                            "name": "命令",
                            "value": f"`{ctx.command}`",
                            "inline": True
                        },
                        {
                            "name": "参数",
                            "value": f"`{ctx.args[2:] if len(ctx.args) > 2 else 'None'}`",
                            "inline": True
                        }
                    ]
                )
                
                # 在调试模式下添加堆栈跟踪
                if logger.level <= logging.DEBUG:
                    error_trace = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                    embed_data.fields.append({
                        "name": "错误堆栈",
                        "value": f"```py\n{error_trace[:1000]}```",
                        "inline": False
                    })
                
                await ctx.send(embed=EmbedBuilder.create(embed_data))
            
            # 重新抛出异常以便上层处理
            raise
            
    return wrapper

class ErrorHandler:
    """
    全局错误处理器。
    提供统一的命令错误处理逻辑。
    """
    
    @staticmethod
    async def on_command_error(ctx: commands.Context, error: Exception) -> None:
        """
        处理命令错误。
        Args:
            ctx (commands.Context): 命令上下文。
            error (Exception): 发生的异常。
        """
        # 忽略命令未找到的错误
        if isinstance(error, commands.CommandNotFound):
            return
            
        # 处理权限错误
        if isinstance(error, commands.MissingPermissions):
            error_msg = "您没有执行此命令的权限"
            logger.warning(f"权限错误: {ctx.author} 尝试执行 {ctx.command} - {error_msg}")
            
            embed = EmbedBuilder.create(EmbedData(
                title="⚠️ 权限不足",
                description=error_msg,
                color=EmbedBuilder.THEME.warning
            ))
            await ctx.send(embed=embed)
            return
            
        # 处理参数错误
        if isinstance(error, commands.MissingRequiredArgument):
            error_msg = f"缺少必要参数: {error.param.name}"
            logger.warning(f"参数错误: {ctx.command} - {error_msg}")
            
            embed = EmbedBuilder.create(EmbedData(
                title="⚠️ 参数缺失",
                description=error_msg,
                color=EmbedBuilder.THEME.warning,
                fields=[
                    {
                        "name": "正确用法",
                        "value": f"`{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                        "inline": False
                    }
                ]
            ))
            await ctx.send(embed=embed)
            return
            
        # 处理其他错误
        error_msg = format_error(error, include_traceback=True)
        
        # 记录错误到终端和日志文件
        logger.error("未处理的命令错误:")
        logger.error(error_msg)
        
        # 发送错误消息到Discord
        embed_data = EmbedData(
            title="❌ 命令执行错误",
            description=f"执行命令时发生未处理的错误:\n```py\n{format_error(error)}```",
            color=EmbedBuilder.THEME.danger,
            fields=[
                {
                    "name": "命令信息",
                    "value": f"命令: `{ctx.command}`\n用户: {ctx.author}\n频道: {ctx.channel}",
                    "inline": False
                }
            ]
        )
        
        # 在调试模式下添加堆栈跟踪
        if logger.level <= logging.DEBUG:
            error_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            embed_data.fields.append({
                "name": "错误堆栈",
                "value": f"```py\n{error_trace[:1000]}```",
                "inline": False
            })
        
        await ctx.send(embed=EmbedBuilder.create(embed_data)) 