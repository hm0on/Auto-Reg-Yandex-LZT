"""
GUI приложение на Flet
"""

import flet as ft
import time
from datetime import datetime
from pathlib import Path
import threading
from typing import Optional

from core import YandexRegistrar, SpanchSMS, ProxyManager, UserAgentManager, NumberManager
from core.number_manager import normalize_phone
import config


class YandexRegisterApp:
    """Главное окно приложения"""
    
    def __init__(self):
        self.page: Optional[ft.Page] = None
        self.registrar: Optional[YandexRegistrar] = None
        self.is_running: bool = False
        self.stop_requested: bool = False
        
        # UI элементы
        self.account_count_field: Optional[ft.TextField] = None
        self.sms_mode_dropdown: Optional[ft.Dropdown] = None
        self.use_proxy_switch: Optional[ft.Switch] = None
        self.auto_scroll_switch: Optional[ft.Switch] = None
        self.start_button: Optional[ft.ElevatedButton] = None
        self.stop_button: Optional[ft.ElevatedButton] = None
        self.clear_logs_button: Optional[ft.TextButton] = None
        self.save_logs_button: Optional[ft.TextButton] = None
        self.logs_container: Optional[ft.ListView] = None
        self.status_text: Optional[ft.Text] = None
        
        # Диалог ввода SMS кода
        self.sms_code_dialog: Optional[ft.AlertDialog] = None
        self.sms_code_input: Optional[ft.TextField] = None
        self.sms_code_event: threading.Event = threading.Event()
        self.manual_sms_code: Optional[str] = None

        # Окно ручного ввода номеров
        self.manual_numbers_dialog: Optional[ft.AlertDialog] = None
        self.manual_number_input: Optional[ft.TextField] = None
        self.manual_numbers_display: Optional[ft.Column] = None
        self._manual_numbers_list: list = []
        self._manual_file_picker: Optional[ft.FilePicker] = None
        
    def _on_pubsub_message(self, message: dict) -> None:
        """Обработчик сообщений pubsub (выполняется в UI потоке)"""
        action = message.get("action")
        data = message.get("data")
        
        if action == "log":
            self._add_log_entry(data)
        elif action == "status":
            self._update_status_ui(data)
        elif action == "running_state":
            self._set_running_state_ui(data)
        elif action == "show_dialog":
            self._create_sms_dialog(data)
        elif action == "close_dialog":
            self._destroy_sms_dialog()
        
    def _add_log_entry(self, message: str) -> None:
        """Добавить запись в лог (UI поток)"""
        if not self.logs_container or not self.page:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = ft.Text(
            f"[{timestamp}] {message}",
            size=12,
            font_family="Consolas",
            selectable=True
        )
        self.logs_container.controls.append(log_entry)
        
        # Автоскролл
        if self.auto_scroll_switch and self.auto_scroll_switch.value:
            self.logs_container.auto_scroll = True
        else:
            self.logs_container.auto_scroll = False

        try:
            self.page.update(self.logs_container)
        except (IndexError, Exception):
            try:
                self.page.update()
            except Exception:
                pass
        
    def log(self, message: str) -> None:
        """Добавить сообщение в лог (thread-safe)"""
        if self.page:
            self.page.pubsub.send_all({"action": "log", "data": message})
        
    def clear_logs(self, e=None) -> None:
        """Очистить логи"""
        if self.logs_container:
            self.logs_container.controls.clear()
            self.page.update()
            
    def save_logs(self, e=None) -> None:
        """Сохранить логи в файл"""
        if not self.logs_container:
            return
            
        log_path = Path(config.LOG_FILE)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_path.with_stem(f"{log_path.stem}_{timestamp}")
        
        with open(log_path, "w", encoding="utf-8") as f:
            for control in self.logs_container.controls:
                if isinstance(control, ft.Text):
                    f.write(control.value + "\n")
                    
        self.log(f"Логи сохранены: {log_path}")
    
    def _update_status_ui(self, text: str) -> None:
        """Обновить статус в UI"""
        if self.status_text and self.page:
            self.status_text.value = text
            try:
                self.page.update(self.status_text)
            except (IndexError, Exception):
                try:
                    self.page.update()
                except Exception:
                    pass
        
    def update_status(self, text: str) -> None:
        """Обновить статус (thread-safe)"""
        if self.page:
            self.page.pubsub.send_all({"action": "status", "data": text})
    
    def _set_running_state_ui(self, running: bool) -> None:
        """Установить состояние работы в UI"""
        self.is_running = running
        
        if self.start_button:
            self.start_button.disabled = running
        if self.stop_button:
            self.stop_button.disabled = not running
        if self.account_count_field:
            self.account_count_field.disabled = running
        if self.sms_mode_dropdown:
            self.sms_mode_dropdown.disabled = running
        if self.use_proxy_switch:
            self.use_proxy_switch.disabled = running

        if self.page:
            try:
                self.page.update()
            except (IndexError, Exception):
                pass

    def set_running_state(self, running: bool) -> None:
        """Установить состояние работы (thread-safe)"""
        if self.page:
            self.page.pubsub.send_all({"action": "running_state", "data": running})
    
    def _create_sms_dialog(self, phone: str) -> None:
        """Создать диалог ввода SMS кода"""
        # Создаём поле ввода
        self.sms_code_input = ft.TextField(
            label="SMS код",
            hint_text="Введите 6-значный код",
            width=200,
            max_length=6,
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
            text_align=ft.TextAlign.CENTER,
            text_size=24,
        )
        
        # Создаём диалог (используем show_dialog/pop_dialog, чтобы кнопки корректно закрывали окно)
        self.sms_code_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Введите SMS код"),
            content=ft.Column([
                ft.Text(f"Номер: +{phone}", size=14, color=ft.Colors.GREY_400),
                ft.Text("Введите код из SMS сообщения:", size=14),
                self.sms_code_input,
            ], tight=True, spacing=10, height=120),
            actions=[
                ft.ElevatedButton(
                    "Готово",
                    icon="check",
                    on_click=self._on_sms_code_submit,
                    bgcolor=ft.Colors.GREEN_700,
                    color=ft.Colors.WHITE,
                ),
                ft.TextButton(
                    content="Отмена",
                    on_click=self._on_sms_code_cancel,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.show_dialog(self.sms_code_dialog)
    
    def _destroy_sms_dialog(self) -> None:
        """Закрыть диалог ввода SMS (по таймауту или принудительно)"""
        try:
            if self.page:
                self.page.pop_dialog()
        except Exception:
            pass
        self.sms_code_dialog = None
        self.sms_code_input = None
        if self.page:
            self.page.update()
    
    def _on_sms_code_submit(self, e=None) -> None:
        """Обработчик нажатия 'Готово' в диалоге"""
        if self.sms_code_input:
            code = self.sms_code_input.value or ""
            if len(code) >= 6 and code.isdigit():
                self.manual_sms_code = code[:6]
                self._destroy_sms_dialog()
                self.sms_code_event.set()  # Сигнализируем рабочему потоку
            else:
                # Показываем ошибку
                self.sms_code_input.error_text = "Введите 6 цифр"
                self.page.update()
    
    def _on_sms_code_cancel(self, e=None) -> None:
        """Обработчик нажатия 'Отмена' в диалоге — закрываем через pop_dialog"""
        self.manual_sms_code = None
        try:
            if self.page:
                self.page.pop_dialog()
        except Exception:
            pass
        self.sms_code_dialog = None
        self.sms_code_input = None
        self.sms_code_event.set()

    # --- Окно ручного ввода номеров ---

    def _on_remove_manual_number(self, number: str) -> None:
        """Удалить номер из списка и из файла"""
        if number not in self._manual_numbers_list:
            return
        self._manual_numbers_list.remove(number)
        path = Path(config.NUMBERS_FILE)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(path, "w", encoding="utf-8") as f:
                for line in lines:
                    if line.strip() and not line.strip().startswith("#"):
                        if normalize_phone(line.strip()) != number:
                            f.write(line)
                    else:
                        f.write(line)
        self._refresh_manual_numbers_display()
        if self.page:
            self.page.update()

    def _refresh_manual_numbers_display(self) -> None:
        """Обновить список номеров в диалоге"""
        if self.manual_numbers_display:
            self.manual_numbers_display.controls = []
            for n in self._manual_numbers_list:
                delete_btn = ft.ElevatedButton(
                    "×",
                    on_click=lambda e, num=n: self._on_remove_manual_number(num),
                )
                self.manual_numbers_display.controls.append(
                    ft.Row(
                        [
                            ft.Text(f"+{n}", size=12),
                            ft.Container(expand=True),
                            delete_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            if self.page:
                self.page.update()

    def _open_manual_numbers_dialog(self, e=None) -> None:
        """Открыть окно ручного ввода номеров и загрузить текущий список из файла"""
        path = Path(config.NUMBERS_FILE)
        self._manual_numbers_list = []
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        n = normalize_phone(line)
                        if n:
                            self._manual_numbers_list.append(n)
        if self.manual_number_input:
            self.manual_number_input.value = ""
        self._refresh_manual_numbers_display()
        if self.manual_numbers_dialog:
            self.manual_numbers_dialog.open = True
            if self.page:
                self.page.update()

    def _close_manual_numbers_dialog(self, e=None) -> None:
        """Закрыть окно ручного ввода номеров"""
        if self.manual_numbers_dialog:
            self.manual_numbers_dialog.open = False
            if self.page:
                self.page.update()

    def _on_manual_add_number(self, e=None) -> None:
        """Добавить введённый номер в список и в файл"""
        if not self.manual_number_input:
            return
        raw = (self.manual_number_input.value or "").strip()
        if not raw:
            return
        n = normalize_phone(raw)
        if not n:
            self.manual_number_input.error_text = "Некорректный номер (ожидается 11 цифр РФ)"
            if self.page:
                self.page.update()
            return
        self.manual_number_input.error_text = None
        self.manual_number_input.value = ""
        self._manual_numbers_list.append(n)
        path = Path(config.NUMBERS_FILE)
        with open(path, "a", encoding="utf-8") as f:
            f.write(n + "\n")
        self._refresh_manual_numbers_display()
        if self.page:
            self.page.update()

    async def _on_manual_import_click(self, e=None) -> None:
        """Выбрать файл и импортировать номера (Flet 0.80+: pick_files — async, возвращает список)"""
        if not self._manual_file_picker or not self.page:
            return
        files = await self._manual_file_picker.pick_files(
            allow_multiple=False,
            dialog_title="Выберите файл с номерами",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt"],
        )
        if not files:
            return
        path = Path(getattr(files[0], "path", None) or files[0].name)
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    n = normalize_phone(line)
                    if n:
                        self._manual_numbers_list.append(n)
                        with open(config.NUMBERS_FILE, "a", encoding="utf-8") as out:
                            out.write(n + "\n")
        self._refresh_manual_numbers_display()
        self.page.update()

    def _on_sms_mode_change(self, e=None) -> None:
        """При выборе ручного режима открыть окно ввода номеров"""
        if self.sms_mode_dropdown and self.sms_mode_dropdown.value == "manual":
            self._open_manual_numbers_dialog()

    # ==================== Диалог настроек ====================
    def _open_settings_dialog(self, e=None) -> None:
        """Открыть диалог настроек"""
        # Обновляем значения из config
        self.settings_api_key_field.value = config.SPANCH_API_KEY
        self.settings_max_price_field.value = str(config.SMS_MAX_PRICE)
        self.settings_headless_switch.value = config.HEADLESS_MODE
        self.settings_dialog.open = True
        self.page.update()
    
    def _close_settings_dialog(self, e=None) -> None:
        """Закрыть диалог настроек без сохранения"""
        self.settings_dialog.open = False
        self.page.update()
    
    def _save_settings(self, e=None) -> None:
        """Сохранить настройки"""
        # Обновляем config в памяти
        new_api_key = self.settings_api_key_field.value.strip()
        try:
            new_max_price = float(self.settings_max_price_field.value.strip())
        except ValueError:
            self.log("Ошибка: некорректная макс. цена SMS")
            return
        new_headless = self.settings_headless_switch.value
        
        config.SPANCH_API_KEY = new_api_key
        config.SMS_MAX_PRICE = new_max_price
        config.HEADLESS_MODE = new_headless
        
        # Сохраняем в файл config.py
        config_path = Path(__file__).parent.parent / "config.py"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = []
            for line in lines:
                if line.strip().startswith("SPANCH_API_KEY"):
                    new_lines.append(f'SPANCH_API_KEY = "{new_api_key}"\n')
                elif line.strip().startswith("SMS_MAX_PRICE"):
                    new_lines.append(f"SMS_MAX_PRICE = {new_max_price}\n")
                elif line.strip().startswith("HEADLESS_MODE"):
                    new_lines.append(f"HEADLESS_MODE = {new_headless}\n")
                else:
                    new_lines.append(line)
            
            with open(config_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            
            self.log("Настройки сохранены")
        except Exception as ex:
            self.log(f"Ошибка сохранения настроек: {ex}")
        
        self.settings_dialog.open = False
        self.page.update()

    def request_manual_sms_code(self, phone: str) -> Optional[str]:
        """
        Запросить ручной ввод SMS кода (вызывается из рабочего потока)
        
        Args:
            phone: Номер телефона для отображения
            
        Returns:
            Введённый код или None при отмене
        """
        self.manual_sms_code = None
        self.sms_code_event.clear()

        # Показываем диалог через pubsub
        if self.page:
            self.page.pubsub.send_all({"action": "show_dialog", "data": phone})

        # Ждём ввод кода по 1 сек, чтобы «Остановить» срабатывал быстро
        start = time.time()
        while time.time() - start < config.MANUAL_SMS_TIMEOUT:
            if self.stop_requested:
                if self.page:
                    self.page.pubsub.send_all({"action": "close_dialog", "data": None})
                return None
            if self.sms_code_event.wait(timeout=1):
                return self.manual_sms_code
        # Таймаут — закрываем диалог
        if self.page:
            self.page.pubsub.send_all({"action": "close_dialog", "data": None})
        return None
        
    def start_registration(self, e=None) -> None:
        """Начать регистрацию"""
        if self.is_running:
            return
            
        # Валидация
        try:
            count = int(self.account_count_field.value or "0")
            if count <= 0:
                self.log("Ошибка: укажите количество аккаунтов больше 0")
                return
        except ValueError:
            self.log("Ошибка: некорректное количество аккаунтов")
            return
            
        self.stop_requested = False
        self.set_running_state(True)
        self.update_status("Работает...")
        
        # Запуск в отдельном потоке
        thread = threading.Thread(
            target=self._registration_worker,
            args=(count,),
            daemon=True
        )
        thread.start()
        
    def _registration_worker(self, count: int) -> None:
        """Рабочий поток регистрации"""
        try:
            sms_api = SpanchSMS()
            proxy_manager = ProxyManager()
            ua_manager = UserAgentManager()
            number_manager = NumberManager()
            
            self.registrar = YandexRegistrar(
                sms_api=sms_api,
                proxy_manager=proxy_manager,
                user_agent_manager=ua_manager,
                number_manager=number_manager,
                log_callback=self.log,
                manual_code_callback=self.request_manual_sms_code  # Callback для ручного ввода кода
            )
            
            use_proxy = self.use_proxy_switch.value if self.use_proxy_switch else False
            sms_mode = self.sms_mode_dropdown.value if self.sms_mode_dropdown else "auto"
            
            self.log(f"Запуск регистрации: {count} аккаунтов")
            self.log(f"Режим SMS: {'Автоматический (API)' if sms_mode == 'auto' else 'Ручной (numbers.txt)'}")
            self.log(f"Прокси: {'Да' if use_proxy else 'Нет'}")
            
            # Проверка для ручного режима
            if sms_mode == "manual":
                if not number_manager.has_numbers:
                    self.log("Ошибка: файл numbers.txt пуст или не существует!")
                    self.log("Добавьте номера в numbers.txt для ручного режима")
                    return
                self.log(f"Номеров в файле: {number_manager.count}")
            
            accounts = self.registrar.register_multiple(
                count=count,
                use_proxy=use_proxy,
                sms_mode=sms_mode,
                stop_flag=lambda: self.stop_requested
            )
            
            # Сохраняем результаты
            if accounts:
                self._save_accounts(accounts)
                
        except Exception as e:
            self.log(f"Критическая ошибка: {e}")
        finally:
            self.set_running_state(False)
            self.update_status("Остановлено")
            
    def _save_accounts(self, accounts: list) -> None:
        """Сохранить аккаунты и cookies в файлы"""
        import json
        from datetime import datetime
        
        for acc in accounts:
            login = acc.get('login', 'unknown')
            cookies = acc.get('cookies', [])
            
            # Сохраняем cookies в отдельный JSON файл
            if cookies:
                cookies_filename = f"cookies_{login}.json"
                try:
                    with open(cookies_filename, "w", encoding="utf-8") as f:
                        json.dump(cookies, f, indent=2, ensure_ascii=False)
                    self.log(f"Cookies сохранены: {cookies_filename}")
                except Exception as e:
                    self.log(f"Ошибка сохранения cookies: {e}")
            
            # Сохраняем информацию об аккаунте в текстовый файл
            with open(config.OUTPUT_FILE, "a", encoding="utf-8") as f:
                line = f"{login}:{acc['password']}:{acc.get('phone', 'N/A')} | cookies: cookies_{login}.json\n"
                f.write(line)
        
        self.log(f"Аккаунты сохранены в {config.OUTPUT_FILE}")
        
    def stop_registration(self, e=None) -> None:
        """Остановить регистрацию"""
        self.stop_requested = True
        self.log("Запрошена остановка...")
        self.update_status("Остановка...")
        # Также отменяем ожидание SMS кода если открыт диалог
        self.sms_code_event.set()
        
    def build_ui(self, page: ft.Page) -> None:
        """Построить интерфейс"""
        self.page = page
        page.title = "Yandex ABUZ"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20
        page.window.width = 700
        page.window.height = 600
        
        # Подписываемся на pubsub для thread-safe обновлений
        page.pubsub.subscribe(self._on_pubsub_message)
        
        # Поле количества аккаунтов
        self.account_count_field = ft.TextField(
            label="Количество аккаунтов",
            value="1",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        # Выбор режима SMS
        self.sms_mode_dropdown = ft.Dropdown(
            label="Режим SMS",
            width=200,
            value="auto",
            options=[
                ft.dropdown.Option("auto", "Автоматический (API)"),
                ft.dropdown.Option("manual", "Ручной"),
            ],
            on_select=self._on_sms_mode_change,
        )
        
        # Переключатель прокси
        self.use_proxy_switch = ft.Switch(
            label="Использовать прокси",
            value=True
        )
        
        # Переключатель автоскролла
        self.auto_scroll_switch = ft.Switch(
            label="Автоскролл логов",
            value=True
        )
        
        # Кнопки управления
        self.start_button = ft.ElevatedButton(
            "Начать регистрацию",
            icon="play_arrow",
            on_click=self.start_registration,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE
        )
        
        self.stop_button = ft.ElevatedButton(
            "Остановить",
            icon="stop",
            on_click=self.stop_registration,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            disabled=True
        )
        
        # Кнопки для логов
        self.clear_logs_button = ft.TextButton(
            "Очистить логи",
            icon="delete_outline",
            on_click=self.clear_logs
        )
        
        self.save_logs_button = ft.TextButton(
            "Сохранить логи",
            icon="save_outlined",
            on_click=self.save_logs
        )
        
        # Статус
        self.status_text = ft.Text(
            "Готов к работе",
            size=14,
            color=ft.Colors.GREY_400
        )
        
        # Контейнер логов
        self.logs_container = ft.ListView(
            expand=True,
            spacing=2,
            padding=10,
            auto_scroll=True
        )

        # Кнопка настроек
        self.settings_button = ft.ElevatedButton(
            "⚙",
            tooltip="Настройки",
            on_click=self._open_settings_dialog,
            width=40,
            height=40,
        )
        
        # Диалог настроек
        self.settings_api_key_field = ft.TextField(
            label="Spanch API Key",
            value=config.SPANCH_API_KEY,
            width=400,
            password=True,
            can_reveal_password=True,
        )
        self.settings_max_price_field = ft.TextField(
            label="Макс. цена SMS ($)",
            value=str(config.SMS_MAX_PRICE),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.settings_headless_switch = ft.Switch(
            label="Скрытый режим браузера",
            value=config.HEADLESS_MODE,
        )
        
        self.settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Настройки"),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.settings_api_key_field,
                        self.settings_max_price_field,
                        self.settings_headless_switch,
                    ],
                    tight=True,
                    spacing=15,
                ),
                width=450,
            ),
            actions=[
                ft.TextButton("Отмена", on_click=self._close_settings_dialog),
                ft.ElevatedButton("Сохранить", on_click=self._save_settings),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Окно ручного ввода номеров (открывается при выборе "Ручной")
        self.manual_number_input = ft.TextField(
            label="Номер телефона",
            hint_text="79XXXXXXXXX или +79XXXXXXXXX",
            width=320,
            keyboard_type=ft.KeyboardType.PHONE,
        )
        self.manual_numbers_display = ft.Column([], scroll=ft.ScrollMode.AUTO, tight=True)
        self._manual_file_picker = ft.FilePicker()

        self.manual_numbers_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Номера для ручного режима"),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.manual_number_input,
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Добавить",
                                    icon="add",
                                    on_click=self._on_manual_add_number,
                                ),
                                ft.ElevatedButton(
                                    "Импортировать номера",
                                    icon="upload_file",
                                    on_click=self._on_manual_import_click,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text("Добавленные номера:", size=12, color=ft.Colors.GREY_400),
                        ft.Container(content=self.manual_numbers_display, height=150),
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=400,
            ),
            actions=[
                ft.ElevatedButton("Готово", on_click=self._close_manual_numbers_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(self.manual_numbers_dialog)
        page.overlay.append(self.settings_dialog)
        page.services.append(self._manual_file_picker)
        
        # Компоновка
        page.add(
            # Заголовок с кнопкой настроек
            ft.Row([
                ft.Text("Yandex Account Registrar", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.settings_button,
            ]),
            ft.Divider(height=20),
            
            # Настройки
            ft.Row([
                self.account_count_field,
                self.sms_mode_dropdown,
            ], spacing=20),
            
            ft.Row([
                self.use_proxy_switch,
                self.auto_scroll_switch,
            ], spacing=40),
            
            ft.Divider(height=20),
            
            # Кнопки управления
            ft.Row([
                self.start_button,
                self.stop_button,
                ft.Container(expand=True),
                self.status_text,
            ], spacing=10),
            
            ft.Divider(height=10),
            
            # Логи
            ft.Container(
                content=self.logs_container,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                padding=5,
                expand=True
            ),
            
            # Кнопки логов
            ft.Row([
                self.clear_logs_button,
                self.save_logs_button,
            ], spacing=10),
        )
        
        self.log("Приложение запущено")
        self.log(f"API URL: {config.SPANCH_API_URL}")
        self.log(f"Файл прокси: {config.PROXY_FILE}")


def main(page: ft.Page):
    """Точка входа Flet"""
    app = YandexRegisterApp()
    app.build_ui(page)


if __name__ == "__main__":
    ft.run(main)
