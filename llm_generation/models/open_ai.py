import os

from llm_generation.config import OPENAI_API_KEY
from llm_generation.models.base import BaseModel

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
import asyncio

import tiktoken
from loguru import logger
from openai import AsyncClient

from llm_generation.config import OPENAI_MAX_TOKEN_LENGTH


class OpenAI(BaseModel):
    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)

    async def generate_response(
        self, user_prompt: str, conversation: list = None, **kwargs
    ) -> str:
        # Truncate the user prompt to MAX_TOKEN_LENGTH tokens
        tokenizer = tiktoken.encoding_for_model("gpt-4o")
        user_prompt_tokens = tokenizer.encode(user_prompt)
        if len(user_prompt_tokens) > OPENAI_MAX_TOKEN_LENGTH:
            user_prompt = tokenizer.decode(user_prompt_tokens[:OPENAI_MAX_TOKEN_LENGTH])

        openai_client = AsyncClient(api_key=OPENAI_API_KEY)
        conversation = conversation or []

        response = await openai_client.chat.completions.create(
            model=self.model_name,
            messages=conversation + [{"role": "user", "content": user_prompt}],
            **kwargs
        )
        # Streaming response
        if "stream" in kwargs:
            content = ""
            if self.streaming_callback is None:
                logger.warning(
                    "No streaming callback is set, skipping callback function"
                )

            async for chunk in response:
                delta = chunk.choices[0].delta

                # Call the streaming callback function
                if self.streaming_callback:
                    # check if the callback function is a coroutine
                    if asyncio.iscoroutinefunction(self.streaming_callback):
                        await self.streaming_callback(delta)
                    else:
                        self.streaming_callback(delta)

                # Append the content
                if delta.content:
                    content += delta.content
        else:
            content = response.choices[0].message.content
        await openai_client.close()
        return content


async def main():
    openai = OpenAI()
    openai.set_streaming_callback(print)
    response = await openai.generate_response("Hello, how are you?", stream=True)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
