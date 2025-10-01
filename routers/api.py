from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, Form
from database import db_handler, minutes_to_seconds, topic_handler
from services.jwt_service import JWTService
from services.payment_service import payment_service
import jwt
import os
from dotenv import load_dotenv
import time
import aiofiles
import json
from pydantic import BaseModel
from typing import Optional, List

# Импорты для Button Realtime
from button_realtime.transcribation_utils import save_and_process_audio
from button_realtime.other_utils import resample_to_16khz

load_dotenv()
JWT_SECRET_KEY = os.getenv("JWT_secret")

router = APIRouter()

# Модели данных для платежей
class CreatePaymentRequest(BaseModel):
    amount: float
    currency: str  # USD или RUB
    payment_method: str  # yandex_pay или paypal
    tariff_name: str
    minutes_to_add: int  # Сколько минут добавить пользователю
    external_order_id: Optional[str] = None

class WebhookPaymentData(BaseModel):
    internal_order_id: str
    external_order_id: str
    status: str
    amount: float
    currency: str
    payment_method: str
    processed_at: int

class TopicRequest(BaseModel):
    title: str
    description: str

class TopicUpdateRequest(BaseModel):
    topic_id: int
    title: str
    description: str

# Модель для CRM обновления баланса пользователя
class UpdateUserBalanceRequest(BaseModel):
    add_remaining_seconds: Optional[int] = None
    add_monthly_seconds: Optional[int] = None
    tariff: Optional[str] = None
    payment_status: Optional[str] = None

# Модель для тарифов
class TariffFeature(BaseModel):
    text: str
    included: bool

class TPricingPlan(BaseModel):
    id: str
    name: str
    price: str
    period: Optional[str] = None
    features: List[TariffFeature]
    popularLabel: Optional[str] = None
    tariff: str
    buttonText: str
    buttonType: str
    disabled: bool

@router.get("/test-db")
async def test_database():
    """Тестовый эндпоинт для проверки работы базы данных"""
    try:
        # Создаем тестового пользователя
        test_user_id = "test_user_123"
        success = await db_handler.create_user(
            user_id=test_user_id,
            user_name="Test User",
            remaining_seconds=minutes_to_seconds(60),  # 60 минут в секундах
            email="test@example.com"
        )
        
        if success:
            # Получаем созданного пользователя
            user = await db_handler.get_user(test_user_id)
            # Конвертируем секунды в минуты для фронтенда
            user_response = user.copy()
            user_response["remaining_time"] = await db_handler.get_remaining_minutes(test_user_id)
            # Удаляем поля remaining_seconds и permanent_seconds, чтобы не путать фронтенд
            if "remaining_seconds" in user_response:
                del user_response["remaining_seconds"]
            if "permanent_seconds" in user_response:
                del user_response["permanent_seconds"]
            
            return {
                "status": "success",
                "message": "База данных работает корректно",
                "test_user": user_response
            }
        else:
            # Пользователь уже существует, просто получаем его
            user = await db_handler.get_user(test_user_id)
            # Конвертируем секунды в минуты для фронтенда
            user_response = user.copy()
            user_response["remaining_time"] = await db_handler.get_remaining_minutes(test_user_id)
            # Удаляем поля remaining_seconds и permanent_seconds, чтобы не путать фронтенд
            if "remaining_seconds" in user_response:
                del user_response["remaining_seconds"]
            if "permanent_seconds" in user_response:
                del user_response["permanent_seconds"]
            
            return {
                "status": "success", 
                "message": "База данных работает корректно (пользователь уже существует)",
                "test_user": user_response
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка базы данных: {str(e)}"
        }

@router.get("/demo-user")
async def get_demo_user():
    """Получить информацию о демо пользователе"""
    try:
        demo_user = await db_handler.get_user("demo_user")
        if demo_user:
            # Конвертируем секунды в минуты для фронтенда
            demo_user_response = demo_user.copy()
            demo_user_response["remaining_time"] = await db_handler.get_remaining_minutes("demo_user")
            
            # Определяем show_topics
            tariff = demo_user.get("tariff", "free")
            permanent_seconds = demo_user.get("permanent_seconds", 0)
            demo_user_response["show_topics"] = tariff != "standart" or permanent_seconds > 0
            
            # Удаляем поля remaining_seconds и permanent_seconds, чтобы не путать фронтенд
            if "remaining_seconds" in demo_user_response:
                del demo_user_response["remaining_seconds"]
            if "permanent_seconds" in demo_user_response:
                del demo_user_response["permanent_seconds"]
            
            return {
                "status": "success",
                "demo_user": demo_user_response
            }
        else:
            return {
                "status": "error",
                "message": "Демо пользователь не найден"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }

@router.get("/check-auth")
async def check_auth(request: Request):
    """Проверка JWT токена из куков"""
    try:
        # Получаем токен из куков
        token = request.cookies.get("auth_token_jwt")
        
        if not token:
            # Нет токена - работаем с неавторизованным пользователем по IP
            client_ip = request.client.host
            user_id = f"user_{client_ip.replace('.', '_')}"
            
            # Ищем пользователя в БД
            user = await db_handler.get_user(user_id)
            
            if not user:
                # Создаем нового гостевого пользователя
                await db_handler.create_user(
                    user_id=user_id,
                    user_name=f"Guest_{client_ip}",
                    remaining_seconds=120  # 2 минуты
                )
                
                # Устанавливаем тариф и статус платежа
                await db_handler.update_user(
                    user_id=user_id,
                    tariff="free",
                    payment_status="unpaid"
                )
                
                # Получаем созданного пользователя
                user = await db_handler.get_user(user_id)
            
            # Определяем show_topics
            tariff = user.get("tariff", "free")
            permanent_seconds = user.get("permanent_seconds", 0)
            show_topics = tariff != "standart" or permanent_seconds > 0
            
            return {
                "status": "unauthorized",
                "message": "Пользователь не авторизован",
                "user": {
                    "id": user["id"],
                    "user_name": user["user_name"],
                    "remaining_time": await db_handler.get_remaining_minutes(user["id"]),
                    "tariff": user.get("tariff"),
                    "payment_status": user.get("payment_status"),
                    "email": user.get("email"),
                    "iat": user.get("iat"),
                    "exp": user.get("exp"),
                    "show_topics": show_topics
                }
            }
        
        # Проверяем токен и получаем данные пользователя
        user = await JWTService.verify_user_from_token(token)
        
        if not user:
            return {
                "status": "unauthorized", 
                "message": "Недействительный токен",
                "user": None
            }
        
        # Определяем show_topics
        tariff = user.get("tariff", "free")
        permanent_seconds = user.get("permanent_seconds", 0)
        show_topics = tariff != "standart" or permanent_seconds > 0
        
        return {
            "status": "authorized",
            "message": "Пользователь авторизован",
            "user": {
                "id": user["id"],
                "user_name": user["user_name"],
                "remaining_time": await db_handler.get_remaining_minutes(user["id"]),  # Возвращаем минуты с округлением вверх
                "tariff": user.get("tariff"),
                "payment_status": user.get("payment_status"),
                "email": user.get("email"),
                "iat": user.get("iat"),
                "exp": user.get("exp"),
                "show_topics": show_topics
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка проверки авторизации: {str(e)}"
        }

@router.get("/tariffs")
async def get_tariffs(request: Request):
    """Получение доступных тарифов с учетом текущего тарифа пользователя"""
    try:
        # Загружаем тарифы из файла
        with open("tariffs.json", "r", encoding="utf-8") as f:
            tariffs_data = json.load(f)
        
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        current_user_tariff = "free"  # По умолчанию для неавторизованных
        
        if token:
            try:
                user_data = await JWTService.verify_user_from_token(token)
                if user_data:
                    current_user_tariff = user_data.get("tariff", "free")
            except:
                pass  # Если токен невалидный, остаемся с free
        
        # Определяем популярный тариф через SQL
        popular_tariff = await get_most_popular_tariff()
        
        # Формируем ответ на основе текущего тарифа
        result_tariffs = []
        
        for tariff in tariffs_data:
            tariff_copy = tariff.copy()
            
            # Логика для Free тарифа
            if current_user_tariff == "free":
                if tariff["tariff"] == "free":
                    tariff_copy["buttonText"] = "Текущий"
                    tariff_copy["buttonType"] = "standard"
                elif tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Купить"
                    tariff_copy["buttonType"] = "secondary"
                else:  # Подписки
                    tariff_copy["buttonText"] = "Начать"
                    tariff_copy["buttonType"] = "secondary"
            
            # Логика для Pay-as-you-go (работает как Free, но показывает все тарифы)
            elif current_user_tariff == "pay-as-you-go":
                if tariff["tariff"] == "free":
                    tariff_copy["buttonText"] = "Бесплатный"
                    tariff_copy["buttonType"] = "secondary"
                elif tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Купить"
                    tariff_copy["buttonType"] = "secondary"
                else:  # Подписки
                    tariff_copy["buttonText"] = "Начать"
                    tariff_copy["buttonType"] = "secondary"
            
            # Логика для подписок (standart, pro)
            else:
                # Не показываем Free тариф для подписчиков
                if tariff["tariff"] == "free":
                    continue
                
                if tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Купить"
                    tariff_copy["buttonType"] = "secondary"
                elif tariff["tariff"] == current_user_tariff:
                    # Текущая подписка
                    tariff_copy["buttonText"] = "Отменить подписку"
                    tariff_copy["buttonType"] = "standard"
                else:
                    # Другие подписки
                    tariff_copy["buttonText"] = "Начать"
                    tariff_copy["buttonType"] = "secondary"
            
            # Добавляем популярный лейбл
            if tariff["tariff"] == popular_tariff:
                tariff_copy["popularLabel"] = "Популярный"
            
            result_tariffs.append(tariff_copy)
        
        return {
            "status": "success",
            "tariffs": result_tariffs,
            "current_tariff": current_user_tariff
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения тарифов: {str(e)}"
        }

async def get_most_popular_tariff():
    """Определяет самый популярный тариф по количеству пользователей"""
    try:
        import aiosqlite
        async with aiosqlite.connect(db_handler.db_path) as db:
            cursor = await db.execute("""
                SELECT tariff, COUNT(*) as count 
                FROM users 
                WHERE tariff IS NOT NULL 
                GROUP BY tariff 
                ORDER BY count DESC 
                LIMIT 1
            """)
            result = await cursor.fetchone()
            return result[0] if result else "pro"  # По умолчанию pro
    except:
        return "pro"  # Fallback

@router.get("/login")
async def login(response: Response, login: str, password: str):
    """Авторизация тестовых пользователей"""
    try:
        # Список допустимых пользователей с паролями
        valid_users = {
            "zeqipe": "test123",
            "dany": "test456", 
            "demo_user": "exampleAIS"
        }
        
        # Проверяем логин и пароль
        if login not in valid_users or password != valid_users[login]:
            return {
                "status": "error",
                "message": "Неверный логин или пароль"
            }
        
        # Получаем пользователя из БД
        user = await db_handler.get_user(login)
        if not user:
            return {
                "status": "error",
                "message": f"Пользователь {login} не найден в БД"
            }
        
        # Создаем JWT токен
        current_time = int(time.time())
        payload = {
            "user_id": user["id"],
            "user_name": user["user_name"],
            "email": user["email"],
            "iat": current_time,
            "exp": current_time + (24 * 60 * 60)  # Токен на 24 часа
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
        
        # Устанавливаем токен в куки
        response.set_cookie(
            key="auth_token_jwt",
            value=token,
            max_age=24 * 60 * 60,  # 24 часа
            httponly=False,  # Изменено на False для доступа из JavaScript
            secure=True,  # Обязательно для SameSite=None
            samesite="none",  # Изменено на none для межсайтовых запросов
            domain=None,  # Позволяет работать с localhost
            path="/"
        )
        
        # Конвертируем секунды в минуты для фронтенда
        user_response = user.copy()
        user_response["remaining_time"] = await db_handler.get_remaining_minutes(user["id"])
        
        # Определяем show_topics
        tariff = user.get("tariff", "free")
        permanent_seconds = user.get("permanent_seconds", 0)
        user_response["show_topics"] = tariff != "standart" or permanent_seconds > 0
        
        # Удаляем поля remaining_seconds и permanent_seconds, чтобы не путать фронтенд
        if "remaining_seconds" in user_response:
            del user_response["remaining_seconds"]
        if "permanent_seconds" in user_response:
            del user_response["permanent_seconds"]
        
        return {
            "status": "success",
            "message": "Авторизация успешна",
            "user": user_response
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка авторизации: {str(e)}"
        }

@router.get("/logout")
async def logout(response: Response):
    """Выход из системы - удаление токена из куков"""
    try:
        # Удаляем куку с токеном
        response.delete_cookie(
            key="auth_token_jwt",
            httponly=False,
            secure=True,  # Обязательно для SameSite=None
            samesite="none",  # Изменено на none для межсайтовых запросов
            domain=None,
            path="/"
        )
        
        return {
            "status": "success",
            "message": "Выход выполнен успешно"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка выхода: {str(e)}"
        }

# Button Realtime - эндпоинт для отправки аудио от клиента
@router.post("/upload-audio/")
async def upload_audio(file: UploadFile, request: Request, client_id: str = Form(...)):
    """Эндпоинт для загрузки аудио файлов (Button Realtime режим)"""
    from routers.websocket import button_connection_manager
    
    client_ip = client_id
    
    # Проверяем, есть ли WebSocket соединение для этого клиента
    audio_queue = await button_connection_manager.get_property(client_ip,'queue')
    play_queue = await button_connection_manager.get_property(client_ip,'play')
    
    if audio_queue is None or play_queue is None:
        raise HTTPException(
            status_code=400, 
            detail=f"WebSocket connection not found for client_id: {client_id}. Ensure WebSocket is connected first."
        )
    
    await button_connection_manager.send_text(client_ip,'В обработку принят файл.')
    
    # Очищаем очереди
    while not audio_queue.empty():
        await audio_queue.get()
    while not play_queue.empty():
        await play_queue.get()
    
    # Сохраняем файл
    filename = str(round(time.time()))+'.wav'
    file_path = f"temp/{filename}"
    
    # Создаем папку temp если не существует
    os.makedirs("temp", exist_ok=True)
    
    # Запускаем таймер обработки
    await button_connection_manager.set_property(client_ip, 'processing_start_time', time.time())
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    # Получаем длительность аудио файла
    import wave
    with wave.open(file_path, 'rb') as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()
        duration = frames / sample_rate
        await button_connection_manager.set_property(client_ip, 'voice_duration', duration)
        
    resampled_file_path = resample_to_16khz(file_path)
    await save_and_process_audio(button_connection_manager, client_ip, resampled_file_path)
    
    return {"status": "success", "message": "Файл обработан"}

# Платежные эндпоинты
@router.post("/create-payment")
async def create_payment(request: Request, payment_data: CreatePaymentRequest):
    """Создание платежа через внешний API"""
    
    # Проверяем авторизацию пользователя
    token = request.cookies.get("auth_token_jwt")
    if not token:
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    
    user_data = await JWTService.verify_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Неверный токен")
    
    user_id = user_data["id"]
    
    # Валидация данных
    if payment_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")
    
    if payment_data.currency not in ["USD", "RUB"]:
        raise HTTPException(status_code=400, detail="Поддерживаются только USD и RUB")
    
    if payment_data.payment_method not in ["yandex_pay", "paypal"]:
        raise HTTPException(status_code=400, detail="Поддерживаются только yandex_pay и paypal")
    
    try:
        # Создаем платеж через внешний API
        result = await payment_service.create_payment(
            user_id=user_id,
            amount=payment_data.amount,
            currency=payment_data.currency,
            payment_method=payment_data.payment_method,
            tariff_name=payment_data.tariff_name,
            minutes_to_add=payment_data.minutes_to_add,
            external_order_id=payment_data.external_order_id
        )
        
        if result["success"]:
            return {
                "status": "success",
                "payment_url": result["payment_url"],
                "internal_order_id": result["internal_order_id"],
                "external_order_id": result["external_order_id"]
            }
        else:
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result["error"]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания платежа: {str(e)}")

@router.get("/payment-status/{internal_order_id}")
async def get_payment_status(internal_order_id: str, request: Request):
    """Получение статуса платежа"""
    
    # Проверяем авторизацию
    token = request.cookies.get("auth_token_jwt")
    if not token:
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    
    user_data = await JWTService.verify_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Неверный токен")
    
    try:
        result = await payment_service.get_payment_status(internal_order_id)
        
        if result["success"]:
            return {
                "status": "success",
                "payment_data": result["data"]
            }
        else:
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result["error"]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статуса: {str(e)}")


@router.post("/webhook/payment")
async def webhook_payment(request: Request):
    """Webhook для получения уведомлений о платежах"""
    
    # Проверяем авторизацию webhook (Bearer токен)
    auth_header = request.headers.get("authorization")
    expected_token = os.getenv("WEBHOOK_AUTH_TOKEN")
    
    if expected_token and auth_header != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="Unauthorized webhook")
    
    try:
        # Получаем данные webhook
        webhook_data = await request.json()
        
        # Валидируем структуру данных
        try:
            payment_data = WebhookPaymentData(**webhook_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Неверная структура данных: {str(e)}")
        
        # Проверяем статус платежа
        if payment_data.status != "SUCCESS":
            return {"received": True, "message": "Payment not successful, ignoring"}
        
        # Обновляем данные пользователя в базе данных
        user_id = payment_data.user_id
        minutes_to_add = payment_data.minutes_to_add
        
        # Получаем текущие данные пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            # Создаем пользователя если не существует
            await db_handler.create_user(
                user_id=user_id,
                user_name=f"user_{user_id}",
                remaining_seconds=minutes_to_seconds(minutes_to_add),  # Конвертируем минуты в секунды
                email=None,
                iat=None,
                exp=None
            )
        else:
            # Добавляем минуты к существующему балансу (используем новый метод)
            await db_handler.add_minutes(user_id, minutes_to_add)
        
        # Обновляем платежную информацию
        await db_handler.update_user(
            user_id=user_id,
            tariff=payment_data.tariff_name,
            payment_date=payment_data.processed_at,
            payment_status="paid"
        )
        
        return {
            "received": True,
            "message": "Payment processed successfully",
            "user_id": user_id,
            "minutes_added": minutes_to_add
        }
        
    except HTTPException:
        raise

@router.post("/topics")
async def create_topic(request: Request, topic_data: TopicRequest):
    """Создание новой темы"""
    try:
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        if not token:
            raise HTTPException(status_code=401, detail="Токен не найден")
        
        # Проверяем токен и получаем данные пользователя
        user_data = await JWTService.verify_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_id = user_data["id"]
        
        # Создаем тему через интерфейсный слой
        result = await topic_handler.create_topic(user_id, topic_data.title, topic_data.description)
        
        if result["status"] == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания темы: {str(e)}")

@router.get("/topics")
async def get_user_topics(request: Request):
    """Получение всех тем пользователя"""
    try:
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        if not token:
            raise HTTPException(status_code=401, detail="Токен не найден")
        
        # Проверяем токен и получаем данные пользователя
        user_data = await JWTService.verify_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_id = user_data["id"]
        
        # Получаем темы через интерфейсный слой
        result = await topic_handler.get_user_topics(user_id)
        
        if result["status"] == "success":
            return result
        else:
            return {"status": "error", "detail": result["message"]}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения тем: {str(e)}")

@router.put("/topics")
async def update_topic(request: Request, topic_data: TopicUpdateRequest):
    """Обновление темы"""
    try:
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        if not token:
            raise HTTPException(status_code=401, detail="Токен не найден")
        
        # Проверяем токен и получаем данные пользователя
        user_data = await JWTService.verify_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_id = user_data["id"]
        
        # Обновляем тему через интерфейсный слой
        result = await topic_handler.update_topic(topic_data.topic_id, user_id, topic_data.title, topic_data.description)
        
        if result["status"] == "success":
            return result
        elif result["status"] == "forbidden":
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления темы: {str(e)}")

@router.delete("/topics/{topic_id}")
async def delete_topic(request: Request, topic_id: int):
    """Удаление темы"""
    try:
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        if not token:
            raise HTTPException(status_code=401, detail="Токен не найден")
        
        # Проверяем токен и получаем данные пользователя
        user_data = await JWTService.verify_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        user_id = user_data["id"]
        
        # Удаляем тему через интерфейсный слой
        result = await topic_handler.delete_topic(topic_id, user_id)
        
        if result["status"] == "success":
            return result
        elif result["status"] == "forbidden":
            raise HTTPException(status_code=403, detail="Доступ запрещен")
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления темы: {str(e)}")

# CRM роуты
@router.get("/crm/api/tariffs")
async def get_crm_tariffs():
    """CRM: Получение списка тарифов"""
    try:
        # Загружаем тарифы из файла
        import json
        with open("tariffs.json", "r", encoding="utf-8") as f:
            tariffs_data = json.load(f)
        
        return {
            "status": "success",
            "tariffs": tariffs_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка получения тарифов: {str(e)}"
        }

@router.get("/crm/api/user/{user_id}/balance")
async def get_crm_user_balance(user_id: str):
    """CRM: Получение баланса конкретного пользователя"""
    try:
        # Получаем пользователя из БД
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "status": "success",
            "data": {
                "user_id": user["id"],
                "user_name": user["user_name"],
                "remaining_seconds": user.get("remaining_seconds", 0),
                "monthly_seconds": 0,  # TODO: добавить поле в БД если нужно
                "tariff": user.get("tariff", "free"),
                "payment_status": user.get("payment_status", "unpaid")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Ошибка получения баланса: {str(e)}"
        }

@router.put("/crm/api/user/{user_id}/balance")
async def update_crm_user_balance(user_id: str, balance_data: UpdateUserBalanceRequest):
    """CRM: Обновление баланса пользователя"""
    try:
        # Проверяем существование пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        updates = {}
        
        # Обрабатываем начисление несгораемых секунд
        if balance_data.add_remaining_seconds is not None:
            current_seconds = user.get("remaining_seconds", 0)
            new_seconds = current_seconds + balance_data.add_remaining_seconds
            updates['remaining_seconds'] = max(0, new_seconds)
        
        # TODO: Обрабатываем начисление месячных секунд (когда добавим поле в БД)
        # if balance_data.add_monthly_seconds is not None:
        #     current_monthly = user.get("monthly_seconds", 0)
        #     new_monthly = current_monthly + balance_data.add_monthly_seconds
        #     updates['monthly_seconds'] = max(0, new_monthly)
        
        # Обрабатываем смену тарифа
        if balance_data.tariff is not None:
            updates['tariff'] = balance_data.tariff
            
        # Обрабатываем статус оплаты
        if balance_data.payment_status is not None:
            updates['payment_status'] = balance_data.payment_status
        
        # Применяем изменения если есть что обновлять
        if updates:
            success = await db_handler.update_user(user_id, **updates)
            if not success:
                raise HTTPException(status_code=500, detail="Ошибка обновления данных")
        
        # Возвращаем обновленные данные
        updated_user = await db_handler.get_user(user_id)
        
        return {
            "status": "success",
            "message": "Баланс обновлен",
            "data": {
                "user_id": updated_user["id"],
                "user_name": updated_user["user_name"],
                "remaining_seconds": updated_user.get("remaining_seconds", 0),
                "monthly_seconds": 0,  # TODO: когда добавим поле в БД
                "tariff": updated_user.get("tariff", "free"),
                "payment_status": updated_user.get("payment_status", "unpaid")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка обновления баланса: {str(e)}"
        }


