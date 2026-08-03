from app.ai_parser import parse_listing_ai
import re


def parse_listing(text: str) -> dict:
    """Парсит текст через AI и чистит данные."""
    result = parse_listing_ai(text)
    
    # Чистим числовые поля
    for field in ["price_rub", "mileage_km", "year"]:
        val = result.get(field)
        if isinstance(val, str):
            # Убираем всё кроме цифр
            val = re.sub(r'[^\d]', '', val)
            result[field] = int(val) if val else None
    
    return result