"""
Limpieza completa de datos transaccionales de lotes en webapp_pd.db.
Preserva maestros: contratistas, reglas, usuarios, ordenativos Oracle.
"""
import sqlite3
from pathlib import Path

DB = Path("data/db/webapp_pd.db")
assert DB.exists(), f"DB no encontrada: {DB.resolve()}"

c = sqlite3.connect(DB)
c.execute("PRAGMA foreign_keys = ON")

print("=== Antes de la limpieza ===")
for t in ("lotes_archivos", "partes_diarios_raw", "partes_diarios_procesados",
          "parte_imagenes", "auditoria_cambios"):
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n}")

print()
print("=== Limpiando (orden: dependientes -> padres) ===")
for t in ("auditoria_cambios", "parte_imagenes", "partes_diarios_procesados",
          "partes_diarios_raw", "lotes_archivos"):
    cur = c.execute(f"DELETE FROM {t}")
    print(f"  {t}: {cur.rowcount} filas eliminadas")

c.commit()

print()
print("=== Después de la limpieza ===")
for t in ("lotes_archivos", "partes_diarios_raw", "partes_diarios_procesados",
          "parte_imagenes", "auditoria_cambios"):
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n}")

print()
print("=== Maestros preservados ===")
for t in ("contratistas", "mapeo_codigos_contratista", "reglas_cod_epec",
          "usuarios_app", "ordenativos_oracle_local",
          "ordenativos_oracle_equipos", "ordenativos_oracle_fotos"):
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n}")

c.execute("VACUUM")
c.close()
print("\n[OK] Limpieza completada + VACUUM.")
