from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import logging
import sys
import time
import os

from .connection_handlers import ConnectionManager, apply_settings
from .web_client import index_page
from .transcribation_utils import process_audio_chunk, initialize_vad
from .other_utils import resample

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uvicorn")
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
connection_manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """
    При запуске приложения инициализируется пул VAD моделей и создается папка temp
    """
    # Создаем папку temp если она не существует
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        logger.info(f"Created directory: {temp_dir}")
    else:
        logger.info(f"Directory {temp_dir} already exists")
    
    await initialize_vad()

@app.get("/", response_class=HTMLResponse)
async def index():
    '''
    Эндпоинт для вывода веб-интерфейса
    '''
    return index_page


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Эндпоинт для подключения по вебсокету от веб-клиента.
    """

    client_ip = str(round(time.time()*100))
    await connection_manager.connect(websocket, client_ip)
    query_params = websocket.query_params
    voice = query_params.get('voice', None)
    topic = query_params.get('topic', None)
    response_length = query_params.get('response_length', 'normal').lower()
    
    # Валидация длины ответа
    valid_response_lengths = ['short', 'normal', 'long']
    if response_length not in valid_response_lengths:
        response_length = 'normal'
    
    print(f"Topic: {topic}, Response Length: {response_length}")
    if topic != 'none':
        await connection_manager.set_property(client_ip,'topic', topic)
    await connection_manager.set_property(client_ip, 'voice', voice)
    await connection_manager.set_property(client_ip, 'response_length', response_length)
    
    # Устанавливаем user_id для standalone режима (используем client_ip)
    await connection_manager.set_property(client_ip, 'user_id', client_ip)
    await connection_manager.set_property(client_ip, 'is_authenticated', False)

    logger.info(f'New connection! Total users: {len(connection_manager.connections)}')
    await connection_manager.send_text(client_ip, 'Успешно подключено')

    await apply_settings(connection_manager,client_ip)

    async def receive_chunk():
        """
        Цикл для получения аудио-чанков от пользователя
        """
        start_time = time.time()
        RECEIVE_TIMEOUT = 16
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_bytes(),
                    timeout=RECEIVE_TIMEOUT
                )
                frame = resample(data,44100,16000)
                frame = frame[300:]

                await process_audio_chunk(connection_manager,client_ip, frame)

                await asyncio.sleep(0.05)

            except asyncio.TimeoutError:
                logger.warning(f"Client {client_ip}: No audio data received for {RECEIVE_TIMEOUT} seconds")
                break


    async def synthesize_and_queue(voice):
            """
            Цикл для синтеза аудио перед отправкой пользователю
            """
            play_queue = await connection_manager.get_property(client_ip, 'play')
            agent = await connection_manager.get_property(client_ip, 'agent')
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
        play_queue = await connection_manager.get_property(client_ip, 'play')
        while True:
            (response_audio, duration) = await play_queue.get()
            if time.time() - last_audio > 3:
                await asyncio.sleep(1.4)
            last_audio = time.time()
            await connection_manager.send_bytes(client_ip, response_audio)
            #await asyncio.sleep(duration)
            await asyncio.sleep(0.05)

    voice = await connection_manager.get_property(client_ip, 'voice')

    receive_task = asyncio.create_task(receive_chunk())
    synthesize_task = asyncio.create_task(synthesize_and_queue(voice))

    play_task = asyncio.create_task(play_audio())

    try:
        await asyncio.gather(receive_task, synthesize_task, play_task)
    except Exception as e:
        print(str(e))
        await connection_manager.send_text(client_ip, f'Возникла ошибка: {str(e)}')
    finally:
        synthesize_task.cancel()
        play_task.cancel()
        logger.info(f'Disconnected! Total users: {len(connection_manager.connections)}')
        await connection_manager.disconnect(client_ip)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8023)#, workers = 4)
