"""Punto de entrada para Vercel (función Python serverless).

Vercel ejecuta este archivo como una función y le entrega todas las rutas
(ver vercel.json). Solo reexporta la app de FastAPI; el código vive en app/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
