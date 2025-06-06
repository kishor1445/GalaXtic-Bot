from discord.ext.commands import Cog, command
from discord import Embed
from galaxtic.bot import GalaxticBot


class Utility(Cog):
    def __init__(self, bot: GalaxticBot):
        self.bot = bot

    @command(name="serverinfo", help="Get information about the server.")
    async def serverinfo(self, ctx):
        guild = ctx.guild

        embed = Embed(
            title=f"Server Info: {guild.name}",
            description=f"ID: {guild.id}\nOwner: {guild.owner}\nMember Count: {guild.member_count}",
            color=self.bot.color,
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)


async def setup(bot: GalaxticBot):
    await bot.add_cog(Utility(bot))
