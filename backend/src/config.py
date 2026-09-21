import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")


settings = Settings()