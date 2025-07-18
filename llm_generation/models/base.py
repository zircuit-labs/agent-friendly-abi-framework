from abc import ABC, abstractmethod

from loguru import logger


class BaseModel(ABC):
    def __init__(self, model_name):
        self.model_name = model_name
        self.logger = logger
        self.streaming_callback = None

    async def generate_response(
        self, user_prompt: str, conversation: list = None, **kwargs
    ) -> str:
        """
        Generate a response based on the conversation
        :param user_prompt: user prompt
        :param conversation: list of conversation
        :param kwargs: additional parameters
        :return: llm response
        """
        pass

    async def generate_json_response(self, conversation: list, **kwargs) -> dict:
        """
        Generate a response based on the conversation
        :param conversation: list of conversation
        :param kwargs: additional parameters
        :return: llm response
        """
        pass

    def set_streaming_callback(self, callback):
        self.streaming_callback = callback
