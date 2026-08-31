import re
import json
from pathlib import Path
from app.ai_parser import parse_listing_ai

MODELS_PATH = Path(__file__).parent.parent / "data" / "car_models.json"
try:
    with open(MODELS_PATH, "r", encoding="utf-8") as f:
        CAR_BRANDS = json.load(f)
except Exception:
    CAR_BRANDS = {}

TRANSMISSION_SYNONYMS = {
    "акпп": "автомат", "ат": "автомат", "at": "автомат", "automatic": "автомат",
    "автоматическая": "автомат", "мкпп": "механика", "мт": "механика",
    "mt": "механика", "manual": "механика", "механическая": "механика",
    "cvt": "вариатор", "вариатор": "вариатор", "робот": "робот",
    "robot": "робот", "dsg": "робот", "dct": "робот",
}

DRIVE_TYPE_SYNONYMS = {
    "2wd": "передний", "fwd": "передний", "передний": "передний",
    "rwd": "задний", "задний": "задний", "4wd": "полный", "awd": "полный",
    "full": "полный", "полный": "полный",
}


def normalize_transmission(value):
    if not value:
        return None
    return TRANSMISSION_SYNONYMS.get(value.strip().lower(), value.strip())


def normalize_drive_type(value):
    if not value:
        return None
    return DRIVE_TYPE_SYNONYMS.get(value.strip().lower(), value.strip())


def extract_year_clean(value):
    if not value:
        return None
    match = re.search(r"(\d{4})", str(value))
    if match:
        year = int(match.group(1))
        if 1990 <= year <= 2026:
            return year
    return None


def fallback_extract_brand_model(text):
    text_lower = text.lower()
    for brand, models in CAR_BRANDS.items():
        if brand.lower() in text_lower:
            for model in models:
                if model.lower() in text_lower:
                    return brand, model
            return brand, None
    return None, None


def parse_listing(text: str) -> dict:
    result = parse_listing_ai(text)

    if not isinstance(result, dict):
        result = {}

    if not result.get("brand") or not result.get("model"):
        fb_brand, fb_model = fallback_extract_brand_model(text)
        if not result.get("brand") and fb_brand:
            result["brand"] = fb_brand
        if not result.get("model") and fb_model:
            result["model"] = fb_model

    for field in ["price_rub", "mileage_km"]:
        val = result.get(field)
        if isinstance(val, str):
            digits = re.sub(r"[^\d]", "", val)
            result[field] = int(digits) if digits else None
        elif val is not None and not isinstance(val, int):
            try:
                result[field] = int(val)
            except (ValueError, TypeError):
                result[field] = None

    result["year"] = extract_year_clean(result.get("year"))
    result["transmission"] = normalize_transmission(result.get("transmission"))
    result["drive_type"] = normalize_drive_type(result.get("drive_type"))

    return result