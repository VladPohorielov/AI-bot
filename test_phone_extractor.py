"""
Test script for phone extractor service
"""
from services.phone_extractor import phone_extractor

def test_phone_extraction():
    """Test phone number extraction from various text samples"""
    
    test_texts = [
        # Ukrainian formats
        "Мій номер +380 67 123 45 67",
        "Зателефонуй на 067-123-45-67 вечором",
        "Контакт: 380671234567",
        "Номер для зв'язку: 0671234567",
        
        # Multiple phones
        "У мене два номери: +380 67 123 45 67 та +380 50 987 65 43",
        
        # With other info
        "Привіт! Завтра о 15:00 зустрічаємось біля ТЦ Глобус. Мій номер +380 67 123 45 67 для зв'язку. Адреса: вул. Хрещатик 1.",
        
        # Kyiv landline
        "Офіс: +380 44 123 45 67",
        "Зателефонуй в офіс 044-123-45-67",
        
        # International
        "My US number is +1 555 123 4567",
        "UK office: +44 20 1234 5678",
    ]
    
    print("=== ТЕСТУВАННЯ PHONE EXTRACTOR ===\n")
    
    for i, text in enumerate(test_texts, 1):
        print(f"ТЕСТ {i}:")
        print(f"Текст: {text}")
        
        phones = phone_extractor.extract_phones(text)
        
        if phones:
            print("Знайдені телефони:")
            for phone in phones:
                print(f"  • {phone.formatted} ({phone.country}, {phone.type}, впевненість: {phone.confidence:.2f})")
            
            print("\nВідображення для бота:")
            display = phone_extractor.format_for_display(phones)
            print(display)
        else:
            print("❌ Телефони не знайдені")
        
        print("-" * 50)

if __name__ == "__main__":
    test_phone_extraction() 