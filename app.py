from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from database import db_handler
from routers import api, websocket, crm

load_dotenv()

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Добавляем заголовки для работы с куки
        if request.method in ["GET", "POST", "PUT", "DELETE"]:
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "*"
        
        return response

OUT_DIR = "static"

def try_serve(path: str) -> FileResponse | None:
    """Пробуем несколько вариантов: точный файл, index.html в папке, вариант .html."""
    # точный путь
    if os.path.isfile(path):
        return FileResponse(path)

    # .../index.html
    idx = os.path.join(path, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)

    # вариант file.html
    htmlvar = path + ".html"
    if os.path.isfile(htmlvar):
        return FileResponse(htmlvar)

    return None

def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    
    # Получаем префикс из переменной окружения
    server_prefix = os.getenv("SERVER_PREFIX", "")
    
    # Создаем папку temp при запуске приложения
    os.makedirs("temp", exist_ok=True)
    
    app = FastAPI(title="FluentGo Voice Assistant", version="1.0.0")
    
    # CSRF middleware
    app.add_middleware(CSRFMiddleware)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )

    # Редирект добавляет слэш, если в out есть папка с index.html (удобно при trailingSlash:true)
    @app.middleware("http")
    async def ensure_trailing_slash_for_dirs(request: Request, call_next):
        path = request.url.path
        
        # Убираем префикс из пути для проверки статических файлов
        if server_prefix and path.startswith(server_prefix):
            path = path[len(server_prefix):]
        
        # не трогаем запросы к файлам
        if "." in os.path.basename(path):
            return await call_next(request)

        candidate_dir = os.path.join(OUT_DIR, path.lstrip("/"))
        if (
            os.path.isdir(candidate_dir)
            and os.path.isfile(os.path.join(candidate_dir, "index.html"))
            and not path.endswith("/")
        ):
            # ✅ сохраняем query при редиректе
            new_path = request.url.path + "/"
            new_url = request.url.replace(path=new_path)  # query сохраняется автоматически
            return RedirectResponse(url=str(new_url), status_code=308)

        return await call_next(request)
    
    # Ассеты Next (JS/CSS/имиджи с хешами)
    app.mount(f"{server_prefix}/_next", StaticFiles(directory=os.path.join(OUT_DIR, "_next")), name="_next")

    # Если у тебя есть собственная папка static/assets в out — можно смонтировать и её:
    assets_dir = os.path.join(OUT_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount(f"{server_prefix}/assets", StaticFiles(directory=assets_dir), name="assets")
    
    # Инициализация базы данных и VAD при запуске
    @app.on_event("startup")
    async def startup_event():
        print("Инициализация базы данных...")
        await db_handler.initialize()
        print("База данных готова к работе!")
        
        # Инициализация VAD моделей
        print("Инициализация VAD моделей...")
        from vad_realtime.transcribation_utils import initialize_vad
        await initialize_vad()
        print("VAD модели готовы к работе!")
        
        # Запуск фоновой задачи очистки неактивных соединений
        import asyncio
        from routers.websocket import vad_connection_manager, button_connection_manager
        
        async def cleanup_task():
            while True:
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
                try:
                    await vad_connection_manager.cleanup_stale_connections()
                    await button_connection_manager.cleanup_stale_connections()
                except Exception as e:
                    print(f"Ошибка очистки соединений: {e}")
        
        asyncio.create_task(cleanup_task())
        print("Фоновая задача очистки соединений запущена!")
    
    # Подключение роутеров с префиксом
    app.include_router(api.router, prefix=f"{server_prefix}/api", tags=["API"])
    app.include_router(crm.router, prefix=f"{server_prefix}/crm", tags=["CRM"])
    app.include_router(websocket.router, prefix=server_prefix, tags=["WebSocket"])

    @app.get(f"{server_prefix}/{{full_path:path}}")
    async def serve_any(full_path: str):
        # сначала пытаемся отдать точный файл из out
        base = os.path.join(OUT_DIR, full_path.lstrip("/"))
        resp = try_serve(base)
        if resp:
            return resp

        # 404.html если есть
        not_found = os.path.join(OUT_DIR, "404.html")
        if os.path.isfile(not_found):
            return FileResponse(not_found, status_code=404)

        # или index.html как общий fallback
        index = os.path.join(OUT_DIR, "index.html")
        if os.path.isfile(index):
            # можно вернуть 200 или 404 в зависимости от предпочтений
            return FileResponse(index, status_code=200)

        return Response("Build is missing. Run next build.", status_code=500)
    
    return app
