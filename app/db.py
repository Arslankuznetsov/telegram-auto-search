import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "listings.db"


async def get_db():
    """Создаёт соединение с БД."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Создаёт таблицы, если их ещё нет."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
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
            parsed_at TIMESTAMP
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


async def get_price_stats(brand: str, model: str = None):
    """Возвращает статистику цен по марке и модели."""
    db = await get_db()
    
    if model:
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as count,
                AVG(price_rub) as avg_price,
                MIN(price_rub) as min_price,
                MAX(price_rub) as max_price
            FROM listings
            WHERE LOWER(brand) = LOWER(?)
              AND LOWER(model) LIKE LOWER(?)
              AND price_rub IS NOT NULL
        """, (brand, f"%{model}%"))
    else:
        cursor = await db.execute("""
            SELECT 
                COUNT(*) as count,
                AVG(price_rub) as avg_price,
                MIN(price_rub) as min_price,
                MAX(price_rub) as max_price
            FROM listings
            WHERE LOWER(brand) = LOWER(?)
              AND price_rub IS NOT NULL
        """, (brand,))
    
    row = await cursor.fetchone()
    
    if row["count"] == 0:
        await db.close()
        return None
    
    if model:
        cursor = await db.execute("""
            SELECT price_rub FROM listings
            WHERE LOWER(brand) = LOWER(?)
              AND LOWER(model) LIKE LOWER(?)
              AND price_rub IS NOT NULL
            ORDER BY price_rub
        """, (brand, f"%{model}%"))
    else:
        cursor = await db.execute("""
            SELECT price_rub FROM listings
            WHERE LOWER(brand) = LOWER(?)
              AND price_rub IS NOT NULL
            ORDER BY price_rub
        """, (brand,))
    
    prices = [r["price_rub"] for r in await cursor.fetchall()]
    await db.close()
    
    mid = len(prices) // 2
    median = prices[mid] if prices else 0
    
    return {
        "count": row["count"],
        "avg": int(row["avg_price"]),
        "min": int(row["min_price"]),
        "max": int(row["max_price"]),
        "median": median
    }