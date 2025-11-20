========================================================
API для внешних платежных сервисов
========================================================

API обычных платежей (не рекуррентных) Yandex Pay + PayPal

Обзор

API для внешних платежных сервисов позволяет сторонним системам интегрироваться с платежной инфраструктурой для обработки произвольных платежей. Система поддерживает создание платежей с пользовательскими данными, автоматическую обработку через Yandex Pay и PayPal, а также отправку уведомлений через webhook.

Базовый URL для тестирования: https://esim-sandbox.oxem.dev
Все запросы к хосту требуют заголовок запроса:
Authorization: Bearer preview-external-api-secret-2024

Базовый URL для production: https://airalo-api.oxem.dev


========================================================
Ключевые возможности (были таблицей → теперь JSON)
========================================================

{
  "features": [
    "Создание произвольных платежей без привязки к продуктам",
    "Поддержка пользовательских данных (key-value)",
    "Интеграция: Yandex Pay (RUB) и PayPal (USD)",
    "Автоматическая конвертация валют",
    "Webhook с Bearer авторизацией",
    "Retry-логика уведомлений",
    "Отслеживание статуса платежей"
  ]
}
// Комментарий: Исходная таблица возможностей преобразована в список.


========================================================
Архитектура
========================================================

Система обрабатывает платежи через Yandex Pay (для рублей) и PayPal (для долларов), сохраняет данные в базе и отправляет webhook уведомления при успешном завершении.

========================================================
API Endpoints
========================================================

--------------------------------------------------------
1. Создание платежа
--------------------------------------------------------

Endpoint: POST /api/external/payments/create

Параметры запроса (таблица → JSON):

{
  "parameters": {
    "external_order_id": {
      "type": "string",
      "required": false,
      "description": "Идентификатор заказа во внешней системе"
    },
    "amount": {
      "type": "number",
      "required": true,
      "description": "Сумма платежа, положительное число"
    },
    "currency": {
      "type": "string",
      "required": true,
      "allowed": ["USD", "RUB"]
    },
    "payment_method": {
      "type": "string",
      "required": true,
      "allowed": ["yandex_pay", "paypal"]
    },
    "webhook_url": {
      "type": "string",
      "required": true,
      "description": "URL, куда будет отправлен webhook"
    },
    "auth_token": {
      "type": "string",
      "required": false,
      "description": "Bearer токен для webhook авторизации"
    },
    "return_url": {
      "type": "string",
      "required": false
    },
    "product_title": {
      "type": "string",
      "required": false
    },
    "custom_data": {
      "type": "object",
      "required": true,
      "description": "Произвольные данные (key-value)"
    }
  }
}
// Комментарий: Вся таблица конвертирована в объект описаний параметров.


Пример запроса
(оставлено без изменений)
curl -X POST https://esim-sandbox.oxem.dev/api/external/payments/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer preview-external-api-secret-2024" \
  -d '{
    "external_order_id": "ORDER-2024-001",
    "amount": 49.99,
    "currency": "USD",
    "payment_method": "paypal",
    "webhook_url": "https://myservice.com/webhook/payment",
    "auth_token": "Bearer_Token_12345",
    "return_url": "https://myservice.com/payment/complete",
    "product_title": "Premium Subscription",
    "custom_data": {
      "user_id": "user_789",
      "product_name": "Premium Subscription",
      "subscription_months": 12,
      "discount_applied": true,
      "referral_code": "FRIEND2024"
    }
  }'

Успешный ответ
{
  "payment_url": "...",
  "internal_order_id": "uuid..."
}

Ошибки (таблица → JSON):

{
  "errors": [
    {
      "status": 400,
      "description": "Некорректные данные",
      "example": {"error": "Invalid amount parameter"}
    },
    {
      "status": 400,
      "description": "Неподдерживаемый метод",
      "example": {"error": "Unknown payment method: crypto"}
    },
    {
      "status": 500,
      "description": "Внутренняя ошибка"
    }
  ]
}

--------------------------------------------------------
2. Получение статуса платежа
--------------------------------------------------------

Endpoint: GET /api/external/payments/{internal_order_id}/status

Параметры пути (таблица → JSON):

{
  "path_parameters": {
    "internal_order_id": {
      "type": "string",
      "format": "UUID",
      "description": "UUID, полученный при создании платежа"
    }
  }
}

Пример ответа оставлен без изменений.

Статусы платежей (таблица → JSON):

{
  "statuses": {
    "PENDING": "Платёж создан, ожидается оплата",
    "SUCCESS": "Платёж завершён успешно",
    "FAILED": "Платёж не прошёл или отменён"
  }
}

Ошибки (таблица → JSON):

{
  "errors": [
    {"status": 404, "description": "Платёж не найден"},
    {"status": 500, "description": "Ошибка сервера"}
  ]
}

--------------------------------------------------------
Webhook уведомления
--------------------------------------------------------

(текст оставлен без изменений)

Webhook поля (таблица → JSON):

{
  "webhook_payload_fields": {
    "internal_order_id": "UUID внутреннего платежа",
    "external_order_id": "Идентификатор во внешней системе",
    "status": "Статус платежа",
    "amount": "Сумма платежа",
    "currency": "Валюта",
    "payment_method": "Способ оплаты",
    "processed_at": "Время обработки",
    "//": "custom_data поля внедряются на корневой уровень"
  }
}

Особенности webhook (таблица → JSON):

{
  "webhook_features": {
    "flatten_custom_data": "custom_data встроен в корень объекта",
    "authorization": "Если auth_token указан — добавляется Bearer header",
    "retry": "3 попытки: 1с, 2с, 4с",
    "success_codes": "Любой 2xx",
    "failure_behavior": {
      "4xx": "retry НЕ делается",
      "5xx": "retry делается"
    }
  }
}

--------------------------------------------------------
Особенности валют и конвертации
--------------------------------------------------------

(текст оставлен без изменений)

Поддерживаемые валюты (таблица → JSON):

{
  "currencies": {
    "USD": "PayPal",
    "RUB": "Yandex Pay"
  }
}

--------------------------------------------------------
3. Симуляция успешной оплаты (sandbox)
--------------------------------------------------------

(текст оставлен без изменений)

Ошибки симуляции (таблица → JSON):

{
  "simulation_errors": [
    {"status": 403, "description": "Недоступно в production"},
    {"status": 404, "description": "Платёж не найден"},
    {"status": 400, "description": "Платёж уже обработан"}
  ]
}

--------------------------------------------------------
Ограничения
--------------------------------------------------------

(таблица → JSON)

{
  "limits": {
    "rate": "100 req/min per IP",
    "custom_data_size": "5 KB",
    "webhook_timeout": "30s",
    "retry_attempts": 3,
    "supported_custom_data_types": ["string", "number", "boolean"]
  }
}

--------------------------------------------------------
Поддержка
--------------------------------------------------------

(оставлено без изменений)
========================================================
