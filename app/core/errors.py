"""Pantallas de error para el navegador y JSON para las llamadas fetch.

Las páginas no consultan la base de datos (no buscan al usuario), así que se
muestran aunque la BD esté caída. Las peticiones que no aceptan HTML (fetch,
imágenes, monitores) siguen recibiendo {"detail": ...} como antes.
"""

import logging
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import SECURITY_HEADERS
from app.core.templating import templates

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pantalla:
    titulo: str
    mensaje: str
    icono: str  # clase de Bootstrap Icons
    reintentar: bool = False  # ofrecer "Reintentar" (errores pasajeros)
    referencia: bool = False  # mostrar código para soporte (errores del servidor)


PANTALLAS: dict[int, Pantalla] = {
    400: Pantalla(
        "Solicitud no válida",
        "No pudimos procesar lo que enviaste. Revisa los datos e inténtalo de nuevo.",
        "bi-exclamation-circle",
    ),
    403: Pantalla(
        "No tienes permiso",
        "Tu usuario no tiene acceso a esta sección. Si crees que es un error, "
        "pide a un administrador que revise tu rol.",
        "bi-shield-lock",
    ),
    404: Pantalla(
        "Página no encontrada",
        "La página o el certificado que buscas no existe o ya no está disponible. "
        "Revisa el enlace o vuelve al inicio.",
        "bi-search",
    ),
    405: Pantalla(
        "Acción no permitida",
        "Esta dirección no admite la acción que intentaste. Vuelve a la página "
        "anterior y usa los botones de la aplicación.",
        "bi-slash-circle",
    ),
    413: Pantalla(
        "Archivo demasiado grande",
        "El archivo supera el tamaño permitido. Prueba con un archivo más liviano.",
        "bi-file-earmark-x",
    ),
    422: Pantalla(
        "Faltan datos o no son válidos",
        "Algunos campos del formulario están vacíos o tienen un formato incorrecto. "
        "Vuelve atrás, revísalos y envía de nuevo.",
        "bi-ui-checks",
    ),
    429: Pantalla(
        "Demasiados intentos",
        "Hiciste muchas solicitudes en poco tiempo. Espera un minuto y vuelve a intentarlo.",
        "bi-hourglass-split",
        reintentar=True,
    ),
    500: Pantalla(
        "Algo salió mal",
        "Ocurrió un error inesperado de nuestro lado. Ya quedó registrado. "
        "Inténtalo de nuevo en unos segundos.",
        "bi-bug",
        reintentar=True,
        referencia=True,
    ),
    503: Pantalla(
        "Servicio no disponible por un momento",
        "No pudimos conectar con la base de datos. Suele resolverse solo en unos "
        "segundos; vuelve a intentarlo.",
        "bi-cloud-slash",
        reintentar=True,
        referencia=True,
    ),
}

# Mensajes internos que no aportan nada al usuario: se usa el texto de la pantalla.
_DETALLES_GENERICOS = {"Not Found", "Method Not Allowed", "No autorizado", "Forbidden"}

CSRF_INVALIDO = "CSRF token inválido"
_PANTALLA_CSRF = Pantalla(
    "La página caducó",
    "Por seguridad, el formulario dejó de ser válido (por ejemplo, porque cerraste "
    "sesión en otra pestaña). Recarga la página e inténtalo de nuevo.",
    "bi-clock-history",
)


def _quiere_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def _pantalla(codigo: int) -> Pantalla:
    if codigo in PANTALLAS:
        return PANTALLAS[codigo]
    return PANTALLAS[500] if codigo >= 500 else PANTALLAS[400]


def respuesta_error(
    request: Request,
    codigo: int,
    detalle: str | None = None,
    referencia: str | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """Pantalla HTML si la pide un navegador; si no, JSON como antes."""
    if not _quiere_html(request):
        cuerpo: dict = {"detail": detalle or _pantalla(codigo).titulo}
        if referencia:
            cuerpo["reference"] = referencia
        return JSONResponse(cuerpo, status_code=codigo, headers=headers)

    pantalla = _PANTALLA_CSRF if detalle == CSRF_INVALIDO else _pantalla(codigo)
    if detalle in _DETALLES_GENERICOS or detalle == CSRF_INVALIDO:
        detalle = None
    respuesta = templates.TemplateResponse(
        request,
        "errors/error.html",
        {
            "codigo": codigo,
            "pantalla": pantalla,
            "detalle": detalle,
            "referencia": referencia,
            # Reintentar solo repite la petición si era una navegación GET.
            "reintentar_url": str(request.url) if request.method == "GET" else None,
        },
        status_code=codigo,
        headers=headers,
    )
    # Los 500 salen por fuera del middleware de seguridad: se ponen aquí también.
    respuesta.headers.update(SECURITY_HEADERS)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def _nueva_referencia() -> str:
    return uuid.uuid4().hex[:8].upper()


async def _http_exception(request: Request, exc: StarletteHTTPException) -> Response:
    # Las redirecciones (p. ej. al login) viajan como HTTPException 3xx: se respetan.
    if exc.status_code < 400:
        return Response(status_code=exc.status_code, headers=exc.headers)
    detalle = exc.detail if isinstance(exc.detail, str) else None
    return respuesta_error(request, exc.status_code, detalle, headers=exc.headers)


async def _validacion(request: Request, exc: RequestValidationError) -> Response:
    if not _quiere_html(request):
        return JSONResponse({"detail": exc.errors()}, status_code=422)
    return respuesta_error(request, 422)


async def _limite(request: Request, exc: RateLimitExceeded) -> Response:
    return respuesta_error(request, 429, headers={"Retry-After": "60"})


async def _bd_no_disponible(request: Request, exc: Exception) -> Response:
    ref = _nueva_referencia()
    logger.exception("Error %s: base de datos no disponible en %s", ref, request.url.path)
    return respuesta_error(request, 503, referencia=ref, headers={"Retry-After": "5"})


async def _inesperado(request: Request, exc: Exception) -> Response:
    ref = _nueva_referencia()
    logger.exception("Error %s: excepción no controlada en %s", ref, request.url.path)
    return respuesta_error(request, 500, referencia=ref)


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(RateLimitExceeded, _limite)
    # Solo errores de conexión son 503; el resto de errores de BD (p. ej. una
    # violación de unicidad) son fallos de la app y van al 500.
    for exc in ERRORES_DE_CONEXION:
        app.add_exception_handler(exc, _bd_no_disponible)
    app.add_exception_handler(Exception, _inesperado)


ERRORES_DE_CONEXION = (OperationalError, InterfaceError, PoolTimeoutError, ConnectionError, TimeoutError)
