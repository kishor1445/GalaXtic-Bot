from galaxtic.bot import GalaxticBot
from galaxtic import logger
from together import Together
from galaxtic import settings

together_client = Together(api_key=settings.AI.TOGETHER_API_KEY)

async def llama_chat(bot: GalaxticBot, prompt: str) -> str:
    chat_msg = [{
        "role": "user",
        "content": prompt
    }]
    logger.info(f"Chat message: {chat_msg}")
    chat_response = await bot.loop.run_in_executor(
        None,
        lambda: together_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=chat_msg,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.1,
        )
    )
    logger.info(f"Chat response: {chat_response}")
    return chat_response.choices[0].message.content.strip()