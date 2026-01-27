"""
Модуль логирования
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
import config


class Logger:
    """Класс для логирования"""
    
    def __init__(
        self,
        name: str = "YandexRegistrar",
        log_file: str = None,
        callback: Callable[[str], None] = None
    ):
        self.name = name
        self.log_file = log_file or config.LOG_FILE
        self.callback = callback
        
        # Настройка стандартного логгера
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Форматтер
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Консольный хендлер
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый хендлер (опционально)
        if self.log_file:
            file_handler = logging.FileHandler(
                self.log_file,
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
    def _log(self, level: int, message: str) -> None:
        """Внутренний метод логирования"""
        self.logger.log(level, message)
        
        # Вызов callback для GUI
        if self.callback:
            self.callback(message)
            
    def debug(self, message: str) -> None:
        """Debug сообщение"""
        self._log(logging.DEBUG, message)
        
    def info(self, message: str) -> None:
        """Info сообщение"""
        self._log(logging.INFO, message)
        
    def warning(self, message: str) -> None:
        """Warning сообщение"""
        self._log(logging.WARNING, message)
        
    def error(self, message: str) -> None:
        """Error сообщение"""
        self._log(logging.ERROR, message)
        
    def critical(self, message: str) -> None:
        """Critical сообщение"""
        self._log(logging.CRITICAL, message)
        
    def set_callback(self, callback: Callable[[str], None]) -> None:
        """Установить callback для GUI"""
        self.callback = callback
