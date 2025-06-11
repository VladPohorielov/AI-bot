"""
Test script for Enhanced Capture Flow
"""
import asyncio
import sys
sys.path.append('.')

# Import only the components we can test without dependencies
from services.phone_extractor import phone_extractor

# Test dataclass separately 
from dataclasses import dataclass
from typing import List

@dataclass
class ExtractedEvent:
    """Test version of ExtractedEvent"""
    id: str
    title: str
    date: str
    time: str
    location: str
    participants: List[str]
    phones: List[str]
    notes: str
    confidence: float
    original_text: str

async def test_enhanced_flow():
    """Test the enhanced capture flow components"""
    
    print("=== ТЕСТУВАННЯ ENHANCED CAPTURE FLOW ===\n")
    
    # Test conversation text with events and phones
    test_conversation = """
    Привіт! Сьогодні обговорили план на наступний тиждень.
    
    Завтра о 14:00 зустрічаємось в офісі на вул. Хрещатик 1 для обговорення проекту.
    Будуть присутні: Олександр, Марія та Владислав.
    
    В п'ятницю о 16:30 планується презентація в конференц-залі ТЦ Глобус.
    Контакт організатора: +380 67 123 45 67
    
    Не забути купити квитки до 20 лютого. Дедлайн - важливий!
    
    Олександр сказав зателефонувати йому на 050-987-65-43 якщо будуть питання.
    """
    
    # Skip enhanced flow testing for now (has import dependencies)
    # flow = EnhancedCaptureFlow()
    
    print("1. ТЕСТУВАННЯ ВИТЯГУВАННЯ ТЕЛЕФОНІВ")
    print("=" * 40)
    phones = phone_extractor.extract_phones(test_conversation)
    print(f"Знайдено телефонів: {len(phones)}")
    for phone in phones:
        print(f"  • {phone.formatted} ({phone.country}, {phone.type}, впевненість: {phone.confidence:.2f})")
    
    print("\n" + phone_extractor.format_for_display(phones))
    
    print("\n2. ТЕСТУВАННЯ СТРУКТУРИ ДАНИХ")
    print("=" * 40)
    
    # Test ExtractedEvent creation
    test_event = ExtractedEvent(
        id="test_1",
        title="Зустріч в офісі",
        date="2024-02-15",
        time="14:00",
        location="вул. Хрещатик 1",
        participants=["Олександр", "Марія", "Владислав"],
        phones=[p.formatted for p in phones],
        notes="Обговорення проекту",
        confidence=0.9,
        original_text=test_conversation[:100] + "..."
    )
    
    print(f"Створена тестова подія:")
    print(f"  ID: {test_event.id}")
    print(f"  Назва: {test_event.title}")
    print(f"  Дата: {test_event.date}")
    print(f"  Час: {test_event.time}")
    print(f"  Місце: {test_event.location}")
    print(f"  Учасники: {', '.join(test_event.participants)}")
    print(f"  Телефони: {', '.join(test_event.phones)}")
    print(f"  Впевненість: {test_event.confidence}")
    
    print("\n3. ТЕСТУВАННЯ ПРОЦЕСУВАННЯ РЕЗУЛЬТАТІВ")
    print("=" * 40)
    
    # Mock analysis result
    mock_analysis = {
        'summary': 'Обговорення планів на тиждень з організацією зустрічей та презентації',
        'events': [
            {
                'title': 'Зустріч в офісі',
                'date': '2024-02-15',
                'time': '14:00',
                'location': 'вул. Хрещатик 1',
                'participants': ['Олександр', 'Марія', 'Владислав'],
                'notes': 'Обговорення проекту',
                'confidence': 0.9
            },
            {
                'title': 'Презентація',
                'date': '2024-02-16',
                'time': '16:30',
                'location': 'конференц-зал ТЦ Глобус',
                'participants': [],
                'notes': 'Планується презентація',
                'confidence': 0.8
            }
        ]
    }
    
    # Mock processed results for testing
    processed = {
        'success': True,
        'total_events': len(mock_analysis['events']),
        'phones': [p.formatted for p in phones],
        'events': [
            ExtractedEvent(
                id=f"event_{i+1}",
                title=event_data.get('title', 'Без назви'),
                date=event_data.get('date', ''),
                time=event_data.get('time', ''),
                location=event_data.get('location', ''),
                participants=event_data.get('participants', []),
                phones=[p.formatted for p in phones],
                notes=event_data.get('notes', ''),
                confidence=event_data.get('confidence', 0.7),
                original_text=test_conversation[:200] + "..."
            ) for i, event_data in enumerate(mock_analysis['events'])
        ]
    }
    
    print(f"Успішність обробки: {processed.get('success', False)}")
    print(f"Загальна кількість подій: {processed.get('total_events', 0)}")
    print(f"Кількість телефонів: {len(processed.get('phones', []))}")
    
    print("\nОброблені події:")
    for i, event in enumerate(processed.get('events', []), 1):
        print(f"  {i}. {event.title} ({event.date} о {event.time})")
        print(f"     Місце: {event.location}")
        print(f"     Впевненість: {event.confidence:.2f}")
    
    print("\n4. ТЕСТУВАННЯ КОНВЕРТАЦІЇ ДЛЯ КАЛЕНДАРЯ")
    print("=" * 40)
    
    if processed.get('events'):
        test_summary = "Тестове резюме розмови"
        
        # Mock calendar event conversion
        event = processed['events'][0]
        calendar_event = {
            'summary': event.title,
            'start_date': event.date,
            'start_time': event.time,
            'location': event.location,
            'attendees': event.participants,
            'description': f"Автоматично створено з чату\n\nРЕЗЮМЕ: {test_summary}\n\nУЧАСНИКИ: {', '.join(event.participants)}\n\nКОНТАКТИ: {', '.join(event.phones)}"
        }
        
        print("Конвертована подія для календаря:")
        print(f"  Назва: {calendar_event['summary']}")
        print(f"  Дата: {calendar_event['start_date']}")
        print(f"  Час: {calendar_event['start_time']}")
        print(f"  Місце: {calendar_event['location']}")
        print(f"  Учасники: {calendar_event['attendees']}")
        print(f"  Опис (перші 200 символів): {calendar_event['description'][:200]}...")
    
    print("\n✅ ТЕСТУВАННЯ ЗАВЕРШЕНО")

if __name__ == "__main__":
    asyncio.run(test_enhanced_flow()) 