import asyncio
from typing_extensions import override
from openai import AsyncAssistantEventHandler, AsyncOpenAI
import re
import time
import logging
import base64
import sys
import io
import wave

from .prod_config import OPEN_AI_API_KEY
from services.token_logger import token_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("uvicorn")

class AsyncOpenAIAgent:
    def __init__(self, instructions, connection_manager, client_ip, model, voice):
        """ Initialize voice assistant. """

        self.client = AsyncOpenAI(api_key=OPEN_AI_API_KEY)
        self.instructions = instructions
        self.handler = connection_manager
        self.client_ip = client_ip
        self.model = model
        self.voice = voice
        self.connection = None
        self._is_running = False
        self._generating = False

    async def connect(self):
        """Start the assistant and establish connection."""
        if self._is_running:
            return
        self.connection = await self.client.beta.realtime.connect(
            model=self.model
        ).enter()

        await self.connection.session.update(
            session={
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_transcription": None,
                "turn_detection": None,
                "temperature": 0.6
            }
        )

        self._is_running = True

    async def disconnect(self):
        """Stop the assistant and close connection."""
        if not self._is_running:
            return
        self._is_running = False

        if self.connection:
            await self.connection.close()
            self.connection = None

    async def cancel(self):
        if self._is_running and self.connection:
            try:
                if self._generating == True:
                    await self.connection.response.cancel()
                self._generating = False
            except Exception as e:
                logger.error(f"[MY_LOG] AOAIAgent_cancel: {e}")

    async def send_text(self, text):
        if self._is_running and self.connection:
            if self._generating:
                await self.cancel()
            await self.connection.conversation.item.create(
                item={
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": text
                    }]
                }
            )
            await self.connection.response.create()
            self._generating = True

    async def read_message(self, play_queue):
        """Чтение и обработка сообщений"""
        if not self.connection:
            pass  # raise RuntimeError("Not connected")
        else:
            self.message = await self.connection.recv()
            await self._handle_message(self.message, play_queue)
            # await asyncio.sleep(0.05)

    async def _handle_message(self, message, play_queue):
        """Внутренний обработчик сообщений"""
        logger.info(f"[MY_LOG] AOAIAgent_h_m: {message.type}")

        if message.type == "response.audio.delta":
            self._generating = True
            audio = base64.b64decode(message.delta)
            (response_audio, duration) = await process_audio(audio)
            await play_queue.put((response_audio, duration))

        elif message.type == "response.audio_transcript.done":
            # await self.handler.add_assistant_message(self.client_ip, message.transcript)
            await self.handler.send_text(self.client_ip,
                                         f"<b>Ответ ассистента:</b> {message.transcript}"
                                         )

        elif message.type == 'response.created':
            self._generating = True
            # Фиксируем начало ответа
            await self.handler.set_property(self.client_ip, 'response_start_time', time.time())
            logger.info(f"[MY_LOG] AOAIAgent_h_m: {message}")
        elif message.type == 'response.done':
            self._generating = False
            
            # Логируем использованные токены
            try:
                if hasattr(message, 'response') and message.response:
                    usage = getattr(message.response, 'usage', None)
                    if usage:
                        # Получаем данные пользователя
                        user_id = await self.handler.get_property(self.client_ip, 'user_id') or self.client_ip
                        user_name = await self.handler.get_property(self.client_ip, 'user_name') or 'Unknown'
                        
                        # Извлекаем токены
                        input_tokens = getattr(usage, 'input_tokens', 0)
                        output_tokens = getattr(usage, 'output_tokens', 0)
                        total_tokens = getattr(usage, 'total_tokens', input_tokens + output_tokens)
                        
                        # Логируем
                        token_logger.log_tokens(user_id, user_name, input_tokens, output_tokens, total_tokens)
            except Exception as e:
                logger.error(f"Ошибка логирования токенов: {e}")
            
            # Фиксируем конец ответа и считаем длительность
            response_start = await self.handler.get_property(self.client_ip, 'response_start_time')
            if response_start:
                response_duration = time.time() - response_start
                await self.handler.set_property(self.client_ip, 'response_duration', response_duration)
                # Вызываем подсчет и вычет времени
                from .connection_handlers import calculate_and_deduct_time
                await calculate_and_deduct_time(self.handler, self.client_ip)
            logger.info(f"[MY_LOG] AOAIAgent_h_m: {message.type}")
        elif message.type == "error":
            logger.error(f"[MY_LOG] AOAIAgent_h_m: {message}")


async def process_audio(response_audio):
    """Обрабатывает аудиобайты, выполняет ресемплинг при необходимости."""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)

        num_samples = len(response_audio[200:]) // 2
        wf.setframerate(24000)
        duration = num_samples / 24000

        wf.writeframes(response_audio[200:])

    buffer.seek(0)
    return buffer.read(), duration


async def cancel_and_start_llm_generation(connection_manager, client_ip, query):
    await connection_manager.cancel_llm_task(client_ip)
    task = asyncio.create_task(start_llm_generation(connection_manager, client_ip, query))
    await connection_manager.set_llm_task(client_ip, task)
    try:
        asyncio.gather(task)
    except asyncio.CancelledError:
        # Обработка отмены если нужно
        await connection_manager.send_text(client_ip, "LLM task was cancelled")
    except Exception as e:
        # Обработка других ошибок
        await connection_manager.send_text(client_ip, f"LLM task failed: {str(e)}")

async def start_llm_generation(connection_manager, client_ip, query):
    queue = await connection_manager.get_property(client_ip,'queue')

    thread = await connection_manager.get_property(client_ip, 'thread')
    assistant = await connection_manager.get_property(client_ip, 'assistant')
    if thread:
        await answer_response_ready(connection_manager, query, queue, client_ip, thread, assistant)
    else:
        await answer_response_new(connection_manager, query, queue, client_ip, assistant)


class EventHandler(AsyncAssistantEventHandler):
    def __init__(self, text_handler, audio_queue):
        super().__init__()
        self.text_handler = text_handler
        self.audio_queue = audio_queue
        self.counter = 0
        self.text_chunk = ''
        self.file_search_used = False

    @override
    async def on_text_created(self, text) -> None:
        # self.counter = 0
        self.text_chunk = ''

    @override
    async def on_message_done(self, message) -> None:
        if self.file_search_used:
            message_content = message.content[0].text
            annotations = message_content.annotations
            citations = []
            for index, annotation in enumerate(annotations):
                message_content.value = message_content.value.replace(
                    annotation.text, f"[{index}]"
                )
                if file_citation := getattr(annotation, "file_citation", None):
                    cited_file = await client.files.retrieve(file_citation.file_id)
                    citations.append(f"[{index}] {cited_file.filename}")
            await self.text_handler(message_content.value, self.audio_queue)

    @override
    async def on_text_delta(self, delta, snapshot):
        if '.' in delta.value:
            first_half = delta.value.split('.')[0]
            second_half = delta.value.split('.')[1]
            self.text_chunk += first_half + '.'
            if not self.text_chunk.isspace():
                await self.text_handler(self.text_chunk.split('.')[0], self.audio_queue)
            self.text_chunk = second_half
        elif '!' in delta.value:
            first_half = delta.value.split('!')[0]
            second_half = delta.value.split('!')[1]
            self.text_chunk += first_half + '!'
            if not self.text_chunk.isspace():
                await self.text_handler(self.text_chunk.split('!')[0], self.audio_queue)
            self.text_chunk = second_half
        elif '?' in delta.value:
            first_half = delta.value.split('?')[0]
            second_half = delta.value.split('?')[1]
            self.text_chunk += first_half + '?'
            if not self.text_chunk.isspace():
                await self.text_handler(self.text_chunk.split('!')[0], self.audio_queue)
            self.text_chunk = second_half
        elif '\n\n' in delta.value:
            first_half = delta.value.split('\n\n')[0]
            second_half = delta.value.split('\n\n')[1]
            self.text_chunk += first_half
            if not self.text_chunk.isspace():
                await self.text_handler(self.text_chunk.split('\n\n')[0], self.audio_queue)
            self.text_chunk = second_half
        elif '\n' in delta.value:
            first_half = delta.value.split('\n')[0]
            second_half = delta.value.split('\n')[1]
            self.text_chunk += first_half
            if not self.text_chunk.isspace():
                await self.text_handler(self.text_chunk.split('\n')[0], self.audio_queue)
            self.text_chunk = second_half
        else:
            self.text_chunk += delta.value

    async def on_tool_call_created(self, tool_call):
        if tool_call.type == 'file_search':
            self.file_search_used = True

    async def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

    async def finalize(self):
        if self.text_chunk and not self.text_chunk.isspace():
            await self.text_handler(self.text_chunk, self.audio_queue)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

async def send_synthesized(text, audio_queue):
    await audio_queue.put(text)


async def answer_response_new(connection_manager, promt, audio_queue, client_ip, my_assistant):
    start_time = time.time()
    thread = await client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": promt
            }
        ]
    )
    await connection_manager.set_property(client_ip, 'thread', thread.id)
    with EventHandler(send_synthesized, audio_queue) as handler:
        async with client.beta.threads.runs.stream(
                thread_id=thread.id,
                assistant_id=my_assistant,
                event_handler=handler
        ) as stream:
            latency = round(time.time() - start_time, 2)
            await connection_manager.send_text(client_ip, f'Задержка на старт генерации {str(latency)} сек')
            try:
                async for _ in stream:
                    await asyncio.sleep(0.05)
                await handler.finalize()
            except:
                await connection_manager.send_text(client_ip, "LLM task was cancelled")
async def answer_response_ready(connection_manager, promt, audio_queue, client_ip, thread, my_assistant):
    start_time = time.time()
    thread = await client.beta.threads.retrieve(
        thread_id=thread
    )
    await client.beta.threads.messages.create(thread_id=thread.id, role='user', content=promt)
    with EventHandler(send_synthesized, audio_queue) as handler:
        async with client.beta.threads.runs.stream(
                thread_id=thread.id,
                assistant_id=my_assistant,
                event_handler=handler
        ) as stream:
            latency = round(time.time() - start_time, 2)
            await connection_manager.send_text(client_ip, f'Задержка на старт генерации {str(latency)} сек')
            try:
                async for _ in stream:
                    await asyncio.sleep(0.05)
                await handler.finalize()
            except:
                await connection_manager.send_text(client_ip, "LLM task was cancelled")

