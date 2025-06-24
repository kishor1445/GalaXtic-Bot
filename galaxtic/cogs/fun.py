from typing import NamedTuple
import discord
from discord.ext import commands
from discord import app_commands
from galaxtic.db import get_db
from galaxtic import settings, logger
import ast
import re
import random
import asyncio


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._verify_task = None
        self.count_cache = []

    @commands.command(name="modi_say", aliases=["msay"])
    @commands.has_role("Modi")
    async def modi_say(self, ctx: commands.Context, *, message: str):
        """Make Modi say something."""
        await ctx.message.delete()
        webhooks = await ctx.channel.webhooks()
        galaxtic_webhook = discord.utils.get(webhooks, name="Galaxtic")
        if not galaxtic_webhook:
            galaxtic_webhook = await ctx.channel.create_webhook(name="Galaxtic")
        await galaxtic_webhook.send(
            content=message,
            username="Modi",
            avatar_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Official_Photograph_of_Prime_Minister_Narendra_Modi_Portrait.png/320px-Official_Photograph_of_Prime_Minister_Narendra_Modi_Portrait.png",
        )

    @modi_say.error
    async def modi_say_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRole):
            await ctx.reply(
                "You do not have permission to use this command.",
            )
        else:
            logger.error(f"Error in modi_say command: {error}")
            await ctx.send("An error occurred while processing your request.")

    @app_commands.command(
        name="set_count_channel",
        description="Set a channel for counting numbers (admin only)",
    )
    @app_commands.describe(channel="Select the channel to use for counting")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_count_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        db = get_db()
        self.count_cache.append(channel.id)
        # Upsert the count channel for this guild
        await db.query(
            f"UPDATE count_channel SET channel_id='{channel.id}' WHERE guild_id='{interaction.guild.id}';"
            f"IF $result = NONE THEN CREATE count_channel SET guild_id='{interaction.guild.id}', channel_id='{channel.id}'; END;"
        )
        await interaction.response.send_message(
            f"Counting channel set to {channel.mention}.", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or not message.guild
            or message.channel.id not in self.count_cache
        ):
            return None

        db = get_db()
        guild_id = str(message.guild.id)
        # Get the count channel info for this guild
        result = await db.query(
            f"SELECT * FROM count_channel WHERE guild_id='{guild_id}' LIMIT 1"
        )
        count_info = result[0]
        # Get or initialize count state
        current_count = count_info.get("current_count", 0)
        highest_count = count_info.get("highest_count", 0)
        last_user = count_info.get("last_user")
        # Check if the message is a valid math expression (no letters)
        expr = message.content.strip().replace("\\", "").replace("^", "**")
        if re.search(r"[a-zA-Z]", expr):
            return  # Ignore messages with any letters

        def safe_eval(expr):
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expr):
                return None
            try:
                node = ast.parse(expr, mode="eval")
                for n in ast.walk(node):
                    if not isinstance(
                        n,
                        (
                            ast.Expression,
                            ast.BinOp,
                            ast.UnaryOp,
                            ast.Constant,
                            ast.operator,
                            ast.unaryop,
                            ast.Load,
                        ),
                    ):
                        return None
                result = eval(compile(node, "<string>", "eval"))
                if isinstance(result, int):
                    return result
                if isinstance(result, float) and result.is_integer():
                    return int(result)
                return None
            except Exception:
                return None

        number = safe_eval(expr)
        if number is None:
            return  # Ignore non-numeric or invalid math expressions
        if number != current_count + 1:
            await message.reply(
                f"❌ Wrong number {message.author.display_name}! The next number should be {current_count + 1}.\n\n Counting has been reset."
            )
            await message.add_reaction("❌")
            await db.query(
                f"UPDATE count_channel SET current_count=0, last_user=NULL WHERE guild_id='{guild_id}'"
            )
            return
        if last_user == str(message.author.id):
            await message.reply("⛔ You can't count twice in a row!")
            await message.add_reaction("❌")
            return
        # Update counts
        new_count = number
        new_high = max(highest_count, new_count)
        await db.query(
            f"UPDATE count_channel SET current_count={new_count}, highest_count={new_high}, last_user='{message.author.id}', last_message_id='{message.id}' WHERE guild_id='{guild_id}'"
        )
        if new_count > highest_count:
            await message.add_reaction("☑️")  # :ballot_box_with_check:
        else:
            await message.add_reaction("✅")

    @app_commands.command(
        name="random_choice",
        description="Pick a random item from a comma-separated list",
    )
    @app_commands.describe(options="Comma-separated list of options")
    async def random_choice(self, interaction: discord.Interaction, options: str):
        items = [item.strip() for item in options.split(",") if item.strip()]
        if not items:
            await interaction.response.send_message(
                "Please provide at least one option.", ephemeral=True
            )
            return
        choice = random.choice(items)
        await interaction.response.send_message(f"🎲 Random choice: **{choice}**")

    async def verify_count_channels(self):
        """Verify all count channels' new messages when bot restarts."""
        await self.bot.wait_until_ready()  # Ensure bot is ready before verification
        db = get_db()
        # Get all count channels
        result = await db.query("SELECT * FROM count_channel")
        logger.info(f"Verifying {len(result)} count channels")
        if not result:
            return
        for count_info in result:
            try:
                channel = self.bot.get_channel(int(count_info["channel_id"]))
                if not channel:
                    continue
                last_message_id = count_info.get("last_message_id")
                logger.info(
                    f"Verifying channel {channel.name} with last message ID {last_message_id}"
                )
                after_message = None
                if last_message_id:
                    try:
                        after_message = await channel.fetch_message(
                            int(last_message_id)
                        )
                        logger.info(
                            f"Found after message: {after_message.content} for channel {channel.name}"
                        )
                    except Exception:
                        after_message = None
                # Get all messages after last_message_id (if any)
                messages = []
                if after_message:
                    async for msg in channel.history(
                        after=after_message, oldest_first=True
                    ):
                        messages.append(msg)
                        logger.info(
                            f"Found message: {msg.content} for channel {channel.name}"
                        )
                else:
                    # If no last_message_id, just check the latest message
                    async for msg in channel.history(limit=1, oldest_first=False):
                        messages.append(msg)
                        logger.info(
                            f"No last message ID found, found message: {msg.content} for channel {channel.name}"
                        )
                # Get or initialize count state
                current_count = count_info.get("current_count", 0)
                highest_count = count_info.get("highest_count", 0)
                last_user = count_info.get("last_user")
                for message in messages:
                    if message.author.bot:
                        continue
                    expr = message.content.strip().replace("\\", "").replace("^", "**")
                    if re.search(r"[a-zA-Z]", expr):
                        continue

                    def safe_eval(expr):
                        allowed = set("0123456789+-*/(). ")
                        if not all(c in allowed for c in expr):
                            return None
                        try:
                            node = ast.parse(expr, mode="eval")
                            for n in ast.walk(node):
                                if not isinstance(
                                    n,
                                    (
                                        ast.Expression,
                                        ast.BinOp,
                                        ast.UnaryOp,
                                        ast.Constant,
                                        ast.operator,
                                        ast.unaryop,
                                        ast.Load,
                                    ),
                                ):
                                    return None
                            result = eval(compile(node, "<string>", "eval"))
                            if isinstance(result, int):
                                return result
                            if isinstance(result, float) and result.is_integer():
                                return int(result)
                            return None
                        except Exception:
                            return None

                    number = safe_eval(expr)
                    logger.info(
                        f"Evaluated expression {expr} to {number} for channel {channel.name}"
                    )
                    if number is None:
                        logger.info(
                            f"Expression {expr} is not a valid number for channel {channel.name}"
                        )
                        continue
                    if number != current_count + 1:
                        # Reset count if wrong
                        await db.query(
                            f"UPDATE count_channel SET current_count=0, last_user=NULL WHERE guild_id='{message.guild.id}'"
                        )
                        current_count = 0
                        last_user = None
                        logger.info(f"Reset count for channel {channel.name} to 0")
                        try:
                            await message.add_reaction("❌")
                        except Exception:
                            pass
                        continue
                    if last_user == str(message.author.id):
                        logger.info(
                            f"Last user {last_user} is the same as the current user {message.author.id} for channel {channel.name}"
                        )
                        try:
                            await message.add_reaction("❌")
                        except Exception:
                            pass
                        continue
                    # Update counts
                    new_high = max(highest_count, number)
                    await db.query(
                        f"UPDATE count_channel SET current_count={number}, highest_count={new_high}, last_user='{message.author.id}', last_message_id='{message.id}' WHERE guild_id='{message.guild.id}'"
                    )
                    logger.info(f"Updated count for channel {channel.name} to {number}")
                    try:
                        if number > highest_count:
                            await message.add_reaction("☑️")
                        else:
                            await message.add_reaction("✅")
                    except Exception:
                        pass
                    current_count = number
                    highest_count = new_high
                    last_user = str(message.author.id)
            except Exception as e:
                print(f"Error verifying count channel: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Start the verification task when the bot is ready
        if self._verify_task is None:
            self._verify_task = asyncio.create_task(self.verify_count_channels())

    async def cog_unload(self):
        # Clean up the verification task if it's running
        if self._verify_task is not None:
            self._verify_task.cancel()
            try:
                await self._verify_task
            except asyncio.CancelledError:
                pass

    async def cog_load(self):
        db = get_db()
        # Load count channels into cache
        result = await db.query("SELECT channel_id FROM count_channel")
        self.count_cache = [
            int(row["channel_id"]) for row in result if "channel_id" in row
        ]
        logger.info(f"Loaded {len(self.count_cache)} count channels into cache")

        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id) if test_guild_id else None
            self.bot.tree.add_command(self.random_choice, guild=test_guild)
            self.bot.tree.add_command(self.set_count_channel, guild=test_guild)


async def setup(bot):
    await bot.add_cog(Fun(bot))
