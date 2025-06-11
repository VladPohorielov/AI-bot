"""
Enhanced Capture Handlers - Stable version with improved UX
Working replacement for the original capture flow
"""
import logging
from typing import Dict, List, Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from states.user_states import CaptureStates, EventEditStates
from services.enhanced_capture_flow import EnhancedCaptureFlow
from services.session_manager import SessionManager
from services.database import get_active_session

logger = logging.getLogger(__name__)
router = Router()
enhanced_flow = EnhancedCaptureFlow()


# ==============================================
# MAIN CAPTURE COMMAND
# ==============================================

@router.message(Command("capture_chat"))
async def cmd_start_enhanced_capture(message: types.Message, state: FSMContext):
    """Enhanced version of capture_chat with better UX"""
    user_id = message.from_user.id
    logger.info(f"Enhanced capture_chat called by user {user_id}")
    
    try:
        # Clear any existing state
        await state.clear()
        
        # Check for existing sessions
        existing_session = await get_active_session(user_id)
        if existing_session:
            # User has active session
            message_count = len(existing_session.messages) if existing_session.messages else 0
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 Продовжити", callback_data="continue_capture"),
                    InlineKeyboardButton(text="🆕 Нова сесія", callback_data="restart_capture")
                ],
                [
                    InlineKeyboardButton(text="📊 Аналіз поточної", callback_data=f"analyze_current"),
                ],
                [
                    InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_capture")
                ]
            ])
            
            await message.answer(
                "🔄 **У вас є активна сесія захоплення**\n\n"
                f"📊 ID сесії: {existing_session.id}\n"
                f"⏰ Почато: {existing_session.start_time.strftime('%H:%M')}\n"
                f"📝 Зібрано повідомлень: {message_count}\n\n"
                "Що хочете зробити?",
                reply_markup=keyboard
            )
            await state.set_state(CaptureStates.CAPTURING)
            await state.update_data(session_id=existing_session.id)
            return
        
        # Start new session
        session = await SessionManager.start_capture_session(user_id, state)
        
        if not session:
            await message.answer(
                "❌ **Помилка створення сесії**\n\n"
                "Не вдалося створити нову сесію захоплення.\n"
                "🔄 Спробуйте ще раз через кілька секунд."
            )
            return
        
        # Success - show instructions
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Завершити захоплення", callback_data="finish_capture")
            ],
            [
                InlineKeyboardButton(text="📊 Показати прогрес", callback_data="show_progress"),
                InlineKeyboardButton(text="🔄 Статус сесії", callback_data="session_status")
            ],
            [
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_capture")
            ]
        ])
        
        await message.answer(
            "✅ **СЕСІЯ ЗАХОПЛЕННЯ РОЗПОЧАТА**\n\n"
            "🎯 **Як це працює:**\n"
            "• Надішліть текстові повідомлення або файли\n"
            "• Переслідіть повідомлення з інших чатів\n" 
            "• Надішліть голосові повідомлення (будуть розпізнані)\n"
            "• Коли закінчите, натисніть \"Завершити захоплення\"\n\n"
            "📝 **Я збираю:**\n"
            "• Дати та часи подій\n"
            "• Місця зустрічей та адреси\n"
            "• Контакти та телефони\n"
            "• Важливі домовленості\n"
            "• Дедлайни та нагадування\n\n"
            "⚡️ Почніть надсилати повідомлення...",
            reply_markup=keyboard
        )
        
        await state.set_state(CaptureStates.CAPTURING)
        await state.update_data(session_id=session.id, message_count=0)
        
        logger.info(f"Enhanced capture session {session.id} started for user {user_id}")
        
    except Exception as e:
        logger.error(f"Enhanced capture failed for user {user_id}: {e}")
        await state.clear()
        
        await message.answer(
            "❌ **Критична помилка**\n\n"
            f"Не вдалося запустити захоплення: {str(e)}\n\n"
            "🔧 Спробуйте ще раз або зверніться до адміністратора"
        )


# ==============================================
# MESSAGE CAPTURE HANDLERS  
# ==============================================

@router.message(CaptureStates.CAPTURING, F.content_type.in_(['text', 'voice', 'audio', 'document']))
async def handle_enhanced_captured_message(message: types.Message, state: FSMContext):
    """Handle captured messages with enhanced processing"""
    user_id = message.from_user.id
    
    try:
        # Get session data
        state_data = await state.get_data()
        session_id = state_data.get('session_id')
        message_count = state_data.get('message_count', 0)
        
        if not session_id:
            logger.warning(f"No session_id found for user {user_id}")
            await message.answer("❌ Сесію не знайдено. Використайте /capture_chat для початку.")
            await state.clear()
            return
        
        # Process different message types
        message_text = ""
        
        if message.content_type == 'text':
            message_text = message.text or ""
            
        elif message.content_type in ['voice', 'audio']:
            # Handle voice messages
            await message.answer("🎤 Розпізнаю голосове повідомлення...")
            try:
                from services.transcription import transcribe_audio
                message_text = await transcribe_audio(message) or ""
                if message_text:
                    await message.answer(f"✅ Розпізнано: \"{message_text[:100]}...\"")
                else:
                    await message.answer("❌ Не вдалося розпізнати голос")
                    return
            except Exception as e:
                logger.error(f"Voice transcription failed: {e}")
                await message.answer("❌ Помилка розпізнавання голосу")
                return
                
        elif message.content_type == 'document':
            # Handle document uploads
            await message.answer("📄 Обробляю документ...")
            try:
                doc_name = message.document.file_name if message.document else "Невідомий документ"
                message_text = f"Документ: {doc_name}"
                await message.answer(f"✅ Додано документ: {doc_name}")
            except Exception as e:
                logger.error(f"Document processing failed: {e}")
                await message.answer("❌ Не вдалося обробити документ")
                return
        
        # Add to session if we have valid text
        if message_text.strip():
            success = await SessionManager.add_message_to_session(user_id, message_text, state)
            
            if success:
                # Update message count
                message_count += 1
                await state.update_data(message_count=message_count)
                
                # Show progress every 5 messages
                if message_count % 5 == 0:
                    await message.answer(
                        f"📊 **Прогрес захоплення**\n\n"
                        f"✅ Зібрано повідомлень: {message_count}\n"
                        f"🔄 Продовжуйте надсилати або натисніть \"Завершити\""
                    )
            else:
                await message.answer("⚠️ Не вдалося додати повідомлення до сесії")
        else:
            await message.answer("⚠️ Порожнє повідомлення не додано")
            
    except Exception as e:
        logger.error(f"Error handling enhanced captured message: {e}")
        await message.answer("❌ Помилка обробки повідомлення")


# ==============================================
# CAPTURE CONTROL HANDLERS
# ==============================================

@router.callback_query(F.data == "finish_capture", CaptureStates.CAPTURING)
async def cq_finish_enhanced_capture(callback: types.CallbackQuery, state: FSMContext):
    """Finish capture and start enhanced analysis"""
    user_id = callback.from_user.id
    
    try:
        # End capture session
        session = await SessionManager.end_capture_session(user_id, state)
        
        if not session:
            await callback.message.edit_text("❌ Не вдалося завершити сесію захоплення")
            return
        
        # Get conversation text for analysis
        conversation_text = session.get_full_text()
        
        if not conversation_text.strip():
            await callback.message.edit_text(
                "⚠️ **Немає даних для аналізу**\n\n"
                "Сесія порожня або містить тільки пробільні символи.\n"
                "Почніть нову сесію захоплення з /capture_chat"
            )
            await state.clear()
            return
        
        # Start enhanced analysis
        results = await enhanced_flow.start_analysis(conversation_text, callback, state)
        
        if results.get('success', False):
            await enhanced_flow.show_results_for_review(callback, state, results)
        else:
            error_msg = results.get('error', 'Невідома помилка аналізу')
            await callback.message.edit_text(f"❌ {error_msg}")
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error finishing enhanced capture: {e}")
        await callback.message.edit_text("❌ Помилка завершення захоплення")
        await state.clear()


@router.callback_query(F.data == "cancel_capture", CaptureStates.CAPTURING)
async def cq_cancel_enhanced_capture(callback: types.CallbackQuery, state: FSMContext):
    """Cancel capture session"""
    user_id = callback.from_user.id
    
    try:
        await SessionManager.cancel_session(user_id, state)
        await callback.message.edit_text(
            "❌ **Сесію захоплення скасовано**\n\n"
            "Всі дані видалено. Можете почати нову сесію з /capture_chat"
        )
        
    except Exception as e:
        logger.error(f"Error canceling enhanced capture: {e}")
        await callback.message.edit_text("❌ Помилка скасування")


@router.callback_query(F.data == "continue_capture", CaptureStates.CAPTURING)
async def cq_continue_enhanced_capture(callback: types.CallbackQuery, state: FSMContext):
    """Continue existing capture session"""
    await callback.message.edit_text(
        "🔄 **Продовжуємо захоплення**\n\n"
        "Надсилайте повідомлення для додавання до поточної сесії.\n"
        "Натисніть \"Завершити захоплення\" коли закінчите."
    )


@router.callback_query(F.data == "restart_capture")
async def cq_restart_enhanced_capture(callback: types.CallbackQuery, state: FSMContext):
    """Restart capture with new session"""
    user_id = callback.from_user.id
    
    try:
        # Cancel existing session
        await SessionManager.cancel_session(user_id, state)
        
        # Start new session
        session = await SessionManager.start_capture_session(user_id, state)
        
        if session:
            await callback.message.edit_text(
                "🆕 **Нова сесія захоплення розпочата**\n\n"
                "Стара сесія скасована. Почніть надсилати повідомлення для нової сесії."
            )
            await state.update_data(session_id=session.id, message_count=0)
        else:
            await callback.message.edit_text("❌ Не вдалося створити нову сесію")
            
    except Exception as e:
        logger.error(f"Error restarting enhanced capture: {e}")
        await callback.message.edit_text("❌ Помилка перезапуску")


@router.callback_query(F.data == "show_progress", CaptureStates.CAPTURING)
async def cq_show_enhanced_progress(callback: types.CallbackQuery, state: FSMContext):
    """Show current capture progress"""
    try:
        state_data = await state.get_data()
        message_count = state_data.get('message_count', 0)
        session_id = state_data.get('session_id', 'N/A')
        
        await callback.answer(
            f"📊 Сесія #{session_id}\n"
            f"📝 Повідомлень: {message_count}\n"
            f"🔄 Статус: Активна",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error showing progress: {e}")
        await callback.answer("❌ Помилка отримання прогресу")


# ==============================================
# ANALYSIS RESULTS HANDLERS
# ==============================================

@router.callback_query(F.data == "confirm_all_events", CaptureStates.REVIEWING_RESULTS)
async def cq_confirm_all_enhanced_events(callback: types.CallbackQuery, state: FSMContext):
    """Confirm and save all events to calendar"""
    try:
        await enhanced_flow.save_events_to_calendar(callback, state)
    except Exception as e:
        logger.error(f"Error confirming events: {e}")
        await callback.message.edit_text("❌ Помилка збереження подій")


@router.callback_query(F.data == "edit_events_menu", CaptureStates.REVIEWING_RESULTS)
async def cq_edit_enhanced_events_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show events editing menu"""
    try:
        state_data = await state.get_data()
        session_data = state_data.get('session_data', {})
        events = session_data.get('events', [])
        
        if not events:
            await callback.answer("Немає подій для редагування")
            return
        
        # Create keyboard for event editing
        keyboard_rows = []
        
        for i, event in enumerate(events[:5]):  # Max 5 events
            event_title = event.get('title', 'Без назви')
            button_text = f"✏️ {event_title[:20]}..." if len(event_title) > 20 else f"✏️ {event_title}"
            keyboard_rows.append([
                InlineKeyboardButton(text=button_text, callback_data=f"edit_event:{event.get('id', i)}")
            ])
        
        keyboard_rows.extend([
            [
                InlineKeyboardButton(text="✅ Зберегти всі", callback_data="confirm_all_events"),
                InlineKeyboardButton(text="🔄 Повторити аналіз", callback_data="retry_analysis")
            ],
            [
                InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_capture")
            ]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        await callback.message.edit_text(
            "✏️ **РЕДАГУВАННЯ ПОДІЙ**\n\n"
            "Оберіть подію для редагування або підтвердіть збереження всіх подій:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error showing edit menu: {e}")
        await callback.answer("❌ Помилка відображення меню")


@router.callback_query(F.data.startswith("edit_event:"))
async def cq_edit_enhanced_specific_event(callback: types.CallbackQuery, state: FSMContext):
    """Edit specific event"""
    try:
        event_id = callback.data.split(":")[1]
        await enhanced_flow.handle_event_editing(callback, state, event_id)
    except Exception as e:
        logger.error(f"Error editing event: {e}")
        await callback.answer("❌ Помилка редагування події")


@router.callback_query(F.data == "retry_analysis", CaptureStates.REVIEWING_RESULTS)
async def cq_retry_enhanced_analysis(callback: types.CallbackQuery, state: FSMContext):
    """Retry analysis with improved prompts"""
    try:
        state_data = await state.get_data()
        session_data = state_data.get('session_data', {})
        conversation_text = session_data.get('conversation_text', '')
        
        if not conversation_text:
            await callback.answer("Немає тексту для повторного аналізу")
            return
        
        # Restart analysis
        results = await enhanced_flow.start_analysis(conversation_text, callback, state)
        
        if results.get('success', False):
            await enhanced_flow.show_results_for_review(callback, state, results)
        else:
            error_msg = results.get('error', 'Невідома помилка аналізу')
            await callback.message.edit_text(f"❌ {error_msg}")
            
    except Exception as e:
        logger.error(f"Error retrying analysis: {e}")
        await callback.answer("❌ Помилка повторного аналізу") 