import discord
from discord.ext import commands


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_commands(self, ctx: commands.Context):
        """Sync slash commands to the current guild only."""
        if ctx.guild is None:
            await ctx.send("❌ This command must be used in a server (guild).")
            return

        guild = discord.Object(id=ctx.guild.id)
        synced = await self.bot.tree.sync(guild=guild)
        await ctx.send(
            f"✅ Synced `{len(synced)}` slash command(s) to **{ctx.guild.name}**."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
