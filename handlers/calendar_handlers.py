"""
Handlers for Google Calendar connection and OAuth flow
"""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from services.google_oauth import google_oauth
from keyboards.inline import get_calendar_connection_keyboard, get_calendar_disconnect_keyboard

router = Router()


@router.message(Command("connect_calendar"))
async def cmd_connect_calendar(message: types.Message, state: FSMContext):
    """
    Start Google Calendar connection process
    """
    user_id = message.from_user.id
    
    # Check if already connected
    is_connected = await google_oauth.check_user_connected(user_id)
    
    if is_connected:
        await message.answer(
            "✅ <b>Google Calendar уже подключен!</b>\n\n"
            "📅 Вы можете создавать события в календаре из извлеченных событий сессий.\n\n"
            "💡 Используйте кнопки ниже для управления подключением:",
            reply_markup=get_calendar_disconnect_keyboard()
        )
        return
    
    # Generate OAuth URL
    try:
        auth_url, state = google_oauth.generate_auth_url(user_id)
        
        await message.answer(
            "🔗 <b>Подключение Google Calendar</b>\n\n"
            "📋 Для подключения календаря:\n"
            "1️⃣ Нажмите кнопку ниже\n"
            "2️⃣ Войдите в Google аккаунт\n"
            "3️⃣ Разрешите доступ к календарю\n"
            "4️⃣ Скопируйте код авторизации\n"
            "5️⃣ Отправьте код в этот чат\n\n"
            f"🔐 <b>Код состояния:</b> <code>{state}</code>\n"
            "💡 <i>Сохраните этот код - он понадобится после авторизации</i>",
            reply_markup=get_calendar_connection_keyboard(auth_url, state)
        )
        
        # Store state in FSM for later verification
        await state.update_data(oauth_state=state)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при создании ссылки авторизации: {str(e)}\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


@router.message(F.text.startswith("/oauth_callback"))
async def cmd_oauth_callback(message: types.Message, state: FSMContext):
    """
    Handle OAuth callback with authorization code
    Format: /oauth_callback CODE STATE
    """
    parts = message.text.split()
    
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Используйте: <code>/oauth_callback КОД СОСТОЯНИЕ</code>\n"
            "где КОД - код авторизации от Google, а СОСТОЯНИЕ - код состояния из предыдущего сообщения."
        )
        return
    
    auth_code = parts[1]
    oauth_state = parts[2]
    
    # Get stored state from FSM
    data = await state.get_data()
    stored_state = data.get('oauth_state')
    
    if not stored_state or stored_state != oauth_state:
        await message.answer(
            "❌ Неверный код состояния.\n\n"
            "Убедитесь, что вы используете правильный код состояния из сообщения с авторизацией."
        )
        return
    
    # Exchange code for tokens
    try:
        await message.answer("🔄 Обмениваю код на токены доступа...")
        
        tokens = await google_oauth.exchange_code_for_tokens(auth_code, oauth_state)
        
        if tokens:
            await message.answer(
                "✅ <b>Google Calendar успешно подключен!</b>\n\n"
                "🎉 Теперь вы можете:\n"
                "• Создавать события в календаре из сессий\n"
                "• Автоматически добавлять извлеченные встречи\n"
                "• Синхронизировать действия с календарем\n\n"
                "💡 События будут создаваться в вашем основном календаре.",
                reply_markup=get_calendar_disconnect_keyboard()
            )
            
            # Clear OAuth state from FSM
            await state.update_data(oauth_state=None)
            
        else:
            await message.answer(
                "❌ Не удалось получить токены доступа.\n\n"
                "Возможные причины:\n"
                "• Неверный код авторизации\n"
                "• Истек срок действия кода\n"
                "• Проблемы с Google API\n\n"
                "Попробуйте подключить календарь заново: /connect_calendar"
            )
    
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке авторизации: {str(e)}\n\n"
            "Попробуйте подключить календарь заново: /connect_calendar"
        )


# Alternative handler for users who send just the code without command
@router.message(F.text.regexp(r'^[a-zA-Z0-9/_-]{20,}$'))
async def handle_oauth_code(message: types.Message, state: FSMContext):
    """
    Handle OAuth authorization code sent as plain text
    """
    # Check if we're expecting an OAuth code
    data = await state.get_data()
    stored_state = data.get('oauth_state')
    
    if not stored_state:
        # Not in OAuth flow, ignore
        return
    
    auth_code = message.text.strip()
    
    await message.answer(
        f"🔍 Обнаружен код авторизации!\n\n"
        f"Если это код от Google, отправьте его в формате:\n"
        f"<code>/oauth_callback {auth_code} {stored_state}</code>\n\n"
        f"Или нажмите кнопку ниже для автоматической обработки:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(
                text="✅ Обработать код", 
                callback_data=f"process_oauth_{auth_code}_{stored_state}"
            )],
            [types.InlineKeyboardButton(
                text="❌ Это не код Google", 
                callback_data="ignore_oauth_code"
            )]
        ])
    )


@router.callback_query(F.data.startswith("process_oauth_"))
async def cq_process_oauth_code(callback: types.CallbackQuery, state: FSMContext):
    """Process OAuth code from callback"""
    await callback.answer()
    
    data_parts = callback.data.split("_", 3)
    if len(data_parts) < 4:
        await callback.message.edit_text("❌ Неверные данные авторизации.")
        return
    
    auth_code = data_parts[2]
    oauth_state = data_parts[3]
    
    # Process like the command handler
    try:
        await callback.message.edit_text("🔄 Обмениваю код на токены доступа...")
        
        tokens = await google_oauth.exchange_code_for_tokens(auth_code, oauth_state)
        
        if tokens:
            await callback.message.edit_text(
                "✅ <b>Google Calendar успешно подключен!</b>\n\n"
                "🎉 Теперь вы можете:\n"
                "• Создавать события в календаре из сессий\n"
                "• Автоматически добавлять извлеченные встречи\n"
                "• Синхронизировать действия с календарем\n\n"
                "💡 События будут создаваться в вашем основном календаре.",
                reply_markup=get_calendar_disconnect_keyboard()
            )
            
            # Clear OAuth state from FSM
            await state.update_data(oauth_state=None)
            
        else:
            await callback.message.edit_text(
                "❌ Не удалось получить токены доступа.\n\n"
                "Попробуйте подключить календарь заново: /connect_calendar"
            )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при обработке авторизации: {str(e)}\n\n"
            "Попробуйте подключить календарь заново: /connect_calendar"
        )


@router.callback_query(F.data == "ignore_oauth_code")
async def cq_ignore_oauth_code(callback: types.CallbackQuery, state: FSMContext):
    """Ignore the OAuth code detection"""
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data == "disconnect_calendar")
async def cq_disconnect_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Handle calendar disconnection request"""
    await callback.answer()
    
    await callback.message.edit_text(
        "🔌 <b>Отключение Google Calendar</b>\n\n"
        "⚠️ После отключения:\n"
        "• События не будут создаваться автоматически\n"
        "• Доступ к календарю будет отозван\n"
        "• Потребуется повторная авторизация для подключения\n\n"
        "Вы уверены, что хотите отключить календарь?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Да, отключить", callback_data="confirm_disconnect")],
            [types.InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel_disconnect")]
        ])
    )


@router.callback_query(F.data == "confirm_disconnect")
async def cq_confirm_disconnect(callback: types.CallbackQuery, state: FSMContext):
    """Confirm calendar disconnection"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    try:
        success = await google_oauth.revoke_user_access(user_id)
        
        if success:
            await callback.message.edit_text(
                "✅ Google Calendar успешно отключен.\n\n"
                "🔗 Для повторного подключения используйте: /connect_calendar"
            )
        else:
            await callback.message.edit_text(
                "⚠️ Календарь отключен локально, но могли возникнуть проблемы с отзывом токенов.\n\n"
                "🔗 Для повторного подключения используйте: /connect_calendar"
            )
    
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при отключении: {str(e)}\n\n"
            "🔗 Для повторного подключения используйте: /connect_calendar"
        )


@router.callback_query(F.data == "cancel_disconnect")
async def cq_cancel_disconnect(callback: types.CallbackQuery, state: FSMContext):
    """Cancel calendar disconnection"""
    await callback.answer()
    
    await callback.message.edit_text(
        "✅ Google Calendar остается подключенным.\n\n"
        "📅 Вы можете создавать события в календаре из извлеченных событий сессий.",
        reply_markup=get_calendar_disconnect_keyboard()
    )


@router.message(Command("calendar_status"))
async def cmd_calendar_status(message: types.Message, state: FSMContext):
    """
    Check Google Calendar connection status
    """
    user_id = message.from_user.id
    
    try:
        is_connected = await google_oauth.check_user_connected(user_id)
        
        if is_connected:
            await message.answer(
                "✅ <b>Google Calendar подключен</b>\n\n"
                "📅 Статус: Активен\n"
                "🔐 Токены: Валидны\n"
                "⚡ Функции: Доступны\n\n"
                "💡 Используйте кнопки для управления подключением:",
                reply_markup=get_calendar_disconnect_keyboard()
            )
        else:
            await message.answer(
                "❌ <b>Google Calendar не подключен</b>\n\n"
                "📅 Статус: Не активен\n"
                "🔐 Токены: Отсутствуют\n"
                "⚡ Функции: Недоступны\n\n"
                "🔗 Для подключения используйте: /connect_calendar"
            )
    
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при проверке статуса: {str(e)}\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        ) 