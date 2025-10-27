import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.reading import router_reading
from app.handlers import router
import os


async def main():
    bot = Bot(token="7440735369:AAFQBj9uRIBNjj4mhZ96_HyY8RQrljWwc1M")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router_reading)
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot is offline")
