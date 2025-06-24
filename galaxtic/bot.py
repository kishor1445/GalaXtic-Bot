import os
from discord.ext.commands import Bot
from galaxtic import logger, settings
from galaxtic.db import setup_database, get_db
import discord
from together import Together
from seafileapi import Repo
from surrealdb import RecordID


class GalaxticBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, intents=discord.Intents.all(), **kwargs)
        self.together_client = Together(api_key=settings.AI.TOGETHER_API_KEY)
        self.seafile_client = Repo(
            token=settings.SEAFILE.REPO_API_TOKEN,
            server_url=settings.SEAFILE.SERVER_URL,
        )
        self.seafile_client.auth()

    async def setup_hook(self):
        logger.info("Setting up database...")
        await setup_database()
        logger.info("Database setup complete")
        logger.info("Setting up extensions...")
        ext = [
            f"galaxtic.cogs.{file[:-3]}"
            for file in os.listdir("galaxtic/cogs")
            if file.endswith(".py") and not file.startswith("__")
        ]
        for cog in ext:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}")
        logger.info("Extensions loaded")

        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id)
            slash_commands = await self.tree.sync(guild=test_guild)
            logger.info(
                f"Synced {len(slash_commands)} slash commands to test guild {test_guild_id}"
            )
        else:
            slash_commands = await self.tree.sync()
            logger.info(f"Synced {len(slash_commands)} global slash commands")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")
        logger.info(f"Synced slash commands: {self.tree.get_commands()}")
        db = get_db()
        bot_info = await db.select("bot_info")
        if not bot_info:
            await db.create(
                RecordID("bot_info", self.user.id),
                {
                    "number_of_guilds": len(self.guilds),
                },
            )
        else:
            new_info = {
                "number_of_guilds": len(self.guilds),
            }
            if bot_info != new_info:
                await db.merge(RecordID("bot_info", self.user.id), new_info)
