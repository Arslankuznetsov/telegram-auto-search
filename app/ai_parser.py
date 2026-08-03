import json
import requests
from app.config import YANDEX_API_KEY, YANDEX_FOLDER_ID


def parse_listing_ai(text: str) -> dict:
    """Парсит текст объявления через YandexGPT."""
    try:
        resp = requests.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers={
                "Authorization": f"Api-Key {YANDEX_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0,
                    "maxTokens": 500
                },
                "messages": [
                    {
                        "role": "system",
                        "text": (
                            "Ты — эксперт-автоподборщик. Извлеки из объявления характеристики строго в JSON.\n\n"
                            "ГДЕ ИСКАТЬ:\n"
                            "- Марка и модель: первая строка после эмодзи (🚘, 🚗), или после 'Марка:', или жирный текст в начале.\n"
                            "- Цена: после 💰, 'Цена:', 'Стоимость:', 'Цена под ключ:'. Только цифры, без пробелов.\n"
                            "- Год: после 📅, 'Год:', 'Год выпуска:', 'Дата выпуска:'. Только 4 цифры.\n"
                            "- Пробег: после 📊, 🛣️, 'Пробег:'. Цифры, без пробелов.\n"
                            "- Двигатель: после ⛽️, 🔧, 'Двигатель:'. Объём и тип (1.4, 1.5T, 2.0 дизель).\n"
                            "- КПП: после ⚙️, или в заголовке (AT, MT, CVT), или 'автомат', 'механика', 'робот', 'вариатор'.\n"
                            "- Привод: после 🛞, ⚙️, или '2WD', '4WD', 'AWD', 'передний', 'задний', 'полный'.\n"
                            "- Продавец: после ☎️, 📞, 'Контакт', 'звонить'. Имя или телефон.\n"
                            "- Регион: город или область, особенно рядом с 'доставка в', 'город', 'нахожусь'.\n\n"
                            "ПРАВИЛА:\n"
                            "- Если модель без марки: K5→Kia, K3→Kia, K7→Kia, Sonata→Hyundai, Avante→Hyundai, Grandeur→Hyundai, Tiggo→Chery, Arrizo→Chery, Jolion→Haval, Dargo→Haval, Coolray→Geely, Monjaro→Geely, Atlas→Geely, Dashing→Jetour, Traveller→Jetour.\n"
                            "- Все числа чисти от пробелов и запятых.\n"
                            "- Если параметр не найден — null.\n"
                            "- Отвечай ТОЛЬКО JSON. Без markdown, без пояснений.\n\n"
                            'ФОРМАТ: {"brand":"","model":"","year":null,"price_rub":null,"mileage_km":null,"engine":"","transmission":"","drive_type":"","seller_name":"","region":""}'
                        )
                    },
                    {"role": "user", "text": text}
                ]
            },
            timeout=30
        )
        
        result = resp.json()
        content = result["result"]["alternatives"][0]["message"]["text"]
        
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        
        return json.loads(content)
        
    except Exception as e:
        print(f"⚠️ AI-парсер ошибка: {e}")
        return {}