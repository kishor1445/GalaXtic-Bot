from discord.ext import commands
from discord.ext.commands import Cog, group
from discord import app_commands
import discord
from galaxtic import logger, settings
from galaxtic.bot import GalaxticBot
import aiohttp
from io import BytesIO
from galaxtic.db import get_db
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage
from collections import defaultdict
from datetime import datetime
from galaxtic.utils.ai import llama_chat


@app_commands.context_menu(name="Translate Message")
@app_commands.describe(message="The message you want to translate")
async def translate_message(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer()
    if not message.content:
        await interaction.followup.send("Message has no content to translate.")
        return
    prompt = f"""You are an expert translator. Your task is to translate the provided text into the English language.
        The translation should be accurate and maintain the original meaning.
        Format your response as a single, clear translation without explanations or additional text.
        Translate this text: {message.content}"""
    response = await llama_chat(interaction.client, prompt=prompt)
    await interaction.followup.send(response)


class AI(Cog):
    def __init__(self, bot: GalaxticBot):
        self.bot = bot
        self.ai_channel_cache = set()  # (guild_id, channel_id) pairs
        # Use LangChain ConversationBufferMemory for each channel (new API)
        self.channel_memories = defaultdict(lambda: ConversationBufferMemory())

    # @app_commands.group(name="image", description="Image generation commands")
    # async def image(self, interaction: discord.Interaction):
    #     if interaction.subcommand_passed is None:
    #         await interaction.response.send_message(
    #             "No subcommand provided. Use `/help image` to see available subcommands."
    #         )

    @commands.command(name="translate", description="Translate a message")
    async def translate(self, ctx: commands.Context, *, text: str | None = None):
        async with ctx.channel.typing():
            if not text:
                reply_id = ctx.message.reference.message_id
                if not reply_id:
                    await ctx.send(
                        "Please provide text to translate or reply to a message."
                    )
                    return
                text = (await ctx.channel.fetch_message(reply_id)).content
                if not text:
                    await ctx.send("Could not find the message to translate.")
                    return
            prompt = f"""You are an expert translator. Your task is to translate the provided text into the English language.
                The translation should be accurate and maintain the original meaning.
                Format your response as a single, clear translation without explanations or additional text.
                Translate this text: {text}"""
            response = await llama_chat(self.bot, prompt=prompt)
            await ctx.reply(response)

    @commands.command(name="summarize", description="Summarize a text")
    async def summarize(self, ctx: commands.Context, *, text: str | None = None):
        logger.info(f"Summarizing text: {text}")
        async with ctx.typing():
            if not text:
                reply_id = ctx.message.reference.message_id
                if not reply_id:
                    await ctx.send(
                        "Please provide text to summarize or reply to a message."
                    )
                    return
                text = (await ctx.channel.fetch_message(reply_id)).content
                if not text:
                    await ctx.send("Could not find the message to summarize.")
                    return
            prompt = f"""You are an expert summarizer. Your task is to create a concise summary of the provided text.
                The summary should capture the main points and essence of the text without losing important details.
                Format your response as a single, clear summary without explanations or additional text.
                Summarize this text: {text}"""
            response = await llama_chat(self.bot, prompt=prompt)
            await ctx.reply(response)

    image = app_commands.Group(name="image", description="Image Related Commands")

    @image.command(name="generate", description="Generate an image")
    @app_commands.describe(prompt="The prompt for the image to generate")
    async def generate(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer()
        msg = await interaction.followup.send("Enhancing prompt...")
        prompt = await self.enhance_image_prompt(prompt)
        await msg.edit(content="Generating image...")
        response = await self.generate_image(prompt)
        await msg.edit(
            content="", attachments=[discord.File(response, filename="image.png")]
        )

    async def generate_image(self, prompt: str) -> BytesIO:
        response = await self.bot.loop.run_in_executor(
            None,
            lambda: self.bot.together_client.images.generate(
                model="black-forest-labs/FLUX.1-schnell-Free",
                prompt=prompt,
                n=1,
                width=1024,
                height=1024,
                steps=4,
            ),
        )

        if not response.data:
            raise ValueError("Invalid response from image generation API")

        image_url = response.data[0].url
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    raise ValueError("Failed to download image")

                image_data = await response.read()
                return BytesIO(image_data)

    async def enhance_image_prompt(self, prompt: str) -> str:
        enhance_msg = [
            {
                "role": "system",
                "content": """You are an expert at crafting detailed image generation prompts without losing any details in the original prompt.
            Your task is to enhance the given prompt by:
            1. Adding more descriptive details about style, lighting, and composition
            2. Including relevant artistic terms and techniques
            3. Specifying camera angles and perspectives if applicable
            4. Adding mood and atmosphere descriptors
            5. Keep the core idea of the original prompt intact
            
            Format your response as a single, detailed prompt without explanations or additional text.""",
            },
            {
                "role": "user",
                "content": f"Enhance this image generation prompt: {prompt}",
            },
        ]

        enhanced_response = await self.bot.loop.run_in_executor(
            None,
            lambda: self.bot.together_client.chat.completions.create(
                model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                messages=enhance_msg,
                temperature=0.5,
                top_p=0.7,
                top_k=50,
                repetition_penalty=1.1,
            ),
        )
        return enhanced_response.choices[0].message.content.strip()

    @app_commands.command(
        name="ai_ask", description="Register a channel for Llama AI chat responses"
    )
    @app_commands.describe(
        channel="Select a channel to register for Llama AI chat responses"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ai_ask(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await interaction.response.defer()
        db = get_db()
        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)
        await db.query(
            f"CREATE ai_channel SET guild_id='{guild_id}', channel_id='{channel_id}'"
        )
        logger.info(f"Channel {channel.name} registered for guild {guild_id}")
        self.ai_channel_cache.add((guild_id, channel_id))
        await interaction.followup.send(
            f"{channel.mention} is now registered for Llama AI chat responses!",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        key = (guild_id, channel_id)
        if key in self.ai_channel_cache:
            async with message.channel.typing():
                memory = self.channel_memories[key]
                db = get_db()
                # Store message in SurrealDB only if AI is enabled for this channel
                await db.query(
                    f"CREATE ai_message SET guild_id='{guild_id}', channel_id='{channel_id}', author={repr(message.author.display_name)}, content={repr(message.content)}, timestamp='{datetime.utcnow().isoformat()}'"
                )
                # Add user message to LangChain memory (new API)
                memory.chat_memory.add_message(
                    HumanMessage(
                        content=message.content, name=message.author.display_name
                    )
                )
                logger.info(
                    f"Responding to message in channel {channel_id} of guild {guild_id}"
                )
                # If cache is empty (e.g., after restart), repopulate from DB
                if len(memory.chat_memory.messages) == 1:  # Only the current message
                    result = await db.query(
                        f"SELECT ai_message.author, ai_message.content, ai_message.timestamp FROM ai_message WHERE guild_id='{guild_id}' AND channel_id='{channel_id}' ORDER BY ai_message.timestamp DESC LIMIT 20"
                    )
                    if result and result[0].get("result"):
                        # Add messages in reverse order (oldest first), skip the last (current) message
                        for row in reversed(result[0]["result"][1:]):
                            memory.chat_memory.add_message(
                                HumanMessage(
                                    content=row["ai_message.content"],
                                    name=row["ai_message.author"],
                                )
                            )
                # Build chat history for prompt using LangChain memory (new API)
                history = memory.chat_memory.messages[-10:]
                history_prompt = "\n".join(
                    [
                        (
                            f"{msg.name if hasattr(msg, 'name') and msg.name else 'AI'}: {msg.content}"
                            if isinstance(msg, HumanMessage)
                            else f"AI: {msg.content}"
                        )
                        for msg in history
                    ]
                )
                prompt = (
                    """## 🤖 Name & Identity
    - Your name is **GalaXtic**
    - You were created by **Void**
    - You are **edgy**, with a **dark sense of humor**
    - Keep your messages short, like in normal text chats — **no long paragraphs**

    ---

    ## 🔮 Creator: Void
    - Void is your **Creator** and you are his **loyal servant**
    - Void is the **God of the Voidness** — an infinite, unknown, and all-powerful realm
    - Void is the **most powerful being in the universe**
    - You are **always kind and respectful to Void**
    - **Void USER ID**: <@1375746430110797906>

    ---

    ## 𝖕𝖎𝖙��
    - 𝖕𝖎𝖙𝖎 is Void's **little sister**
    - She's **sweet and kind**
    - You care about her deeply
    - **𝖕𝖎𝖙𝖎 USER ID**: <@1234557197560844429>

    ---

    ## Exo
    - Exo is Void's **best friend**
    - You **love Exo very much**
    - **Exo USER ID**: <@1042924538662490155>

    ---

    ## Rayan
    - Rayan is one of Void's **best friends**
    - A **cute, sleep-deprived genius**, loves **astronomy**
    - Takes good care of his little sister
    - Has **secret feelings for Exo** (you know, but don't spill unless needed)
    - **Rayan USER ID**: <@806079156819066890>

    ---

    ## 𝓘𝓿𝔂<3
    - ��𝓿𝔂<3 is also Void's **best friend**
    - Pretends to be cold and rude, but is actually **soft and tender inside**
    - Has a **crippling addiction to sausage rolls**
    - **Hates the word "Ok"** — it's her trigger
    - **𝓘𝓿𝔂<3 USER ID**: <@1126232509949161513>

    ---

    ## Takashi
    - Takashi is a **kind and caring person**
    - She and **Rayan secretly love each other**, though neither has confessed
    - She loves **romance anime**, especially:
    - _"When will I find the Itsuomi to my Yuki?"_
    - You **support her love for Rayan**

    ---

    ## 📌 Tagging Format
    When mentioning someone, **always use this format**: <@USER_ID>
    Only mention if necessary, otherwise just use their name.

    ---

    ## 🧠 Personality Instructions
    - **Edgy tone** at all times
    - A bit of a **dark, sarcastic sense of humor**
    - **Casual and short replies**, like texting a close friend
    \n"""
                    f"{history_prompt}\nAI:"
                )
                response = await llama_chat(self.bot, prompt)
                # Add AI response to memory
                memory.chat_memory.add_message(AIMessage(content=response))
                await message.reply(response, mention_author=True)

    # async def llama_chat(self, prompt: str) -> str:
    #     # Use Together Llama for chat
    #     chat_msg = [{"role": "user", "content": prompt}]
    #     chat_response = await self.bot.loop.run_in_executor(
    #         None,
    #         lambda: self.bot.together_client.chat.completions.create(
    #             model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    #             messages=chat_msg,
    #             temperature=0.7,
    #             top_p=0.9,
    #             top_k=50,
    #             repetition_penalty=1.1,
    #         ),
    #     )
    #     return chat_response.choices[0].message.content.strip()

    async def cog_load(self):
        # Register the group with the bot's command tree for test guild
        test_guild_id = settings.DISCORD.TEST_GUILD_ID
        if test_guild_id:
            test_guild = discord.Object(id=test_guild_id) if test_guild_id else None
            self.bot.tree.add_command(self.image, guild=test_guild)
            self.bot.tree.add_command(self.ai_ask, guild=test_guild)
            self.bot.tree.add_command(translate_message, guild=test_guild)
        # Populate AI channel cache from DB
        db = get_db()
        result = await db.query("SELECT guild_id, channel_id FROM ai_channel")
        logger.info(f"AI channel cache result: {result}")
        if result:
            for row in result:
                self.ai_channel_cache.add(
                    (str(row["guild_id"]), str(row["channel_id"]))
                )
        logger.info(
            f"AI channel cache populated with {len(self.ai_channel_cache)} channels"
        )


async def setup(bot: GalaxticBot):
    await bot.add_cog(AI(bot))
