import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app import setup
from app.bot import bot, dp


async def main():
    await setup()
    print("✅ База данных готова")
    print("🤖 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())