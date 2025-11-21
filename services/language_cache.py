import time
import httpx
from typing import Optional, List

class LanguageCache:
    """Кэш для списка поддерживаемых языков с TTL"""
    
    def __init__(self, ttl: int = 86400):
        """
        :param ttl: Время жизни кэша в секундах (по умолчанию 24 часа)
        """
        self.languages: Optional[List[str]] = None
        self.timestamp: float = 0
        self.ttl: int = ttl
    
    def is_expired(self) -> bool:
        """Проверить истек ли кэш"""
        if self.languages is None:
            return True
        return (time.time() - self.timestamp) >= self.ttl
    
    async def get_languages(self) -> List[str]:
        """
        Получить список языков:
        - Если кэш актуален - вернуть из кэша
        - Если истек или пуст - запросить из API и закэшировать
        - Fallback на дефолтные значения
        """
        # Проверяем нужно ли обновить кэш
        if not self.is_expired():
            return self.languages
        
        # Кэш истек или пуст - запрашиваем из API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://iec.study/wp-json/iec/v1/languages/all",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        languages = data["data"].get("languages", [])
                        
                        if languages:
                            # Обновляем кэш
                            self.languages = languages
                            self.timestamp = time.time()
                            return self.languages
        except Exception:
            pass
        
        # Если не получилось из API - используем старый кэш (если есть)
        if self.languages:
            return self.languages
        
        # Fallback на дефолтные значения
        self.languages = ["ru", "en", "fr", "it", "es", "de"]
        self.timestamp = time.time()
        return self.languages
    
    def clear(self):
        """Очистить кэш принудительно"""
        self.languages = None
        self.timestamp = 0

class ExchangeRateCache:
    """Кэш для курса обмена валют с TTL"""
    
    def __init__(self, ttl: int = 3600):
        """
        :param ttl: Время жизни кэша в секундах (по умолчанию 1 час)
        """
        self.rate: Optional[float] = None
        self.timestamp: float = 0
        self.ttl: int = ttl
    
    def is_expired(self) -> bool:
        """Проверить истек ли кэш"""
        if self.rate is None:
            return True
        return (time.time() - self.timestamp) >= self.ttl
    
    async def get_exchange_rate(self) -> Optional[float]:
        """
        Получить курс обмена RUB/USD:
        - Если кэш актуален - вернуть из кэша
        - Если истек или пуст - запросить из API и закэшировать
        - Возвращает None если не удалось получить
        """
        # Проверяем нужно ли обновить кэш
        if not self.is_expired():
            return self.rate
        
        # Кэш истек или пуст - запрашиваем из API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://iec.study/wp-json/airalo/v1/exchange-rate-rub",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        rate = data["data"].get("final_rate")
                        
                        if rate:
                            # Обновляем кэш
                            self.rate = rate
                            self.timestamp = time.time()
                            return self.rate
        except Exception:
            pass
        
        # Если не получилось из API - используем старый кэш (если есть)
        if self.rate:
            return self.rate
        
        # Если ничего нет - возвращаем None
        return None
    
    def clear(self):
        """Очистить кэш принудительно"""
        self.rate = None
        self.timestamp = 0

# Глобальные экземпляры кэшей
language_cache = LanguageCache(ttl=86400)  # TTL = 24 часа
exchange_rate_cache = ExchangeRateCache(ttl=3600)  # TTL = 1 час

