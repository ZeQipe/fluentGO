import aiohttp
import numpy as np
import logging
import sys
import wave

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

def resample_to_16khz(input_file, output_file=None):
    """
    Очень быстрый ресемплинг WAV-файла из 44.1кГц в 16кГц.
    Оптимизировано для скорости, работает с 16-битными WAV файлами.
    
    Args:
        input_file (str): Путь к входному WAV-файлу
        output_file (str, optional): Путь для сохранения результата
        
    Returns:
        str: Путь к сохранённому файлу
    """
    if output_file is None:
        name_parts = input_file.rsplit('.', 1)
        output_file = f"{name_parts[0]}_16khz.{name_parts[1] if len(name_parts) > 1 else 'wav'}"
    
    # Открываем входной файл
    with wave.open(input_file, 'rb') as in_wav:
        # Получаем параметры
        channels = in_wav.getnchannels()
        samp_width = in_wav.getsampwidth()
        orig_rate = in_wav.getframerate()
        n_frames = in_wav.getnframes()
        
        # Читаем все фреймы
        frames = in_wav.readframes(n_frames)
    
    resampled = resample(frames, orig_rate, 16000)
    
    # Создаем выходной файл
    with wave.open(output_file, 'wb') as out_wav:
        out_wav.setnchannels(1)
        out_wav.setsampwidth(samp_width)
        out_wav.setframerate(16000)
        out_wav.writeframes(resampled)
    
    return output_file