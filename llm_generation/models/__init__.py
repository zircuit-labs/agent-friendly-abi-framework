from llm_generation.models.base import BaseModel
from llm_generation.models.open_ai import OpenAI


def get_model(model_name: str) -> BaseModel:
    model_dict = {
        "gpt-4o": OpenAI(model_name=model_name),
        "gpt-4o-mini": OpenAI(model_name=model_name),
        "o3-mini": OpenAI(model_name=model_name)
    }

    if model_name not in model_dict:
        raise ValueError(f"Model {model_name} not found")

    return model_dict[model_name]
