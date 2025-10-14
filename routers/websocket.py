from fastapi import APIRouter, WebSocket
import asyncio
import logging
import sys
import time

# Импортируем компоненты из vad_realtime (серверная версия)
from vad_realtime.connection_handlers import ConnectionManager as VADConnectionManager, apply_settings as vad_apply_settings
from vad_realtime.transcribation_utils import process_audio_chunk
from vad_realtime.other_utils import resample

# Импортируем компоненты из button_realtime
from button_realtime.connection_handlers import ConnectionManager as ButtonConnectionManager, apply_settings as button_apply_settings

# Импортируем JWT сервис для работы с токенами
from services.jwt_service import JWTService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uvicorn")

router = APIRouter()
# Два отдельных менеджера для разных режимов
vad_connection_manager = VADConnectionManager()
button_connection_manager = ButtonConnectionManager()

async def get_user_id_from_cookies(websocket: WebSocket) -> tuple[str, bool]:
    """Извлекает user_id из JWT токена в куки WebSocket запроса
    
    Returns:
        tuple[str, bool]: (user_id, is_authenticated)
    """
    try:
        # Получаем куки из WebSocket запроса
        cookies = websocket.cookies
        jwt_token = cookies.get("auth_token_jwt")
        
        if jwt_token:
            # Проверяем токен и получаем данные пользователя
            user_data = await JWTService.verify_user_from_token(jwt_token)
            if user_data:
                return user_data["id"], True  # Авторизованный пользователь
        
        # Если токена нет или он невалидный - неавторизованный пользователь
        return None, False
        
    except Exception as e:
        logger.error(f"Ошибка получения user_id из куки: {e}")
        return None, False

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket эндпоинт для голосового взаимодействия (VAD Realtime)
    """
    # Получаем session_id из query параметров
    session_id = websocket.query_params.get('session_id')
    if not session_id:
        await websocket.close(code=1008, reason="session_id required")
        return
    
    await vad_connection_manager.connect(websocket, session_id)
    
    # Получаем user_id из JWT токена в куки
    user_id, is_authenticated = await get_user_id_from_cookies(websocket)
    
    # Если неавторизован - создаем/находим временного пользователя по IP
    if not user_id:
        from database import db_handler
        client_ip_address = websocket.client.host
        user_id = f"user_{client_ip_address.replace('.', '_')}"
        
        # Проверяем существует ли пользователь
        user = await db_handler.get_user(user_id)
        if not user:
            # Создаем временного пользователя
            await db_handler.create_user(
                user_id=user_id,
                user_name=f"Guest_{client_ip_address}",
                remaining_seconds=120  # 2 минуты
            )
            await db_handler.update_user(
                user_id=user_id,
                tariff="free",
                payment_status="unpaid"
            )
    
    query_params = websocket.query_params
    voice = query_params.get('voice', 'alloy').lower()  # Приводим к нижнему регистру
    topic = query_params.get('topic', None)
    response_length = query_params.get('response_length', 'normal').lower()
    
    # Валидация голоса
    valid_voices = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
    if voice not in valid_voices:
        voice = 'alloy'  # Fallback на alloy
    
    # Валидация длины ответа
    valid_response_lengths = ['short', 'normal', 'long']
    if response_length not in valid_response_lengths:
        response_length = 'normal'  # Fallback на normal
    
    print(f"VAD WebSocket connection - authenticated: {is_authenticated}, user: {user_id}, voice: {voice}, topic: {topic}, response_length: {response_length}")
    
    if topic != 'none':
        await vad_connection_manager.set_property(session_id,'topic', topic)
    await vad_connection_manager.set_property(session_id, 'voice', voice)
    await vad_connection_manager.set_property(session_id, 'response_length', response_length)
    
    # Сохраняем информацию о пользователе
    await vad_connection_manager.set_property(session_id, 'user_id', user_id)
    await vad_connection_manager.set_property(session_id, 'is_authenticated', is_authenticated)

    # Проверяем баланс при подключении
    if user_id:
        from database import db_handler
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        if remaining_seconds <= 0:
            await vad_connection_manager.send_text(session_id, "Доступ запрещен. У вас закончились минуты. Пожалуйста, пополните баланс.")
            await vad_connection_manager.disconnect(session_id)
            await websocket.close(code=1008, reason="Access denied - no remaining time")
            return

    logger.info(f'New connection! Total users: {len(vad_connection_manager.connections)}')
    await vad_connection_manager.send_text(session_id, 'Успешно подключено')

    await vad_apply_settings(vad_connection_manager, session_id)

    async def receive_chunk():
        """
        Цикл для получения аудио-чанков от пользователя
        """
        start_time = time.time()
        RECEIVE_TIMEOUT = 60  # Увеличили с 16 до 60 секунд
        while True:
            try:
                # Пробуем получить данные (аудио или текст)
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=RECEIVE_TIMEOUT
                )
                
                # Если это текстовое сообщение (ping/pong), игнорируем
                if message["type"] == "websocket.receive" and "text" in message:
                    continue
                
                # Если это аудио данные
                if message["type"] == "websocket.receive" and "bytes" in message:
                    # Обновляем активность при получении аудио чанков
                    await vad_connection_manager.update_activity(session_id)
                    
                    data = message["bytes"]
                    frame = resample(data, 44100, 16000)
                    frame = frame[300:]
                    
                    # Убеждаемся, что размер кратен 2 для int16
                    if len(frame) % 2 != 0:
                        frame = frame[:-1]

                    await process_audio_chunk(vad_connection_manager, session_id, frame)

                await asyncio.sleep(0.05)

            except asyncio.TimeoutError:
                logger.warning(f"Client {session_id}: No audio data received for {RECEIVE_TIMEOUT} seconds")
                break

    async def handle_ping_pong():
        """
        Обработка ping-pong сообщений
        """
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=5
                )
                if message == "ping":
                    await vad_connection_manager.ping(session_id)
                    await vad_connection_manager.pong(session_id)
                elif message == "pong":
                    await vad_connection_manager.ping(session_id)  # Обновляем время последнего ping
                else:
                    # Любое другое текстовое сообщение обновляет активность
                    await vad_connection_manager.update_activity(session_id)
            except asyncio.TimeoutError:
                # Отправляем ping клиенту
                await vad_connection_manager.send_text(session_id, "ping")
                await vad_connection_manager.ping(session_id)
            except:
                break

    async def synthesize_and_queue(voice):
            """
            Цикл для синтеза аудио перед отправкой пользователю
            """
            play_queue = await vad_connection_manager.get_property(session_id, 'play')
            agent = await vad_connection_manager.get_property(session_id, 'agent')
            while True:
                try:
                    await agent.read_message(play_queue)
                    await asyncio.sleep(0.05)
                except asyncio.TimeoutError:
                    continue

    async def play_audio():
        """
        Цикл для отправки синтезированного аудио ответа
        """
        last_audio = 0
        play_queue = await vad_connection_manager.get_property(session_id, 'play')
        while True:
            (response_audio, duration) = await play_queue.get()
            if time.time() - last_audio > 3:
                await asyncio.sleep(1.4)
            last_audio = time.time()
            await vad_connection_manager.send_bytes(session_id, response_audio)
            #await asyncio.sleep(duration)
            await asyncio.sleep(0.05)

    voice = await vad_connection_manager.get_property(session_id, 'voice')

    receive_task = asyncio.create_task(receive_chunk())
    synthesize_task = asyncio.create_task(synthesize_and_queue(voice))
    play_task = asyncio.create_task(play_audio())
    ping_pong_task = asyncio.create_task(handle_ping_pong())

    try:
        await asyncio.gather(receive_task, synthesize_task, play_task, ping_pong_task)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        # Не отправляем ошибку в закрытое соединение
    finally:
        # Останавливаем LLM агента перед отменой задач
        try:
            agent = await vad_connection_manager.get_property(session_id, 'agent')
            if agent:
                await agent.disconnect()
        except:
            pass
        
        synthesize_task.cancel()
        play_task.cancel()
        ping_pong_task.cancel()
        logger.info(f'Disconnected! Total users: {len(vad_connection_manager.connections)}')
        await vad_connection_manager.disconnect(session_id)

@router.websocket("/ws-button")
async def websocket_button_endpoint(websocket: WebSocket):
    """
    WebSocket эндпоинт для голосового взаимодействия (Button Realtime)
    """
    # Получаем session_id из query параметров
    session_id = websocket.query_params.get('session_id')
    if not session_id:
        await websocket.close(code=1008, reason="session_id required")
        return

    await button_connection_manager.connect(websocket, session_id)
    
    # Получаем user_id из JWT токена в куки
    user_id, is_authenticated = await get_user_id_from_cookies(websocket)
    
    # Если неавторизован - создаем/находим временного пользователя по IP
    if not user_id:
        from database import db_handler
        client_ip_address = websocket.client.host
        user_id = f"user_{client_ip_address.replace('.', '_')}"
        
        # Проверяем существует ли пользователь
        user = await db_handler.get_user(user_id)
        if not user:
            # Создаем временного пользователя
            await db_handler.create_user(
                user_id=user_id,
                user_name=f"Guest_{client_ip_address}",
                remaining_seconds=120  # 2 минуты
            )
            await db_handler.update_user(
                user_id=user_id,
                tariff="free",
                payment_status="unpaid"
            )
    
    query_params = websocket.query_params
    voice = query_params.get('voice', 'alloy').lower()  # Приводим к нижнему регистру
    topic = query_params.get('topic', None)
    response_length = query_params.get('response_length', 'normal').lower()
    
    # Валидация голоса
    valid_voices = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
    if voice not in valid_voices:
        voice = 'alloy'  # Fallback на alloy
    
    # Валидация длины ответа
    valid_response_lengths = ['short', 'normal', 'long']
    if response_length not in valid_response_lengths:
        response_length = 'normal'  # Fallback на normal
    
    print(f"Button WebSocket connection - authenticated: {is_authenticated}, user: {user_id}, voice: {voice}, topic: {topic}, response_length: {response_length}")
    
    if topic != 'none':
        await button_connection_manager.set_property(session_id, 'topic', topic)
    await button_connection_manager.set_property(session_id, 'voice', voice)
    await button_connection_manager.set_property(session_id, 'response_length', response_length)
    
    # Сохраняем информацию о пользователе
    await button_connection_manager.set_property(session_id, 'user_id', user_id)
    await button_connection_manager.set_property(session_id, 'is_authenticated', is_authenticated)
    
    # Проверяем баланс при подключении
    if user_id:
        from database import db_handler
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        if remaining_seconds <= 0:
            await button_connection_manager.send_text(session_id, "Доступ запрещен. У вас закончились минуты. Пожалуйста, пополните баланс.")
            await button_connection_manager.disconnect(session_id)
            await websocket.close(code=1008, reason="Access denied - no remaining time")
            return
    
    logger.info(f'New connection! Total users: {len(button_connection_manager.connections)}')
    await button_connection_manager.send_text(session_id, f'CONNECTED:{session_id}')
    await button_connection_manager.send_text(session_id, 'Успешно подключено')

    await button_apply_settings(button_connection_manager, session_id)

    async def handle_ping_pong():
        """
        Обработка ping-pong сообщений
        """
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=5
                )
                if message == "ping":
                    await button_connection_manager.ping(session_id)
                    await button_connection_manager.pong(session_id)
                elif message == "pong":
                    await button_connection_manager.ping(session_id)  # Обновляем время последнего ping
            except asyncio.TimeoutError:
                # Отправляем ping клиенту
                await button_connection_manager.send_text(session_id, "ping")
                await button_connection_manager.ping(session_id)
            except:
                break

    async def synthesize_and_queue(voice):
            """
            Цикл для синтеза аудио перед отправкой пользователю
            """
            play_queue = await button_connection_manager.get_property(session_id, 'play')
            agent = await button_connection_manager.get_property(session_id, 'agent')
            while True:
                try:
                    await agent.read_message(play_queue)
                    await asyncio.sleep(0.05)
                except asyncio.TimeoutError:
                    continue

    async def play_audio():
        """
        Цикл для отправки синтезированного аудио ответа
        """
        last_audio = 0
        play_queue = await button_connection_manager.get_property(session_id, 'play')
        while True:
            (response_audio, duration) = await play_queue.get()
            if time.time() - last_audio > 3:
                await asyncio.sleep(1.4)
            last_audio = time.time()
            await button_connection_manager.send_bytes(session_id, response_audio)
            # await asyncio.sleep(duration)
            await asyncio.sleep(0.05)

    voice = await button_connection_manager.get_property(session_id, 'voice')

    synthesize_task = asyncio.create_task(synthesize_and_queue(voice))
    play_task = asyncio.create_task(play_audio())
    ping_pong_task = asyncio.create_task(handle_ping_pong())

    try:
        await asyncio.gather(synthesize_task, play_task, ping_pong_task)
    except Exception as e:
        print(f"Button WebSocket error: {str(e)}")
        # Не отправляем ошибку в закрытое соединение
    finally:
        # Останавливаем LLM агента перед отменой задач
        try:
            agent = await button_connection_manager.get_property(session_id, 'agent')
            if agent:
                await agent.disconnect()
        except:
            pass
        
        synthesize_task.cancel()
        play_task.cancel()
        ping_pong_task.cancel()
        logger.info(f'Disconnected! Total users: {len(button_connection_manager.connections)}')
        await button_connection_manager.disconnect(session_id)
