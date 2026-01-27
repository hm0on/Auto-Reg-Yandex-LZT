"""
Модуль для управления User-Agent
"""

import random
from typing import List


class UserAgentManager:
    """Менеджер User-Agent для ротации"""
    
    # Список актуальных User-Agent (Windows Chrome)
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]
    
    def __init__(self):
        self.current_index = 0
        self._shuffle_agents()
        
    def _shuffle_agents(self) -> None:
        """Перемешать список User-Agent"""
        self.agents = self.USER_AGENTS.copy()
        random.shuffle(self.agents)
        
    def get_random(self) -> str:
        """Получить случайный User-Agent"""
        return random.choice(self.agents)
    
    def get_next(self) -> str:
        """Получить следующий User-Agent (последовательно)"""
        agent = self.agents[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.agents)
        return agent
    
    def reset(self) -> None:
        """Сбросить и перемешать User-Agent"""
        self.current_index = 0
        self._shuffle_agents()
