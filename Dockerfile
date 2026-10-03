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

# Spend telemetry lives in TESSERA_DATA_DIR. Mount it on a persistent volume
# and run ONE instance: the daily ceiling is read from this file, so an
# ephemeral disk resets it on every cold start and each extra instance gets
# its own budget.
VOLUME ["/app/data"]

# The per-caller limit keys on the client address. Trusting X-Forwarded-For
# from anyone ("*") lets a client rotate that header and drain the daily
# budget, so trust only the platform's proxy: set FORWARDED_ALLOW_IPS to its
# address or CIDR at deploy time. uvicorn reads it from the environment.
ENV TESSERA_DATA_DIR=/app/data PORT=8000 FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000
CMD uvicorn tessera.api.app:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers
