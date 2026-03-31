# ============================================================================
# FastAPI сервис конвертации документов DOC/XLS → DOCX/XLSX
# Astra Linux 1.8 (Орёл, Debian 11) + Python 3.11 + LibreOffice + JDK 17
# ============================================================================
FROM registry.astralinux.ru/astra/ubi18-python311:latest

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
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_RUNTIME_DIR=/tmp/runtime-nobody

# ── Установка системных зависимостей ───────────────────────────────────────
# default-jdk-headless на Astra Linux 1.8 устанавливает JDK 17
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    default-jdk-headless \
    xvfb \
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
RUN pip install --break-system-packages -U pip && pip install --break-system-packages -r requirements.txt

COPY app/converter.py .
COPY app/main.py .

# ── Подготовка директорий и прав ───────────────────────────────────────────
# nobody:nogroup — стандартный непривилегированный пользователь в Debian/Astra
RUN mkdir -p ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /tmp/runtime-nobody /tmp/lo-userprofile && \
    chown -R nobody:nogroup ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /tmp/runtime-nobody /tmp/lo-userprofile /app && \
    chmod -R 755 ${RAW_DATA_DIR} ${PREPARED_DATA_DIR} /app && \
    chmod 700 /tmp/runtime-nobody && \
    chmod 755 /tmp/lo-userprofile

# ── Запуск ─────────────────────────────────────────────────────────────────
EXPOSE ${API_PORT}
USER nobody

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${API_PORT}/health || exit 1

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD []
