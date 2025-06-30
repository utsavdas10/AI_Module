import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # LLM API Keys
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY", "")

    class Config:
        case_sensitive = True

settings = Settings()