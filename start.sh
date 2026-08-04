#!/bin/sh
set -e
alembic upgrade head
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 60 \
  --keep-alive 5
