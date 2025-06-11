"""
Enhanced Capture Flow Service
Provides improved UX with confirmation, editing, and error handling
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

from aiogram import types
from aiogram.fsm.context import FSMContext

from states.user_states import CaptureStates, EventEditStates
from services.analysis import GPTAnalysisService
from services.phone_extractor import phone_extractor
from services.google_calendar import create_calendar_event


logger = logging.getLogger(__name__)


@dataclass
class ExtractedEvent:
    """Represents an extracted event with all details"""
    id: str                    # Unique event ID
    title: str                 # Event title
    date: str                  # Date in YYYY-MM-DD format
    time: str                  # Time in HH:MM format
    location: str              # Event location
    participants: List[str]    # List of participants
    phones: List[str]          # Extracted phone numbers
    notes: str                 # Additional notes
    confidence: float          # AI extraction confidence
    original_text: str         # Original text segment


@dataclass
class CaptureSessionData:
    """Session data stored in FSM context"""
    session_id: int
    conversation_text: str
    summary: str
    events: List[ExtractedEvent]
    phones: List[str]
    current_edit_event_id: Optional[str] = None
    current_edit_field: Optional[str] = None


class EnhancedCaptureFlow:
    """Service for managing enhanced capture flow with UX improvements"""
    
    def __init__(self):
        self.gpt_service = GPTAnalysisService()
    
    async def start_analysis(
        self, 
        conversation_text: str, 
        callback: types.CallbackQuery, 
        state: FSMContext
    ) -> Dict[str, Any]:
        """
        Start analysis with progress indication
        Returns analysis results and updates FSM state
        """
        user_id = callback.from_user.id
        
        try:
            # Show analysis progress
            await callback.message.edit_text(
                "🔍 **Аналізую переписку...**\n\n"
                "⏳ Обробляю текст з допомогою AI...\n"
                "📊 Витягую події, дати та контакти...\n"
                "🔄 Зачекайте кілька секунд..."
            )
            
            # Set state to analyzing
            await state.set_state(CaptureStates.ANALYZING)
            
            # Extract phones first
            phones = phone_extractor.extract_phones(conversation_text)
            
            # Perform GPT analysis
            analysis_result = await self.gpt_service.analyze_conversation(conversation_text)
            
            # Process results into enhanced format
            processed_result = await self._process_analysis_results(
                analysis_result, 
                phones,
                conversation_text
            )
            
            # Store in FSM context
            session_data = CaptureSessionData(
                session_id=0,  # Will be updated
                conversation_text=conversation_text,
                summary=processed_result['summary'],
                events=processed_result['events'],
                phones=[p.formatted for p in phones]
            )
            
            await state.update_data(session_data=asdict(session_data))
            await state.set_state(CaptureStates.REVIEWING_RESULTS)
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Analysis failed for user {user_id}: {e}")
            await state.set_state(CaptureStates.IDLE)
            
            return {
                "success": False,
                "error": f"❌ Помилка аналізу: {str(e)}",
                "summary": "",
                "events": [],
                "phones": []
            }
    
    async def _process_analysis_results(
        self,
        analysis_result: Dict,
        phones: List,
        original_text: str
    ) -> Dict[str, Any]:
        """Process raw analysis results into enhanced format"""
        
        # Enhanced summary with phones
        summary = analysis_result.get('summary', '')
        if phones:
            phone_text = phone_extractor.format_for_display(phones)
            summary += f"\n\n{phone_text}"
        
        # Process events into ExtractedEvent objects
        events = []
        raw_events = analysis_result.get('events', [])
        
        for i, event_data in enumerate(raw_events):
            event = ExtractedEvent(
                id=f"event_{i+1}",
                title=event_data.get('title', 'Без назви'),
                date=event_data.get('date', ''),
                time=event_data.get('time', ''),
                location=event_data.get('location', ''),
                participants=event_data.get('participants', []),
                phones=[p.formatted for p in phones],  # Associate phones with event
                notes=event_data.get('notes', ''),
                confidence=event_data.get('confidence', 0.7),
                original_text=original_text[:200] + "..." if len(original_text) > 200 else original_text
            )
            events.append(event)
        
        return {
            "success": True,
            "summary": summary,
            "events": events,
            "phones": [p.formatted for p in phones],
            "total_events": len(events)
        }
    
    async def show_results_for_review(
        self,
        callback: types.CallbackQuery,
        state: FSMContext,
        results: Dict[str, Any]
    ):
        """Show analysis results with review/edit options"""
        
        if not results.get('success', False):
            await callback.message.edit_text(
                f"{results.get('error', 'Невідома помилка')}\n\n"
                "🔄 Спробуйте ще раз або зверніться до адміністратора."
            )
            return
        
        # Create results message
        text = "✅ **АНАЛІЗ ЗАВЕРШЕНО**\n\n"
        text += "📋 **РЕЗЮМЕ:**\n"
        text += results['summary'][:800]  # Limit length
        
        if len(results['summary']) > 800:
            text += "...\n*(повне резюме буде в календарі)*"
        
        text += f"\n\n🎯 **ЗНАЙДЕНО ПОДІЙ:** {results['total_events']}\n"
        
        # Show events summary
        for i, event in enumerate(results['events'][:3]):  # Show max 3 events in preview
            confidence_indicator = "🟢" if event.confidence > 0.8 else "🟡" if event.confidence > 0.6 else "🔴"
            text += f"\n{i+1}. {confidence_indicator} **{event.title}**"
            if event.date:
                text += f"\n   📅 {event.date}"
            if event.time:
                text += f" о {event.time}"
            if event.location:
                text += f"\n   📍 {event.location}"
        
        if len(results['events']) > 3:
            text += f"\n\n*... та ще {len(results['events']) - 3} подій*"
        
        # Create keyboard with options
        keyboard = self._create_review_keyboard(results['events'])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    
    def _create_review_keyboard(self, events: List[ExtractedEvent]):
        """Create keyboard for reviewing results"""
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        
        # Main action buttons
        builder.button(text="✅ Додати все в календар", callback_data="confirm_all_events")
        builder.button(text="✏️ Редагувати події", callback_data="edit_events_menu")
        
        # Individual event toggle buttons (if not too many)
        if len(events) <= 5:
            builder.row()  # New row
            for event in events:
                confidence_emoji = "🟢" if event.confidence > 0.8 else "🟡" if event.confidence > 0.6 else "🔴"
                builder.button(
                    text=f"{confidence_emoji} {event.title[:20]}", 
                    callback_data=f"toggle_event:{event.id}"
                )
        
        builder.row()  # New row for secondary actions
        builder.button(text="🔄 Повторити аналіз", callback_data="retry_analysis")
        builder.button(text="❌ Відмінити", callback_data="cancel_session")
        
        return builder.as_markup()
    
    async def handle_event_editing(
        self,
        callback: types.CallbackQuery,
        state: FSMContext,
        event_id: str
    ):
        """Handle editing of specific event"""
        
        # Get session data
        state_data = await state.get_data()
        session_data = CaptureSessionData(**state_data.get('session_data', {}))
        
        # Find the event
        event = next((e for e in session_data.events if e.id == event_id), None)
        if not event:
            await callback.answer("❌ Подію не знайдено")
            return
        
        # Update session data with current editing event
        session_data.current_edit_event_id = event_id
        await state.update_data(session_data=asdict(session_data))
        await state.set_state(CaptureStates.EDITING_EVENT)
        
        # Show editing menu
        text = f"✏️ **РЕДАГУВАННЯ ПОДІЇ**\n\n"
        text += f"**Назва:** {event.title}\n"
        text += f"**Дата:** {event.date or 'не вказано'}\n"
        text += f"**Час:** {event.time or 'не вказано'}\n"
        text += f"**Місце:** {event.location or 'не вказано'}\n"
        text += f"**Учасники:** {', '.join(event.participants) or 'не вказано'}\n"
        text += f"**Примітки:** {event.notes or 'не вказано'}\n"
        
        keyboard = self._create_event_edit_keyboard()
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    
    def _create_event_edit_keyboard(self):
        """Create keyboard for editing individual event fields"""
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        
        # Field editing buttons
        builder.button(text="📝 Назва", callback_data="edit_field:title")
        builder.button(text="📅 Дата", callback_data="edit_field:date")
        builder.button(text="⏰ Час", callback_data="edit_field:time")
        builder.button(text="📍 Місце", callback_data="edit_field:location")
        builder.button(text="👥 Учасники", callback_data="edit_field:participants")
        builder.button(text="📒 Примітки", callback_data="edit_field:notes")
        
        builder.row()  # New row
        builder.button(text="✅ Готово", callback_data="finish_editing")
        builder.button(text="🗑 Видалити подію", callback_data="delete_event")
        builder.button(text="◀️ Назад", callback_data="back_to_review")
        
        return builder.as_markup()
    
    async def save_events_to_calendar(
        self,
        callback: types.CallbackQuery,
        state: FSMContext,
        selected_events: List[str] = None
    ):
        """Save selected events to Google Calendar"""
        
        user_id = callback.from_user.id
        
        try:
            # Get session data
            state_data = await state.get_data()
            session_data = CaptureSessionData(**state_data.get('session_data', {}))
            
            # Determine which events to save
            events_to_save = session_data.events
            if selected_events:
                events_to_save = [e for e in session_data.events if e.id in selected_events]
            
            if not events_to_save:
                await callback.answer("❌ Немає подій для збереження")
                return
            
            await state.set_state(CaptureStates.SAVING_TO_CALENDAR)
            
            # Show progress
            await callback.message.edit_text(
                f"💾 **ЗБЕРЕЖЕННЯ В КАЛЕНДАР**\n\n"
                f"📊 Зберігаємо {len(events_to_save)} подій...\n"
                f"🔄 Зачекайте..."
            )
            
            saved_count = 0
            calendar_links = []
            
            # Save each event
            for event in events_to_save:
                try:
                    # Convert to calendar event format
                    calendar_event = self._convert_to_calendar_event(event, session_data.summary)
                    
                    # Save to Google Calendar
                    result = await create_calendar_event(user_id, calendar_event)
                    
                    if result.get('success'):
                        saved_count += 1
                        if result.get('event_link'):
                            calendar_links.append({
                                'title': event.title,
                                'link': result['event_link']
                            })
                    
                except Exception as e:
                    logger.error(f"Failed to save event {event.id}: {e}")
                    continue
            
            # Show results
            await self._show_save_results(callback, state, saved_count, len(events_to_save), calendar_links)
            
        except Exception as e:
            logger.error(f"Calendar save failed for user {user_id}: {e}")
            await callback.message.edit_text(
                "❌ **ПОМИЛКА ЗБЕРЕЖЕННЯ**\n\n"
                f"Не вдалося зберегти події в календар: {str(e)}\n\n"
                "🔄 Спробуйте ще раз або перевірте підключення до Google Calendar."
            )
    
    def _convert_to_calendar_event(self, event: ExtractedEvent, summary: str) -> Dict:
        """Convert ExtractedEvent to Google Calendar event format"""
        
        # Build description
        description = f"Автоматично створено з чату\n\n"
        description += f"РЕЗЮМЕ РОЗМОВИ:\n{summary}\n\n"
        
        if event.participants:
            description += f"УЧАСНИКИ:\n{', '.join(event.participants)}\n\n"
        
        if event.phones:
            description += f"КОНТАКТИ:\n{', '.join(event.phones)}\n\n"
        
        if event.notes:
            description += f"ДОДАТКОВІ ПРИМІТКИ:\n{event.notes}\n\n"
        
        description += f"Текст джерела:\n{event.original_text}"
        
        return {
            'summary': event.title,
            'description': description,
            'start_date': event.date,
            'start_time': event.time,
            'location': event.location,
            'attendees': event.participants
        }
    
    async def _show_save_results(
        self,
        callback: types.CallbackQuery,
        state: FSMContext,
        saved_count: int,
        total_count: int,
        calendar_links: List[Dict]
    ):
        """Show results of calendar save operation"""
        
        if saved_count == total_count:
            text = f"✅ **УСПІШНО ЗБЕРЕЖЕНО**\n\n"
            text += f"📅 Збережено {saved_count} з {total_count} подій в Google Calendar!\n\n"
        else:
            text = f"⚠️ **ЧАСТКОВО ЗБЕРЕЖЕНО**\n\n"
            text += f"📅 Збережено {saved_count} з {total_count} подій\n\n"
        
        # Add calendar links
        if calendar_links:
            text += "🔗 **ПОСИЛАННЯ НА ПОДІЇ:**\n"
            for link_data in calendar_links[:5]:  # Max 5 links
                text += f"• [{link_data['title']}]({link_data['link']})\n"
        
        text += f"\n📱 Перевірте свій Google Calendar для деталей."
        
        # Keyboard for final actions
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        
        if saved_count < total_count:
            builder.button(text="🔄 Повторити збереження", callback_data="retry_save")
        
        builder.button(text="📅 Відкрити Google Calendar", 
                      url="https://calendar.google.com")
        builder.button(text="✅ Готово", callback_data="finish_session")
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await state.set_state(CaptureStates.COMPLETED)


# Global instance
enhanced_flow = EnhancedCaptureFlow() 