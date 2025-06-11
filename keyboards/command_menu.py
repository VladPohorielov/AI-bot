from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command="/start", description="🚀 Запустить Briefly"),
        BotCommand(command="/help", description="ℹ️ Помощь"),
        BotCommand(command="/settings", description="⚙️ Настройки"),
        BotCommand(command="/summary", description="📝 Создать краткое резюме"),
        BotCommand(command="/ask", description="🤖 Спілкуватися з ChatGPT"),
        BotCommand(command="/capture_chat", description="📝 Начать сессию захвата"),
        BotCommand(command="/end_capture", description="🛑 Завершить сессию"),
        BotCommand(command="/my_sessions", description="📚 История сессий"),
        BotCommand(command="/connect_calendar", description="📅 Подключить Google Calendar"),
        BotCommand(command="/calendar_status", description="📊 Статус календаря"),
        BotCommand(command="/cancel", description="❌ Отменить текущее действие")
    ]
    await bot.set_my_commands(main_menu_commands, BotCommandScopeDefault())
