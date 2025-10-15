# РОУТЫ С ПРЕФИКСОМ

## 🔧 Настройка префикса

В файле `.env` добавлена переменная:
```env
SERVER_PREFIX=/fluent
```

## 📋 ВСЕ РОУТЫ С ПРЕФИКСОМ `/fluent`

### **🔗 API Роуты (`/fluent/api/`)**

#### **🔐 Аутентификация и сессии:**
- `GET /fluent/api/session-id` - Получение ID сессии для WebSocket
- `GET /fluent/api/check-auth` - Проверка JWT токена
- `GET /fluent/api/login` - Авторизация пользователей
- `GET /fluent/api/logout` - Выход из системы

#### **👤 Пользователи и баланс:**
- `GET /fluent/api/test-db` - Тест базы данных
- `GET /fluent/api/demo-user` - Информация о демо пользователе
- `GET /fluent/api/tariffs` - Получение тарифов
- `GET /fluent/api/language` - Получение языка
- `PUT /fluent/api/language` - Установка языка

#### **🎵 Аудио обработка:**
- `POST /fluent/api/upload-audio/` - Загрузка аудио (Button Realtime)

#### **💳 Платежи:**
- `POST /fluent/api/create-payment` - Создание платежа
- `GET /fluent/api/payment-status/{internal_order_id}` - Статус платежа
- `POST /fluent/api/webhook/payment` - Webhook для платежей

#### **📚 Темы:**
- `POST /fluent/api/topics` - Создание темы
- `GET /fluent/api/topics` - Получение тем пользователя
- `PUT /fluent/api/topics` - Обновление темы
- `DELETE /fluent/api/topics/{topic_id}` - Удаление темы

#### **❓ Справка:**
- `GET /fluent/api/help` - Получение справочной информации

---

### **🔗 CRM Роуты (`/fluent/crm/`)**

#### **👥 Управление пользователями:**
- `GET /fluent/crm/api/tariffs` - Получение тарифов для CRM
- `POST /fluent/crm/api/user` - Создание пользователя
- `GET /fluent/crm/api/user/{user_id}/balance` - Баланс пользователя
- `PUT /fluent/crm/api/user/{user_id}/balance` - Обновление баланса
- `PUT /fluent/crm/api/user/{user_id}/status` - Изменение статуса пользователя

---

### **🔗 WebSocket Роуты**

#### **🎤 Голосовое взаимодействие:**
- `WS /fluent/ws` - VAD Realtime (автоматическое распознавание речи)
- `WS /fluent/ws-button` - Button Realtime (ручное управление записью)

---

### **🔗 Статические файлы**

#### **📁 Фронтенд:**
- `GET /fluent/` - Главная страница
- `GET /fluent/{full_path:path}` - SPA fallback (все остальные пути)
- `GET /fluent/_next/*` - Next.js ассеты
- `GET /fluent/assets/*` - Статические ресурсы

---

## **📊 Сводка по типам роутов:**

| **Тип** | **Количество** | **Назначение** |
|---------|----------------|----------------|
| **API GET** | 8 | Получение данных |
| **API POST** | 6 | Создание/отправка данных |
| **API PUT** | 2 | Обновление данных |
| **API DELETE** | 1 | Удаление данных |
| **CRM GET** | 2 | CRM получение данных |
| **CRM POST** | 1 | CRM создание |
| **CRM PUT** | 2 | CRM обновление |
| **WebSocket** | 2 | Реальное время |
| **Static** | 4 | Статические файлы |

**Всего роутов: 28**

---

## **🔧 Изменения в коде:**

### **1. app.py:**
- Добавлен импорт `load_dotenv()`
- Получение `SERVER_PREFIX` из переменной окружения
- Все роутеры подключены с префиксом
- Статические файлы монтируются с префиксом
- Fallback роут обновлен с префиксом

### **2. env.example:**
- Добавлена переменная `SERVER_PREFIX=/fluent`
- Обновлены все URL в переменных окружения

### **3. Переменные окружения обновлены:**
- `VAD_WS_ENDPOINT=wss://your-domain.com/fluent/ws`
- `BUTTON_WS_ENDPOINT=wss://your-domain.com/fluent/ws-button`
- `BUTTON_UPLOAD_ENDPOINT=https://your-domain.com/fluent/api/upload-audio/`
- `WEBHOOK_URL=https://your-domain.com/fluent/api/webhook/payment`
- `PAYMENT_RETURN_URL=https://your-domain.com/fluent/payment/success`
- `NEXT_PUBLIC_UPLOAD_URL=/fluent/api/upload-audio/`

---

## **✅ Результат:**

Теперь **ВСЕ роуты** начинаются с префикса `/fluent` (или любого другого, указанного в `SERVER_PREFIX`).

**Примеры:**
- API: `https://domain.com/fluent/api/session-id`
- WebSocket: `wss://domain.com/fluent/ws`
- CRM: `https://domain.com/fluent/crm/api/tariffs`
- Статика: `https://domain.com/fluent/`
