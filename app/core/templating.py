import json as _json
from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["now"] = datetime.today
templates.env.filters["tojson"] = lambda obj: _json.dumps(obj, ensure_ascii=False)
