import asyncio
from app.telegram.client import client


async def show():
    await client.start()
    messages = await client.get_messages('@AsiaExport_PRO', limit=2)
    for msg in messages:
        print("=== СООБЩЕНИЕ ===")
        print(f"Тип: {type(msg).__name__}")
        print(f"ID: {msg.id}")
        
        # Все атрибуты, которые могут содержать текст
        for attr in ['text', 'caption', 'message', 'raw_text']:
            val = getattr(msg, attr, None)
            if val:
                print(f"  {attr}: {str(val)[:200]}")
        
        # Есть ли media?
        if hasattr(msg, 'media') and msg.media:
            print(f"  media: {type(msg.media).__name__}")
        
        # Все поля (первые 15)
        print("  Все поля:")
        for field in dir(msg):
            if not field.startswith('_'):
                try:
                    val = getattr(msg, field)
                    if val and not callable(val) and not field.startswith('_'):
                        print(f"    {field}: {str(val)[:100]}")
                except:
                    pass
        
        print()
    
    await client.disconnect()

asyncio.run(show())