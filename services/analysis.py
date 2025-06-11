"""
GPT Analysis Service for conversation capture sessions
Handles text analysis, summarization, and event extraction
"""
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from config import OPENAI_API_KEY

# Setup logging
logger = logging.getLogger(__name__)


class GPTAnalysisService:
    """Service for analyzing captured conversation sessions"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    
    async def analyze_conversation(self, conversation_text: str, session_id: int = None, user_id: int = None) -> Dict:
        """
        Analyze conversation text and extract summary + events with retries
        Optionally saves events to database if session_id and user_id provided
        Returns dict with 'summary' and 'events' keys
        """
        if not self.client:
            logger.error("OpenAI API key not configured")
            return {
                "summary": "❌ Ошибка: OpenAI API key не настроен",
                "events": []
            }
        
        if not conversation_text.strip():
            logger.warning("Empty conversation text provided")
            return {
                "summary": "Пустая сессия - нет текста для анализа",
                "events": []
            }
        
        # Try analysis with retries
        result = await self._analyze_with_retries(conversation_text)
        
        # Save events to database if session info provided
        if session_id and user_id and result.get("events"):
            try:
                await self._save_events_to_db(result["events"], session_id, user_id)
                logger.info(f"Saved {len(result['events'])} events to database for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to save events to database: {e}")
                # Don't fail the whole operation if DB save fails
        
        return result
    
    async def _analyze_with_retries(self, conversation_text: str, max_retries: int = 3) -> Dict:
        """
        Call GPT API with exponential backoff retries
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"GPT analysis attempt {attempt + 1}/{max_retries}")
                
                # Create analysis prompt
                system_prompt = self._get_analysis_prompt()
                
                # Extract phone numbers before GPT analysis
                try:
                    from .phone_extractor import phone_extractor
                    phones = phone_extractor.extract_phones(conversation_text)
                    phone_context = ""
                    if phones:
                        phone_context = f"\n\nВИТЯГНУТІ ТЕЛЕФОНИ:\n{phone_extractor.format_for_display(phones)}"
                except:
                    phone_context = ""

                # Call GPT for analysis
                response = await self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": conversation_text + phone_context}
                    ],
                    max_tokens=1500,
                    temperature=0.3,
                    timeout=30.0  # 30 second timeout
                )
                
                # Parse response
                result_text = response.choices[0].message.content
                result = self._parse_analysis_result(result_text)
                
                logger.info("GPT analysis completed successfully")
                return result
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "summary": "❌ Превышен лимит запросов к OpenAI API",
                        "events": []
                    }
                    
            except APIConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "summary": "❌ Ошибка подключения к OpenAI API",
                        "events": []
                    }
                    
            except APIError as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1 and e.status_code in [500, 502, 503, 504]:
                    # Retry on server errors
                    wait_time = 2 ** attempt
                    logger.info(f"Server error, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "summary": f"❌ Ошибка OpenAI API: {str(e)}",
                        "events": []
                    }
                    
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Unexpected error, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {
                        "summary": f"❌ Неожиданная ошибка: {str(e)}",
                        "events": []
                    }
        
        # This shouldn't be reached, but just in case
        return {
            "summary": "❌ Не удалось проанализировать текст после всех попыток",
            "events": []
        }
    
    async def _save_events_to_db(self, events: List[Dict], session_id: int, user_id: int):
        """
        Save extracted events to database
        """
        try:
            from .database import AsyncSessionLocal, Event
            
            async with AsyncSessionLocal() as session:
                for event_data in events:
                    # Parse datetime from date/time strings
                    start_datetime = self._parse_datetime(
                        event_data.get("date"), 
                        event_data.get("time")
                    )
                    
                    # Create Event object
                    event = Event(
                        session_id=session_id,
                        user_id=user_id,
                        title=event_data.get("title", ""),
                        event_type=event_data.get("type", "event"),
                        priority=event_data.get("priority", "medium"),
                        start_datetime=start_datetime,
                        location=event_data.get("location"),
                        participants=event_data.get("participants", []),
                        action_items=event_data.get("action_items", [])
                    )
                    
                    session.add(event)
                
                await session.commit()
                logger.info(f"Successfully saved {len(events)} events to database")
                
        except Exception as e:
            logger.error(f"Database save error: {e}")
            raise
    
    def _parse_datetime(self, date_str: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date and time strings into datetime object
        """
        if not date_str:
            return None
            
        try:
            # Parse date (YYYY-MM-DD format)
            date_parts = date_str.split("-")
            if len(date_parts) != 3:
                return None
                
            year, month, day = map(int, date_parts)
            
            # Parse time if provided
            hour, minute = 0, 0
            if time_str:
                time_parts = time_str.split(":")
                if len(time_parts) >= 2:
                    hour, minute = int(time_parts[0]), int(time_parts[1])
            
            return datetime(year, month, day, hour, minute)
            
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse datetime: {date_str} {time_str}")
            return None
    
    def _get_analysis_prompt(self) -> str:
        """Get sophisticated system prompt for conversation analysis with examples"""
        return """Ты - экспертный AI ассистент Briefly для анализа переписок, встреч и разговоров. 

ЗАДАЧА: Проанализировать текст и извлечь:
1. Краткое резюме основных тем и решений
2. Структурированные события (встречи, дедлайны, задачи)

ТИПЫ СОБЫТИЙ:
- meeting: встречи, созвоны, переговоры
- deadline: дедлайны, сроки сдачи
- task: задачи, поручения
- appointment: личные встречи, appointments
- reminder: напоминания

ПАРСИНГ ДАТЕ/ВРЕМЕНИ:
- "завтра" -> следующий день от текущей даты
- "понедельник" -> ближайший понедельник
- "через неделю" -> +7 дней
- "в 15:00" -> 15:00
- "в 3 дня" -> 15:00
- Точные даты: "12 декабря", "2024-01-15"

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
{
  "summary": "Краткое резюме ключевых моментов и решений",
  "events": [
    {
      "title": "Четкое название события",
      "date": "YYYY-MM-DD или null",
      "time": "HH:MM или null", 
      "location": "место/ссылка или null",
      "participants": ["имя1", "имя2"],
      "action_items": ["конкретное действие", "кто за что отвечает"],
      "type": "meeting|deadline|task|appointment|reminder",
      "priority": "high|medium|low"
    }
  ]
}

ПРИМЕРЫ:

Текст: "Встречаемся завтра в 14:00 в офисе с командой. Алексей готовит презентацию, Мария - отчет по бюджету"
Результат:
{
  "summary": "Запланирована встреча команды для обсуждения презентации и бюджета",
  "events": [
    {
      "title": "Встреча команды",
      "date": null,
      "time": "14:00",
      "location": "офис",
      "participants": ["Алексей", "Мария"],
      "action_items": ["Алексей готовит презентацию", "Мария готовит отчет по бюджету"],
      "type": "meeting",
      "priority": "medium"
    }
  ]
}

Текст: "Дедлайн по проекту 15 января. Нужно закончить разработку и тестирование"
Результат:
{
  "summary": "Установлен дедлайн завершения проекта с требованиями по разработке и тестированию",
  "events": [
    {
      "title": "Дедлайн по проекту",
      "date": "2024-01-15",
      "time": null,
      "location": null,
      "participants": [],
      "action_items": ["закончить разработку", "провести тестирование"],
      "type": "deadline",
      "priority": "high"
    }
  ]
}

ВАЖНО:
- Извлекай только четко упомянутые события
- Не додумывай детали которых нет в тексте
- Summary должно быть кратким и информативным (1-2 предложения)
- action_items - только конкретные задачи/действия
- priority определяй по контексту (дедлайны = high, обычные встречи = medium)
- Возвращай ТОЛЬКО валидный JSON без дополнительного текста"""

    def _parse_analysis_result(self, result_text: str) -> Dict:
        """Parse GPT response and extract structured data with enhanced validation"""
        try:
            # Try to find JSON in the response
            result_text = result_text.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            # Additional cleanup
            result_text = result_text.strip()
            
            # Parse JSON
            parsed = json.loads(result_text)
            
            # Validate structure
            if not isinstance(parsed, dict):
                raise ValueError("Response is not a dictionary")
            
            summary = parsed.get("summary", "Не удалось извлечь резюме")
            events = parsed.get("events", [])
            
            # Enhanced validation for events
            validated_events = []
            for i, event in enumerate(events):
                if not isinstance(event, dict):
                    logger.warning(f"Event {i} is not a dictionary, skipping")
                    continue
                    
                if not event.get("title"):
                    logger.warning(f"Event {i} has no title, skipping")
                    continue
                
                # Validate and sanitize fields
                validated_event = {
                    "title": str(event.get("title", "")).strip(),
                    "date": self._validate_date(event.get("date")),
                    "time": self._validate_time(event.get("time")),
                    "location": str(event.get("location", "")).strip() if event.get("location") else None,
                    "participants": self._validate_list(event.get("participants")),
                    "action_items": self._validate_list(event.get("action_items")),
                    "type": self._validate_event_type(event.get("type")),
                    "priority": self._validate_priority(event.get("priority"))
                }
                
                # Only add if title is not empty after sanitization
                if validated_event["title"]:
                    validated_events.append(validated_event)
                else:
                    logger.warning(f"Event {i} has empty title after validation, skipping")
            
            logger.info(f"Successfully validated {len(validated_events)} events from GPT response")
            
            return {
                "summary": summary.strip() if summary else "Не удалось извлечь резюме",
                "events": validated_events
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {
                "summary": "❌ Ошибка парсинга ответа GPT (неверный JSON)",
                "events": []
            }
        except Exception as e:
            logger.error(f"Analysis result parsing error: {e}")
            return {
                "summary": f"❌ Ошибка обработки результата: {str(e)}",
                "events": []
            }
    
    def _validate_date(self, date_value) -> Optional[str]:
        """Validate date string format"""
        if not date_value:
            return None
        
        date_str = str(date_value).strip()
        if not date_str or date_str.lower() == "null":
            return None
            
        # Basic date format validation (YYYY-MM-DD)
        try:
            parts = date_str.split("-")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                year, month, day = map(int, parts)
                if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                    return date_str
        except:
            pass
            
        logger.warning(f"Invalid date format: {date_value}")
        return None
    
    def _validate_time(self, time_value) -> Optional[str]:
        """Validate time string format"""
        if not time_value:
            return None
            
        time_str = str(time_value).strip()
        if not time_str or time_str.lower() == "null":
            return None
            
        # Basic time format validation (HH:MM)
        try:
            parts = time_str.split(":")
            if len(parts) >= 2:
                hour, minute = int(parts[0]), int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
        except:
            pass
            
        logger.warning(f"Invalid time format: {time_value}")
        return None
    
    def _validate_list(self, list_value) -> List[str]:
        """Validate and sanitize list of strings"""
        if not list_value:
            return []
            
        if isinstance(list_value, list):
            result = []
            for item in list_value:
                if item and isinstance(item, (str, int, float)):
                    cleaned = str(item).strip()
                    if cleaned:
                        result.append(cleaned)
            return result
        elif isinstance(list_value, str):
            # Sometimes GPT returns comma-separated string instead of list
            return [item.strip() for item in list_value.split(",") if item.strip()]
        
        return []
    
    def _validate_event_type(self, type_value) -> str:
        """Validate event type"""
        valid_types = ["meeting", "deadline", "task", "appointment", "reminder", "event"]
        
        if not type_value:
            return "event"
            
        type_str = str(type_value).strip().lower()
        return type_str if type_str in valid_types else "event"
    
    def _validate_priority(self, priority_value) -> str:
        """Validate priority value"""
        valid_priorities = ["high", "medium", "low"]
        
        if not priority_value:
            return "medium"
            
        priority_str = str(priority_value).strip().lower()
        return priority_str if priority_str in valid_priorities else "medium"
    
    async def generate_summary_only(self, text: str) -> str:
        """
        Generate only summary without event extraction (faster)
        """
        if not self.client:
            return "❌ Ошибка: OpenAI API key не настроен"
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "Создай краткое резюме предоставленного текста на русском языке. Выдели основные темы и важные моменты."
                    },
                    {"role": "user", "content": text}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"❌ Ошибка при создании резюме: {str(e)}"
    
    def get_prompt_examples(self) -> List[Dict]:
        """
        Get example conversations for testing prompt accuracy
        """
        return [
            {
                "name": "Meeting Planning",
                "text": "Давайте встретимся завтра в 15:00 в зале переговоров. Антон подготовит презентацию по Q4, Лена покажет новый дизайн. Нужно обсудить бюджет на следующий год.",
                "expected_events": 1,
                "expected_types": ["meeting"]
            },
            {
                "name": "Deadline with Tasks", 
                "text": "Дедлайн проекта 25 декабря. Иван доделывает бэкенд, Катя тестирует API, я пишу документацию. Все должно быть готово к понедельнику.",
                "expected_events": 1,
                "expected_types": ["deadline"]
            },
            {
                "name": "Multiple Events",
                "text": "Созвон в пятницу в 10 утра по Zoom. Отчет нужно сдать до 20 числа. Во вторник встречаемся с клиентом в их офисе на Крещатике.",
                "expected_events": 3,
                "expected_types": ["meeting", "deadline", "meeting"]
            },
            {
                "name": "Voice Message Style",
                "text": "Эй, слушай, завтра никак не получается. Давайте лучше в среду, часа в два дня? Мне нужно показать тебе новые макеты. Кстати, не забудь документы по договору принести.",
                "expected_events": 1,
                "expected_types": ["meeting"]
            },
            {
                "name": "Complex Business Discussion",
                "text": "Совещание по бюджету перенесли на понедельник 14:30. Участвуют: Иванов, Петрова, Сидоров. Нужно подготовить: отчет по расходам за Q3, план на Q4, анализ конкурентов. Встречаемся в большом зале. Дедлайн по презентации - пятница.",
                "expected_events": 2,
                "expected_types": ["meeting", "deadline"]
            }
        ]
    
    async def test_prompt_accuracy(self, example_idx: int = None) -> Dict:
        """
        Test prompt accuracy on example conversations
        """
        examples = self.get_prompt_examples()
        
        if example_idx is not None:
            examples = [examples[example_idx]] if example_idx < len(examples) else []
        
        results = []
        for i, example in enumerate(examples):
            print(f"Testing example {i+1}: {example['name']}")
            
            result = await self.analyze_conversation(example["text"])
            events_count = len(result.get("events", []))
            event_types = [e.get("type") for e in result.get("events", [])]
            
            accuracy = {
                "example_name": example["name"],
                "expected_events": example["expected_events"],
                "actual_events": events_count,
                "expected_types": example["expected_types"],
                "actual_types": event_types,
                "events_match": events_count == example["expected_events"],
                "summary": result.get("summary", ""),
                "events": result.get("events", [])
            }
            
            results.append(accuracy)
        
        return {
            "total_tests": len(results),
            "passed": sum(1 for r in results if r["events_match"]),
            "results": results
        }


# Global instance
gpt_analysis = GPTAnalysisService() 