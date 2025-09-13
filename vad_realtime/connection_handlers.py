import asyncio
import time
import io
from fastapi import WebSocket
from datetime import datetime

from .prod_config import INSTRUCTIONS_4
from .llm_utils import AsyncOpenAIAgent

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uvicorn")


class ConnectionManager:
    '''Менеджер для обработки информации, связанной с каждым отдельным соединением'''
    def __init__(self):
        self.connections = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_ip: str):
        await websocket.accept()
        audio_queue = asyncio.Queue()
        play_queue = asyncio.Queue()
        start_time = datetime.now()
        async with self.lock:
            self.connections[client_ip] = {
                'queue': audio_queue, # Очередь синтеза аудио
                'chat_history': [], # История разговора
                'play': play_queue, # Очередь отправки аудио
                'socket': websocket, # Вебсокет, по которому происходит связь с клиентом
                'audio_buffer': io.BytesIO(), # Аудиобуфер, в который копятся чанки перед отправкой на транскрибацию
                'temporary_buffer': [], # Аудиобуфер с чанками, в который начинают писаться аудио в случае обнаружения голоса
                'is_recording': False, # Идет ли запись аудио
                'last_voice_time': time.time(), # Когда последний раз был обнаружен голос
                'thread': None, # История разговора OpenAI данного соединения
                'llm_task': None, # Поток генерации ответа от LLM
                'voice': 1,
                'topic': None,
                'agent': None,
                # Таймеры для подсчета времени - используем очередь для параллельных запросов
                'time_tracking_queue': [],  # Очередь для отслеживания времени каждого запроса
                'current_request_id': None,  # ID текущего запроса
                'user_id': None,  # ID пользователя для вычета времени
                'is_authenticated': False  # Статус авторизации
            }

    async def set_llm_task(self, client_ip: str, task):
        async with self.lock:
            if client_ip in self.connections:
                self.connections[client_ip]['llm_task'] = task

    async def add_user_message(self, client_ip, message):
        async with self.lock:
            if client_ip in self.connections:
                self.connections[client_ip]['chat_history'].append({'role':'user','content':message})
                logger.info(f'User: {message}')

    async def add_assistant_message(self, client_ip, message):
        async with self.lock:
            if client_ip in self.connections:
                self.connections[client_ip]['chat_history'].append({'role':'assistant','content':message})
                logger.info(f'Assistant: {message}')

    async def cancel_llm_task(self, client_ip: str):
        async with self.lock:
            if client_ip in self.connections:
                current_task = self.connections[client_ip].get('llm_task')
                if current_task and not current_task.done():
                    current_task.cancel()
                    try:
                        await current_task
                    except asyncio.CancelledError:
                        pass
                self.connections[client_ip]['llm_task'] = None
    async def clear_queues(self, client_ip: str):
        if client_ip in self.connections:
            self.connections[client_ip]['queue'] = asyncio.Queue()
            while not self.connections[client_ip]['play'].empty():
                await self.connections[client_ip]['play'].get()
            return self.connections[client_ip]['queue']

    async def disconnect(self, client_ip: str):
        async with self.lock:
            if client_ip in self.connections:
                try:
                    await self.connections[client_ip]['socket'].close()
                except:
                    pass
                del self.connections[client_ip]

    async def send_text(self, client_ip: str, message: str):
        try:
            async with self.lock:
                if client_ip in self.connections:
                    # Для корректной отправки русского текста
                    import json
                    if isinstance(message, dict):
                        message = json.dumps(message, ensure_ascii=False)
                    await self.connections[client_ip]['socket'].send_text(message)
        except Exception as e:
            # Удаляем разорванное соединение
            if client_ip in self.connections:
                del self.connections[client_ip]

    async def send_bytes(self, client_ip: str, data: bytes):
        try:
            async with self.lock:
                if client_ip in self.connections:
                    await self.connections[client_ip]['socket'].send_bytes(data)
        except Exception as e:
            # Удаляем разорванное соединение
            if client_ip in self.connections:
                del self.connections[client_ip]

    async def record_temporary_chunk(self, client_ip: str, chunk):
        async with self.lock:
            if client_ip in self.connections:
                self.connections[client_ip]['temporary_buffer'].append(chunk)
                if len(self.connections[client_ip]['temporary_buffer']) > 2:
                    self.connections[client_ip]['temporary_buffer'].pop(0)

    async def get_temporary_chunks(self, client_ip):
        async with self.lock:
            if client_ip in self.connections:
                return self.connections[client_ip]['temporary_buffer']
            return None

    async def get_eleven_labs_config(self, client_ip):
        async with self.lock:
            if client_ip in self.connections:
                return self.connections[client_ip]['el_config']
            return None

    async def set_property(self, client_ip, property, value):
        async with self.lock:
            if client_ip in self.connections:
                self.connections[client_ip][property] = value

    async def get_property(self, client_ip, property):
        async with self.lock:
            if client_ip in self.connections:
                return self.connections[client_ip][property]
            return None



async def calculate_and_deduct_time_for_request(connection_manager, client_ip, request_id):
    """Подсчитывает время для конкретного запроса и вычитает из БД"""
    from database import db_handler, seconds_to_minutes_ceil
    
    connection = connection_manager.connections.get(client_ip)
    if not connection:
        return
    
    # Получаем user_id
    user_id = connection.get('user_id')
    if not user_id:
        return
    
    # Находим запрос в очереди
    request_data = None
    for i, request in enumerate(connection['time_tracking_queue']):
        if request['request_id'] == request_id:
            request_data = request
            # Удаляем обработанный запрос из очереди
            connection['time_tracking_queue'].pop(i)
            break
    
    if not request_data:
        return
    
    # Суммируем все времена (в секундах)
    total_seconds = int(
        request_data.get('voice_duration', 0) +
        request_data.get('processing_duration', 0) +
        request_data.get('response_duration', 0)
    )
    
    if total_seconds > 0:
        # Вычитаем время из БД
        success = await db_handler.decrease_seconds(user_id, total_seconds)
        
        # Получаем оставшееся время
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        remaining_minutes = seconds_to_minutes_ceil(remaining_seconds)
        
        # Отправляем информацию на фронт (только если соединение активно)
        if client_ip in connection_manager.connections:
            if remaining_seconds <= 0:
                await connection_manager.send_text(client_ip, "<b>Минут осталось:</b> 0")
            else:
                await connection_manager.send_text(client_ip, f"<b>Минут осталось:</b> {remaining_minutes}")

async def calculate_and_deduct_time(connection_manager, client_ip):
    """Старая функция для совместимости с Button режимом"""
    from database import db_handler, seconds_to_minutes_ceil
    
    connection = connection_manager.connections.get(client_ip)
    if not connection:
        return
    
    # Получаем user_id
    user_id = connection.get('user_id')
    if not user_id:
        return
    
    # Суммируем все времена (в секундах)
    total_seconds = int(
        connection.get('voice_duration', 0) +
        connection.get('processing_duration', 0) +
        connection.get('response_duration', 0)
    )
    
    if total_seconds > 0:
        # Вычитаем время из БД
        success = await db_handler.decrease_seconds(user_id, total_seconds)
        
        # Получаем оставшееся время
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        remaining_minutes = seconds_to_minutes_ceil(remaining_seconds)
        
        # Отправляем информацию на фронт (только если соединение активно)
        if client_ip in connection_manager.connections:
            if remaining_seconds <= 0:
                await connection_manager.send_text(client_ip, "<b>Минут осталось:</b> 0")
            else:
                await connection_manager.send_text(client_ip, f"<b>Минут осталось:</b> {remaining_minutes}")
        
        # Сбрасываем счетчики
        connection['voice_duration'] = 0
        connection['processing_duration'] = 0
        connection['response_duration'] = 0

async def apply_settings(connection_manager, client_ip):
    """Получает информацию о настройках из БД админки и применяет для данного соединения"""

    voice = await connection_manager.get_property(client_ip, 'voice')
    topic = await connection_manager.get_property(client_ip, 'topic')
    if topic:
        instruction = INSTRUCTIONS_4.replace('[МЕСТО ДЛЯ ВСТАВКИ ТЕМАТИКИ]',f'## Тема разговора: {topic}')
    else:
        instruction = INSTRUCTIONS_4.replace('[МЕСТО ДЛЯ ВСТАВКИ ТЕМАТИКИ]', f'## Темы разговора нет, свободно говори о чем угодно.')
    agent = AsyncOpenAIAgent(instruction,connection_manager,client_ip,"gpt-4o-realtime-preview-2024-12-17",voice)
    await agent.connect()
    await connection_manager.set_property(client_ip, 'agent', agent)
    await connection_manager.send_text(client_ip,'Настройки применены. Ассистент инициализирован.')

