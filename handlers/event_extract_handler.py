"""
Simple Event Extract Handler for "Витягати події" button
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "extract_events")
async def cq_extract_events_simple(callback: types.CallbackQuery, state: FSMContext):
    """
    Simple event extraction from text analysis
    """
    if not callback.from_user:
        return
    
    user_id = callback.from_user.id
    logger.info(f"🔍 Extract events button pressed by user {user_id}")
    
    try:
        # Get last analyzed text from FSM data
        data = await state.get_data()
        last_text = data.get('last_analyzed_text', '')
        
        if not last_text:
            await callback.answer(
                "❌ Немає тексту для аналізу. Надішліть спочатку текстове повідомлення.",
                show_alert=True
            )
            return
        
        # Show progress message
        if callback.message:
            await callback.message.edit_text(
                "🔍 **АНАЛІЗУЮ ПОДІЇ**\n\n"
                "⏳ Шукаю події у тексті...\n"
                "📊 Аналізую дати та час...\n"
                "👥 Визначаю учасників...\n"
                "🔄 Зачекайте кілька секунд..."
            )
        
        # Simple event extraction using existing GPT service
        try:
            from services.analysis import GPTAnalysisService
            gpt_service = GPTAnalysisService()
            
            # Use existing summarization to extract key points
            summary = await gpt_service.generate_summary_only(last_text)
            
            # Simple heuristic to detect if events are present
            event_keywords = ["зустріч", "дзвінок", "нарада", "презентація", "дедлайн", "завтра", "сьогодні", 
                            "о 14", "о 15", "о 16", "понеділок", "вівторок", "середа", "четвер", "п'ятниця"]
            
            has_events = any(keyword in last_text.lower() for keyword in event_keywords)
            
            if has_events:
                result_text = (
                    "🎯 **ЗНАЙДЕНІ ПОТЕНЦІЙНІ ПОДІЇ**\n\n"
                    f"📋 **Короткий зміст:**\n{summary}\n\n"
                    "🔍 **Виявлено ознаки подій:**\n"
                    "• Згадки про час та дати\n"
                    "• Планові заходи\n"
                    "• Зустрічі та наради\n\n"
                    "📅 **Для створення в календарі:**\n"
                    "1. Використайте /capture_chat для детального аналізу\n"
                    "2. Або /connect_calendar для підключення Google Calendar\n\n"
                    "💡 Більш точний аналіз доступний через режим захоплення переписки."
                )
            else:
                result_text = (
                    "📋 **АНАЛІЗ ЗАВЕРШЕНО**\n\n"
                    f"📝 **Короткий зміст:**\n{summary}\n\n"
                    "🔍 **Результат пошуку подій:**\n"
                    "У тексті не знайдено явних подій для календаря.\n\n"
                    "💡 **Поради:**\n"
                    "• Надішліть текст з конкретними датами\n"
                    "• Вкажіть час та місце заходів\n"
                    "• Використайте /capture_chat для детального аналізу"
                )
            
            if callback.message:
                await callback.message.edit_text(result_text, reply_markup=create_simple_result_keyboard())
            
        except Exception as analysis_error:
            logger.error(f"Analysis error: {analysis_error}")
            
            if callback.message:
                await callback.message.edit_text(
                    "❌ **Помилка аналізу**\n\n"
                    "Не вдалося проаналізувати текст для пошуку подій.\n\n"
                    "🔄 Спробуйте:\n"
                    "• /capture_chat для детального аналізу\n"
                    "• /summary для створення резюме\n"
                    "• Надіслати новий текст"
                )
        
        await callback.answer()
        logger.info(f"✅ Simple event extraction completed for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Event extraction failed for user {user_id}: {e}")
        await callback.answer("❌ Помилка витягування подій", show_alert=True)


def create_simple_result_keyboard():
    """Create simple keyboard for event extraction results"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Детальний аналіз", callback_data="start_capture_mode")
    builder.button(text="📅 Підключити календар", callback_data="connect_calendar_from_settings")
    builder.button(text="🔄 Новий текст", callback_data="request_new_analysis")
    
    return builder.as_markup()


@router.callback_query(F.data == "start_capture_mode")
async def cq_start_capture_mode(callback: types.CallbackQuery, state: FSMContext):
    """Start capture mode for detailed analysis"""
    await callback.answer(
        "📝 Використайте команду /capture_chat для детального аналізу переписок",
        show_alert=True
    )


@router.callback_query(F.data == "request_new_analysis")
async def cq_request_new_analysis(callback: types.CallbackQuery, state: FSMContext):
    """Request new text for analysis"""
    if callback.message:
        await callback.message.edit_text(
            "📝 **НОВИЙ АНАЛІЗ**\n\n"
            "Надішліть новий текст для аналізу подій.\n\n"
            "💡 **Для кращих результатів включіть:**\n"
            "• Конкретні дати та час\n"
            "• Назви заходів\n"
            "• Місця проведення\n"
            "• Імена учасників"
        )
    
    await callback.answer() 