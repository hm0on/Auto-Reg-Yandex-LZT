"""
Модуль для регистрации аккаунтов Яндекс
Использует Camoufox для максимального антидетекта
"""

import time
import random
import string
from typing import Optional, Callable, Dict, Any
from camoufox.sync_api import Camoufox
from playwright.sync_api import Page, BrowserContext, TimeoutError as PlaywrightTimeout

from .sms_api import SpanchSMS
from .proxy_manager import ProxyManager
from .user_agents import UserAgentManager
from .number_manager import NumberManager
import config


class YandexRegistrar:
    """Класс для регистрации аккаунтов Яндекс через Camoufox"""
    
    REGISTER_URL = "https://passport.yandex.ru/registration"
    
    # ==================== Селекторы ====================
    # Страница ввода номера
    SEL_PHONE_INPUT = "#passp-field-phone"
    SEL_PHONE_SUBMIT = "#passp\\:phone\\:controls\\:next"  # Экранируем двоеточие
    
    # Страница подтверждения (звонок/SMS)
    SEL_CODE_INPUT = "#passp-field-phoneCode"
    SEL_CODE_SUBMIT = "[data-t='button:action']"
    SEL_NO_CALL_BUTTON = "[data-t='button:default:retry-to-request-code']"

    # Капча
    SEL_CAPTCHA_IMAGE = "#captcha-image"
    SEL_CAPTCHA_INPUT = "#passp-field-captcha"
    
    # Страница выбора "для кого аккаунт"
    SEL_FOR_SELF_RADIO = "input[value='FOR_SELF']"
    SEL_FOR_WHOM_SUBMIT = "[data-testid='survey-for-whom-submit']"
    
    # Страница ввода имени/фамилии
    SEL_FIRSTNAME_INPUT = "input[aria-label='Имя']"
    SEL_LASTNAME_INPUT = "input[aria-label='Фамилия']"
    SEL_NAME_SUBMIT = "[data-testid='fln-next']"
    
    # Страница ввода логина
    SEL_LOGIN_INPUT = "input[aria-label='login']"
    SEL_LOGIN_SUBMIT = "[data-testid='auth-reg-login-next']"
    
    # Страница ввода пароля
    SEL_PASSWORD_INPUT = "input[aria-label='Пароль']"
    SEL_PASSWORD_SUBMIT = "[data-testid='reg-password-next']"
    
    # Страница согласия с правилами
    SEL_EULA_CHECKBOX = "[data-testid='input'][type='checkbox']"
    SEL_EULA_SUBMIT = "[data-testid='eula-next']"
    
    # Страница госуслуг (пропускаем)
    SEL_SKIP_GOSUSLUGI = "[data-testid='identification-promo-start-skip-btn']"
    SEL_CLOSE_GOSUSLUGI = "[data-testid='button'][aria-label='Закрыть']"
    
    # Таймауты
    WAIT_BEFORE_NO_CALL_SEC = 70  # ждать минуту и 10 сек перед кликом «Звонка не было»
    WAIT_NO_CALL_TIMEOUT = 130   # общий таймаут: 70 сек ожидания + до 60 сек на появление кнопки
    
    def __init__(
        self,
        sms_api: SpanchSMS = None,
        proxy_manager: ProxyManager = None,
        user_agent_manager: UserAgentManager = None,
        number_manager: NumberManager = None,
        log_callback: Callable[[str], None] = None,
        manual_code_callback: Callable[[str], Optional[str]] = None
    ):
        self.sms_api = sms_api or SpanchSMS()
        self.proxy_manager = proxy_manager or ProxyManager()
        self.ua_manager = user_agent_manager or UserAgentManager()
        self.number_manager = number_manager or NumberManager()
        self.log_callback = log_callback or print
        self.manual_code_callback = manual_code_callback  # Callback для запроса кода в GUI
        
        self.browser: Optional[Camoufox] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self.use_proxy: bool = True
        self.sms_mode: str = "auto"  # "auto" или "manual"
        
        # Текущая активация SMS
        self.current_activation_id: Optional[int] = None
        self.current_phone: Optional[str] = None
        
    def log(self, message: str) -> None:
        """Вывести лог"""
        if self.log_callback:
            self.log_callback(message)
            
    def _generate_name(self) -> tuple[str, str, str]:
        """
        Генерация случайного имени и фамилии с учётом пола
        
        Returns:
            (имя, фамилия, пол) - пол: "male" или "female"
        """
        # Мужские имена
        male_first_names = [
            "Александр", "Дмитрий", "Максим", "Сергей", "Андрей", 
            "Алексей", "Артём", "Илья", "Кирилл", "Михаил",
            "Никита", "Егор", "Иван", "Арсений", "Даниил",
            "Матвей", "Тимофей", "Роман", "Владимир", "Павел"
        ]
        
        # Женские имена
        female_first_names = [
            "Анна", "Мария", "Елена", "Ольга", "Наталья", 
            "Ирина", "Татьяна", "Светлана", "Юлия", "Екатерина",
            "Алина", "Дарья", "Полина", "Виктория", "Анастасия",
            "Ксения", "Валерия", "София", "Вероника", "Кристина"
        ]
        
        # Мужские фамилии
        male_last_names = [
            "Иванов", "Смирнов", "Кузнецов", "Попов", "Соколов", 
            "Лебедев", "Козлов", "Новиков", "Морозов", "Петров",
            "Волков", "Соловьёв", "Васильев", "Зайцев", "Павлов",
            "Семёнов", "Голубев", "Виноградов", "Богданов", "Воробьёв"
        ]
        
        # Женские фамилии
        female_last_names = [
            "Иванова", "Смирнова", "Кузнецова", "Попова", "Соколова", 
            "Лебедева", "Козлова", "Новикова", "Морозова", "Петрова",
            "Волкова", "Соловьёва", "Васильева", "Зайцева", "Павлова",
            "Семёнова", "Голубева", "Виноградова", "Богданова", "Воробьёва"
        ]
        
        # Выбираем пол
        gender = random.choice(["male", "female"])
        
        if gender == "male":
            first_name = random.choice(male_first_names)
            last_name = random.choice(male_last_names)
        else:
            first_name = random.choice(female_first_names)
            last_name = random.choice(female_last_names)
        
        return first_name, last_name, gender
    
    def _transliterate(self, text: str) -> str:
        """Транслитерация кириллицы в латиницу"""
        transliteration = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        result = ""
        for char in text.lower():
            result += transliteration.get(char, char)
        return result
    
    def _generate_login(self, first_name: str, last_name: str) -> str:
        """
        Генерация уникального логина с высокой вероятностью доступности
        
        Форматы логина (выбирается случайно):
        - ivan.petrov2847
        - petrov.ivan93x
        - ivanpetrov_2847
        - i.petrov.2847abc
        - ivan_p_2847
        """
        first = self._transliterate(first_name)
        last = self._transliterate(last_name)
        
        # Случайные компоненты для уникальности
        digits = ''.join(random.choices(string.digits, k=random.randint(4, 6)))
        letters = ''.join(random.choices(string.ascii_lowercase, k=random.randint(2, 3)))
        year = str(random.randint(1985, 2005))[-2:]  # Последние 2 цифры года рождения
        
        # Разные форматы логинов
        login_formats = [
            f"{first}.{last}{digits}",
            f"{last}.{first}{digits}",
            f"{first}{last}_{digits}",
            f"{first}_{last}{digits}",
            f"{first[0]}.{last}.{digits}{letters}",
            f"{first}_{last[0]}_{digits}",
            f"{last}{first[0]}{digits}{letters}",
            f"{first}.{last}.{year}{digits[:2]}",
            f"{first}{digits}{letters}",
            f"{last}_{first}{year}{letters}",
        ]
        
        return random.choice(login_formats)
    
    def _generate_password(self, length: int = 12) -> str:
        """Генерация надёжного пароля"""
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(random.choices(chars, k=length))
        return password
    
    def _get_browser_config(self) -> Dict[str, Any]:
        """Получить конфигурацию для Camoufox"""
        cfg = {
            "headless": config.HEADLESS_MODE,
            "locale": config.BROWSER_LOCALE,
            "geoip": True,  # Автоматическое определение геолокации по IP
            "i_know_what_im_doing": True,  # Отключает предупреждения
            "firefox_user_prefs": {
                # Отключаем проверку SSL сертификатов (для прокси)
                "security.cert_pinning.enforcement_level": 0,
                "network.stricttransportsecurity.preloadlist": False,
                "security.enterprise_roots.enabled": True,
            },
        }
        
        # Прокси
        if self.use_proxy and self.proxy_manager.has_proxies:
            proxy_str = self.proxy_manager.get_next()
            if proxy_str:
                proxy_config = self.proxy_manager.get_camoufox_proxy(proxy_str)
                if proxy_config:
                    cfg["proxy"] = proxy_config
                    self.log(f"Прокси: {proxy_config['server']}")
        
        return cfg
    
    def _create_browser(self) -> None:
        """Создать экземпляр браузера Camoufox"""
        browser_config = self._get_browser_config()
        
        self.log("Запуск Camoufox...")
        self.browser = Camoufox(**browser_config)
        self.context = self.browser.__enter__()
        
        # Создаём страницу с игнорированием SSL ошибок (для прокси)
        try:
            self.page = self.context.new_page(ignore_https_errors=True)
        except TypeError:
            # Если параметр не поддерживается - создаём обычную страницу
            self.page = self.context.new_page()
        
        # Установка таймаутов
        self.page.set_default_timeout(config.PAGE_LOAD_TIMEOUT * 1000)
        self.page.set_default_navigation_timeout(config.PAGE_LOAD_TIMEOUT * 1000)
        
        self.log("Браузер запущен")
    
    def _check_captcha(self) -> bool:
        """Проверка наличия капчи"""
        try:
            # Проверяем наличие картинки капчи или поля ввода капчи
            captcha_selectors = [
                self.SEL_CAPTCHA_IMAGE,
                self.SEL_CAPTCHA_INPUT,
                "[class*='captcha']",
                "[class*='Captcha']",
                "img[src*='captcha']",
            ]
            
            for selector in captcha_selectors:
                if self.page.locator(selector).count() > 0:
                    return True
            return False
        except Exception:
            return False

    def _has_change_number_button(self) -> bool:
        """Проверить наличие кнопки «Изменить номер» — номер уже зарегистрирован в Яндексе"""
        if not self.page:
            return False
        try:
            return self.page.get_by_role("button", name="Изменить номер").count() > 0
        except Exception:
            return False

    def _page_has_phone_already_registered(self) -> bool:
        """Проверить, показывает ли страница «номер уже зарегистрирован» (кнопка «Изменить номер» или текст)"""
        if not self.page:
            return False
        try:
            if self._has_change_number_button():
                return True
            text = self.page.content().lower()
            phrases = [
                "уже зарегистрирован",
                "уже привязан",
                "учётная запись с этим номером",
                "привязан к другому",
                "зарегистрирован в другом",
                "this phone is already",
                "already registered",
            ]
            return any(p in text for p in phrases)
        except Exception:
            return False

    def _wait_for_element(self, selector: str, timeout: float = None, state: str = "visible") -> bool:
        """
        Ждать появления элемента
        
        Args:
            selector: CSS селектор
            timeout: Таймаут в секундах (по умолчанию из config)
            state: Состояние элемента (visible, attached, hidden)
            
        Returns:
            True если элемент найден
        """
        timeout = timeout or config.ELEMENT_TIMEOUT
        try:
            self.page.locator(selector).wait_for(state=state, timeout=timeout * 1000)
            return True
        except PlaywrightTimeout:
            return False
        except Exception:
            return False
    
    def _element_exists(self, selector: str) -> bool:
        """Проверить существование элемента"""
        try:
            return self.page.locator(selector).count() > 0
        except Exception:
            return False
    
    def _get_element_text(self, selector: str) -> str:
        """Получить текст элемента"""
        try:
            return self.page.locator(selector).inner_text()
        except Exception:
            return ""
    
    def _close_session(self) -> None:
        """Закрыть текущую сессию браузера"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.__exit__(None, None, None)
        except Exception:
            pass
        finally:
            self.page = None
            self.context = None
            self.browser = None
            
    def _cancel_current_activation(self) -> None:
        """Отменить текущую активацию SMS"""
        if self.current_activation_id:
            try:
                self.sms_api.cancel_order(self.current_activation_id)
                self.log(f"Активация {self.current_activation_id} отменена")
            except Exception as e:
                self.log(f"Ошибка отмены активации: {e}")
            finally:
                self.current_activation_id = None
                self.current_phone = None
    
    def _get_sms_number(self) -> bool:
        """
        Получить номер для SMS (автоматический режим через API)
        
        Returns:
            True если номер получен, False при ошибке
        """
        if self.sms_mode == "manual":
            return False
            
        self.log("Запрос номера через Spanch SMS...")
        
        # Используем улучшенный метод API
        number = self.sms_api.get_number_object()
        
        if number:
            self.current_activation_id = number.id
            self.current_phone = number.phone
            self.log(f"Получен номер: {number.phone} (ID: {number.id}, цена: ${number.price})")
            return True
        else:
            # Получаем детали ошибки
            result = self.sms_api.get_number()
            error = self.sms_api.get_error(result) or "Неизвестная ошибка"
            self.log(f"Ошибка получения номера: {error}")
            return False
    
    def _get_manual_number(self) -> Optional[str]:
        """
        Получить номер из файла numbers.txt (ручной режим)
        
        Returns:
            Номер телефона или None если номеров нет
        """
        if not self.number_manager.has_numbers:
            self.log("Файл numbers.txt пуст или не существует")
            return None
        
        number = self.number_manager.get_next()
        if number:
            self.log(f"Номер из файла: +{number} (осталось: {self.number_manager.remaining})")
            return number
        else:
            self.log("Номера в файле закончились")
            return None
    
    def _wait_for_manual_sms_code(self) -> Optional[str]:
        """
        Запросить SMS код через GUI диалог
        
        Вызывает callback для показа диалога ввода кода в GUI.
        
        Returns:
            Код или None при отмене/таймауте
        """
        if not self.manual_code_callback:
            self.log("Ошибка: callback для ручного ввода не задан")
            return None
        
        self.log("Ожидание ввода SMS кода...")
        
        # Вызываем callback - он покажет диалог в GUI и вернёт код
        code = self.manual_code_callback(self.current_phone)
        
        if code:
            self.log(f"Получен код: {code}")
            return code
        else:
            self.log("Код не был введён")
            return None
    
    def _wait_for_sms_code(self) -> Optional[str]:
        """
        Ожидание SMS кода (автоматический режим через API)
        
        Returns:
            Код или None при таймауте/ошибке
        """
        if self.sms_mode == "manual":
            # В ручном режиме не используем API
            return None
        
        if not self.current_activation_id:
            return None
            
        self.log("Ожидание SMS кода...")
        
        # Используем встроенный метод ожидания с прогрессом
        start_time = time.time()
        last_log_time = start_time
        
        while time.time() - start_time < config.SMS_WAIT_TIMEOUT:
            if getattr(self, "_stop_flag", None) and self._stop_flag():
                self.log("Остановка по запросу пользователя")
                return None

            code_obj = self.sms_api.get_code_object(self.current_activation_id)

            if code_obj:
                if code_obj.received:
                    self.log(f"Получен код: {code_obj.code}")
                    return code_obj.code
            else:
                # Проверяем на ошибку
                result = self.sms_api.get_code(self.current_activation_id)
                if not self.sms_api.is_success(result):
                    error = self.sms_api.get_error(result)
                    self.log(f"Ошибка получения кода: {error}")
                    return None
            
            # Логируем прогресс каждые 30 секунд
            if time.time() - last_log_time >= 30:
                elapsed = int(time.time() - start_time)
                remaining = config.SMS_WAIT_TIMEOUT - elapsed
                self.log(f"Ожидание кода... ({elapsed}с прошло, {remaining}с осталось)")
                last_log_time = time.time()
                    
            time.sleep(config.SMS_CHECK_INTERVAL)
            
        self.log("Таймаут ожидания SMS")
        return None
    
    def _fill_input(self, selector: str, value: str, delay: float = 0.05) -> bool:
        """Заполнить поле ввода с имитацией печати"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=config.ELEMENT_TIMEOUT * 1000)
            element.click()
            element.fill("")  # Очистить поле
            element.type(value, delay=delay * 1000)  # Имитация печати
            return True
        except Exception as e:
            self.log(f"Ошибка заполнения {selector}: {e}")
            return False
    
    def _click_element(self, selector: str) -> bool:
        """Кликнуть по элементу"""
        try:
            element = self.page.locator(selector)
            element.wait_for(state="visible", timeout=config.ELEMENT_TIMEOUT * 1000)
            element.click()
            return True
        except Exception as e:
            self.log(f"Ошибка клика {selector}: {e}")
            return False
    
    def _wait_and_check(self, seconds: float = 1.0) -> bool:
        """Подождать и проверить капчу"""
        time.sleep(seconds)
        if self._check_captcha():
            self.log("Обнаружена капча!")
            return False
        return True
    
    def _enter_phone_number(self, phone: str) -> bool:
        """
        Ввести номер телефона на странице регистрации
        
        Args:
            phone: Номер телефона (с кодом страны или без)
            
        Returns:
            True если успешно
        """
        self.log(f"Ввод номера телефона: {phone}")
        
        # Ждём появления поля ввода
        if not self._wait_for_element(self.SEL_PHONE_INPUT):
            self.log("Поле ввода номера не найдено")
            return False
        
        # Очищаем и вводим номер
        phone_input = self.page.locator(self.SEL_PHONE_INPUT)
        phone_input.click()
        
        # Поле может уже содержать +7, очищаем и вводим полностью
        phone_input.fill("")
        time.sleep(0.3)
        
        # Форматируем номер (добавляем + если нужно)
        if not phone.startswith("+"):
            if phone.startswith("7"):
                phone = "+" + phone
            else:
                phone = "+7" + phone
        
        phone_input.type(phone, delay=50)
        time.sleep(0.5)
        
        return True
    
    def _click_phone_submit(self) -> bool:
        """Нажать кнопку 'Продолжить' после ввода номера"""
        self.log("Нажатие 'Продолжить'...")
        
        if not self._wait_for_element(self.SEL_PHONE_SUBMIT):
            self.log("Кнопка 'Продолжить' не найдена")
            return False
        
        self.page.locator(self.SEL_PHONE_SUBMIT).click()
        time.sleep(2)
        
        return True
    
    def _wait_for_sms_option(self) -> bool:
        """
        Ждать минуту и 10 секунд, затем нажать кнопку 'Звонка не было' / 'Выслать СМС'.
        Яндекс сначала пытается позвонить; кнопка для SMS появляется через ~60 секунд.
        Кликаем только после WAIT_BEFORE_NO_CALL_SEC, чтобы не вводить код в поле «последние 6 цифр звонящего».
        """
        before_sec = self.WAIT_BEFORE_NO_CALL_SEC
        self.log(f"Ожидание {before_sec} сек перед кнопкой 'Звонка не было'...")
        
        start_time = time.time()
        while time.time() - start_time < self.WAIT_NO_CALL_TIMEOUT:
            if getattr(self, "_stop_flag", None) and self._stop_flag():
                self.log("Остановка по запросу пользователя")
                return False

            elapsed = time.time() - start_time

            # Проверяем «номер уже зарегистрирован» (кнопка «Изменить номер») — отменяем активацию и берём другой
            if self._page_has_phone_already_registered():
                self.log("Номер уже зарегистрирован в Яндексе, отменяем активацию и берём другой")
                self._cancel_current_activation()
                return False

            # Проверяем капчу
            if self._check_captcha():
                self.log("Обнаружена капча!")
                return False

            # Кнопку ищем и нажимаем только после заданной задержки
            if elapsed >= before_sec:
                if self._element_exists(self.SEL_NO_CALL_BUTTON):
                    button = self.page.locator(self.SEL_NO_CALL_BUTTON)
                    if button.is_enabled():
                        self.log("Кнопка 'Звонка не было' доступна, нажимаем")
                        return True
            
            if int(elapsed) % 15 == 0 and int(elapsed) > 0:
                self.log(f"Ожидание... ({int(elapsed)} сек)")
            
            time.sleep(2)
        
        self.log("Таймаут ожидания кнопки SMS")
        return False
    
    def _request_sms_code(self) -> bool:
        """Нажать кнопку для запроса SMS кода"""
        self.log("Запрос SMS кода...")
        
        if not self._click_element(self.SEL_NO_CALL_BUTTON):
            self.log("Не удалось нажать кнопку запроса SMS")
            return False
        
        time.sleep(2)
        return True
    
    def _enter_sms_code(self, code: str) -> bool:
        """Ввести SMS код"""
        self.log(f"Ввод SMS кода: {code}")
        
        if not self._wait_for_element(self.SEL_CODE_INPUT):
            self.log("Поле ввода кода не найдено")
            return False
        
        code_input = self.page.locator(self.SEL_CODE_INPUT)
        code_input.click()
        code_input.fill("")
        code_input.type(code, delay=50)
        time.sleep(0.5)
        
        return True
    
    def _click_code_submit(self) -> bool:
        """Нажать кнопку 'Продолжить' после ввода кода"""
        self.log("Подтверждение кода...")
        
        if self._wait_for_element(self.SEL_CODE_SUBMIT, timeout=15):
            try:
                self.page.locator(self.SEL_CODE_SUBMIT).first.click()
                time.sleep(2)
                return True
            except Exception:
                pass
        
        # Пробуем клик по кнопке с текстом "Продолжить"
        try:
            btn = self.page.get_by_role("button", name="Продолжить")
            if btn.count() > 0:
                btn.first.click()
                time.sleep(2)
                return True
        except Exception:
            pass
        
        self.log("Кнопка подтверждения не найдена")
        return False
    
    def register_account(self) -> Optional[Dict[str, str]]:
        """
        Зарегистрировать один аккаунт
        
        Флоу регистрации Яндекса:
        1. Ввод номера телефона
        2. Яндекс пытается позвонить (ждём ~60 сек)
        3. Нажимаем "Звонка не было" для получения SMS
        4. Вводим SMS код
        5. После верификации - создание аккаунта
        
        Returns:
            {"login": "...", "password": "...", "phone": "..."} или None при ошибке
        """
        try:
            # Создаём браузер
            self._create_browser()
            
            # Генерируем данные заранее (понадобятся после верификации номера)
            first_name, last_name, gender = self._generate_name()
            login = self._generate_login(first_name, last_name)
            password = self._generate_password()
            
            gender_ru = "М" if gender == "male" else "Ж"
            self.log(f"Данные: {first_name} {last_name} ({gender_ru})")
            self.log(f"Логин: {login}, Пароль: {password}")
            
            # ==================== Шаг 1: Открытие страницы ====================
            self.log("Открытие страницы регистрации...")
            self.page.goto(self.REGISTER_URL, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Проверяем капчу
            if self._check_captcha():
                self.log("Капча на странице регистрации!")
                return None
            
            # ==================== Шаг 2: Получение номера ====================
            if self.sms_mode == "auto":
                if not self._get_sms_number():
                    self.log("Не удалось получить номер")
                    return None
                phone = self.current_phone
            else:
                # Ручной режим - берём номер из файла numbers.txt
                phone = self._get_manual_number()
                if not phone:
                    self.log("Нет доступных номеров в numbers.txt")
                    return None
                self.current_phone = phone
            
            # ==================== Шаг 3: Ввод номера ====================
            if not self._enter_phone_number(phone):
                return None
            
            if self._check_captcha():
                self.log("Капча после ввода номера!")
                return None
            
            # ==================== Шаг 4: Нажимаем "Продолжить" ====================
            if not self._click_phone_submit():
                return None

            time.sleep(2)
            if self._page_has_phone_already_registered():
                self.log("Номер уже зарегистрирован в Яндексе, отменяем активацию и берём другой")
                self._cancel_current_activation()
                return None

            if self._check_captcha():
                self.log("Капча после отправки номера!")
                return None

            # ==================== Шаг 5: Ждём кнопку "Звонка не было" ====================
            if not self._wait_for_sms_option():
                return None
            
            # ==================== Шаг 6: Запрашиваем SMS ====================
            if not self._request_sms_code():
                return None
            
            if self._check_captcha():
                self.log("Капча после запроса SMS!")
                return None
            
            # ==================== Шаг 7: Ожидаем SMS код ====================
            if self.sms_mode == "auto":
                # Автоматический режим - получаем код через API
                sms_code = self._wait_for_sms_code()
            else:
                # Ручной режим - получаем код через GUI диалог
                sms_code = self._wait_for_manual_sms_code()
            
            if not sms_code:
                self.log("Не удалось получить SMS код")
                return None
            
            # ==================== Шаг 8: Вводим SMS код ====================
            if not self._enter_sms_code(sms_code):
                return None
            
            # ==================== Шаг 9: Подтверждаем код ====================
            if not self._click_code_submit():
                # Возможно страница уже перешла (авто-отправка при вводе 6 цифр)
                if self._element_exists(self.SEL_FOR_SELF_RADIO) or self._element_exists(self.SEL_FOR_WHOM_SUBMIT):
                    self.log("Страница уже на шаге 'для кого аккаунт', продолжаем")
                else:
                    return None
            
            if self._check_captcha():
                self.log("Капча после ввода кода!")
                return None
            
            # ==================== Шаг 10: Выбор "для себя" ====================
            self.log("Выбор типа аккаунта...")
            time.sleep(2)
            
            if self._check_captcha():
                self.log("Капча на странице выбора!")
                return None
            
            # Нажимаем radio "для себя"
            if self._wait_for_element(self.SEL_FOR_SELF_RADIO, timeout=10):
                self.page.locator(self.SEL_FOR_SELF_RADIO).click()
                time.sleep(0.5)
            else:
                self.log("Кнопка 'для себя' не найдена, возможно уже выбрано")
            
            # Кнопка "Продолжить" на шаге "для кого аккаунт"
            clicked = self._click_element(self.SEL_FOR_WHOM_SUBMIT)
            if not clicked:
                try:
                    btn = self.page.get_by_role("button", name="Продолжить")
                    if btn.count() > 0:
                        btn.first.click()
                        clicked = True
                        time.sleep(1)
                except Exception:
                    pass
            if not clicked:
                try:
                    # Альтернатива: кнопка по data-testid или по тексту
                    for sel in ["[data-testid='survey-for-whom-submit']", "button:has-text('Продолжить')"]:
                        if self.page.locator(sel).count() > 0:
                            self.page.locator(sel).first.click()
                            clicked = True
                            break
                except Exception:
                    pass
            if not clicked:
                self.log("Не удалось нажать 'Продолжить' на выборе типа")
                return None
            
            time.sleep(2)
            
            # ==================== Шаг 11: Ввод имени и фамилии ====================
            self.log(f"Ввод имени: {first_name}")
            
            if not self._wait_for_element(self.SEL_FIRSTNAME_INPUT, timeout=10):
                self.log("Поле имени не найдено")
                return None
            
            # Имя
            firstname_input = self.page.locator(self.SEL_FIRSTNAME_INPUT)
            firstname_input.click()
            firstname_input.fill("")
            firstname_input.type(first_name, delay=50)
            time.sleep(0.3)
            
            # Фамилия
            self.log(f"Ввод фамилии: {last_name}")
            if not self._wait_for_element(self.SEL_LASTNAME_INPUT):
                self.log("Поле фамилии не найдено")
                return None
            
            lastname_input = self.page.locator(self.SEL_LASTNAME_INPUT)
            lastname_input.click()
            lastname_input.fill("")
            lastname_input.type(last_name, delay=50)
            time.sleep(0.5)
            
            # Кнопка "Далее"
            if not self._click_element(self.SEL_NAME_SUBMIT):
                self.log("Не удалось нажать 'Далее' после ввода имени")
                return None
            
            time.sleep(2)
            
            if self._check_captcha():
                self.log("Капча после ввода имени!")
                return None
            
            # ==================== Шаг 12: Ввод логина ====================
            self.log(f"Ввод логина: {login}")
            
            if not self._wait_for_element(self.SEL_LOGIN_INPUT, timeout=10):
                self.log("Поле логина не найдено")
                return None
            
            login_input = self.page.locator(self.SEL_LOGIN_INPUT)
            login_input.click()
            login_input.fill("")
            login_input.type(login, delay=50)
            time.sleep(0.5)
            
            # Кнопка "Продолжить"
            if not self._click_element(self.SEL_LOGIN_SUBMIT):
                self.log("Не удалось нажать 'Продолжить' после ввода логина")
                return None
            
            time.sleep(2)
            
            if self._check_captcha():
                self.log("Капча после ввода логина!")
                return None
            
            # ==================== Шаг 13: Ввод пароля ====================
            self.log("Ввод пароля...")
            
            if not self._wait_for_element(self.SEL_PASSWORD_INPUT, timeout=10):
                self.log("Поле пароля не найдено")
                return None
            
            password_input = self.page.locator(self.SEL_PASSWORD_INPUT)
            password_input.click()
            password_input.fill("")
            password_input.type(password, delay=50)
            time.sleep(0.5)
            
            # Кнопка "Далее"
            if not self._click_element(self.SEL_PASSWORD_SUBMIT):
                self.log("Не удалось нажать 'Далее' после ввода пароля")
                return None
            
            time.sleep(2)
            
            if self._check_captcha():
                self.log("Капча после ввода пароля!")
                return None
            
            # ==================== Шаг 14: Согласие с правилами ====================
            self.log("Согласие с правилами...")
            
            if self._wait_for_element(self.SEL_EULA_CHECKBOX, timeout=10):
                checkbox = self.page.locator(self.SEL_EULA_CHECKBOX)
                if not checkbox.is_checked():
                    checkbox.click()
                    time.sleep(0.5)
            
            # Кнопка "Хорошо"
            if not self._click_element(self.SEL_EULA_SUBMIT):
                self.log("Не удалось нажать 'Хорошо'")
                return None
            
            time.sleep(2)
            
            # ==================== Шаг 15: Пропуск госуслуг ====================
            self.log("Пропуск верификации госуслуг...")
            
            # Пробуем нажать "Не сейчас"
            if self._wait_for_element(self.SEL_SKIP_GOSUSLUGI, timeout=5):
                self._click_element(self.SEL_SKIP_GOSUSLUGI)
                time.sleep(1)
            
            # Пробуем нажать крестик (закрыть)
            if self._wait_for_element(self.SEL_CLOSE_GOSUSLUGI, timeout=3):
                self._click_element(self.SEL_CLOSE_GOSUSLUGI)
                time.sleep(1)
            
            # ==================== Готово! ====================
            self.log("=" * 40)
            self.log("✓ АККАУНТ УСПЕШНО СОЗДАН!")
            self.log("=" * 40)
            self.log(f"Логин: {login}")
            self.log(f"Пароль: {password}")
            self.log(f"Телефон: {self.current_phone}")
            self.log(f"Имя: {first_name} {last_name}")
            
            return {
                "login": login,
                "password": password,
                "phone": self.current_phone or "manual",
                "first_name": first_name,
                "last_name": last_name,
                "gender": gender,
                "status": "created"
            }
            
        except PlaywrightTimeout:
            self.log("Таймаут при загрузке страницы")
            return None
        except Exception as e:
            self.log(f"Ошибка регистрации: {e}")
            return None
        finally:
            self._close_session()
            
    def register_multiple(
        self,
        count: int,
        use_proxy: bool = True,
        sms_mode: str = "auto",
        stop_flag: Callable[[], bool] = None
    ) -> list[Dict[str, str]]:
        """
        Зарегистрировать несколько аккаунтов
        
        Args:
            count: Количество аккаунтов
            use_proxy: Использовать ли прокси
            sms_mode: Режим SMS ("auto" или "manual")
            stop_flag: Функция для проверки остановки
            
        Returns:
            Список успешно созданных аккаунтов
        """
        self.use_proxy = use_proxy
        self.sms_mode = sms_mode
        self._stop_flag = stop_flag

        accounts = []

        for i in range(count):
            if stop_flag and stop_flag():
                self.log("Остановка по запросу пользователя")
                break

            self.log(f"\n{'='*40}")
            self.log(f"Регистрация аккаунта {i + 1}/{count}")
            self.log(f"{'='*40}")
            
            result = self.register_account()
            
            if result:
                accounts.append(result)
                self.log(f"✓ Аккаунт создан: {result['login']}")
            else:
                self.log("✗ Не удалось создать аккаунт")
                # Отменяем текущую активацию если была
                self._cancel_current_activation()
                
            # Пауза между регистрациями (проверяем stop на каждой секунде)
            if i < count - 1:
                delay = random.uniform(3, 7)
                self.log(f"Пауза {delay:.1f} сек...")
                end_pause = time.time() + delay
                while time.time() < end_pause:
                    if stop_flag and stop_flag():
                        break
                    time.sleep(1)
                
        self.log(f"\nГотово! Создано {len(accounts)}/{count} аккаунтов")
        return accounts
