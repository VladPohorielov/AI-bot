# 🚀 Vercel Deployment для OAuth Callback

Цей файл пояснює як задеплоїти OAuth callback endpoint на Vercel для обробки Google Calendar авторизації.

## 🏗️ Структура файлів

```
/
├── api/
│   └── oauth_callback.py    # Vercel serverless function
├── vercel.json             # Конфігурація Vercel
├── requirements.txt        # Python залежності
└── README.md
```

## ⚙️ Налаштування Vercel

### 1. Підключення до GitHub

1. Відкрити [vercel.com](https://vercel.com)
2. Зареєструватись/увійти через GitHub
3. Імпортувати репозиторій: `https://github.com/VladPohorielov/AI-bot`

### 2. Конфігурація Environment Variables

У Vercel Dashboard → Settings → Environment Variables додати:

```env
GOOGLE_CLIENT_ID=ваш_google_client_id
GOOGLE_CLIENT_SECRET=ваш_google_client_secret
ENCRYPTION_KEY=ваш_32_byte_encryption_key
```

### 3. Оновлення Google OAuth

У [Google Cloud Console](https://console.cloud.google.com/):

1. **APIs & Services** → **Credentials**
2. Редагувати OAuth 2.0 Client ID
3. **Authorized redirect URIs** додати:
   ```
   https://your-app-name.vercel.app/api/oauth_callback
   https://your-app-name.vercel.app/oauth/callback
   ```

## 🔗 URL Structure

- **Production**: `https://your-app.vercel.app/api/oauth_callback`
- **Local Dev**: `http://localhost:8080/oauth/callback`

## 📋 Endpoint Features

✅ **Обробка OAuth параметрів**: `code`, `state`, `error`  
✅ **Валідація помилок** з зрозумілими повідомленнями  
✅ **Успішна сторінка** з інструкціями для користувача  
✅ **Автозакриття вікна** через 5 секунд  
✅ **Копіювання коду** у буфер обміну  
✅ **Підтримка Flask** для локальної розробки

## 🧪 Тестування

### Локально

```bash
cd api
python oauth_callback.py
```

Endpoint доступний на: `http://localhost:8080/oauth/callback`

### Production

Після deployment на Vercel:

```
https://your-app.vercel.app/api/oauth_callback?code=test&state=test
```

## 🔧 Troubleshooting

### 404 NOT_FOUND

- ✅ Перевірити що файл `api/oauth_callback.py` існує
- ✅ Переконатись що `vercel.json` правильно налаштований
- ✅ Перевірити що зміни запушені в GitHub

### 500 Internal Error

- ✅ Перевірити Environment Variables у Vercel
- ✅ Переглянути logs у Vercel Dashboard → Functions

### Redirect URI Mismatch

- ✅ Оновити redirect URIs у Google Cloud Console
- ✅ Використовувати точний URL з Vercel Dashboard

## 📝 Наступні кроки

1. ✅ Створити структуру файлів
2. ✅ Закомітити та запушити в GitHub
3. 🔄 Підключити до Vercel
4. 🔄 Налаштувати Environment Variables
5. 🔄 Оновити Google OAuth redirect URIs
6. 🔄 Протестувати OAuth flow
