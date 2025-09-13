from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

router = APIRouter()

# Получаем путь к статическим файлам
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'static'

# Монтируем статические файлы
router.mount("/static", StaticFiles(directory=str(OUT_DIR)), name="static")

@router.get("/")
async def read_index():
    """Главная страница"""
    index_path = OUT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        raise HTTPException(status_code=404, detail="Index file not found")

@router.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """SPA fallback - на все остальные запросы отдаём index.html (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ!)"""
    # Если запрашивается файл, пытаемся его найти
    file_path = OUT_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Иначе отдаём index.html для SPA роутинга
    index_path = OUT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")
