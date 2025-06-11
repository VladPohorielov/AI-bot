"""
Capture Chat Command Handler - NEW FEATURE
Handles /capture_chat command without breaking existing structure
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.user_states import CaptureStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("capture_chat"))
async def cmd_capture_chat(message: types.Message, state: FSMContext):
    """
    🚀 PRODUCTION READY: /capture_chat command handler
    Initiates conversation capture session
    """
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    logger.info(f"🎯 /capture_chat command called by user {user_id}")
    
    try:
        # Set FSM state to wait for conversation text
        await state.set_state(CaptureStates.CAPTURING)
        
        # Create keyboard with cancel option
        keyboard = create_capture_waiting_keyboard()
        
        await message.answer(
            "📝 **РЕЖИМ ЗАХОПЛЕННЯ ПЕРЕПИСКИ**\n\n"
            "🎯 **Що робити:**\n"
            "• Надішліть текст переписки або розмови\n"
            "• Я проаналізую її та знайду події\n"
            "• Створю summary та витягну всі зустрічі\n\n"
            "⚡️ **Очікую ваш текст...**",
            reply_markup=keyboard
        )
        
        logger.info(f"✅ Capture chat mode activated for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Capture chat command failed for user {user_id}: {e}")
        await message.answer(
            "❌ **Помилка команди /capture_chat**\n\n"
            f"Не вдалося запустити режим захоплення: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або використайте /help"
        )


@router.message(CaptureStates.CAPTURING, F.content_type == 'text', ~F.text.startswith('/'))
async def handle_capture_text_input(message: types.Message, state: FSMContext):
    """Handle text input in capture mode (exclude commands)"""
    if not message.from_user or not message.text:
        return
    
    user_id = message.from_user.id
    text_input = message.text
    
    logger.info(f"📝 Received capture text from user {user_id}, length: {len(text_input)}")
    
    try:
        await process_capture_request(message, text_input, state)
        
    except Exception as e:
        logger.error(f"❌ Capture text processing failed for user {user_id}: {e}")
        await message.answer(
            "❌ **Помилка обробки переписки**\n\n"
            f"Не вдалося проаналізувати текст: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або натисніть /cancel"
        )


# Handle commands in capture mode
@router.message(CaptureStates.CAPTURING, F.text.startswith('/'))
async def handle_commands_in_capture_mode(message: types.Message, state: FSMContext):
    """Handle commands when in capture waiting state"""
    if not message.from_user or not message.text:
        return
    
    command = message.text.lower()
    if command in ['/cancel', '/start']:
        await state.clear()
        await message.answer(
            "❌ **Режим захоплення відмінено**\n\n"
            "Використайте /capture_chat щоб почати знову."
        )
    else:
        await message.answer(
            "⚠️ **Ви в режимі захоплення переписки**\n\n"
            "Надішліть текст переписки або натисніть /cancel для виходу."
        )


async def process_capture_request(message: types.Message, input_text: str, state: FSMContext):
    """Process capture request with enhanced analysis"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    # Validate input
    if len(input_text.strip()) < 20:
        await message.answer(
            "⚠️ **Замало тексту**\n\n"
            "Для якісного аналізу потрібно щонайменше 20 символів.\n"
            "Надішліть більше тексту або використайте /cancel"
        )
        return
    
    # Show progress
    progress_message = await message.answer(
        "🔍 **Аналізую переписку...**\n\n"
        "⏳ Створюю summary...\n"
        "📅 Шукаю події та зустрічі...\n"
        "🔄 Зачекайте кілька секунд..."
    )
    
    try:
        # Clear FSM state
        await state.clear()
        
        # Import existing services to use current functionality
        from services.analysis import GPTAnalysisService
        from services.event_extractor_new import EventExtractorService
        
        # 1. Generate summary (existing functionality)
        gpt_service = GPTAnalysisService()
        summary = await gpt_service.generate_summary_only(input_text)
        
        # 2. Extract events (NEW functionality)
        extractor = EventExtractorService()
        events = await extractor.extract_events(input_text)
        
        # Delete progress message
        try:
            await progress_message.delete()
        except:
            pass
        
        # Send summary first
        summary_text = (
            "📋 **SUMMARY ПЕРЕПИСКИ**\n\n"
            f"{summary}\n\n"
            f"📊 **Статистика:** {len(input_text)} символів проаналізовано"
        )
        
        await message.answer(summary_text)
        
        # Send events if found
        if events:
            for event in events:
                await send_event_card(message, event)
        else:
            await message.answer(
                "ℹ️ **Події не знайдено**\n\n"
                "У переписці немає згадок про зустрічі або події."
            )
        
        logger.info(f"✅ Capture completed for user {user_id}: {len(events)} events found")
        
    except Exception as e:
        logger.error(f"❌ Capture processing failed for user {user_id}: {e}")
        
        # Delete progress message
        try:
            await progress_message.delete()
        except:
            pass
        
        await message.answer(
            "❌ **Помилка аналізу переписки**\n\n"
            f"Не вдалося проаналізувати текст: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або зверніться до адміністратора"
        )


async def send_event_card(message: types.Message, event: dict):
    """Send formatted event card with action buttons"""
    event_text = (
        f"📅 **Подія: {event.get('title', 'Без назви')}**\n"
        f"🗓 Дата: {event.get('date', 'Не вказана')}\n"
        f"⏰ Час: {event.get('time', 'Не вказаний')}\n"
        f"📍 Місце: {event.get('location', 'Не вказане')}\n"
        f"⏳ Тривалість: {event.get('duration', 'Не вказана')}\n"
        f"💰 Оплата: {event.get('payment', 'Не вказана')}\n"
        f"🔹 Інше: {event.get('notes', 'Немає')}"
    )
    
    keyboard = create_event_card_keyboard(event.get('id', ''))
    
    await message.answer(event_text, reply_markup=keyboard)


# ==============================================
# CALLBACK HANDLERS
# ==============================================

@router.callback_query(F.data == "cancel_capture")
async def cq_cancel_capture(callback: types.CallbackQuery, state: FSMContext):
    """Cancel capture mode"""
    await state.clear()
    
    if callback.message:
        await callback.message.edit_text(
            "❌ **Режим захоплення відмінено**\n\n"
            "Використайте /capture_chat щоб почати знову."
        )
    await callback.answer()


@router.callback_query(F.data.startswith("event_add_"))
async def cq_add_event_to_calendar(callback: types.CallbackQuery):
    """Add event to Google Calendar"""
    if not callback.data:
        return
        
    event_id = callback.data.replace("event_add_", "")
    
    # TODO: Implement calendar integration
    await callback.answer(
        "🔄 Додавання до календаря буде доступне після налаштування /connect_calendar",
        show_alert=True
    )


@router.callback_query(F.data.startswith("event_edit_"))
async def cq_edit_event(callback: types.CallbackQuery):
    """Edit event details"""
    if not callback.data:
        return
        
    event_id = callback.data.replace("event_edit_", "")
    
    await callback.answer(
        "✏️ Редагування подій буде доступне в наступній версії",
        show_alert=True
    )


@router.callback_query(F.data.startswith("event_cancel_"))
async def cq_cancel_event(callback: types.CallbackQuery):
    """Cancel/dismiss event"""
    if callback.message:
        await callback.message.edit_text(
            "❌ **Подію відмінено**\n\n"
            "Використайте /capture_chat для нового аналізу."
        )
    await callback.answer()


# ==============================================
# HELPER FUNCTIONS
# ==============================================

def create_capture_waiting_keyboard():
    """Create keyboard for waiting for text input"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Відмінити", callback_data="cancel_capture")
    
    return builder.as_markup()


def create_event_card_keyboard(event_id: str):
    """Create keyboard for event card"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Додати у Calendar", callback_data=f"event_add_{event_id}")
    builder.button(text="✏️ Редагувати", callback_data=f"event_edit_{event_id}")
    builder.button(text="❌ Відмінити", callback_data=f"event_cancel_{event_id}")
    
    builder.adjust(1)  # Each button on a new line
    
    return builder.as_markup() 