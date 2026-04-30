"""
Seed de datos paramétricos para la webapp (SQLite).

Tablas afectadas:
  - contratistas   (id 1=CONECTAR, 2=COOPLYF  — hardcodeados en el frontend)
  - usuarios_app   (id 1=admin auditor         — hardcodeado como subido_por)

Idempotente: usa INSERT OR IGNORE via merge(), no falla si los datos ya existen.

Uso (desde python-version/):
    python scripts/seed_webapp_db.py
"""
import sys
from pathlib import Path

# Asegurar que python-version/ esté en el path para importar api.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.core.database import engine, SessionLocal, Base
import api.db.models.base_models   # noqa: F401 — registra tablas en metadata
import api.db.models.domain_models # noqa: F401 — registra tablas en metadata

# ── Datos a sembrar ───────────────────────────────────────────────────────────

CONTRATISTAS = [
    {"id": 1, "nombre": "CONECTAR", "activo": True},
    {"id": 2, "nombre": "COOPLYF",  "activo": True},
]

USUARIOS = [
    {
        "id":       1,
        "username": "admin",
        "email":    "admin@epec.com.ar",
        "rol":      "admin",
        "is_active": True,
    },
    {
        "id":       2,
        "username": "auditor1",
        "email":    "auditor1@epec.com.ar",
        "rol":      "auditor",
        "is_active": True,
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert(db, model, rows: list[dict], pk: str = "id") -> tuple[int, int]:
    """Inserta filas que no existen (idempotente por PK). Devuelve (insertadas, omitidas)."""
    inserted = omitted = 0
    for row in rows:
        existing = db.get(model, row[pk])
        if existing is None:
            db.add(model(**row))
            inserted += 1
        else:
            omitted += 1
    db.commit()
    return inserted, omitted

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    from api.db.models.base_models import Contratista, UsuarioApp

    # Crear tablas si no existen (equivalente a alembic upgrade cuando se parte de cero)
    Base.metadata.create_all(bind=engine)
    print("Tablas verificadas / creadas.")

    with SessionLocal() as db:
        ins, omit = _upsert(db, Contratista, CONTRATISTAS)
        print(f"contratistas  — insertadas: {ins}, ya existían: {omit}")

        ins, omit = _upsert(db, UsuarioApp, USUARIOS)
        print(f"usuarios_app  — insertadas: {ins}, ya existían: {omit}")

    print("\nSeed completado. La DB está lista para recibir lotes.")
    print(f"  DB: {ROOT / 'data' / 'db' / 'webapp_pd.db'}")


if __name__ == "__main__":
    main()
