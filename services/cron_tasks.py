import asyncio
import os
import httpx
from datetime import datetime, timedelta
from database import db_handler
from services.cron_manager import cron_logger
from services import payment_manager

# Московский timezone offset (UTC+3)
MOSCOW_TZ_OFFSET = 3

async def retry_on_error(task_func, task_name: str, max_retries: int = 3, retry_delay: int = 300):
    """
    Обертка для повторных попыток при ошибке
    
    :param task_func: Async функция задачи
    :param task_name: Название задачи для логов
    :param max_retries: Максимум попыток
    :param retry_delay: Задержка между попытками (секунды)
    """
    for attempt in range(1, max_retries + 1):
        try:
            await task_func()
            return  # Успех - выходим
        except Exception as e:
            cron_logger.log_task_error(task_name, str(e), {"attempt": attempt})
            
            if attempt < max_retries:
                cron_logger.log_task_retry(task_name, attempt + 1, max_retries)
                await asyncio.sleep(retry_delay)
            else:
                cron_logger.log(task_name, "ERROR", f"Все {max_retries} попытки исчерпаны")


# ========================================
# КРОНТАБ 1: Удаление гостевых пользователей
# ========================================
async def cleanup_guest_users_task():
    """
    Удаление всех гостевых (неавторизованных) пользователей
    Запуск: 1 число каждого месяца
    """
    task_name = "cleanup_guest_users"
    cron_logger.log_task_start(task_name)
    
    try:
        # Находим всех пользователей с ID вида user_{ip}
        # В sqlite нет regex, поэтому получим всех и отфильтруем
        async with db_handler.get_connection() as db:
            cursor = await db.execute("SELECT id, user_name FROM users")
            all_users = await cursor.fetchall()
        
        deleted_count = 0
        for user in all_users:
            user_id = user[0]
            # Проверяем паттерн: user_{ip} (например user_192_168_1_1)
            if user_id.startswith("user_") and user_id.replace("user_", "").replace("_", ".").count(".") >= 3:
                # Это гостевой пользователь - удаляем
                async with db_handler.get_connection() as db:
                    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    await db.execute("DELETE FROM topic WHERE user_id = ?", (user_id,))
                    await db.commit()
                deleted_count += 1
        
        cron_logger.log_task_success(task_name, f"Удалено {deleted_count} гостевых пользователей", {
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        raise Exception(f"Ошибка удаления гостей: {str(e)}")


# ========================================
# КРОНТАБ 2: Запрос автоплатежей
# ========================================
async def process_subscription_payments_task():
    """
    Проверка и запрос автоплатежей для подписок
    Запуск: каждый день
    """
    task_name = "subscription_payments"
    cron_logger.log_task_start(task_name)
    
    try:
        # Находим пользователей с активными подписками
        async with db_handler.get_connection() as db:
            cursor = await db.execute("""
                SELECT id, subscription_id, payment_system, payment_date, tariff, subscription_status
                FROM users
                WHERE subscription_status = 'active'
                AND payment_date IS NOT NULL
                AND subscription_id IS NOT NULL
            """)
            subscribers = await cursor.fetchall()
        
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        for subscriber in subscribers:
            user_id, sub_id, payment_sys, last_payment_ts, tariff, sub_status = subscriber
            
            # Проверяем прошел ли месяц с последней оплаты
            if not last_payment_ts:
                continue
            
            last_payment_date = datetime.fromtimestamp(last_payment_ts)
            current_date = datetime.now()
            
            # Если день и месяц совпадают (прошел ровно месяц/год)
            if last_payment_date.day == current_date.day and (
                (current_date.month - last_payment_date.month) % 12 == 1 or
                (current_date.year - last_payment_date.year >= 1 and current_date.month == last_payment_date.month)
            ):
                processed_count += 1
                
                try:
                    # Обрабатываем YooKassa
                    if payment_sys == "yookassa":
                        success = await _charge_yookassa_subscription(user_id, sub_id, tariff)
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                            await _reset_user_subscription(user_id)
                    
                    # PayPal проверяем статус (списания автоматические)
                    elif payment_sys == "paypal":
                        success = await _check_paypal_subscription_status(user_id, sub_id)
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                            await _reset_user_subscription(user_id)
                    
                except Exception as e:
                    cron_logger.log(task_name, "ERROR", f"Ошибка обработки подписки {user_id}", {"error": str(e)})
                    failed_count += 1
        
        cron_logger.log_task_success(task_name, "Автоплатежи обработаны", {
            "total_processed": processed_count,
            "success": success_count,
            "failed": failed_count
        })
        
    except Exception as e:
        raise Exception(f"Ошибка обработки автоплатежей: {str(e)}")


async def _charge_yookassa_subscription(user_id: str, subscription_id: str, tariff: str) -> bool:
    """Списание средств с YooKassa подписки"""
    try:
        # Загружаем данные тарифа
        import json
        with open("document/tariffs.json", "r", encoding="utf-8") as f:
            tariffs = json.load(f)
        
        tariff_data = next((t for t in tariffs if t.get("id") == tariff), None)
        if not tariff_data:
            return False
        
        # Парсим минуты
        minutes = payment_manager.parse_minutes_from_tariff(tariff_data)
        
        # Запрос к Airalo API для списания
        api_url = os.getenv("PAYMENT_API_URL", "https://esim-sandbox.oxem.dev")
        api_token = os.getenv("PAYMENT_API_TOKEN", "preview-external-api-secret-2024")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/api/external/subscriptions/{subscription_id}/charge",
                headers={"Authorization": f"Bearer {api_token}"},
                json={},
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "SUCCESS":
                    # Обновляем минуты пользователя (ЗАМЕНЯЕМ, не добавляем)
                    await db_handler.update_user(
                        user_id=user_id,
                        remaining_seconds=minutes * 60,
                        payment_date=int(datetime.now().timestamp())
                    )
                    return True
        
        return False
        
    except Exception as e:
        cron_logger.log("subscription_charge", "ERROR", f"YooKassa charge error: {str(e)}")
        return False


async def _check_paypal_subscription_status(user_id: str, subscription_id: str) -> bool:
    """Проверка статуса PayPal подписки"""
    try:
        api_url = os.getenv("PAYMENT_API_URL", "https://esim-sandbox.oxem.dev")
        api_token = os.getenv("PAYMENT_API_TOKEN", "preview-external-api-secret-2024")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/external/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {api_token}"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "").upper()
                
                # Если активна - PayPal уже списал автоматически (webhook придет)
                if status in ["ACTIVE", "SUCCESS"]:
                    return True
        
        return False
        
    except Exception as e:
        cron_logger.log("subscription_check", "ERROR", f"PayPal check error: {str(e)}")
        return False


async def _reset_user_subscription(user_id: str):
    """Сброс подписки пользователя на free"""
    await db_handler.update_user(
        user_id=user_id,
        tariff="free",
        remaining_seconds=0,
        subscription_status="cancelled",
        payment_status="unpaid"
    )
    cron_logger.log("subscription_reset", "INFO", f"Подписка пользователя {user_id} сброшена на free")


# ========================================
# КРОНТАБ 3: Начисление 2 минут авторизованным
# ========================================
async def grant_free_minutes_task():
    """
    Начисление 2 минут авторизованным пользователям без подписки
    Запуск: 1 число каждого месяца
    """
    task_name = "grant_free_minutes"
    cron_logger.log_task_start(task_name)
    
    try:
        # Находим авторизованных без подписки, без несгораемых минут, с балансом 0
        async with db_handler.get_connection() as db:
            cursor = await db.execute("""
                SELECT id FROM users
                WHERE id NOT LIKE 'user_%'
                AND (tariff IS NULL OR tariff = 'free')
                AND permanent_seconds = 0
                AND remaining_seconds = 0
            """)
            eligible_users = await cursor.fetchall()
        
        granted_count = 0
        for user in eligible_users:
            user_id = user[0]
            await db_handler.update_user(
                user_id=user_id,
                remaining_seconds=120  # 2 минуты
            )
            granted_count += 1
        
        cron_logger.log_task_success(task_name, f"Начислено 2 минуты {granted_count} пользователям", {
            "granted_count": granted_count
        })
        
    except Exception as e:
        raise Exception(f"Ошибка начисления минут: {str(e)}")


# ========================================
# КРОНТАБ 4: Очистка хранилища платежей
# ========================================
async def cleanup_payments_storage_task():
    """
    Очистка хранилища платежей (active_payments)
    Запуск: каждый час
    """
    task_name = "cleanup_payments"
    cron_logger.log_task_start(task_name)
    
    try:
        cleaned_count = 0
        payment_ids_to_remove = []
        
        # Проходим по всем платежам
        for payment_id, payment_info in list(payment_manager.active_payments.items()):
            try:
                # Проверяем статус через payment_manager
                result = await payment_manager.check_payment_status(payment_id)
                status = result.get("status")
                
                # Если closed - удаляем
                if status == "closed":
                    payment_ids_to_remove.append(payment_id)
                    cleaned_count += 1
                    
            except Exception as e:
                cron_logger.log(task_name, "WARNING", f"Ошибка проверки платежа {payment_id}", {"error": str(e)})
        
        # Удаляем из хранилища
        for payment_id in payment_ids_to_remove:
            if payment_id in payment_manager.active_payments:
                del payment_manager.active_payments[payment_id]
        
        cron_logger.log_task_success(task_name, f"Очищено {cleaned_count} платежей", {
            "cleaned_count": cleaned_count,
            "remaining_count": len(payment_manager.active_payments)
        })
        
    except Exception as e:
        raise Exception(f"Ошибка очистки хранилища: {str(e)}")

