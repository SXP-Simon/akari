from discord.ext import commands
from .general import *
from .utility import *

def command(**kwargs):
    def decorator(func):
        @commands.command(**kwargs)
        async def wrapper(self, ctx, *args, **kw):
            return await func(self, ctx, *args, **kw)
        return wrapper
    return decorator

def group(**kwargs):
    def decorator(func):
        @commands.group(**kwargs)
        async def wrapper(self, ctx, *args, **kw):
            return await func(self, ctx, *args, **kw)
        return wrapper
    return decorator

__all__ = [
    'command',
    'group',
    # General commands
    'GeneralCommands',
    # Utility commands
    'UtilityCommands'
] 