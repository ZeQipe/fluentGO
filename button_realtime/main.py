from fastapi import FastAPI, WebSocket, UploadFile, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncio
import logging
import sys
import time
import aiofiles

from .connection_handlers import ConnectionManager, apply_settings
from .web_client import index_page
from .transcribation_utils import save_and_process_audio
from .other_utils import resample_to_16khz

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

@app.get("/", response_class=HTMLResponse)
async def index():
    '''
    Эндпоинт для вывода веб-интерфейса
    '''
    return index_page


# Эндпоинт для отправки аудио от клиента
@app.post("/upload-audio/")
async def upload_audio(file: UploadFile, request: Request, client_id: str = Form(...)):
    client_ip = client_id
    audio_queue = await connection_manager.get_property(client_ip,'queue')
    play_queue = await connection_manager.get_property(client_ip,'play')
    await connection_manager.send_text(client_ip,'В обработку принят файл.')
    while not audio_queue.empty():
        await audio_queue.get()
    while not play_queue.empty():
        await play_queue.get()
    filename = str(round(time.time()))+'.wav'
    file_path = f"temp/{filename}"
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    resampled_file_path = resample_to_16khz(file_path)
    await save_and_process_audio(connection_manager,client_ip,resampled_file_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Эндпоинт для подключения по вебсокету от веб-клиента.
    """

    client_ip = websocket.client.host
    client_ip = f"user_{client_ip}"

    await connection_manager.connect(websocket, client_ip)
    query_params = websocket.query_params
    voice = query_params.get('voice', None)
    topic = query_params.get('topic', None)
    print(topic)
    if topic != 'none':
        await connection_manager.set_property(client_ip, 'topic', topic)
    await connection_manager.set_property(client_ip, 'voice', voice)
    logger.info(f'New connection! Total users: {len(connection_manager.connections)}')
    await connection_manager.send_text(client_ip, f'CONNECTED:{client_ip}')
    await connection_manager.send_text(client_ip, 'Успешно подключено')

    await apply_settings(connection_manager,client_ip)


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
            # await asyncio.sleep(duration)
            await asyncio.sleep(0.05)

    voice = await connection_manager.get_property(client_ip, 'voice')

    synthesize_task = asyncio.create_task(synthesize_and_queue(voice))

    play_task = asyncio.create_task(play_audio())

    try:
        await asyncio.gather(synthesize_task, play_task)
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
    uvicorn.run(app, 
    host="127.0.0.1", 
    port=8025,)#, workers = 4)
