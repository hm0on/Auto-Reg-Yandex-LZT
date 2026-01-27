"""
GUI приложение на Flet
"""

import flet as ft
from datetime import datetime
from pathlib import Path
import threading
from typing import Optional

from core import YandexRegistrar, SpanchSMS, ProxyManager, UserAgentManager, NumberManager
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
            
        self.page.update()
        
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
            self.page.update()
        
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
            self.page.update()
            
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
        
        # Создаём диалог
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
                    "Отмена",
                    on_click=self._on_sms_code_cancel,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(self.sms_code_dialog)
        self.sms_code_dialog.open = True
        self.page.update()
    
    def _destroy_sms_dialog(self) -> None:
        """Уничтожить диалог ввода SMS"""
        if self.sms_code_dialog:
            self.sms_code_dialog.open = False
            if self.page and self.sms_code_dialog in self.page.overlay:
                self.page.overlay.remove(self.sms_code_dialog)
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
        """Обработчик нажатия 'Отмена' в диалоге"""
        self.manual_sms_code = None
        self._destroy_sms_dialog()
        self.sms_code_event.set()  # Сигнализируем рабочему потоку
    
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
        
        # Ждём пока пользователь введёт код (с таймаутом)
        if self.sms_code_event.wait(timeout=config.MANUAL_SMS_TIMEOUT):
            return self.manual_sms_code
        else:
            # Таймаут - закрываем диалог
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
        """Сохранить аккаунты в файл"""
        with open(config.OUTPUT_FILE, "a", encoding="utf-8") as f:
            for acc in accounts:
                line = f"{acc['login']}:{acc['password']}:{acc.get('phone', 'N/A')}\n"
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
            ]
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
        
        # Компоновка
        page.add(
            # Заголовок
            ft.Text("Yandex Account Registrar", size=24, weight=ft.FontWeight.BOLD),
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
    ft.app(main)
