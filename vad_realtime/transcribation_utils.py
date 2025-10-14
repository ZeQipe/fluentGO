import numpy as np
import io
from silero_vad import load_silero_vad, get_speech_timestamps
import time
import wave
import asyncio
import openai

from .llm_utils import cancel_and_start_llm_generation
from .prod_config import OPEN_AI_API_KEY

client = openai.AsyncClient(api_key=OPEN_AI_API_KEY)


async def process_audio_chunk(connection_manager, client_ip: str, chunk: bytes):
    """
    Обрабатывает аудио-чанк
    """
    connection = connection_manager.connections[client_ip]
    
    # НЕ блокируем при обработке - даем возможность договорить текущее сообщение
    
    detected = await detect_voice(chunk)
    if detected:
        if not connection['is_recording']:
            connection['is_recording'] = True
            # Создаем новый запрос с уникальным ID
            import uuid
            request_id = str(uuid.uuid4())
            connection['current_request_id'] = request_id
            # Добавляем в очередь отслеживания времени
            connection['time_tracking_queue'].append({
                'request_id': request_id,
                'recording_start_time': time.time(),
                'voice_duration': 0,
                'processing_start_time': None,
                'processing_duration': 0,
                'response_start_time': None,
                'response_duration': 0
            })
            connection['audio_buffer'] = io.BytesIO()
            await connection_manager.send_text(client_ip, "Voice detected. Clearing playback queue.")
            await connection_manager.clear_queues(client_ip)
            temp_chunks = await connection_manager.get_temporary_chunks(client_ip)
            for n in temp_chunks:
                connection['audio_buffer'].write(n)

        connection['last_voice_time'] = len(connection['audio_buffer'].getvalue())
        connection['audio_buffer'].write(chunk)
    elif connection['is_recording']:
        connection['audio_buffer'].write(chunk)
        if len(connection['audio_buffer'].getvalue()) - connection['last_voice_time'] > 80000:
            # Голос не обнаружен в течение 3 секунд, сохраняем файл
            # Находим текущий запрос в очереди и обновляем его
            current_request_id = connection.get('current_request_id')
            if current_request_id:
                for request in connection['time_tracking_queue']:
                    if request['request_id'] == current_request_id:
                        # Фиксируем длительность записи голоса
                        request['voice_duration'] = time.time() - request['recording_start_time']
                        # Начинаем обработку
                        request['processing_start_time'] = time.time()
                        break
            
            await connection_manager.send_text(client_ip, "Запрос обрабатывается...")
            await save_and_process_audio(connection_manager, client_ip)
            connection['is_recording'] = False
            connection['audio_buffer'] = io.BytesIO()

    await connection_manager.record_temporary_chunk(client_ip, chunk)


class VADModelPool:
    """
    Пул VAD моделей для нагрузоустойчивости сервиса
    """
    def __init__(self, pool_size: int = 4):
        self.pool_size = pool_size
        self.models_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """Публичный метод инициализации"""
        if not self._initialized:
            async with self.lock:
                if not self._initialized:
                    for _ in range(self.pool_size):
                        model = load_silero_vad()
                        await self.models_queue.put(model)
                    self._initialized = True

    async def acquire_model(self):
        """
        Возвращает свободную модель VAD для использования
        """
        if not self._initialized:
            raise RuntimeError("VAD pool not initialized")
        return await self.models_queue.get()

    async def release_model(self, model):
        """
        Отпускает и возвращает в пул свободную модель VAD
        """
        await self.models_queue.put(model)

vad_pool = VADModelPool(pool_size=4)

async def initialize_vad():
    """Публичная функция для инициализации VAD пула"""
    await vad_pool.initialize()
async def detect_voice(frame):
    """
    Определяет наличие голоса в чанке аудио
    """
    try:
        vad_model = await vad_pool.acquire_model()
        
        # Проверяем, что размер буфера кратен 2 (размер int16)
        if len(frame) % 2 != 0:
            # Обрезаем последний байт, если размер нечетный
            frame = frame[:-1]
        
        # Если буфер пустой или слишком маленький, возвращаем False
        if len(frame) < 2:
            return False
            
        audio_int16 = np.frombuffer(frame, np.int16)
        audio_float32 = int2float(audio_int16)
        speech_timestamps = get_speech_timestamps(audio_float32, vad_model, threshold=0.6)
        if speech_timestamps:
            return True
        return False
    finally:
        await vad_pool.release_model(vad_model)


def int2float(sound):
    """
    Конвертирует
    """
    abs_max = np.abs(sound).max()
    sound = sound.astype('float32')
    if abs_max > 0:
        sound *= 1 / 32768
    sound = sound.squeeze()
    return sound

async def save_and_process_audio(connection_manager, client_ip: str):
    """Сохраняет и обрабатывает аудиофайл"""
    # Проверяем оставшееся время перед обработкой
    from database import db_handler
    
    user_id = await connection_manager.get_property(client_ip, 'user_id')
    if user_id:
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        if remaining_seconds <= 0:
            await connection_manager.send_text(
                client_ip, 
                "У вас закончились минуты. Пожалуйста, пополните баланс для продолжения."
            )
            # Разрываем соединение
            await connection_manager.disconnect(client_ip)
            return
    
    connection = connection_manager.connections[client_ip]
    audio_data = connection['audio_buffer'].getvalue()
    connection['is_recording'] = False
    connection['audio_buffer'] = io.BytesIO()

    filename = f"temp/{str(round(time.time()))}.wav"
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_data)
    start_time = time.time()
    with open(filename, 'rb') as f:
        transcribed_text = await audio_to_text(f)

    # transcribed_text = await transcribate_file_rt(filename, False)


    await connection_manager.add_user_message(client_ip, transcribed_text)
    await connection_manager.send_text(client_ip, f'<b>Запрос пользователя:</b> {transcribed_text}')
    latency = round(time.time() - start_time, 2)
    await connection_manager.send_text(client_ip, f'Задержка на транскрибацию {str(latency)} сек')

    if transcribed_text and not transcribed_text.isspace():
        await connection_manager.send_text(client_ip, 'Генерируется ответ')
        
        # Фиксируем время обработки для текущего запроса
        connection = connection_manager.connections[client_ip]
        current_request_id = connection.get('current_request_id')
        if current_request_id:
            for request in connection['time_tracking_queue']:
                if request['request_id'] == current_request_id:
                    if request['processing_start_time']:
                        request['processing_duration'] = time.time() - request['processing_start_time']
                    break
        
        agent = await connection_manager.get_property(client_ip, 'agent')
        # Передаем request_id в agent для отслеживания
        await agent.send_text(transcribed_text, request_id=current_request_id)


async def audio_to_text(audio_stream):
    # audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    # buffer = io.BytesIO()
    # audio.export(buffer, format="wav", codec="pcm_s16le", parameters=["-ar", "16000", "-ac", "1"])
    # buffer.name = "audio.wav"
    # buffer.seek(0)

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_stream,
    )
    return transcript.text



