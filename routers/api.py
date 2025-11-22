from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, Form
from fastapi.responses import FileResponse
from database import db_handler, minutes_to_seconds, topic_handler
from services.jwt_service import JWTService
from services.payment_service import payment_service
from services import payment_manager
from services.language_cache import language_cache, exchange_rate_cache
from services.report_generator import report_generator
from services.config_parser import get_config_parser
import jwt
import os
from dotenv import load_dotenv
import time
import aiofiles
import json
import uuid
import math
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from routers.websocket import get_user_id_from_cookies

# Импорты для Button Realtime
from button_realtime.transcribation_utils import save_and_process_audio
from button_realtime.other_utils import resample_to_16khz

load_dotenv()
JWT_SECRET_KEY = os.getenv("JWT_secret")

router = APIRouter()

@router.get("/session-id")
async def get_session_id(request: Request):
    """Получение уникального ID сессии для WebSocket соединения"""
    # Получаем user_id из JWT токена в куки
    user_id, is_authenticated = await get_user_id_from_cookies(request)
    
    # Если неавторизован - проверяем существующий аккаунт по IP
    if not user_id:
        client_ip_address = request.client.host
        user_id = f"user_{client_ip_address.replace('.', '_')}"
        
        # Проверяем существует ли пользователь
        user = await db_handler.get_user(user_id)
        if not user:
            # Аккаунт не существует - разрешаем подключение (создастся при WebSocket)
            session_id = str(uuid.uuid4())
            return {"session_id": session_id}
    
    # Проверяем баланс для существующих пользователей
    remaining_seconds = await db_handler.get_remaining_seconds(user_id)
    if remaining_seconds <= 0:
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещен. У вас закончились минуты. Пожалуйста, пополните баланс."
        )
    
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}

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
    # Для подписок: уникальный ID транзакции (защита от повторной обработки)
    charge_id: Optional[str] = None
    # custom_data поля встраиваются в корень по документации Airalo API
    user_id: Optional[str] = None
    product_name: Optional[str] = None
    email: Optional[str] = None
    minutes: Optional[int] = None
    tariff_id: Optional[str] = None
    subscription_months: Optional[int] = None

class PurchaseSubscriptionRequest(BaseModel):
    tariff_id: str
    payment_system: str  # "yookassa" или "paypal"

class TopicRequest(BaseModel):
    title: str
    description: str

class TopicUpdateRequest(BaseModel):
    topic_id: int
    title: str
    description: str

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
        with open("document/tariffs.json", "r", encoding="utf-8") as f:
            tariffs_data = json.load(f)
        
        # Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        current_user_tariff = "free"  # По умолчанию для неавторизованных
        current_user_status = "user"  # По умолчанию статус обычного пользователя
        
        if token:
            try:
                user_data = await JWTService.verify_user_from_token(token)
                if user_data:
                    current_user_tariff = user_data.get("tariff", "free")
                    # Получаем статус пользователя из БД
                    user_db_data = await db_handler.get_user(user_data.get("id"))
                    if user_db_data:
                        current_user_status = user_db_data.get("status", "user")
            except:
                pass  # Если токен невалидный, остаемся с free и user
        
        # Проверяем локализацию и конвертируем цены в рубли если нужно
        locale = request.cookies.get("iec_preferred_locale", "en")
        exchange_rate = None
        
        if locale == "ru":
            # Получаем курс из кэша (автоматически обновится если TTL истек)
            exchange_rate = await exchange_rate_cache.get_exchange_rate()
        
        # Определяем популярный тариф из файла тарифов (если задан)
        popular_tariff = None
        for t in tariffs_data:
            # Поддержка двух вариантов разметки в JSON: popular=true или наличие popularLabel
            if t.get("popular") is True or t.get("popularLabel"):
                popular_tariff = t.get("tariff")
                break
        # Если в тарифах не отмечен популярный — не проставляем popularLabel вовсе
        
        # Формируем ответ на основе текущего тарифа
        result_tariffs = []
        
        for tariff in tariffs_data:
            # Проверяем доступность тарифа по статусу
            tariff_statuses = tariff.get("statuses", [])
            
            # Если statuses пустой, null или содержит "all" - доступен всем
            if not tariff_statuses or "all" in tariff_statuses:
                pass  # Тариф доступен
            # Если статус пользователя не в списке разрешенных - скрываем тариф
            elif current_user_status not in tariff_statuses:
                continue  # Пропускаем этот тариф
            
            tariff_copy = tariff.copy()
            
            # Конвертируем цену в рубли если локаль RU и есть курс
            if exchange_rate and locale == "ru":
                try:
                    # Извлекаем числовое значение из строки типа "$15" или "$0"
                    price_str = tariff_copy.get("price", "$0")
                    price_usd = float(price_str.replace("$", "").strip())
                    
                    # Конвертируем в рубли и округляем вверх
                    price_rub = math.ceil(price_usd * exchange_rate)
                    
                    # Заменяем цену на рублевый формат
                    tariff_copy["price"] = f"{price_rub} ₽"
                except:
                    pass  # Если не удалось сконвертировать, оставляем исходную цену
            
            # Логика для Free тарифа
            if current_user_tariff == "free":
                if tariff["tariff"] == "free":
                    tariff_copy["buttonText"] = "Current"
                    tariff_copy["buttonType"] = "standard"
                elif tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Buy"
                    tariff_copy["buttonType"] = "secondary"
                else:  # Подписки
                    tariff_copy["buttonText"] = "Start"
                    tariff_copy["buttonType"] = "secondary"
            
            # Логика для Pay-as-you-go (работает как Free, но показывает все тарифы)
            elif current_user_tariff == "pay-as-you-go":
                if tariff["tariff"] == "free":
                    tariff_copy["buttonText"] = "Free"
                    tariff_copy["buttonType"] = "secondary"
                elif tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Buy"
                    tariff_copy["buttonType"] = "secondary"
                else:  # Подписки
                    tariff_copy["buttonText"] = "Start"
                    tariff_copy["buttonType"] = "secondary"
            
            # Логика для подписок (standart, pro)
            else:
                # Не показываем Free тариф для подписчиков
                if tariff["tariff"] == "free":
                    continue
                
                if tariff["tariff"] == "pay-as-you-go":
                    tariff_copy["buttonText"] = "Buy"
                    tariff_copy["buttonType"] = "secondary"
                elif tariff["tariff"] == current_user_tariff:
                    # Текущая подписка
                    tariff_copy["buttonText"] = "Cancel subscription"
                    tariff_copy["buttonType"] = "standard"
                else:
                    # Другие подписки
                    tariff_copy["buttonText"] = "Start"
                    tariff_copy["buttonType"] = "secondary"
            
            # Добавляем популярный лейбл (только если тариф помечен популярным в JSON)
            if popular_tariff and tariff["tariff"] == popular_tariff:
                tariff_copy["popularLabel"] = "Popular"
            
            # Добавляем hasModal и paymentButtons на основе локали и типа тарифа
            from config import MODAL_LANGUAGES, ONE_TIME_PAYMENT_SYSTEMS, SUBSCRIPTION_PAYMENT_SYSTEMS, DEFAULT_PAYMENT_SYSTEM
            
            # Определяем hasModal по языку
            has_modal = locale in MODAL_LANGUAGES
            tariff_copy["hasModal"] = has_modal
            
            # Определяем paymentButtons
            if not has_modal:
                # Для всех языков кроме MODAL_LANGUAGES - дефолтная система
                tariff_copy["paymentButtons"] = DEFAULT_PAYMENT_SYSTEM
            else:
                # Для языков с модалкой - определяем по типу тарифа
                tariff_type = tariff.get("type")
                if tariff_type == "one-time":
                    tariff_copy["paymentButtons"] = ONE_TIME_PAYMENT_SYSTEMS
                elif tariff_type == "subscription":
                    tariff_copy["paymentButtons"] = SUBSCRIPTION_PAYMENT_SYSTEMS
                else:
                    # Для тарифов без типа или с неизвестным типом
                    tariff_copy["paymentButtons"] = []
            
            result_tariffs.append(tariff_copy)
        
        # Формируем ответ
        response = {
            "status": "success",
            "tariffs": result_tariffs,
            "current_tariff": current_user_tariff
        }
        
        # Если локаль RU, но курс не получен - добавляем ошибку
        if locale == "ru" and exchange_rate is None:
            response["err"] = "не получены данные по текущему курсу"
        
        return response
        
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

@router.get("/language")
async def get_language(request: Request):
    """Получение текущего языка из куков"""
    # Получаем язык из куков, если нет - возвращаем null
    # Фронтенд сам решит, использовать ли "en" по умолчанию
    language = request.cookies.get("iec_preferred_locale")
    
    return {"language": language if language else None}

@router.get("/language/settings")
async def get_language_settings(request: Request):
    """Получение списка поддерживаемых языков (с кэшированием)"""
    # Получаем языки из кэша (автоматически обновится если TTL истек)
    languages = await language_cache.get_languages()
    
    # Получаем текущий язык из куки
    # Если куки нет - возвращаем null, фронтенд сам установит "en" если нужно
    current_locale = request.cookies.get("iec_preferred_locale")
    
    return {
        "status": "success",
        "languages": languages,
        "currentLocale": current_locale if current_locale else None
    }

class LanguageRequest(BaseModel):
    language: str

@router.put("/language")
async def set_language(response: Response, request: LanguageRequest):
    """Установка языка в куки"""
    language = request.language
    
    # Получаем список поддерживаемых языков из кэша
    supported_languages = await language_cache.get_languages()
    
    # Проверяем, что язык поддерживается
    if language not in supported_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый язык. Доступные языки: {', '.join(supported_languages)}"
        )
    
    # Устанавливаем куку с языком
    response.set_cookie(
        key="iec_preferred_locale",
        value=language,
        max_age=365 * 24 * 60 * 60,  # 1 год
        httponly=False,
        secure=False,  # Для разработки
        samesite="lax",
        domain=None,
        path="/"
    )
    
    return {"status": "success", "language": language}

@router.delete("/language")
async def delete_language(response: Response):
    """Удаление куки с языком"""
    response.delete_cookie(
        key="iec_preferred_locale",
        httponly=False,
        secure=False,
        samesite="lax",
        domain=None,
        path="/"
    )
    
    return {"status": "success", "message": "Язык сброшен"}

@router.get("/video")
async def get_video():
    """Получение ссылки на видео из document/ConfigData.txt (секция -> Media)"""
    try:
        parser = get_config_parser()
        video_url = parser.get_media()
        
        # Проверяем что ссылка не пустая
        if not video_url:
            raise HTTPException(
                status_code=500,
                detail="Ссылка на видео отсутствует в ConfigData.txt"
            )
        
        return {
            "status": "success",
            "videoUrl": video_url
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Файл ConfigData.txt не найден: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при чтении ConfigData.txt: {str(e)}"
        )

@router.get("/help")
async def get_help():
    """Получение справочной информации из document/ConfigData.txt (секция -> Help)"""
    try:
        parser = get_config_parser()
        help_items = parser.get_help()
        
        return {
            "status": "success",
            "items": help_items
        }
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Файл ConfigData.txt не найден: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения справки: {str(e)}")

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
        
        # Создаем JWT токен с вложенной структурой data (как у внешней системы)
        current_time = int(time.time())
        payload = {
            "iss": "https://fluentgo.ai",
            "iat": current_time,
            "exp": current_time + (24 * 60 * 60),  # Токен на 24 часа
            "data": {
                "user_id": user["id"],
                "email": user["email"],
                "name": user["user_name"]
            }
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
        
        # Устанавливаем токен в куки
        response.set_cookie(
            key="auth_token_jwt",
            value=token,
            max_age=24 * 60 * 60,  # 24 часа
            httponly=True,  # Защита от XSS атак
            secure=True,  # Только через HTTPS
            samesite="lax",  # Защита от CSRF
            domain=".iec.study",  # Работает на всех поддоменах
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
async def logout(request: Request, response: Response):
    """Выход из системы - удаление токена из куков"""
    try:
        # Проверяем наличие токена
        token = request.cookies.get("auth_token_jwt")
        
        if not token:
            raise HTTPException(status_code=404, detail="Токен не найден")
        
        # Удаляем куку с токеном (параметры должны совпадать с установкой)
        response.delete_cookie(
            key="auth_token_jwt",
            httponly=True,
            secure=True,
            samesite="lax",
            domain=".iec.study",
            path="/"
        )
        
        return {
            "status": "success",
            "message": "Выход выполнен успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка выхода: {str(e)}")

# Button Realtime - эндпоинт для отправки аудио от клиента
@router.post("/upload-audio/")
async def upload_audio(file: UploadFile, request: Request, session_id: str = Form(...)):
    """Эндпоинт для загрузки аудио файлов (Button Realtime режим)"""
    from routers.websocket import button_connection_manager
    
    # Проверяем, есть ли WebSocket соединение для этого клиента
    audio_queue = await button_connection_manager.get_property(session_id,'queue')
    play_queue = await button_connection_manager.get_property(session_id,'play')
    
    if audio_queue is None or play_queue is None:
        raise HTTPException(
            status_code=400, 
            detail=f"WebSocket connection not found for session_id: {session_id}. Ensure WebSocket is connected first."
        )
    
    # Проверяем оставшееся время перед обработкой (только для HTTP - предотвращаем загрузку файлов)
    user_id = await button_connection_manager.get_property(session_id, 'user_id')
    if user_id:
        remaining_seconds = await db_handler.get_remaining_seconds(user_id)
        if remaining_seconds <= 0:
            await button_connection_manager.send_text(
                session_id, 
                "У вас закончились минуты. Пожалуйста, пополните баланс для продолжения."
            )
            # Разрываем соединение
            await button_connection_manager.disconnect(session_id)
            raise HTTPException(
                status_code=403,
                detail="У вас закончились минуты. Пожалуйста, пополните баланс для продолжения."
            )
    
    await button_connection_manager.send_text(session_id,'В обработку принят файл.')
    
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
    await button_connection_manager.set_property(session_id, 'processing_start_time', time.time())
    
    # Проверяем размер файла перед сохранением
    content = await file.read()
    if len(content) == 0:
        await button_connection_manager.send_text(session_id, "Ошибка: загруженный файл пустой")
        raise HTTPException(status_code=400, detail="Файл пустой")
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(content)
    
    # Получаем длительность аудио файла
    import wave
    
    # Проверяем что файл существует и не пустой
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        await button_connection_manager.send_text(session_id, "Ошибка: загруженный файл пустой или поврежден")
        raise HTTPException(status_code=400, detail="Файл пустой или поврежден")
    
    try:
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            duration = frames / sample_rate
            await button_connection_manager.set_property(session_id, 'voice_duration', duration)
    except (wave.Error, EOFError) as e:
        await button_connection_manager.send_text(session_id, f"Ошибка обработки аудио файла: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Некорректный аудио файл: {str(e)}")
        
    resampled_file_path = resample_to_16khz(file_path)
    await save_and_process_audio(button_connection_manager, session_id, resampled_file_path)
    
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
    """
    Webhook для получения уведомлений о платежах от Airalo API
    
    Airalo отправляет POST запрос с данными о завершенном платеже.
    Мы автоматически начисляем минуты и обновляем тариф пользователя.
    """
    
    # Проверяем авторизацию webhook (Bearer токен от Airalo)
    auth_header = request.headers.get("authorization")
    expected_token = os.getenv("WEBHOOK_AUTH_TOKEN")
    
    if expected_token and auth_header != f"Bearer {expected_token}":
        payment_manager.log_payment("ERROR", "Неавторизованный webhook запрос", {
            "auth_header": auth_header,
            "ip": request.client.host if request.client else None
        })
        raise HTTPException(status_code=401, detail="Unauthorized webhook")
    
    try:
        # Получаем данные webhook
        webhook_data = await request.json()
        
        payment_manager.log_payment("INFO", "Получен webhook от Airalo API", {
            "data": webhook_data
        })
        
        # Валидируем структуру данных
        try:
            payment_data = WebhookPaymentData(**webhook_data)
        except Exception as e:
            payment_manager.log_payment("ERROR", f"Неверная структура webhook данных: {str(e)}", {
                "data": webhook_data,
                "exception": str(e)
            })
            raise HTTPException(status_code=400, detail=f"Неверная структура данных: {str(e)}")
        
        # Проверка на повторную обработку (idempotency)
        # По документации @PAYPAL.md (строки 320, 358-361): "charge_id может повторяться"
        # Для подписок каждое списание имеет уникальный charge_id
        if payment_data.charge_id:
            if payment_data.charge_id in payment_manager.processed_charge_ids:
                payment_manager.log_payment("INFO", f"Webhook с charge_id {payment_data.charge_id} уже был обработан, пропускаем", {
                    "charge_id": payment_data.charge_id,
                    "payment_id": payment_data.external_order_id
                })
                return {
                    "received": True, 
                    "message": "Duplicate charge_id, already processed",
                    "charge_id": payment_data.charge_id
                }
        
        # Проверяем статус платежа (по документации: SUCCESS для успешных)
        if payment_data.status.upper() != "SUCCESS":
            payment_manager.log_payment("INFO", f"Webhook со статусом {payment_data.status}, пропускаем", {
                "payment_id": payment_data.external_order_id
            })
            return {"received": True, "message": f"Payment status: {payment_data.status}"}
        
        # Извлекаем данные из custom_data (они встроены в корень по документации)
        user_id = payment_data.user_id
        minutes = payment_data.minutes or 0
        tariff_id = payment_data.tariff_id
        
        if not user_id:
            payment_manager.log_payment("ERROR", "user_id отсутствует в webhook данных", {
                "payment_id": payment_data.external_order_id
            })
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Получаем текущие данные пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            payment_manager.log_payment("ERROR", f"Пользователь {user_id} не найден", {
                "payment_id": payment_data.external_order_id
            })
            return {
                "received": True,
                "error": "User not found",
                "user_id": user_id
            }
        
        # Проверяем есть ли информация о платеже в нашем хранилище
        payment_info = payment_manager.active_payments.get(payment_data.external_order_id)
        
        if payment_info:
            # Есть в хранилище - определяем тип минут
            is_permanent = payment_info.get("is_permanent", False)
            
            if is_permanent:
                # Несгораемые минуты (для разовых покупок Buy)
                new_permanent = user.get("permanent_seconds", 0) + (minutes * 60)
                await db_handler.update_user(
                    user_id=user_id,
                    permanent_seconds=new_permanent,
                    payment_status="active"
                )
                payment_manager.log_payment("INFO", f"Начислены несгораемые минуты через webhook", {
                    "user_id": user_id,
                    "minutes": minutes,
                    "payment_id": payment_data.external_order_id
                })
            else:
                # Сгораемые минуты (для подписок Start)
                # ВАЖНО: Заменяем старые минуты, а не добавляем (обновление тарифа)
                new_remaining = minutes * 60
                await db_handler.update_user(
                    user_id=user_id,
                    remaining_seconds=new_remaining,
                    tariff=tariff_id,
                    payment_status="active"
                )
                payment_manager.log_payment("INFO", f"Установлены сгораемые минуты через webhook (старые обнулены)", {
                    "user_id": user_id,
                    "new_minutes": minutes,
                    "tariff": tariff_id,
                    "payment_id": payment_data.external_order_id
                })
            
            # Удаляем из хранилища после успешной обработки
            del payment_manager.active_payments[payment_data.external_order_id]
            
        else:
            # Нет в хранилище - начисляем как несгораемые минуты (безопасный вариант)
            payment_manager.log_payment("WARNING", f"Платеж не найден в хранилище, начисляем как несгораемые", {
                "payment_id": payment_data.external_order_id,
                "user_id": user_id
            })
            
            new_permanent = user.get("permanent_seconds", 0) + (minutes * 60)
            await db_handler.update_user(
                user_id=user_id,
                permanent_seconds=new_permanent,
                payment_status="active"
            )
        
        # Добавляем charge_id в обработанные (защита от повторов)
        if payment_data.charge_id:
            payment_manager.processed_charge_ids.add(payment_data.charge_id)
            payment_manager.log_payment("INFO", f"charge_id {payment_data.charge_id} добавлен в обработанные", {
                "charge_id": payment_data.charge_id,
                "payment_id": payment_data.external_order_id
            })
        
        return {
            "received": True,
            "message": "Payment processed successfully",
            "user_id": user_id,
            "minutes_added": minutes,
            "payment_id": payment_data.external_order_id
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
        # 1. Читаем базовые темы из файла
        base_topics = await get_base_topics_from_file()
        
        # 2. Получаем JWT токен из куков
        token = request.cookies.get("auth_token_jwt")
        user_topics = []
        
        # 3. Если авторизован - получаем темы из БД
        if token:
            user_data = await JWTService.verify_user_from_token(token)
            if user_data:
                user_id = user_data["id"]
                result = await topic_handler.get_user_topics(user_id)
                if result["status"] == "success":
                    # Добавляем base: false к пользовательским темам
                    for topic in result["topics"]:
                        topic["base"] = False
                    user_topics = result["topics"]
        
        # 4. Генерируем уникальные ID для базовых тем
        used_ids = {topic["id"] for topic in user_topics}
        base_topics_with_ids = await assign_unique_ids_to_base_topics(base_topics, used_ids)
        
        # 5. Объединяем все темы
        all_topics = user_topics + base_topics_with_ids
        
        return {
            "status": "success",
            "topics": all_topics
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения тем: {str(e)}")

async def get_base_topics_from_file():
    """Получение базовых тем из ConfigData.txt (секция -> Topic)"""
    try:
        parser = get_config_parser()
        topics = parser.get_topics()
        
        # Добавляем поле base: True к каждой теме
        base_topics = []
        for topic in topics[:6]:  # Берем только первые 6 тем
            base_topics.append({
                "title": topic["title"],
                "description": topic["description"],
                "base": True
            })
        
        return base_topics
        
    except FileNotFoundError:
        return []
    except Exception as e:
        return []

async def assign_unique_ids_to_base_topics(base_topics, used_ids):
    """Присваиваем уникальные ID базовым темам, заполняя пропуски в ID пользовательских тем"""
    base_topics_with_ids = []
    
    # Сортируем занятые ID для поиска пропусков
    sorted_used_ids = sorted(used_ids)
    
    # Находим все свободные ID (пропуски)
    free_ids = []
    if sorted_used_ids:
        # Проверяем пропуски между существующими ID
        for i in range(len(sorted_used_ids) - 1):
            current_id = sorted_used_ids[i]
            next_id = sorted_used_ids[i + 1]
            # Добавляем все ID между current_id и next_id
            for free_id in range(current_id + 1, next_id):
                free_ids.append(free_id)
        
        # Добавляем ID после последнего занятого
        last_used_id = sorted_used_ids[-1]
        for free_id in range(last_used_id + 1, last_used_id + 1 + len(base_topics)):
            free_ids.append(free_id)
    else:
        # Если нет занятых ID, начинаем с 1
        free_ids = list(range(1, len(base_topics) + 1))
    
    # Присваиваем свободные ID базовым темам
    for i, topic in enumerate(base_topics):
        if i < len(free_ids):
            topic_with_id = topic.copy()
            topic_with_id["id"] = free_ids[i]
            base_topics_with_ids.append(topic_with_id)
        else:
            # Если не хватает свободных ID, генерируем новые
            topic_with_id = topic.copy()
            topic_with_id["id"] = max(used_ids) + i + 1 if used_ids else i + 1
            base_topics_with_ids.append(topic_with_id)
    
    return base_topics_with_ids

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

@router.post("/subscription/refuse")
async def refuse_subscription(request: Request):
    """Отмена подписки пользователя"""
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
        
        # Получаем текущую подписку пользователя
        user = await db_handler.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        current_tariff = user.get("tariff", "free")
        
        # Отменяем подписку и устанавливаем free тариф
        success = await db_handler.update_user(
            user_id=user_id,
            tariff="free",
            payment_status="cancelled"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Не удалось отменить подписку")
        
        return {
            "status": "success",
            "message": "Подписка успешно отменена",
            "previous_tariff": current_tariff,
            "current_tariff": "free"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отмены подписки: {str(e)}")

@router.get("/doc/policy/")
async def get_policy_document():
    """Получение PDF документа с политикой конфиденциальности"""
    file_path = "document/Fluent Terms of Service.pdf"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Документ не найден")
    
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename="Fluent_Terms_of_Service.pdf"
    )

# ========================================
# Новая система платежей через Airalo API
# ========================================

@router.post("/subscription/purchase")
async def purchase_subscription(request: Request, data: PurchaseSubscriptionRequest):
    """
    Создание платежа для покупки тарифа
    
    Принимает:
        - tariff_id: ID тарифа из tariffs.json
        - payment_system: "yookassa" или "paypal"
    
    Возвращает:
        - paymentUrl: URL для оплаты
        - status: "await" (ожидание оплаты)
        - paymentId: ID платежа для проверки статуса
    """
    try:
        # 1. Проверяем авторизацию через JWT в куках
        token = request.cookies.get("auth_token_jwt")
        if not token:
            raise HTTPException(status_code=401, detail="Пользователь не авторизован")
        
        user_data = await JWTService.verify_user_from_token(token)
        if not user_data:
            raise HTTPException(status_code=401, detail="Неверный токен авторизации")
        
        # Получаем полные данные пользователя из БД
        user = await db_handler.get_user(user_data["id"])
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден в базе")
        
        # 2. Валидация payment_system
        if data.payment_system not in ["yookassa", "paypal"]:
            raise HTTPException(
                status_code=400, 
                detail="Некорректная платежная система. Допустимые значения: yookassa, paypal"
            )
        
        # 3. Загружаем тарифы из файла
        try:
            with open("document/tariffs.json", "r", encoding="utf-8") as f:
                tariffs_data = json.load(f)
        except Exception as e:
            payment_manager.log_payment("ERROR", f"Ошибка чтения tariffs.json: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка загрузки тарифов")
        
        # 4. Находим тариф по ID
        tariff = None
        for t in tariffs_data:
            if t.get("id") == data.tariff_id or t.get("tariff") == data.tariff_id:
                tariff = t
                break
        
        if not tariff:
            raise HTTPException(status_code=404, detail=f"Тариф {data.tariff_id} не найден")
        
        # 5. Получаем локаль из куки для определения валюты
        locale = request.cookies.get("iec_preferred_locale", "en")
        
        # 6. Определяем тип платежа по тексту кнопки
        button_text = tariff.get("buttonText", "").lower()
        
        if button_text == "buy":
            # Разовая покупка (несгораемые минуты)
            payment_manager.log_payment("INFO", f"Создание разового платежа для пользователя {user['id']}", {
                "tariff_id": data.tariff_id,
                "payment_system": data.payment_system,
                "locale": locale
            })
            
            result = await payment_manager.create_one_time_payment(
                user_data=user,
                tariff_data=tariff,
                payment_system=data.payment_system,
                locale=locale
            )
            
        elif button_text == "start":
            # Подписка (сгораемые минуты)
            payment_manager.log_payment("INFO", f"Создание подписки для пользователя {user['id']}", {
                "tariff_id": data.tariff_id,
                "payment_system": data.payment_system,
                "locale": locale
            })
            
            result = await payment_manager.create_subscription_payment(
                user_data=user,
                tariff_data=tariff,
                payment_system=data.payment_system,
                locale=locale
            )
            
        else:
            # Неизвестный тип кнопки
            raise HTTPException(
                status_code=400, 
                detail=f"Неподдерживаемый тип тарифа (buttonText: {button_text}). Ожидается 'buy' или 'start'"
            )
        
        # 7. Обрабатываем результат
        if result.get("success"):
            return {
                "paymentUrl": result.get("payment_url"),
                "status": "await",
                "paymentId": result.get("payment_id")
            }
        else:
            # Логируем ошибку (уже залогировано внутри функций)
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "Не удалось создать платеж")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        payment_manager.log_payment("ERROR", f"Исключение в /subscription/purchase: {str(e)}", {
            "user_id": user_data.get("id") if 'user_data' in locals() else None,
            "tariff_id": data.tariff_id,
            "exception": str(e)
        })
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@router.get("/subscription/payment-status")
async def check_subscription_payment_status(request: Request, paymentId: str):
    """
    Проверка статуса платежа
    
    Параметры:
        - paymentId: ID платежа полученный при создании
    
    Возвращает:
        - status: "await" | "success" | "closed"
    """
    try:
        if not paymentId:
            raise HTTPException(status_code=400, detail="Параметр paymentId обязателен")
        
        # Проверяем статус платежа через Airalo API
        result = await payment_manager.check_payment_status(paymentId)
        
        status = result.get("status")
        payment_info = result.get("payment_info")
        
        # Если платеж успешен - обновляем данные пользователя
        if status == "success" and payment_info:
            try:
                user_id = payment_info.get("user_id")
                minutes_to_add = payment_info.get("minutes_to_add", 0)
                is_permanent = payment_info.get("is_permanent", False)
                tariff_id = payment_info.get("tariff_id")
                
                # Получаем текущие данные пользователя
                user = await db_handler.get_user(user_id)
                if user:
                    # Определяем куда добавлять минуты
                    if is_permanent:
                        # Несгораемые минуты (для разовых покупок Buy)
                        new_permanent = user.get("permanent_seconds", 0) + (minutes_to_add * 60)
                        await db_handler.update_user(
                            user_id=user_id,
                            permanent_seconds=new_permanent
                        )
                        payment_manager.log_payment("INFO", f"Начислены несгораемые минуты пользователю {user_id}", {
                            "minutes": minutes_to_add
                        })
                    else:
                        # Сгораемые минуты (для подписок Start)
                        # ВАЖНО: Заменяем старые минуты, а не добавляем (обновление тарифа)
                        new_remaining = minutes_to_add * 60
                        await db_handler.update_user(
                            user_id=user_id,
                            remaining_seconds=new_remaining,
                            tariff=tariff_id,
                            payment_status="active"
                        )
                        payment_manager.log_payment("INFO", f"Установлены сгораемые минуты пользователю {user_id} (старые обнулены)", {
                            "new_minutes": minutes_to_add,
                            "tariff": tariff_id
                        })
                else:
                    payment_manager.log_payment("ERROR", f"Пользователь {user_id} не найден при начислении минут")
                    
            except Exception as e:
                payment_manager.log_payment("ERROR", f"Ошибка начисления минут: {str(e)}", {
                    "payment_id": paymentId,
                    "exception": str(e)
                })
        
        return {"status": status}
        
    except HTTPException:
        raise
    except Exception as e:
        payment_manager.log_payment("ERROR", f"Ошибка проверки статуса платежа {paymentId}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка проверки статуса: {str(e)}")


@router.get("/payment/success")
async def payment_success_handler(
    request: Request,
    payment_id: Optional[str] = None,
    paymentId: Optional[str] = None,
    subscription_id: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Обработка возврата пользователя после оплаты
    
    Параметры могут приходить в разных форматах от разных платежных систем:
        - payment_id / paymentId / subscription_id: ID платежа
        - status: статус от платежной системы (опционально)
    
    Автоматически проверяет статус и обновляет данные пользователя
    """
    try:
        # Определяем ID платежа (разные системы могут передавать по-разному)
        payment_identifier = payment_id or paymentId or subscription_id
        
        if not payment_identifier:
            payment_manager.log_payment("WARNING", "Возврат на /payment/success без payment_id")
            return {
                "status": "error",
                "message": "Payment ID not provided",
                "redirect": "https://iec.study/fluent/"
            }
        
        payment_manager.log_payment("INFO", f"Обработка возврата на /payment/success", {
            "payment_id": payment_identifier,
            "status_param": status,
            "query_params": dict(request.query_params)
        })
        
        # Проверяем статус платежа через наш API
        result = await payment_manager.check_payment_status(payment_identifier)
        
        payment_status = result.get("status")
        payment_info = result.get("payment_info")
        
        # Если платеж успешен - обновляем данные пользователя
        if payment_status == "success" and payment_info:
            try:
                user_id = payment_info.get("user_id")
                minutes_to_add = payment_info.get("minutes_to_add", 0)
                is_permanent = payment_info.get("is_permanent", False)
                tariff_id = payment_info.get("tariff_id")
                
                # Получаем текущие данные пользователя
                user = await db_handler.get_user(user_id)
                if user:
                    # Определяем куда добавлять минуты
                    if is_permanent:
                        # Несгораемые минуты (для разовых покупок Buy)
                        new_permanent = user.get("permanent_seconds", 0) + (minutes_to_add * 60)
                        await db_handler.update_user(
                            user_id=user_id,
                            permanent_seconds=new_permanent
                        )
                        payment_manager.log_payment("INFO", f"Начислены несгораемые минуты пользователю {user_id}", {
                            "minutes": minutes_to_add
                        })
                    else:
                        # Сгораемые минуты (для подписок Start)
                        new_remaining = user.get("remaining_seconds", 0) + (minutes_to_add * 60)
                        await db_handler.update_user(
                            user_id=user_id,
                            remaining_seconds=new_remaining,
                            tariff=tariff_id,
                            payment_status="active"
                        )
                        payment_manager.log_payment("INFO", f"Начислены сгораемые минуты пользователю {user_id}", {
                            "minutes": minutes_to_add,
                            "tariff": tariff_id
                        })
                    
                    # Успешно начислены минуты
                    return {
                        "status": "success",
                        "message": "Payment processed successfully",
                        "minutes_added": payment_info.get("minutes_to_add", 0),
                        "redirect": "https://iec.study/fluent/"
                    }
                else:
                    payment_manager.log_payment("ERROR", f"Пользователь {user_id} не найден при начислении минут")
                    return {
                        "status": "error",
                        "message": "User not found",
                        "redirect": "https://iec.study/fluent/"
                    }
                    
            except Exception as e:
                payment_manager.log_payment("ERROR", f"Ошибка начисления минут: {str(e)}", {
                    "payment_id": payment_identifier,
                    "exception": str(e)
                })
                return {
                    "status": "error",
                    "message": "Failed to process payment",
                    "redirect": "https://iec.study/fluent/"
                }
        
        elif payment_status == "await":
            # Платеж еще обрабатывается
            return {
                "status": "pending",
                "message": "Payment is being processed",
                "payment_id": payment_identifier,
                "redirect": "https://iec.study/fluent/"
            }
        
        else:
            # Платеж отменен или ошибка
            payment_manager.log_payment("WARNING", f"Возврат с неуспешным платежом {payment_identifier}", {
                "status": payment_status
            })
            return {
                "status": "failed",
                "message": "Payment was not completed",
                "redirect": "https://iec.study/fluent/"
            }
        
    except Exception as e:
        payment_manager.log_payment("ERROR", f"Ошибка обработки /payment/success: {str(e)}", {
            "payment_id": payment_identifier if 'payment_identifier' in locals() else None,
            "exception": str(e)
        })
        return {
            "status": "error",
            "message": "Internal server error",
            "redirect": "https://iec.study/fluent/"
        }


# ========================================
# Секретный роут для генерации отчетов
# ========================================
@router.get("/secret/report")
async def generate_token_report(password: str):
    """
    Генерация PDF отчета по использованию токенов за текущий месяц
    
    Параметры:
        - password: Пароль для доступа к отчету (из .env)
    
    Возвращает:
        - PDF файл с отчетом
    """
    try:
        # Проверяем пароль
        expected_password = os.getenv("REPORT_PASSWORD", "")
        
        if not expected_password:
            raise HTTPException(
                status_code=500,
                detail="Report password not configured"
            )
        
        if password != expected_password:
            raise HTTPException(
                status_code=403,
                detail="Invalid password"
            )
        
        # Генерируем отчет за текущий месяц
        now = datetime.now()
        year = now.year
        month = now.month
        
        # Генерируем PDF
        pdf_buffer = report_generator.generate_pdf_report(year, month)
        
        # Возвращаем PDF файл
        from fastapi.responses import StreamingResponse
        
        filename = f"token_report_{year}_{month:02d}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации отчета: {str(e)}"
        )


# CRM роуты (будут перенесены в отдельный файл)


