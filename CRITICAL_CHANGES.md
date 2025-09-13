# КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ ДЛЯ РАБОТЫ СЕРВЕРА

## 1. ✅ ИСПРАВЛЕНО: run.py
Убран root_path (он ломал роутинг):
```python
uvicorn.run(
    "run:app",
    host="127.0.0.1",
    port=8055,
    reload=True
    # root_path убран!
)
```

## 2. ✅ ИСПРАВЛЕНО: nginx_final.conf
Правильное проксирование БЕЗ root_path:
- `/api/*` → проксируется на `http://127.0.0.1:8055/api/*`
- `/ws` → проксируется на `http://127.0.0.1:8055/ws`
- `/ws-button` → проксируется на `http://127.0.0.1:8055/ws-button`
- `/fluentgo/api/*` → rewrite и проксирование на `/api/*` (опционально)

## 3. ❌ НУЖНО ИСПРАВИТЬ В .env:

```env
# БЫЛО:
PORT=8000
VAD_WS_ENDPOINT=wss://en.workandtravel.com/vad_realtime/ws
BUTTON_WS_ENDPOINT=wss://en.workandtravel.com/button_realtime/ws
BUTTON_UPLOAD_ENDPOINT=https://en.workandtravel.com/button_realtime/upload-audio
DATABASE_PATH=./server/users.db
TEMP_AUDIO_DIR=./server/temp
COOKIE_SECURE=false
DEBUG=true

# НУЖНО:
PORT=8055
VAD_WS_ENDPOINT=wss://en.workandtravel.com/ws
BUTTON_WS_ENDPOINT=wss://en.workandtravel.com/ws-button
BUTTON_UPLOAD_ENDPOINT=https://en.workandtravel.com/api/upload-audio/
DATABASE_PATH=./users.db
TEMP_AUDIO_DIR=./temp
COOKIE_SECURE=true
DEBUG=false
```

## 4. ❌ НУЖНО ОБНОВИТЬ CORS в app.py:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000", 
        "http://localhost:3000", 
        "http://172.18.0.1:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "https://en.workandtravel.com"  # <-- ДОБАВИТЬ
    ],
    # ...
)
```

## ТЕСТИРОВАНИЕ:

После всех изменений проверьте:

1. **API**: `https://en.workandtravel.com/api/test-db`
2. **WebSocket VAD**: `wss://en.workandtravel.com/ws?voice=alloy`
3. **WebSocket Button**: `wss://en.workandtravel.com/ws-button?voice=sage`
4. **Альтернативный путь**: `https://en.workandtravel.com/fluentgo/api/test-db`

## ЗАПУСК СЕРВЕРА:

```bash
cd /path/to/server
python run.py
```

Или для продакшена без reload:
```bash
uvicorn run:app --host 127.0.0.1 --port 8055
```

## ПЕРЕЗАПУСК NGINX:

```bash
sudo nginx -t  # Проверка конфигурации
sudo systemctl reload nginx  # Перезагрузка
```
