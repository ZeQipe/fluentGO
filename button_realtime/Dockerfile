# Используем официальный образ Python 3.10 в качестве базового
FROM python:3.10

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
	
# Устанавливаем ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Устанавливаем зависимости
RUN pip install --no-cache-dir aiohttp \
    && pip install --no-cache-dir elevenlabs \
    && pip install --no-cache-dir fastapi \
    && pip install --no-cache-dir openai \
    && pip install --no-cache-dir uvicorn \
    && pip install --no-cache-dir wave==0.0.2 \
    && pip install --no-cache-dir websockets \
    && pip install --no-cache-dir aiofiles \
    && pip install --no-cache-dir numpy==1.26.0 \
    && pip install --no-cache-dir python-multipart
# Копируем необходимые файлы в рабочую директорию
#COPY requirements.txt .
COPY web_client.py .
COPY connection_handlers.py .
COPY llm_utils.py .
COPY other_utils.py .
COPY prod_config.py .
COPY transcribation_utils.py .
COPY main.py .

# Создаем директорию temp
RUN mkdir temp

# Запускаем приложение (замените на команду, которая запускает ваше приложение)
#CMD ["python", "your_script.py"]
