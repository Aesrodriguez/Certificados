import hashlib
import json as _json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["now"] = datetime.today

STATIC_DIR = TEMPLATES_DIR.parent / "static"


@lru_cache(maxsize=None)
def static_url(path: str) -> str:
    """URL de un archivo estático con huella de su contenido (?v=...).

    Los estáticos se cachean 24 h en el navegador; al cambiar el archivo cambia la
    huella y por tanto la URL, así el navegador baja la versión nueva tras cada
    despliegue. La caché del proceso se reinicia en cada despliegue.
    """
    archivo = STATIC_DIR / path
    try:
        huella = hashlib.sha256(archivo.read_bytes()).hexdigest()[:10]
    except OSError:
        return f"/static/{path}"
    return f"/static/{path}?v={huella}"


templates.env.globals["static"] = static_url


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
