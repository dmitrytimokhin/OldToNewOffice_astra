"""
Конвертер документов: DOC/XLS → DOCX/XLSX
Python 3.11+ | Все конвертации через LibreOffice (надёжно и без зависимостей xlrd)
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class DocumentConverter:

    """
    Конвертер документов через LibreOffice
    """

    SUPPORTED_EXTENSIONS = {
        '.doc': ('doc', 'docx'),
        '.docx': ('docx', 'docx'),
        '.xls': ('xls', 'xlsx'),
        '.xlsx': ('xlsx', 'xlsx')
    }

    def __init__(
        self,
        raw_dir: str,
        prepared_dir: str,
        libreoffice_path: str = "/usr/bin/libreoffice"
    ):
        
        """
        Инициализация конвертера.

        Args:
            raw_dir: Путь к папке с исходными файлами
            prepared_dir: Путь к папке для обработанных файлов
            libreoffice_path: Путь к исполняемому файлу LibreOffice
        """

        # Упрощение путей и переменных окружения
        self.raw_dir = Path(os.getenv("RAW_DATA_DIR", raw_dir)).resolve()
        self.prepared_dir = Path(os.getenv("PREPARED_DATA_DIR", prepared_dir)).resolve()
        self.libreoffice_path = os.getenv("LIBREOFFICE_PATH", libreoffice_path)

        # Валидация LibreOffice
        if not Path(self.libreoffice_path).exists():
            raise RuntimeError(f"LibreOffice не найден: {self.libreoffice_path}")

        # Валидация исходной папки
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Исходная папка не существует: {self.raw_dir}")

        # Создаём целевую папку
        self.prepared_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Исходная папка: {self.raw_dir}")
        logger.info(f"Целевая папка: {self.prepared_dir}")
        logger.info(f"LibreOffice: {self.libreoffice_path}")
        logger.info(f"HOME: {os.getenv('HOME', 'не установлена')}")


    def convert_with_libreoffice(
            self, 
            src: Path, 
            dst_dir: Path, 
            target_ext: str
            ) -> Path | None:
        
        """
        Универсальная конвертация через LibreOffice БЕЗ указания фильтра.
        Возвращает путь к сконвертированному файлу или None при ошибке.

        Args:
            src: Путь к исходному файлу
            dst_dir: Папка для сохранения результата
            target_ext: Целевое расширение ('docx' или 'xlsx')

        Returns:
            Путь к сконвертированному файлу или None
        """

        # Очищаем расширение от точки и приводим к нижнему регистру
        target_ext = target_ext.lower().lstrip('.')

        try:
            env = os.environ.copy()
            env["HOME"] = "/tmp"  # Критически важно для пользователя nobody!

            # LibreOffice автоматически выберет правильный фильтр по расширению
            result = subprocess.run(
                [
                    self.libreoffice_path,
                    "--headless",
                    "--invisible",
                    "--convert-to", target_ext,  # ← Без двоеточия и фильтра!
                    "--outdir", str(dst_dir),
                    str(src)
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env=env
            )

            # LibreOffice сохраняет файл с именем исходника, но с НОВЫМ расширением
            # Проверяем все варианты регистра расширения (.docx, .DOCX, .Docx)
            candidates = [
                dst_dir / f"{src.stem}.{ext}"
                for ext in (target_ext.lower(), target_ext.upper(), target_ext.capitalize())
            ]
            converted = next((c for c in candidates if c.exists()), None)

            if converted:
                logger.debug(f"Найден сконвертированный файл: {converted.name}")
                return converted

            # Отладка: выводим реальные файлы в папке вывода
            actual_files = [f.name for f in dst_dir.iterdir() if f.is_file()]
            logger.debug(f"Файлы в папке вывода ({dst_dir}): {actual_files}")
            
            stderr_preview = result.stderr[:500].replace('\n', ' ').strip()
            logger.error(
                f"Не найден сконвертированный файл для {src.name}. "
                f"Код возврата: {result.returncode}. stderr: {stderr_preview}"
            )
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"Таймаут конвертации {src.name} (>120 сек)")
            return None
        except Exception as e:
            logger.error(f"Ошибка конвертации {src.name}: {type(e).__name__}: {str(e)[:150]}")
            return None

    def process_file(
            self, 
            src: Path, 
            dst: Path
            ) -> Tuple[bool, str]:
        
        """
        Обработка одного файла: копирование или конвертация.

        Args:
            src: Путь к исходному файлу
            dst: Путь к целевому файлу

        Returns:
            Кортеж (успех, статус_операции)
        """

        ext = src.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.warning(f"Пропущен неподдерживаемый формат: {src.name}")
            return False, "unsupported"

        src_type, dst_ext = self.SUPPORTED_EXTENSIONS[ext]
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Уже новый формат — копируем
        if src_type == dst_ext:
            shutil.copy2(src, dst)
            # src.unlink(missing_ok=True)
            logger.debug(f"Скопирован: {src.name} → {dst.name}")
            return True, "copied"

        # Конвертация старых форматов через LibreOffice
        if src_type in ('doc', 'xls'):
            converted_path = self.convert_with_libreoffice(src, dst.parent, dst_ext)
            if converted_path:
                # Если LibreOffice сохранил файл с другим именем (регистр расширения), переименовываем
                if converted_path != dst:
                    dst.unlink(missing_ok=True)
                    try:
                        converted_path.rename(dst)
                        logger.debug(f"Переименован: {converted_path.name} → {dst.name}")
                    except Exception as e:
                        logger.warning(f"Не удалось переименовать {converted_path.name} → {dst.name}: {e}")
                        # Но файл всё равно существует, считаем успехом
                # Удаляем исходный файл ТОЛЬКО после успешной конвертации и переименования
                # src.unlink(missing_ok=True)
                return True, f"converted_{src_type}"
            return False, f"failed_{src_type}"

        return False, "unknown"

    def process(self) -> Dict[str, int]:
        """Основной метод обработки всех файлов."""
        logger.info(f"\nПоиск файлов в: {self.raw_dir}")
        files = [
            f for f in self.raw_dir.rglob('*')
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

        # Проверка на пустую папку
        skip_empty = os.getenv("SKIP_EMPTY", "false").lower() == "true"
        if not files:
            msg = "Не найдено файлов для обработки (.doc, .docx, .xls, .xlsx)"
            if skip_empty:
                logger.warning(f"{msg} — пропускаем (SKIP_EMPTY=true)")
                return {"total": 0, "copied": 0, "converted_doc": 0, "converted_xls": 0, "failed": 0}
            else:
                logger.error(f"{msg} — остановка (установите SKIP_EMPTY=true для пропуска)")
                raise RuntimeError("Нет файлов для обработки")

        logger.info(f"Найдено файлов: {len(files)}\n")

        stats = {
            "total": len(files),
            "copied": 0,
            "converted_doc": 0,
            "converted_xls": 0,
            "failed": 0,
            "failed_files": []
        }

        for i, src in enumerate(sorted(files), 1):
            rel_path = src.relative_to(self.raw_dir)
            dst = self.prepared_dir / rel_path.with_suffix(f".{self.SUPPORTED_EXTENSIONS[src.suffix.lower()][1]}")
            logger.info(f"[{i}/{len(files)}] {rel_path} → {dst.relative_to(self.prepared_dir)}")
            
            success, status = self.process_file(src, dst)

            if status == "copied":
                stats["copied"] += 1
            elif status == "converted_doc":
                stats["converted_doc"] += 1
            elif status == "converted_xls":
                stats["converted_xls"] += 1
            elif status.startswith("failed"):
                stats["failed"] += 1
                stats["failed_files"].append(str(rel_path))

            status_emoji = "✓" if success else "✗"
            logger.info(f"{status_emoji} {status}")

        # Итоги
        logger.info("\n" + "="*70)
        logger.info("ИТОГОВАЯ СТАТИСТИКА")
        logger.info("="*70)
        logger.info(f"Всего файлов:          {stats['total']}")
        logger.info(f"Скопировано (новые):   {stats['copied']}")
        logger.info(f"Конвертировано DOC→DOCX: {stats['converted_doc']}")
        logger.info(f"Конвертировано XLS→XLSX: {stats['converted_xls']}")
        logger.info(f"Ошибок:                {stats['failed']}")
        logger.info("="*70)

        if stats["failed_files"]:
            logger.warning("\nФайлы с ошибками:")
            for f in stats["failed_files"][:10]:
                logger.warning(f" - {f}")
            if len(stats["failed_files"]) > 10:
                logger.warning(f"   ... и ещё {len(stats['failed_files']) - 10} файлов")

        if stats["failed"] == 0:
            logger.info("\nВсе файлы успешно обработаны!")
        else:
            logger.warning(f"\nЗавершено с ошибками: {stats['failed']} из {stats['total']} файлов")

        return stats


def main():
    """Точка входа."""
    raw_dir = os.getenv("RAW_DATA_DIR", "/app/raw_data")
    prepared_dir = os.getenv("PREPARED_DATA_DIR", "/app/prepared_data")
    libreoffice_path = os.getenv("LIBREOFFICE_PATH", "/usr/bin/libreoffice")

    try:
        converter = DocumentConverter(raw_dir, prepared_dir, libreoffice_path)
        stats = converter.process()
        sys.exit(0 if stats["failed"] == 0 else 1)
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        sys.exit(2)


if __name__ == "__main__":
    # Проверяем версию Python
    if sys.version_info < (3, 11):
        logger.error(f"Требуется Python 3.11+, обнаружена версия {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(3)
    main()
