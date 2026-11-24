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
| `DATABASE_URL_DIRECT` | URL directa de Neon (psycopg2, solo Alembic). Opcional: si falta se usa `DATABASE_URL` |
| `SESSION_SECRET` | Secreto aleatorio para tokens de sesión (mín. 32 chars) |
| `GMAIL_SENDER`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` | Envío de correos por la API de Gmail |
| `ADMIN_EMAIL` | Email del admin inicial (solo para seed_admin.py) |
| `ADMIN_PASSWORD` | Contraseña del admin inicial |
| `ADMIN_FULL_NAME` | Nombre completo del admin inicial |
| `ENV` | `production` en Render, `development` en local. En Vercel es `production` por defecto |

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Los tests no necesitan base de datos ni `.env`: `tests/conftest.py` fija variables falsas.

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

## Despliegue en Vercel

La app corre como una función Python serverless: `api/index.py` reexporta la app de
FastAPI y `vercel.json` envía todas las rutas a esa función (región `pdx1`, hasta 60 s
por petición para que alcance a generar el PDF y enviar el correo al aprobar).

1. En Vercel, **Add New → Project** e importar el repositorio. Si el repo tiene más
   carpetas, poner `Certificados` como *Root Directory*. *Framework Preset*: **Other**.
2. En **Settings → Environment Variables** definir:
   - `DATABASE_URL` — usar la URL del **pooler** de la base (en Supabase, el puerto
     `6543`), con el driver `postgresql+asyncpg://` y `?ssl=require`. En Vercel cada
     petición abre su propia conexión, así que la URL directa agotaría las conexiones.
   - `SESSION_SECRET`
   - `GMAIL_SENDER`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
   - `FIRMA_NOMBRE`, `FIRMA_CARGO` (opcionales)
   - `ENV` no hace falta: en Vercel vale `production` por defecto (cookies `secure`).
3. **Migraciones:** Vercel no ejecuta `alembic`. Antes de desplegar una versión con
   migraciones nuevas, correrlas una vez desde un equipo local contra la base de producción:
   ```bash
   DATABASE_URL_DIRECT="postgresql+psycopg2://...?sslmode=require" alembic upgrade head
   ```
4. Primer administrador: `python scripts/seed_admin.py` desde local, apuntando a la misma base.
5. Health check: `GET /healthz` (sin BD) y `GET /keepalive` (hace `SELECT 1`).

`.vercelignore` evita que un despliegue con la CLI (`vercel`) suba `.env` o `.venv`.

> **Límite de intentos de login:** el contador de `slowapi` vive en memoria, y en Vercel
> cada instancia lleva el suyo, así que el límite de 10/minuto es aproximado. El bloqueo
> de cuenta tras 5 intentos fallidos sí se guarda en la base y funciona igual.
