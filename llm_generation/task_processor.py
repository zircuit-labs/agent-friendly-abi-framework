import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Dict

import yaml
from loguru import logger
from jinja2 import Template

from llm_generation.conversation_manager import ConversationManager
from llm_generation.models import get_model
from llm_generation.models.base import BaseModel


class TaskProcessor:
    def __init__(
        self, prompt_template_config_path: str, model_name: str, streaming_callback=None
    ):
        self.conversation_manager: ConversationManager = ConversationManager()
        self.model_name = model_name
        # Load the task config -> the whole config file
        self.task_config: Dict = self._load_prompt_template_config(
            prompt_template_config_path, model_name
        )
        self._validate_config()

        # Load model task config -> the specific model config
        self.model_task_config: Dict = self.task_config["model"][model_name]

        # Load system prompt
        self.system_prompt = self.model_task_config.get("system_prompt", None)

        # Load the model
        self.model: BaseModel = get_model(model_name)

        # Callback function for streaming
        self.streaming_callback = streaming_callback
        if self.streaming_callback:
            self.model.set_streaming_callback(self.streaming_callback)

    def init_system_prompt(self, **kwargs):
        if self.system_prompt:
            self.system_prompt = self.system_prompt.format(**kwargs)
        else:
            logger.warning("System prompt not found in the model task config")

    def _validate_config(self):
        if "model" not in self.task_config:
            raise ValueError(
                f"`model` property not found in the prompt template config"
            )
        if self.model_name not in self.task_config["model"]:
            raise ValueError(
                f"Model {self.model_name} not found in the prompt template config"
            )
        if "rounds" not in self.task_config["model"][self.model_name]:
            raise ValueError(
                f"`rounds` property not found in the prompt template config"
            )
        if not isinstance(self.task_config["model"][self.model_name]["rounds"], dict):
            raise ValueError(
                f"`rounds` property should be a dict in the prompt template config"
            )
        for round_count in self.task_config["model"][self.model_name]["rounds"]:
            if (
                "prompt"
                not in self.task_config["model"][self.model_name]["rounds"][round_count]
            ):
                raise ValueError(
                    f"`prompt` property not found in the prompt template config for conversation round {round}"
                )

    def _load_prompt_template_config(
        self, prompt_template_config_path: str, model_name: str
    ):
        base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        template_config_path = os.path.join(base_folder, prompt_template_config_path)
        logger.info(f"Loading prompt template config from {template_config_path}")
        with open(template_config_path, "r") as f:
            prompt_template_config = yaml.safe_load(f)
        return prompt_template_config

    async def _call_model(self, user_prompt: str, conversation_round: int):
        conversation = []
        # Check if the system message is needed
        if self.system_prompt and len(self.conversation_manager.get_history()) == 0:
            system_message = self.system_prompt
            self.conversation_manager.add_system_message(system_message)

        # Add existing conversation
        conversation.extend(self.conversation_manager.get_history())

        # Generation parameters
        generation_parameters = self.model_task_config["rounds"][
            conversation_round
        ].get("generation_parameters", {})

        # Generate response
        response = await self.model.generate_response(
            user_prompt, conversation, **generation_parameters
        )

        # Add assistant message to the conversation
        self.conversation_manager.add_user_message(user_prompt)
        self.conversation_manager.add_assistant_message(response)
        return response

    def _format_prompt(self, conversation_round: int, **kwargs):
        if conversation_round not in self.model_task_config["rounds"]:
            raise ValueError(
                f"Conversation round {conversation_round} not found in the model task config"
            )
        if "prompt" not in self.model_task_config["rounds"][conversation_round]:
            raise ValueError(
                f"`prompt` property not found in the model task config for conversation round {conversation_round}"
            )
        prompt_template = self.model_task_config["rounds"][conversation_round]["prompt"]
        
        # First try Jinja2 template rendering
        try:
            template = Template(prompt_template)
            return template.render(**kwargs)
        except Exception as e:
            logger.warning(f"Jinja2 template rendering failed: {e}")
            # Fallback to basic string formatting
            try:
                return prompt_template.format(**kwargs)
            except KeyError as ke:
                logger.error(f"String formatting failed: {ke}")
                # Try a simpler fallback approach
                result = prompt_template
                for key, value in kwargs.items():
                    placeholder = "{" + key + "}"
                    result = result.replace(placeholder, str(value))
                return result

    def _extract_json(self, raw_text):
        # Regular expression to match JSON content inside triple backticks
        match = re.search(r"```(?:json)?\n?(.*?)\n?```", raw_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.exception(
                    f"Error: Extracted content is not valid JSON. {json_str}"
                )
        else:
            return json.loads(raw_text)

    def _remove_thinking_text(self, raw_text):
        # Remove the thinking text from the generated response by deepseek-r1
        if "</think>" in raw_text:
            return raw_text[raw_text.index("</think>") + len("</think>") :].strip()
        return raw_text

    async def run(
        self,
        conversation_round=1,
        is_json=False,
        should_remove_thinking=False,
        **kwargs,
    ):
        user_prompt = self._format_prompt(
            conversation_round=conversation_round, **kwargs
        )

        response = await self._call_model(
            user_prompt=user_prompt, conversation_round=conversation_round
        )

        # Extract JSON from the response
        if is_json:
            return self._extract_json(response)

        # Remove the thinking text from the generated response by reasoning models
        if should_remove_thinking:
            return self._remove_thinking_text(response)
        return response


async def main():
    def callback_func(content, delta):
        print(f"Content: {content}")
        print(delta)

    task_processor = TaskProcessor(
        prompt_template_config_path="prompt_template/public_terminal/reasoning_based_general_response.yml",
        model_name="sonar-reasoning-pro",
        streaming_callback=callback_func,
    )
    response = await task_processor.run(
        current_date=f'{datetime.now(UTC).strftime("%YYYY-%mm-%dd")}',
        user_question="what happened to bybit?",
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
