from discord.ext import commands

def command(**kwargs):
    def decorator(func):
        return commands.command(**kwargs)(func)
    return decorator

def group(**kwargs):
    def decorator(func):
        return commands.group(**kwargs)(func)
    return decorator 