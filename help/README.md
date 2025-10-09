# FluentGo CRM API

API для управления пользователями, их балансами и тарифами в системе FluentGo.

## Описание

CRM API предоставляет пять endpoint'ов для административного управления пользователями:

1. **Получение списка тарифов** - просмотр всех доступных тарифных планов
2. **Создание пользователя** - создание нового пользователя в системе
3. **Получение баланса пользователя** - просмотр информации о конкретном пользователе
4. **Обновление баланса пользователя** - изменение баланса, тарифа или статуса оплаты
5. **Изменение статуса пользователя** - управление ролями и привилегиями пользователя

---

## Endpoints

### 1. GET `/crm/api/tariffs`

**Назначение:** Получение списка всех доступных тарифов из файла `tariffs.json`.

**Для чего нужен:**
- Отображение тарифных планов в CRM панели
- Синхронизация данных о тарифах
- Проверка актуальных цен и условий

**Запрос:**
```bash
curl -X GET http://localhost:8000/crm/api/tariffs
```

**Ответ:**
```json
{
  "status": "success",
  "tariffs": {
    "free": {
      "name": "Бесплатный",
      "price": 0,
      "minutes": 10
    },
    "standart": {
      "name": "Стандарт",
      "price": 990,
      "minutes": 120
    },
    "pro": {
      "name": "Про",
      "price": 1990,
      "minutes": 300
    }
  }
}
```

---

### 2. POST `/crm/api/user`

**Назначение:** Создание нового пользователя в системе CRM.

**Для чего нужен:**
- Регистрация нового пользователя со стороны CRM
- Создание пользователя с предустановленными параметрами
- Массовое создание пользователей через интеграции
- Импорт пользователей из внешних систем

**Обязательные поля:**
- `id` - уникальный идентификатор пользователя
- `user_name` - имя пользователя
- `email` - email пользователя

**Опциональные поля (со значениями по умолчанию):**
- `remaining_seconds` - сгораемые секунды (по умолчанию: `0`)
- `permanent_seconds` - несгораемые секунды (по умолчанию: `0`)
- `tariff` - тарифный план (по умолчанию: `"free"`)
- `payment_status` - статус оплаты (по умолчанию: `"unpaid"`)
- `payment_date` - дата оплаты timestamp (по умолчанию: `null`)
- `status` - статус/роль пользователя (по умолчанию: `"default"`)
- `iat` - JWT issued at timestamp (по умолчанию: `null`)
- `exp` - JWT expiration timestamp (по умолчанию: `null`)

**Тело запроса:**
```json
{
  "id": "new_user_123",
  "user_name": "John Doe",
  "email": "john.doe@example.com"
}
```

**Примеры использования:**

#### Создать пользователя с минимальными данными:
```bash
curl -X POST http://localhost:8000/crm/api/user \
  -H "Content-Type: application/json" \
  -d '{
    "id": "new_user_123",
    "user_name": "John Doe",
    "email": "john.doe@example.com"
  }'
```

#### Создать пользователя с полными данными:
```bash
curl -X POST http://localhost:8000/crm/api/user \
  -H "Content-Type: application/json" \
  -d '{
    "id": "new_user_456",
    "user_name": "Jane Smith",
    "email": "jane.smith@example.com",
    "remaining_seconds": 3600,
    "permanent_seconds": 1800,
    "tariff": "pro",
    "payment_status": "active",
    "status": "premium"
  }'
```

#### Создать пользователя с тарифом Standard и начальным балансом:
```bash
curl -X POST http://localhost:8000/crm/api/user \
  -H "Content-Type: application/json" \
  -d '{
    "id": "user_standard_001",
    "user_name": "Alice Johnson",
    "email": "alice@example.com",
    "remaining_seconds": 7200,
    "tariff": "standart",
    "payment_status": "active"
  }'
```

**Ответ при успехе (200):**
```json
{
  "status": "success",
  "message": "Пользователь успешно создан",
  "data": {
    "user_id": "new_user_123",
    "user_name": "John Doe",
    "email": "john.doe@example.com",
    "remaining_seconds": 0,
    "permanent_seconds": 0,
    "tariff": "free",
    "payment_status": "unpaid",
    "payment_date": null,
    "status": "default"
  }
}
```

**Ответ при конфликте (409):**
```json
{
  "detail": "Пользователь с таким ID уже существует"
}
```

---

### 3. GET `/crm/api/user/{user_id}/balance`

**Назначение:** Получение информации о балансе и статусе конкретного пользователя.

**Для чего нужен:**
- Проверка оставшегося времени пользователя
- Просмотр текущего тарифа
- Проверка статуса оплаты
- Мониторинг активности пользователей

**Параметры:**
- `user_id` (path) - уникальный идентификатор пользователя

**Запрос:**
```bash
curl -X GET http://localhost:8000/crm/api/user/zeqipe/balance
```

**Ответ:**
```json
{
  "status": "success",
  "data": {
    "user_id": "zeqipe",
    "user_name": "zeqipe",
    "remaining_seconds": 7200,
    "monthly_seconds": 0,
    "tariff": "standart",
    "payment_status": "active"
  }
}
```

**Поля ответа:**
- `remaining_seconds` - оставшиеся секунды (сгораемые по тарифу)
- `monthly_seconds` - месячные секунды (пока не используется)
- `tariff` - текущий тариф: `free`, `standart`, `pro`
- `payment_status` - статус оплаты: `active`, `unpaid`, `expired`

---

### 4. PUT `/crm/api/user/{user_id}/balance`

**Назначение:** Обновление баланса пользователя, смена тарифа или изменение статуса оплаты.

**Для чего нужен:**
- Начисление минут после оплаты
- Списание времени вручную (компенсации, штрафы)
- Смена тарифного плана
- Изменение статуса оплаты (активация, деактивация)
- Административные корректировки баланса

**Параметры:**
- `user_id` (path) - уникальный идентификатор пользователя

**Тело запроса:**
```json
{
  "add_remaining_seconds": 3600,
  "tariff": "pro",
  "payment_status": "active"
}
```

**Поля запроса (все опциональные):**
- `add_remaining_seconds` (integer) - количество секунд для добавления/списания (может быть отрицательным)
- `add_monthly_seconds` (integer) - месячные секунды (пока не реализовано)
- `tariff` (string) - новый тариф: `free`, `standart`, `pro`
- `payment_status` (string) - новый статус: `active`, `unpaid`, `expired`

**Примеры использования:**

#### Добавить 60 минут (3600 секунд):
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "add_remaining_seconds": 3600
  }'
```

#### Списать 30 минут (1800 секунд):
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "add_remaining_seconds": -1800
  }'
```

#### Изменить тариф на Pro:
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "tariff": "pro",
    "payment_status": "active"
  }'
```

#### Полное обновление:
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "add_remaining_seconds": 7200,
    "tariff": "standart",
    "payment_status": "active"
  }'
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Баланс обновлен",
  "data": {
    "user_id": "zeqipe",
    "user_name": "zeqipe",
    "remaining_seconds": 10800,
    "monthly_seconds": 0,
    "tariff": "standart",
    "payment_status": "active"
  }
}
```

---

### 5. PUT `/crm/api/user/{user_id}/status`

**Назначение:** Изменение статуса (привилегий/роли) пользователя в системе.

**Для чего нужен:**
- Назначение ролей пользователям
- Управление привилегиями и уровнями доступа
- Установка специальных статусов (VIP, модератор, админ)
- Изменение уровня пользователя

**Параметры:**
- `user_id` (path) - уникальный идентификатор пользователя

**Тело запроса:**
```json
{
  "status": "admin"
}
```

**Поле запроса:**
- `status` (string, обязательное) - новый статус/роль пользователя

**Возможные значения статуса (примеры):**
- `default` - обычный пользователь (по умолчанию)
- `premium` - премиум пользователь
- `vip` - VIP пользователь
- `moderator` - модератор
- `admin` - администратор
- `trial` - пробный период
- Любое другое строковое значение по вашей бизнес-логике

**Примеры использования:**

#### Назначить пользователя администратором:
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "admin"
  }'
```

#### Назначить VIP статус:
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "vip"
  }'
```

#### Назначить модератором:
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "moderator"
  }'
```

**Ответ:**
```json
{
  "status": "success",
  "message": "Статус пользователя изменен на 'admin'",
  "data": {
    "user_id": "zeqipe",
    "user_name": "zeqipe",
    "status": "admin",
    "email": "test1@example.com",
    "tariff": "standart",
    "payment_status": "active"
  }
}
```

---

## Коды ответов

| Код | Описание |
|-----|----------|
| 200 | Успешное выполнение запроса |
| 404 | Пользователь не найден |
| 409 | Конфликт - пользователь с таким ID уже существует |
| 500 | Внутренняя ошибка сервера |

---

## Формат ошибок

```json
{
  "status": "error",
  "message": "Описание ошибки"
}
```

или

```json
{
  "detail": "Пользователь не найден"
}
```

---

## Как работает система баланса

### Типы секунд в системе:

1. **`remaining_seconds`** (сгораемые) - секунды, начисленные по тарифу
   - Обновляются каждый месяц
   - Тратятся первыми
   
2. **`permanent_seconds`** (несгораемые) - постоянные секунды
   - Не обнуляются при обновлении подписки
   - Тратятся после `remaining_seconds`
   - Используются для компенсаций, бонусов

### Логика списания:
1. Сначала тратятся `remaining_seconds`
2. Когда `remaining_seconds` = 0, начинают тратиться `permanent_seconds`
3. Если оба баланса = 0, доступ к сервису ограничивается

---

## Swagger документация

Полная документация API доступна в файле `API.yaml` (OpenAPI 3.0.0).

**Просмотр через Swagger Editor:**
1. Откройте https://editor.swagger.io/
2. Скопируйте содержимое файла `API.yaml`
3. Вставьте в левую панель редактора

**Просмотр локально:**
```bash
# Установите Swagger UI (если еще не установлен)
npm install -g swagger-ui-watcher

# Запустите
swagger-ui-watcher API.yaml
```

---

## База данных

API работает с SQLite базой данных `users.db`:

### Таблица `users`:
- `id` - уникальный идентификатор
- `user_name` - имя пользователя
- `email` - email пользователя
- `remaining_seconds` - сгораемые секунды
- `permanent_seconds` - несгораемые секунды
- `tariff` - текущий тариф
- `payment_status` - статус оплаты
- `payment_date` - дата последней оплаты
- `status` - статус пользователя в системе
- `iat` - JWT issued at timestamp
- `exp` - JWT expiration timestamp

---

## Тестовые пользователи

В системе предустановлены 3 тестовых пользователя:

| User ID | Обычные минуты | Несгораемые минуты | Тариф |
|---------|----------------|-------------------|-------|
| zeqipe | 120 | 45 | standart |
| dany | 300 | 0 | pro |
| demo_user | 0 | 999 | free |

---

## Примеры использования в CRM

### Сценарий 1: Регистрация нового пользователя
```bash
# 1. Создаем пользователя с бесплатным тарифом
curl -X POST http://localhost:8000/crm/api/user \
  -H "Content-Type: application/json" \
  -d '{
    "id": "new_client_789",
    "user_name": "Michael Brown",
    "email": "michael.brown@example.com"
  }'

# 2. Проверяем созданного пользователя
curl -X GET http://localhost:8000/crm/api/user/new_client_789/balance
```

### Сценарий 2: Создание пользователя с активной подпиской
```bash
# Создаем пользователя сразу с Pro тарифом и начисленными минутами
curl -X POST http://localhost:8000/crm/api/user \
  -H "Content-Type: application/json" \
  -d '{
    "id": "premium_user_555",
    "user_name": "Sarah Wilson",
    "email": "sarah.wilson@example.com",
    "remaining_seconds": 18000,
    "tariff": "pro",
    "payment_status": "active"
  }'
```

### Сценарий 3: Пользователь оплатил подписку
```bash
# 1. Проверяем текущий баланс
curl -X GET http://localhost:8000/crm/api/user/zeqipe/balance

# 2. Начисляем 300 минут (18000 секунд) по тарифу Pro
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "add_remaining_seconds": 18000,
    "tariff": "pro",
    "payment_status": "active"
  }'
```

### Сценарий 4: Компенсация за технические проблемы
```bash
# Начисляем 60 бонусных минут как несгораемые
# (используем отдельный endpoint для permanent_seconds из database.py)
```

### Сценарий 5: Деактивация пользователя
```bash
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/balance \
  -H "Content-Type: application/json" \
  -d '{
    "payment_status": "expired"
  }'
```

### Сценарий 6: Назначение пользователя модератором
```bash
# Назначаем роль модератора
curl -X PUT http://localhost:8000/crm/api/user/zeqipe/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "moderator"
  }'

# Проверяем статус
curl -X GET http://localhost:8000/crm/api/user/zeqipe/balance
```

---

## Интеграция с CRM платформой

### Передача языка интерфейса через cookies

При переходе пользователя с CRM платформы на поддомен приложения, **CRM должна устанавливать cookie** с языком интерфейса.

**Параметры cookie:**
- **Ключ:** `language`
- **Значение:** код языка (например: `ru`, `en`, `es`, `fr` и т.д.)

**Назначение:**
- Поддомен FluentGo получает информацию о предпочитаемом языке пользователя
- Автоматическое переключение интерфейса на нужный язык
- Сохранение языковых предпочтений при навигации

**Важно:**
- Cookie должна быть установлена **до** перенаправления пользователя на поддомен
- Рекомендуется использовать `SameSite=Lax` для работы между поддоменами
- Domain должен быть `.fluentgo.com` (с точкой в начале) для доступа со всех поддоменов

---

## Безопасность

⚠️ **Важно:** CRM API предназначен только для внутреннего использования.

Рекомендуется:
- Добавить авторизацию (JWT токены, API ключи)
- Ограничить доступ по IP
- Логировать все операции изменения баланса
- Использовать HTTPS в продакшене

---

## Контакты

Для вопросов и поддержки: support@fluentgo.com

