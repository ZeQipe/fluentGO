"""
Парсер для файла ConfigData.txt с поддержкой флагов секций.
Быстрый парсер с кэшированием для эффективной работы.
"""
import os
import re
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
from datetime import datetime, timedelta


class ConfigDataParser:
    """Парсер для ConfigData.txt с поддержкой секций по флагам"""
    
    # Флаги секций
    FLAG_TOPIC = "-> Topic"
    FLAG_HELP = "-> Help"
    FLAG_MEDIA = "-> Media"
    
    # Время жизни кэша (в секундах)
    CACHE_TTL = 60
    
    def __init__(self, file_path: str = "document/ConfigData.txt"):
        self.file_path = file_path
        self._cache: Optional[Dict] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def _is_cache_valid(self) -> bool:
        """Проверяет валидность кэша"""
        if self._cache is None or self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).total_seconds() < self.CACHE_TTL
    
    def _read_file(self) -> str:
        """Читает файл ConfigData.txt"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Файл {self.file_path} не найден")
        
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _find_section_bounds(self, content: str, flag: str) -> Optional[Tuple[int, int]]:
        """
        Находит границы секции по флагу.
        Возвращает (start_index, end_index) или None если секция не найдена.
        """
        # Ищем начало секции (флаг)
        flag_pattern = re.escape(flag)
        match = re.search(f"^{flag_pattern}$", content, re.MULTILINE)
        
        if not match:
            return None
        
        start_index = match.end()
        
        # Ищем конец секции (следующий флаг или конец файла)
        next_flags = [
            self.FLAG_TOPIC,
            self.FLAG_HELP,
            self.FLAG_MEDIA
        ]
        next_flags.remove(flag)  # Убираем текущий флаг
        
        # Ищем следующий флаг
        end_index = len(content)
        for next_flag in next_flags:
            next_match = re.search(f"^{re.escape(next_flag)}$", content[start_index:], re.MULTILINE)
            if next_match:
                end_index = min(end_index, start_index + next_match.start())
        
        return (start_index, end_index)
    
    def _parse_topics(self, content: str) -> List[Dict[str, str]]:
        """Парсит секцию Topics"""
        bounds = self._find_section_bounds(content, self.FLAG_TOPIC)
        if not bounds:
            return []
        
        section_content = content[bounds[0]:bounds[1]].strip()
        
        # Парсим по блокам (разделитель - две пустые строки)
        blocks = section_content.split("\n\n")
        
        topics = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            lines = block.split("\n", 1)
            if len(lines) >= 1:
                topic = {
                    "title": lines[0].strip(),
                    "description": lines[1].strip() if len(lines) > 1 else ""
                }
                # Валидация: название не должно быть пустым
                if topic["title"]:
                    topics.append(topic)
        
        return topics
    
    def _parse_help(self, content: str) -> List[Dict[str, str]]:
        """Парсит секцию Help (FAQ)"""
        bounds = self._find_section_bounds(content, self.FLAG_HELP)
        if not bounds:
            return []
        
        section_content = content[bounds[0]:bounds[1]].strip()
        
        # Парсим по блокам (разделитель - две пустые строки)
        blocks = section_content.split("\n\n")
        
        help_items = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            lines = block.split("\n", 1)
            if len(lines) >= 1:
                item = {
                    "title": lines[0].strip(),
                    "description": lines[1].strip() if len(lines) > 1 else ""
                }
                # Валидация: вопрос не должен быть пустым
                if item["title"]:
                    help_items.append(item)
        
        return help_items
    
    def _parse_media(self, content: str) -> Optional[str]:
        """Парсит секцию Media (ссылка на видео)"""
        bounds = self._find_section_bounds(content, self.FLAG_MEDIA)
        if not bounds:
            return None
        
        section_content = content[bounds[0]:bounds[1]].strip()
        
        # Берем первую непустую строку
        lines = section_content.split("\n")
        for line in lines:
            line = line.strip()
            if line:
                # Валидация: проверяем что это похоже на URL
                if line.startswith("http://") or line.startswith("https://"):
                    return line
                # Если не URL, все равно возвращаем (может быть относительный путь)
                return line
        
        return None
    
    def parse_all(self, use_cache: bool = True) -> Dict:
        """
        Парсит весь файл и возвращает все секции.
        
        Returns:
            Dict с ключами: 'topics', 'help', 'media'
        """
        # Проверяем кэш
        if use_cache and self._is_cache_valid():
            return self._cache.copy()
        
        # Читаем файл
        content = self._read_file()
        
        # Парсим все секции
        result = {
            "topics": self._parse_topics(content),
            "help": self._parse_help(content),
            "media": self._parse_media(content)
        }
        
        # Сохраняем в кэш
        self._cache = result
        self._cache_timestamp = datetime.now()
        
        return result
    
    def get_topics(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """Получает только секцию Topics"""
        return self.parse_all(use_cache)["topics"]
    
    def get_help(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """Получает только секцию Help"""
        return self.parse_all(use_cache)["help"]
    
    def get_media(self, use_cache: bool = True) -> Optional[str]:
        """Получает только секцию Media"""
        return self.parse_all(use_cache)["media"]
    
    def clear_cache(self):
        """Очищает кэш (полезно при обновлении файла)"""
        self._cache = None
        self._cache_timestamp = None


class TariffsParser:
    """Парсер для TariffsData.txt с тарифами"""
    
    # Флаг начала нового тарифа
    FLAG_TARIFF = "-> Tariff"
    
    # Время жизни кэша (в секундах)
    CACHE_TTL = 60
    
    def __init__(self, file_path: str = "document/TariffsData.txt"):
        self.file_path = file_path
        self._cache: Optional[List[Dict]] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def _is_cache_valid(self) -> bool:
        """Проверяет валидность кэша"""
        if self._cache is None or self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).total_seconds() < self.CACHE_TTL
    
    def _read_file(self) -> str:
        """Читает файл TariffsData.txt"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Файл {self.file_path} не найден")
        
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _parse_value(self, value: str, key: str):
        """Преобразует строковое значение в нужный тип"""
        value = value.strip()
        
        # Boolean поля
        if key in ["disabled", "popular"]:
            return value.lower() == "true"
        
        # Списки (statuses)
        if key == "statuses":
            if not value:
                return []
            return [s.strip() for s in value.split(",") if s.strip()]
        
        # Остальные поля - строки
        return value
    
    def _parse_tariff_block(self, block: str) -> Optional[Dict]:
        """Парсит один блок тарифа"""
        lines = block.strip().split("\n")
        if not lines:
            return None
        
        tariff = {}
        features = []
        parsing_features = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Проверяем начало секции features
            if "<>" in line and not parsing_features:
                parts = line.split("<>", 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                
                if key == "features":
                    parsing_features = True
                    continue
                else:
                    tariff[key] = self._parse_value(value, key)
            
            # Если парсим features - каждая строка это фича
            elif parsing_features:
                if line and not line.startswith("->"):
                    features.append({
                        "text": line,
                        "included": True
                    })
        
        # Добавляем features в тариф (если нет - пустой массив)
        tariff["features"] = features if features else []
        
        # Валидация: обязательные поля
        required_fields = ["id", "name", "price", "period", "type"]
        if not all(field in tariff for field in required_fields):
            return None
        
        # Добавляем дефолтные значения для опциональных полей если их нет
        if "statuses" not in tariff:
            tariff["statuses"] = []
        if "disabled" not in tariff:
            tariff["disabled"] = False
        if "popular" not in tariff:
            tariff["popular"] = False
        if "popularLabel" not in tariff:
            tariff["popularLabel"] = ""
        
        # buttonText и buttonType вычисляются на бэке, не читаем из файла
        tariff["buttonText"] = ""
        tariff["buttonType"] = ""
        
        # Удаляем пустые строки из необязательных полей
        if tariff.get("popularLabel") == "":
            tariff["popularLabel"] = ""
        
        return tariff
    
    def parse_all(self, use_cache: bool = True) -> List[Dict]:
        """
        Парсит весь файл и возвращает список тарифов.
        
        Returns:
            List[Dict] со всеми тарифами
        """
        # Проверяем кэш
        if use_cache and self._is_cache_valid():
            return self._cache.copy()
        
        # Читаем файл
        content = self._read_file()
        
        # Разбиваем на блоки по флагу "-> Tariff"
        blocks = re.split(f"^{re.escape(self.FLAG_TARIFF)}$", content, flags=re.MULTILINE)
        
        tariffs = []
        for block in blocks[1:]:  # Пропускаем первый пустой блок
            tariff = self._parse_tariff_block(block)
            if tariff:
                tariffs.append(tariff)
        
        # Сохраняем в кэш
        self._cache = tariffs
        self._cache_timestamp = datetime.now()
        
        return tariffs
    
    def get_tariffs(self, use_cache: bool = True) -> List[Dict]:
        """Получает все тарифы"""
        return self.parse_all(use_cache)
    
    def clear_cache(self):
        """Очищает кэш (полезно при обновлении файла)"""
        self._cache = None
        self._cache_timestamp = None


# Глобальные экземпляры парсеров
_config_parser = None
_tariffs_parser = None

def get_config_parser(file_path: str = "document/ConfigData.txt") -> ConfigDataParser:
    """Получает глобальный экземпляр парсера (singleton)"""
    global _config_parser
    if _config_parser is None or _config_parser.file_path != file_path:
        _config_parser = ConfigDataParser(file_path)
    return _config_parser

def get_tariffs_parser(file_path: str = "document/TariffsData.txt") -> TariffsParser:
    """Получает глобальный экземпляр парсера тарифов (singleton)"""
    global _tariffs_parser
    if _tariffs_parser is None or _tariffs_parser.file_path != file_path:
        _tariffs_parser = TariffsParser(file_path)
    return _tariffs_parser

