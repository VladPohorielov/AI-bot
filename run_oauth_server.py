#!/usr/bin/env python3
"""
Script to run OAuth callback server for Google Calendar integration
"""
import asyncio
import sys
from services.oauth_server import main

if __name__ == '__main__':
    print("🚀 Запуск OAuth callback сервера для Google Calendar...")
    print("📍 Переконайтеся, що у .env файлі налаштовані:")
    print("   - GOOGLE_CLIENT_ID")
    print("   - GOOGLE_CLIENT_SECRET") 
    print("   - GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/callback")
    print("")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ OAuth сервер зупинено")
    except Exception as e:
        print(f"\n❌ Помилка запуску сервера: {e}")
        sys.exit(1) 