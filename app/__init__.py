from app.db import init_db
from pathlib import Path


async def setup():
    """Инициализация приложения."""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    await init_db()