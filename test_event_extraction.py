#!/usr/bin/env python3
"""
Test script to verify event extraction functionality
"""
import asyncio
import sys
import os
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from services.event_extraction import extract_events_from_text

async def test_event_extraction():
    print("🧪 Testing event extraction service...")
    
    # Test conversation similar to the screenshot
    test_text = """
    Катя: Привіт! Ти завтра вільний на коротку зйомку в Одесі? Потрібен оператор на кілька годин.
    
    Андрій: Привіт! Так, завтра якраз маю вікно. Що саме планується знімати?
    
    Катя: Робимо промо для кав'ярні на Дерибасівській. Потрібно буде відзняти інтер'єр, процес приготування кави + кілька кадрів з моделями на вулиці.
    
    Андрій: Звучить цікаво. Скільки орієнтовно по часу?
    
    Катя: Десь 3-4 години. починаємо о 10:00. Потрібен стабілізатор + можливо пару кадрів з дрона, якщо маєш.
    
    Андрій: Стаб є, дрон теж можу взяти. По оплаті?
    
    Катя: 1500 грн за зйомку, оплата одразу після.
    
    Андрій: Ок, підходить. Адресу скинеш?
    
    Катя: Так, кав'ярня "Brew&Go", Дерибасівська, 15. Я буду на місці з 9:45, чекатиму біля входу.
    
    Андрій: Супер, до зустрічі тоді завтра!
    
    Катя: До зустрічі! Дякую 🙏
    """
    
    try:
        print("🔍 Extracting events...")
        events = await extract_events_from_text(test_text)
        
        print(f"✅ Events extracted: {len(events)}")
        
        if events:
            for i, event in enumerate(events, 1):
                print(f"\n📅 Event {i}:")
                print(f"  Title: {event.get('title')}")
                print(f"  Date: {event.get('date')}")
                print(f"  Time: {event.get('time')}")
                print(f"  Location: {event.get('location')}")
                print(f"  Participants: {event.get('participants')}")
                print(f"  Type: {event.get('type')}")
                print(f"  Priority: {event.get('priority')}")
        else:
            print("❌ No events found")
            
        return len(events) > 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_event_extraction())
    sys.exit(0 if success else 1) 