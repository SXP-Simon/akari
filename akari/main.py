import discord
from akari.config.settings import Settings
from akari.bot.bot import MyBot

def main():
    Settings.validate()
    intents = discord.Intents.default()
    intents.message_content = True
    bot = MyBot(command_prefix="!", intents=intents)
    bot.run(Settings.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
