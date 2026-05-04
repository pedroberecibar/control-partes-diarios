"""Limpieza completa de lotes, partes y uploads.

Borra (en orden FK-safe):
  auditoria_cambios → partes_diarios_procesados (+ parte_imagenes en CASCADE)
  → partes_diarios_raw → lotes_archivos
  → archivos físicos en data/uploads/

No toca usuarios_app ni contratistas.
"""
import sys
from pathlib import Path

# Asegurar que el módulo corre desde python-version/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.core.database import SessionLocal
from api.db.models.base_models import LoteArchivo
from api.db.models.domain_models import (
    AuditoriaCambio,
    ParteDiarioProcesado,
    ParteDiarioRaw,
)

UPLOADS_DIR = ROOT / "data" / "uploads"


def reset_lotes(dry_run: bool = False) -> None:
    with SessionLocal() as db:
        n_audit   = db.query(AuditoriaCambio).count()
        n_proc    = db.query(ParteDiarioProcesado).count()
        n_raw     = db.query(ParteDiarioRaw).count()
        n_lotes   = db.query(LoteArchivo).count()

        uploads = list(UPLOADS_DIR.glob("*")) if UPLOADS_DIR.exists() else []

        print(f"  auditoria_cambios:          {n_audit}")
        print(f"  partes_diarios_procesados:  {n_proc}  (+ imagenes en CASCADE)")
        print(f"  partes_diarios_raw:         {n_raw}")
        print(f"  lotes_archivos:             {n_lotes}")
        print(f"  archivos en uploads/:       {len(uploads)}")

        if dry_run:
            print("\n[DRY RUN] Nada fue borrado.")
            return

        db.query(AuditoriaCambio).delete(synchronize_session=False)
        db.query(ParteDiarioProcesado).delete(synchronize_session=False)
        db.query(ParteDiarioRaw).delete(synchronize_session=False)
        db.query(LoteArchivo).delete(synchronize_session=False)
        db.commit()
        print("  DB: registros eliminados.")

    for f in uploads:
        if f.is_file():
            f.unlink()
    print(f"  Uploads: {len(uploads)} archivo(s) eliminado(s).")
    print("\nSistema limpio. Podés subir un nuevo lote.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"\n{'[DRY RUN] ' if dry else ''}Registros a borrar:\n")
    reset_lotes(dry_run=dry)
