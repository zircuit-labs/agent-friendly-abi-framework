import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENAI_MAX_TOKEN_LENGTH = int(os.getenv("OPENAI_MAX_TOKEN_LENGTH", "81920"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
