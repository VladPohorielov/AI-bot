# handlers/common_handlers.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from keyboards.inline import get_main_settings_keyboard
from states.user_states import SettingsStates
from config import DEFAULT_LANGUAGE, DEFAULT_SUMMARY_STYLE, SUPPORTED_LANGUAGES, \
    SUMMARY_STYLES

router = Router()


def get_user_settings(user_id: int, dp_user_settings: dict):
    if user_id not in dp_user_settings:
        dp_user_settings[user_id] = {
            "language": DEFAULT_LANGUAGE,
            "summary_style": DEFAULT_SUMMARY_STYLE,
            "summary_style_name": SUMMARY_STYLES[DEFAULT_SUMMARY_STYLE]["name"]
        }
    elif 'summary_style_name' not in dp_user_settings[user_id]:
        current_style_key = dp_user_settings[user_id].get('summary_style', DEFAULT_SUMMARY_STYLE)
        dp_user_settings[user_id]['summary_style_name'] = \
        SUMMARY_STYLES.get(current_style_key, SUMMARY_STYLES[DEFAULT_SUMMARY_STYLE])["name"]
    return dp_user_settings[user_id]


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, user_settings: dict, whisper_model: tuple):
    await state.clear()
    current_user_settings = get_user_settings(message.from_user.id, user_settings)

    user_name = message.from_user.first_name or "пользователь"
    _, device = whisper_model

    current_summary_style_name = current_user_settings.get('summary_style_name', SUMMARY_STYLES[DEFAULT_SUMMARY_STYLE]["name"])

    text = (
        f"👋 Привет, {hbold(user_name)}!\n"
        f"Я {hbold('Briefly')} — ваш персональный AI-помічник.\n\n"
        "Вміє:\n"
        "1️⃣ 🗣️ Транскрибувати голосові та аудіо сообщения\n"
        "2️⃣ 📝 Створювать короткі summary з тексту і переписок\n"
        "3️⃣ 📅 Витягати події з переписок і створювать нагадування у Google Calendar\n\n"
        f"🔹 Текущий язык транскрибации: {hbold(SUPPORTED_LANGUAGES.get(current_user_settings['language'], 'Авто'))}\n"
        f"🔹 Текущий стиль резюме: {hbold(current_summary_style_name)}\n"
        f"🔬 Whisper работает на: {hbold(device.upper())}\n\n"
        "➡️ Говоріть. Пишіть. Отримуйте суть.\n"
        "⚙️ Используйте /settings для изменения настроек."
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: types.Message, user_settings: dict):
    current_user_settings = get_user_settings(message.from_user.id, user_settings)
    current_lang_name = SUPPORTED_LANGUAGES.get(current_user_settings['language'], "Авто")

    current_style_key = current_user_settings.get('summary_style', DEFAULT_SUMMARY_STYLE)
    current_style_name = SUMMARY_STYLES.get(current_style_key, SUMMARY_STYLES[DEFAULT_SUMMARY_STYLE])["name"]

    text = (
        f"ℹ️ <b>Справка по {hbold('Briefly')}:</b>\n\n"
        "📝 <b>Основные функции:</b>\n"
        "🗣️ Транскрибация голосовых и аудио сообщений\n"
        "📝 Создание кратких summary из текста и переписок\n"
        "📅 Извлечение событий из переписок и создание напоминаний в Google Calendar\n\n"
        "🎤 <b>Как пользоваться:</b>\n"
        "1.  Отправьте голосовое сообщение или аудиофайл — получите транскрипцию\n"
        "2.  Отправьте текстовое сообщение — получите краткое резюме\n"
        "3.  Используйте /capture_chat для анализа переписок и извлечения событий\n"
        "4.  Подключите Google Calendar (/connect_calendar) для автоматических напоминаний\n\n"
        "⚙️ <b>Настройки (/settings):</b>\n"
        f"- <b>Язык транскрибации:</b> Сейчас \"{current_lang_name}\". Влияет на точность распознавания речи.\n"
        f"- <b>Стиль резюме:</b> Сейчас \"{current_style_name}\". Определяет подробность изложения.\n"
        "- <b>Календарь:</b> Управление подключением Google Calendar\n"
        "- <b>Уведомления и хранение данных:</b> Дополнительные настройки\n\n"
        "💡 <b>Полезные команды:</b>\n"
        "/capture_chat — начать захват переписки\n"
        "/my_sessions — история ваших сессий\n"
        "/connect_calendar — подключить Google Calendar\n\n"
        "❌ <b>Отмена:</b> Команда /cancel прервет текущую операцию."
    )
    await message.answer(text)


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, state: FSMContext):
    await state.set_state(SettingsStates.MAIN_SETTINGS_MENU)
    await message.answer("⚙️ <b>Настройки Briefly</b>\n\nВыберите, что вы хотите настроить:",
                         reply_markup=get_main_settings_keyboard())


@router.callback_query(F.data == "settings:close", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_settings_close(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👌 Настройки закрыты.")
    await callback.answer()


@router.message(Command("cancel"))
@router.callback_query(F.data == "cancel_state")
async def cmd_cancel(event: types.Message | types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        text = "🤷 Нет активных действий для отмены."
        if isinstance(event, types.Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return

    await state.clear()
    text = "✅ Действие отменено."
    if isinstance(event, types.Message):
        await event.answer(text)
    elif isinstance(event, types.CallbackQuery) and event.message:
        try:
            await event.message.edit_text(text)
        except Exception:
            await event.message.answer(text)
        await event.answer()


@router.message(F.text.startswith('/'))
async def unhandled_command_fallback(message: types.Message):
    await message.reply("😕 Неизвестная команда. Попробуйте /start или /help.")