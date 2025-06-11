"""
Handlers for conversation capture session commands
"""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from states.user_states import CaptureStates
from services.session_manager import session_manager
from services.analysis import gpt_analysis
from services.database import CaptureSession, Event
from keyboards.inline import get_capture_session_keyboard, get_sessions_pagination_keyboard
from services.google_calendar import google_calendar
from services.google_oauth import google_oauth

router = Router()


@router.message(Command("capture_chat"))
async def cmd_capture_chat(message: types.Message, state: FSMContext):
    """
    Start a new conversation capture session
    """
    user_id = message.from_user.id
    
    # Check if user already has an active session
    active_session = await session_manager.start_capture_session(user_id, state)
    
    if not active_session:
        await message.answer(
            "❌ Произошла ошибка при создании сессии. Попробуйте еще раз."
        )
        return
    
    # Check if this was an existing session
    current_state = await state.get_state()
    if current_state == CaptureStates.CAPTURING:
        # Session was already active
        session_info = await session_manager.get_session_info(state)
        message_count = len(active_session.messages) if active_session.messages else 0
        
        await message.answer(
            f"📝 У вас уже есть активная сессия захвата!\n\n"
            f"📊 Собрано сообщений: {message_count}\n"
            f"🕐 Начата: {active_session.start_time.strftime('%H:%M %d.%m.%Y')}\n\n"
            "Продолжайте отправлять сообщения или завершите сессию.",
            reply_markup=get_capture_session_keyboard()
        )
    else:
        # New session created
        await message.answer(
            "🎯 <b>Сессия захвата начата!</b>\n\n"
            "📝 Теперь отправляйте мне сообщения (текст, голос, аудио), "
            "которые нужно объединить и проанализировать.\n\n"
            "💡 Все ваши сообщения будут сохранены в одну сессию. "
            "После завершения я создам общее резюме и найду важные события.\n\n"
            "🛑 Нажмите кнопку ниже или используйте /end_capture когда закончите.",
            reply_markup=get_capture_session_keyboard()
        )


@router.callback_query(F.data == "end_capture")
async def cq_end_capture(callback: types.CallbackQuery, state: FSMContext):
    """
    Handle end capture button press
    """
    await callback.answer()
    
    # Use the same logic as /end_capture command
    await end_capture_session(callback.message, state, edit_message=True)


@router.callback_query(F.data == "cancel_capture")
async def cq_cancel_capture(callback: types.CallbackQuery, state: FSMContext):
    """
    Handle cancel capture button press
    """
    await callback.answer()
    
    user_id = callback.from_user.id
    success = await session_manager.cancel_session(user_id, state)
    
    text = "✅ Сессия захвата отменена." if success else "❌ Ошибка при отмене сессии."
    
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)


@router.message(Command("end_capture"))
async def cmd_end_capture(message: types.Message, state: FSMContext):
    """
    End active capture session and start processing
    """
    await end_capture_session(message, state)


async def end_capture_session(message: types.Message, state: FSMContext, edit_message: bool = False):
    """
    Common logic for ending capture session
    """
    user_id = message.from_user.id
    
    # Check if user has active session
    current_state = await state.get_state()
    if current_state != CaptureStates.CAPTURING:
        text = "❌ У вас нет активной сессии захвата."
        if edit_message:
            try:
                await message.edit_text(text)
            except Exception:
                await message.answer(text)
        else:
            await message.answer(text)
        return
    
    # End the session
    session = await session_manager.end_capture_session(user_id, state)
    
    if not session:
        text = "❌ Ошибка при завершении сессии."
        if edit_message:
            try:
                await message.edit_text(text)
            except Exception:
                await message.answer(text)
        else:
            await message.answer(text)
        return
    
    # Show session summary
    message_count = len(session.messages) if session.messages else 0
    full_text = session.get_full_text()
    
    if message_count == 0:
        text = (
            "⚠️ Сессия завершена, но не было собрано ни одного сообщения.\n"
            "Сессия сохранена как пустая."
        )
        # Complete processing immediately for empty session
        await session_manager.complete_session_processing(user_id, state, "", [])
    else:
        text = (
            f"✅ <b>Сессия захвата завершена!</b>\n\n"
            f"📊 Собрано сообщений: {message_count}\n"
            f"📏 Общий объем текста: {len(full_text)} символов\n\n"
            "🔄 Начинаю анализ и обработку...\n"
            "Это может занять несколько секунд."
        )
        
        # Trigger GPT analysis
        await process_session_with_gpt(user_id, state, session, message)
    
    if edit_message:
        try:
            await message.edit_text(text)
        except Exception:
            await message.answer(text)
    else:
        await message.answer(text)


# Handler for capturing messages during session
@router.message(CaptureStates.CAPTURING)
async def handle_capture_message(message: types.Message, state: FSMContext):
    """
    Handle messages during active capture session
    """
    user_id = message.from_user.id
    message_text = ""
    
    # Extract text from different message types
    if message.text:
        message_text = message.text
    elif message.voice:
        message_text = "[ГОЛОСОВОЕ СООБЩЕНИЕ - будет транскрибировано]"
        # TODO: In later tasks, integrate with existing whisper transcription
    elif message.audio:
        message_text = "[АУДИО ФАЙЛ - будет транскрибирован]"
    elif message.document:
        message_text = f"[ДОКУМЕНТ: {message.document.file_name}]"
    elif message.photo:
        message_text = "[ФОТО]"
    else:
        message_text = "[НЕПОДДЕРЖИВАЕМЫЙ ТИП СООБЩЕНИЯ]"
    
    # Add message to session
    success = await session_manager.add_message_to_session(user_id, message_text, state)
    
    if success:
        # Get current message count
        session_info = await session_manager.get_session_info(state)
        
        # Send confirmation (every 5 messages to avoid spam)
        # Get actual count from database
        from services.database import get_active_session
        active_session = await get_active_session(user_id)
        message_count = len(active_session.messages) if active_session and active_session.messages else 0
        
        if message_count % 5 == 0 or message_count == 1:
            await message.reply(
                f"✅ Сообщение добавлено в сессию ({message_count})",
                reply_markup=get_capture_session_keyboard()
            )
    else:
        await message.reply("❌ Ошибка при добавлении сообщения в сессию.")


async def process_session_with_gpt(user_id: int, state: FSMContext, session, message: types.Message):
    """
    Process captured session with GPT analysis with comprehensive error handling
    """
    analysis_msg = None
    try:
        # Get full conversation text
        full_text = session.get_full_text()
        
        # Validate session has content
        if not full_text or len(full_text.strip()) < 10:
            await session_manager.complete_session_processing(
                user_id, state, 
                "⚠️ Сессия слишком короткая для анализа", 
                []
            )
            await message.answer("⚠️ Сессия содержит мало текста для анализа.")
            return
        
        # Show progress to user with more detailed status
        analysis_msg = await message.answer(
            "🔄 <b>Анализирую сессию...</b>\n\n"
            f"📊 Объем текста: {len(full_text)} символов\n"
            "⏳ Это может занять 30-60 секунд\n\n"
            "🤖 Извлекаю события и создаю резюме..."
        )
        
        # Perform GPT analysis with database saving
        print(f"Starting GPT analysis for session {session.id}, user {user_id}")
        analysis_result = await gpt_analysis.analyze_conversation(
            full_text, 
            session_id=session.id, 
            user_id=user_id
        )
        
        # Validate analysis result
        if not analysis_result or not isinstance(analysis_result, dict):
            raise ValueError("Invalid analysis result format")
        
        # Extract and validate results
        summary = analysis_result.get("summary", "")
        events = analysis_result.get("events", [])
        
        # Log results for debugging
        print(f"Analysis completed: {len(events)} events found")
        
        # Check for analysis errors in summary
        if summary.startswith("❌"):
            print(f"Analysis error in summary: {summary}")
            # Still save the session but mark as partial failure
            await session_manager.complete_session_processing(
                user_id, state, summary, []
            )
            await show_analysis_results(analysis_msg, summary, [], len(session.messages) if session.messages else 0)
            return
        
        # Complete session processing with results
        success = await session_manager.complete_session_processing(
            user_id, state, summary, events
        )
        
        if not success:
            raise Exception("Failed to save session results to database")
        
        # Show results to user
        message_count = len(session.messages) if session.messages else 0
        await show_analysis_results(analysis_msg, summary, events, message_count)
        
        print(f"Session {session.id} processing completed successfully")
        
    except Exception as e:
        # Enhanced error handling with specific error types
        error_msg = str(e)
        print(f"Error processing session {session.id if session else 'unknown'}: {error_msg}")
        
        # Determine error type and create appropriate message
        if "rate limit" in error_msg.lower() or "rate_limit" in error_msg.lower():
            user_error = "⏳ Превышен лимит запросов к AI. Попробуйте через несколько минут."
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            user_error = "🌐 Проблема с подключением к AI сервису. Попробуйте позже."
        elif "api" in error_msg.lower():
            user_error = "🤖 Временная проблема с AI сервисом. Сессия сохранена."
        elif "invalid" in error_msg.lower():
            user_error = "📝 Не удалось обработать результат анализа. Сессия сохранена."
        else:
            user_error = f"❌ Ошибка при анализе: {error_msg}"
        
        # Always try to complete session processing to avoid stuck state
        try:
            await session_manager.complete_session_processing(
                user_id, state, user_error, []
            )
        except Exception as completion_error:
            print(f"Failed to complete session processing: {completion_error}")
            # Force clear state to prevent user being stuck
            try:
                await state.clear()
            except:
                pass
        
        # Inform user about the error
        try:
            if analysis_msg:
                await analysis_msg.edit_text(
                    f"⚠️ <b>Анализ завершен с ошибкой</b>\n\n"
                    f"{user_error}\n\n"
                    "💾 Ваши сообщения сохранены и доступны в /my_sessions"
                )
            else:
                await message.answer(
                    f"⚠️ <b>Ошибка при анализе сессии</b>\n\n"
                    f"{user_error}\n\n"
                    "💾 Сообщения сохранены в истории."
                )
        except Exception as msg_error:
            print(f"Failed to send error message to user: {msg_error}")
            # Last resort - try simple message
            try:
                await message.answer("⚠️ Анализ завершен с ошибкой. Сессия сохранена.")
            except:
                pass


async def show_analysis_results(message: types.Message, summary: str, events: list, message_count: int):
    """
    Display analysis results to user with enhanced formatting and event confirmation options
    """
    try:
        # Prepare summary text with better formatting
        result_text = f"✅ <b>Анализ сессии завершен!</b>\n\n"
        result_text += f"📊 Обработано сообщений: <code>{message_count}</code>\n\n"
        
        # Summary section with better formatting
        if summary and not summary.startswith("❌"):
            result_text += f"📝 <b>Резюме:</b>\n<i>{summary}</i>\n\n"
        elif summary.startswith("❌"):
            result_text += f"⚠️ <b>Ошибка анализа:</b>\n{summary}\n\n"
        else:
            result_text += f"📝 <b>Резюме:</b>\n<i>Не удалось создать резюме</i>\n\n"
        
        # Events section with priority indicators
        if events:
            result_text += f"📅 <b>Найденные события ({len(events)}):</b>\n"
            
            # Sort events by priority and type
            sorted_events = sorted(events, key=lambda x: (
                {"high": 0, "medium": 1, "low": 2}.get(x.get("priority", "medium"), 1),
                {"deadline": 0, "meeting": 1, "task": 2, "appointment": 3, "reminder": 4}.get(x.get("type", "event"), 5)
            ))
            
            for i, event in enumerate(sorted_events, 1):
                # Priority indicator
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.get("priority", "medium"), "🟡")
                
                # Type indicator  
                type_emoji = {
                    "meeting": "🤝", "deadline": "⏰", "task": "📋", 
                    "appointment": "📅", "reminder": "🔔"
                }.get(event.get("type", "event"), "📌")
                
                result_text += f"\n{i}. {priority_emoji}{type_emoji} <b>{event.get('title', 'Без названия')}</b>\n"
                
                # Date and time with better formatting
                if event.get('date') or event.get('time'):
                    date_str = ""
                    if event.get('date'):
                        date_str = event['date']
                    if event.get('time'):
                        time_str = event['time']
                        date_str += f" в {time_str}" if date_str else f"Время: {time_str}"
                    if date_str:
                        result_text += f"   🕐 <code>{date_str}</code>\n"
                
                # Location
                if event.get('location'):
                    result_text += f"   📍 {event['location']}\n"
                
                # Participants with count
                if event.get('participants'):
                    participants = event['participants']
                    if len(participants) > 3:
                        result_text += f"   👥 {', '.join(participants[:3])} и еще {len(participants)-3}\n"
                    else:
                        result_text += f"   👥 {', '.join(participants)}\n"
                
                # Action items with numbering
                if event.get('action_items'):
                    items = event['action_items']
                    if len(items) == 1:
                        result_text += f"   ✅ {items[0]}\n"
                    else:
                        result_text += f"   ✅ Задачи ({len(items)}):\n"
                        for j, item in enumerate(items[:3], 1):  # Show max 3 items
                            result_text += f"      {j}. {item}\n"
                        if len(items) > 3:
                            result_text += f"      ... и еще {len(items)-3}\n"
                
                # Type and priority info
                if event.get('type') != 'event' or event.get('priority') != 'medium':
                    type_name = {
                        "meeting": "встреча", "deadline": "дедлайн", "task": "задача", 
                        "appointment": "встреча", "reminder": "напоминание"
                    }.get(event.get('type', 'event'), 'событие')
                    
                    priority_name = {
                        "high": "высокий", "medium": "средний", "low": "низкий"
                    }.get(event.get('priority', 'medium'), 'средний')
                    
                    result_text += f"   📊 {type_name.title()}, приоритет: {priority_name}\n"
            
            # Add confirmation options for events with calendar sync
            result_text += f"\n💡 <b>Что дальше?</b>\n"
            result_text += "• Используйте /my_sessions для просмотра истории\n"
            result_text += "• Настройте /connect_calendar для синхронизации\n"
            
            # Check if calendar is connected and add sync option
            session_data = await session_manager.get_current_session_data(message.from_user.id)
            session_id = session_data.get('session_id') if session_data else None
            
            if session_id:
                is_calendar_connected = await google_oauth.check_user_connected(message.from_user.id)
                if is_calendar_connected:
                    result_text += f"\n📅 <b>Календарь подключен!</b>\n"
                    # Smart message splitting with calendar sync keyboard
                    await send_long_message_with_calendar_sync(message, result_text, events, session_id)
                    return
                else:
                    result_text += f"\n📅 <b>Подключите календарь</b> для автоматического создания событий:\n"
                    result_text += "/connect_calendar\n"
            
        else:
            result_text += "📅 <b>События не найдены</b>\n"
            result_text += "В сессии не было обнаружено встреч, дедлайнов или задач.\n\n"
            result_text += "💡 <b>Совет:</b> Попробуйте более подробно описать даты, время и задачи в следующих сессиях."
        
        # Smart message splitting
        await send_long_message(message, result_text, events)
            
    except Exception as e:
        # Enhanced fallback with error logging
        print(f"Error displaying analysis results: {e}")
        try:
            fallback_text = (
                f"✅ <b>Анализ завершен!</b>\n\n"
                f"📊 Обработано: <code>{message_count}</code> сообщений\n\n"
            )
            
            if summary and not summary.startswith("❌"):
                # Truncate summary if too long
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
                fallback_text += f"📝 <b>Резюме:</b>\n<i>{summary_short}</i>\n\n"
            
            if events:
                fallback_text += f"📅 Найдено событий: <code>{len(events)}</code>\n"
                fallback_text += "Используйте /my_sessions для подробного просмотра"
            else:
                fallback_text += "📅 События не найдены"
            
            await message.edit_text(fallback_text)
        except Exception as fallback_error:
            print(f"Fallback display also failed: {fallback_error}")
            try:
                await message.edit_text("✅ Анализ завершен! Результаты сохранены.")
            except:
                pass


async def send_long_message(message: types.Message, text: str, events: list = None):
    """
    Send long messages with smart splitting to avoid Telegram limits
    """
    MAX_LENGTH = 4096
    
    if len(text) <= MAX_LENGTH:
        await message.edit_text(text, disable_web_page_preview=True)
        return
    
    # Split at logical points
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > MAX_LENGTH:
            if current_part:
                parts.append(current_part)
                current_part = line
            else:
                # Single line is too long, force split
                parts.append(line[:MAX_LENGTH])
                current_part = line[MAX_LENGTH:]
        else:
            current_part += ('\n' if current_part else '') + line
    
    if current_part:
        parts.append(current_part)
    
    # Send parts
    for i, part in enumerate(parts):
        try:
            if i == 0:
                await message.edit_text(part, disable_web_page_preview=True)
            else:
                await message.answer(part, disable_web_page_preview=True)
        except Exception as e:
            print(f"Error sending message part {i}: {e}")
            # Try without formatting
            try:
                clean_part = part.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('<code>', '').replace('</code>', '')
                if i == 0:
                    await message.edit_text(clean_part)
                else:
                    await message.answer(clean_part)
            except:
                pass 


async def send_long_message_with_calendar_sync(message: types.Message, text: str, events: list, session_id: int):
    """
    Send long messages with calendar sync buttons
    """
    from keyboards.inline import get_calendar_sync_keyboard
    
    MAX_LENGTH = 4000  # Leave room for keyboard
    
    if len(text) <= MAX_LENGTH:
        keyboard = get_calendar_sync_keyboard(session_id, len(events))
        await message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
        return
    
    # Split message but add keyboard to last part
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > MAX_LENGTH:
            if current_part:
                parts.append(current_part)
                current_part = line
            else:
                parts.append(line[:MAX_LENGTH])
                current_part = line[MAX_LENGTH:]
        else:
            current_part += ('\n' if current_part else '') + line
    
    if current_part:
        parts.append(current_part)
    
    # Send parts
    for i, part in enumerate(parts):
        try:
            if i == 0:
                await message.edit_text(part, disable_web_page_preview=True)
            elif i == len(parts) - 1:  # Last part gets the keyboard
                keyboard = get_calendar_sync_keyboard(session_id, len(events))
                await message.answer(part, reply_markup=keyboard, disable_web_page_preview=True)
            else:
                await message.answer(part, disable_web_page_preview=True)
        except Exception as e:
            print(f"Error sending message part {i}: {e}")


@router.callback_query(F.data.startswith("sync_calendar_"))
async def cq_sync_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Handle calendar sync request - show event confirmation"""
    session_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Get session events
    try:
        from services.database import get_session_events
        events = await get_session_events(session_id)
        
        if not events:
            await callback.message.edit_text(
                f"📅 <b>Нет событий для синхронизации</b>\n\n"
                f"В сессии #{session_id} не найдено событий для календаря."
            )
            return
        
        # Show event confirmation interface
        await show_event_confirmation(callback.message, session_id, events, user_id)
        
    except Exception as e:
        print(f"Error loading events for confirmation: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка загрузки событий</b>\n\n"
            f"Не удалось загрузить события из сессии #{session_id}."
        )


@router.callback_query(F.data.startswith("skip_calendar_"))
async def cq_skip_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Skip calendar sync"""
    await callback.message.edit_text(
        f"✅ <b>Анализ завершен!</b>\n\n"
        f"📊 События сохранены в базе данных.\n"
        f"📚 Используйте /my_sessions для просмотра истории.\n\n"
        f"💡 Подключите календарь для автоматической синхронизации: /connect_calendar"
    )


@router.message(Command("my_sessions"))
async def cmd_my_sessions(message: types.Message, state: FSMContext):
    """
    Show user's session history with pagination
    """
    user_id = message.from_user.id
    
    # Parse command arguments for page and filters
    command_parts = message.text.split()
    page = 1
    status_filter = None
    search_query = None
    
    # Simple command parsing: /my_sessions [page] [status] [search]
    if len(command_parts) > 1:
        try:
            page = int(command_parts[1])
        except ValueError:
            # First argument might be status or search
            if command_parts[1] in ['completed', 'active', 'failed']:
                status_filter = command_parts[1]
            else:
                search_query = ' '.join(command_parts[1:])
    
    if len(command_parts) > 2 and not search_query:
        if command_parts[2] in ['completed', 'active', 'failed']:
            status_filter = command_parts[2]
        else:
            search_query = ' '.join(command_parts[2:])
    
    if len(command_parts) > 3 and not search_query:
        search_query = ' '.join(command_parts[3:])
    
    await show_user_sessions(message, user_id, page, status_filter, search_query)


async def show_user_sessions(
    message: types.Message, 
    user_id: int, 
    page: int = 1, 
    status_filter: str = None,
    search_query: str = None
):
    """
    Display user sessions with pagination and filtering
    """
    from services.database import get_user_sessions_paginated, get_user_stats
    from keyboards.inline import get_sessions_pagination_keyboard
    
    try:
        # Get user stats first
        stats = await get_user_stats(user_id)
        
        # Get paginated sessions
        per_page = 5  # Show 5 sessions per page for better readability
        sessions, total_count = await get_user_sessions_paginated(
            user_id, page, per_page, status_filter, search_query
        )
        
        if total_count == 0:
            # No sessions found
            if status_filter or search_query:
                await message.answer(
                    "🔍 Не найдено сессий по вашему запросу.\n\n"
                    f"📊 Всего у вас сессий: {stats['total_sessions']}\n"
                    f"📅 Извлечено событий: {stats['total_events']}"
                )
            else:
                await message.answer(
                    "📭 У вас пока нет завершенных сессий.\n\n"
                    "💡 Используйте /capture_chat чтобы начать новую сессию захвата разговора."
                )
            return
        
        # Build header
        header = f"📚 <b>История сессий</b>\n\n"
        header += f"📊 Всего сессий: {stats['total_sessions']} | События: {stats['total_events']}\n"
        
        if status_filter:
            header += f"🔍 Фильтр: {status_filter}\n"
        if search_query:
            header += f"🔎 Поиск: {search_query}\n"
        
        header += f"📄 Страница {page} из {(total_count + per_page - 1) // per_page}\n\n"
        
        # Build sessions list
        sessions_text = ""
        for i, session in enumerate(sessions, 1):
            session_number = (page - 1) * per_page + i
            
            # Session status emoji
            status_emoji = {
                'completed': '✅',
                'active': '🔄',
                'failed': '❌'
            }.get(session.status, '❓')
            
            # Format dates
            start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
            end_date = session.end_time.strftime('%d.%m.%Y %H:%M') if session.end_time else "—"
            
            # Message count
            message_count = len(session.messages) if session.messages else 0
            
            # Events count
            events_count = len(session.extracted_events) if session.extracted_events else 0
            
            # Summary preview
            summary_preview = ""
            if session.summary:
                summary_preview = session.summary[:100] + "..." if len(session.summary) > 100 else session.summary
                summary_preview = f"\n💭 {summary_preview}"
            
            sessions_text += (
                f"{status_emoji} <b>Сессия #{session.id}</b>\n"
                f"📅 {start_date} — {end_date}\n"
                f"📝 Сообщений: {message_count} | 📅 События: {events_count}{summary_preview}\n\n"
            )
        
        # Combine text
        full_text = header + sessions_text
        
        # Add usage hint
        full_text += (
            "💡 <i>Для просмотра деталей используйте:</i>\n"
            "• /session_details [ID] — подробности сессии\n"
            "• /my_sessions [страница] — навигация\n"
            "• /my_sessions completed — только завершенные\n"
            "• /my_sessions 1 поиск — поиск по тексту"
        )
        
        # Get pagination keyboard
        keyboard = get_sessions_pagination_keyboard(
            page, 
            (total_count + per_page - 1) // per_page, 
            status_filter, 
            search_query
        )
        
        await message.answer(full_text, reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при получении истории сессий: {str(e)}\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


@router.message(Command("session_details"))
async def cmd_session_details(message: types.Message, state: FSMContext):
    """
    Show detailed information about a specific session
    """
    user_id = message.from_user.id
    command_parts = message.text.split()
    
    if len(command_parts) < 2:
        await message.answer(
            "❌ Укажите ID сессии.\n\n"
            "Пример: /session_details 123"
        )
        return
    
    try:
        session_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ ID сессии должен быть числом.")
        return
    
    await show_session_details(message, user_id, session_id)


async def show_session_details(message: types.Message, user_id: int, session_id: int):
    """
    Display detailed information about a specific session
    """
    from services.database import AsyncSessionLocal, get_session_events
    from sqlalchemy import select
    
    try:
        async with AsyncSessionLocal() as db_session:
            # Get session
            stmt = select(CaptureSession).where(
                CaptureSession.id == session_id,
                CaptureSession.user_id == user_id
            )
            result = await db_session.execute(stmt)
            session = result.scalar_one_or_none()
            
            if not session:
                await message.answer("❌ Сессия не найдена или не принадлежит вам.")
                return
            
            # Get events for this session
            events = await get_session_events(session_id)
            
            # Format session details
            status_emoji = {
                'completed': '✅',
                'active': '🔄',
                'failed': '❌'
            }.get(session.status, '❓')
            
            start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
            end_date = session.end_time.strftime('%d.%m.%Y %H:%M') if session.end_time else "—"
            
            message_count = len(session.messages) if session.messages else 0
            events_count = len(events)
            
            # Build header
            text = f"{status_emoji} <b>Сессия #{session.id}</b>\n\n"
            text += f"📅 Начата: {start_date}\n"
            text += f"🏁 Завершена: {end_date}\n"
            text += f"📝 Сообщений: {message_count}\n"
            text += f"📅 Извлечено событий: {events_count}\n\n"
            
            # Add summary
            if session.summary:
                text += f"📋 <b>Резюме:</b>\n{session.summary}\n\n"
            
            # Add events
            if events:
                text += "📅 <b>Извлеченные события:</b>\n"
                for event in events:
                    priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(event.priority, '⚪')
                    type_emoji = {
                        'meeting': '👥',
                        'deadline': '⏰', 
                        'task': '✅',
                        'appointment': '📅',
                        'reminder': '💭'
                    }.get(event.event_type, '📝')
                    
                    event_date = event.start_datetime.strftime('%d.%m %H:%M') if event.start_datetime else 'Без даты'
                    
                    text += f"{type_emoji} {priority_emoji} {event.title}\n"
                    text += f"   📅 {event_date}"
                    if event.location:
                        text += f" | 📍 {event.location}"
                    text += "\n"
                text += "\n"
            
            # Add sample messages if available
            if session.messages:
                text += "💬 <b>Примеры сообщений:</b>\n"
                sample_count = min(3, len(session.messages))
                for i in range(sample_count):
                    msg = session.messages[i]
                    msg_text = msg.get('text', '') if isinstance(msg, dict) else str(msg)
                    if len(msg_text) > 100:
                        msg_text = msg_text[:100] + "..."
                    text += f"• {msg_text}\n"
                
                if len(session.messages) > sample_count:
                    text += f"... и еще {len(session.messages) - sample_count} сообщений\n"
            
            # Add action buttons for the session
            from keyboards.inline import get_session_actions_keyboard
            keyboard = get_session_actions_keyboard(session_id)
            
            # Send with action buttons if text is short enough, otherwise split
            if len(text) < 4000:
                await message.answer(text, reply_markup=keyboard)
            else:
                await send_long_message(message, text)
                await message.answer(
                    f"🔧 <b>Действия для сессии #{session_id}:</b>",
                    reply_markup=keyboard
                )
            
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при получении деталей сессии: {str(e)}\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )


# Callback handlers for session pagination
@router.callback_query(F.data.startswith("sessions_page_"))
async def cq_sessions_page(callback: types.CallbackQuery, state: FSMContext):
    """Handle session pagination callbacks"""
    await callback.answer()
    
    data_parts = callback.data.split("_")
    page = int(data_parts[2])
    
    # Extract filters from callback data if present
    status_filter = data_parts[3] if len(data_parts) > 3 and data_parts[3] != "none" else None
    search_query = "_".join(data_parts[4:]) if len(data_parts) > 4 else None
    
    user_id = callback.from_user.id
    
    # Show sessions for the requested page
    await show_user_sessions(callback.message, user_id, page, status_filter, search_query)
    
    # Edit the original message instead of sending new one
    try:
        await callback.message.delete()
    except Exception:
        pass 


# Session export functionality
async def export_session_text(session_id: int, user_id: int, format_type: str = "txt") -> str:
    """Export session as formatted text"""
    from services.database import AsyncSessionLocal, get_session_events
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db_session:
        # Get session
        stmt = select(CaptureSession).where(
            CaptureSession.id == session_id,
            CaptureSession.user_id == user_id
        )
        result = await db_session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        # Get events
        events = await get_session_events(session_id)
        
        # Format based on type
        if format_type == "md":
            return format_session_markdown(session, events)
        elif format_type == "json":
            return format_session_json(session, events)
        elif format_type == "csv":
            return format_events_csv(events)
        else:  # txt
            return format_session_text(session, events)


def format_session_text(session, events) -> str:
    """Format session as plain text"""
    start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
    end_date = session.end_time.strftime('%d.%m.%Y %H:%M') if session.end_time else "—"
    
    text = f"СЕССИЯ ЗАХВАТА #{session.id}\n"
    text += f"{'=' * 50}\n\n"
    text += f"Период: {start_date} — {end_date}\n"
    text += f"Сообщений: {len(session.messages) if session.messages else 0}\n"
    text += f"Статус: {session.status}\n\n"
    
    if session.summary:
        text += f"РЕЗЮМЕ:\n{'-' * 20}\n{session.summary}\n\n"
    
    if events:
        text += f"СОБЫТИЯ ({len(events)}):\n{'-' * 20}\n"
        for i, event in enumerate(events, 1):
            text += f"{i}. {event.title}\n"
            text += f"   Тип: {event.event_type} | Приоритет: {event.priority}\n"
            if event.start_datetime:
                text += f"   Дата: {event.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
            if event.location:
                text += f"   Место: {event.location}\n"
            text += "\n"
    
    if session.messages:
        text += f"СООБЩЕНИЯ:\n{'-' * 20}\n"
        for i, msg in enumerate(session.messages, 1):
            msg_text = msg.get('text', '') if isinstance(msg, dict) else str(msg)
            timestamp = msg.get('timestamp', '') if isinstance(msg, dict) else ''
            text += f"{i}. [{timestamp}] {msg_text}\n"
    
    return text


def format_session_markdown(session, events) -> str:
    """Format session as Markdown"""
    start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
    end_date = session.end_time.strftime('%d.%m.%Y %H:%M') if session.end_time else "—"
    
    text = f"# Сессия захвата #{session.id}\n\n"
    text += f"**Период:** {start_date} — {end_date}  \n"
    text += f"**Сообщений:** {len(session.messages) if session.messages else 0}  \n"
    text += f"**Статус:** {session.status}\n\n"
    
    if session.summary:
        text += f"## Резюме\n\n{session.summary}\n\n"
    
    if events:
        text += f"## События ({len(events)})\n\n"
        for i, event in enumerate(events, 1):
            priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(event.priority, '⚪')
            type_emoji = {
                'meeting': '👥', 'deadline': '⏰', 'task': '✅',
                'appointment': '📅', 'reminder': '💭'
            }.get(event.event_type, '📝')
            
            text += f"{i}. {type_emoji} {priority_emoji} **{event.title}**\n"
            text += f"   - Тип: {event.event_type}\n"
            text += f"   - Приоритет: {event.priority}\n"
            if event.start_datetime:
                text += f"   - Дата: {event.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
            if event.location:
                text += f"   - Место: {event.location}\n"
            text += "\n"
    
    return text


def format_session_json(session, events) -> str:
    """Format session as JSON"""
    import json
    
    session_data = {
        "id": session.id,
        "start_time": session.start_time.isoformat(),
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "status": session.status,
        "summary": session.summary,
        "messages": session.messages,
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "priority": event.priority,
                "start_datetime": event.start_datetime.isoformat() if event.start_datetime else None,
                "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
                "location": event.location,
                "participants": event.participants,
                "action_items": event.action_items
            }
            for event in events
        ]
    }
    
    return json.dumps(session_data, ensure_ascii=False, indent=2)


def format_events_csv(events) -> str:
    """Format events as CSV"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Название', 'Тип', 'Приоритет', 'Дата начала', 'Дата окончания', 'Место', 'Участники'])
    
    # Data
    for event in events:
        participants = ', '.join(event.participants) if event.participants else ''
        writer.writerow([
            event.id,
            event.title,
            event.event_type,
            event.priority,
            event.start_datetime.strftime('%d.%m.%Y %H:%M') if event.start_datetime else '',
            event.end_datetime.strftime('%d.%m.%Y %H:%M') if event.end_datetime else '',
            event.location or '',
            participants
        ])
    
    return output.getvalue()


# Session action callback handlers
@router.callback_query(F.data.startswith("export_session_"))
async def cq_export_session(callback: types.CallbackQuery, state: FSMContext):
    """Handle session export requests"""
    await callback.answer()
    
    data_parts = callback.data.split("_")
    session_id = int(data_parts[2])
    export_type = data_parts[3]  # text or json
    
    user_id = callback.from_user.id
    
    try:
        if export_type == "text":
            # Show format selection
            from keyboards.inline import get_export_format_keyboard
            await callback.message.edit_text(
                f"📄 Выберите формат экспорта для сессии #{session_id}:",
                reply_markup=get_export_format_keyboard(session_id)
            )
        elif export_type == "json":
            # Direct JSON export
            content = await export_session_text(session_id, user_id, "json")
            if content:
                await send_export_file(callback.message, content, f"session_{session_id}.json", "application/json")
            else:
                await callback.message.edit_text("❌ Сессия не найдена.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка экспорта: {str(e)}")


@router.callback_query(F.data.startswith("export_format_"))
async def cq_export_format(callback: types.CallbackQuery, state: FSMContext):
    """Handle format selection for export"""
    await callback.answer()
    
    data_parts = callback.data.split("_")
    session_id = int(data_parts[2])
    format_type = data_parts[3]
    
    user_id = callback.from_user.id
    
    try:
        content = await export_session_text(session_id, user_id, format_type)
        if content:
            # Determine file extension and MIME type
            extensions = {'txt': '.txt', 'md': '.md', 'json': '.json', 'csv': '.csv'}
            mime_types = {
                'txt': 'text/plain',
                'md': 'text/markdown', 
                'json': 'application/json',
                'csv': 'text/csv'
            }
            
            filename = f"session_{session_id}{extensions.get(format_type, '.txt')}"
            mime_type = mime_types.get(format_type, 'text/plain')
            
            await send_export_file(callback.message, content, filename, mime_type)
        else:
            await callback.message.edit_text("❌ Сессия не найдена.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка экспорта: {str(e)}")


@router.callback_query(F.data.startswith("share_session_"))
async def cq_share_session(callback: types.CallbackQuery, state: FSMContext):
    """Handle session sharing requests"""
    await callback.answer()
    
    data_parts = callback.data.split("_")
    session_id = int(data_parts[2])
    share_type = data_parts[3]  # summary or events
    
    user_id = callback.from_user.id
    
    try:
        if share_type == "summary":
            content = await get_session_summary_share(session_id, user_id)
        else:  # events
            content = await get_session_events_share(session_id, user_id)
        
        if content:
            await callback.message.edit_text(
                f"📤 <b>Поделиться сессией #{session_id}</b>\n\n"
                f"{content}\n\n"
                "💡 <i>Скопируйте текст выше для отправки</i>",
                reply_markup=None
            )
        else:
            await callback.message.edit_text("❌ Сессия не найдена.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при подготовке: {str(e)}")


async def get_session_summary_share(session_id: int, user_id: int) -> str:
    """Get formatted summary for sharing"""
    from services.database import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db_session:
        stmt = select(CaptureSession).where(
            CaptureSession.id == session_id,
            CaptureSession.user_id == user_id
        )
        result = await db_session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
        text = f"📋 <b>Резюме сессии от {start_date}</b>\n\n"
        
        if session.summary:
            text += session.summary
        else:
            text += "Резюме не было создано для этой сессии."
        
        return text


async def get_session_events_share(session_id: int, user_id: int) -> str:
    """Get formatted events for sharing"""
    from services.database import get_session_events, AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db_session:
        stmt = select(CaptureSession).where(
            CaptureSession.id == session_id,
            CaptureSession.user_id == user_id
        )
        result = await db_session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        events = await get_session_events(session_id)
        start_date = session.start_time.strftime('%d.%m.%Y %H:%M')
        
        text = f"📅 <b>События из сессии от {start_date}</b>\n\n"
        
        if events:
            for i, event in enumerate(events, 1):
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(event.priority, '⚪')
                type_emoji = {
                    'meeting': '👥', 'deadline': '⏰', 'task': '✅',
                    'appointment': '📅', 'reminder': '💭'
                }.get(event.event_type, '📝')
                
                text += f"{i}. {type_emoji} {priority_emoji} <b>{event.title}</b>\n"
                if event.start_datetime:
                    text += f"   📅 {event.start_datetime.strftime('%d.%m %H:%M')}"
                if event.location:
                    text += f" | 📍 {event.location}"
                text += "\n"
        else:
            text += "События не были найдены в этой сессии."
        
        return text


async def send_export_file(message: types.Message, content: str, filename: str, mime_type: str):
    """Send content as a file"""
    from aiogram.types import BufferedInputFile
    
    # Create file from string content
    file_data = content.encode('utf-8')
    file = BufferedInputFile(file_data, filename)
    
    await message.answer_document(
        document=file,
        caption=f"📄 Экспорт сессии: {filename}"
    )


@router.callback_query(F.data.startswith("delete_session_"))
async def cq_delete_session(callback: types.CallbackQuery, state: FSMContext):
    """Handle session deletion request"""
    await callback.answer()
    
    session_id = int(callback.data.split("_")[2])
    
    from keyboards.inline import get_delete_confirm_keyboard
    await callback.message.edit_text(
        f"🗑️ <b>Удаление сессии #{session_id}</b>\n\n"
        "⚠️ Это действие нельзя отменить. Все данные сессии будут удалены навсегда.\n\n"
        "Вы уверены?",
        reply_markup=get_delete_confirm_keyboard(session_id)
    )


@router.callback_query(F.data.startswith("confirm_delete_"))
async def cq_confirm_delete(callback: types.CallbackQuery, state: FSMContext):
    """Confirm session deletion"""
    await callback.answer()
    
    session_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    try:
        success = await delete_user_session(session_id, user_id)
        if success:
            await callback.message.edit_text(
                f"✅ Сессия #{session_id} была успешно удалена.",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                "❌ Сессия не найдена или не принадлежит вам.",
                reply_markup=None
            )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при удалении: {str(e)}",
            reply_markup=None
        )


@router.callback_query(F.data.startswith("cancel_delete_"))
async def cq_cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    """Cancel session deletion"""
    await callback.answer()
    
    session_id = int(callback.data.split("_")[2])
    await show_session_details(callback.message, callback.from_user.id, session_id)


async def delete_user_session(session_id: int, user_id: int) -> bool:
    """Delete a user's session and related events"""
    from services.database import AsyncSessionLocal
    from sqlalchemy import select, delete
    
    async with AsyncSessionLocal() as db_session:
        # First check if session belongs to user
        stmt = select(CaptureSession).where(
            CaptureSession.id == session_id,
            CaptureSession.user_id == user_id
        )
        result = await db_session.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return False
        
        # Delete related events first
        events_delete_stmt = delete(Event).where(Event.session_id == session_id)
        await db_session.execute(events_delete_stmt)
        
        # Delete session
        session_delete_stmt = delete(CaptureSession).where(CaptureSession.id == session_id)
        await db_session.execute(session_delete_stmt)
        
        await db_session.commit()
        return True


@router.callback_query(F.data == "back_to_sessions")
async def cq_back_to_sessions(callback: types.CallbackQuery, state: FSMContext):
    """Return to sessions list"""
    await callback.answer()
    
    user_id = callback.from_user.id
    await show_user_sessions(callback.message, user_id, 1)


async def show_event_confirmation(message: types.Message, session_id: int, events: list, user_id: int):
    """
    Display events for user confirmation before creating calendar events
    """
    try:
        # Build confirmation message
        text = f"📅 <b>Подтверждение событий</b>\n\n"
        text += f"🔍 Найдено <code>{len(events)}</code> событий в сессии #{session_id}.\n"
        text += f"Выберите которые создать в календаре:\n\n"
        
        # Store event selection state in FSM
        from aiogram.fsm.context import FSMContext
        from states.capture_states import CaptureStates
        
        # Initialize event selection state
        event_selection = {}
        for i, event in enumerate(events):
            event_selection[f"event_{i}"] = True  # All selected by default
        
        # Display events with selection status
        for i, event in enumerate(events):
            selected = "✅" if event_selection.get(f"event_{i}", True) else "☑️"
            
            # Priority and type indicators
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.priority, "🟡")
            type_emoji = {
                "meeting": "🤝", "deadline": "⏰", "task": "📋", 
                "appointment": "📅", "reminder": "🔔"
            }.get(event.event_type, "📌")
            
            text += f"{selected} {i+1}. {priority_emoji}{type_emoji} <b>{event.title}</b>\n"
            
            # Show key details
            if event.start_datetime:
                dt_str = event.start_datetime.strftime("%d.%m.%Y %H:%M")
                text += f"   🕐 {dt_str}\n"
            
            if event.location:
                text += f"   📍 {event.location}\n"
            
            if event.participants and len(event.participants) > 0:
                participants_str = ", ".join(event.participants[:2])
                if len(event.participants) > 2:
                    participants_str += f" и еще {len(event.participants)-2}"
                text += f"   👥 {participants_str}\n"
            
            # Action items preview
            if event.action_items and len(event.action_items) > 0:
                if len(event.action_items) == 1:
                    text += f"   ✅ {event.action_items[0][:50]}{'...' if len(event.action_items[0]) > 50 else ''}\n"
                else:
                    text += f"   ✅ {len(event.action_items)} задач\n"
            
            text += "\n"
        
        # Add usage instructions
        text += f"💡 <b>Управление:</b>\n"
        text += f"• Нажмите на номер события чтобы включить/исключить\n"
        text += f"• Используйте кнопки для массовых операций\n"
        
        # Send with confirmation keyboard
        from keyboards.inline import get_event_confirmation_keyboard
        keyboard = get_event_confirmation_keyboard(session_id, len(events), event_selection)
        
        await message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
        
    except Exception as e:
        print(f"Error showing event confirmation: {e}")
        await message.edit_text(
            f"❌ <b>Ошибка отображения событий</b>\n\n"
            f"Не удалось показать события для подтверждения."
        )


@router.callback_query(F.data.startswith("toggle_event_"))
async def cq_toggle_event(callback: types.CallbackQuery, state: FSMContext):
    """Toggle individual event selection"""
    try:
        # Parse callback data: toggle_event_{session_id}_{event_index}
        parts = callback.data.split("_")
        session_id = int(parts[2])
        event_index = int(parts[3])
        
        # Get current selection state from FSM data
        data = await state.get_data()
        event_selection = data.get('event_selection', {})
        
        # Initialize if not exists
        if not event_selection:
            # Get events count
            from services.database import get_session_events
            events = await get_session_events(session_id)
            event_selection = {f"event_{i}": True for i in range(len(events))}
        
        # Toggle selection
        key = f"event_{event_index}"
        event_selection[key] = not event_selection.get(key, True)
        
        # Save updated selection
        await state.update_data(event_selection=event_selection)
        
        # Update keyboard to reflect change
        selected_count = sum(1 for selected in event_selection.values() if selected)
        total_count = len(event_selection)
        
        from keyboards.inline import get_event_confirmation_keyboard
        keyboard = get_event_confirmation_keyboard(session_id, total_count, event_selection)
        
        # Update status text
        text = callback.message.text
        lines = text.split('\n')
        
        # Find and update the specific event line
        for i, line in enumerate(lines):
            if line.startswith(("✅", "☑️")) and f"{event_index+1}." in line:
                # Toggle the checkbox
                if line.startswith("✅"):
                    lines[i] = line.replace("✅", "☑️", 1)
                else:
                    lines[i] = line.replace("☑️", "✅", 1)
                break
        
        # Update selection summary
        for i, line in enumerate(lines):
            if "Выберите которые создать" in line:
                lines[i] = f"Выберите которые создать в календаре: <code>{selected_count}/{total_count}</code>"
                break
        
        updated_text = '\n'.join(lines)
        
        await callback.message.edit_text(updated_text, reply_markup=keyboard, disable_web_page_preview=True)
        await callback.answer(f"Событие {'выбрано' if event_selection[key] else 'исключено'}")
        
    except Exception as e:
        print(f"Error toggling event selection: {e}")
        await callback.answer("❌ Ошибка изменения выбора")


@router.callback_query(F.data.startswith("select_all_events_"))
async def cq_select_all_events(callback: types.CallbackQuery, state: FSMContext):
    """Select all events"""
    try:
        session_id = int(callback.data.split("_")[3])
        
        # Get events count
        from services.database import get_session_events
        events = await get_session_events(session_id)
        
        # Select all
        event_selection = {f"event_{i}": True for i in range(len(events))}
        await state.update_data(event_selection=event_selection)
        
        # Refresh display
        await refresh_event_confirmation_display(callback.message, session_id, events, callback.from_user.id, event_selection)
        await callback.answer("✅ Все события выбраны")
        
    except Exception as e:
        print(f"Error selecting all events: {e}")
        await callback.answer("❌ Ошибка выбора")


@router.callback_query(F.data.startswith("deselect_all_events_"))
async def cq_deselect_all_events(callback: types.CallbackQuery, state: FSMContext):
    """Deselect all events"""
    try:
        session_id = int(callback.data.split("_")[3])
        
        # Get events count
        from services.database import get_session_events
        events = await get_session_events(session_id)
        
        # Deselect all
        event_selection = {f"event_{i}": False for i in range(len(events))}
        await state.update_data(event_selection=event_selection)
        
        # Refresh display
        await refresh_event_confirmation_display(callback.message, session_id, events, callback.from_user.id, event_selection)
        await callback.answer("☑️ Все события исключены")
        
    except Exception as e:
        print(f"Error deselecting all events: {e}")
        await callback.answer("❌ Ошибка исключения")


@router.callback_query(F.data.startswith("confirm_create_events_"))
async def cq_confirm_create_events(callback: types.CallbackQuery, state: FSMContext):
    """Create selected events in calendar"""
    try:
        session_id = int(callback.data.split("_")[3])
        user_id = callback.from_user.id
        
        # Get selection state
        data = await state.get_data()
        event_selection = data.get('event_selection', {})
        
        # Get all events
        from services.database import get_session_events
        events = await get_session_events(session_id)
        
        # Filter selected events
        selected_events = []
        for i, event in enumerate(events):
            if event_selection.get(f"event_{i}", True):  # Default to selected
                selected_events.append(event)
        
        if not selected_events:
            await callback.message.edit_text(
                f"📅 <b>Нет выбранных событий</b>\n\n"
                f"Выберите хотя бы одно событие для создания в календаре."
            )
            return
        
        # Show progress
        await callback.message.edit_text(
            f"📅 <b>Создание событий...</b>\n\n"
            f"🔄 Создаём {len(selected_events)} событий в календаре"
        )
        
        # Create events one by one
        created_events = []
        failed_events = []
        
        for event in selected_events:
            try:
                # Convert Event model to dict for API
                event_data = {
                    'title': event.title,
                    'event_type': event.event_type,
                    'priority': event.priority,
                    'start_datetime': event.start_datetime.isoformat() if event.start_datetime else None,
                    'end_datetime': event.end_datetime.isoformat() if event.end_datetime else None,
                    'location': event.location,
                    'participants': event.participants or [],
                    'action_items': event.action_items or [],
                    'session_id': session_id
                }
                
                # Create calendar event
                calendar_event_id = await google_calendar.create_calendar_event(user_id, event_data)
                
                if calendar_event_id:
                    # Update database with calendar event ID
                    from services.database import AsyncSessionLocal, Event
                    async with AsyncSessionLocal() as db_session:
                        db_event = await db_session.get(Event, event.id)
                        if db_event:
                            db_event.calendar_event_id = calendar_event_id
                            await db_session.commit()
                    
                    created_events.append({
                        'event_id': event.id,
                        'title': event.title,
                        'calendar_event_id': calendar_event_id
                    })
                else:
                    failed_events.append({
                        'event_id': event.id,
                        'title': event.title,
                        'error': 'Failed to create calendar event'
                    })
            
            except Exception as event_error:
                print(f"Error creating calendar event for {event.title}: {event_error}")
                failed_events.append({
                    'event_id': event.id,
                    'title': event.title,
                    'error': str(event_error)
                })
        
        # Show results
        await show_creation_results(callback.message, created_events, failed_events)
        
        # Clear selection state
        await state.update_data(event_selection={})
        
    except Exception as e:
        print(f"Error creating selected events: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка создания событий</b>\n\n"
            f"Произошла ошибка при создании событий в календаре."
        )


async def refresh_event_confirmation_display(message: types.Message, session_id: int, events: list, user_id: int, event_selection: dict):
    """Refresh the event confirmation display with updated selection"""
    try:
        # Rebuild the display
        text = f"📅 <b>Подтверждение событий</b>\n\n"
        selected_count = sum(1 for selected in event_selection.values() if selected)
        text += f"🔍 Найдено <code>{len(events)}</code> событий в сессии #{session_id}.\n"
        text += f"Выберите которые создать в календаре: <code>{selected_count}/{len(events)}</code>\n\n"
        
        # Display events with current selection
        for i, event in enumerate(events):
            selected = "✅" if event_selection.get(f"event_{i}", True) else "☑️"
            
            # Priority and type indicators
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.priority, "🟡")
            type_emoji = {
                "meeting": "🤝", "deadline": "⏰", "task": "📋", 
                "appointment": "📅", "reminder": "🔔"
            }.get(event.event_type, "📌")
            
            text += f"{selected} {i+1}. {priority_emoji}{type_emoji} <b>{event.title}</b>\n"
            
            # Show key details
            if event.start_datetime:
                dt_str = event.start_datetime.strftime("%d.%m.%Y %H:%M")
                text += f"   🕐 {dt_str}\n"
            
            if event.location:
                text += f"   📍 {event.location}\n"
            
            if event.participants and len(event.participants) > 0:
                participants_str = ", ".join(event.participants[:2])
                if len(event.participants) > 2:
                    participants_str += f" и еще {len(event.participants)-2}"
                text += f"   👥 {participants_str}\n"
            
            if event.action_items and len(event.action_items) > 0:
                if len(event.action_items) == 1:
                    text += f"   ✅ {event.action_items[0][:50]}{'...' if len(event.action_items[0]) > 50 else ''}\n"
                else:
                    text += f"   ✅ {len(event.action_items)} задач\n"
            
            text += "\n"
        
        # Add usage instructions
        text += f"💡 <b>Управление:</b>\n"
        text += f"• Нажмите на номер события чтобы включить/исключить\n"
        text += f"• Используйте кнопки для массовых операций\n"
        
        # Update with new keyboard
        from keyboards.inline import get_event_confirmation_keyboard
        keyboard = get_event_confirmation_keyboard(session_id, len(events), event_selection)
        
        await message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
        
    except Exception as e:
        print(f"Error refreshing confirmation display: {e}")


async def show_creation_results(message: types.Message, created_events: list, failed_events: list):
    """Show results of calendar event creation"""
    try:
        result_text = f"📅 <b>Результаты создания событий</b>\n\n"
        
        if created_events:
            result_text += f"✅ <b>Успешно создано: {len(created_events)}</b>\n"
            for event in created_events:
                result_text += f"  📌 {event['title']}\n"
            result_text += "\n"
        
        if failed_events:
            result_text += f"❌ <b>Не удалось создать: {len(failed_events)}</b>\n"
            for event in failed_events:
                error_msg = event.get('error', 'Неизвестная ошибка')
                if len(error_msg) > 100:
                    error_msg = error_msg[:100] + "..."
                result_text += f"  ❌ {event['title']}: {error_msg}\n"
            result_text += "\n"
        
        # Summary
        total_attempted = len(created_events) + len(failed_events)
        success_rate = (len(created_events) / total_attempted * 100) if total_attempted > 0 else 0
        
        result_text += f"📊 <b>Итого:</b> {success_rate:.0f}% успешно ({len(created_events)}/{total_attempted})\n\n"
        
        if created_events:
            result_text += f"💡 Откройте Google Calendar чтобы просмотреть созданные события.\n"
        
        if failed_events:
            result_text += f"💡 Проверьте подключение календаря: /connect_calendar\n"
        
        result_text += f"📚 История сессий: /my_sessions"
        
        await message.edit_text(result_text, disable_web_page_preview=True)
        
    except Exception as e:
        print(f"Error showing creation results: {e}")
        await message.edit_text(
            f"✅ <b>События созданы!</b>\n\n"
            f"📊 Успешно: {len(created_events)}, ошибок: {len(failed_events)}\n"
            f"📚 Подробности в /my_sessions"
        ) 