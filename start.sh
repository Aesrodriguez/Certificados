#!/bin/sh
set -e
alembic upgrade head
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 1 --bind 0.0.0.0:${PORT:-8000} --timeout 60
