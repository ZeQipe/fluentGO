from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from database import db_handler
from routers import api, websocket, static

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Добавляем заголовки для работы с куки
        if request.method in ["GET", "POST", "PUT", "DELETE"]:
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "*"
        
        return response

def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    
    app = FastAPI(title="FluentGo Voice Assistant", version="1.0.0")
    
    # CSRF middleware
    app.add_middleware(CSRFMiddleware)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000", 
            "http://localhost:3000", 
            "http://172.18.0.1:3000",
            "http://127.0.0.1:8000",
            "http://localhost:8000"
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
    
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
    
    # Подключение роутеров
    app.include_router(api.router, prefix="/api", tags=["API"])
    app.include_router(websocket.router, tags=["WebSocket"])
    app.include_router(static.router, tags=["Static"])
    
    return app
