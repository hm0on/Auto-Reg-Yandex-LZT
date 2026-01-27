"""
Модуль для работы с API Spanch SMS
Документация: https://telegra.ph/API-Spanch-SMS-08-22
"""

import json
import time
import requests
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
import config


@dataclass
class SMSNumber:
    """Данные полученного номера"""
    id: int
    phone: str
    price: float
    
    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> Optional["SMSNumber"]:
        """Создать из ответа API"""
        if data.get("status") != "success":
            return None
        return cls(
            id=data.get("id", 0),
            phone=str(data.get("phone", "")),
            price=float(data.get("price", 0))
        )


@dataclass  
class SMSCode:
    """Данные полученного кода"""
    code: str
    full_message: str
    received: bool
    
    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> Optional["SMSCode"]:
        """Создать из ответа API"""
        if data.get("status") != "success":
            return None
        return cls(
            code=data.get("code", ""),
            full_message=data.get("full", ""),
            received=data.get("message") == "received"
        )


class SpanchSMSError(Exception):
    """Исключение для ошибок API"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class SpanchSMS:
    """
    Класс для работы с API Spanch SMS
    
    Пример использования:
        api = SpanchSMS()
        
        # Проверка баланса
        balance = api.get_balance_value()
        print(f"Баланс: ${balance}")
        
        # Получение номера
        number = api.get_number_object()
        if number:
            print(f"Номер: {number.phone}, ID: {number.id}")
            
            # Ожидание кода
            code = api.wait_for_code(number.id, timeout=120)
            if code:
                print(f"Код: {code}")
    """
    
    # Константы статусов
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    
    # Константы сообщений
    MSG_RECEIVED = "received"
    MSG_WAITING = "waiting"
    
    def __init__(self, api_key: str = None, max_retries: int = 3):
        """
        Инициализация клиента API
        
        Args:
            api_key: API ключ (если None, берётся из config)
            max_retries: Максимальное количество повторных попыток
        """
        self.api_key = api_key or config.SPANCH_API_KEY
        self.base_url = config.SPANCH_API_URL
        self.max_retries = max_retries
        self._session = requests.Session()
        
    def _parse_json_string(self, value: Any) -> Any:
        """Парсит JSON-строку если это строка, иначе возвращает как есть"""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value
        
    def _make_request(
        self, 
        params: Dict[str, Any], 
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Выполнить запрос к API с retry логикой
        
        Args:
            params: Параметры запроса
            retry: Использовать ли retry при ошибках
            
        Returns:
            Ответ API в виде словаря
        """
        params["api_key"] = self.api_key
        
        last_error = None
        attempts = self.max_retries if retry else 1
        
        for attempt in range(attempts):
            try:
                response = self._session.get(
                    self.base_url, 
                    params=params, 
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Парсим JSON-строки в message если есть
                if "message" in data:
                    data["message"] = self._parse_json_string(data["message"])
                    
                return data
                
            except requests.exceptions.Timeout:
                last_error = "Timeout: сервер не ответил вовремя"
            except requests.exceptions.ConnectionError:
                last_error = "Connection error: не удалось подключиться к серверу"
            except requests.exceptions.HTTPError as e:
                # Пытаемся получить JSON с сообщением об ошибке
                try:
                    error_data = e.response.json()
                    if error_data.get("status") == "error":
                        return error_data
                except (json.JSONDecodeError, ValueError):
                    pass
                last_error = f"HTTP error: {e.response.status_code}"
            except requests.RequestException as e:
                last_error = f"Request error: {str(e)}"
            except (json.JSONDecodeError, ValueError):
                last_error = "Invalid JSON response"
                
            # Экспоненциальная задержка перед повтором
            if attempt < attempts - 1:
                delay = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                time.sleep(delay)
                
        return {"status": self.STATUS_ERROR, "message": last_error}
    
    def is_success(self, response: Dict[str, Any]) -> bool:
        """Проверить, успешен ли ответ"""
        return response.get("status") == self.STATUS_SUCCESS
    
    def get_error(self, response: Dict[str, Any]) -> Optional[str]:
        """Получить сообщение об ошибке из ответа"""
        if response.get("status") == self.STATUS_ERROR:
            return response.get("message", "Unknown error")
        return None
    
    # ==================== Базовые методы API ====================
    
    def get_balance(self) -> Dict[str, Any]:
        """Получить баланс (сырой ответ)"""
        return self._make_request({"action": "getBalance"})
    
    def get_balance_value(self) -> float:
        """Получить баланс как число"""
        result = self.get_balance()
        if self.is_success(result):
            try:
                return float(result.get("message", 0))
            except (ValueError, TypeError):
                return 0.0
        return 0.0
    
    def get_gateways(self) -> Dict[str, Any]:
        """Получить список доступных шлюзов (сырой ответ)"""
        return self._make_request({"action": "getGateways"})
    
    def get_gateways_list(self) -> List[str]:
        """Получить список шлюзов как список строк"""
        result = self.get_gateways()
        if self.is_success(result):
            message = result.get("message", "")
            if isinstance(message, str):
                return [g.strip() for g in message.split(",")]
            elif isinstance(message, list):
                return message
        return []
    
    def get_countries(self) -> Dict[str, Any]:
        """Получить список доступных стран (сырой ответ)"""
        return self._make_request({"action": "getCountries"})
    
    def get_countries_list(self) -> List[str]:
        """Получить список стран как список кодов"""
        result = self.get_countries()
        if self.is_success(result):
            message = result.get("message", [])
            if isinstance(message, list):
                return message
        return []
    
    def get_services(self) -> Dict[str, Any]:
        """Получить список доступных сервисов (сырой ответ)"""
        return self._make_request({"action": "getServices"})
    
    def get_services_list(self) -> List[str]:
        """Получить список сервисов как список строк"""
        result = self.get_services()
        if self.is_success(result):
            message = result.get("message", [])
            if isinstance(message, list):
                return message
        return []
    
    def get_operators(self, country: str) -> Dict[str, Any]:
        """Получить список операторов для страны"""
        return self._make_request({
            "action": "getOperators",
            "country": country.lower()
        })
    
    def get_operators_list(self, country: str) -> List[str]:
        """Получить список операторов как список строк"""
        result = self.get_operators(country)
        if self.is_success(result):
            message = result.get("message", [])
            if isinstance(message, list):
                return message
        return []
    
    def get_prices(self, country: str, service: str, gateway: str) -> Dict[str, Any]:
        """Получить актуальные цены"""
        return self._make_request({
            "action": "getPrices",
            "country": country.lower(),
            "service": service.lower(),
            "gateway": gateway.lower()
        })
    
    def get_cheapest_price(self, country: str, service: str, gateway: str) -> Optional[float]:
        """Получить минимальную цену для сервиса"""
        result = self.get_prices(country, service, gateway)
        if self.is_success(result):
            prices = result.get("prices", [])
            if prices:
                return min(p.get("price", float("inf")) for p in prices)
        return None
    
    # ==================== Работа с номерами ====================
    
    def get_number(
        self,
        service: str = None,
        country: str = None,
        gateway: str = None,
        operator: str = None,
        max_price: float = None,
        route: str = None
    ) -> Dict[str, Any]:
        """
        Получить виртуальный номер для сервиса (сырой ответ)
        
        Args:
            service: Название сервиса (по умолчанию из config)
            country: Код страны (по умолчанию из config)
            gateway: Название шлюза (по умолчанию из config)
            operator: Код оператора (опционально)
            max_price: Максимальная цена в USD (опционально)
            route: Маршрут для шлюза (опционально)
            
        Returns:
            {"status": "success", "id": 12345, "phone": 79005553535, "price": 1.5}
        """
        params = {
            "action": "getNumber",
            "service": (service or config.SMS_SERVICE).lower(),
            "country": (country or config.SMS_COUNTRY).lower(),
            "gateway": (gateway or config.SMS_GATEWAY).lower(),
            "maxPrice": max_price if max_price is not None else config.SMS_MAX_PRICE
        }
        
        if operator:
            params["operator"] = operator
        if route:
            params["route"] = route
            
        return self._make_request(params)
    
    def get_number_object(self, **kwargs) -> Optional[SMSNumber]:
        """
        Получить номер как объект SMSNumber
        
        Returns:
            SMSNumber или None при ошибке
        """
        result = self.get_number(**kwargs)
        return SMSNumber.from_response(result)
    
    def get_code(self, activation_id: int) -> Dict[str, Any]:
        """
        Получить код активации (сырой ответ)
        
        Args:
            activation_id: ID активации
            
        Returns:
            {"status": "success", "message": "received", "code": "12345", "full": "..."}
            или {"status": "success", "message": "waiting"}
        """
        return self._make_request({
            "action": "getCode",
            "id": activation_id
        })
    
    def get_code_object(self, activation_id: int) -> Optional[SMSCode]:
        """
        Получить код как объект SMSCode
        
        Returns:
            SMSCode или None при ошибке
        """
        result = self.get_code(activation_id)
        return SMSCode.from_response(result)
    
    def wait_for_code(
        self, 
        activation_id: int, 
        timeout: int = None,
        check_interval: int = None
    ) -> Optional[str]:
        """
        Ожидать получения SMS кода
        
        Args:
            activation_id: ID активации
            timeout: Таймаут ожидания в секундах
            check_interval: Интервал проверки в секундах
            
        Returns:
            Код или None при таймауте/ошибке
        """
        timeout = timeout or config.SMS_WAIT_TIMEOUT
        check_interval = check_interval or config.SMS_CHECK_INTERVAL
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.get_code(activation_id)
            
            if self.is_success(result):
                if result.get("message") == self.MSG_RECEIVED:
                    return result.get("code")
            else:
                # Ошибка API - прекращаем ожидание
                error = self.get_error(result)
                if "no longer active" in error.lower():
                    return None
                    
            time.sleep(check_interval)
            
        return None
    
    def cancel_order(self, activation_id: int) -> Dict[str, Any]:
        """
        Отменить заказ и вернуть деньги
        
        Args:
            activation_id: ID активации
        """
        return self._make_request({
            "action": "getCancel",
            "id": activation_id
        })
    
    def request_new_code(self, activation_id: int) -> Dict[str, Any]:
        """
        Запросить повторную отправку кода
        
        Args:
            activation_id: ID активации
        """
        return self._make_request({
            "action": "getNewCode",
            "id": activation_id
        })
    
    # ==================== Аренда номеров ====================
    
    def rent_number(
        self,
        service: str,
        country: str,
        hours: int,
        gateway: str,
        operator: str = None
    ) -> Dict[str, Any]:
        """
        Арендовать номер на указанное время
        
        Args:
            service: Название сервиса
            country: Код страны
            hours: Время аренды (4, 12, 24, 48, 168)
            gateway: Название шлюза (crabbs, bob, gary, sandy)
            operator: Код оператора (опционально)
        """
        params = {
            "action": "getRentNumber",
            "service": service.lower(),
            "country": country.lower(),
            "time": hours,
            "gateway": gateway.lower()
        }
        
        if operator:
            params["operator"] = operator
            
        return self._make_request(params)
    
    def get_rent_status(self, activation_id: int) -> Dict[str, Any]:
        """Получить статус аренды и SMS сообщения"""
        return self._make_request({
            "action": "getRentStatus",
            "id": activation_id
        })
    
    def cancel_rent(self, activation_id: int) -> Dict[str, Any]:
        """Отменить аренду номера"""
        return self._make_request({
            "action": "setRentStatus",
            "id": activation_id
        })
    
    # ==================== Утилиты ====================
    
    def check_service_available(self, service: str) -> bool:
        """Проверить, доступен ли сервис"""
        services = self.get_services_list()
        return service.lower() in [s.lower() for s in services]
    
    def check_country_available(self, country: str) -> bool:
        """Проверить, доступна ли страна"""
        countries = self.get_countries_list()
        return country.upper() in [c.upper() for c in countries]
    
    def close(self):
        """Закрыть сессию"""
        self._session.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
