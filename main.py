import asyncio
import urllib3
urllib3.disable_warnings()

from app import setup
from app.telegram.client import client, start_monitoring, process_new_message
from app.bot import bot, dp
from app.db import get_channels, get_db


async def initial_scan():
    """Собирает объявления при старте."""
    print("📡 Первичный сбор объявлений...")
    db = await get_db()
    channels = await get_channels()
    
    for channel in channels:
        try:
            new_count = 0
            messages = await client.get_messages(channel, limit=50)
            for msg in messages:
                text = msg.text or msg.raw_text or getattr(msg, 'caption', None)
                if text:
                    from types import SimpleNamespace
                    fake_event = SimpleNamespace()
                    fake_event.message = msg
                    fake_event.get_chat = lambda c=channel: client.get_entity(c)
                    await process_new_message(fake_event)
                    new_count += 1
            
            print(f"  ✅ {channel}: {new_count} обработано")
        except Exception as e:
            print(f"  ⚠️ {channel}: {e}")
    
    await db.close()


async def main() -> None:
    await setup()
    print("✅ База готова")

    await client.start()
    me = await client.get_me()
    print(f"✅ Telegram: {me.first_name}")

    await initial_scan()

    await start_monitoring()
    print("🔄 Мониторинг запущен")

    print("🤖 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())