import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "listings.db"


async def get_db():
    """Создаёт соединение с БД."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def init_db():
    """Создаёт таблицы, если их ещё нет."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            channel_username TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,

            brand TEXT,
            model TEXT,
            generation TEXT,
            year INTEGER,
            price_rub INTEGER,
            mileage_km INTEGER,
            engine TEXT,
            transmission TEXT,
            drive_type TEXT,
            vin TEXT,
            seller_name TEXT,
            region TEXT,
            link TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parsed_at TIMESTAMP,

            UNIQUE(channel_username, message_id)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_brand_model
            ON listings(brand, model);
        CREATE INDEX IF NOT EXISTS idx_listings_price
            ON listings(price_rub);
        CREATE INDEX IF NOT EXISTS idx_listings_year
            ON listings(year);
        CREATE INDEX IF NOT EXISTS idx_listings_channel
            ON listings(channel_username);

        CREATE VIRTUAL TABLE IF NOT EXISTS listings_fts USING fts5(
            raw_text,
            brand,
            model,
            content='listings',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS listings_ai AFTER INSERT ON listings BEGIN
            INSERT INTO listings_fts(rowid, raw_text, brand, model)
            VALUES (new.id, new.raw_text, new.brand, new.model);
        END;

        CREATE TRIGGER IF NOT EXISTS listings_ad AFTER DELETE ON listings BEGIN
            INSERT INTO listings_fts(listings_fts, rowid, raw_text, brand, model)
            VALUES('delete', old.id, old.raw_text, old.brand, old.model);
        END;

        CREATE TRIGGER IF NOT EXISTS listings_au AFTER UPDATE ON listings BEGIN
            INSERT INTO listings_fts(listings_fts, rowid, raw_text, brand, model)
            VALUES('delete', old.id, old.raw_text, old.brand, old.model);
            INSERT INTO listings_fts(rowid, raw_text, brand, model)
            VALUES (new.id, new.raw_text, new.brand, new.model);
        END;

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()
    await db.close()


async def get_listings_count():
    """Возвращает количество объявлений в базе."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as count FROM listings")
    result = await cursor.fetchone()
    await db.close()
    return result["count"]


async def get_channels():
    """Возвращает список каналов."""
    db = await get_db()
    cursor = await db.execute("SELECT username FROM channels")
    rows = await cursor.fetchall()
    await db.close()
    return [row["username"] for row in rows]


async def add_channel(username: str):
    """Добавляет канал в БД."""
    db = await get_db()
    username = username.strip().lstrip("@")
    await db.execute(
        "INSERT OR IGNORE INTO channels (username) VALUES (?)",
        (f"@{username}",)
    )
    await db.commit()
    await db.close()


async def remove_channel(username: str):
    """Удаляет канал из БД."""
    db = await get_db()
    username = username.strip().lstrip("@")
    await db.execute(
        "DELETE FROM channels WHERE username = ?",
        (f"@{username}",)
    )
    await db.commit()
    await db.close()


async def get_price_stats(brand: str, model: str = None, year_from: int = None, year_to: int = None):
    """Возвращает статистику цен по марке и модели с возможной фильтрацией по году."""
    db = await get_db()

    conditions = ["price_rub IS NOT NULL"]
    params = []

    if model:
        conditions.append("LOWER(brand) = LOWER(?)")
        params.append(brand)
        conditions.append("LOWER(model) LIKE LOWER(?)")
        params.append(f"%{model}%")
    else:
        conditions.append("LOWER(brand) = LOWER(?)")
        params.append(brand)

    if year_from is not None:
        conditions.append("year >= ?")
        params.append(year_from)

    if year_to is not None:
        conditions.append("year <= ?")
        params.append(year_to)

    where_clause = " AND ".join(conditions)

    cursor = await db.execute(f"""
        SELECT price_rub
        FROM listings
        WHERE {where_clause}
        ORDER BY price_rub
    """, params)

    rows = await cursor.fetchall()
    await db.close()

    if not rows:
        return None

    prices = [row["price_rub"] for row in rows]
    count = len(prices)

    avg = sum(prices) / count
    min_price = min(prices)
    max_price = max(prices)

    mid = count // 2
    if count % 2 == 0:
        median = (prices[mid - 1] + prices[mid]) / 2
    else:
        median = prices[mid]

    return {
        "count": count,
        "avg": int(avg),
        "min": int(min_price),
        "max": int(max_price),
        "median": int(median)
    }


async def save_user(user_id: int, username: str = None, first_name: str = None):
    """Сохраняет пользователя, если его ещё нет."""
    db = await get_db()
    await db.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    """, (user_id, username, first_name))
    await db.commit()
    await db.close()


async def get_users_count():
    """Возвращает количество пользователей."""
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) as count FROM users")
    result = await cursor.fetchone()
    await db.close()
    return result["count"]