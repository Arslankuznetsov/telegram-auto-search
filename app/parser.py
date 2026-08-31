import re
import json
from pathlib import Path
from app.ai_parser import parse_listing_ai

# Загружаем справочник марок/моделей для fallback
MODELS_PATH = Path(__file__).parent.parent / "data" / "car_models.json"
try:
    with open(MODELS_PATH, "r", encoding="utf-8") as f:
        CAR_BRANDS = json.load(f)
except Exception:
    CAR_BRANDS = {}


# Словари синонимов для нормализации
TRANSMISSION_SYNONYMS = {
    "акпп": "автомат",
    "ат": "автомат",
    "at": "автомат",
    "automatic": "автомат",
    "автоматическая": "автомат",
    "мкпп": "механика",
    "мт": "механика",
    "mt": "механика",
    "manual": "механика",
    "механическая": "механика",
    "cvt": "вариатор",
    "вариатор": "вариатор",
    "робот": "робот",
    "robot": "робот",
    "dsg": "робот",
    "dct": "робот",
}

DRIVE_TYPE_SYNONYMS = {
    "2wd": "передний",
    "fwd": "передний",
    "передний": "передний",
    "rwd": "задний",
    "задний": "задний",
    "4wd": "полный",
    "awd": "полный",
    "full": "полный",
    "полный": "полный",
}


def normalize_transmission(value: str | None) -> str | None:
    """Приводит коробку передач к каноническому значению."""
    if not value:
        return None
    return TRANSMISSION_SYNONYMS.get(value.strip().lower(), value.strip())


def normalize_drive_type(value: str | None) -> str | None:
    """Приводит привод к каноническому значению."""
    if not value:
        return None
    return DRIVE_TYPE_SYNONYMS.get(value.strip().lower(), value.strip())


def extract_year_clean(value: str | None) -> int | None:
    """Извлекает только 4 цифры года из строки."""
    if not value:
        return None
    match = re.search(r"(\d{4})", str(value))
    if match:
        year = int(match.group(1))
        if 1990 <= year <= 2026:
            return year
    return None


def fallback_extract_brand_model(text: str) -> tuple[str | None, str | None]:
    """Ищет марку и модель в тексте по справочнику."""
    text_lower = text.lower()
    for brand, models in CAR_BRANDS.items():
        if brand.lower() in text_lower:
            # Нашли марку, теперь ищем модель
            for model in models:
                if model.lower() in text_lower:
                    return brand, model
            return brand, None
    return None, None


def parse_listing(text: str) -> dict:
    """Парсит текст через AI, затем нормализует и дополняет данные."""
    result = parse_listing_ai(text)

    if not isinstance(result, dict):
        result = {}

    # Fallback для марки/модели, если AI не справился
    if not result.get("brand") or not result.get("model"):
        fb_brand, fb_model = fallback_extract_brand_model(text)
        if not result.get("brand") and fb_brand:
            result["brand"] = fb_brand
        if not result.get("model") and fb_model:
            result["model"] = fb_model

    # Чистим числовые поля
    for field in ["price_rub", "mileage_km"]:
        val = result.get(field)
        if isinstance(val, str):
            # Убираем всё кроме цифр
            digits = re.sub(r"[^\d]", "", val)
            result[field] = int(digits) if digits else None
        elif val is not None and not isinstance(val, int):
            # если float и т.п., приводим к int
            try:
                result[field] = int(val)
            except (ValueError, TypeError):
                result[field] = None

    # Год обрабатываем отдельно, чтобы не получить 202306 из "2023/06"
    result["year"] = extract_year_clean(result.get("year"))

    # Нормализуем transmission и drive_type
    result["transmission"] = normalize_transmission(result.get("transmission"))
    result["drive_type"] = normalize_drive_type(result.get("drive_type"))

    return result