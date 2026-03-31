# ============================================================================
# FastAPI сервис конвертации документов DOC/XLS → DOCX/XLSX
# Python 3.11 + LibreOffice + default-jdk-headless (работает с Java 17/21)
# ============================================================================
FROM python:3.11-slim

# ── Переменные окружения ───────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    RAW_DATA_DIR=/app/raw_data \
    PREPARED_DATA_DIR=/app/prepared_data \
    LIBREOFFICE_PATH=/usr/bin/soffice \
    API_PORT=8000 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Установка системных зависимостей ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    default-jdk-headless \
    libx11-6 libxext6 libxrender1 libxt6 libgl1 libsm6 libice6 \
    libxinerama1 libfontconfig1 libdbus-1-3 \
    fonts-dejavu-core fonts-liberation fonts-freefont-ttf \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Проверка установки (не прервёт сборку при ошибке)
RUN /usr/bin/soffice --version || true
RUN java -version || true

# ── Настройка Python-окружения ─────────────────────────────────────────────
WORKDIR /app

COPY app/requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

COPY app/converter.py .
COPY app/main.py .

# ── Подготовка директорий и прав ───────────────────────────────────────────
RUN mkdir -p ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /tmp && \
    chown -R nobody:nogroup ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /tmp /app && \
    chmod -R 755 ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /tmp /app

# ── Запуск ─────────────────────────────────────────────────────────────────
EXPOSE ${API_PORT}
USER nobody

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${API_PORT}/health || exit 1

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD []