"""
Summary Handler - /summary command with FSM
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup

from services.analysis import GPTAnalysisService
from config import SUMMARY_STYLES

logger = logging.getLogger(__name__)
router = Router()


class SummaryStates(StatesGroup):
    """States for summary command flow"""
    WAITING_FOR_TEXT = State()


@router.message(Command("summary"))
async def cmd_summary(message: types.Message, state: FSMContext):
    """
    🚀 PRODUCTION READY: /summary command
    Accepts text input and returns summary
    """
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    logger.info(f"🚀 /summary called by user {user_id}")
    
    try:
        await state.clear()  # Clean previous state
        
        # Check if text provided with command
        if not message.text:
            message.text = "/summary"
        
        command_text = message.text[8:].strip()  # Remove "/summary "
        
        if command_text:
            # Text provided directly with command
            await process_summary_request(message, command_text, state)
        else:
            # No text provided - enter FSM state to wait for text
            await state.set_state(SummaryStates.WAITING_FOR_TEXT)
            
            keyboard = create_summary_waiting_keyboard()
            
            await message.answer(
                "📝 **SUMMARY MODE**\n\n"
                "Надішліть текст для створення резюме:\n\n"
                "📄 **Підтримує:**\n"
                "• Текстові повідомлення\n"
                "• Довгі переписки\n"
                "• Документи та статті\n"
                "• Будь-який текстовий контент\n\n"
                "⚡️ Надішліть текст або натисніть відміну...",
                reply_markup=keyboard
            )
            
        logger.info(f"✅ Summary command processed for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Summary command failed for user {user_id}: {e}")
        await state.clear()
        
        await message.answer(
            "❌ **Помилка команди /summary**\n\n"
            f"Не вдалося запустити режим резюме: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або використайте /help"
        )


@router.message(SummaryStates.WAITING_FOR_TEXT, F.content_type == 'text', ~F.text.startswith('/'))
async def handle_summary_text_input(message: types.Message, state: FSMContext):
    """Handle text input in summary waiting state (exclude commands)"""
    if not message.from_user or not message.text:
        return
    
    user_id = message.from_user.id
    text_input = message.text
    
    logger.info(f"📝 Received summary text from user {user_id}, length: {len(text_input)}")
    
    try:
        await process_summary_request(message, text_input, state)
        
    except Exception as e:
        logger.error(f"❌ Summary text processing failed for user {user_id}: {e}")
        await message.answer(
            "❌ **Помилка обробки тексту**\n\n"
            f"Не вдалося створити резюме: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або натисніть /cancel"
        )


async def process_summary_request(message: types.Message, input_text: str, state: FSMContext):
    """Process summary request with progress indication"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    # Validate input
    if len(input_text.strip()) < 20:
        await message.answer(
            "⚠️ **Замало тексту**\n\n"
            "Для якісного резюме потрібно щонайменше 20 символів.\n"
            "Надішліть більше тексту або використайте /cancel"
        )
        return
    
    # Show progress
    progress_message = await message.answer(
        "🔍 **Аналізую текст...**\n\n"
        "⏳ Створюю резюме з допомогою AI...\n"
        "📊 Витягую ключові моменти...\n"
        "🔄 Зачекайте кілька секунд..."
    )
    
    try:
        # Get user settings for summary style
        user_summary_style = await get_user_summary_style(user_id)
        
        # Create summary using GPT service
        gpt_service = GPTAnalysisService()
        summary = await gpt_service.generate_summary_only(input_text)
        
        # Clear FSM state
        await state.clear()
        
        # Format result
        text_length = len(input_text)
        summary_length = len(summary)
        compression_ratio = round((1 - summary_length / text_length) * 100)
        
        result_text = (
            "✅ **РЕЗЮМЕ ГОТОВО**\n\n"
            f"📋 **Результат:**\n{summary}\n\n"
            f"📊 **Статистика:**\n"
            f"• Оригінал: {text_length} символів\n"
            f"• Резюме: {summary_length} символів\n"
            f"• Стиснення: {compression_ratio}%\n"
            f"• Стиль: {user_summary_style['name']}"
        )
        
        # Delete progress message
        try:
            await progress_message.delete()
        except:
            pass
        
        # Send result with keyboard
        keyboard = create_summary_result_keyboard()
        await message.answer(result_text, reply_markup=keyboard)
        
        logger.info(f"✅ Summary completed for user {user_id}: {summary_length} chars")
        
    except Exception as e:
        logger.error(f"❌ Summary generation failed for user {user_id}: {e}")
        
        # Delete progress message
        try:
            await progress_message.delete()
        except:
            pass
        
        await message.answer(
            "❌ **Помилка створення резюме**\n\n"
            f"Не вдалося проаналізувати текст: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або зверніться до адміністратора"
        )
        
        await state.clear()


async def get_user_summary_style(user_id: int) -> dict:
    """Get user's preferred summary style"""
    try:
        from services.database import get_user_setting
        style_key = await get_user_setting(user_id, 'summary_style', 'default')
        return SUMMARY_STYLES.get(style_key, SUMMARY_STYLES['default'])
    except:
        return SUMMARY_STYLES['default']


# ==============================================
# CALLBACK HANDLERS
# ==============================================

# Handle commands in summary mode
@router.message(SummaryStates.WAITING_FOR_TEXT, F.text.startswith('/'))
async def handle_commands_in_summary_mode(message: types.Message, state: FSMContext):
    """Handle commands when in summary waiting state"""
    if not message.from_user or not message.text:
        return
    
    command = message.text.lower()
    if command in ['/cancel', '/start']:
        await state.clear()
        await message.answer(
            "❌ **Режим резюме відмінено**\n\n"
            "Використайте /summary щоб почати знову."
        )
    else:
        await message.answer(
            "⚠️ **Ви в режимі створення резюме**\n\n"
            "Надішліть текст для резюме або натисніть /cancel для виходу."
        )


@router.callback_query(F.data == "cancel_summary", SummaryStates.WAITING_FOR_TEXT)
async def cq_cancel_summary(callback: types.CallbackQuery, state: FSMContext):
    """Cancel summary mode"""
    await state.clear()
    
    if callback.message:
        await callback.message.edit_text(
            "❌ **Режим резюме відмінено**\n\n"
            "Використайте /summary щоб почати знову."
        )
    await callback.answer()


@router.callback_query(F.data == "new_summary")
async def cq_new_summary(callback: types.CallbackQuery, state: FSMContext):
    """Start new summary session"""
    await state.set_state(SummaryStates.WAITING_FOR_TEXT)
    
    keyboard = create_summary_waiting_keyboard()
    
    if callback.message:
        await callback.message.edit_text(
            "📝 **НОВИЙ SUMMARY**\n\n"
            "Надішліть текст для створення резюме:\n\n"
            "⚡️ Готовий приймати ваш текст...",
            reply_markup=keyboard
        )
    await callback.answer()


@router.callback_query(F.data == "summary_settings")  
async def cq_summary_settings(callback: types.CallbackQuery):
    """Show summary settings"""
    await callback.answer(
        "⚙️ Використайте /settings для зміни стилю резюме",
        show_alert=True
    )


# ==============================================
# HELPER FUNCTIONS
# ==============================================

def create_summary_waiting_keyboard():
    """Create keyboard for waiting for text input"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Відмінити", callback_data="cancel_summary")
    builder.button(text="⚙️ Налаштування", callback_data="summary_settings")
    
    return builder.as_markup()


def create_summary_result_keyboard():
    """Create keyboard for summary result"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Нове резюме", callback_data="new_summary")
    builder.button(text="⚙️ Налаштування", callback_data="summary_settings")
    
    return builder.as_markup() 