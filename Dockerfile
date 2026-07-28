FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY apps ./apps
COPY packages ./packages
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 mil && mkdir -p /app/data && chown -R mil:mil /app
USER mil
EXPOSE 8000
CMD ["python", "scripts/container_start.py"]
