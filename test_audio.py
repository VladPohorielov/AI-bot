#!/usr/bin/env python3
"""
Скрипт діагностики аудіо обробки для Briefly бота
"""

import os
import sys
import subprocess
import shutil
import tempfile

def test_ffmpeg():
    """Тест доступності FFmpeg"""
    print("🔍 Перевірка FFmpeg...")
    
    # Метод 1: через shutil.which
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        print(f"✅ FFmpeg знайдено: {ffmpeg_path}")
    else:
        print("❌ FFmpeg не знайдено через shutil.which")
    
    # Метод 2: пряма команда
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg працює: {version_line}")
            return True
        else:
            print(f"❌ FFmpeg повернув код: {result.returncode}")
            print(f"Stderr: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg не знайдено в PATH")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg не відповідає (timeout)")
        return False
    except Exception as e:
        print(f"❌ Помилка запуску FFmpeg: {e}")
        return False


def test_whisper():
    """Тест Whisper"""
    print("\n🔍 Перевірка Whisper...")
    
    try:
        import whisper
        print("✅ Модуль whisper імпортовано")
        
        # Тест завантаження моделі
        print("📥 Завантажуємо модель...")
        model = whisper.load_model("base")
        print("✅ Модель завантажена")
        
        return True
        
    except ImportError as e:
        print(f"❌ Не вдається імпортувати whisper: {e}")
        return False
    except Exception as e:
        print(f"❌ Помилка завантаження моделі: {e}")
        return False


def test_dependencies():
    """Тест залежностей"""
    print("\n🔍 Перевірка залежностей...")
    
    dependencies = [
        'whisper',
        'torch',
        'aiogram',
        'openai',
        'google-auth',
        'google-auth-oauthlib',
        'google-auth-httplib2',
        'google-api-python-client',
        'sqlalchemy',
        'aiosqlite',
        'python-dotenv',
        'cryptography',
        'ffmpeg-python'
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep}")
            missing.append(dep)
    
    if missing:
        print(f"\n⚠️ Відсутні залежності: {', '.join(missing)}")
        print("Встановіть їх: pip install " + " ".join(missing))
        return False
    else:
        print("\n✅ Всі залежності встановлені")
        return True


def test_audio_conversion():
    """Тест конвертації аудіо"""
    print("\n🔍 Тест конвертації аудіо...")
    
    if not test_ffmpeg():
        print("❌ FFmpeg недоступний, пропускаємо тест конвертації")
        return False
    
    temp_ogg_path = None
    temp_wav_path = None
    
    try:
        # Створюємо тестовий OGG файл (імітація голосового повідомлення)
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
            temp_ogg_path = temp_ogg.name
            
        # Створюємо тестовий WAV файл для конвертації
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        # Генеруємо 1 секунду тиші як тестовий аудіо
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=duration=1',
            '-y', temp_ogg_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Тестовий OGG файл створено")
            
            # Тест конвертації OGG -> WAV
            cmd2 = ['ffmpeg', '-i', temp_ogg_path, '-y', temp_wav_path]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
            
            if result2.returncode == 0:
                print("✅ Конвертація OGG -> WAV працює")
                return True
            else:
                print(f"❌ Помилка конвертації: {result2.stderr}")
                return False
        else:
            print(f"❌ Помилка створення тестового файлу: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Помилка тесту конвертації: {e}")
        return False
    finally:
        # Очищуємо тимчасові файли
        for path in [temp_ogg_path, temp_wav_path]:
            if path and os.path.exists(path):
                os.unlink(path)


def main():
    """Головна функція діагностики"""
    print("🤖 Briefly Bot - Діагностика аудіо обробки")
    print("=" * 50)
    
    tests = [
        ("Python версія", lambda: print(f"Python {sys.version}")),
        ("FFmpeg", test_ffmpeg),
        ("Залежності", test_dependencies),
        ("Whisper", test_whisper),
        ("Конвертація аудіо", test_audio_conversion)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            if test_func():
                results.append((name, True))
            else:
                results.append((name, False))
        except Exception as e:
            print(f"❌ Помилка в тесті {name}: {e}")
            results.append((name, False))
    
    # Підсумок
    print(f"\n{'='*50}")
    print("📊 ПІДСУМОК ДІАГНОСТИКИ:")
    print("=" * 50)
    
    passed = 0
    for name, result in results:
        status = "✅ ПРОЙДЕНО" if result else "❌ ПРОВАЛЕНО"
        print(f"{name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nПройдено: {passed}/{len(results)} тестів")
    
    if passed == len(results):
        print("🎉 Всі тести пройшли! Бот повинен працювати правильно.")
    else:
        print("⚠️ Є проблеми. Дивіться деталі вище.")
        
        # Рекомендації
        print("\n💡 РЕКОМЕНДАЦІЇ:")
        for name, result in results:
            if not result:
                if "FFmpeg" in name:
                    print("- Встановіть FFmpeg: winget install ffmpeg")
                    print("- Перезапустіть PowerShell після встановлення")
                elif "Залежності" in name:
                    print("- Встановіть відсутні пакети: pip install -r requirements.txt")
                elif "Whisper" in name:
                    print("- Перевірте встановлення: pip install openai-whisper")


if __name__ == "__main__":
    main() 