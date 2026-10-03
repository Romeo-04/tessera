# The API only. The web app is static and deploys separately (web/vercel.json),
# so the judge-facing demo never depends on this container being awake.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# Committed, reviewed scope. The built corpus (data/spl, data/index,
# data/interactions.csv) is mounted or baked in at deploy time; without it
# the API serves /health and alerts and answers live routes with a demo
# fallback rather than failing to start.
COPY data/formulary.csv ./data/formulary.csv

ENV TESSERA_DATA_DIR=/app/data PORT=8000
EXPOSE 8000
CMD uvicorn tessera.api.app:create_app --factory --host 0.0.0.0 --port ${PORT} \
    --proxy-headers --forwarded-allow-ips="*"
