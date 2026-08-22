import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app import setup
from app.telegram.client import client, start_monitoring, process_new_message
from app.db import get_db, get_channels


async def initial_scan():
    """Собирает последние объявления при старте."""
    print("📡 Начальное сканирование каналов...")
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


async def main():
    await setup()
    print("✅ База данных готова")

    await client.start()
    me = await client.get_me()
    print(f"✅ Telegram: {me.first_name}")

    await initial_scan()

    await start_monitoring()
    print("🔄 Мониторинг запущен")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())