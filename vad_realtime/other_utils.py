import aiohttp
import numpy as np
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uvicorn")

# Асинхронные REST запросы
async def send_post_request(url: str, data: dict, headers: dict = None) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                response_data = await response.json()
                logger.info(response_data)
                return response_data
    except Exception as e:
        print(str(e))
async def send_post_file(url: str, data: dict, headers: dict) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as response:
                response_data = await response.json()
                return response_data
    except Exception as e:
        print(str(e))

async def send_get_request(url: str, headers: dict) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response_data = await response.json()
                return response_data
    except Exception as e:
        print(str(e))

async def send_patch_request(url: str, data: dict, headers: dict) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=data, headers=headers) as response:
                response_data = await response.json()
                return response_data
    except Exception as e:
        print(str(e))

def resample(audio, orig_sr, target_sr):
    '''Меняет количество сэмплов у аудиофайла'''
    # Проверяем, что размер буфера кратен 2 (размер int16)
    if len(audio) % 2 != 0:
        # Обрезаем последний байт, если размер нечетный
        audio = audio[:-1]
    
    # Если буфер пустой, возвращаем пустой массив байтов
    if len(audio) < 2:
        return b''
    
    audio_data = np.frombuffer(audio, dtype=np.int16)
    resampled_data = np.interp(
        np.linspace(0, len(audio_data), int(len(audio_data) * target_sr / orig_sr)),
        np.arange(len(audio_data)),
        audio_data
    )
    resampled_data = np.int16(resampled_data)
    return resampled_data.tobytes()
