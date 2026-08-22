from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from app.config import BOT_TOKEN, ADMIN_IDS
from app.db import get_db, add_channel, remove_channel, get_channels

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


TWO_WORD_BRANDS = [
    "land rover",
    "alfa romeo",
    "great wall",
    "li auto",
    "mercedes benz",
]


def parse_query(text: str):
    """Разбирает строку на марку и модель с учётом двухсловных марок."""
    words = text.split()

    if len(words) >= 2 and " ".join(words[:2]).lower() in TWO_WORD_BRANDS:
        brand = " ".join(words[:2])
        model = " ".join(words[2:]) if len(words) > 2 else None
    elif len(words) >= 2:
        brand = words[0]
        model = " ".join(words[1:])
    else:
        brand = words[0]
        model = None

    return brand, model


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"🚗 Поиск автомобилей из Telegram-каналов.\n\n"
        f"Ваш ID: {message.from_user.id}\n\n"
        f"🔍 /search <марка> <модель>\n"
        f"💰 /price <марка> <модель> — аналитика цен\n"
        f"📊 /stats — статистика\n"
        f"ℹ️ /help — помощь"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🚗 Поиск автомобилей из Telegram-каналов.\n\n"
        "🔍 Поиск:\n"
        "/search BMW X5\n"
        "/search Land Rover Discovery Sport\n\n"
        "🔍 С фильтрами:\n"
        "/search BMW X5 цена_от=1500000 год_от=2018\n\n"
        "💰 Аналитика:\n"
        "/price Toyota Camry\n"
        "/price Land Rover\n\n"
        "📊 /stats — статистика базы"
    )


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    text = message.text.replace("/search", "").strip()

    if not text:
        await message.answer(
            "❌ Укажите марку и модель.\n"
            "Например: /search BMW X5\n\n"
            "С фильтрами:\n"
            "/search BMW X5 цена_от=1500000 год_от=2018"
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

    brand, model = parse_query(query)

    db = await get_db()
    try:
        conditions = []
        params = []

        if model:
            conditions.append("LOWER(brand) = LOWER(?)")
            params.append(brand)
            conditions.append("LOWER(model) LIKE LOWER(?)")
            params.append(f"%{model}%")
        else:
            conditions.append("LOWER(brand) = LOWER(?)")
            params.append(brand)

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
            SELECT brand, model, year, price_rub, mileage_km,
                   engine, transmission, drive_type, region, link
            FROM listings
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT 10
        """, params)

        results = await cursor.fetchall()

        if not results:
            await message.answer(f"😔 По запросу «{query}» ничего не найдено.")
            return

        response = f"🔍 «{query}» — найдено {len(results)}:\n\n"

        for i, row in enumerate(results, 1):
            brand = row["brand"] or "?"
            model = row["model"] or ""
            year = f"{row['year']} г." if row["year"] else ""
            price = f"{row['price_rub']:,} ₽" if row["price_rub"] else "? ₽"
            mileage = f"{row['mileage_km']:,} км" if row["mileage_km"] else ""
            engine = row["engine"] or ""
            transmission = row["transmission"] or ""
            drive = row["drive_type"] or ""
            region = row["region"] or ""

            response += f"{i}. {brand} {model}\n"

            details = []
            if year:
                details.append(f"📅 {year}")
            if price:
                details.append(f"💰 {price}")
            if mileage:
                details.append(f"🛣 {mileage}")
            if engine:
                details.append(f"🔧 {engine}")
            if transmission:
                details.append(f"⚙️ {transmission}")
            if drive:
                details.append(f"🛞 {drive}")
            if region:
                details.append(f"📍 {region}")

            response += " | ".join(details) + "\n"
            response += f"🔗 {row['link']}\n\n"

        await message.answer(response)

    finally:
        await db.close()


@dp.message(Command("price"))
async def cmd_price(message: types.Message):
    text = message.text.replace("/price", "").strip()

    if not text:
        await message.answer(
            "❌ Укажите марку и модель.\n"
            "Например: /price BMW X5\n"
            "Или только марку: /price Toyota"
        )
        return

    brand, model = parse_query(text)

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

    await message.answer(f"✅ Канал {username} добавлен")


@dp.message(Command("remove_channel"))
async def cmd_remove_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Недостаточно прав")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите канал или номер из /channels.\n"
            "Например: /remove_channel @autosale\n"
            "Или: /remove_channel 2"
        )
        return

    value = parts[1]

    # Если передали номер — находим канал по номеру
    if value.isdigit():
        channels = await get_channels()
        idx = int(value) - 1
        if 0 <= idx < len(channels):
            await remove_channel(channels[idx])
            await message.answer(f"✅ Канал {channels[idx]} удалён")
        else:
            await message.answer("❌ Неверный номер канала.")
    else:
        await remove_channel(value)
        await message.answer(f"✅ Канал {value} удалён")


@dp.message(Command("channels"))
async def cmd_channels(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Недостаточно прав")
        return

    channels = await get_channels()
    if not channels:
        await message.answer("📡 Нет каналов.")
        return

    response = "📡 Каналы:\n"
    for i, ch in enumerate(channels, 1):
        response += f"{i}. {ch}\n"

    response += "\nУдаление: /remove_channel <номер>"

    await message.answer(response)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as total FROM listings")
        total = (await cursor.fetchone())["total"]

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT brand) as brands FROM listings WHERE brand IS NOT NULL"
        )
        brands = (await cursor.fetchone())["brands"]

        await message.answer(
            f"📊 Статистика:\n"
            f"• Всего объявлений: {total}\n"
            f"• Уникальных марок: {brands}"
        )
    finally:
        await db.close()


# Универсальный обработчик — в самом конце, чтобы не перехватывать команды
@dp.message()
async def on_any_message(message: types.Message):
    """Отвечает на любое непонятное сообщение подсказкой."""
    if message.text and not message.text.startswith("/"):
        await message.answer(
            "🚗 Отправь команду:\n\n"
            "🔍 /search BMW X5 — поиск\n"
            "💰 /price Toyota Camry — аналитика\n"
            "ℹ️ /help — все команды"
        )