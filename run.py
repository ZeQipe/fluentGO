from pathlib import Path
from app import create_app

# Проверяем, что папка static существует
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / 'static'

print(f"Server root: {ROOT}")
print(f"Static directory: {OUT_DIR}")
print(f"Static directory exists: {OUT_DIR.exists()}")

if not OUT_DIR.exists():
    print(f"ERROR: Static directory {OUT_DIR} does not exist!")
    exit(1)

# Создаем приложение
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("run:app", 
    host="0.0.0.0", 
    port=8055, 
    reload=True)