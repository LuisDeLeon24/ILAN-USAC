FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SENTINEL_ROOT=/src

WORKDIR /src
COPY api /src/api
COPY theme /src/theme
COPY scripts /src/scripts
COPY web /src/web
COPY worker /src/worker
COPY docs /src/docs

RUN pip install --no-cache-dir -e "/src/api[dev]" \
    && python /src/scripts/generate_theme.py --root /src \
    && python /src/scripts/check_theme.py --root /src \
    && sed -i 's/\r$//' /src/api/entrypoint.sh \
    && chmod +x /src/api/entrypoint.sh

WORKDIR /src/api
EXPOSE 8000
ENTRYPOINT ["/src/api/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
