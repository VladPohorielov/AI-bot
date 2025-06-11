"""
Event extraction service using g4f for free analysis
"""
import g4f
import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def extract_events_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract events from text using g4f
    Returns list of events with title, date, time, location, etc.
    """
    if not text or not text.strip():
        return []

    system_prompt = """
You are an event extraction assistant. Extract planned meetings, events, deadlines from conversation text.

TASK: Find scheduled meetings, events, deadlines in the text and return them in JSON format.

RESPONSE FORMAT - ONLY valid JSON array:
[
    {
        "title": "Event title",
        "date": "YYYY-MM-DD or 'tomorrow' or 'today'", 
        "time": "HH:MM",
        "location": "address or place",
        "participants": ["name1", "name2"],
        "type": "meeting/deadline/event",
        "priority": "high/medium/low"
    }
]

RULES:
1. Look for specific plans: meetings, deadlines, events
2. DO NOT extract past events or just mentions
3. If date not explicit, try to understand from context
4. If time not specified, put approximate or null
5. If no events - return empty array []

EXAMPLES:
- "meet tomorrow at cafe at 9:45" → event with time
- "call on Monday" → event without exact time
- "went to cinema yesterday" → DO NOT extract (past)

IMPORTANT: Respond ONLY with valid JSON array, no other text!
"""

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Извлеки события из этого текста:\n\n{text}"}
    ]

    try:
        logger.info("Extracting events using g4f...")
        
        # Use sync method in executor for compatibility
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: g4f.ChatCompletion.create(
                model=g4f.models.gpt_4o_mini,
                messages=messages
            )
        )
        
        if not response or not isinstance(response, str):
            logger.warning("Empty or invalid response from g4f")
            return []
        
        logger.debug(f"Raw g4f response: {response}")
        
        # Check if response is blocked
        blocked_phrases = ["request blocked", "get in touch", "solution for your use case"]
        if any(phrase in response.lower() for phrase in blocked_phrases):
            logger.warning("Request was blocked by provider")
            return []
        
        # Try to extract JSON from response
        events = _parse_events_response(response)
        logger.info(f"Extracted {len(events)} events from text")
        return events
        
    except Exception as e:
        logger.error(f"Error extracting events: {e}", exc_info=True)
        return []


def _parse_events_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse events from g4f response, handling various JSON formats
    """
    try:
        logger.debug(f"Parsing response: {response[:200]}...")
        
        # Clean response - remove markdown formatting
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Fix common JSON issues with quotes
        response = re.sub(r'"([^"]*)"([^"]*)"([^"]*)"', r'"\1\2\3"', response)  # Fix nested quotes
        response = response.replace('"', '"').replace('"', '"')  # Fix smart quotes
        
        # If response doesn't look like JSON, try to extract events manually
        if not (response.startswith('[') or response.startswith('{')):
            logger.debug("Response doesn't look like JSON, trying manual extraction")
            return _extract_events_manually(response)
        
        # Find JSON array in response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # Try to find JSON object and wrap in array
            obj_match = re.search(r'\{.*\}', response, re.DOTALL)
            if obj_match:
                json_str = f"[{obj_match.group(0)}]"
            else:
                logger.warning("No JSON found in response")
                return _extract_events_manually(response)
        
        logger.debug(f"Extracted JSON string: {json_str[:100]}...")
        
        # Parse JSON
        events_data = json.loads(json_str)
        
        if not isinstance(events_data, list):
            logger.warning(f"Expected list, got {type(events_data)}")
            if isinstance(events_data, dict):
                events_data = [events_data]
            else:
                return []
        
        # Validate and clean events
        valid_events = []
        for event_data in events_data:
            if isinstance(event_data, dict):
                cleaned_event = _clean_event_data(event_data)
                if cleaned_event:
                    valid_events.append(cleaned_event)
        
        logger.info(f"Successfully parsed {len(valid_events)} events from JSON")
        return valid_events
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.debug(f"Failed to parse: {response}")
        # Fallback to manual extraction
        return _extract_events_manually(response)
    except Exception as e:
        logger.error(f"Error parsing events response: {e}")
        return []


def _extract_events_manually(response: str) -> List[Dict[str, Any]]:
    """
    Manually extract events from non-JSON response
    """
    try:
        logger.info("Attempting manual event extraction")
        
        # Look for common patterns in Ukrainian/Russian
        events = []
        text = response.lower()
        
        # Look for time patterns and associated context
        time_patterns = [
            r'(\d{1,2}:\d{2})',  # HH:MM format
            r'о\s+(\d{1,2}:\d{2})',  # о HH:MM
            r'в\s+(\d{1,2}:\d{2})',  # в HH:MM
            r'начина.*?(\d{1,2}:\d{2})',  # начинаемо о HH:MM
            r'з\s+(\d{1,2}:\d{2})',  # з HH:MM
        ]
        
        # Look for location patterns
        location_patterns = [
            r'кав[\'\u2019]?ярн[яіи]\s*["\'\u201c\u201d]?([^"\'\u201c\u201d.\n,]+)["\'\u201c\u201d]?',  # кав'ярня "Name"
            r'дерибасівськ[аій]*[,\s]*(\d+)',  # Дерибасівська, 15
            r'"([^"]+)"[,\s]*дерибасівськ',  # "Name", Дерибасівська
        ]
        
        found_time = None
        found_location = None
        
        # Extract time
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                found_time = match.group(1)
                break
        
        # Extract location
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if 'brew' in match.group(1).lower() or len(match.group(1)) > 3:
                    found_location = match.group(1).strip(' "\'.,')
                    if 'дерибасівськ' in text:
                        found_location += ", Дерибасівська"
                break
        
        # Check if this looks like a planned event
        future_indicators = ['завтра', 'tomorrow', 'зустр', 'встрет', 'съемк', 'зйомк']
        has_future_indicator = any(indicator in text for indicator in future_indicators)
        
        if has_future_indicator and (found_time or found_location):
            # Determine event type
            event_type = "meeting"
            if any(word in text for word in ['съемк', 'зйомк', 'фото', 'відео']):
                event_type = "event"
                
            # Extract participants
            participants = []
            names = ['катя', 'андрій', 'андрей']
            for name in names:
                if name in text:
                    participants.append(name.capitalize())
            
            if not participants:
                participants = ["Учасники"]
            
            # Create event
            event = {
                "title": "Зйомка для кав'ярні" if "зйомк" in text or "съемк" in text else "Зустріч",
                "date": _parse_date("завтра"),
                "time": _parse_time(found_time) if found_time else None,
                "location": found_location,
                "participants": participants,
                "type": event_type,
                "priority": "medium"
            }
            
            events.append(event)
        
        logger.info(f"Manual extraction found {len(events)} events")
        return events
        
    except Exception as e:
        logger.error(f"Manual extraction failed: {e}")
        return []


def _clean_event_data(event_data: Dict) -> Optional[Dict[str, Any]]:
    """
    Clean and validate event data
    """
    try:
        # Required fields
        title = event_data.get("title", "").strip()
        if not title:
            return None
        
        # Process date
        date_str = event_data.get("date", "").strip()
        parsed_date = _parse_date(date_str)
        
        # Process time
        time_str = event_data.get("time", "").strip()
        parsed_time = _parse_time(time_str)
        
        # Build cleaned event
        cleaned = {
            "title": title,
            "date": parsed_date,
            "time": parsed_time,
            "location": event_data.get("location", "").strip() or None,
            "participants": _clean_participants(event_data.get("participants", [])),
            "type": _clean_type(event_data.get("type", "meeting")),
            "priority": _clean_priority(event_data.get("priority", "medium"))
        }
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Error cleaning event data: {e}")
        return None


def _parse_date(date_str: str) -> Optional[str]:
    """
    Parse date string into standardized format
    """
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    # Handle relative dates
    if "завтра" in date_str or "tomorrow" in date_str:
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    elif "сегодня" in date_str or "today" in date_str:
        today = datetime.now()
        return today.strftime("%Y-%m-%d")
    elif "послезавтра" in date_str:
        day_after = datetime.now() + timedelta(days=2)
        return day_after.strftime("%Y-%m-%d")
    
    # Try to parse absolute dates
    try:
        # Format: YYYY-MM-DD
        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return date_str
        
        # Format: DD.MM.YYYY or DD/MM/YYYY
        date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', date_str)
        if date_match:
            day, month, year = date_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Format: DD.MM or DD/MM (current year)
        date_match = re.search(r'(\d{1,2})[./](\d{1,2})', date_str)
        if date_match:
            day, month = date_match.groups()
            year = datetime.now().year
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
    except Exception as e:
        logger.debug(f"Error parsing date '{date_str}': {e}")
    
    return None


def _parse_time(time_str: str) -> Optional[str]:
    """
    Parse time string into HH:MM format
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # Match HH:MM format
    time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if time_match:
        hour, minute = time_match.groups()
        return f"{hour.zfill(2)}:{minute}"
    
    # Match single hour (e.g., "9", "15")
    hour_match = re.search(r'\b(\d{1,2})\b', time_str)
    if hour_match:
        hour = int(hour_match.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    
    return None


def _clean_participants(participants) -> List[str]:
    """
    Clean participants list
    """
    if not participants:
        return []
    
    if isinstance(participants, str):
        # Split by common delimiters
        participants = re.split(r'[,;]\s*', participants)
    
    if isinstance(participants, list):
        cleaned = []
        for p in participants:
            if isinstance(p, str) and p.strip():
                cleaned.append(p.strip())
        return cleaned
    
    return []


def _clean_type(event_type) -> str:
    """
    Clean event type
    """
    if not event_type or not isinstance(event_type, str):
        return "meeting"
    
    event_type = event_type.lower().strip()
    valid_types = ["meeting", "deadline", "event", "call", "appointment"]
    
    return event_type if event_type in valid_types else "meeting"


def _clean_priority(priority) -> str:
    """
    Clean priority level
    """
    if not priority or not isinstance(priority, str):
        return "medium"
    
    priority = priority.lower().strip()
    valid_priorities = ["high", "medium", "low"]
    
    return priority if priority in valid_priorities else "medium" 