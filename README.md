# OldToNewOffice — Document Converter API

REST API-сервис для автоматической конвертации документов старых форматов в современные:

- `.doc` → `.docx`
- `.xls` → `.xlsx`
- `.docx`, `.xlsx` — копируются без изменений

Конвертация выполняется через **LibreOffice** в headless-режиме. Сервис упакован в Docker и предназначен для запуска на сервере с **Astra Linux 1.8 (Орёл)**.

---

## Стек

| Компонент | Версия |
|---|---|
| Базовый образ | `registry.astralinux.ru/astra/ubi18-python311:latest` |
| Python | 3.11 |
| FastAPI | ≥ 0.104 |
| LibreOffice | из репозитория Astra Linux |
| JDK | 17 (default-jdk-headless) |

---

## Структура проекта

```
.
├── Dockerfile
└── app/
    ├── main.py           # FastAPI-приложение, endpoints
    ├── converter.py      # Логика конвертации через LibreOffice
    ├── requirements.txt  # Python-зависимости
    └── raw_data/         # Папка с исходными файлами (монтируется как volume)
```

---

## Сборка и запуск

### 1. Сборка образа

```bash
docker build -t oldtonew-converter .
```

### 2. Запуск контейнера

Минимальный запуск:

```bash
docker run -d \
  --name converter \
  -p 8000:8000 \
  -v /path/to/your/raw_data:/app/raw_data \
  -v /path/to/your/prepared_data:/app/prepared_data \
  oldtonew-converter
```

Замените `/path/to/your/raw_data` и `/path/to/your/prepared_data` на реальные пути на сервере.

### 3. Проверка работоспособности

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "libreoffice_available": true,
  "raw_dir_exists": true,
  "prepared_dir_exists": true
}
```

---

## API

### `POST /convert`

Запускает конвертацию всех файлов из `raw_data` в `prepared_data`.

```bash
curl -X POST http://localhost:8000/convert
```

Пример ответа:

```json
{
  "success": true,
  "message": "Конвертация завершена успешно",
  "stats": {
    "total": 4,
    "copied": 2,
    "converted_doc": 1,
    "converted_xls": 1,
    "failed": 0,
    "failed_files": []
  }
}
```

### `GET /files/{path}`

Список файлов в папке. `path` — `raw` или `prepared`.

```bash
curl http://localhost:8000/files/raw
curl http://localhost:8000/files/prepared?recursive=true
```

### `DELETE /delete/{path}/{file}`

Удаление файла из указанной папки.

```bash
curl -X DELETE http://localhost:8000/delete/raw/document.doc
```

### `GET /stats`

Краткая статистика по папкам.

```bash
curl http://localhost:8000/stats
```

### `GET /health`

Health check для мониторинга и оркестраторов (Kubernetes, Docker Swarm).

---

## Переменные окружения

Все переменные имеют значения по умолчанию и не обязательны к переопределению.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `RAW_DATA_DIR` | `/app/raw_data` | Папка с исходными файлами |
| `PREPARED_DATA_DIR` | `/app/prepared_data` | Папка для результатов |
| `LIBREOFFICE_PATH` | `/usr/bin/soffice` | Путь к исполняемому файлу LibreOffice |
| `API_PORT` | `8000` | Порт сервиса |
| `SKIP_EMPTY` | `false` | Не падать с ошибкой, если `raw_data` пуста |

Пример запуска с переопределением переменных:

```bash
docker run -d \
  --name converter \
  -p 8000:8000 \
  -e SKIP_EMPTY=true \
  -v /data/input:/app/raw_data \
  -v /data/output:/app/prepared_data \
  oldtonew-converter
```

---

## Поддерживаемые форматы

| Входной формат | Выходной формат | Операция |
|---|---|---|
| `.doc` | `.docx` | Конвертация через LibreOffice |
| `.xls` | `.xlsx` | Конвертация через LibreOffice |
| `.docx` | `.docx` | Копирование |
| `.xlsx` | `.xlsx` | Копирование |

Прочие форматы игнорируются.

---

## Остановка и удаление контейнера

```bash
docker stop converter
docker rm converter
```

Удаление образа:

```bash
docker rmi oldtonew-converter
```
