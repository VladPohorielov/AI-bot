import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from config import SUPPORTED_LANGUAGES, SUMMARY_STYLES
from handlers.common_handlers import get_user_settings
from keyboards.inline import (get_language_keyboard,
                              get_main_settings_keyboard,
                              get_summary_style_keyboard,
                              get_calendar_settings_menu_keyboard,
                              get_auto_create_confirmation_keyboard,
                              get_disconnect_calendar_confirmation_keyboard,
                              get_notifications_settings_keyboard,
                              get_data_retention_keyboard)
from states.user_states import SettingsStates
from services.database import get_user_calendar_status, get_user_setting, update_user_setting, disconnect_user_calendar, cleanup_user_data

logger = logging.getLogger(__name__)
router = Router()
logger.info("settings_handlers.router created.")


@router.callback_query(F.data == "settings:main")
async def cq_back_to_main_settings(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"cq_back_to_main_settings called by user {callback.from_user.id}")
    await state.set_state(SettingsStates.MAIN_SETTINGS_MENU)
    await callback.message.edit_text(
        "⚙️ <b>Настройки Briefly</b>\n\nВыберите, что вы хотите настроить:",
        reply_markup=get_main_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "settings:language", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_select_language_menu(callback: types.CallbackQuery, state: FSMContext, user_settings: dict):
    user_id = callback.from_user.id
    logger.info(f"cq_select_language_menu called by user {user_id}")
    user_prefs = get_user_settings(user_id, user_settings)
    await state.set_state(SettingsStates.CHOOSING_LANGUAGE)
    await callback.message.edit_text(
        "🗣️ Выберите язык для транскрибации аудио:",
        reply_markup=get_language_keyboard(user_prefs["language"])
    )
    await callback.answer()


@router.callback_query(SettingsStates.CHOOSING_LANGUAGE, F.data.startswith("select_lang:"))
async def cq_set_language(callback: types.CallbackQuery, state: FSMContext, user_settings: dict):
    user_id = callback.from_user.id
    lang_code = callback.data.split(":")[1]
    logger.info(f"cq_set_language called by user {user_id}, lang_code: {lang_code}")

    if lang_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"Invalid lang_code '{lang_code}' from user {user_id}")
        await callback.answer("❌ Неверный код языка.", show_alert=True)
        return

    user_prefs = get_user_settings(user_id, user_settings)
    user_prefs["language"] = lang_code
    logger.info(f"User {user_id} language set to {lang_code}")

    await callback.answer(f"✅ Язык установлен: {SUPPORTED_LANGUAGES[lang_code]}", show_alert=False)
    await state.set_state(SettingsStates.MAIN_SETTINGS_MENU)
    await callback.message.edit_text(
        f"⚙️ <b>Настройки Briefly</b>\n\nЯзык транскрибации изменен на: {hbold(SUPPORTED_LANGUAGES[lang_code])}\nВыберите, что вы хотите настроить:",
        reply_markup=get_main_settings_keyboard()
    )


@router.callback_query(F.data == "settings:summary_style", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_select_summary_style_menu(callback: types.CallbackQuery, state: FSMContext, user_settings: dict):
    user_id = callback.from_user.id
    logger.info(f"cq_select_summary_style_menu called by user {user_id}")
    user_prefs = get_user_settings(user_id, user_settings)
    await state.set_state(SettingsStates.CHOOSING_SUMMARY_STYLE)
    await callback.message.edit_text(
        "💡 Выберите стиль для генерируемого резюме:",
        reply_markup=get_summary_style_keyboard(user_prefs["summary_style"])
    )
    await callback.answer()


@router.callback_query(SettingsStates.CHOOSING_SUMMARY_STYLE, F.data.startswith("select_style:"))
async def cq_set_summary_style(callback: types.CallbackQuery, state: FSMContext, user_settings: dict):
    user_id = callback.from_user.id
    style_code = callback.data.split(":")[1]
    logger.info(f"cq_set_summary_style called by user {user_id}, style_code: {style_code}")

    if style_code not in SUMMARY_STYLES:
        logger.warning(f"Invalid style_code '{style_code}' from user {user_id}")
        await callback.answer("❌ Неверный стиль резюме.", show_alert=True)
        return

    user_prefs = get_user_settings(user_id, user_settings)
    user_prefs["summary_style"] = style_code
    user_prefs["summary_style_name"] = SUMMARY_STYLES[style_code]["name"]
    logger.info(f"User {user_id} summary style set to {style_code}")

    await callback.answer(f"✅ Стиль резюме установлен: {SUMMARY_STYLES[style_code]['name']}", show_alert=False)
    await state.set_state(SettingsStates.MAIN_SETTINGS_MENU)
    await callback.message.edit_text(
        f"⚙️ <b>Настройки Briefly</b>\n\nСтиль резюме изменен на: {hbold(SUMMARY_STYLES[style_code]['name'])}\nВыберите, что вы хотите настроить:",
        reply_markup=get_main_settings_keyboard()
    )


# Calendar Settings Handlers
@router.callback_query(F.data == "settings:calendar", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_calendar_settings_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show calendar settings submenu"""
    user_id = callback.from_user.id
    logger.info(f"cq_calendar_settings_menu called by user {user_id}")
    
    try:

        
        # Get calendar status
        calendar_status = await get_user_calendar_status(user_id)
        
        # Build status text
        if calendar_status['connected']:
            status_text = (
                "📅 <b>Настройки календаря</b>\n\n"
                "✅ <b>Статус:</b> Календарь подключен\n"
            )
            if calendar_status['calendar_id']:
                status_text += f"📍 <b>ID календаря:</b> <code>{calendar_status['calendar_id'][:20]}...</code>\n"
            
            auto_status = "включено" if calendar_status['auto_create_events'] else "отключено"
            status_text += f"⚙️ <b>Автосоздание событий:</b> {auto_status}\n\n"
            status_text += "💡 Выберите действие:"
        else:
            status_text = (
                "📅 <b>Настройки календаря</b>\n\n"
                "❌ <b>Статус:</b> Календарь не подключен\n\n"
                "🔗 Подключите Google Calendar для автоматического создания событий из ваших разговоров.\n\n"
                "💡 Выберите действие:"
            )
        
        keyboard = get_calendar_settings_menu_keyboard(
            calendar_status['connected'],
            calendar_status['auto_create_events']
        )
        
        await callback.message.edit_text(status_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in calendar settings menu: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка</b>\n\nНе удалось загрузить настройки календаря.",
            reply_markup=get_main_settings_keyboard()
        )
        await callback.answer()


@router.callback_query(F.data == "toggle_auto_create")
async def cq_toggle_auto_create(callback: types.CallbackQuery, state: FSMContext):
    """Toggle auto-create events setting"""
    user_id = callback.from_user.id
    logger.info(f"cq_toggle_auto_create called by user {user_id}")
    
    try:

        
        current_setting = await get_user_setting(user_id, 'auto_create_events', False)
        new_setting = not current_setting
        
        confirmation_text = (
            "⚙️ <b>Изменение настройки</b>\n\n"
            f"🔄 <b>Автосоздание событий:</b> {current_setting} → {new_setting}\n\n"
        )
        
        if new_setting:
            confirmation_text += (
                "✅ При включении автосоздания:\n"
                "• События будут автоматически создаваться в календаре после анализа сессий\n"
                "• Вы сможете просматривать их в Google Calendar\n"
                "• Отключить можно в любое время\n\n"
            )
        else:
            confirmation_text += (
                "☑️ При отключении автосоздания:\n"
                "• События будут сохраняться только в Briefly\n"
                "• Вы сможете создавать их в календаре вручную\n"
                "• Включить можно в любое время\n\n"
            )
        
        confirmation_text += "Подтвердить изменение?"
        
        # Store the new setting in FSM for confirmation
        await state.update_data(pending_auto_create=new_setting)
        
        await callback.message.edit_text(
            confirmation_text,
            reply_markup=get_auto_create_confirmation_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error toggling auto create: {e}")
        await callback.answer("❌ Ошибка изменения настройки")


@router.callback_query(F.data == "confirm_auto_create")
async def cq_confirm_auto_create(callback: types.CallbackQuery, state: FSMContext):
    """Confirm auto-create setting change"""
    user_id = callback.from_user.id
    
    try:

        
        # Get pending setting from FSM
        data = await state.get_data()
        new_setting = data.get('pending_auto_create', False)
        
        # Update database
        success = await update_user_setting(user_id, 'auto_create_events', new_setting)
        
        if success:
            status_text = "включено" if new_setting else "отключено"
            await callback.answer(f"✅ Автосоздание событий {status_text}")
            
            # Return to calendar settings
            await cq_calendar_settings_menu(callback, state)
        else:
            await callback.answer("❌ Ошибка сохранения настройки")
        
        # Clear pending data
        await state.update_data(pending_auto_create=None)
        
    except Exception as e:
        logger.error(f"Error confirming auto create: {e}")
        await callback.answer("❌ Ошибка подтверждения")


@router.callback_query(F.data == "cancel_auto_create")
async def cq_cancel_auto_create(callback: types.CallbackQuery, state: FSMContext):
    """Cancel auto-create setting change"""
    # Clear pending data
    await state.update_data(pending_auto_create=None)
    
    # Return to calendar settings  
    await cq_calendar_settings_menu(callback, state)
    await callback.answer("Изменение отменено")


@router.callback_query(F.data == "disconnect_calendar")
async def cq_disconnect_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Show calendar disconnect confirmation"""
    user_id = callback.from_user.id
    
    try:

        
        await callback.message.edit_text(
            "🔌 <b>Отключение календаря</b>\n\n"
            "⚠️ При отключении календаря:\n"
            "• Связь с Google Calendar будет разорвана\n"
            "• Автосоздание событий будет отключено\n"
            "• Токены доступа будут удалены\n"
            "• Ранее созданные события останутся в календаре\n\n"
            "❓ Вы уверены что хотите отключить календарь?",
            reply_markup=get_disconnect_calendar_confirmation_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing disconnect confirmation: {e}")
        await callback.answer("❌ Ошибка")


@router.callback_query(F.data == "confirm_disconnect_calendar")
async def cq_confirm_disconnect_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Confirm calendar disconnection"""
    user_id = callback.from_user.id
    
    try:

        
        # Disconnect calendar in database
        success = await disconnect_user_calendar(user_id)
        
        if success:
            await callback.answer("🔌 Календарь отключен")
            
            # Show updated calendar settings
            await cq_calendar_settings_menu(callback, state)
        else:
            await callback.answer("❌ Ошибка отключения календаря")
        
    except Exception as e:
        logger.error(f"Error disconnecting calendar: {e}")
        await callback.answer("❌ Ошибка отключения")


@router.callback_query(F.data == "cancel_disconnect_calendar")
async def cq_cancel_disconnect_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Cancel calendar disconnection"""
    # Return to calendar settings
    await cq_calendar_settings_menu(callback, state)
    await callback.answer("Отключение отменено")


@router.callback_query(F.data == "connect_calendar_from_settings")
async def cq_connect_calendar_from_settings(callback: types.CallbackQuery, state: FSMContext):
    """Redirect to calendar connection from settings"""
    await callback.message.edit_text(
        "🔗 <b>Подключение календаря</b>\n\n"
        "Используйте команду /connect_calendar для подключения Google Calendar."
    )
    await callback.answer()


# Notifications Settings Handlers  
@router.callback_query(F.data == "settings:notifications", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_notifications_settings_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show notifications settings submenu"""
    user_id = callback.from_user.id
    logger.info(f"cq_notifications_settings_menu called by user {user_id}")
    
    try:
        # Get current notifications settings
        notifications_enabled = await get_user_setting(user_id, 'notifications_enabled', True)
        event_notifications = await get_user_setting(user_id, 'event_notifications', True)
        session_notifications = await get_user_setting(user_id, 'session_notifications', True)
        error_notifications = await get_user_setting(user_id, 'error_notifications', True)
        
        # Build status text
        main_status = "включены" if notifications_enabled else "отключены"
        status_text = (
            "🔔 <b>Настройки уведомлений</b>\n\n"
            f"📱 <b>Статус уведомлений:</b> {main_status}\n\n"
        )
        
        if notifications_enabled:
            status_text += "💡 <b>Активные категории:</b>\n"
            if event_notifications:
                status_text += "• ✅ Уведомления о событиях\n"
            else:
                status_text += "• ☑️ Уведомления о событиях\n"
            
            if session_notifications:
                status_text += "• ✅ Уведомления о завершении сессий\n"
            else:
                status_text += "• ☑️ Уведомления о завершении сессий\n"
            
            if error_notifications:
                status_text += "• ✅ Уведомления об ошибках\n"
            else:
                status_text += "• ☑️ Уведомления об ошибках\n"
        else:
            status_text += "ℹ️ Все уведомления отключены\n"
        
        status_text += "\n💡 Настройте категории уведомлений:"
        
        keyboard = get_notifications_settings_keyboard(notifications_enabled)
        
        await callback.message.edit_text(status_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in notifications settings menu: {e}")
        await callback.answer("❌ Ошибка загрузки настроек")


# Data Retention Settings Handlers
@router.callback_query(F.data == "settings:data_retention", SettingsStates.MAIN_SETTINGS_MENU)
async def cq_data_retention_settings_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show data retention settings submenu"""
    user_id = callback.from_user.id
    logger.info(f"cq_data_retention_settings_menu called by user {user_id}")
    
    try:
        # Get current retention setting
        retention_days = await get_user_setting(user_id, 'data_retention_days', 30)
        
        # Format period text
        if retention_days == 0:
            period_text = "♾️ навсегда"
        elif retention_days == 7:
            period_text = "📅 1 неделя"
        elif retention_days == 30:
            period_text = "📅 1 месяц"
        elif retention_days == 90:
            period_text = "📅 3 месяца"
        elif retention_days == 365:
            period_text = "📅 1 год"
        else:
            period_text = f"📅 {retention_days} дней"
        
        status_text = (
            "📚 <b>Настройки хранения данных</b>\n\n"
            f"⏰ <b>Текущий период хранения:</b> {period_text}\n\n"
            "📋 <b>Что сохраняется:</b>\n"
            "• Сессии разговоров и их анализ\n"
            "• Извлеченные события и задачи\n"
            "• История экспорта и обмена\n\n"
            "🗑️ <b>Автоматическая очистка:</b>\n"
            "• Старые данные удаляются автоматически\n"
            "• Настройки и подключения сохраняются\n"
            "• События в календаре не затрагиваются\n\n"
            "💡 Выберите период хранения:"
        )
        
        keyboard = get_data_retention_keyboard(retention_days)
        
        await callback.message.edit_text(status_text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in data retention settings menu: {e}")
        await callback.answer("❌ Ошибка загрузки настроек")


@router.callback_query(F.data.startswith("set_retention_"))
async def cq_set_retention_period(callback: types.CallbackQuery, state: FSMContext):
    """Set data retention period"""
    user_id = callback.from_user.id
    retention_days = int(callback.data.split("_")[2])
    
    try:
        # Save retention setting to database
        await update_user_setting(user_id, 'data_retention_days', retention_days)
        
        if retention_days == 0:
            period_text = "♾️ хранить всегда"
        elif retention_days == 7:
            period_text = "📅 1 неделя"
        elif retention_days == 30:
            period_text = "📅 1 месяц"
        elif retention_days == 90:
            period_text = "📅 3 месяца"
        elif retention_days == 365:
            period_text = "📅 1 год"
        else:
            period_text = f"📅 {retention_days} дней"
        
        await callback.answer(f"✅ Период хранения установлен: {period_text}")
        
        # Return to data retention menu with updated settings
        await cq_data_retention_settings_menu(callback, state)
        
    except Exception as e:
        logger.error(f"Error setting retention period: {e}")
        await callback.answer("❌ Ошибка установки периода")


# Additional handlers for missing functionality
@router.callback_query(F.data == "settings:close")
async def cq_close_settings(callback: types.CallbackQuery, state: FSMContext):
    """Close settings menu"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Настройки закрыты")


@router.callback_query(F.data == "calendar_status")
async def cq_calendar_status_info(callback: types.CallbackQuery, state: FSMContext):
    """Show detailed calendar status information"""
    user_id = callback.from_user.id
    
    try:
        calendar_status = await get_user_calendar_status(user_id)
        
        if calendar_status['connected']:
            info_text = (
                "✅ <b>Календарь подключен</b>\n\n"
                "🔗 <b>Статус подключения:</b> Активно\n"
            )
            if calendar_status['calendar_id']:
                info_text += f"📅 <b>ID календаря:</b> <code>{calendar_status['calendar_id']}</code>\n"
            
            auto_status = "включено" if calendar_status['auto_create_events'] else "отключено"
            info_text += f"⚙️ <b>Автосоздание событий:</b> {auto_status}\n"
            info_text += f"🔑 <b>Токен доступа:</b> {'сохранен' if calendar_status['has_refresh_token'] else 'отсутствует'}\n\n"
            info_text += "💡 Вы можете управлять настройками через меню."
        else:
            info_text = (
                "❌ <b>Календарь не подключен</b>\n\n"
                "📋 <b>Для подключения:</b>\n"
                "1. Нажмите 'Подключить календарь'\n"
                "2. Авторизуйтесь в Google\n"
                "3. Разрешите доступ к календарю\n\n"
                "🔒 <b>Безопасность:</b>\n"
                "• Токены хранятся в зашифрованном виде\n"
                "• Доступ только к календарным событиям\n"
                "• Возможность отключения в любое время"
            )
        
        await callback.answer(info_text, show_alert=True)
        
    except Exception as e:
        logger.error(f"Error showing calendar status: {e}")
        await callback.answer("❌ Ошибка получения статуса")


@router.callback_query(F.data == "toggle_notifications")
async def cq_toggle_notifications(callback: types.CallbackQuery, state: FSMContext):
    """Toggle notifications on/off"""
    user_id = callback.from_user.id
    
    try:
        # Get current setting
        notifications_enabled = await get_user_setting(user_id, 'notifications_enabled', True)
        new_setting = not notifications_enabled
        
        # Save new setting
        await update_user_setting(user_id, 'notifications_enabled', new_setting)
        
        status_text = "включены" if new_setting else "отключены"
        await callback.answer(f"🔔 Уведомления {status_text}")
        
        # Refresh notifications menu
        await cq_notifications_settings_menu(callback, state)
        
    except Exception as e:
        logger.error(f"Error toggling notifications: {e}")
        await callback.answer("❌ Ошибка изменения настройки")


@router.callback_query(F.data.startswith("_notifications"))
async def cq_notification_category_settings(callback: types.CallbackQuery, state: FSMContext):
    """Handle specific notification category settings"""
    category = callback.data.replace("_notifications", "")
    
    await callback.answer(
        f"⚙️ Настройки уведомлений категории '{category}' будут добавлены в следующих версиях.",
        show_alert=True
    )


@router.callback_query(F.data == "retention_info")
async def cq_retention_info(callback: types.CallbackQuery, state: FSMContext):
    """Show detailed information about data retention"""
    info_text = (
        "📚 <b>Подробная информация о хранении данных</b>\n\n"
        "🗂️ <b>Что сохраняется:</b>\n"
        "• Тексты сессий разговоров\n"
        "• Сгенерированные резюме\n"
        "• Извлеченные события и задачи\n"
        "• Время создания и статус сессий\n\n"
        "🗑️ <b>Что удаляется автоматически:</b>\n"
        "• Завершенные сессии старше выбранного периода\n"
        "• Связанные с ними события (только из БД)\n"
        "• Временные файлы транскрипции\n\n"
        "✅ <b>Что сохраняется навсегда:</b>\n"
        "• Настройки пользователя\n"
        "• Подключения к календарю\n"
        "• События в Google Calendar\n\n"
        "🔄 <b>Периодичность очистки:</b>\n"
        "Автоматическая очистка выполняется ежедневно в 03:00 UTC"
    )
    
    await callback.answer(info_text, show_alert=True)


@router.callback_query(F.data == "custom_retention")
async def cq_custom_retention(callback: types.CallbackQuery, state: FSMContext):
    """Handle custom retention period setting"""
    await callback.answer(
        "⚙️ Настройка произвольного периода хранения будет добавлена в следующих версиях.\n\n"
        "Пока используйте предустановленные варианты: 7, 30, 90, 365 дней или 'навсегда'.",
        show_alert=True
    )


@router.callback_query(F.data == "select_calendar")
async def cq_select_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Handle calendar selection"""
    await callback.answer(
        "📅 Выбор конкретного календаря будет доступен после подключения к Google Calendar.\n\n"
        "Используйте команду /connect_calendar для подключения.",
        show_alert=True
    )
