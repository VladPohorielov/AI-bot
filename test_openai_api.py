#!/usr/bin/env python3
"""
Test OpenAI API connection and key validity
"""

import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

async def test_openai_api():
    """Test OpenAI API connection"""
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    print("🔍 ПЕРЕВІРКА OPENAI API...")
    print(f"API ключ завантажений: {'✅' if api_key else '❌'}")
    
    if not api_key:
        print("\n❌ OPENAI_API_KEY не знайдено в .env файлі!")
        print("\n📋 ЩО РОБИТИ:")
        print("1. Створіть .env файл: python setup_env.py")
        print("2. Отримайте API ключ: https://platform.openai.com/api-keys")
        print("3. Додайте ключ до .env: OPENAI_API_KEY=your_key_here")
        return
    
    if api_key == "your_openai_api_key_here":
        print("\n⚠️  Ви використовуєте placeholder ключ!")
        print("Замініть 'your_openai_api_key_here' на справжній ключ")
        return
    
    print(f"API ключ (перші 10 символів): {api_key[:10]}...")
    
    try:
        client = AsyncOpenAI(api_key=api_key)
        print("\n🧪 Тестування API...")
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Привіт! Це тест. Відповідь одним словом: працює"}
            ],
            max_tokens=10,
            timeout=10.0
        )
        
        result = response.choices[0].message.content
        print(f"✅ API ПРАЦЮЄ! Відповідь: {result}")
        print("\n🎉 ChatGPT готовий до використання в боті!")
        
    except Exception as e:
        print(f"\n❌ ПОМИЛКА API: {e}")
        print("\n🔧 МОЖЛИВІ ПРИЧИНИ:")
        print("• Неправильний API ключ")
        print("• Недостатньо коштів на рахунку OpenAI") 
        print("• Проблеми з мережею")
        print("• API ключ заблокований")
        
        print("\n📋 ЩО РОБИТИ:")
        print("1. Перевірте ключ на: https://platform.openai.com/api-keys")
        print("2. Перевірте баланс: https://platform.openai.com/usage")
        print("3. Створіть новий ключ якщо потрібно")

if __name__ == "__main__":
    asyncio.run(test_openai_api()) 