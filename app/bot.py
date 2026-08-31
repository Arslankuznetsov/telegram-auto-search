from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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

BRAND_ALIASES = {
    "кия": "Kia", "киа": "Kia", "хендай": "Hyundai", "хёндай": "Hyundai",
    "хундай": "Hyundai", "тойота": "Toyota", "бмв": "BMW",
    "мерседес": "Mercedes-Benz", "мерс": "Mercedes-Benz",
    "фольксваген": "Volkswagen", "фольцваген": "Volkswagen",
    "шевроле": "Chevrolet", "хонда": "Honda", "ниссан": "Nissan",
    "митсубиси": "Mitsubishi", "мицубиси": "Mitsubishi", "мазда": "Mazda",
    "субару": "Subaru", "лексус": "Lexus", "ауди": "Audi", "шкода": "Skoda",
    "рено": "Renault", "пежо": "Peugeot", "ситроен": "Citroen",
    "опель": "Opel", "форд": "Ford", "лада": "Lada", "газ": "ГАЗ",
    "уаз": "УАЗ", "джили": "Geely", "чери": "Chery", "хавал": "Haval",
    "чанган": "Changan", "чанъань": "Changan", "лифан": "Lifan",
    "джетур": "Jetour", "омода": "Omoda", "эксид": "Exeed",
    "лисян": "Li Auto", "воях": "Voyah", "зикр": "Zeekr",
}


def transliterate(text: str) -> str:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
        "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    }
    result = []
    for ch in text.lower():
        result.append(mapping.get(ch, ch))
    return "".join(result)


def parse_query(text: str):
    """Разбирает строку на марку и модель с учётом русских названий."""
    words = text.split()
    if not words:
        return None, None

    first_lower = words[0].lower()
    if first_lower in BRAND_ALIASES:
        brand = BRAND_ALIASES[first_lower]
        model_words = words[1:]
    elif len(words) >= 2 and " ".join(words[:2]).lower() in BRAND_ALIASES:
        brand = BRAND_ALIASES[" ".join(words[:2]).lower()]
        model_words = words[2:]
    elif len(words) >= 2 and " ".join(words[:2]).lower() in TWO_WORD_BRANDS:
        brand = " ".join(words[:2])
        model_words = words[2:]
    elif len(words) >= 2:
        brand = words[0]
        model_words = words[1:]
    else:
        brand = words[0]
        model_words = []

    model = " ".join(model_words) if model_words else None
    if model and any("а" <= ch <= "я" or "ё" <= ch <= "ё" for ch in model.lower()):
        model = transliterate(model)

    return brand, model


def parse_mileage(text: str) -> int | None:
    """Понимает: 50000, 50 тыс, 50к, 50k"""
    text = text.strip().lower().replace(" ", "")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    # убираем "тыс", "к", "k"
    if "тыс" in text or text.endswith("к") or text.endswith("k"):
        text = text.replace("тыс", "").replace("к", "").replace("k", "")
        try:
            return int(float(text.replace(",", ".")) * 1000)
        except ValueError:
            return None
    return None


def parse_price(text: str) -> int | None:
    """Понимает: 1500000, 1.5 млн, 1,5 млн, 1.5м"""
    text = text.strip().lower().replace(" ", "")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "млн" in text or text.endswith("м"):
        text = text.replace("млн", "").replace("м", "")
        try:
            return int(float(text.replace(",", ".")) * 1_000_000)
        except ValueError:
            return None
    return None


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/search"), KeyboardButton(text="/price")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/help")],
        [KeyboardButton(text="/stats")],
    ],
    resize_keyboard=True,
    persistent=True,
)


class SearchState(StatesGroup):
    waiting_for_query = State()
    waiting_for_mileage = State()
    waiting_for_price = State()
    waiting_for_price_query = State()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"🚗 Поиск автомобилей из Telegram-каналов.\n\n"
        f"Ваш ID: {message.from_user.id}\n\n"
        f"🔍 /search — поиск по марке и модели\n"
        f"📚 /catalog — выбрать из каталога\n"
        f"💰 /price — аналитика цен\n"
        f"📊 /stats — статистика\n"
        f"ℹ️ /help — помощь",
        reply_markup=main_keyboard,
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🚗 Поиск автомобилей из Telegram-каналов.\n\n"
        "🔍 Поиск:\n"
        "1. Нажми /search\n"
        "2. Введи марку и модель (можно по-русски: кия к5)\n"
        "3. Введи максимальный пробег (например, 50000 или 'нет')\n"
        "4. Введи максимальную цену (например, 1500000 или 'до 1,5 млн')\n\n"
        "📚 Каталог:\n"
        "Нажми /catalog и выбери марку, затем модель.\n\n"
        "💰 Аналитика:\n"
        "Нажми /price и введи марку/модель.\n\n"
        "📊 /stats — статистика базы",
        reply_markup=main_keyboard,
    )


async def execute_search(message: types.Message, query: str, mileage_max=None, price_max=None):
    brand, model = parse_query(query)

    db = await get_db()
    try:
        conditions = []
        params = []

        if brand:
            conditions.append("LOWER(brand) = LOWER(?)")
            params.append(brand)
        if model:
            conditions.append("LOWER(model) LIKE LOWER(?)")
            params.append(f"%{model}%")

        if mileage_max is not None:
            conditions.append("mileage_km <= ?")
            params.append(mileage_max)
        if price_max is not None:
            conditions.append("price_rub <= ?")
            params.append(price_max)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

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


async def execute_price(message: types.Message, text: str):
    text = text.strip()
    if not text:
        await message.answer("❌ Введите марку и модель. Например: кия к5")
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


# === Каталог ===

@dp.message(Command("catalog"))
async def cmd_catalog(message: types.Message):
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT brand, COUNT(*) as cnt
            FROM listings
            WHERE brand IS NOT NULL
            GROUP BY LOWER(brand)
            ORDER BY LOWER(brand)
        """)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        await message.answer("📚 Каталог пока пуст.")
        return

    brands_with_counts = {}
    for row in rows:
        brand = row["brand"]
        cnt = row["cnt"]
        key = brand.lower()
        if key not in brands_with_counts:
            brands_with_counts[key] = {"brand": brand, "cnt": cnt}
        else:
            brands_with_counts[key]["cnt"] += cnt

    sorted_brands = sorted(brands_with_counts.values(), key=lambda x: x["brand"].lower())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in sorted_brands:
        brand = item["brand"]
        cnt = item["cnt"]
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=f"{brand} ({cnt})", callback_data=f"brand:{brand}")]
        )

    await message.answer("📚 Выберите марку:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("brand:"))
async def process_brand_callback(callback: types.CallbackQuery):
    brand = callback.data.split(":", 1)[1]

    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT model, COUNT(*) as cnt
            FROM listings
            WHERE brand = ? AND model IS NOT NULL
            GROUP BY LOWER(model)
            ORDER BY LOWER(model)
        """, (brand,))
        rows = await cursor.fetchall()
    finally:
        await db.close()

    await callback.answer()

    if not rows:
        await callback.message.answer(f"Нет моделей для {brand}")
        return

    models_with_counts = {}
    for row in rows:
        model = row["model"]
        cnt = row["cnt"]
        key = model.lower()
        if key not in models_with_counts:
            models_with_counts[key] = {"model": model, "cnt": cnt}
        else:
            models_with_counts[key]["cnt"] += cnt

    sorted_models = sorted(models_with_counts.values(), key=lambda x: x["model"].lower())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in sorted_models:
        model = item["model"]
        cnt = item["cnt"]
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=f"{model} ({cnt})", callback_data=f"model:{brand}:{model}")]
        )

    await callback.message.answer(f"🚗 {brand} — выберите модель:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("model:"))
async def process_model_callback(callback: types.CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка")
        return

    brand = parts[1]
    model = parts[2]
    await callback.answer()

    await execute_search(callback.message, f"{brand} {model}")


# === Поиск и цена ===

@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    text = message.text.replace("/search", "").strip()
    if text:
        await execute_search(message, text)
    else:
        await message.answer("🔍 Введите марку и модель.\nНапример: кия к5")
        await state.set_state(SearchState.waiting_for_query)


@dp.message(SearchState.waiting_for_query)
async def process_query(message: types.Message, state: FSMContext):
    query = message.text.strip()
    await state.update_data(query=query)
    await message.answer("Максимальный пробег? (например, 50000 или напишите 'нет')")
    await state.set_state(SearchState.waiting_for_mileage)


@dp.message(SearchState.waiting_for_mileage)
async def process_mileage(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ("нет", "не важно", "-", "пропустить"):
        mileage_max = None
    else:
        mileage_max = parse_mileage(text)

    await state.update_data(mileage_max=mileage_max)
    await message.answer("Максимальная цена? (например, 1500000 или 'до 1,5 млн')")
    await state.set_state(SearchState.waiting_for_price)


@dp.message(SearchState.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    if text in ("нет", "не важно", "-", "пропустить"):
        price_max = None
    else:
        price_max = parse_price(text)

    data = await state.get_data()
    query = data.get("query", "")
    mileage_max = data.get("mileage_max")
    await state.clear()
    await execute_search(message, query, mileage_max, price_max)


@dp.message(Command("price"))
async def cmd_price(message: types.Message, state: FSMContext):
    text = message.text.replace("/price", "").strip()
    if text:
        await execute_price(message, text)
    else:
        await message.answer("💰 Введите марку и модель.\nНапример: кия к5 или toyota camry")
        await state.set_state(SearchState.waiting_for_price_query)


@dp.message(SearchState.waiting_for_price_query)
async def process_price_query(message: types.Message, state: FSMContext):
    await state.clear()
    await execute_price(message, message.text)


# === Админские команды ===

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


@dp.message()
async def on_any_message(message: types.Message):
    if message.text and not message.text.startswith("/"):
        await message.answer(
            "🚗 Отправь команду:\n\n"
            "🔍 /search BMW X5 — поиск\n"
            "📚 /catalog — каталог\n"
            "💰 /price Toyota Camry — аналитика\n"
            "ℹ️ /help — все команды",
            reply_markup=main_keyboard,
        )