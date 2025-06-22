from discord.ext.commands import Cog
from discord import app_commands
from galaxtic.db import get_db
from galaxtic import settings, logger
from surrealdb import RecordID
import discord
from typing import Dict, Tuple, List
from discord.ui import Modal, TextInput
from discord import TextStyle, Colour


def dict_to_embed(data: Dict) -> discord.Embed:
    """Build a discord.Embed from the persisted data structure."""
    embed = discord.Embed()

    if title := data.get("title"):
        embed.title = title

    if desc := data.get("description"):
        embed.description = desc

    if colour := data.get("colour"):
        try:
            embed.colour = Colour(colour)
        except (ValueError, TypeError):
            pass  # keep default

    # Images & thumbnails
    if thumb := data.get("thumbnail_url"):
        embed.set_thumbnail(url=thumb)
    if img := data.get("image_url"):
        embed.set_image(url=img)

    # Author
    if auth_name := data.get("author_name"):
        embed.set_author(
            name=auth_name,
            icon_url=data.get("author_icon_url", ""),
            url=data.get("author_url", ""),
        )

    # Footer
    if footer := data.get("footer_text"):
        embed.set_footer(
            text=footer, icon_url=data.get("footer_icon_url", "")
        )

    # Fields
    for fld in data.get("fields", []):
        embed.add_field(
            name=fld.get("name", ""),
            value=fld.get("value", ""),
            inline=fld.get("inline", False),
        )

    return embed


class EmbedSectionModal(Modal):
    def __init__(
        self,
        section: str,
        name: str,
        current_data: dict,
        db,
        rec,
        chooser_view: "SectionChooserView",
        org_msg,
    ):
        super().__init__(title=f"Edit {section.title()}: {name}")
        self.section = section
        self.embed_name = name
        self.db = db
        self.rec = rec
        self.current = current_data
        self.chooser_view = chooser_view
        self.org_msg = org_msg

        if section == "title":
            self.title_input = TextInput(
                label="Title",
                default=current_data.get("title", ""),
                max_length=256,
                required=False,
            )
            self.add_item(self.title_input)
        elif section == "description":
            self.desc_input = TextInput(
                label="Description",
                style=TextStyle.paragraph,
                default=current_data.get("description", ""),
                max_length=4000,
                required=False,
            )
            self.add_item(self.desc_input)
        elif section == "images":
            self.thumb = TextInput(
                label="Thumbnail URL",
                default=current_data.get("thumbnail_url", ""),
                required=False,
            )
            self.img = TextInput(
                label="Image URL",
                default=current_data.get("image_url", ""),
                required=False,
            )
            self.add_item(self.thumb)
            self.add_item(self.img)
        elif section == "footer":
            self.foot_text = TextInput(
                label="Footer Text",
                default=current_data.get("footer_text", ""),
                max_length=2048,
                required=False,
            )
            self.foot_icon = TextInput(
                label="Footer Icon URL",
                default=current_data.get("footer_icon_url", ""),
                required=False,
            )
            self.add_item(self.foot_text)
            self.add_item(self.foot_icon)
        elif section == "color":
            self.color_input = TextInput(
                label="Color (hex code, e.g. #FF5733)",
                default=current_data.get("color", ""),
                required=False,
            )
            self.add_item(self.color_input)
        elif section == "author":
            self.author_name = TextInput(
                label="Author Name",
                default=current_data.get("author_name", ""),
                required=False,
            )
            self.author_icon = TextInput(
                label="Author Icon URL",
                default=current_data.get("author_icon_url", ""),
                required=False,
            )
            self.author_url = TextInput(
                label="Author URL",
                default=current_data.get("author_url", ""),
                required=False,
            )
            self.add_item(self.author_name)
            self.add_item(self.author_icon)
            self.add_item(self.author_url)
        elif section == "fields":
            self.field_inputs: List[Tuple[TextInput, TextInput]] = []
            existing_fields = current_data.get("fields", [])
            for i in range(1):
                existing = existing_fields[i] if i < len(existing_fields) else {}
                n = TextInput(
                    label=f"Field {i+1} Name",
                    default=existing.get("name", ""),
                    required=False,
                )
                v = TextInput(
                    label=f"Field {i+1} Value",
                    style=TextStyle.paragraph,
                    default=existing.get("value", ""),
                    required=False,
                )
                self.field_inputs.append((n, v))
                self.add_item(n)
                self.add_item(v)

    async def on_submit(self, interaction):
        await interaction.response.defer()
        
        if self.section == "title":
            value = self.title_input.value.strip()
            if value:
                self.current["title"] = value
            else:
                self.current.pop("title", None)

        elif self.section == "description":
            value = self.desc_input.value.strip()
            if value:
                self.current["description"] = value
            else:
                self.current.pop("description", None)

        elif self.section == "images":
            thumb_val = self.thumb.value.strip()
            img_val = self.img.value.strip()
            if thumb_val:
                self.current["thumbnail_url"] = thumb_val
            else:
                self.current.pop("thumbnail_url", None)
            if img_val:
                self.current["image_url"] = img_val
            else:
                self.current.pop("image_url", None)

        elif self.section == "footer":
            txt = self.foot_text.value.strip()
            icon = self.foot_icon.value.strip()
            if txt:
                self.current["footer_text"] = txt
            else:
                self.current.pop("footer_text", None)
            if icon:
                self.current["footer_icon_url"] = icon
            else:
                self.current.pop("footer_icon_url", None)

        elif self.section == "color":
            raw = self.color_input.value.strip()
            if raw:
                raw_no = raw.lstrip("#")
                try:
                    self.current["colour"] = int(raw_no, 16) if not raw_no.isdigit() else int(raw_no)
                except ValueError:
                    await interaction.response.send_message("⚠️ Invalid color value.", ephemeral=True)
                    return
            else:
                self.current.pop("colour", None)

        elif self.section == "author":
            name_val = self.author_name.value.strip()
            icon_val = self.author_icon.value.strip()
            url_val = self.author_url.value.strip()
            if name_val:
                self.current["author_name"] = name_val
            else:
                self.current.pop("author_name", None)
            if icon_val:
                self.current["author_icon_url"] = icon_val
            else:
                self.current.pop("author_icon_url", None)
            if url_val:
                self.current["author_url"] = url_val
            else:
                self.current.pop("author_url", None)

        elif self.section == "fields":
            new_fields = []
            for n_input, v_input in self.field_inputs:
                n_val = n_input.value.strip()
                v_val = v_input.value.strip()
                if n_val and v_val:
                    new_fields.append({"name": n_val, "value": v_val, "inline": False})
            if new_fields:
                self.current["fields"] = new_fields
            else:
                # if user cleared all, remove key
                self.current.pop("fields", None)

        
        await self.db.patch(
            self.rec,
            [{"op": "replace", "path": f"/embeds/{self.embed_name}", "value": self.current}],
        )
        await self.org_msg.edit(embed=dict_to_embed(self.current), view=self.chooser_view)

class SectionChooserView(discord.ui.View):
    def __init__(self, embed_name: str, embed_data: dict, db, rec):
        super().__init__(timeout=300)
        self.embed_name = embed_name
        self.embed_data = embed_data
        self.db = db
        self.rec = rec
        self.msg = None

        for label, section in [
            ("Title", "title"),
            ("Description", "description"),
            ("Images", "images"),
            ("Footer", "footer"),
            ("Color", "color"),
            ("Author", "author"),
            ("Fields", "fields"),
            ("Cancel", "cancel")
        ]:
            self.add_item(self.SectionButton(label, section))
    
    async def on_timeout(self):
        if self.msg:
            await self.msg.edit(
                content="⏰ Editing timed out.",
                view=None,
            )
        self.stop()


    class SectionButton(discord.ui.Button):
        def __init__(self, label, section):
            super().__init__(label=label, style=discord.ButtonStyle.secondary if label != "Cancel" else discord.ButtonStyle.danger)
            self.section = section

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            
            if self.section == "cancel":
                await interaction.response.defer()
                await view.msg.edit(
                    content="❌ Editing cancelled.",
                    view=None,
                )
                view.stop()
                return
            
            await interaction.response.send_modal(
                EmbedSectionModal(
                    self.section,
                    view.embed_name,
                    view.embed_data,
                    view.db,
                    view.rec,
                    chooser_view=view,
                    org_msg=view.msg,
                )
            )


class EmbedMsg(Cog):
    embed = app_commands.Group(
        name="embed",
        description="Commands to manage embed messages.",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot

    @embed.command(name="create", description="Create an embed entity.")
    async def create_embed(self, interaction: discord.Interaction, name: str):
        db = get_db()
        is_exists = await db.select(RecordID("guilds", interaction.guild.id))
        if not is_exists:
            await db.create(
                RecordID("guilds", interaction.guild.id), {"embeds": {name: {}}}
            )
            logger.info(
                f"Created guild data for {interaction.guild.name} with empty embeds."
            )
        else:
            logger.info(f"Creating embed {name} for guild {interaction.guild.name}.")
            embeds = is_exists.get("embeds", {})
            if name in embeds:
                await interaction.response.send_message(
                    f"Embed with name `{name}` already exists.", ephemeral=True
                )
                return
            embeds[name] = {}
            await db.merge(RecordID("guilds", interaction.guild.id), {"embeds": embeds})
        await interaction.response.send_message(
            f"Embed `{name}` created successfully.", ephemeral=True
        )

    @embed.command(name="edit", description="Edit an embed entity.")
    @app_commands.describe(name="The name used when you created the embed")
    async def edit_embed(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        
        db = get_db()
        rec = RecordID("guilds", interaction.guild.id)

        embeds = (await db.query("SELECT VALUE embeds FROM $ref", {"ref": rec}))[0]

        if name not in embeds:
            await interaction.followup.send(
                f"Embed `{name}` does not exist.", ephemeral=True
            )
            return

        data = embeds[name]
        view = SectionChooserView(name, data, db, rec)
        preview = dict_to_embed(data)

        msg = await interaction.followup.send(
            content=f"🛠️ Editing embed **{name}** — choose a section to modify:",
            embed=preview,
            view=view
        )
        view.msg = msg

    @embed.command(name="delete", description="Delete an embed entity.")
    async def delete_embed(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        db = get_db()
        embeds = (
            await db.query(
                "SELECT VALUE embeds FROM $ref",
                {"ref": RecordID("guilds", interaction.guild.id)},
            )
        )[0]
        if not embeds:
            await interaction.followup.send(
                f"No embeds found for this server.", ephemeral=True
            )
            return
        
        if name not in embeds:
            await interaction.followup.send(
                f"Embed with name `{name}` does not exist.", ephemeral=True
            )
            return

        del embeds[name]
        await db.patch(
            RecordID("guilds", interaction.guild.id),
            [{"op": "remove", "path": f"/embeds/{name}"}],
        )
        await interaction.followup.send(
            f"Embed `{name}` deleted successfully.", ephemeral=True
        )

    async def cog_load(self):
        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id)
            self.bot.tree.add_command(self.embed, guild=test_guild)
            logger.info(f"Embed commands loaded for test guild {test_guild_id}.")


async def setup(bot):
    await bot.add_cog(EmbedMsg(bot))
