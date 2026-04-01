"""
FastAPI сервис для конвертации документов DOC/XLS → DOCX/XLSX
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ✅ Прямой импорт: converter.py лежит в той же папке
from converter import DocumentConverter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Converter API",
    description="API для конвертации документов через LibreOffice",
    version="1.0.0"
)

# CORS для вызовов из JupyterHub
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ В продакшене укажите конкретные origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔹 Универсальное определение путей (локально / Docker)
def _resolve_data_dir(env_var: str, default_docker: str, default_local: str) -> Path:
    """
    Возвращает путь к папке данных:
    - Из переменной окружения (если задана)
    - Иначе: /app/... для Docker, ./... для локальной разработки
    """
    if os.getenv(env_var):
        return Path(os.getenv(env_var)).resolve()
    
    in_docker = Path("/.dockerenv").exists()
    return Path(default_docker if in_docker else default_local).resolve()


def _resolve_libreoffice_path() -> str:
    """Определяет путь к LibreOffice с учётом ОС и окружения"""
    # Если задан через ENV — используем
    if os.getenv("LIBREOFFICE_PATH"):
        return os.getenv("LIBREOFFICE_PATH")
    
    # Проверяем типичные пути
    candidates = [
        "/usr/bin/libreoffice",           # Linux (Docker)
        "/usr/bin/soffice",               # Альтернатива Linux
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
        shutil.which("libreoffice"),      # В PATH
        shutil.which("soffice"),          # В PATH
    ]
    
    for path in candidates:
        if path and Path(path).exists():
            return path
    
    # Fallback
    return "/usr/bin/libreoffice"


# Определяем пути
RAW_DATA_DIR = _resolve_data_dir("RAW_DATA_DIR", "/app/raw_data", "./raw_data")
PREPARED_DATA_DIR = _resolve_data_dir("PREPARED_DATA_DIR", "/app/prepared_data", "./prepared_data")
LIBREOFFICE_PATH = _resolve_libreoffice_path()

# Создаём директории при старте
for dir_path in [RAW_DATA_DIR, PREPARED_DATA_DIR]:
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Папка данных: {dir_path}")
    except Exception as e:
        logger.error(f"❌ Не удалось создать папку {dir_path}: {e}")


# 🔹 Pydantic модели для ответов

class FileInfo(BaseModel):
    """Метаданные одного файла"""
    name: str
    relative_path: str
    size_bytes: int
    modified_timestamp: float
    modified_human: Optional[str] = None

class FileListResponse(BaseModel):
    path: str
    files: List[FileInfo]

# ✅ Новая модель для статистики конвертации
class ConversionStats(BaseModel):
    total: int
    copied: int
    converted_doc: int
    converted_xls: int
    failed: int
    failed_files: List[str]  # ✅ Список строк, а не int!

class ConvertResponse(BaseModel):
    success: bool
    message: str
    stats: Optional[ConversionStats] = None  # ✅ Используем новую модель

class DeleteResponse(BaseModel):
    success: bool
    message: str


# 🔹 Вспомогательные функции безопасности
def _validate_path_param(path: str) -> Path:
    """Разрешаем только 'raw' или 'prepared' для защиты от path traversal"""
    if path not in ("raw", "prepared"):
        raise HTTPException(status_code=400, detail="Invalid path. Use 'raw' or 'prepared'")
    return RAW_DATA_DIR if path == "raw" else PREPARED_DATA_DIR

def _safe_join(base: Path, filename: str) -> Path:
    """Безопасное соединение: извлекаем только имя файла, блокируем ../"""
    clean_name = Path(filename).name
    result = base / clean_name
    try:
        result.resolve().relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return result


# 🔹 Endpoints
@app.on_event("startup")
async def startup_event():
    """Проверка окружения при старте"""
    logger.info(f"✅ Сервис запущен")
    logger.info(f"   RAW_DATA_DIR:      {RAW_DATA_DIR}")
    logger.info(f"   PREPARED_DATA_DIR: {PREPARED_DATA_DIR}")
    logger.info(f"   LIBREOFFICE_PATH:  {LIBREOFFICE_PATH}")
    logger.info(f"   LibreOffice exists: {Path(LIBREOFFICE_PATH).exists()}")

@app.get("/health")
async def health_check():
    """Health check для Kubernetes / мониторинга"""
    return {
        "status": "ok",
        "libreoffice_available": Path(LIBREOFFICE_PATH).exists(),
        "raw_dir_exists": RAW_DATA_DIR.exists(),
        "prepared_dir_exists": PREPARED_DATA_DIR.exists()
    }

@app.post("/convert", response_model=ConvertResponse)
async def convert_documents():
    """
    Запускает конвертацию всех файлов из raw_data → prepared_data.
    """
    try:
        if not Path(LIBREOFFICE_PATH).exists():
            raise RuntimeError(f"LibreOffice не найден: {LIBREOFFICE_PATH}")
            
        converter = DocumentConverter(
            raw_dir=str(RAW_DATA_DIR),
            prepared_dir=str(PREPARED_DATA_DIR),
            libreoffice_path=LIBREOFFICE_PATH
        )
        stats = converter.process()
        
        # ✅ Создаём модель статистики с правильной типизацией
        stats_model = ConversionStats(
            total=stats["total"],
            copied=stats["copied"],
            converted_doc=stats["converted_doc"],
            converted_xls=stats["converted_xls"],
            failed=stats["failed"],
            failed_files=stats.get("failed_files", [])  # ✅ Гарантируем список
        )
        
        return ConvertResponse(
            success=stats["failed"] == 0,
            message="Конвертация завершена успешно" if stats["failed"] == 0 else f"Завершено с ошибками: {stats['failed']}",
            stats=stats_model
        )
        
    except RuntimeError as e:
        logger.error(f"❌ Ошибка инициализации конвертера: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization error: {str(e)}")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка конвертации: {e}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)[:200]}")

@app.get("/files/{path}", response_model=FileListResponse)
async def list_files(path: str, recursive: bool = Query(default=False)):
    """Список файлов в папке."""
    base_dir = _validate_path_param(path)
    
    try:
        if not base_dir.exists():
            return FileListResponse(path=path, files=[])
            
        files = base_dir.rglob('*') if recursive else base_dir.iterdir()
        
        file_list = []
        for f in sorted(files, key=lambda x: x.name):
            if f.is_file():
                stat = f.stat()
                file_list.append(FileInfo(
                    name=f.name,
                    relative_path=str(f.relative_to(base_dir)),
                    size_bytes=stat.st_size,
                    modified_timestamp=stat.st_mtime,
                    modified_human=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                ))
        
        return FileListResponse(path=path, files=file_list)
        
    except Exception as e:
        logger.error(f"❌ Ошибка чтения файлов: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@app.post("/upload", response_model=FileInfo)
async def upload_file(file: UploadFile = File(...)):
    """
    Загрузить файл в raw_data для последующей конвертации.

    Поддерживаемые форматы: .doc, .docx, .xls, .xlsx

    Example (notebook):
        with open("document.doc", "rb") as f:
            requests.post(f"{BASE_URL}/upload", files={"file": f})
    """
    allowed_extensions = {".doc", ".docx", ".xls", ".xlsx"}
    suffix = Path(file.filename).suffix.lower()

    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат '{suffix}'. Допустимы: {', '.join(allowed_extensions)}"
        )

    save_path = _safe_join(RAW_DATA_DIR, file.filename)

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        stat = save_path.stat()
        logger.info(f"⬆️ Загружен файл: {save_path} ({stat.st_size} байт)")
        return FileInfo(
            name=save_path.name,
            relative_path=save_path.name,
            size_bytes=stat.st_size,
            modified_timestamp=stat.st_mtime,
            modified_human=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        )
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки файла: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/download/{path}/{file}")
async def download_file(path: str, file: str):
    """
    Скачать файл из указанной папки на локальное устройство.

    Params:
    - path: "raw" или "prepared"
    - file: имя файла (без путей)

    Example:
        curl -OJ http://localhost:8000/download/prepared/document.docx
    """
    base_dir = _validate_path_param(path)
    file_path = _safe_join(base_dir, file)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{file}' not found in '{path}'")

    logger.info(f"⬇️ Скачивание файла: {file_path}")
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


@app.delete("/delete/{path}/{file}", response_model=DeleteResponse)
async def delete_file(path: str, file: str):
    """
    Удаление файла из указанной папки.
    
    Params:
    - path: "raw" или "prepared"
    - file: имя файла (без путей)
    """
    base_dir = _validate_path_param(path)
    file_path = _safe_join(base_dir, file)
    
    try:
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        file_path.unlink()
        logger.info(f"🗑️ Удалён файл: {file_path}")
        return DeleteResponse(success=True, message=f"File '{file}' deleted from {path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка удаления: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@app.get("/stats")
async def get_folder_stats():
    """Базовая статистика по папкам"""
    def _count(directory: Path):
        if not directory.exists():
            return {"total": 0, "extensions": []}
        files = [f for f in directory.rglob('*') if f.is_file()]
        return {
            "total": len(files),
            "extensions": list(set(f.suffix.lower() for f in files))
        }
    
    return {
        "raw_data": {"path": str(RAW_DATA_DIR), **_count(RAW_DATA_DIR)},
        "prepared_data": {"path": str(PREPARED_DATA_DIR), **_count(PREPARED_DATA_DIR)}
    }


# 🔹 Запуск через uvicorn (для локального теста)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)