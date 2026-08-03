import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_PORT = int(os.getenv("PROXY_PORT", "10808"))
CHANNELS = os.getenv("CHANNELS", "").split(",")
CHANNELS = [ch.strip() for ch in CHANNELS if ch.strip()]
GIGACHAT_TOKEN = os.getenv("GIGACHAT_TOKEN")
ADMIN_IDS = [int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip()]
# Получаем переменные окружения
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')

# Проверяем, что переменные заданы
if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
    raise ValueError(
        "YANDEX_API_KEY и YANDEX_FOLDER_ID должны быть заданы "
        "в файле .env или переменных окружения"
    )