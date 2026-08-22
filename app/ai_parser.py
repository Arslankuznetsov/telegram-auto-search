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
                            "Ты — парсер автомобильных объявлений для агрегатора. "
                            "Преврати текст из Telegram-канала в строгий JSON.\n\n"

                            "ТРЕБОВАНИЯ К ДАННЫМ:\n"
                            "1. brand — всегда официальное английское название марки: Kia, Hyundai, Honda, Chevrolet, Toyota, BMW, Land Rover, Skoda, Volkswagen, Mercedes-Benz.\n"
                            "2. model — модель без поколения и лишних слов. Например: 'K5 3generation Noblesse' → model='K5'.\n"
                            "3. generation — поколение (число или римская цифра), если указано.\n"
                            "4. year — год выпуска, только 4 цифры.\n"
                            "5. price_rub — цена в рублях, только цифры. Убирай пробелы и запятые.\n"
                            "6. mileage_km — пробег в км, только цифры.\n"
                            "7. engine — объём и тип: '1.5T', '2.0 бензин', '3.0 дизель'.\n"
                            "8. transmission — одно из: 'автомат', 'механика', 'робот', 'вариатор'.\n"
                            "9. drive_type — одно из: 'передний', 'задний', 'полный'.\n"
                            "10. seller_name — имя или телефон продавца, если есть.\n"
                            "11. region — город или регион, если есть.\n\n"

                            "ПРАВИЛА:\n"
                            "- Если марка написана по-русски ('КИЯ', 'Хонда', 'Шевроле') — переведи в английский.\n"
                            "- Если модели нет, но есть 'K5', 'Sonata', 'Tiggo' — определи марку сам.\n"
                            "- Числа возвращай только целыми, без пробелов и знаков.\n"
                            "- Отсутствующие поля — null.\n"
                            "- Отвечай ТОЛЬКО JSON, без пояснений.\n\n"

                            'ФОРМАТ: {"brand":"","model":"","generation":null,"year":null,"price_rub":null,"mileage_km":null,"engine":"","transmission":"","drive_type":"","seller_name":"","region":""}'
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