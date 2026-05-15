import sqlite3
c = sqlite3.connect("data/db/webapp_pd.db")

print("=== Todos los lotes ===")
for r in c.execute("""
    SELECT id, nombre_archivo, estado, paso_actual, progreso_pct,
           substr(coalesce(detalle_error,''),1,400) AS err,
           fecha_subida
    FROM lotes_archivos ORDER BY id
"""):
    print(r)

print()
print("=== Total filas por lote_id en partes_diarios_procesados ===")
for r in c.execute("""
    SELECT lote_id, COUNT(*) FROM partes_diarios_procesados
    GROUP BY lote_id ORDER BY lote_id
"""):
    print(r)
