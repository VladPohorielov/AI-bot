# Виправлення проблеми з FFmpeg для Briefly бота

## Проблема

Бот не може обробляти голосові повідомлення через відсутність FFmpeg.

## Рішення 1: Встановлення FFmpeg (Рекомендовано)

### Крок 1: Встановіть FFmpeg через winget

```powershell
winget install "FFmpeg (Essentials Build)"
```

### Крок 2: Перезапустіть PowerShell ПОВНІСТЮ

- Закрийте всі вікна PowerShell/Command Prompt
- Відкрийте нове вікно PowerShell як Адміністратор

### Крок 3: Перевірте встановлення

```powershell
ffmpeg -version
```

### Крок 4: Якщо не працює, додайте PATH вручну

```powershell
# Знайдіть, де встановлено FFmpeg
Get-ChildItem C:\Users\$env:USERNAME\AppData\Local\Microsoft\WinGet\Packages\ -Recurse -Name "ffmpeg.exe" | Select-Object -First 1

# Або перевірте стандартні шляхи:
Test-Path "C:\tools\ffmpeg\bin\ffmpeg.exe"
Test-Path "C:\ffmpeg\bin\ffmpeg.exe"

# Додайте до PATH (замініть шлях на актуальний):
$env:PATH += ";C:\tools\ffmpeg\bin"

# Або встановіть постійно:
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\tools\ffmpeg\bin", "User")
```

## Рішення 2: Альтернативне встановлення

### Через Chocolatey

```powershell
# Встановіть Chocolatey (якщо не встановлено)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Встановіть FFmpeg
choco install ffmpeg
```

### Ручне встановлення

1. Завантажте FFmpeg з https://ffmpeg.org/download.html
2. Розпакуйте в `C:\ffmpeg`
3. Додайте `C:\ffmpeg\bin` до змінної PATH

## Рішення 3: Запуск без FFmpeg (Тимчасове)

Якщо FFmpeg не встановлюється, бот все одно може працювати з текстом та іншими функціями:

```powershell
python main_bot.py
```

**Обмеження:** Голосові повідомлення та аудіофайли не будуть оброблятися.

## Діагностика

Запустіть діагностичний скрипт:

```powershell
python test_audio.py
```

Це покаже, які компоненти працюють і що потрібно виправити.

## Перевірка після встановлення

1. Перезапустіть PowerShell
2. Виконайте:
   ```powershell
   ffmpeg -version
   python test_audio.py
   python main_bot.py
   ```

## Поширені помилки

### "ffmpeg не розпізнано"

- Перезапустіть PowerShell
- Перевірте PATH
- Встановіть заново

### "WinError 2: Не удается найти указанный файл"

- FFmpeg не в PATH
- Спробуйте альтернативне встановлення

### Проблеми з правами доступу

- Запустіть PowerShell як Адміністратор
- Використовуйте `--user` для pip install

---

**Важливо:** Після успішного встановлення FFmpeg бот зможе повноцінно обробляти голосові повідомлення, аудіофайли та створювати транскрипції.
