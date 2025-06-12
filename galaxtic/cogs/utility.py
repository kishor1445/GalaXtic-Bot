from discord.ext.commands import Cog, command
from discord import Embed
from galaxtic.bot import GalaxticBot
from galaxtic import settings, logger
from discord import app_commands
import discord
import asyncio
import tempfile
import yt_dlp
import os
import aiohttp

ydl_opts = {
    #"format": "best[ext=mp4][vcodec!=none][acodec!=none]/best",
    # "format": "bv*+ba/best",
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "quiet": True,
    "no_warnings": True,
    "cookiefile": settings.COOKIES_FILE,
    "merge_output_format": "mp4",
}

async def get_share_link(path: str) -> str:
    url = f"{settings.SEAFILE.SERVER_URL.rstrip('/')}/api/v2.1/via-repo-token/share-links/"
    headers = {
        "Authorization": f"Bearer {settings.SEAFILE.REPO_API_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "permissions": {
            "can_edit": False,
            "can_download": True,
            "can_upload": False
        },
        "path": path,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to create share link: {resp.status} - {text}")

            data = await resp.json()
            return data.get("download_link")


async def search_ytdlp_async(url, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(url, ydl_opts))


def _extract(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


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

    @app_commands.command(
        name="download",
        description="Download a file from a URL and send it in the channel.",
    )
    @app_commands.describe(url="The URL of the file to download")
    async def download(self, interaction: discord.Interaction, url: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = ydl_opts.copy()
            opts.update(
                {
                    "outtmpl": os.path.join(tmpdir, "%(title).70s.%(ext)s"),
                    "postprocessor_args": ["-c:v", "libx264", "-c:a", "aac"],
                }
            )
            try:
                logger.info("Downloading the requested file...")
                await interaction.response.send_message("Downloading your file...")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, lambda: yt_dlp.YoutubeDL(opts).download([url])
                )
            except Exception as e:
                await interaction.edit_original_response(
                    content=f"❌ Failed to download: `{e}`"
                )
                return

            files = os.listdir(tmpdir)
            if not files:
                await interaction.edit_original_response(
                    content="❌ No file was downloaded."
                )
                return
            
            await interaction.edit_original_response(content="Checking the file size...")
            file_path = os.path.join(tmpdir, files[0])
            file_size = os.path.getsize(file_path)
            logger.info("Checking the file size")
            if file_size <= 10 * 1024 * 1024:
                # Under 25MB → send directly
                await interaction.edit_original_response(content="Uploading to discord...")
                await interaction.followup.send(
                    file=discord.File(file_path, filename=os.path.basename(file_path))
                )
                await interaction.edit_original_response(content="Your file is ready!!")
            else:
                # Over 10MB → upload to Cloudinary
                await interaction.edit_original_response(content="File size is > 10M Uploading the file to the cloud stoarge... (this may take a while)")
                logger.info(f"Attempting to upload {file_size/1024/1024:.2f}MB file")
                try:
                    loop = asyncio.get_running_loop()
                    uploaded = await loop.run_in_executor(
                        None,
                        lambda: self.bot.seafile_client.upload_file(
                            parent_dir="/",
                            file_path=file_path
                        ),
                    )
                    uploaded_file_path = "/" + uploaded["name"]
                    public_url = await get_share_link(uploaded_file_path)
                    if public_url:
                        await interaction.edit_original_response(content=f"Your file is ready!\n{public_url}")
                    else:
                        raise Exception("Cloudinary upload returned no URL.")
                except Exception as e:
                    logger.error(f"Cloudinary upload failed: {e}")
                    await interaction.edit_original_response(
                        content=f"❌ Upload to the cloud failed"
                    )

    async def cog_load(self):
        test_guild_id = settings.DISCORD.TEST_GUILD_ID

        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id)
            self.bot.tree.add_command(self.download, guild=test_guild)


async def setup(bot: GalaxticBot):
    await bot.add_cog(Utility(bot))
