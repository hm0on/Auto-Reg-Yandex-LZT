"""
Модуль для управления номерами телефонов из файла (ручной режим)
"""

from typing import Optional, List
from pathlib import Path
import config


class NumberManager:
    """Менеджер номеров - последовательный выбор из файла"""
    
    def __init__(self, numbers_file: str = None):
        self.numbers_file = numbers_file or config.NUMBERS_FILE
        self.numbers: List[str] = []
        self.current_index: int = 0
        self._load_numbers()
        
    def _load_numbers(self) -> None:
        """Загрузить номера из файла"""
        numbers_path = Path(self.numbers_file)
        
        if not numbers_path.exists():
            self.numbers = []
            return
            
        with open(numbers_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if line and not line.startswith("#"):
                    # Нормализуем номер
                    number = self._normalize_number(line)
                    if number:
                        self.numbers.append(number)
                        
    def _normalize_number(self, number: str) -> Optional[str]:
        """
        Нормализовать номер телефона
        
        Поддерживаемые форматы:
        - +79001234567
        - 79001234567
        - 89001234567
        - 9001234567
        """
        # Убираем все кроме цифр и +
        cleaned = ''.join(c for c in number if c.isdigit() or c == '+')
        
        # Убираем + если есть
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        
        # Если начинается с 8, заменяем на 7
        if cleaned.startswith('8') and len(cleaned) == 11:
            cleaned = '7' + cleaned[1:]
        
        # Если 10 цифр (без кода страны), добавляем 7
        if len(cleaned) == 10:
            cleaned = '7' + cleaned
        
        # Проверяем длину (должно быть 11 цифр для РФ)
        if len(cleaned) == 11 and cleaned.startswith('7'):
            return cleaned
        
        return None
                    
    def reload(self) -> None:
        """Перезагрузить список номеров"""
        self.current_index = 0
        self._load_numbers()
        
    def get_next(self) -> Optional[str]:
        """Получить следующий номер"""
        if not self.numbers:
            return None
            
        if self.current_index >= len(self.numbers):
            return None  # Номера закончились
            
        number = self.numbers[self.current_index]
        self.current_index += 1
        return number
    
    def get_current(self) -> Optional[str]:
        """Получить текущий номер без переключения"""
        if not self.numbers or self.current_index >= len(self.numbers):
            return None
        return self.numbers[self.current_index]
    
    def peek_next(self) -> Optional[str]:
        """Посмотреть следующий номер без переключения"""
        return self.get_current()
    
    def mark_used(self, number: str) -> None:
        """
        Отметить номер как использованный (удалить из файла)
        Опционально - можно вызвать после успешной регистрации
        """
        # Перечитываем файл и удаляем использованный номер
        numbers_path = Path(self.numbers_file)
        if not numbers_path.exists():
            return
            
        with open(numbers_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Фильтруем строки
        new_lines = []
        for line in lines:
            cleaned = line.strip()
            if cleaned.startswith("#") or not cleaned:
                new_lines.append(line)
                continue
            normalized = self._normalize_number(cleaned)
            if normalized != number:
                new_lines.append(line)
        
        with open(numbers_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    
    @property
    def count(self) -> int:
        """Количество номеров в списке"""
        return len(self.numbers)
    
    @property
    def remaining(self) -> int:
        """Количество оставшихся номеров"""
        return max(0, len(self.numbers) - self.current_index)
    
    @property
    def has_numbers(self) -> bool:
        """Есть ли номера в списке"""
        return len(self.numbers) > 0 and self.current_index < len(self.numbers)
