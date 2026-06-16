# Clara Certificados

Sistema web de gestión de certificados para servicios exequiales.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 async (asyncpg)
- **Base de datos:** Neon (PostgreSQL), migraciones con Alembic
- **Frontend:** Jinja2 + Bootstrap 5 (server-rendered, sin build step)
- **PDF:** ReportLab (generación en memoria, sin guardar en disco)
- **Email:** Resend SDK (PDF adjunto como base64)
- **Despliegue:** Render Web Service (plan Free)

## Roles

| Rol | Permisos |
|---|---|
| **Admin** | Gestión de usuarios, log de auditoría |
| **Asesor** | Crear/editar solicitudes de certificado, enviar a revisión |
| **Revisor** | Aprobar o rechazar solicitudes, descargar/reenviar PDF |

## Flujo de un certificado

```
DRAFT → PENDING → APPROVED  (se genera PDF y se envía por email)
               ↘ REJECTED   (exige comentario; vuelve a ser editable)
```

## Setup local

```bash
# 1. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Variables de entorno (copia y completa)
cp .env.example .env

# 4. Aplicar migraciones
alembic upgrade head

# 5. Crear usuario Admin inicial
python scripts/seed_admin.py

# 6. Levantar servidor de desarrollo
uvicorn app.main:app --reload
```

Abrir en: http://localhost:8000

## Variables de entorno requeridas

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL del pooler de Neon (asyncpg) |
| `DATABASE_URL_DIRECT` | URL directa de Neon (psycopg2, solo Alembic) |
| `SESSION_SECRET` | Secreto aleatorio para tokens de sesión (mín. 32 chars) |
| `RESEND_API_KEY` | API key de Resend |
| `EMAIL_FROM` | Dirección origen de emails (ej. `Clara <no-reply@tudominio.com>`) |
| `ADMIN_EMAIL` | Email del admin inicial (solo para seed_admin.py) |
| `ADMIN_PASSWORD` | Contraseña del admin inicial |
| `ADMIN_FULL_NAME` | Nombre completo del admin inicial |
| `ENV` | `production` en Render, `development` en local |

## Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## Seguridad

- Contraseñas hasheadas con **argon2** (recomendado por OWASP)
- Bloqueo de cuenta tras 5 intentos fallidos (15 min)
- Rate limiting en `/login`: 10 intentos/minuto por IP (`slowapi`)
- Sesiones server-side en PostgreSQL (revocables inmediatamente)
- Cookie de sesión: `httponly`, `secure`, `samesite=strict`
- CSRF: token HMAC por sesión en todos los formularios POST/PUT/DELETE
- Headers de seguridad: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- RBAC estricto: `require_role()` en cada ruta protegida
- Auditoría: cada acción sensible queda registrada con actor, IP y timestamp
- Sin SQL crudo: todo vía ORM SQLAlchemy
- Secretos exclusivamente por variables de entorno (`.env` en `.gitignore`)
- Dependencias auditadas con `pip-audit` (0 CVEs conocidos)

## Despliegue en Render

El archivo `render.yaml` define el Blueprint. Al conectar el repo en Render:

1. Render ejecuta `pip install -r requirements.txt && alembic upgrade head`
2. Inicia la app con `gunicorn app.main:app -k uvicorn.workers.UvicornWorker`
3. Configurar manualmente en el dashboard de Render:
   - `DATABASE_URL`, `DATABASE_URL_DIRECT`, `RESEND_API_KEY`, `EMAIL_FROM`
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_FULL_NAME`, `ENV=production`
4. En la **Render Shell**, ejecutar una vez: `python scripts/seed_admin.py`
5. Health check: `GET /healthz`

> **Plan Free de Render:** el servicio entra en modo sleep tras ~15 min de inactividad. El primer request tras el sleep tarda ~30-60 s (cold start). Comportamiento esperado y aceptado.
