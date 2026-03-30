import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/meetings.db")
LABMEETING_PATH = os.getenv("LABMEETING_PATH", "../labmeeting")
GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "./credentials.json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
