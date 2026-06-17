#!/usr/bin/env python3
"""
Importa todos los registros de BASE CERTIFICADOS SOLICITADOS 2026.xls
a la base de datos de producción.

Uso:
    python3 scripts/seed_from_excel.py            # inserta
    python3 scripts/seed_from_excel.py --dry-run  # solo muestra lo que haría
"""

import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

# ── 0. Dependencias ────────────────────────────────────────────────────────
try:
    import xlrd
except ImportError:
    os.system("pip3 install xlrd --quiet")
    import xlrd

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    os.system("pip3 install psycopg2-binary --quiet")
    import psycopg2
    import psycopg2.extras

# ── 1. Cargar .env ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

def _load_env(path: Path) -> dict:
    env: dict = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env

env = _load_env(ROOT / ".env")

RAW_URL = (
    env.get("DATABASE_URL_DIRECT")
    or env.get("DATABASE_URL")
    or os.environ.get("DATABASE_URL_DIRECT")
    or os.environ.get("DATABASE_URL")
)
if not RAW_URL:
    sys.exit("ERROR: DATABASE_URL_DIRECT no encontrado en .env")

# Adaptar URL para psycopg2 (quitar +asyncpg si existe)
CONN_STR = re.sub(r"postgresql\+\w+://", "postgresql://", RAW_URL)

DRY_RUN = "--dry-run" in sys.argv

# ── 2. Constantes de mapeo ─────────────────────────────────────────────────
EXCEL_PATH = ROOT / "Docs" / "BASE CERTIFICADOS SOLICITADOS 2026.xls"

MESES_NUM = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

EMPRESA_MAP = {"PYF": "PARQUES Y FUNERARIAS"}


# ── 3. Utilidades ──────────────────────────────────────────────────────────
def clean(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    # Quitar .0 de números float
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s or None


def clean_doc(val):
    s = clean(val)
    if not s:
        return None
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def parse_date(val, datemode):
    if not val:
        return None
    if isinstance(val, float):
        try:
            return xlrd.xldate_as_datetime(val, datemode).date()
        except Exception:
            return None
    if isinstance(val, str):
        val = val.strip()
        # "viernes, 26 de diciembre de 2025"
        m = re.match(
            r"(?:\w+,\s*)?(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
            val,
            re.IGNORECASE,
        )
        if m:
            day, month_name, year = m.groups()
            month = MESES_ES.get(month_name.lower())
            if month:
                try:
                    return date(int(year), month, int(day))
                except ValueError:
                    pass
        # YYYY-MM-DD
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def map_status(val):
    if val and "ENVIADO" in val.upper():
        return "APPROVED"
    return "PENDING"


def match_asesor(funcionaria, users):
    """
    Intenta emparejar el nombre FUNCIONARIA con un usuario existente.
    Retorna el UUID del admin como fallback.
    """
    admin_id = next((uid for uid, name, role in users if role == "admin"), None)
    fallback = admin_id or users[0][0]

    if not funcionaria:
        return fallback

    fn = funcionaria.upper()
    # Ignorar entradas tipo PQRS o DP
    if re.match(r"^(PQRS|DP\s)", fn):
        return fallback

    best = None
    for uid, name, role in users:
        parts = name.upper().split()
        if any(p in fn for p in parts if len(p) > 3):
            best = uid
            break
    return best or fallback


# ── 4. Leer Excel ──────────────────────────────────────────────────────────
print(f"Leyendo {EXCEL_PATH.name} …")
wb = xlrd.open_workbook(str(EXCEL_PATH))
sh = wb.sheet_by_name("BASE")
headers = [sh.cell_value(0, c) for c in range(sh.ncols)]
h = {v.strip(): i for i, v in enumerate(headers)}


# ── 5. Conectar a BD ───────────────────────────────────────────────────────
print("Conectando a la base de datos …")
psycopg2.extras.register_uuid()
conn = psycopg2.connect(CONN_STR, sslmode="require")
conn.autocommit = True   # cada INSERT es su propia transacción
cur = conn.cursor()

# Obtener usuarios existentes
cur.execute("SELECT id, full_name, role FROM users WHERE is_active = TRUE")
users = [(row[0], row[1], row[2]) for row in cur.fetchall()]
if not users:
    sys.exit("ERROR: No hay usuarios en la BD. Crea el admin primero.")

print(f"Usuarios encontrados ({len(users)}):")
for uid, name, role in users:
    print(f"  {role:8} | {name}")

# Contar registros existentes
cur.execute("SELECT COUNT(*) FROM certificate_requests")
existing = cur.fetchone()[0]
print(f"\nRegistros actuales en BD: {existing}")

# ── 6. Procesar filas ──────────────────────────────────────────────────────
now = datetime.now(timezone.utc)
inserted = 0
skipped = 0
errors = []

INSERT_SQL = """
INSERT INTO certificate_requests (
    id, created_at, updated_at,
    status, asesor_id, submitted_at, reviewed_at,
    cliente_nombre_completo, cliente_tipo_documento, cliente_numero_documento,
    cliente_telefono, cliente_email, cliente_parentesco,
    fallecido_nombre_completo, fallecido_tipo_documento, fallecido_numero_documento,
    fallecido_fecha_fallecimiento,
    empresa, tipo_certificado, numero_aviso, fecha_afiliacion,
    numero_recibo_caja, numero_contrato, observaciones
) VALUES (
    %(id)s, %(created_at)s, %(updated_at)s,
    %(status)s, %(asesor_id)s, %(submitted_at)s, %(reviewed_at)s,
    %(cliente_nombre_completo)s, %(cliente_tipo_documento)s, %(cliente_numero_documento)s,
    %(cliente_telefono)s, %(cliente_email)s, %(cliente_parentesco)s,
    %(fallecido_nombre_completo)s, %(fallecido_tipo_documento)s, %(fallecido_numero_documento)s,
    %(fallecido_fecha_fallecimiento)s,
    %(empresa)s, %(tipo_certificado)s, %(numero_aviso)s, %(fecha_afiliacion)s,
    %(numero_recibo_caja)s, %(numero_contrato)s, %(observaciones)s
)
"""

print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Procesando {sh.nrows - 1} filas …\n")

for r in range(1, sh.nrows):
    def col(name):
        return sh.cell_value(r, h[name]) if name in h else None

    fallecido_nombre = clean(col("NOMBRE FALLECIDO"))
    if not fallecido_nombre:
        skipped += 1
        continue

    # Fecha de creación de la solicitud (MES + DIA del Excel, año 2026)
    mes_str = clean(col("MES")) or "ENERO"
    dia_val  = col("DIA")
    mes_num  = MESES_NUM.get(mes_str.upper(), 1)
    try:
        dia_num = int(float(dia_val)) if dia_val else 1
        if dia_num < 1 or dia_num > 31:
            dia_num = 1
    except (TypeError, ValueError):
        dia_num = 1
    try:
        req_date = date(2026, mes_num, dia_num)
    except ValueError:
        req_date = date(2026, mes_num, 1)
    created_at = datetime(req_date.year, req_date.month, req_date.day,
                          8, 0, 0, tzinfo=timezone.utc)

    # Empresa
    empresa_raw = clean(col("EMPRESA"))
    empresa = EMPRESA_MAP.get(empresa_raw, empresa_raw) if empresa_raw else None

    # Estado y fechas de flujo
    estado_raw = clean(col("ESTADO"))
    status = map_status(estado_raw)
    submitted_at = created_at          # todas ya fueron enviadas
    reviewed_at  = created_at if status == "approved" else None

    # Asesor
    funcionaria = clean(col("FUNCIONARIA"))
    asesor_id = match_asesor(funcionaria, users)

    # Número aviso (NA → null)
    aviso_raw = clean(col("NUMERO AVISO"))
    numero_aviso = None if aviso_raw and aviso_raw.upper() == "NA" else aviso_raw

    # Observaciones: combinar campo original + FUNCIONARIA si procede
    obs_parts = []
    obs_raw = clean(col("OBSERVACIONES"))
    if obs_raw:
        obs_parts.append(obs_raw)
    if funcionaria and not re.match(r"^(PQRS|DP\s)", funcionaria.upper()):
        obs_parts.append(f"Funcionaria: {funcionaria}")
    observaciones = " | ".join(obs_parts) or None

    record = {
        "id":                          uuid.uuid4(),
        "created_at":                  created_at,
        "updated_at":                  created_at,
        "status":                      status,
        "asesor_id":                   asesor_id,
        "submitted_at":                submitted_at,
        "reviewed_at":                 reviewed_at,
        "cliente_nombre_completo":     clean(col("SOLICITANTE")) or "N/D",
        "cliente_tipo_documento":      "CC",
        "cliente_numero_documento":    clean_doc(col("CEDULA")) or "0",
        "cliente_telefono":            "N/D",
        "cliente_email":               clean(col("EMAIL")) or "sin-correo@recordar.com",
        "cliente_parentesco":          "N/D",
        "fallecido_nombre_completo":   fallecido_nombre,
        "fallecido_tipo_documento":    "CC",
        "fallecido_numero_documento":  clean_doc(col("CEDULA FALL")) or "0",
        "fallecido_fecha_fallecimiento": parse_date(col("FECHA DEL SERVICIO"), wb.datemode),
        "empresa":                     empresa,
        "tipo_certificado":            clean(col("DOCUMENTO SOLICITADO")),
        "numero_aviso":                numero_aviso,
        "fecha_afiliacion":            parse_date(col("FECHA DE AFILIACION"), wb.datemode),
        "numero_recibo_caja":          clean_doc(col("No. RECIBO DE CAJA")),
        "numero_contrato":             (clean(col("CONTRATO")) or "")[:100] or None,
        "observaciones":               observaciones,
    }

    # Fecha de fallecimiento es requerida; si falta, usar fecha de la solicitud
    if record["fallecido_fecha_fallecimiento"] is None:
        record["fallecido_fecha_fallecimiento"] = req_date

    if DRY_RUN:
        if inserted < 3:
            print(f"  [{r}] {record['fallecido_nombre_completo']} | "
                  f"{record['tipo_certificado']} | {record['status']} | "
                  f"{record['fallecido_fecha_fallecimiento']}")
        inserted += 1
        continue

    try:
        cur.execute(INSERT_SQL, record)
        inserted += 1
    except Exception as exc:
        errors.append(f"Fila {r}: {exc}")

# ── 7. Commit ──────────────────────────────────────────────────────────────
if not DRY_RUN and inserted > 0:
    print(f"✓ {inserted} registros insertados.")
elif DRY_RUN:
    print(f"\n[DRY RUN] Se insertarían {inserted} registros.")

if skipped:
    print(f"  {skipped} filas vacías ignoradas.")
if errors:
    print(f"\nErrores ({len(errors)}):")
    for e in errors[:10]:
        print(f"  {e}")

cur.close()
conn.close()
