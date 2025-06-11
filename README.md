# 🤖 Briefly - AI Telegram Bot

**Briefly** — персональний AI-помічник для Telegram, який допомагає обробляти голосові повідомлення, створювати резюме переписок та керувати подіями в календарі.

## 🚀 Основні можливості

- 🗣️ **Транскрибація голосових повідомлень** - перетворення аудіо у текст за допомогою Whisper
- 📝 **Створення резюме** - інтелектуальне згортання тексту та переписок
- 📅 **Управління подіями** - витягування подій з переписок та додавання у Google Calendar
- 🌐 **Мультимовність** - підтримка української, російської, англійської та інших мов
- ⚙️ **Налаштування** - персоналізація стилів резюме та мовних налаштувань
- 📱 **Зручний інтерфейс** - інтуїтивне керування через Telegram

## 🛠️ Технології

- **Python 3.11+**
- **aiogram 3.10** - Telegram Bot API
- **OpenAI Whisper** - транскрибація аудіо
- **OpenAI GPT** - створення резюме та аналіз тексту
- **Google Calendar API** - інтеграція з календарем
- **SQLAlchemy + SQLite** - база даних
- **aiohttp** - OAuth сервер

## 📋 Команди бота

- `/start` - Запустити Briefly
- `/help` - Довідка по використанню
- `/settings` - Налаштування бота
- `/capture_chat` - Почати захоплення переписки
- `/end_capture` - Завершити захоплення
- `/my_sessions` - Історія сесій
- `/connect_calendar` - Підключити Google Calendar
- `/cancel` - Скасувати поточну операцію

## ⚡ Швидкий старт

### 1. Клонування репозиторію

```bash
git clone https://github.com/VladPohorielov/AI-bot.git
cd AI-bot
```

### 2. Встановлення залежностей

```bash
pip install -r requirements.txt
```

### 3. Налаштування змінних середовища

Створіть файл `.env` та додайте необхідні ключі:

```env
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# Google Calendar OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://ai-bot-tau-seven.vercel.app/oauth_callback.html

# Security
ENCRYPTION_KEY=your_32_byte_encryption_key
```

### 4. Налаштування Google OAuth

Дивіться детальну інструкцію у файлі [GOOGLE_OAUTH_SETUP.md](./GOOGLE_OAUTH_SETUP.md)

### 5. Запуск бота

```bash
# Запуск OAuth сервера (в окремому терміналі)
python run_oauth_server.py

# Запуск бота
python main_bot.py
```

## 📁 Структура проекту

```
AI-bot/
├── handlers/                 # Обробники команд та повідомлень
│   ├── enhanced_capture_handlers.py
│   ├── settings_handlers.py
│   ├── voice_audio_handler.py
│   └── ...
├── services/                 # Бізнес-логіка та сервіси
│   ├── analysis.py          # Аналіз тексту та витягування подій
│   ├── google_calendar.py   # Google Calendar API
│   ├── google_oauth.py      # OAuth авторизація
│   ├── enhanced_capture_flow.py # Покращений процес захоплення
│   ├── phone_extractor.py   # Витягування номерів телефонів
│   └── ...
├── states/                   # FSM стани
├── keyboards/               # Telegram клавіатури
├── tests/                   # Тести
├── config.py               # Конфігурація
├── main_bot.py            # Основний файл бота
└── requirements.txt       # Залежності
```

## 🔧 Налаштування для розробки

### Тестування

```bash
# Тест транскрибації
python test_audio.py

# Тест витягування подій
python test_event_extraction.py

# Тест покращеного процесу захоплення
python test_enhanced_flow.py

# Тест витягування телефонів
python test_phone_extractor.py
```

### Налаштування середовища

```bash
# Автоматичне налаштування .env
python setup_env.py
```

## 🌟 Нові функції

### Enhanced Capture Flow

- Покращений процес захоплення переписок
- Мануальний перегляд та редагування витягнутих подій
- Інтеграція витягування номерів телефонів
- FSM для управління складними робочими процесами

### Phone Extractor

- Розпізнавання українських номерів телефонів (+380, 067, 044)
- Підтримка міжнародних форматів
- Скоринг впевненості та типізація телефонів
- Дедуплікація та форматування для ботів

## 📄 Документація

- [GOOGLE_OAUTH_SETUP.md](./GOOGLE_OAUTH_SETUP.md) - Налаштування Google OAuth
- [ENHANCED_PROGRESS.md](./ENHANCED_PROGRESS.md) - Деталі покращень
- [FIXES_SUMMARY.md](./FIXES_SUMMARY.md) - Історія виправлень
- [README_FFMPEG_FIX.md](./README_FFMPEG_FIX.md) - Виправлення FFmpeg

## 🤝 Внесок у проект

1. Зробіть форк репозиторію
2. Створіть гілку для нової функції (`git checkout -b feature/amazing-feature`)
3. Закомітьте зміни (`git commit -m 'Add amazing feature'`)
4. Запушіть у гілку (`git push origin feature/amazing-feature`)
5. Створіть Pull Request

## 📝 Ліцензія

Цей проект розповсюджується під ліцензією MIT. Дивіться файл [LICENSE](LICENSE) для деталей.

## 👨‍💻 Автор

**Vlad Pohorielov** - [GitHub](https://github.com/VladPohorielov)

## 📞 Підтримка

Якщо у вас виникли питання або проблеми, створіть [issue](https://github.com/VladPohorielov/AI-bot/issues) у репозиторії.
