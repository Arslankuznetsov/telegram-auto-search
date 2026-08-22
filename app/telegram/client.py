from telethon import TelegramClient, events
from app.config import API_ID, API_HASH
from app.db import get_db, get_channels
from app.parser import parse_listing

client = TelegramClient(
    'telegram.session', API_ID, API_HASH)


async def process_new_message(event):
    """Обрабатывает новое сообщение из канала."""
    message = event.message
    chat = await event.get_chat()
    
    text = message.text or message.raw_text or getattr(message, 'caption', None)
    if not text:
        return
    
    parsed = parse_listing(text)
    
    if chat.username:
        link = f"https://t.me/{chat.username}/{message.id}"
    else:
        link = f"https://t.me/c/{chat.id}/{message.id}"
    
    db = await get_db()
    try:
        await db.execute("""
            INSERT INTO listings (
                telegram_id, channel_username, message_id,
                raw_text, brand, model, year, price_rub, mileage_km, link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id, f"@{chat.username}" if chat.username else str(chat.id),
            message.id, text,
            parsed.get("brand"), parsed.get("model"), parsed.get("year"),
            parsed.get("price_rub"), parsed.get("mileage_km"),
            link
        ))
        await db.commit()
        
        brand_model = f"{parsed.get('brand') or '?'} {parsed.get('model') or ''}".strip()
        price = f"{parsed.get('price_rub'):,}₽" if parsed.get('price_rub') else "?₽"
        year = parsed.get('year') or "?"
        print(f"📥 {brand_model} | {year} г. | {price} | {link}")
        
    except Exception as e:
        if "UNIQUE constraint" not in str(e):
            print(f"⚠️ Ошибка сохранения: {e}")
    finally:
        await db.close()


async def start_monitoring():
    """Запускает мониторинг каналов из БД."""
    channels = await get_channels()
    for channel in channels:
        print(f"👂 Подписан на {channel}")
        client.add_event_handler(
            process_new_message,
            events.NewMessage(chats=channel)
        )
    print(f"✅ Мониторинг запущен ({len(channels)} каналов)")