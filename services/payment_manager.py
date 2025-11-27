"""
Сервис управления платежами через Airalo API
Поддержка YooKassa и PayPal для разовых покупок и подписок
"""

import os
import json
import uuid
import httpx
import math
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# ========================================
# In-Memory хранилище активных платежей
# ========================================
# Структура: {payment_id: {user_id, tariff_id, payment_type, payment_system, minutes_to_add, amount, currency, status, created_at}}
active_payments: Dict[str, dict] = {}

# ========================================
# Защита от повторной обработки webhook
# ========================================
# Множество обработанных charge_id для подписок (PayPal, YooKassa)
# По документации @PAYPAL.md (строки 320, 358-361): "charge_id может повторяться"
processed_charge_ids: set = set()

# Множество обработанных payment_id (idempotency для начисления минут)
# Используется для защиты от многократного начисления при повторных вызовах
processed_payment_ids: set = set()


# ========================================
# Логирование платежей
# ========================================
def log_payment(level: str, message: str, data: dict = None):
    """
    Логирование платежных операций в файл payment_logs.txt
    
    Args:
        level: Уровень лога (INFO, ERROR, WARNING)
        message: Сообщение
        data: Дополнительные данные для логирования
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        if data:
            log_entry += f"\nData: {json.dumps(data, ensure_ascii=False, indent=2)}"
        
        log_entry += "\n" + "="*80 + "\n"
        
        with open("payment_logs.txt", "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Ошибка логирования: {e}")


# ========================================
# Парсинг минут из тарифа
# ========================================
def parse_minutes_from_tariff(tariff_data: dict) -> int:
    """
    Извлекает количество минут из features тарифа
    
    Args:
        tariff_data: Данные тарифа из TariffsData.txt
        
    Returns:
        Количество минут (0 если не найдено)
    """
    features = tariff_data.get("features", [])
    
    for feature in features:
        text = feature.get("text", "").lower()
        
        # Паттерны для поиска минут: "100 minutes", "50 min/month", "Unlimited"
        # Ищем число перед "min"
        match = re.search(r'(\d+)\s*min', text)
        if match:
            return int(match.group(1))
        
        # Проверяем на "Unlimited"
        if "unlimited" in text:
            return 999999  # Условно бесконечно
    
    return 0


# ========================================
# Получение курса валют
# ========================================
async def get_exchange_rate() -> Optional[float]:
    """
    Получает курс RUB/USD для конвертации цен
    
    Returns:
        Курс final_rate или None при ошибке
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://iec.study/wp-json/airalo/v1/exchange-rate-rub",
                timeout=5.0
            )
            if response.status_code == 200:
                rate_data = response.json()
                if rate_data.get("success") and rate_data.get("data"):
                    return rate_data["data"].get("final_rate")
    except Exception as e:
        log_payment("ERROR", f"Ошибка получения курса валют: {e}")
    
    return None


# ========================================
# Конвертация цены в нужную валюту
# ========================================
async def convert_price(price_usd: float, locale: str) -> Tuple[int, str]:
    """
    Конвертирует цену в USD или RUB в зависимости от локали
    
    Args:
        price_usd: Цена в долларах
        locale: Локаль пользователя
        
    Returns:
        (сумма, валюта) - целое число в рублях/долларах
    """
    if locale == "ru":
        # Конвертируем в рубли
        exchange_rate = await get_exchange_rate()
        if exchange_rate:
            # Округляем вверх, возвращаем целое число в рублях
            price_rub = math.ceil(price_usd * exchange_rate)
            return price_rub, "RUB"
        else:
            log_payment("WARNING", "Не удалось получить курс, используем USD")
    
    # Округляем вверх, возвращаем целое число в долларах
    return math.ceil(price_usd), "USD"


# ========================================
# Создание разового платежа
# ========================================
async def create_one_time_payment(
    user_data: dict,
    tariff_data: dict,
    payment_system: str,
    locale: str
) -> dict:
    """
    Создает разовый платеж через Airalo API (external/payments/create)
    
    Args:
        user_data: Данные пользователя
        tariff_data: Данные тарифа
        payment_system: "yookassa" или "paypal"
        locale: Локаль пользователя
        
    Returns:
        {"success": bool, "payment_url": str, "payment_id": str, "error": str}
    """
    try:
        # Генерируем уникальный ID платежа
        external_order_id = str(uuid.uuid4())
        
        # Извлекаем цену из тарифа
        price_str = tariff_data.get("price", "$0")
        price_usd = float(price_str.replace("$", "").strip())
        
        # Конвертируем цену
        amount, currency = await convert_price(price_usd, locale)
        
        # Конвертируем payment_system в payment_method для API
        # yookassa и paypal используются напрямую
        payment_method = payment_system  # "yookassa" или "paypal"
        
        # Извлекаем минуты
        minutes = parse_minutes_from_tariff(tariff_data)
        
        # Формируем название продукта
        if payment_system == "yookassa":
            product_title = f"Покупка минут по тарифу {tariff_data.get('name', 'Unknown')}"
        else:
            product_title = f"Разовая покупка {minutes} минут"
        
        # Формируем тело запроса
        payload = {
            "external_order_id": external_order_id,
            "amount": amount,  # Целое число в рублях/долларах
            "currency": currency,
            "payment_method": payment_method,  # "yookassa" или "paypal"
            "webhook_url": os.getenv("WEBHOOK_URL", "https://iec.study/fluent/api/webhook/payment"),
            "auth_token": os.getenv("WEBHOOK_AUTH_TOKEN", "Bearer_Token_12345"),
            "return_url": os.getenv("PAYMENT_RETURN_URL", "https://iec.study/fluent"),
            "product_title": product_title,
            "custom_data": {
                "user_id": user_data.get("id"),
                "product_name": tariff_data.get("name"),
                "email": user_data.get("email", ""),
                "minutes": minutes,
                "tariff_id": tariff_data.get("id")
            }
        }
        
        # Отправляем запрос
        # Токен одинаковый для sandbox и production
        api_token = os.getenv("PAYMENT_API_TOKEN", "preview-external-api-secret-2024")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }
        
        log_payment("INFO", f"Создание разового платежа для пользователя {user_data.get('id')}", {
            "payload": payload,
            "payment_system": payment_system
        })
        
        # Получаем базовый URL API
        api_base_url = os.getenv("PAYMENT_API_URL")
        if not api_base_url:
            raise Exception("PAYMENT_API_URL не установлен в переменных окружения")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_base_url}/api/external/payments/create",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                payment_url = result.get("payment_url")
                internal_order_id = result.get("internal_order_id")
                
                # Сохраняем информацию о платеже
                active_payments[external_order_id] = {
                    "user_id": user_data.get("id"),
                    "tariff_id": tariff_data.get("id"),
                    "payment_type": "one_time",
                    "payment_system": payment_system,
                    "minutes_to_add": minutes,
                    "amount": amount,
                    "currency": currency,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "internal_order_id": internal_order_id,
                    "is_permanent": True  # Несгораемые минуты для покупки (Buy)
                }
                
                log_payment("INFO", f"Платеж успешно создан: {external_order_id}", result)
                
                return {
                    "success": True,
                    "payment_url": payment_url,
                    "payment_id": external_order_id
                }
            else:
                error_data = {
                    "status_code": response.status_code,
                    "response": response.text,
                    "payload": payload
                }
                log_payment("ERROR", f"Ошибка создания платежа: {response.status_code}", error_data)
                
                return {
                    "success": False,
                    "error": f"Payment API error: {response.status_code}"
                }
                
    except Exception as e:
        log_payment("ERROR", f"Исключение при создании платежа: {str(e)}", {
            "user_id": user_data.get("id"),
            "tariff_id": tariff_data.get("id"),
            "exception": str(e)
        })
        
        return {
            "success": False,
            "error": str(e)
        }


# ========================================
# Создание подписки
# ========================================
async def create_subscription_payment(
    user_data: dict,
    tariff_data: dict,
    payment_system: str,
    locale: str
) -> dict:
    """
    Создает подписку через Airalo API (external/subscriptions/create)
    
    Args:
        user_data: Данные пользователя
        tariff_data: Данные тарифа
        payment_system: "yookassa" или "paypal"
        locale: Локаль пользователя
        
    Returns:
        {"success": bool, "payment_url": str, "payment_id": str, "error": str}
    """
    try:
        # Извлекаем цену из тарифа
        price_str = tariff_data.get("price", "$0")
        price_usd = float(price_str.replace("$", "").strip())
        
        # Извлекаем минуты
        minutes = parse_minutes_from_tariff(tariff_data)
        
        # Формируем название продукта
        if payment_system == "yookassa":
            product_title = f"Подписка {tariff_data.get('name', 'Unknown')}"
        else:
            product_title = tariff_data.get("name", "Subscription")
        
        # Формируем тело запроса в зависимости от платежной системы
        if payment_system == "paypal":
            # PayPal подписки - конвертируем цену по локали
            amount, currency = await convert_price(price_usd, locale)
            
            payload = {
                "payment_provider": "PAYPAL",
                "amount": amount,  # Целое число в рублях/долларах
                "currency": currency,  # USD или RUB
                "interval_count": 1,
                "interval_unit": "MONTH",
                "product_title": product_title,
                "webhook_url": os.getenv("WEBHOOK_URL", "https://iec.study/fluent/api/webhook/payment"),
                "return_url": os.getenv("PAYMENT_RETURN_URL", "https://iec.study/fluent"),
                "custom_data": {
                    "user_id": user_data.get("id"),
                    "product_name": tariff_data.get("name"),
                    "email": user_data.get("email", ""),
                    "minutes": minutes,
                    "tariff_id": tariff_data.get("id")
                },
                "auth_token": os.getenv("WEBHOOK_AUTH_TOKEN", "Bearer_Token_12345")
            }
        else:
            # YooKassa подписки - ВСЕГДА конвертируем в RUB
            # YooKassa работает только с рублями
            amount, currency = await convert_price(price_usd, "ru")
            
            payload = {
                "amount": amount,  # Целое число в рублях (всегда RUB для YooKassa)
                "currency": "RUB",
                "product_title": product_title,
                "webhook_url": os.getenv("WEBHOOK_URL", "https://iec.study/fluent/api/webhook/payment"),
                "return_url": os.getenv("PAYMENT_RETURN_URL", "https://iec.study/fluent"),
                "custom_data": {
                    "user_id": user_data.get("id"),
                    "product_name": tariff_data.get("name"),
                    "email": user_data.get("email", ""),
                    "minutes": minutes,
                    "tariff_id": tariff_data.get("id")
                },
                "auth_token": os.getenv("WEBHOOK_AUTH_TOKEN", "Bearer_Token_12345"),
                "customer_email": user_data.get("email", "")
            }
        
        # Отправляем запрос
        # Токен одинаковый для sandbox и production
        api_token = os.getenv("PAYMENT_API_TOKEN")
        if not api_token:
            raise Exception("PAYMENT_API_TOKEN не установлен в переменных окружения")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}"
        }
        
        log_payment("INFO", f"Создание подписки для пользователя {user_data.get('id')}", {
            "payload": payload,
            "payment_system": payment_system
        })
        
        # Получаем базовый URL API
        api_base_url = os.getenv("PAYMENT_API_URL")
        if not api_base_url:
            raise Exception("PAYMENT_API_URL не установлен в переменных окружения")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_base_url}/api/external/subscriptions/create",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                payment_url = result.get("payment_url")
                subscription_id = result.get("subscription_id")
                
                # Сохраняем информацию о подписке
                active_payments[subscription_id] = {
                    "user_id": user_data.get("id"),
                    "tariff_id": tariff_data.get("id"),
                    "payment_type": "subscription",
                    "payment_system": payment_system,
                    "minutes_to_add": minutes,
                    "amount": amount,
                    "currency": currency,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "is_permanent": False  # Сгораемые минуты для подписки (Start)
                }
                
                log_payment("INFO", f"Подписка успешно создана: {subscription_id}", result)
                
                return {
                    "success": True,
                    "payment_url": payment_url,
                    "payment_id": subscription_id
                }
            else:
                error_data = {
                    "status_code": response.status_code,
                    "response": response.text,
                    "payload": payload
                }
                log_payment("ERROR", f"Ошибка создания подписки: {response.status_code}", error_data)
                
                return {
                    "success": False,
                    "error": f"Subscription API error: {response.status_code}"
                }
                
    except Exception as e:
        log_payment("ERROR", f"Исключение при создании подписки: {str(e)}", {
            "user_id": user_data.get("id"),
            "tariff_id": tariff_data.get("id"),
            "exception": str(e)
        })
        
        return {
            "success": False,
            "error": str(e)
        }


# ========================================
# Проверка статуса платежа
# ========================================
async def check_payment_status(payment_id: str) -> dict:
    """
    Проверяет статус платежа через Airalo API
    
    Args:
        payment_id: ID платежа
        
    Returns:
        {"status": "await" | "success" | "closed", "payment_info": dict}
    """
    try:
        # Проверяем наличие в хранилище
        if payment_id not in active_payments:
            log_payment("WARNING", f"Платеж {payment_id} не найден в хранилище")
            return {"status": "closed"}
        
        payment_info = active_payments[payment_id]
        payment_type = payment_info.get("payment_type")
        payment_system = payment_info.get("payment_system")
        
        # Определяем endpoint для проверки
        api_token = os.getenv("PAYMENT_API_TOKEN")
        if not api_token:
            log_payment("ERROR", "PAYMENT_API_TOKEN не установлен в переменных окружения")
            return {"status": "closed"}
        
        headers = {
            "Authorization": f"Bearer {api_token}"
        }
        
        # Получаем базовый URL API
        api_base_url = os.getenv("PAYMENT_API_URL")
        if not api_base_url:
            log_payment("ERROR", "PAYMENT_API_URL не установлен в переменных окружения")
            return {"status": "closed"}
        
        if payment_type == "one_time":
            # Проверка разового платежа
            internal_order_id = payment_info.get("internal_order_id", payment_id)
            url = f"{api_base_url}/api/external/payments/{internal_order_id}/status"
        else:
            # Проверка подписки
            url = f"{api_base_url}/api/external/subscriptions/{payment_id}/status"
        
        log_payment("INFO", f"Проверка статуса платежа {payment_id}", {"url": url})
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            
            if response.status_code == 200:
                result = response.json()
                api_status = result.get("status", "").upper()
                
                log_payment("INFO", f"Получен статус платежа {payment_id}: {api_status}", result)
                
                # Маппинг статусов
                if api_status in ["PENDING"]:
                    return {"status": "await", "payment_info": payment_info}
                
                elif api_status in ["SUCCESS", "ACTIVE"]:
                    # Платеж успешен - НЕ удаляем из хранилища!
                    # Удаление произойдет после успешного начисления минут
                    log_payment("INFO", f"Платеж {payment_id} успешно завершен в API", payment_info)
                    return {"status": "success", "payment_info": payment_info}
                
                elif api_status in ["FAILED", "CANCELLED", "EXPIRED"]:
                    # Платеж отменен/ошибка - удаляем из хранилища
                    if payment_id in active_payments:
                        del active_payments[payment_id]
                    log_payment("WARNING", f"Платеж {payment_id} отменен/ошибка: {api_status}", payment_info)
                    return {"status": "closed", "payment_info": payment_info}
                
                else:
                    # Неизвестный статус
                    log_payment("WARNING", f"Неизвестный статус {api_status} для платежа {payment_id}")
                    return {"status": "await", "payment_info": payment_info}
            
            elif response.status_code == 404:
                # Платеж не найден
                if payment_id in active_payments:
                    del active_payments[payment_id]
                log_payment("ERROR", f"Платеж {payment_id} не найден в API (404)")
                return {"status": "closed"}
            
            else:
                # Ошибка API
                log_payment("ERROR", f"Ошибка проверки статуса: {response.status_code}", {
                    "response": response.text
                })
                return {"status": "await"}  # Считаем что еще в процессе
                
    except Exception as e:
        log_payment("ERROR", f"Исключение при проверке статуса платежа {payment_id}: {str(e)}")
        return {"status": "closed"}

