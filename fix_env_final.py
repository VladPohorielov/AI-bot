#!/usr/bin/env python3
"""
Fix .env file with proper Fernet ENCRYPTION_KEY
"""

import os
from cryptography.fernet import Fernet

def fix_env_file():
    """Fix .env file with proper Fernet encryption key"""
    
    # Generate proper Fernet key (base64 encoded)
    encryption_key = Fernet.generate_key().decode()
    print(f"✅ Generated Fernet key: {encryption_key}")
    
    # Read current .env file
    env_path = ".env"
    if not os.path.exists(env_path):
        print("❌ .env file not found! Run setup_env.py first")
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace any existing encryption key
        lines = content.split('\n')
        new_lines = []
        encryption_found = False
        
        for line in lines:
            if line.startswith('ENCRYPTION_KEY='):
                new_lines.append(f'ENCRYPTION_KEY={encryption_key}')
                encryption_found = True
                print("✅ Replaced existing ENCRYPTION_KEY")
            else:
                new_lines.append(line)
        
        if not encryption_found:
            new_lines.append(f'ENCRYPTION_KEY={encryption_key}')
            print("✅ Added new ENCRYPTION_KEY")
        
        # Write back to file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        print("\n✅ .env file updated with proper Fernet ENCRYPTION_KEY!")
        print("\n📋 STATUS:")
        print("🔐 ENCRYPTION_KEY: ✅ Fixed")
        print("🤖 TELEGRAM_BOT_TOKEN: Check .env file")
        print("🧠 OPENAI_API_KEY: Check .env file (optional)")
        print("\n🚀 Ready to run: python main_bot.py")
            
    except Exception as e:
        print(f"❌ Error fixing .env file: {e}")

if __name__ == "__main__":
    fix_env_file() 