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

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, cog_names: str | None = None):
        cog_names = cog_names.split(",") if cog_names else None
        if cog_names is None:
            n_cogs = 0
            # reload all cogs
            for cog in self.bot.cogs:
                try:
                    await self.bot.reload_extension(f"galaxtic.cogs.{cog}")
                    n_cogs += 1
                except Exception as e:
                    await ctx.send(f"❌ Failed to reload cog `{cog}`: {e}")
                    continue
            await ctx.send(f"✅ Reloaded **{n_cogs}** cogs.")
        else:
            n_cogs = 0
            for cog_name in cog_names:
                try:
                    await self.bot.reload_extension(f"galaxtic.cogs.{cog_name}")
                    n_cogs += 1
                except Exception as e:
                    await ctx.send(f"❌ Failed to reload cog `{cog_name}`: {e}")
                    continue
            await ctx.send(f"✅ Reloaded **{n_cogs}** cogs: {', '.join(cog_names)}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
