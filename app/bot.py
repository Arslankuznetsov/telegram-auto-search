from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from app.config import BOT_TOKEN
from app.db import get_db

from app.db import get_db, add_channel, remove_channel, get_channels
from app.config import ADMIN_IDS

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"🚗 Поиск автомобилей из Telegram-каналов.\n\n"
        f"Ваш ID: {message.from_user.id}\n\n"
        f"🔍 /search <марка> <модель>\n"
        f"📊 /stats"
        f"📊 /price <марка> <модель> — аналитика цен\n"
    )


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    text = message.text.replace("/search", "").strip()
    
    if not text:
        await message.answer(
            "❌ Укажите марку и модель.\n"
            "Например: /search BMW X5\n\n"
            "С фильтрами: /search BMW X5 цена_от=1500000 год_от=2018"
        )
        return
    
    filters = {}
    query_parts = []
    
    for word in text.split():
        if "=" in word:
            key, value = word.split("=", 1)
            try:
                filters[key] = int(value.replace(" ", ""))
            except ValueError:
                query_parts.append(word)
        else:
            query_parts.append(word)
    
    query = " ".join(query_parts)
    
    if not query:
        await message.answer("❌ Укажите марку для поиска.")
        return
    
    db = await get_db()
    try:
        conditions = []
        params = []
        
        words = query.split()
        if len(words) >= 2:
            brand = words[0]
            model = " ".join(words[1:])
            conditions.append("LOWER(brand) = LOWER(?)")
            params.append(brand)
            conditions.append("LOWER(model) LIKE LOWER(?)")
            params.append(f"%{model}%")
        else:
            conditions.append("(LOWER(brand) = LOWER(?) OR LOWER(model) LIKE LOWER(?))")
            params.append(words[0])
            params.append(f"%{words[0]}%")
        
        if "цена_от" in filters:
            conditions.append("price_rub >= ?")
            params.append(filters["цена_от"])
        if "цена_до" in filters:
            conditions.append("price_rub <= ?")
            params.append(filters["цена_до"])
        if "год_от" in filters:
            conditions.append("year >= ?")
            params.append(filters["год_от"])
        if "год_до" in filters:
            conditions.append("year <= ?")
            params.append(filters["год_до"])
        
        where_clause = " AND ".join(conditions)
        
        cursor = await db.execute(f"""
            SELECT brand, model, year, price_rub, mileage_km, link
            FROM listings
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT 10
        """, params)
        results = await cursor.fetchall()
        
        if not results:
            filter_desc = []
            if "цена_от" in filters:
                filter_desc.append(f"цена от {filters['цена_от']:,} ₽")
            if "цена_до" in filters:
                filter_desc.append(f"цена до {filters['цена_до']:,} ₽")
            if "год_от" in filters:
                filter_desc.append(f"год от {filters['год_от']}")
            if "год_до" in filters:
                filter_desc.append(f"год до {filters['год_до']}")
            
            filter_text = ", ".join(filter_desc) if filter_desc else ""
            await message.answer(
                f"😔 По запросу «{query}»"
                f"{(' (' + filter_text + ')') if filter_text else ''} ничего не найдено."
            )
            return
        
        filter_desc = []
        if "цена_от" in filters:
            filter_desc.append(f"цена от {filters['цена_от']:,} ₽")
        if "цена_до" in filters:
            filter_desc.append(f"цена до {filters['цена_до']:,} ₽")
        if "год_от" in filters:
            filter_desc.append(f"год от {filters['год_от']}")
        if "год_до" in filters:
            filter_desc.append(f"год до {filters['год_до']}")
        
        filter_text = (" | " + ", ".join(filter_desc)) if filter_desc else ""
        response = f"🔍 «{query}»{filter_text} — найдено {len(results)}:\n\n"
        
        for i, row in enumerate(results, 1):
            brand = row["brand"] or "?"
            model = row["model"] or ""
            year = f"{row['year']} г." if row["year"] else ""
            price = f"{row['price_rub']:,} ₽" if row["price_rub"] else "? ₽"
            mileage = f"{row['mileage_km']:,} км" if row["mileage_km"] else ""
            
            response += f"{i}. {brand} {model}\n"
            details = []
            if year:
                details.append(f"📅 {year}")
            if price:
                details.append(f"💰 {price}")
            if mileage:
                details.append(f"🛣 {mileage}")
            response += " | ".join(details) + "\n"
            response += f"🔗 {row['link']}\n\n"
        
        await message.answer(response)
        
    finally:
        await db.close()

@dp.message(Command("add_channel"))
async def cmd_add_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Недостаточно прав")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите канал.\nНапример: /add_channel @autosale")
        return
    
    username = parts[1]
    await add_channel(username)
    
    # Подписываемся на канал в реальном времени
    from app.telegram.client import client
    from telethon import events
    from app.telegram.client import process_new_message
    
    client.add_event_handler(
        process_new_message,
        events.NewMessage(chats=username)
    )
    
    await message.answer(f"✅ Канал {username} добавлен и мониторится")


@dp.message(Command("remove_channel"))
async def cmd_remove_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Недостаточно прав")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите канал.\nНапример: /remove_channel @autosale")
        return
    
    username = parts[1]
    await remove_channel(username)
    await message.answer(f"✅ Канал {username} удалён")


@dp.message(Command("channels"))
async def cmd_channels(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Недостаточно прав")
        return
    
    channels = await get_channels()
    if not channels:
        await message.answer("📡 Нет каналов.")
        return
    
    response = "📡 Каналы:\n" + "\n".join(f"• {ch}" for ch in channels)
    await message.answer(response)
@dp.message(Command("price"))
async def cmd_price(message: types.Message):
    """Показывает аналитику цен."""
    text = message.text.replace("/price", "").strip()
    
    if not text:
        await message.answer(
            "❌ Укажите марку и модель.\n"
            "Например: /price BMW X5\n"
            "Или только марку: /price Toyota"
        )
        return
    
    words = text.split()
    brand = words[0]
    model = " ".join(words[1:]) if len(words) > 1 else None
    
    from app.db import get_price_stats
    stats = await get_price_stats(brand, model)
    
    if not stats:
        await message.answer(f"😔 Нет данных по {text}")
        return
    
    response = (
        f"📊 Аналитика цен: {text}\n\n"
        f"• Объявлений: {stats['count']}\n"
        f"• Средняя цена: {stats['avg']:,} ₽\n"
        f"• Медиана: {stats['median']:,} ₽\n"
        f"• Диапазон: {stats['min']:,} — {stats['max']:,} ₽"
    )
    
    await message.answer(response)    
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as total FROM listings")
        total = (await cursor.fetchone())["total"]
        
        cursor = await db.execute("SELECT COUNT(DISTINCT brand) as brands FROM listings WHERE brand IS NOT NULL")
        brands = (await cursor.fetchone())["brands"]
        
        await message.answer(
            f"📊 Статистика:\n"
            f"• Всего объявлений: {total}\n"
            f"• Уникальных марок: {brands}"
        )
    finally:
        await db.close()