#!/usr/bin/env python3
"""
Fix .env file with proper ENCRYPTION_KEY
"""

import os
import secrets

def fix_env_file():
    """Fix .env file with proper encryption key"""
    
    # Generate proper encryption key
    encryption_key = secrets.token_urlsafe(32)
    print(f"✅ Generated encryption key: {encryption_key}")
    
    # Read current .env file
    env_path = ".env"
    if not os.path.exists(env_path):
        print("❌ .env file not found! Run setup_env.py first")
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the placeholder encryption key
        if "your_encryption_key_here" in content:
            content = content.replace("your_encryption_key_here", encryption_key)
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ .env file updated with proper ENCRYPTION_KEY!")
            print("\n📋 NEXT STEPS:")
            print("1. Add your TELEGRAM_BOT_TOKEN to .env")
            print("2. Add your OPENAI_API_KEY to .env (optional)")
            print("3. Run: python main_bot.py")
        else:
            print("⚠️  ENCRYPTION_KEY already set or file format changed")
            print("Current content preview:")
            print(content[:500] + "..." if len(content) > 500 else content)
            
    except Exception as e:
        print(f"❌ Error fixing .env file: {e}")

if __name__ == "__main__":
    fix_env_file() 