import asyncio

from app.telegram.client import client


async def main() -> None:
    await client.start()

    me = await client.get_me()

    print(f"✅ Успешный вход: {me.first_name}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())