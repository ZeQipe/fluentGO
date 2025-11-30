import os
from datetime import datetime
from typing import Optional

class TokenLogger:
    """Логгер для записи использованных токенов OpenAI"""
    
    def __init__(self, log_file: str = "logs/tokens.txt"):
        self.log_file = log_file
        # Создаем папку logs если её нет
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def log_tokens(
        self, 
        user_id: str, 
        user_name: str, 
        input_tokens: int, 
        output_tokens: int, 
        total_tokens: int,
        incoming_seconds: float = 0.0,
        outgoing_seconds: float = 0.0
    ):
        """
        Записать использование токенов
        
        Формат (новый):
            {user_id}/{user_name}/{input_tokens}/{output_tokens}/{total_tokens}/{incoming_seconds}/{outgoing_seconds}
        
        Обратная совместимость:
            Старые записи без секунд остаются валидными (парсер поддерживает оба формата).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Приводим секунды к целому числу для компактности лога
        in_sec = int(round(incoming_seconds or 0))
        out_sec = int(round(outgoing_seconds or 0))
        log_entry = f"[{timestamp}] {user_id}/{user_name}/{input_tokens}/{output_tokens}/{total_tokens}/{in_sec}/{out_sec}\n"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Ошибка записи токенов: {e}")
    
    def log_from_usage(
        self,
        user_id: str,
        user_name: str,
        usage: dict
    ):
        """
        Записать токены из объекта usage OpenAI
        
        :param usage: dict с полями input_tokens, output_tokens, total_tokens
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        
        self.log_tokens(user_id, user_name, input_tokens, output_tokens, total_tokens)

# Глобальный экземпляр логгера
token_logger = TokenLogger()

