import logging
import asyncio
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hcode

from config import (MAX_MESSAGE_LENGTH, SUMMARY_DISPLAY_CHUNK_SIZE,
                    SUMMARY_STYLES)
from handlers.common_handlers import get_user_settings
from services.summarization import generate_summary
from services.event_extraction import extract_events_from_text

logger = logging.getLogger(__name__)
router = Router()
logger.info("text_input_handler.router created.")


@router.message(F.text, ~F.text.startswith('/'))
async def handle_text_input(message: types.Message, user_settings: dict, state: FSMContext):
    if not message.from_user:
        await message.answer("⚠️ Помилка: користувач не знайдений.")
        return
        
    user_id = message.from_user.id
    text_input = message.text
    
    if not text_input:
        await message.answer("⚠️ Пустий текст для аналізу.")
        return
    
    logger.info(f"handle_text_input called by user {user_id} with text: '{text_input[:50]}...'")
    status_msg = await message.answer("💡 Аналізую ваш текст...")

    user_prefs = get_user_settings(user_id, user_settings)
    selected_summary_style = user_prefs.get("summary_style", "default")
    logger.debug(f"User {user_id} prefs for text input: style={selected_summary_style}")

    try:
        # Run summary and event extraction in parallel
        await status_msg.edit_text("💡 Генерую резюме та аналізую події...")
        
        summary_task = generate_summary(text_input, selected_summary_style)
        events_task = extract_events_from_text(text_input)
        
        summary, events = await asyncio.gather(summary_task, events_task)
        
        logger.info(f"Analysis complete for user {user_id}. Summary length: {len(summary)}, Events found: {len(events)}")

        # Store text for event extraction button
        await state.update_data(last_analyzed_text=text_input)

        # Build response
        summary_header = f"💡 <b>Краткое резюме</b> (Стиль: {hbold(SUMMARY_STYLES.get(selected_summary_style, {}).get('name', 'Стандартный'))}):"
        response_parts = [f"{summary_header}\n{summary}"]
        
        # Add events if found
        events_header = ""  # Initialize to avoid unbound variable
        if events:
            events_header = f"\n\n📅 <b>Знайдені події</b> ({len(events)}):"
            response_parts.append(events_header)
            
            for i, event in enumerate(events, 1):
                event_text = _format_event(event, i)
                response_parts.append(event_text)
            
            # Add calendar suggestion
            response_parts.append(
                "\n💡 <b>Підказка:</b> Використовуйте /capture_chat для детального аналізу розмов і синхронізації з Google Calendar."
            )
        
        full_response_text = "\n".join(response_parts)

        # Create keyboard with event extraction button
        keyboard = create_text_analysis_keyboard(bool(events))

        if len(full_response_text) <= MAX_MESSAGE_LENGTH:
            await status_msg.edit_text(full_response_text, reply_markup=keyboard)
        else:
            await status_msg.edit_text("✅ Аналіз готовий! Надсилаю результат частинами...")
            
            # Send summary
            await message.answer(f"{summary_header}\n{summary}")
            
            # Send events if any
            if events:
                events_text = "\n".join(response_parts[1:])  # Skip summary part
                if len(events_text) <= MAX_MESSAGE_LENGTH:
                    await message.answer(events_text, reply_markup=keyboard)
                else:
                    # Send events one by one if too long
                    await message.answer(events_header)
                    for i, event in enumerate(events, 1):
                        event_text = _format_event(event, i)
                        await message.answer(event_text)
                    
                    await message.answer(
                        "💡 <b>Підказка:</b> Використовуйте /capture_chat для детального аналізу розмов і синхронізації з Google Calendar.",
                        reply_markup=keyboard
                    )
            else:
                # No events found, show keyboard anyway
                await message.answer("🔍 Використайте кнопки нижче для додаткових дій:", reply_markup=keyboard)
        
        logger.info(f"Successfully processed text input for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error processing text input for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка при обработке текста: {e}")


def _format_event(event: dict, index: int) -> str:
    """
    Format event for display
    """
    title = event.get("title", "Без назви")
    date_str = event.get("date", "Дата не вказана")
    time_str = event.get("time", "Час не вказаний")
    location = event.get("location")
    participants = event.get("participants", [])
    event_type = event.get("type", "meeting")
    
    # Event type emoji
    type_emoji = {
        "meeting": "🤝",
        "deadline": "⏰", 
        "event": "🎉",
        "call": "📞",
        "appointment": "📅"
    }.get(event_type, "📅")
    
    result = f"{type_emoji} <b>{index}. {title}</b>\n"
    
    # Date and time
    if date_str and time_str:
        result += f"📅 {date_str} о {time_str}\n"
    elif date_str:
        result += f"📅 {date_str}\n"
    elif time_str:
        result += f"🕐 {time_str}\n"
    
    # Location
    if location:
        result += f"📍 {location}\n"
    
    # Participants
    if participants:
        if len(participants) == 1:
            result += f"👤 {participants[0]}\n"
        else:
            result += f"👥 {', '.join(participants)}\n"
    
    return result.strip()


def create_text_analysis_keyboard(has_events: bool):
    """Create keyboard for text analysis results"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    
    # Always show extract events button
    builder.button(text="🔍 Витягати події", callback_data="extract_events")
    builder.button(text="📝 Новий summary", callback_data="new_summary")
    
    # Show capture chat option if no events found
    if not has_events:
        builder.button(text="📝 Детальний аналіз", callback_data="start_capture_mode")
    
    builder.row()  # New row
    builder.button(text="📅 Підключити календар", callback_data="connect_calendar_from_settings")
    
    return builder.as_markup()
