"""
ChatGPT Handler - Direct interaction with OpenAI ChatGPT
Allows users to chat directly with GPT using /ask command
"""
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup

from services.analysis import GPTAnalysisService

logger = logging.getLogger(__name__)
router = Router()


class ChatGPTStates(StatesGroup):
    """States for ChatGPT conversation"""
    CHATTING = State()


@router.message(Command("ask"))
async def cmd_ask_chatgpt(message: types.Message, state: FSMContext):
    """
    🚀 PRODUCTION READY: /ask command for ChatGPT interaction
    Usage: /ask [prompt] or /ask (then send prompt)
    """
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    logger.info(f"🤖 /ask command called by user {user_id}")
    
    try:
        await state.clear()  # Clean previous state
        
        # Check if prompt provided with command
        if not message.text:
            message.text = "/ask"
        
        prompt_text = message.text[4:].strip()  # Remove "/ask "
        
        if prompt_text:
            # Prompt provided directly with command
            await process_chatgpt_request(message, prompt_text, state)
        else:
            # No prompt provided - enter chat mode
            await state.set_state(ChatGPTStates.CHATTING)
            
            keyboard = create_chatgpt_keyboard()
            
            await message.answer(
                "🤖 **CHATGPT РЕЖИМ**\n\n"
                "Тепер ви можете спілкуватися з ChatGPT!\n\n"
                "💬 **Що можна робити:**\n"
                "• Задавати будь-які питання\n"
                "• Просити допомогу з кодом\n"
                "• Перекладати тексти\n"
                "• Створювати контент\n"
                "• Аналізувати інформацію\n\n"
                "⚡️ Надішліть ваше питання або промт...",
                reply_markup=keyboard
            )
            
        logger.info(f"✅ ChatGPT command processed for user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ ChatGPT command failed for user {user_id}: {e}")
        await state.clear()
        
        await message.answer(
            "❌ **Помилка команди /ask**\n\n"
            f"Не вдалося запустити ChatGPT режим: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або використайте /help"
        )


@router.message(ChatGPTStates.CHATTING, F.content_type == 'text')
async def handle_chatgpt_conversation(message: types.Message, state: FSMContext):
    """Handle text input in ChatGPT conversation state"""
    if not message.from_user or not message.text:
        return
    
    user_id = message.from_user.id
    user_prompt = message.text
    
    logger.info(f"🤖 ChatGPT prompt from user {user_id}, length: {len(user_prompt)}")
    
    try:
        await process_chatgpt_request(message, user_prompt, state, keep_chat_mode=True)
        
    except Exception as e:
        logger.error(f"❌ ChatGPT conversation failed for user {user_id}: {e}")
        await message.answer(
            "❌ **Помилка ChatGPT**\n\n"
            f"Не вдалося отримати відповідь: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або натисніть /cancel"
        )


async def process_chatgpt_request(message: types.Message, user_prompt: str, state: FSMContext, keep_chat_mode: bool = False):
    """Process ChatGPT request with progress indication"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    # Validate input
    if len(user_prompt.strip()) < 3:
        await message.answer(
            "⚠️ **Занадто короткий промт**\n\n"
            "Напишіть більш детальне питання або запит.\n"
            "Мінімум 3 символи."
        )
        return
    
    # Show progress
    progress_message = await message.answer(
        "🤖 **ChatGPT думає...**\n\n"
        "⏳ Обробляю ваш запит...\n"
        "🧠 Генерую відповідь...\n"
        "🔄 Зачекайте кілька секунд..."
    )
    
    try:
        # Use OpenAI GPT service for direct conversation
        gpt_service = GPTAnalysisService()
        
        if not gpt_service.client:
            await progress_message.edit_text(
                "❌ **OpenAI API не налаштований**\n\n"
                "Для використання ChatGPT потрібен API ключ OpenAI.\n\n"
                "💡 Використайте /summary для G4F (безкоштовного) резюме."
            )
            return
        
        # Create conversation with ChatGPT
        try:
            response = await gpt_service.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "Ви ChatGPT в Telegram боті Briefly. "
                            "Відповідайте корисно, дружелюбно та українською мовою. "
                            "Якщо запитують англійською - відповідайте англійською. "
                            "Будьте стислими, але інформативними."
                        )
                    },
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.7,
                timeout=30.0
            )
            
            chatgpt_response = response.choices[0].message.content
            
            if not keep_chat_mode:
                await state.clear()
            
            # Format response
            result_text = (
                f"🤖 **ChatGPT відповідь:**\n\n"
                f"{chatgpt_response}\n\n"
                f"💭 **Ваш запит:** {user_prompt[:100]}{'...' if len(user_prompt) > 100 else ''}"
            )
            
            # Delete progress message
            try:
                await progress_message.delete()
            except:
                pass
            
            # Send result with keyboard
            keyboard = create_chatgpt_result_keyboard(keep_chat_mode)
            
            # Split long responses
            if len(result_text) > 4000:
                # Send response part by part
                await message.answer(f"🤖 **ChatGPT відповідь:**\n\n{chatgpt_response}")
                await message.answer(
                    f"💭 **Ваш запит:** {user_prompt[:200]}{'...' if len(user_prompt) > 200 else ''}",
                    reply_markup=keyboard
                )
            else:
                await message.answer(result_text, reply_markup=keyboard)
            
            logger.info(f"✅ ChatGPT response sent to user {user_id}: {len(chatgpt_response)} chars")
            
        except Exception as api_error:
            logger.error(f"❌ OpenAI API error for user {user_id}: {api_error}")
            
            # Delete progress message
            try:
                await progress_message.delete()
            except:
                pass
            
            await message.answer(
                f"❌ **Помилка ChatGPT API**\n\n"
                f"Не вдалося отримати відповідь: {str(api_error)}\n\n"
                "💡 **Можливі причини:**\n"
                "• Перевищено ліміт запитів\n"
                "• Проблеми з підключенням\n"
                "• API ключ недійсний\n\n"
                "🔄 Спробуйте ще раз або використайте /summary"
            )
        
    except Exception as e:
        logger.error(f"❌ ChatGPT processing failed for user {user_id}: {e}")
        
        # Delete progress message
        try:
            await progress_message.delete()
        except:
            pass
        
        await message.answer(
            "❌ **Загальна помилка**\n\n"
            f"Щось пішло не так: {str(e)}\n\n"
            "🔄 Спробуйте ще раз або зверніться до адміністратора"
        )
        
        if not keep_chat_mode:
            await state.clear()


# ==============================================
# CALLBACK HANDLERS
# ==============================================

@router.callback_query(F.data == "continue_chat")
async def cq_continue_chat(callback: types.CallbackQuery, state: FSMContext):
    """Continue ChatGPT conversation"""
    await state.set_state(ChatGPTStates.CHATTING)
    
    if callback.message:
        await callback.message.edit_text(
            "🤖 **Продовжуємо спілкування з ChatGPT**\n\n"
            "💬 Надішліть ваше наступне питання або промт...",
            reply_markup=create_chatgpt_keyboard()
        )
    
    await callback.answer()


@router.callback_query(F.data == "new_chat")
async def cq_new_chat(callback: types.CallbackQuery, state: FSMContext):
    """Start new ChatGPT conversation"""
    await state.set_state(ChatGPTStates.CHATTING)
    
    if callback.message:
        await callback.message.edit_text(
            "🤖 **Новий ChatGPT чат**\n\n"
            "💬 Надішліть ваше питання або промт...",
            reply_markup=create_chatgpt_keyboard()
        )
    
    await callback.answer()


@router.callback_query(F.data == "exit_chat")
async def cq_exit_chat(callback: types.CallbackQuery, state: FSMContext):
    """Exit ChatGPT conversation mode"""
    await state.clear()
    
    if callback.message:
        await callback.message.edit_text(
            "✅ **ChatGPT режим завершено**\n\n"
            "Використайте /ask щоб почати знову.\n"
            "Або /summary для звичайного резюме."
        )
    
    await callback.answer()


# ==============================================
# HELPER FUNCTIONS
# ==============================================

def create_chatgpt_keyboard():
    """Create keyboard for ChatGPT chat mode"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Завершити чат", callback_data="exit_chat")
    builder.button(text="ℹ️ Поради", callback_data="chatgpt_tips")
    
    return builder.as_markup()


def create_chatgpt_result_keyboard(chat_mode: bool = False):
    """Create keyboard for ChatGPT result"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    if chat_mode:
        builder.button(text="💬 Продовжити чат", callback_data="continue_chat")
        builder.button(text="❌ Завершити", callback_data="exit_chat")
    else:
        builder.button(text="🔄 Нове питання", callback_data="new_chat")
        builder.button(text="📝 Summary режим", callback_data="new_summary")
    
    return builder.as_markup()


@router.callback_query(F.data == "chatgpt_tips")
async def cq_chatgpt_tips(callback: types.CallbackQuery):
    """Show ChatGPT usage tips"""
    tips_text = (
        "💡 ПОРАДИ ДЛЯ ChatGPT:\n\n"
        "🎯 Будьте конкретними\n"
        "💻 Вказуйте мову коду\n"
        "📝 Зазначте стиль тексту\n"
        "🌍 Вкажіть мови перекладу"
    )
    
    await callback.answer(tips_text, show_alert=True) 