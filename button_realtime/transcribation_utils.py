import time
import openai

from .prod_config import OPEN_AI_API_KEY

client = openai.AsyncOpenAI(api_key=OPEN_AI_API_KEY)

async def save_and_process_audio(connection_manager, client_ip: str, filename):
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
        
        # Фиксируем время обработки
        processing_start = await connection_manager.get_property(client_ip, 'processing_start_time')
        if processing_start:
            processing_duration = time.time() - processing_start
            await connection_manager.set_property(client_ip, 'processing_duration', processing_duration)
        
        agent = await connection_manager.get_property(client_ip, 'agent')
        await agent.send_text(transcribed_text)


async def audio_to_text(audio_stream):

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_stream,
    )
    return transcript.text