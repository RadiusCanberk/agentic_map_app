import os
from dotenv import load_dotenv

from src.utils.read_json import load_system_prompts

load_dotenv()

# Database URL - read from .env file
DATABASE_URL = os.getenv("DATABASE_URL")
# Google Maps API Key
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# System Prompt
SYSTEM_PROMPT = load_system_prompts()
# OpenRouter API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")

# OpenStreetMap (Nominatim) usage identification
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT")
NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL")
