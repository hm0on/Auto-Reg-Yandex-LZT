"""
Модуль для управления прокси
"""

import re
from typing import Optional, Dict, List
from pathlib import Path
import config


class ProxyManager:
    """Менеджер прокси - последовательный выбор из файла"""
    
    def __init__(self, proxy_file: str = None):
        self.proxy_file = proxy_file or config.PROXY_FILE
        self.proxies: List[str] = []
        self.current_index: int = 0
        self._load_proxies()
        
    def _load_proxies(self) -> None:
        """Загрузить прокси из файла"""
        proxy_path = Path(self.proxy_file)
        
        if not proxy_path.exists():
            self.proxies = []
            return
            
        with open(proxy_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Пропускаем пустые строки и комментарии
                if line and not line.startswith("#"):
                    self.proxies.append(line)
                    
    def reload(self) -> None:
        """Перезагрузить список прокси"""
        self.current_index = 0
        self._load_proxies()
        
    def get_next(self) -> Optional[str]:
        """Получить следующий прокси"""
        if not self.proxies:
            return None
            
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy
    
    def get_current(self) -> Optional[str]:
        """Получить текущий прокси без переключения"""
        if not self.proxies:
            return None
        return self.proxies[self.current_index]
    
    def parse_proxy(self, proxy_string: str) -> Dict[str, str]:
        """
        Парсинг строки прокси в словарь
        
        Поддерживаемые форматы:
        - protocol://user:pass@host:port
        - protocol://host:port
        - host:port (по умолчанию http)
        """
        result = {
            "protocol": "http",
            "host": "",
            "port": "",
            "username": "",
            "password": ""
        }
        
        # Паттерн для парсинга прокси
        pattern = r"(?:(?P<protocol>\w+)://)?(?:(?P<username>[^:@]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)"
        match = re.match(pattern, proxy_string)
        
        if match:
            groups = match.groupdict()
            result["protocol"] = groups.get("protocol") or "http"
            result["host"] = groups.get("host") or ""
            result["port"] = groups.get("port") or ""
            result["username"] = groups.get("username") or ""
            result["password"] = groups.get("password") or ""
            
        return result
    
    def get_playwright_proxy(self, proxy_string: str = None) -> Optional[Dict[str, str]]:
        """
        Получить прокси в формате для Playwright/Camoufox
        
        Returns:
            {
                "server": "http://host:port",
                "username": "user",  # опционально
                "password": "pass"   # опционально
            }
        """
        proxy = proxy_string or self.get_current()
        if not proxy:
            return None
            
        parsed = self.parse_proxy(proxy)
        
        result = {
            "server": f"{parsed['protocol']}://{parsed['host']}:{parsed['port']}"
        }
        
        if parsed["username"] and parsed["password"]:
            result["username"] = parsed["username"]
            result["password"] = parsed["password"]
            
        return result
    
    def get_camoufox_proxy(self, proxy_string: str = None) -> Optional[Dict[str, str]]:
        """Алиас для get_playwright_proxy (Camoufox использует Playwright API)"""
        return self.get_playwright_proxy(proxy_string)
    
    def get_requests_proxy(self, proxy_string: str = None) -> Optional[Dict[str, str]]:
        """Получить прокси в формате для requests"""
        proxy = proxy_string or self.get_current()
        if not proxy:
            return None
            
        parsed = self.parse_proxy(proxy)
        
        if parsed["username"] and parsed["password"]:
            proxy_url = f"{parsed['protocol']}://{parsed['username']}:{parsed['password']}@{parsed['host']}:{parsed['port']}"
        else:
            proxy_url = f"{parsed['protocol']}://{parsed['host']}:{parsed['port']}"
            
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    @property
    def count(self) -> int:
        """Количество прокси в списке"""
        return len(self.proxies)
    
    @property
    def has_proxies(self) -> bool:
        """Есть ли прокси в списке"""
        return len(self.proxies) > 0
