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

                            "ВАЖНО: Особое внимание удели извлечению model (модель). "
                            "Модель может быть в любом месте текста: в заголовке, после эмодзи (🚘, 🚗), "
                            "после марки, в скобках, в начале объявления. "
                            "Даже если написано слитно или в другом регистре, "
                            "найди и верни её в читаемом виде.\n\n"

                            "Примеры моделей, которые нужно извлекать:\n"
                            "- 'Kia K5' → brand='Kia', model='K5'\n"
                            "- 'Audi A3 Sportback' → brand='Audi', model='A3 Sportback'\n"
                            "- 'BMW X1 sDrive20Li' → brand='BMW', model='X1'\n"
                            "- 'Volkswagen Tiguan' → brand='Volkswagen', model='Tiguan'\n"
                            "- 'Land Rover Discovery Sport' → brand='Land Rover', model='Discovery Sport'\n"
                            "- 'КИЯ К5' → brand='Kia', model='K5'\n\n"

                            "Если модель не удаётся найти, ставь null, но только если её действительно нет в тексте.\n\n"

                            "ТРЕБОВАНИЯ К ДАННЫМ:\n"
                            "1. brand — всегда официальное английское название марки.\n"
                            "2. model — модель без поколения и лишних слов.\n"
                            "3. generation — поколение, если указано (число или римская цифра).\n"
                            "4. year — год выпуска. Извлекай только 4 цифры. Если указано '2023/06' или 'Февраль 2023', бери '2023'. Не включай месяц.\n"
                            "5. price_rub — цена в рублях, только цифры. Убирай пробелы и запятые.\n"
                            "6. mileage_km — пробег в км. Всегда преобразуй в целое число. '45 тыс. км', '45к', '45 000', '45000' → 45000.\n"
                            "7. engine — объём и тип: '1.5T', '2.0 бензин', '3.0 дизель'.\n"
                            "8. transmission — обязательно приведи к одному из значений: 'автомат', 'механика', 'робот', 'вариатор'. Синонимы: АКПП, AT, automatic → 'автомат'; МКПП, MT, manual → 'механика'; CVT → 'вариатор'; robot → 'робот'.\n"
                            "9. drive_type — обязательно приведи к одному из значений: 'передний', 'задний', 'полный'. Синонимы: 2WD, FWD → 'передний'; RWD → 'задний'; 4WD, AWD, full → 'полный'.\n"
                            "10. seller_name — имя, телефон или название продавца. Ищи после: ☎️, 📞, 'контакт', 'звонить', 'продавец'.\n"
                            "11. region — город или регион. Ищи после: 📍, 'город', 'доставка в', 'нахожусь'.\n\n"

                            "ПРАВИЛА:\n"
                            "- Если марка написана по-русски ('КИЯ', 'Хонда', 'Шевроле') — переведи в английский.\n"
                            "- Если модели нет, но есть 'K5', 'Sonata', 'Tiggo' — определи марку сам.\n"
                            "- Числа возвращай только целыми, без пробелов и знаков.\n"
                            "- Отсутствующие поля — null.\n"
                            "- Отвечай ТОЛЬКО JSON, без пояснений.\n\n"

                            'ПРИМЕР ОТВЕТА:\n'
                            '{"brand":"Kia","model":"K5","generation":null,"year":2022,"price_rub":2230000,"mileage_km":15000,"engine":"2.0","transmission":"автомат","drive_type":"передний","seller_name":"Алексей","region":"Москва"}'
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

        parsed = json.loads(content)

        # Гарантируем, что вернём словарь
        if isinstance(parsed, dict):
            return parsed
        else:
            return {}

    except Exception as e:
        print(f"⚠️ AI-парсер ошибка: {e}")
        return {}