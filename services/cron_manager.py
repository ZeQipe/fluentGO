import os
from datetime import datetime
from typing import Any, Dict

class CronLogger:
    """Логгер для кронтабов с детальными отчетами"""
    
    def __init__(self, log_file: str = "cron_logs.txt"):
        self.log_file = log_file
    
    def log(self, task_name: str, level: str, message: str, data: Dict[str, Any] = None):
        """
        Логирование события кронтаба
        
        :param task_name: Название задачи (например, "cleanup_guests")
        :param level: Уровень: INFO, WARNING, ERROR, SUCCESS
        :param message: Описание события
        :param data: Дополнительные данные (dict)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Формируем строку лога
        log_entry = f"[{timestamp}] [{level}] [{task_name}] {message}"
        
        if data:
            log_entry += f" | Data: {data}"
        
        log_entry += "\n"
        
        # Записываем в файл
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            # Ошибку записи лога игнорируем для консоли, чтобы не засорять вывод
            # Можно добавить альтернативное хранилище/алерт при необходимости
            pass
        
        # Убрано дублирование в консоль
    
    def log_task_start(self, task_name: str):
        """Логировать начало выполнения задачи"""
        self.log(task_name, "INFO", "Задача запущена")
    
    def log_task_success(self, task_name: str, message: str = "Задача завершена успешно", data: Dict[str, Any] = None):
        """Логировать успешное завершение задачи"""
        self.log(task_name, "SUCCESS", message, data)
    
    def log_task_error(self, task_name: str, error: str, data: Dict[str, Any] = None):
        """Логировать ошибку задачи"""
        self.log(task_name, "ERROR", f"Ошибка: {error}", data)
    
    def log_task_retry(self, task_name: str, attempt: int, max_attempts: int):
        """Логировать повторную попытку"""
        self.log(task_name, "WARNING", f"Повторная попытка {attempt}/{max_attempts}")

# Глобальный экземпляр логгера
cron_logger = CronLogger()

