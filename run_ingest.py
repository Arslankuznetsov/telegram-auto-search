import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).parent))

from app import setup
from app.telegram.client import client, process_new_message
from app.db import get_db, get_channels

LIVE_CHECK_INTERVAL = 5 * 60      # проверка новых каналов раз в 5 минут
RESCAN_INTERVAL = 2 * 60 * 60     # полное контрольное сканирование раз в 2 часа
MESSAGES_ON_RESCAN = 50           # сколько последних сообщений проверяем при контрольном сканировании
MESSAGES_ON_NEW_CHANNEL = 20      # сколько сообщений берём при добавлении нового канала


async def scan_channel(channel: str, limit: int, label: str = "скан"):
    """Сканирует последние limit сообщений канала и сохраняет новые."""
    print(f"📡 {label}: {channel}")
    db = await get_db()
    try:
        messages = await client.get_messages(channel, limit=limit)
        new_count = 0

        for msg in messages:
            text = msg.text or msg.raw_text or getattr(msg, 'caption', None)
            if not text:
                continue

            cursor = await db.execute(
                "SELECT id FROM listings WHERE channel_username = ? AND message_id = ?",
                (channel, msg.id)
            )
            exists = await cursor.fetchone()
            if exists:
                continue

            fake_event = SimpleNamespace()
            fake_event.message = msg
            fake_event.get_chat = lambda c=channel: client.get_entity(c)
            await process_new_message(fake_event)
            new_count += 1

        if new_count:
            print(f"  ✅ {channel}: {new_count} новых")
        else:
            print(f"  ➖ {channel}: нет новых")
    except Exception as e:
        print(f"  ⚠️ {channel}: {e}")
    finally:
        await db.close()


async def live_channel_worker():
    """Проверяет список каналов и подписывается на новые."""
    from telethon import events

    subscribed = set()

    while True:
        channels = await get_channels()
        current = set(channels)

        new_channels = current - subscribed

        for channel in new_channels:
            try:
                client.add_event_handler(
                    process_new_message,
                    events.NewMessage(chats=channel)
                )
                print(f"👂 Подписан на live-обновления: {channel}")

                await scan_channel(channel, limit=MESSAGES_ON_NEW_CHANNEL, label="новый канал")

            except Exception as e:
                print(f"⚠️ Ошибка подписки на {channel}: {e}")

                # Если канал не существует — удаляем его из базы
                if "No user has" in str(e):
                    from app.db import remove_channel
                    await remove_channel(channel.lstrip("@"))
                    print(f"🗑 Канал {channel} удалён из базы, так как не существует")

        subscribed = current
        await asyncio.sleep(LIVE_CHECK_INTERVAL)


async def periodic_rescan_worker():
    """Периодически перепроверяет последние сообщения всех каналов."""
    while True:
        print("🔄 Контрольное сканирование всех каналов...")
        channels = await get_channels()
        for channel in channels:
            await scan_channel(channel, limit=MESSAGES_ON_RESCAN, label="контроль")
        await asyncio.sleep(RESCAN_INTERVAL)


async def main():
    await setup()
    print("✅ База данных готова")

    await client.start()
    me = await client.get_me()
    print(f"✅ Telegram: {me.first_name}")

    # запускаем фоновые задачи
    asyncio.create_task(live_channel_worker())
    asyncio.create_task(periodic_rescan_worker())

    # держим Telethon активным
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())