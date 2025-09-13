import httpx
import os
import uuid
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        # URLs из документации
        self.sandbox_url = "https://esim-sandbox.oxem.dev"
        self.production_url = "https://airalo-api.oxem.dev"
        
        # Используем sandbox по умолчанию, можно переключить через env
        self.base_url = os.getenv("PAYMENT_API_URL", self.sandbox_url)
        
        # URL нашего webhook endpoint
        self.webhook_url = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/api/webhook/payment")
        
        # Bearer токен для авторизации webhook (опционально)
        self.webhook_auth_token = os.getenv("WEBHOOK_AUTH_TOKEN")
        
        # URL для возврата пользователя после оплаты
        self.return_url = os.getenv("PAYMENT_RETURN_URL", "http://127.0.0.1:8000/payment/success")
    
    async def create_payment(
        self,
        user_id: str,
        amount: float,
        currency: str,
        payment_method: str,
        tariff_name: str,
        minutes_to_add: int,
        external_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создает платеж через внешний API
        
        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            currency: Валюта (USD или RUB)
            payment_method: Способ оплаты (yandex_pay или paypal)
            tariff_name: Название тарифа
            external_order_id: Внешний ID заказа (опционально)
        
        Returns:
            Dict с payment_url и internal_order_id
        """
        
        if not external_order_id:
            external_order_id = f"FLUENTGO-{int(time.time())}-{user_id}"
        
        # Данные для отправки в webhook
        custom_data = {
            "user_id": user_id,
            "tariff_name": tariff_name,
            "minutes_to_add": minutes_to_add,
            "service": "fluentgo_ai_assistant",
            "created_at": int(time.time())
        }
        
        # Формируем запрос согласно документации API
        payload = {
            "external_order_id": external_order_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "webhook_url": self.webhook_url,
            "return_url": self.return_url,
            "product_title": f"FluentGo - {tariff_name}",
            "custom_data": custom_data
        }
        
        # Добавляем auth_token если есть
        if self.webhook_auth_token:
            payload["auth_token"] = self.webhook_auth_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/external/payments/create",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Платеж создан успешно: {result.get('internal_order_id')}")
                    return {
                        "success": True,
                        "payment_url": result.get("payment_url"),
                        "internal_order_id": result.get("internal_order_id"),
                        "external_order_id": external_order_id
                    }
                else:
                    error_data = response.json() if response.content else {"error": "Unknown error"}
                    logger.error(f"Ошибка создания платежа: {response.status_code} - {error_data}")
                    return {
                        "success": False,
                        "error": error_data.get("error", "Payment creation failed"),
                        "status_code": response.status_code
                    }
                    
        except httpx.TimeoutException:
            logger.error("Таймаут при создании платежа")
            return {
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании платежа: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_payment_status(self, internal_order_id: str) -> Dict[str, Any]:
        """
        Получает статус платежа по internal_order_id
        
        Args:
            internal_order_id: UUID платежа из внешней системы
            
        Returns:
            Dict со статусом платежа
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/api/external/payments/{internal_order_id}/status"
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Статус платежа {internal_order_id}: {result.get('status')}")
                    return {
                        "success": True,
                        "data": result
                    }
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "error": "Payment not found"
                    }
                else:
                    error_data = response.json() if response.content else {"error": "Unknown error"}
                    logger.error(f"Ошибка получения статуса: {response.status_code} - {error_data}")
                    return {
                        "success": False,
                        "error": error_data.get("error", "Status check failed"),
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса платежа: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    


# Глобальный экземпляр сервиса
payment_service = PaymentService()
