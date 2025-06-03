import asyncio
from discord.ext.commands import when_mentioned_or
from galaxtic import settings, logger
from galaxtic.bot import GalaxticBot
import discord

async def run_bot():
    while True:
        try:
            async with GalaxticBot(command_prefix=when_mentioned_or("!")) as bot:
                await bot.start(settings.DISCORD.BOT_TOKEN)
        except (discord.errors.ConnectionClosed, discord.errors.ConnectionClosedError, discord.GatewayNotFound, discord.ConnectionClosed) as e:
            logger.error(f"Discord connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot stopped by user.")
