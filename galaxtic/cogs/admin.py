import discord
from discord.ext import commands
from discord import app_commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="add_roles", description="Add multiple roles to the server (admin only)"
    )
    @app_commands.describe(roles="Comma-separated list of role names to add")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_roles(self, interaction: discord.Interaction, roles: str):
        role_names = [role.strip() for role in roles.split(",") if role.strip()]
        created = []
        skipped = []
        for name in role_names:
            # Check if role already exists
            if discord.utils.get(interaction.guild.roles, name=name):
                skipped.append(name)
                continue
            try:
                await interaction.guild.create_role(name=name)
                created.append(name)
            except Exception as e:
                skipped.append(f"{name} (error: {e})")
        msg = ""
        if created:
            msg += f"✅ Created roles: {', '.join(created)}\n"
        if skipped:
            msg += f"⚠️ Skipped (already exists or error): {', '.join(skipped)}"
        if not msg:
            msg = "No roles were created."
        await interaction.response.send_message(msg, ephemeral=True)

    @commands.command(
        name="add_roles",
        help="Add multiple roles to the server (admin only). Usage: !add_roles role1, role2, role3",
    )
    @commands.has_permissions(administrator=True)
    async def add_roles_prefix(self, ctx, *, roles: str):
        role_names = [role.strip() for role in roles.split(",") if role.strip()]
        created = []
        skipped = []
        for name in role_names:
            if discord.utils.get(ctx.guild.roles, name=name):
                skipped.append(name)
                continue
            try:
                await ctx.guild.create_role(name=name)
                created.append(name)
            except Exception as e:
                skipped.append(f"{name} (error: {e})")
        msg = ""
        if created:
            msg += f"✅ Created roles: {', '.join(created)}\n"
        if skipped:
            msg += f"⚠️ Skipped (already exists or error): {', '.join(skipped)}"
        if not msg:
            msg = "No roles were created."
        await ctx.send(msg)


async def setup(bot):
    await bot.add_cog(Admin(bot))
