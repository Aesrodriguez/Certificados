import json as _json
from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["now"] = datetime.today


def _tojson_safe(obj: object) -> str:
    """JSON serializer que escapa < > & ' como secuencias \\uXXXX para que
    sea seguro incrustarlo dentro de <script> sin XSS, incluso con | safe."""
    s = _json.dumps(obj, ensure_ascii=False)
    s = s.replace("&", "\\u0026")
    s = s.replace("<", "\\u003c")
    s = s.replace(">", "\\u003e")
    s = s.replace("'", "\\u0027")
    return s


templates.env.filters["tojson"] = _tojson_safe
