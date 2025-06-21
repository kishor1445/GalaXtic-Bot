import discord
from discord import app_commands
from discord.ext.commands import Cog
from galaxtic.db import get_db
from galaxtic import settings, logger
from surrealdb import RecordID


class Media(Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="set_media_channel", description="Set the media channel for the server."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def set_media_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild

        db = get_db()
        is_exists = await db.select(RecordID("guilds", guild.id))
        if not is_exists:
            await db.create(RecordID("guilds", guild.id), {"media_channel_id": channel.id})
            logger.info(f"Created guild data for {guild.name} with media channel {channel.name}")
        else:
            logger.info(f"Updated media channel for {guild.name} to {channel.name}")
            await db.merge(
                "guilds:" + str(guild.id),
                {
                    "media_channel_id": channel.id,
                }
            )
        await interaction.response.send_message(
            f"Media channel set to {channel.mention}.", ephemeral=True
        )

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        
        logger.info(f"Checking message in {message.channel.name} for media content: {message.content}")
        if await self.is_media_channel(message.channel):
            logger.info(f"Message in {message.channel.name} is in a media channel.")
            platform = self.is_media_url(message.content) or "Unknown"
            if platform == "Unknown":
                logger.info(f"Message in {message.channel.name} does not contain a recognized media URL.")
                return


            webhooks = await message.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="Galaxtic")
            if not webhook:
                logger.info(f"Creating a new webhook for {message.channel.name}.")
                webhook = await message.channel.create_webhook(name="Galaxtic")
            else:
                logger.info(f"Using existing webhook for {message.channel.name}.")

            fixed_url = self.fix_url(message.content, platform)
            await webhook.send(
                f"[{platform}]({fixed_url})",
                username=message.author.name,
                avatar_url=message.author.display_avatar.url,
            )
            await message.delete()
            logger.info(f"Sent media URL to webhook and deleted original message in {message.channel.name}.")

    def fix_url(self, url: str, platform: str) -> str:
        logger.info(f"Fixing URL for platform {platform}: {url}")
        if platform == "Instagram":
            return url.replace("instagram.com", "ddinstagram.com")

    def is_media_url(self, url: str) -> bool:
        media_platforms = {
            "instagram.com": "Instagram",
            "twitter.com": "Twitter",
            "tiktok.com": "TikTok",
        }
        for platform, name in media_platforms.items():
            if platform in url:
                logger.info(f"Detected media URL: {url} from platform {name}")
                return name
        return None

    async def is_media_channel(self, channel: discord.TextChannel) -> bool:
        db = get_db()
        logger.info(f"Checking if {channel.name} is a media channel.")
        _id = RecordID("guilds", channel.guild.id)
        print(_id)
        result = await db.select(_id)
        print(result)
        if not result:
            logger.info(f"No guild data found for {channel.guild.name}.")
            return False
        
        logger.info(f"Found media channel ID {result.get('media_channel_id')} for guild {channel.guild.name}.")
        return result.get("media_channel_id") == channel.id
    
    def cog_load(self):
        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id) if test_guild_id else None
            self.bot.tree.add_command(self.set_media_channel, guild=test_guild)


async def setup(bot):
    await bot.add_cog(Media(bot))
