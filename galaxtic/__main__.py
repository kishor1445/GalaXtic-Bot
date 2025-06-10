import asyncio
import discord
from discord.ext.commands import when_mentioned_or
from galaxtic import settings, logger
from galaxtic.bot import GalaxticBot


async def main():
    async with GalaxticBot(command_prefix=when_mentioned_or("!"), activity=discord.Activity(type=discord.ActivityType.listening, name="Void")) as bot:
        await bot.start(settings.DISCORD.BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
