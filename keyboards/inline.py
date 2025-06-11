from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SUPPORTED_LANGUAGES, SUMMARY_STYLES


def get_main_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗣️ Язык транскрибации", callback_data="settings:language")
    builder.button(text="💡 Стиль резюме", callback_data="settings:summary_style")
    builder.button(text="📅 Календарь", callback_data="settings:calendar")
    builder.button(text="🔔 Уведомления", callback_data="settings:notifications")
    builder.button(text="📚 Хранение данных", callback_data="settings:data_retention")
    builder.button(text="◀️ Закрыть настройки", callback_data="settings:close")
    builder.adjust(1)
    return builder.as_markup()


def get_language_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, name in SUPPORTED_LANGUAGES.items():
        text = f"✅ {name}" if code == current_lang else name
        builder.button(text=text, callback_data=f"select_lang:{code}")
    builder.button(text="◀️ Назад к настройкам", callback_data="settings:main")
    builder.adjust(1)
    return builder.as_markup()


def get_summary_style_keyboard(current_style: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, style_info in SUMMARY_STYLES.items():
        name = style_info["name"]
        text = f"✅ {name}" if code == current_style else name
        builder.button(text=text, callback_data=f"select_style:{code}")
    builder.button(text="◀️ Назад к настройкам", callback_data="settings:main")
    builder.adjust(1)
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_state")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_capture_session_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for active capture session"""
    buttons = [
        [InlineKeyboardButton(text="🛑 Завершить сессию", callback_data="end_capture")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_capture")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_sessions_pagination_keyboard(
    current_page: int, 
    total_pages: int, 
    status_filter: str = None, 
    search_query: str = None
) -> InlineKeyboardMarkup:
    """Create pagination keyboard for session history"""
    builder = InlineKeyboardBuilder()
    
    # Build callback data parts - handle None values properly
    filter_part = status_filter or "none"
    search_part = search_query.replace(" ", "_") if search_query else "none"
    
    # Previous page button
    if current_page > 1:
        prev_callback = f"sessions_page_{current_page - 1}_{filter_part}_{search_part}"
        builder.button(text="◀️ Назад", callback_data=prev_callback)
    
    # Page info
    builder.button(text=f"📄 {current_page}/{total_pages}", callback_data="sessions_page_info")
    
    # Next page button  
    if current_page < total_pages:
        next_callback = f"sessions_page_{current_page + 1}_{filter_part}_{search_part}"
        builder.button(text="Вперед ▶️", callback_data=next_callback)
    
    # Filter buttons row
    if status_filter != "completed":
        builder.button(text="✅ Завершенные", callback_data=f"sessions_page_1_completed_{search_part}")
    if status_filter != "active":
        builder.button(text="🔄 Активные", callback_data=f"sessions_page_1_active_{search_part}")
    if status_filter:
        builder.button(text="🗂️ Все", callback_data=f"sessions_page_1_none_{search_part}")
    
    # Refresh button
    refresh_callback = f"sessions_page_{current_page}_{filter_part}_{search_part}"
    builder.button(text="🔄 Обновить", callback_data=refresh_callback)
    
    # Layout: navigation on first row, filters on second, refresh on third
    builder.adjust(3, 3, 1)
    return builder.as_markup()


def get_session_actions_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Create action keyboard for individual session"""
    builder = InlineKeyboardBuilder()
    
    # Main actions
    builder.button(text="📄 Экспорт текста", callback_data=f"export_session_{session_id}_text")
    builder.button(text="📊 Экспорт JSON", callback_data=f"export_session_{session_id}_json")
    
    # Share options
    builder.button(text="📤 Поделиться резюме", callback_data=f"share_session_{session_id}_summary")
    builder.button(text="📅 Поделиться событиями", callback_data=f"share_session_{session_id}_events")
    
    # Navigation
    builder.button(text="📚 К списку сессий", callback_data="back_to_sessions")
    builder.button(text="🗑️ Удалить сессию", callback_data=f"delete_session_{session_id}")
    
    # Layout: 2 export buttons, 2 share buttons, 2 navigation buttons
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def get_delete_confirm_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard for session deletion"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="❌ Да, удалить", callback_data=f"confirm_delete_{session_id}")
    builder.button(text="↩️ Отмена", callback_data=f"cancel_delete_{session_id}")
    
    builder.adjust(2)
    return builder.as_markup()


def get_export_format_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Format selection keyboard for export"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📄 Простой текст", callback_data=f"export_format_{session_id}_txt")
    builder.button(text="📝 Markdown", callback_data=f"export_format_{session_id}_md")
    builder.button(text="📊 JSON (полный)", callback_data=f"export_format_{session_id}_json")
    builder.button(text="📋 CSV (события)", callback_data=f"export_format_{session_id}_csv")
    
    builder.button(text="↩️ Назад", callback_data=f"back_to_session_{session_id}")
    
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_calendar_connection_keyboard(auth_url: str, state: str) -> InlineKeyboardMarkup:
    """Keyboard for Google Calendar connection"""
    builder = InlineKeyboardBuilder()
    
    # OAuth authorization button
    builder.button(text="🔗 Открыть Google OAuth", url=auth_url)
    
    builder.adjust(1)
    return builder.as_markup()


def get_calendar_disconnect_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for connected calendar management"""
    builder = InlineKeyboardBuilder()
    
    # Disconnect option
    builder.button(text="🔌 Отключить календарь", callback_data="disconnect_calendar")
    
    builder.adjust(1)
    return builder.as_markup()



def get_calendar_list_keyboard(calendars: list, current_calendar_id: str = None) -> InlineKeyboardMarkup:
    """Keyboard for calendar selection"""
    builder = InlineKeyboardBuilder()
    
    for calendar in calendars:
        calendar_id = calendar.get('id', '')
        calendar_name = calendar.get('summary', 'Без названия')
        
        # Mark current calendar
        if calendar_id == current_calendar_id:
            text = f"✅ {calendar_name}"
        else:
            text = f"📅 {calendar_name}"
        
        builder.button(text=text, callback_data=f"select_cal_{calendar_id}")
    
    # Back button
    builder.button(text="↩️ Назад к настройкам", callback_data="calendar_settings")
    
    builder.adjust(1)
    return builder.as_markup()


def get_oauth_instructions_keyboard() -> InlineKeyboardMarkup:
    """Instructions keyboard for OAuth flow"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔗 Понятно, открыть Google", callback_data="understood_oauth")
    builder.button(text="❓ Помощь", callback_data="oauth_help")
    builder.button(text="↩️ Назад", callback_data="back_to_oauth")
    
    builder.adjust(1, 2)
    return builder.as_markup()


def get_calendar_sync_keyboard(session_id: int, events_count: int) -> InlineKeyboardMarkup:
    """Keyboard for calendar synchronization"""
    builder = InlineKeyboardBuilder()
    
    # Main sync button
    builder.button(
        text=f"📅 Создать {events_count} событий в календаре", 
        callback_data=f"sync_calendar_{session_id}"
    )
    
    # Skip option
    builder.button(text="⏭️ Пропустить", callback_data=f"skip_calendar_{session_id}")
    
    # Session actions
    builder.button(text="📋 Детали сессии", callback_data=f"show_session_{session_id}")
    builder.button(text="📚 К списку сессий", callback_data="back_to_sessions")
    
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def get_event_confirmation_keyboard(session_id: int, event_count: int, event_selection: dict = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for event confirmation interface
    """
    if event_selection is None:
        event_selection = {f"event_{i}": True for i in range(event_count)}
    
    buttons = []
    
    # Individual event toggle buttons (first 6 events)
    max_individual_buttons = min(6, event_count)
    event_row = []
    
    for i in range(max_individual_buttons):
        selected = event_selection.get(f"event_{i}", True)
        emoji = "✅" if selected else "☑️"
        callback_data = f"toggle_event_{session_id}_{i}"
        event_row.append(InlineKeyboardButton(text=f"{emoji}{i+1}", callback_data=callback_data))
        
        # Add row every 3 buttons
        if len(event_row) == 3:
            buttons.append(event_row)
            event_row = []
    
    # Add remaining buttons in last row
    if event_row:
        buttons.append(event_row)
    
    # If more than 6 events, show summary
    if event_count > 6:
        selected_count = sum(1 for selected in event_selection.values() if selected)
        buttons.append([InlineKeyboardButton(
            text=f"📊 Выбрано: {selected_count}/{event_count}",
            callback_data="show_selection_summary"
        )])
    
    # Mass selection buttons
    mass_buttons = []
    selected_count = sum(1 for selected in event_selection.values() if selected)
    
    if selected_count < event_count:
        mass_buttons.append(InlineKeyboardButton(
            text="✅ Выбрать все",
            callback_data=f"select_all_events_{session_id}"
        ))
    
    if selected_count > 0:
        mass_buttons.append(InlineKeyboardButton(
            text="☑️ Исключить все",
            callback_data=f"deselect_all_events_{session_id}"
        ))
    
    if mass_buttons:
        buttons.append(mass_buttons)
    
    # Action buttons
    action_buttons = []
    
    if selected_count > 0:
        action_buttons.append(InlineKeyboardButton(
            text=f"📅 Создать ({selected_count})",
            callback_data=f"confirm_create_events_{session_id}"
        ))
    
    action_buttons.append(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"skip_calendar_{session_id}"
    ))
    
    buttons.append(action_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_calendar_settings_menu_keyboard(calendar_connected: bool = False, auto_create: bool = False) -> InlineKeyboardMarkup:
    """Calendar settings submenu keyboard"""
    builder = InlineKeyboardBuilder()
    
    if calendar_connected:
        # Calendar is connected
        builder.button(text="✅ Календарь подключен", callback_data="calendar_status")
        
        # Auto-create toggle
        auto_text = "✅ Автосоздание событий" if auto_create else "☑️ Автосоздание событий"
        builder.button(text=auto_text, callback_data="toggle_auto_create")
        
        # Management options
        builder.button(text="📅 Выбрать календарь", callback_data="select_calendar")
        builder.button(text="🔌 Отключить календарь", callback_data="disconnect_calendar")
    else:
        # Calendar not connected
        builder.button(text="❌ Календарь не подключен", callback_data="calendar_status")
        builder.button(text="🔗 Подключить календарь", callback_data="connect_calendar_from_settings")
    
    # Back button
    builder.button(text="◀️ Назад к настройкам", callback_data="settings:main")
    
    builder.adjust(1)
    return builder.as_markup()


def get_notifications_settings_keyboard(notifications_enabled: bool = True) -> InlineKeyboardMarkup:
    """Notifications settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    # Notifications toggle
    notif_text = "🔔 Уведомления включены" if notifications_enabled else "🔕 Уведомления отключены"
    builder.button(text=notif_text, callback_data="toggle_notifications")
    
    # Specific notification settings (if enabled)
    if notifications_enabled:
        builder.button(text="📅 Уведомления событий", callback_data="event_notifications")
        builder.button(text="📊 Уведомления о сессиях", callback_data="session_notifications")
        builder.button(text="⚠️ Уведомления об ошибках", callback_data="error_notifications")
    
    # Back button
    builder.button(text="◀️ Назад к настройкам", callback_data="settings:main")
    
    builder.adjust(1)
    return builder.as_markup()


def get_data_retention_keyboard(retention_days: int = 30) -> InlineKeyboardMarkup:
    """Data retention settings keyboard"""
    builder = InlineKeyboardBuilder()
    
    # Current setting info
    builder.button(text=f"📚 Хранить {retention_days} дней", callback_data="retention_info")
    
    # Quick options
    retention_options = [7, 30, 90, 365]
    for days in retention_options:
        if days != retention_days:
            text = f"📅 {days} дней"
            if days == 7:
                text = "📅 1 неделя"
            elif days == 30:
                text = "📅 1 месяц"
            elif days == 90:
                text = "📅 3 месяца"
            elif days == 365:
                text = "📅 1 год"
            
            builder.button(text=text, callback_data=f"set_retention_{days}")
    
    # Custom option
    builder.button(text="⚙️ Настроить вручную", callback_data="custom_retention")
    
    # Never delete option
    builder.button(text="♾️ Хранить всегда", callback_data="set_retention_0")
    
    # Back button
    builder.button(text="◀️ Назад к настройкам", callback_data="settings:main")
    
    builder.adjust(1, 2, 1, 1, 1)
    return builder.as_markup()


def get_auto_create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for auto-create toggle"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Да, изменить", callback_data="confirm_auto_create")
    builder.button(text="❌ Отмена", callback_data="cancel_auto_create")
    
    builder.adjust(2)
    return builder.as_markup()


def get_disconnect_calendar_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for calendar disconnection"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔌 Да, отключить", callback_data="confirm_disconnect_calendar")
    builder.button(text="❌ Отмена", callback_data="cancel_disconnect_calendar")
    
    builder.adjust(2)
    return builder.as_markup()
