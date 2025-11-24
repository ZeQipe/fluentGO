
# API для внешних платежных сервисов
Источник: API для внешних платежных сервисов :contentReference[oaicite:0]{index=0}

## Базовая информация

**Sandbox URL:** `https://esim-sandbox.oxem.dev`  
**Production URL:** `https://airalo-api.oxem.dev`

Все запросы требуют заголовок:

```
Authorization: Bearer <token>
```

- Sandbox: `preview-external-api-secret-2024`
- Production: `preview-external-api-secret-2025`

---

# Возможности API

- Создание произвольных платежей  
- Пользовательские данные  
- Поддержка Yandex Pay / YooKassa / PayPal  
- Автоконвертация валют  
- Webhook-уведомления  
- Логика повторов  
- Получение статуса платежа  

---

# 1. Создание платежа

**POST** `/api/external/payments/create`

## Параметры запроса

| Поле               | Тип     | Обяз. | Описание |
|--------------------|---------|-------|----------|
| external_order_id  | string  | нет   | ID заказа внешней системы |
| amount             | number  | да    | Сумма (положительное число) |
| currency           | string  | да    | `USD` или `RUB` |
| payment_method     | string  | да    | `yandex_pay`, `yookassa`, `paypal` |
| webhook_url        | string  | да    | URL webhook |
| auth_token         | string  | нет   | Bearer токен |
| return_url         | string  | нет   | URL возврата |
| product_title      | string  | нет   | Название товара |
| custom_data        | object  | да    | Плоский объект |

### Пример запроса

```bash
curl -X POST https://esim-sandbox.oxem.dev/api/external/payments/create \
  -H "Content-Type: application/json" \
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
```

### Успешный ответ

```json
{
  "payment_url": "https://www.paypal.com/checkoutnow?token=4XJ84923H6394714N",
  "internal_order_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

---

# 2. Получение статуса платежа

**GET** `/api/external/payments/{internal_order_id}/status`

### Ответ

```json
{
  "internal_order_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "external_order_id": "ORDER-2024-001",
  "status": "SUCCESS",
  "amount": 49.99,
  "currency": "USD",
  "payment_method": "paypal",
  "custom_data": {
    "user_id": "user_789",
    "product_name": "Premium Subscription",
    "subscription_months": 12,
    "discount_applied": true,
    "referral_code": "FRIEND2024"
  },
  "created_at": 1704067200000,
  "processed_at": 1704067320000
}
```

### Статусы

| Статус  | Описание |
|---------|----------|
| PENDING | Ожидает оплаты |
| SUCCESS | Успешно |
| FAILED  | Ошибка / отмена |

---

# Webhook уведомления

POST на `webhook_url`.

### Заголовки
```
Content-Type: application/json
Authorization: Bearer {auth_token}
```

### Payload

```json
{
  "internal_order_id": "...",
  "external_order_id": "...",
  "status": "SUCCESS",
  "amount": 49.99,
  "currency": "USD",
  "payment_method": "paypal",
  "processed_at": 1704067320000,
  "user_id": "user_789",
  "product_name": "Premium Subscription",
  "subscription_months": 12
}
```

### Retry логика

| Условие | Повтор |
|------|--------|
| 2xx | OK |
| 4xx | нет |
| 5xx | retry 1s → 2s → 4s |

---

# Конвертация валют

| Направление | Как |
|-------------|------|
| USD → RUB | курс ЦБ |
| RUB → USD | обратный курс |

---

# Способы оплаты

| Метод        | Валюта | Особенности |
|--------------|--------|-------------|
| Yandex Pay   | RUB    | РФ |
| YooKassa     | RUB    | Много методов |
| PayPal       | USD    | Международно |

---

# Preview Endpoint — симуляция оплаты

**POST** `/api/external/payments/test/complete/{internal_order_id}`  
Только sandbox.

### Что делает

- Ставит статус `SUCCESS`
- Проставляет `processed_at`
- Отправляет webhook
- Применяет retry логику

---

# Ограничения

| Ограничение | Значение |
|-------------|----------|
| Rate limit | 100/m |
| custom_data | макс 5 KB |
| Webhook timeout | 30s |
| Retry | 3 |
| Типы данных | string / number / boolean |

---

# Тестовые данные

```json
{
  "amount": 1.00,
  "currency": "USD",
  "payment_method": "paypal",
  "webhook_url": "https://webhook.site/your-unique-url",
  "custom_data": {
    "test": true,
    "environment": "sandbox"
  }
}
```

---

# Поддержка

- Проверить логи webhook  
- Проверить auth_token  
- Сравнить статус через API  

