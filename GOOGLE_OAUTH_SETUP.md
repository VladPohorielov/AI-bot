# Налаштування Google OAuth для Calendar API

## Крок 1: Створити Google Cloud проект

1. Відкрити [Google Cloud Console](https://console.cloud.google.com/)
2. Створити новий проект або вибрати існуючий
3. Активувати Google Calendar API:
   - Перейти в **APIs & Services** > **Library**
   - Знайти та активувати **Google Calendar API**

## Крок 2: Створити OAuth 2.0 credentials

1. Перейти в **APIs & Services** > **Credentials**
2. Натиснути **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Якщо треба, налаштувати OAuth consent screen:
   - User Type: **External** (для тестування)
   - App name: назва вашого бота
   - User support email: ваш email
   - Developer contact: ваш email
4. Створити OAuth client ID:
   - Application type: **Web application**
   - Name: `Telegram Calendar Bot`
   - Authorized redirect URIs:
     - `http://localhost:8080/oauth/callback`
     - `http://127.0.0.1:8080/oauth/callback`

## Крок 3: Отримати credentials

Після створення OAuth client ID ви отримаєте:

- **Client ID** (наприклад: `123456789-abcdefg.apps.googleusercontent.com`)
- **Client Secret** (наприклад: `GOCSPX-1234567890abcdefghij`)

## Крок 4: Додати тестових користувачів (ВАЖЛИВО!)

🚨 **Обов'язково для External застосунків:**

1. Перейти в **APIs & Services** > **OAuth consent screen**
2. Знайти секцію **"Test users"**
3. Натиснути **"+ ADD USERS"**
4. Додати ваш email (vladpog2015@gmail.com)
5. Натиснути **"SAVE"**

Без цього кроку буде помилка **403: access_denied**!

## Крок 5: Оновити .env файл

Замінити у файлі `.env`:

```env
GOOGLE_CLIENT_ID=ваш_реальний_client_id
GOOGLE_CLIENT_SECRET=ваш_реальний_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/callback
```

## Крок 6: Запустити OAuth сервер

Перед підключенням календаря потрібно запустити OAuth callback сервер:

```bash
python services/oauth_server.py
```

## Крок 7: Тестування

1. Запустити бота
2. Використати команду `/settings` → **Підключити календар**
3. Перейти за посиланням авторизації
4. Дозволити доступ до календаря
5. Повернутись до бота

## Можливі проблеми

### 401: invalid_client

- Перевірити правильність Client ID та Client Secret
- Переконатися, що redirect URI точно співпадає
- Перевірити, що Google Calendar API активоване

### 403: access_denied

- **Додати ваш email у Test users** в OAuth consent screen
- Або опублікувати застосунок (PUBLISH APP)
- Переконатися, що використовується правильний Google аккаунт

### redirect_uri_mismatch

- Перевірити точну відповідність redirect URI в Google Console та .env файлі

## Для продакшена

Коли застосунок готовий до продакшена:
1. Налаштувати домен замість localhost
2. Опублікувати застосунок у Google Console
3. Пройти процес верифікації Google (якщо потрібно)
