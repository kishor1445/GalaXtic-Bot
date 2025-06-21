import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from galaxtic.db import get_db
from datetime import datetime
from galaxtic import settings, logger
from galaxtic.utils.ai import llama_chat


class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def search_anilist(self, query):
        url = "https://graphql.anilist.co"
        query_str = """
        query ($search: String) {
            Page(perPage: 5) {
                media(search: $search, type: ANIME) {
                    id
                    title {
                        romaji
                        english
                    }
                    type
                    format
                    episodes
                    status
                    season
                    seasonYear
                    genres
                    description(asHtml: false)
                    siteUrl
                    coverImage {
                        large
                    }
                    nextAiringEpisode {
                        episode
                        airingAt
                    }
                }
            }
        }
        """
        variables = {"search": query}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"query": query_str, "variables": variables}
            ) as resp:
                data = await resp.json()
                return data.get("data", {}).get("Page", {}).get("media", [])

    @app_commands.command(name="add_anime", description="Add an anime to your list")
    @app_commands.describe(name="Anime name")
    async def add_anime(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        results = await self.search_anilist(name)
        if not results:
            logger.error(f"Anime not found: {name}")
            await interaction.followup.send("Anime not found.")
            return
        if len(results) == 1:
            logger.info(f"Anime found: {results}")
            anime = results[0]
            await self.send_anime_confirmation(interaction, anime)
        else:
            logger.error(f"Multiple anime found for {name}: {results}")
            view = AnimeSelectView(results, interaction.user.id, self)
            msg = await interaction.followup.send(
                content="Select the correct anime:", view=view
            )
            view.message = msg

    async def send_anime_confirmation(self, interaction, anime, message=None):
        db = get_db()
        user_id = str(interaction.user.id)
        anime_id = anime["id"]
        # Check if anime already exists for this user
        check_result = await db.query(
            f"SELECT * FROM user_anime WHERE user_id='{user_id}' AND anime_id={anime_id} LIMIT 1"
        )
        logger.info(f"Check result: {check_result}")
        already_added = bool(check_result)

        # Build a detailed embed
        anime_type = anime.get("type", "N/A")
        title = (
            anime["title"]["english"] or anime["title"]["romaji"]
        ) + f" ({anime_type})"
        raw_desc = anime.get("description", "No description.")
        if raw_desc:
            raw_desc = (
                raw_desc.replace("<br>", "\n").replace("<i>", "").replace("</i>", "")
            )
            # Use llama_chat to enhance and summarize the description
            prompt = (
                "You are an expert anime assistant. Summarize and enhance the following anime description. "
                "Make it engaging, concise, and avoid spoilers. Keep it under 1000 characters.\n"
                f"Description: {raw_desc}"
            )
            try:
                logger.info(f"Prompt: {prompt}")
                desc = await llama_chat(self.bot, prompt)
                logger.info(f"Desc: {desc}")
                if len(desc) > 1000:
                    desc = desc[:997] + "..."
            except Exception as e:
                logger.error(f"Error in llama_chat: {e}")
                desc = raw_desc[:1000] + "... (AI summary failed)"
        else:
            desc = "No description."

        embed = discord.Embed(
            title=title,
            url=anime["siteUrl"],
            description=desc,
            color=discord.Color.blue(),
        )
        embed.set_image(url=anime["coverImage"]["large"])
        embed.set_footer(
            text=(
                "This confirmation will expire in 5 minutes."
                if not already_added
                else "This anime is already in your list."
            )
        )
        status = anime.get("status", "").upper()
        episodes = anime.get("episodes")
        next_ep = anime.get("nextAiringEpisode")
        if status == "RELEASING":
            last_ep = (
                str(next_ep["episode"] - 1)
                if next_ep and next_ep.get("episode")
                else "?"
            )
            next_ep_num = (
                str(next_ep["episode"]) if next_ep and next_ep.get("episode") else "?"
            )
            next_ep_time = (
                f"<t:{next_ep['airingAt']}:R>"
                if next_ep and next_ep.get("airingAt")
                else "?"
            )
            episodes_display = (
                f"Ongoing\nLast: {last_ep}\nNext: {next_ep_num} ({next_ep_time})"
            )
        elif episodes is not None:
            episodes_display = str(episodes)
        else:
            episodes_display = "N/A"
        embed.add_field(name="Format", value=anime.get("format", "N/A"), inline=True)
        embed.add_field(name="Episodes", value=episodes_display, inline=True)
        embed.add_field(name="Status", value=anime.get("status", "N/A"), inline=True)
        embed.add_field(
            name="Season",
            value=f"{anime.get('season', 'N/A')} {anime.get('seasonYear', 'N/A')}",
            inline=True,
        )
        genres = ", ".join(anime.get("genres", [])) or "N/A"
        embed.add_field(name="Genres", value=genres, inline=False)
        if anime.get("id", None) is not None:
            embed.add_field(
                name="Streaming",
                value=f"[Watch Free](https://www.miruro.tv/watch?id={anime.get('id')})",
            )

        if already_added:
            if message:
                await message.edit(
                    content="This anime is already in your list!",
                    embed=embed,
                    view=None,
                )
            else:
                await interaction.followup.send(
                    content="This anime is already in your list!",
                    embed=embed,
                    view=None,
                )
            return

        view = AnimeConfirmView(anime, interaction.user.id)
        if message:
            await message.edit(content=None, embed=embed, view=view)
            view.message = message
        else:
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg

    @app_commands.command(
        name="remove_anime", description="Remove an anime/movie from your list"
    )
    @app_commands.describe(name="Anime or movie name")
    async def remove_anime(self, interaction: discord.Interaction, name: str):
        db = get_db()
        user_id = str(interaction.user.id)
        await db.query(
            f"DELETE user_anime WHERE user_id='{user_id}' AND (anime_title='{name}')"
        )
        await interaction.response.send_message(
            f"Removed '{name}' from your list (if it existed).", ephemeral=True
        )

    async def cog_load(self):
        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        test_guild = discord.Object(id=test_guild_id) if test_guild_id else None
        self.bot.tree.add_command(self.add_anime, guild=test_guild)
        self.bot.tree.add_command(self.remove_anime, guild=test_guild)


class AnimeConfirmView(discord.ui.View):
    def __init__(self, anime, user_id):
        super().__init__(timeout=300)  # 5 minutes
        self.anime = anime
        self.user_id = user_id
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Failed to edit message on timeout: {e}")

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This confirmation isn't for you.", ephemeral=True
            )
            return
        db = get_db()
        # Check if anime already exists for this user
        user_id = str(self.user_id)
        anime_id = self.anime["id"]
        check_result = await db.query(
            f"SELECT * FROM user_anime WHERE user_id='{user_id}' AND anime_id={anime_id} LIMIT 1"
        )
        if check_result and check_result[0].get("result"):
            await interaction.response.send_message(
                "This anime is already in your list!", ephemeral=True
            )
            return
        await db.query(
            f"CREATE user_anime SET user_id='{self.user_id}', anime_id={self.anime['id']}, anime_title={repr(self.anime['title']['english'] or self.anime['title']['romaji'])}, anime_type='{self.anime['type']}', added_at='{datetime.utcnow().isoformat()}'"
        )
        await interaction.response.edit_message(
            content="Anime added to your list!", view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This confirmation isn't for you.", ephemeral=True
            )
            return
        try:
            await interaction.response.edit_message(content="Cancelled.", view=None)
        except Exception as e:
            print(f"Error in cancel button: {e}")
            try:
                await interaction.response.send_message(
                    f"Failed to cancel: {e}", ephemeral=True
                )
            except Exception as inner_e:
                print(f"Error sending error message: {inner_e}")


class AnimeSelectView(discord.ui.View):
    def __init__(self, results, user_id, anime_cog):
        super().__init__(timeout=120)  # 2 minutes
        self.user_id = user_id
        self.anime_cog = anime_cog
        self.message = None
        self.has_been_removed = False  # Add flag to track if view was removed
        self.select = AnimeSelect(results, user_id, anime_cog)
        self.add_item(self.select)

    async def on_timeout(self):
        if self.has_been_removed:  # Skip if view was already removed
            return
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Failed to edit select menu on timeout: {e}")


class AnimeSelect(discord.ui.Select):
    def __init__(self, results, user_id, anime_cog):
        options = []
        for anime in results:
            title = anime["title"]["english"] or anime["title"]["romaji"]
            year = anime.get("seasonYear", "N/A")
            options.append(
                discord.SelectOption(
                    label=title,
                    description=f"{anime.get('format', 'N/A')} ({year})",
                    value=str(anime["id"]),
                )
            )
        super().__init__(
            placeholder="Choose the correct anime...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.results = results
        self.user_id = user_id
        self.anime_cog = anime_cog

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This selection isn't for you.", ephemeral=True
            )
            return
        anime_id = int(self.values[0])
        anime = next((a for a in self.results if a["id"] == anime_id), None)
        if anime:
            # Mark the view as removed
            self.view.has_been_removed = True
            # Show loading message while preparing confirmation
            await interaction.response.edit_message(
                content="Loading anime details...", view=None
            )
            await self.anime_cog.send_anime_confirmation(
                interaction, anime, message=interaction.message
            )
        else:
            await interaction.response.send_message(
                "Anime not found in selection.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Anime(bot))
