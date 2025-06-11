#!/usr/bin/env python3
"""
Setup script for creating .env file with API keys
Run this script to generate .env template
"""

import os

def create_env_file():
    env_content = """# ==============================================
# TELEGRAM BOT CONFIGURATION
# ==============================================
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# ==============================================
# OPENAI API CONFIGURATION
# ==============================================
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# ==============================================
# GOOGLE CALENDAR OAUTH CONFIGURATION
# ==============================================
# Get credentials from: https://console.cloud.google.com/
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/callback

# ==============================================
# SECURITY CONFIGURATION
# ==============================================
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
ENCRYPTION_KEY=your_encryption_key_here
"""

    env_path = ".env"
    
    if os.path.exists(env_path):
        print("⚠️  .env файл уже існує!")
        choice = input("Перезаписати? (y/n): ").lower()
        if choice != 'y':
            print("❌ Операція скасована")
            return
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print("✅ .env файл створено успішно!")
        print("\n📋 ІНСТРУКЦІЇ:")
        print("1. Отримайте OpenAI API ключ: https://platform.openai.com/api-keys")
        print("2. Замініть 'your_openai_api_key_here' на справжній ключ")
        print("3. Також додайте ваш Telegram bot token")
        print("4. Перезапустіть бота")
        
    except Exception as e:
        print(f"❌ Помилка створення .env файлу: {e}")

if __name__ == "__main__":
    create_env_file() 