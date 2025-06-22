from discord.ext.commands import Cog, command
from galaxtic import settings
import asyncio
import yt_dlp
import discord
from collections import deque

SONGS_QUEUE = {}

yt_dlp_opts = {
    "format": "bestaudio[acodec=opus]/bestaudio",
    "noplaylist": True,
    "youtube_include_dash_manifest": False,
    "youtube_include_hls_manifest": False,
    "cookiefile": settings.COOKIES_FILE,
}

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -c:a libopus -b:a 384k -vbr on",
}

ytdl = yt_dlp.YoutubeDL(yt_dlp_opts)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = ""

    @classmethod
    def extract_info(cls, url, stream):
        info = ytdl.extract_info(url, download=not stream)
        return ytdl.sanitize_info(info)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream)
        )
        if "entries" in data:
            # take first item from a playlist
            data = data["entries"][0]
        filename = data["title"] if stream else ytdl.prepare_filename(data)
        return filename


async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))


def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


class SongData:
    def __init__(self, audio_url: str, title: str, thumbnail: str, duration: str):
        self.audio_url = audio_url
        self.title = title
        self.thumbnail = thumbnail
        self.duration = duration


class Music(Cog):
    def __init__(self, bot):
        self.bot = bot

    @command(name="join", help="Tells the bot to join the voice channel")
    async def join(self, ctx):
        if not ctx.message.author.voice:
            await ctx.send(
                "{} is not connected to a voice channel".format(ctx.message.author.name)
            )
            return
        else:
            channel = ctx.message.author.voice.channel
        await channel.connect()

    @command(name="leave", help="To make the bot leave the voice channel")
    async def leave(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_connected():
            await voice_client.disconnect()
        else:
            await ctx.send("The bot is not connected to a voice channel.")

    @command(name="play", help="To play song")
    async def play(self, ctx, *, song_query):
        if not ctx.author.voice:
            await ctx.send("You need to be connected to a voice channel to play music.")
            return
        voice_channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client

        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        query = "ytsearchmusic1: " + song_query

        results = await search_ytdlp_async(query, yt_dlp_opts)
        tracks = results.get("entries", [])
        if tracks is None:
            await ctx.send("No results found for your query.")
            return

        first_track = tracks[0]
        audio_url = first_track["url"]
        title = first_track.get("title", "Unknown Title")
        thumbnail = first_track.get("thumbnail", None)
        duration = first_track.get("duration_string", "Unknown Duration")

        guild_id = str(ctx.guild.id)
        if SONGS_QUEUE.get(guild_id) is None:
            SONGS_QUEUE[guild_id] = deque()

        SONGS_QUEUE[guild_id].append(SongData(audio_url, title, thumbnail, duration))

        if voice_client.is_playing() or voice_client.is_paused():
            await ctx.send(f"Added to queue: {title}")
        else:
            await self.play_next_song(voice_client, guild_id, ctx.channel)

    @command(name="skip", help="Skips the current song")
    async def skip(self, ctx):
        if ctx.guild.voice_client and (
            ctx.guild.voice_client.is_playing() or ctx.guild.voice_client.is_paused()
        ):
            ctx.guild.voice_client.stop()
            await ctx.send("Skipped the current song.")
        else:
            await ctx.send("The bot is not playing anything at the moment.")

    @command(name="pause", help="This command pauses the song")
    async def pause(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client is None:
            await ctx.send("I'm not in a voice channel.")
            return
        if not voice_client.is_playing():
            await ctx.send("Nothing is currently playing.")

        voice_client.pause()
        await ctx.send("Playback paused.")

    @command(name="resume", help="Resumes the song")
    async def resume(self, ctx):
        voice_client = ctx.message.guild.voice_client

        if not voice_client:
            await ctx.send("I'm not in a voice channel.")
            return

        if not voice_client.is_paused():
            await ctx.send("I am not paused right now.")

        await voice_client.resume()
        await ctx.send("Playback resumed.")

    @command(name="stop", help="Stops the song")
    async def stop(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await ctx.send("I'm not connected to any voice channel.")

        guild_id = str(ctx.guild.id)
        if guild_id in SONGS_QUEUE:
            SONGS_QUEUE[guild_id].clear()

        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        await voice_client.disconnect()

        await ctx.send("Playback stopped and I have left the voice channel.")

    async def play_next_song(self, voice_client, guild_id, channel):
        if SONGS_QUEUE[guild_id]:
            song_data = SONGS_QUEUE[guild_id].popleft()
            source = discord.FFmpegOpusAudio(
                song_data.audio_url, **ffmpeg_options, executable="ffmpeg"
            )

            def after_play(error):
                if error:
                    print(f"Error occurred while playing audio: {error}")
                asyncio.run_coroutine_threadsafe(
                    self.play_next_song(voice_client, guild_id, channel), self.bot.loop
                )

            voice_client.play(source, after=after_play)
            embed = discord.Embed(
                title="Now Playing",
                description=song_data.title,
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="", value=f"**Duration**: {song_data.duration}", inline=True
            )
            if song_data.thumbnail:
                embed.set_image(url=song_data.thumbnail)
            asyncio.create_task(channel.send(embed=embed))
        else:
            await voice_client.disconnect()
            SONGS_QUEUE[guild_id] = deque()


async def setup(bot):
    await bot.add_cog(Music(bot))
