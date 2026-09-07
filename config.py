"""
Конфигурация приложения
"""

import os
from pathlib import Path

# API Spanch SMS
SPANCH_API_URL = "https://spanch-projects.com/api"
# Store the real credential outside the repository, either in the environment
# or in the local ignored file used by the GUI settings dialog.
SPANCH_API_KEY_FILE = "spanch_api_key.txt"
_api_key_file = Path(SPANCH_API_KEY_FILE)
SPANCH_API_KEY = os.getenv("SPANCH_API_KEY", "").strip()
if not SPANCH_API_KEY and _api_key_file.exists():
    SPANCH_API_KEY = _api_key_file.read_text(encoding="utf-8").strip()

# Настройки SMS
SMS_SERVICE = "yandex"  # Название сервиса для Spanch API
SMS_COUNTRY = "ru"      # Страна для номера
SMS_GATEWAY = "bob"     # Шлюз (можно изменить: crabbs, bob, ocean, gary, plankton, squidward, sandy, patrick)
SMS_MAX_PRICE = 1       # Максимальная цена номера в USD (баланс должен быть >= этой суммы)

# Таймауты (в секундах)
SMS_WAIT_TIMEOUT = 120  # Время ожидания SMS
SMS_CHECK_INTERVAL = 5  # Интервал проверки SMS
PAGE_LOAD_TIMEOUT = 30  # Таймаут загрузки страницы
ELEMENT_TIMEOUT = 10    # Таймаут ожидания элемента

# Настройки браузера (Camoufox)
HEADLESS_MODE = False    # Запуск браузера в фоновом режиме
BROWSER_LOCALE = "ru-RU"  # Локаль браузера
BROWSER_TIMEZONE = "Europe/Moscow"  # Таймзона

# Файлы
PROXY_FILE = "proxys.txt"
NUMBERS_FILE = "numbers.txt"  # Файл с номерами для ручного режима
OUTPUT_FILE = "accounts.txt"
LOG_FILE = "logs.txt"

# Ручной режим SMS
MANUAL_SMS_TIMEOUT = 180  # Время ожидания ручного ввода кода (секунд)
