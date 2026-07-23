from telethon import TelegramClient

from app.config import API_ID, API_HASH

client = TelegramClient(
    "telegram",
    API_ID,
    API_HASH,
)