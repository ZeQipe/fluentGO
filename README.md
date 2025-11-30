# FluentGO - Voice Assistant Platform

AI-powered voice assistant for English language learning with real-time conversation practice.

## 🚀 Quick Start

### Prerequisites

- Docker и Docker Compose
- Минимум 4GB RAM
- Минимум 10GB свободного места на диске

### Запуск в продакшене

1. **Клонируйте репозиторий:**
```bash
git clone <repository-url>
cd fluentGO
```

2. **Настройте переменные окружения:**
```bash
cp env.example .env
nano .env  # Отредактируйте настройки
```

**ВАЖНО! Обязательно измените:**
- `POSTGRES_PASSWORD` - пароль для PostgreSQL
- `JWT_secret` - секретный ключ для JWT
- `OPENAI_API_KEY` - ключ API OpenAI
- `PAYMENT_API_TOKEN` - токен платежного API

3. **Запустите приложение:**
```bash
docker-compose up -d
```

4. **Проверьте статус:**
```bash
docker-compose ps
docker-compose logs -f app
```

Приложение будет доступно на `http://localhost:8055`

---

## 📦 Архитектура

### Сервисы

- **app** - FastAPI приложение (порт 8055)
- **postgres** - PostgreSQL 15 база данных (порт 5432)
- **redis** - Redis для кэширования (порт 6379)

### Volumes

- `postgres_data` - данные PostgreSQL
- `redis_data` - данные Redis
- `app_logs` - логи приложения
- `.:/app` - монтирование текущей директории в контейнер

---

## 🗄️ База данных

### PostgreSQL

Приложение использует PostgreSQL с SQLAlchemy 2.0 ORM и asyncpg драйвером.

**Структура таблиц:**

#### `users`
- `id` (TEXT, PRIMARY KEY)
- `user_name` (TEXT)
- `remaining_seconds` (INTEGER) - сгораемые секунды
- `permanent_seconds` (INTEGER) - несгораемые секунды
- `email` (TEXT)
- `tariff` (TEXT)
- `payment_status` (TEXT)
- `status` (TEXT) - статус пользователя (user/vip/CMO)
- `subscription_id` (TEXT)
- `payment_system` (TEXT)
- `subscription_status` (TEXT)

#### `topic`
- `id` (INTEGER, PRIMARY KEY, AUTOINCREMENT)
- `user_id` (TEXT, FOREIGN KEY → users.id)
- `title` (TEXT)
- `description` (TEXT)

### Миграция из SQLite

Если у вас есть существующая база `users.db` (SQLite), вы можете мигрировать данные:

```bash
# TODO: Создать скрипт миграции
python scripts/migrate_sqlite_to_postgres.py
```

---

## 🔧 Управление

### Остановка приложения

```bash
docker-compose down
```

### Перезапуск

```bash
docker-compose restart
```

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только приложение
docker-compose logs -f app

# Только база данных
docker-compose logs -f postgres
```

### Подключение к PostgreSQL

```bash
docker-compose exec postgres psql -U fluentgo_user -d fluentgo
```

### Резервное копирование БД

```bash
# Создание бэкапа
docker-compose exec postgres pg_dump -U fluentgo_user fluentgo > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из бэкапа
docker-compose exec -T postgres psql -U fluentgo_user fluentgo < backup_20240101_120000.sql
```

---

## 🛠️ Разработка

### Локальный запуск без Docker

1. **Установите зависимости:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
.\venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

2. **Настройте локальный PostgreSQL:**
```bash
# Установите PostgreSQL
# Создайте базу данных
createdb fluentgo

# Укажите DATABASE_URL в .env
DATABASE_URL=postgresql+asyncpg://your_user:your_password@localhost:5432/fluentgo
```

3. **Запустите приложение:**
```bash
python run.py
```

### Структура проекта

```
fluentGO/
├── app.py                 # Главное FastAPI приложение
├── database.py            # SQLAlchemy модели и обработчики
├── run.py                 # Точка входа
├── config.py              # Конфигурация
├── requirements.txt       # Python зависимости
├── docker-compose.yml     # Docker конфигурация
├── Dockerfile            # Docker образ приложения
│
├── routers/              # API роуты
│   ├── api.py           # Основные API эндпоинты
│   ├── websocket.py     # WebSocket соединения
│   └── crm.py           # CRM интеграция
│
├── services/            # Бизнес-логика
│   ├── jwt_service.py
│   ├── payment_manager.py
│   ├── config_parser.py
│   └── ...
│
├── vad_realtime/        # VAD режим реального времени
├── button_realtime/     # Button режим
├── static/              # Frontend файлы
└── document/            # Конфигурационные файлы
```

---

## 📝 API Документация

После запуска приложения документация доступна по адресам:

- Swagger UI: `http://localhost:8055/docs`
- ReDoc: `http://localhost:8055/redoc`

---

## 🔐 Безопасность

### Важные моменты:

1. **Обязательно измените пароли в `.env`**
2. **Используйте сильные пароли для PostgreSQL**
3. **Никогда не коммитьте `.env` в git**
4. **Регулярно делайте бэкапы базы данных**
5. **Используйте HTTPS в продакшене**

---

## 🐛 Troubleshooting

### Приложение не запускается

```bash
# Проверьте логи
docker-compose logs app

# Проверьте подключение к БД
docker-compose exec app python -c "import asyncio; from database import db_handler; asyncio.run(db_handler.initialize())"
```

### PostgreSQL не принимает соединения

```bash
# Проверьте статус
docker-compose ps postgres

# Перезапустите
docker-compose restart postgres

# Проверьте логи
docker-compose logs postgres
```

### Ошибки миграции

```bash
# Пересоздайте таблицы
docker-compose exec app python -c "
import asyncio
from database import Base, db_handler

async def recreate_tables():
    async with db_handler.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print('Таблицы пересозданы')

asyncio.run(recreate_tables())
"
```

---

## 📊 Мониторинг

### Health Check

```bash
curl http://localhost:8055/api/test-db
```

### Метрики PostgreSQL

```sql
-- Размер базы данных
SELECT pg_size_pretty(pg_database_size('fluentgo'));

-- Активные соединения
SELECT count(*) FROM pg_stat_activity;

-- Размер таблиц
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 📜 License

[Укажите лицензию]

## 👥 Contributors

[Укажите контрибьюторов]

---

**Версия:** 2.0.0  
**Дата обновления:** 30.11.2025  
**Изменения:** Миграция на PostgreSQL, удаление nginx, оптимизация Docker конфигурации

