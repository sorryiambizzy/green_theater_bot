import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
RUTRACKER_USERNAME = os.environ["RUTRACKER_USERNAME"]
RUTRACKER_PASSWORD = os.environ["RUTRACKER_PASSWORD"]
