# main_bot.py
import asyncio
import os
import logging
import sys
from typing import Callable, Dict, Any, Awaitable

from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv

from handlers import common_handlers, settings_handlers, voice_audio_handler, text_input_handler, capture_handlers, calendar_handlers
from keyboards.command_menu import set_main_menu
from services.transcription import load_whisper_model
from services.database import init_database
from services.google_oauth import oauth_cleanup_task
from config import TELEGRAM_BOT_TOKEN


class DataMiddleware(BaseMiddleware):
    def __init__(self, user_settings: dict, whisper_model: tuple):
        self.user_settings = user_settings
        self.whisper_model = whisper_model

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["user_settings"] = self.user_settings
        data["whisper_model"] = self.whisper_model
        
        # Add logging for debugging
        if isinstance(event, (types.Message, types.CallbackQuery)):
            user_id = event.from_user.id if event.from_user else "unknown"
            if isinstance(event, types.Message):
                logging.info(f"Message from user {user_id}: {event.text[:50] if event.text else 'non-text'}")
            elif isinstance(event, types.CallbackQuery):
                logging.info(f"Callback from user {user_id}: {event.data}")
        
        return await handler(event, data)


async def main():
    load_dotenv()

    # Validate bot token
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("Please set TELEGRAM_BOT_TOKEN in your .env file")
        sys.exit(1)

    # Initialize database
    await init_database()

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    user_settings = {}
    whisper_model = load_whisper_model()

    # Setup middleware for all event types
    middleware = DataMiddleware(user_settings, whisper_model)
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    dp.inline_query.middleware(middleware)

    await set_main_menu(bot)

    # Register routers in order of priority
    
    # 1. Enhanced handlers FIRST (highest priority)
    try:
        from handlers import enhanced_capture_handlers
        dp.include_router(enhanced_capture_handlers.router)
        print("✅ Enhanced capture handlers loaded (PRIORITY)")
    except ImportError as e:
        print(f"Enhanced handlers not available: {e}")
    
    # 2. Summary handler (before common to avoid conflicts)
    try:
        from handlers import summary_handler
        dp.include_router(summary_handler.router)
        print("✅ Summary handler loaded")
    except ImportError as e:
        print(f"Summary handler not available: {e}")
    
    # 3. ChatGPT handler (before common to avoid conflicts)
    try:
        from handlers import chatgpt_handler
        dp.include_router(chatgpt_handler.router)
        print("✅ ChatGPT handler loaded")
    except ImportError as e:
        print(f"ChatGPT handler not available: {e}")
    
    # 4. Calendar handlers (before common to avoid conflicts)
    dp.include_router(calendar_handlers.router)
    
    # 5. Common handlers (includes /start, /help, unhandled commands)
    dp.include_router(common_handlers.router)
    
    # 6. Event extraction handler (for "Витягати події" button)
    try:
        from handlers import event_extract_handler
        dp.include_router(event_extract_handler.router)
        print("✅ Event extraction handler loaded")
    except ImportError as e:
        print(f"Event extraction handler not available: {e}")
    
    # 7. Settings handlers
    dp.include_router(settings_handlers.router)
    
    # 8. Old capture handlers (FALLBACK ONLY if enhanced not available)
    # NOTE: Commenting out to avoid conflicts - enhanced handlers handle this
    # dp.include_router(capture_handlers.router)
    dp.include_router(voice_audio_handler.router)
    dp.include_router(text_input_handler.router)

    # Start background OAuth cleanup task
    asyncio.create_task(oauth_cleanup_task())

    # Enhanced logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set specific loggers for debugging
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("handlers").setLevel(logging.DEBUG)
    
    try:
        print("🚀 Bot starting...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
