import os
import sys

# Подавляем предупреждения NNPACK от PyTorch ДО импорта любых модулей
os.environ['NNPACK_DISABLE'] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['OMP_NUM_THREADS'] = '1'

# Подавляем stderr для torch (временно при импорте)
import warnings
warnings.filterwarnings('ignore')

# Временно перенаправляем stderr чтобы подавить NNPACK warnings при импорте torch
import io
_original_stderr = sys.stderr
sys.stderr = io.StringIO()

from pathlib import Path
from app import create_app

# Восстанавливаем stderr после импорта
sys.stderr = _original_stderr

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
    host="127.0.0.1", 
    port=8055, 
    reload=True)