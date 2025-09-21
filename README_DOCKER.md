# FluentGO - Docker Deployment Guide

Полная Docker-конфигурация для развертывания FluentGO Voice Assistant с Nginx, базой данных и всеми необходимыми сервисами.

## 🚀 Быстрый запуск

### 1. Подготовка окружения

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd FluentoGO/server

# Скопируйте файл с переменными окружения
cp env.example .env

# Отредактируйте .env файл (см. раздел "Настройка переменных")
nano .env
```

### 2. Настройка переменных окружения

Откройте файл `.env` и заполните **обязательные** переменные:

```bash
# ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ:
OPENAI_API_KEY=sk-your-openai-key-here
ELEVENLABS_API_KEY=your-elevenlabs-key-here
JWT_secret=your-super-secret-jwt-key-change-this

# Замените your-domain.com на ваш домен:
VAD_WS_ENDPOINT=wss://your-domain.com/ws
BUTTON_WS_ENDPOINT=wss://your-domain.com/ws-button
BUTTON_UPLOAD_ENDPOINT=https://your-domain.com/api/upload-audio/
WEBHOOK_URL=https://your-domain.com/api/webhook/payment
PAYMENT_RETURN_URL=https://your-domain.com/payment/success
ALLOWED_ORIGINS=https://your-domain.com
```

### 3. Запуск всех сервисов

```bash
# Сборка и запуск всех контейнеров
docker-compose up -d --build

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f app
```

### 4. Проверка работоспособности

```bash
# Проверка API
curl http://localhost/api/test-db

# Проверка Nginx
curl http://localhost/health

# Проверка через браузер
# Откройте http://localhost в браузере
```

## 📁 Структура проекта

```
server/
├── docker-compose.yml      # Основная конфигурация Docker
├── Dockerfile             # Образ FastAPI приложения
├── nginx.conf             # Конфигурация Nginx
├── env.example            # Шаблон переменных окружения
├── .env                   # Ваши переменные (создать из env.example)
├── app.py                 # FastAPI приложение
├── run.py                 # Точка входа
├── requirements.txt       # Python зависимости
├── database.py           # Работа с базой данных
├── routers/              # API роуты
├── services/             # Бизнес-логика
├── static/               # Статические файлы (Next.js build)
├── temp/                 # Временные файлы
└── users.db              # База данных SQLite
```

## 🐳 Docker сервисы

### 1. **app** - FastAPI приложение
- **Порт**: 8055 (внутренний)
- **Функции**: API, WebSocket, обработка аудио
- **Зависимости**: Python 3.11, PyTorch, OpenAI, ElevenLabs

### 2. **nginx** - Reverse Proxy
- **Порты**: 80 (HTTP), 443 (HTTPS)
- **Функции**: Проксирование, статические файлы, SSL
- **Upstream**: app:8055

### 3. **redis** - Кэширование (опционально)
- **Порт**: 6379
- **Функции**: Кэш, сессии
- **Данные**: Сохраняются в volume

## 🔧 Конфигурация

### Nginx маршрутизация

| Путь | Назначение | Upstream |
|------|------------|----------|
| `/api/*` | REST API | app:8055 |
| `/ws` | WebSocket VAD | app:8055 |
| `/ws-button` | WebSocket Button | app:8055 |
| `/_next/*` | Next.js статика | app:8055 |
| `/health` | Проверка здоровья | app:8055/api/test-db |
| `/*` | SPA роутинг | app:8055 |

### Переменные окружения

#### Обязательные:
- `OPENAI_API_KEY` - Ключ OpenAI для GPT и TTS
- `ELEVENLABS_API_KEY` - Ключ ElevenLabs для голоса
- `JWT_secret` - Секрет для JWT токенов

#### Важные для продакшена:
- `VAD_WS_ENDPOINT` - WebSocket endpoint для VAD
- `BUTTON_WS_ENDPOINT` - WebSocket endpoint для Button
- `ALLOWED_ORIGINS` - CORS origins
- `COOKIE_SECURE=true` - Безопасные куки

## 🛠️ Управление

### Основные команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Пересборка
docker-compose up -d --build

# Логи
docker-compose logs -f [service_name]

# Вход в контейнер
docker-compose exec app bash
```

### Обновление кода

```bash
# Остановка сервисов
docker-compose down

# Обновление кода
git pull

# Пересборка и запуск
docker-compose up -d --build
```

### Резервное копирование

```bash
# Создание бэкапа базы данных
docker-compose exec app cp /app/users.db /app/backup_$(date +%Y%m%d_%H%M%S).db

# Копирование бэкапа на хост
docker cp fluentgo_app:/app/backup_*.db ./backups/
```

## 🔍 Мониторинг и отладка

### Проверка здоровья сервисов

```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Проверка портов
netstat -tlnp | grep -E ':(80|443|8055|6379)'
```

### Логи и отладка

```bash
# Все логи
docker-compose logs

# Логи конкретного сервиса
docker-compose logs -f app
docker-compose logs -f nginx

# Последние 100 строк
docker-compose logs --tail=100 app

# Логи с временными метками
docker-compose logs -t app
```

### Тестирование API

```bash
# Проверка базы данных
curl http://localhost/api/test-db

# Получение тарифов
curl http://localhost/api/tariffs

# Демо пользователь
curl http://localhost/api/demo-user

# WebSocket тест (требует wscat)
wscat -c ws://localhost/ws?voice=alloy
```

## 🔒 Безопасность

### Продакшен настройки

1. **SSL сертификаты**:
   ```bash
   # Создайте папку для SSL
   mkdir ssl
   # Поместите сертификаты в ssl/
   # Обновите nginx.conf для HTTPS
   ```

2. **Firewall**:
   ```bash
   # Откройте только необходимые порты
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```

3. **Переменные окружения**:
   - Используйте сильные пароли
   - Не коммитьте `.env` в git
   - Регулярно меняйте `JWT_secret`

### Рекомендации

- Используйте HTTPS в продакшене
- Настройте регулярные бэкапы
- Мониторьте использование ресуров
- Обновляйте зависимости регулярно
- Используйте Docker secrets для чувствительных данных

## 🚨 Устранение неполадок

### Частые проблемы

1. **Контейнер не запускается**:
   ```bash
   docker-compose logs app
   # Проверьте переменные в .env
   ```

2. **502 Bad Gateway**:
   ```bash
   # Проверьте, что app контейнер запущен
   docker-compose ps
   # Проверьте логи nginx
   docker-compose logs nginx
   ```

3. **WebSocket не работает**:
   ```bash
   # Проверьте nginx конфигурацию
   docker-compose exec nginx nginx -t
   # Проверьте переменные WS endpoints
   ```

4. **База данных не найдена**:
   ```bash
   # Создайте пустую базу
   touch users.db
   # Перезапустите приложение
   docker-compose restart app
   ```

### Полная переустановка

```bash
# Остановка и удаление всех контейнеров
docker-compose down -v

# Удаление образов
docker-compose down --rmi all

# Очистка volumes
docker volume prune

# Пересборка с нуля
docker-compose up -d --build
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь, что все переменные в `.env` заполнены
3. Проверьте доступность внешних API (OpenAI, ElevenLabs)
4. Убедитесь, что порты не заняты другими процессами

---

**Готово!** 🎉 Ваш FluentGO сервер должен работать на `http://localhost`
