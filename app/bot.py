import re

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.config import BOT_TOKEN, ADMIN_IDS
from app.db import get_db, add_channel, remove_channel, get_channels, save_user, get_users_count

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
    text = text.strip().lower().replace(" ", "")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "тыс" in text or text.endswith("к") or text.endswith("k"):
        text = text.replace("тыс", "").replace("к", "").replace("k", "")
        try:
            return int(float(text.replace(",", ".")) * 1000)
        except ValueError:
            return None
    return None


def parse_price(text: str) -> int | None:
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


MAIN_MENU_TEXT = "Главное меню"
CANCEL_TEXT = "Отмена"


def build_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/search"), KeyboardButton(text="/price")],
            [KeyboardButton(text="/catalog"), KeyboardButton(text="/help")],
            [KeyboardButton(text="/stats"), KeyboardButton(text=MAIN_MENU_TEXT)],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def build_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


main_keyboard = build_main_keyboard()
cancel_keyboard = build_cancel_keyboard()


class SearchState(StatesGroup):
    waiting_for_query = State()
    waiting_for_filter = State()
    waiting_for_mileage_filter = State()
    waiting_for_price_filter = State()
    waiting_for_year_filter = State()
    waiting_for_price_query = State()


def build_search_filter_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пробег"), KeyboardButton(text="Цена")],
            [KeyboardButton(text="Год"), KeyboardButton(text="Поиск")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def parse_year_filters(text: str):
    normalized = text.lower().strip()
    if not normalized:
        return None, None

    year_from = None
    year_to = None

    patterns = [
        ("year_from", r"(?:year[_\-\s]*from|year[_\-\s]*ot|year[_\-\s]*от|год[_\-\s]*от|from|от)\s*[:=]?\s*(\d{4})"),
        ("year_to", r"(?:year[_\-\s]*to|year[_\-\s]*do|year[_\-\s]*до|год[_\-\s]*до|to|до)\s*[:=]?\s*(\d{4})"),
    ]

    for key, pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            value = int(match.group(1))
            if key == "year_from":
                year_from = value
            else:
                year_to = value

    if year_from is None and year_to is None:
        range_match = re.search(r"(\d{4})\s*(?:-|–|—)\s*(\d{4})", normalized)
        if range_match:
            return int(range_match.group(1)), int(range_match.group(2))

    return year_from, year_to


def strip_year_filters(text: str) -> str:
    normalized = text
    for pattern in [
        r"\s*(?:year[_\-\s]*from|year[_\-\s]*ot|year[_\-\s]*от|год[_\-\s]*от|from|от)\s*[:=]?\s*\d{4}",
        r"\s*(?:year[_\-\s]*to|year[_\-\s]*do|year[_\-\s]*до|год[_\-\s]*до|to|до)\s*[:=]?\s*\d{4}",
        r"\s*\d{4}\s*(?:-|–|—)\s*\d{4}",
    ]:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


def parse_filter_value(raw_text: str, kind: str):
    text = raw_text.strip().lower()
    if not text or text in ("нет", "не важно", "без ограничений", "-", "пропустить"):
        return None

    if kind == "mileage":
        return parse_mileage(text.replace("до ", "").replace("до", ""))
    if kind == "price":
        return parse_price(text.replace("до ", "").replace("до", ""))
    if kind == "year":
        year_from, year_to = parse_year_filters(text)
        if year_from is not None or year_to is not None:
            return year_from, year_to
        if text.isdigit() and len(text) == 4:
            return int(text), int(text)
        if re.search(r"\d{4}\s*(?:-|–|—)\s*\d{4}", text):
            m = re.search(r"(\d{4})\s*(?:-|–|—)\s*(\d{4})", text)
            return int(m.group(1)), int(m.group(2))
        return None
    return None


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await save_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    name = message.from_user.first_name or message.from_user.username or "друг"
    await message.answer(
        f"🚗 Привет, {name}! Я бот для поиска автомобилей в Telegram-каналах.\n\n"
        "Я помогаю быстро находить объявления по марке, модели, пробегу и цене, "
        "смотрю статистику по рынку и подсказываю, где искать подходящие варианты.\n\n"
        "Что можно делать:\n"
        "🔍 /search — быстрый поиск по объявлениям\n"
        "📚 /catalog — выбор марки и модели из каталога\n"
        "💰 /price — анализ цен по запросу\n"
        "📊 /stats — статистика базы\n"
        "ℹ️ /help — подробная инструкция",
        reply_markup=main_keyboard,
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🚗 Помощь по боту\n\n"
        "🔍 Поиск объявлений\n"
        "1. Нажмите /search или кнопку /search.\n"
        "2. Введите марку и модель, например: кия к5, bmw x5, toyota camry.\n"
        "3. Укажите максимум пробега: 200000, 50 тыс, 80k или 'нет'.\n"
        "4. Укажите максимальную цену: 1500000, 1.5 млн или 'нет'.\n"
        "5. Подтвердите или укажите год: год_от=2018 и год_до=2022.\n\n"
        "Примеры запросов:\n"
        "• /search kia k5\n"
        "• /search bmw x5 mileage=120000 price=2500000\n"
        "• /search toyota camry year_from=2018 year_to=2022\n"
        "• /search год_от=2020 год_до=2023 kia sportage\n\n"
        "📚 Каталог\n"
        "Команда /catalog показывает список марок. Нажмите на марку, и в этом же сообщении появятся модели.\n"
        "Кнопка '← Назад' возвращает к списку марок.\n\n"
        "💰 Аналитика цен\n"
        "Команда /price строит среднюю цену, медиану и диапазон по выбранной марке/модели.\n"
        "Примеры: /price kia k5, /price toyota camry.\n\n"
        "📊 Статистика\n"
        "Команда /stats показывает количество объявлений и базовые метрики.\n\n"
        "✅ Во время ввода вы увидите только кнопку 'Отмена'. После завершения бот возвращает основную клавиатуру.",
        reply_markup=main_keyboard,
    )


async def execute_search(message: types.Message, query: str, mileage_max=None, price_max=None, year_from=None, year_to=None, exact_model: bool = False):
    raw_query = (query or "").strip()
    if not raw_query:
        await message.answer("❌ Введите запрос. Например: кия к5", reply_markup=main_keyboard)
        return

    if year_from is None or year_to is None:
        free_year_from, free_year_to = parse_year_filters(raw_query)
        if year_from is None:
            year_from = free_year_from
        if year_to is None:
            year_to = free_year_to

    clean_query = strip_year_filters(raw_query)
    brand, model = parse_query(clean_query or raw_query)

    db = await get_db()
    try:
        conditions = []
        params = []

        if brand:
            conditions.append("LOWER(brand) = LOWER(?)")
            params.append(brand)
        if model:
            if exact_model:
                conditions.append("LOWER(TRIM(model)) = LOWER(?)")
                params.append(model.strip())
            else:
                conditions.append("LOWER(model) LIKE LOWER(?)")
                params.append(f"%{model.strip()}%")

        if mileage_max is not None:
            conditions.append("mileage_km <= ?")
            params.append(mileage_max)
        if price_max is not None:
            conditions.append("price_rub <= ?")
            params.append(price_max)
        if year_from is not None:
            conditions.append("year >= ?")
            params.append(year_from)
        if year_to is not None:
            conditions.append("year <= ?")
            params.append(year_to)

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
            await message.answer(f"😔 По запросу «{clean_query or raw_query}» ничего не найдено.", reply_markup=main_keyboard)
            return

        response = f"🔍 «{clean_query or raw_query}» — найдено {len(results)}:\n\n"

        for i, row in enumerate(results, 1):
            brand_name = row["brand"] or "?"
            model_name = row["model"] or ""
            year = f"{row['year']} г." if row["year"] else ""
            price = f"{row['price_rub']:,} ₽" if row["price_rub"] else "? ₽"
            mileage = f"{row['mileage_km']:,} км" if row["mileage_km"] else ""
            engine = row["engine"] or ""
            transmission = row["transmission"] or ""
            drive = row["drive_type"] or ""
            region = row["region"] or ""

            response += f"{i}. {brand_name} {model_name}\n"

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

        await message.answer(response, reply_markup=main_keyboard)

    finally:
        await db.close()


async def execute_price(message: types.Message, text: str):
    text = text.strip()
    if not text:
        await message.answer("❌ Введите марку и модель. Например: кия к5", reply_markup=main_keyboard)
        return

    year_from, year_to = parse_year_filters(text)
    clean_text = strip_year_filters(text)
    brand, model = parse_query(clean_text or text)

    from app.db import get_price_stats

    stats = await get_price_stats(brand, model, year_from=year_from, year_to=year_to)

    if not stats:
        await message.answer(f"😔 Нет данных по {clean_text or text}", reply_markup=main_keyboard)
        return

    response = (
        f"📊 Аналитика цен: {clean_text or text}\n\n"
        f"• Объявлений: {stats['count']}\n"
        f"• Средняя цена: {stats['avg']:,} ₽\n"
        f"• Медиана: {stats['median']:,} ₽\n"
        f"• Диапазон: {stats['min']:,} — {stats['max']:,} ₽"
    )

    if year_from is not None or year_to is not None:
        response += f"\n\n📅 Фильтр по году: {year_from or '—'} — {year_to or '—'}"

    await message.answer(response, reply_markup=main_keyboard)


@dp.message(Command("catalog"))
async def cmd_catalog(message: types.Message):
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT brand, COUNT(*) as cnt
            FROM listings
            WHERE brand IS NOT NULL AND model IS NOT NULL
            GROUP BY LOWER(TRIM(brand))
            ORDER BY LOWER(TRIM(brand))
        """)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        await message.answer("📚 Каталог пока пуст.", reply_markup=main_keyboard)
        return

    unique = {}
    for row in rows:
        brand = row["brand"].strip()
        cnt = row["cnt"]
        key = brand.lower()
        if key not in unique:
            unique[key] = {"brand": brand, "cnt": cnt}
        else:
            unique[key]["cnt"] += cnt

    sorted_brands = sorted(unique.values(), key=lambda x: x["brand"].lower())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in sorted_brands:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=f"{item['brand']} ({item['cnt']})", callback_data=f"brand:{item['brand']}")]
        )

    await message.answer("📚 Выберите марку:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("brand:"))
async def process_brand_callback(callback: types.CallbackQuery):
    brand = callback.data.split(":", 1)[1]

    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT TRIM(model) as model, COUNT(*) as cnt
            FROM listings
            WHERE LOWER(TRIM(brand)) = LOWER(?) AND model IS NOT NULL
            GROUP BY LOWER(TRIM(model))
            ORDER BY LOWER(TRIM(model))
        """, (brand,))
        rows = await cursor.fetchall()
    finally:
        await db.close()

    await callback.answer()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="catalog:back")]])
    if not rows:
        await callback.message.edit_text(f"🚗 {brand}\n\nНет доступных моделей.", reply_markup=keyboard)
        return

    for row in rows:
        model = row["model"].strip()
        cnt = row["cnt"]
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=f"{model} ({cnt})", callback_data=f"model:{brand}:{model}")]
        )

    await callback.message.edit_text(f"🚗 {brand} — выберите модель:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == "catalog:back")
async def process_catalog_back(callback: types.CallbackQuery):
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT brand, COUNT(*) as cnt
            FROM listings
            WHERE brand IS NOT NULL AND model IS NOT NULL
            GROUP BY LOWER(TRIM(brand))
            ORDER BY LOWER(TRIM(brand))
        """)
        rows = await cursor.fetchall()
    finally:
        await db.close()

    unique = {}
    for row in rows:
        brand = row["brand"].strip()
        cnt = row["cnt"]
        key = brand.lower()
        if key not in unique:
            unique[key] = {"brand": brand, "cnt": cnt}
        else:
            unique[key]["cnt"] += cnt

    sorted_brands = sorted(unique.values(), key=lambda x: x["brand"].lower())
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for item in sorted_brands:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{item['brand']} ({item['cnt']})", callback_data=f"brand:{item['brand']}")
        ])

    await callback.answer()
    await callback.message.edit_text("📚 Выберите марку:", reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("model:"))
async def process_model_callback(callback: types.CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка")
        return

    brand = parts[1]
    model = parts[2].strip()
    await callback.answer()

    await execute_search(callback.message, f"{brand} {model}", exact_model=True)


@dp.message(Command("search"))
async def cmd_search(message: types.Message, state: FSMContext):
    text = message.text.replace("/search", "").strip()
    if text:
        await state.update_data(query=text, mileage_max=None, price_max=None, year_from=None, year_to=None)
        await message.answer(
            "🔍 Выберите фильтр или введите значение вручную.\n\n"
            "Доступно: Пробег, Цена, Год, Поиск",
            reply_markup=build_search_filter_keyboard(),
        )
        await state.set_state(SearchState.waiting_for_filter)
    else:
        await message.answer("🔍 Введите марку и модель.\nНапример: кия к5 или BMW X5", reply_markup=cancel_keyboard)
        await state.set_state(SearchState.waiting_for_query)


@dp.message(SearchState.waiting_for_query)
async def process_query(message: types.Message, state: FSMContext):
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_keyboard)
        return

    query = message.text.strip()
    await state.update_data(query=query, mileage_max=None, price_max=None, year_from=None, year_to=None)
    await message.answer(
        "🔍 Выберите фильтр или введите значение вручную.\n\n"
        "Доступно: Пробег, Цена, Год, Поиск",
        reply_markup=build_search_filter_keyboard(),
    )
    await state.set_state(SearchState.waiting_for_filter)


async def finish_search(message: types.Message, state: FSMContext):
    data = await state.get_data()
    query = data.get("query", "")
    mileage_max = data.get("mileage_max")
    price_max = data.get("price_max")
    year_from = data.get("year_from")
    year_to = data.get("year_to")
    await state.clear()
    await execute_search(message, query, mileage_max, price_max, year_from, year_to)


@dp.message(SearchState.waiting_for_filter)
async def process_search_filter(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_keyboard)
        return

    if text == "Пробег":
        await message.answer(
            "📏 Введите максимум пробега или один из вариантов:\n"
            "• до 50 тыс\n"
            "• до 100 тыс\n"
            "• до 200 тыс\n"
            "• 70000",
            reply_markup=build_search_filter_keyboard(),
        )
        await state.set_state(SearchState.waiting_for_mileage_filter)
        return

    if text == "Цена":
        await message.answer(
            "💰 Введите максимальную цену или один из вариантов:\n"
            "• до 1 млн\n"
            "• до 2 млн\n"
            "• до 3 млн\n"
            "• 1500000",
            reply_markup=build_search_filter_keyboard(),
        )
        await state.set_state(SearchState.waiting_for_price_filter)
        return

    if text == "Год":
        await message.answer(
            "📅 Введите год или диапазон:\n"
            "• от 2018\n"
            "• до 2022\n"
            "• 2018-2022\n"
            "• 2020",
            reply_markup=build_search_filter_keyboard(),
        )
        await state.set_state(SearchState.waiting_for_year_filter)
        return

    if text == "Поиск":
        data = await state.get_data()
        query = data.get("query", "")
        if not query:
            await message.answer("🔍 Сначала укажите марку и модель.", reply_markup=build_search_filter_keyboard())
            return
        await finish_search(message, state)
        return

    await message.answer(
        "⚠️ Используйте кнопки: Пробег, Цена, Год, Поиск.\n"
        "Или введите значение после выбора фильтра.",
        reply_markup=build_search_filter_keyboard(),
    )


@dp.message(SearchState.waiting_for_mileage_filter)
async def process_mileage_filter(message: types.Message, state: FSMContext):
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_keyboard)
        return

    value = parse_filter_value(message.text, "mileage")
    if value is None:
        await message.answer("⚠️ Введите корректный пробег, например: 70000, 50 тыс или 'без ограничений'.", reply_markup=build_search_filter_keyboard())
        return

    await state.update_data(mileage_max=value)
    await message.answer(f"✅ Пробег: до {value:,} км", reply_markup=build_search_filter_keyboard())
    await state.set_state(SearchState.waiting_for_filter)


@dp.message(SearchState.waiting_for_price_filter)
async def process_price_filter(message: types.Message, state: FSMContext):
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_keyboard)
        return

    value = parse_filter_value(message.text, "price")
    if value is None:
        await message.answer("⚠️ Введите корректную цену, например: 1500000, 1.5 млн или 'без ограничений'.", reply_markup=build_search_filter_keyboard())
        return

    await state.update_data(price_max=value)
    await message.answer(f"✅ Цена: до {value:,} ₽", reply_markup=build_search_filter_keyboard())
    await state.set_state(SearchState.waiting_for_filter)


@dp.message(SearchState.waiting_for_year_filter)
async def process_year_filter(message: types.Message, state: FSMContext):
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Поиск отменён.", reply_markup=main_keyboard)
        return

    result = parse_filter_value(message.text, "year")
    if result is None:
        await message.answer("⚠️ Введите год или диапазон, например: 2018, 2020, 2018-2022 или 'от 2018 до 2022'.", reply_markup=build_search_filter_keyboard())
        return

    year_from, year_to = result
    await state.update_data(year_from=year_from, year_to=year_to)
    if year_from == year_to:
        await message.answer(f"✅ Год: {year_from}", reply_markup=build_search_filter_keyboard())
    else:
        await message.answer(f"✅ Год: {year_from} — {year_to}", reply_markup=build_search_filter_keyboard())
    await state.set_state(SearchState.waiting_for_filter)


@dp.message(Command("price"))
async def cmd_price(message: types.Message, state: FSMContext):
    text = message.text.replace("/price", "").strip()
    if text:
        await execute_price(message, text)
    else:
        await message.answer("💰 Введите марку и модель.\nНапример: кия к5 или toyota camry", reply_markup=cancel_keyboard)
        await state.set_state(SearchState.waiting_for_price_query)


@dp.message(SearchState.waiting_for_price_query)
async def process_price_query(message: types.Message, state: FSMContext):
    if message.text == CANCEL_TEXT:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard)
        return

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

        users = await get_users_count()

        await message.answer(
            f"📊 Статистика:\n"
            f"• Всего объявлений: {total}\n"
            f"• Уникальных марок: {brands}\n"
            f"• Пользователей: {users}"
        )
    finally:
        await db.close()


@dp.message(lambda message: message.text == MAIN_MENU_TEXT)
async def cmd_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await save_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    name = message.from_user.first_name or message.from_user.username or "друг"
    await message.answer(
        f"🚗 Главное меню\n\nПривет, {name}! Я помогу быстро искать автомобили и смотреть аналитику.\n\n"
        "🔍 /search — поиск по объявлениям\n"
        "📚 /catalog — каталог по маркам и моделям\n"
        "💰 /price — аналитика цен\n"
        "📊 /stats — статистика\n"
        "ℹ️ /help — помощь",
        reply_markup=main_keyboard,
    )


@dp.message(lambda message: message.text == CANCEL_TEXT)
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_keyboard)


@dp.message()
async def on_any_message(message: types.Message):
    if message.text and not message.text.startswith("/"):
        await save_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
        await message.answer(
            "🚗 Отправь команду:\n\n"
            "🔍 /search BMW X5 — поиск\n"
            "📚 /catalog — каталог\n"
            "💰 /price Toyota Camry — аналитика\n"
            "ℹ️ /help — все команды",
            reply_markup=main_keyboard,
        )