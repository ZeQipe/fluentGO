# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY vad_realtime/requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем необходимые файлы VAD модуля
COPY vad_realtime/web_client.py .
COPY vad_realtime/connection_handlers.py .
COPY vad_realtime/llm_utils.py .
COPY vad_realtime/other_utils.py .
COPY vad_realtime/prod_config.py .
COPY vad_realtime/transcribation_utils.py .
COPY vad_realtime/main.py .

# Копируем database.py из корневой директории (для проверки баланса)
COPY database.py .

# Создаем директорию temp
RUN mkdir -p temp

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт
EXPOSE 8000

# Запускаем VAD realtime приложение
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
