# Handoff — Estado del bug Traza 14 / motor PD al cerrar sesión 2026-05-13

## Resumen de un vistazo

- ✅ **Bug raíz Traza 14 → id_estado=4 (Fuera de Alcance) RESUELTO** y confirmado vía logs `[DIAG]`.
- ✅ **DB transaccional vaciada** — partís de cero mañana, sin contaminación de lotes viejos.
- ⚠️ **Bug secundario detectado** (W-5 self-overlap) que rompe el *reproceso* de un lote ya importado. Con DB vacía no se manifiesta — pero conviene arreglarlo antes de volver a reprocesar nada.
- 🧹 Quedan tareas de limpieza menores: remover los `[DIAG]` temporales y los scripts auxiliares.

---

## 1. Lo que funcionó hoy (validado end-to-end)

### 1.1 Traza 14 cae a id_estado=4 (Fuera de Alcance)
Logs del segundo reproceso del lote 5 (ver `python-version/docs/resultado_powershell_bug.md` líneas 355-358):
```
[DIAG] TRAZAS_FUERA_ALCANCE runtime: ['No Corresponde TOR CE', 'Otro Origen', 'Código de Tarea No Mapeado']
[DIAG] Filas Traza14 en df: 524
[DIAG] Sample TRAZA_CALIDAD (Traza14): 'Código de Tarea No Mapeado'
[DIAG] Post-select Traza14 id_estado: {4: 524}
```
**Las 524 filas con Traza 14 mapearon a id_estado=4 correctamente**. El fix de `np.select` con `TRAZAS_FUERA_ALCANCE` en `src/etapa3_core.py::normalizar_a_fact_schema` funciona.

### 1.2 Fixes de infraestructura aplicados

| Archivo | Cambio | Por qué |
|---|---|---|
| `api/services/worker.py:17` | `import traceback` | Para usar `traceback.format_exc()` |
| `api/services/worker.py:229-244` | `pd.to_numeric(Suministro).round().astype("Int64")` + warning si hay decimales | Tolerar Suministros float con parte decimal accidental (el lote 5 tenía 1 caso) |
| `api/services/worker.py:134-148` | `print("[WORKER ERROR]...", flush=True)` + `detalle_error = traceback.format_exc()[:4000]` (antes `str(e)[:500]`) | Hacer visibles las excepciones del motor en la consola y persistir el traceback completo |
| `src/etapa3_core.py:846-862` | Los 3 logs `[DIAG]` ahora son `print(..., flush=True)` | Garantizar visibilidad incluso si la propagación de loggers entre threads falla |
| `python-version/run_api_dev.ps1` (nuevo) | `uvicorn ... --reload-dir api --reload-dir src` | Sin esto, cambios en `src/` no disparaban reload — fue la causa de "no veo los DIAG" durante horas |

### 1.3 Causa raíz original del "no veo logs y persiste id_estado=3"
**Había 3+ instancias de uvicorn corriendo simultáneamente** bindeadas al puerto 8000 (venv raíz `D:\...\venv\`, Python 3.14 system-wide, y `python-version\venv\`). Windows repartía requests al azar y la que típicamente respondía era la versión vieja del código (sin `TRAZAS_FUERA_ALCANCE`). Solucionado matando todos los `python.exe` con uvicorn en su línea de comando y arrancando una única instancia limpia. Ver `docs/resultado_powershell_bug.md` para la cronología completa.

---

## 2. Bug secundario detectado: W-5 self-overlap (NO resuelto)

En `api/services/worker.py:229-247`, el check W-5 detecta duplicados históricos por `ID_PARTE_HASH` contra `partes_diarios_procesados`:

```python
_hashes_lote = hashing.id_parte_hash(...)
_set_lote = set(_hashes_lote.dropna())
hashes_existentes = contar_hashes_existentes(db, _set_lote)
if _set_lote:
    overlap_pct = len(hashes_existentes) / len(_set_lote)
    if overlap_pct > src_config.OVERLAP_WARNING_THRESHOLD:
        log.warning("  OVERLAP_WARNING: %.0f%% ... Se procesará con Traza 18.", ...)
```

**Problema**: el lookup NO excluye el `lote_id` actual. Cuando se reprocesa un lote ya importado:
1. El motor consulta `partes_diarios_procesados` y encuentra que el 97% de los hashes ya existen.
2. Marca esos partes con Traza 18 ("Registro Ya Procesado en Lote Anterior") → id_estado=3 (Rechazado).
3. Recién DESPUÉS de que termina el motor, `ParteImportService._limpiar_lote_previo` borra las filas viejas del lote.
4. Resultado del segundo reproceso del lote 5: 145.702 filas en id_estado=3 (cuando antes del reproceso tenía ~60k).

**Evidencia** (`resultado_powershell_bug.md` líneas 331, 451-454):
```
WARNING api.services.worker: OVERLAP_WARNING: 97% de partes del lote ya existen (threshold=50%). Se procesará con Traza 18.
...
ID_ESTADO breakdown
  3                                      145,702
  1                                        3,151
  4                                          529
  2                                            4
```

**Fix sugerido** (no aplicado todavía — la DB ya está vacía y mañana podés validar Traza 14 sin tropezarte con este bug):
- En `worker.py:232`, antes de llamar `contar_hashes_existentes(db, _set_lote)`, eliminar primero las filas del `lote_id` actual (idem semántica que `_limpiar_lote_previo`) — o pasar `lote_id` al helper para que filtre `WHERE lote_id != :lote_id` en la query.
- Función helper a modificar: `api/services/parte_dedup_helpers.py::contar_hashes_existentes` (firma probable: agregar `lote_id_excluir: int | None = None`).
- Alternativa más simple: invertir el orden en `procesar_lote_en_background` — hacer `_limpiar_lote_previo` ANTES del motor. Riesgo: si el motor falla, perdés el lote viejo. Inferior a la opción anterior.

---

## 3. Otras observaciones del log que conviene mirar mañana

### 3.1 Regla "Otro Origen" muy agresiva
```
WARNING src.etapa3_core: Regla Otro Origen: 115586 parte(s) reclasificados (SEC_CODIGO_ORIGEN != PROTELEM).
```
115.586 de 149.386 partes (77%) del lote 5 fueron reclasificadas a "Otro Origen" porque el `SEC_CODIGO_ORIGEN` no era `PROTELEM`. Si el comportamiento esperado es que sólo se procese data PROTELEM, está bien — pero conviene confirmar con el archivo origen. Estaba en `src/etapa3_core.py` función `ensamblar_waterfall`.

### 3.2 Sample TRAZA_CALIDAD final del lote 5 (con W-5 contaminando todo)
```
  Registro Ya Procesado en Lote Anterior    145,423   ← W-5 self-overlap
  Corregido Medidor Vacio                     2,419
  Corregido Nro Medidor                         712
  Código de Tarea No Mapeado                    524   ← Traza 14 OK
  Informados con ORD-SUMI aprobado              276
  Corregido Sumi                                 20
  Otro Origen                                     5
  Corregido Sumi Nro EQP                          4
  Sin Orden Asociada                              3
```

### 3.3 USES coverage en aprobados
```
WARNING importar_lote 5 — 2505 partes APROBADOS sin VALOR_USES_ORIGEN (cod_epec sin regla definida): []
```
2.505 aprobados sin VALOR_USES_ORIGEN. La lista de códigos sin regla vino vacía (`[]`) — investigar si es realmente un bug o un edge case sin código declarado.

### 3.4 "Motor de sonidos"
Mencionaste que mañana querés probar "cómo funciona el motor de sonidos". No vi código relacionado en esta sesión — si está en otra rama o módulo distinto, contámelo cuando llegues y miramos.

---

## 4. Cómo retomar mañana (paso a paso)

### 4.1 Estado actual de la DB
- `lotes_archivos`: **0**
- `partes_diarios_raw`: **0**
- `partes_diarios_procesados`: **0**
- `parte_imagenes`: **0**
- `auditoria_cambios`: **0**
- Maestros intactos: contratistas (2), reglas_cod_epec (21), usuarios_app (2), ordenativos_oracle_* (74k + 250k + 285k).

### 4.2 Arrancar el backend (terminal #1)
```powershell
cd "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version"
.\venv\Scripts\activate
.\run_api_dev.ps1
```
El script ya tiene `--reload-dir api --reload-dir src` — no vuelvas a usar el comando viejo `uvicorn api.main:app --reload --port 8000` salvo que quieras revivir el bug de cambios no recargados en `src/`.

**Antes de arrancar verificá puerto 8000 libre**:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```
Debe devolver vacío. Si no, hay un uvicorn zombi de la sesión anterior — matalo con:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

### 4.3 Arrancar el frontend (terminal #2)
```powershell
cd "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\frontend-app"
npm run dev
```
Importante: NO uses `--mode mock`, queremos pegar contra el backend real.

### 4.4 Subir un lote nuevo
Desde la UI subí un Excel de CONECTAR o COOPLYF. Mirá la consola de uvicorn durante el procesamiento:
- Deberías ver los 3 `[DIAG] ...` con `Filas Traza14 en df: N` y `Post-select Traza14 id_estado: {4: N}`.
- Si aparece `[WORKER ERROR]`, el traceback completo va a la consola y a `lote.detalle_error` en la DB.

### 4.5 Validar Traza 14 en la UI
- En la pantalla DetalleLote, las filas con Traza "Código de Tarea No Mapeado" deben aparecer en la columna **Fuera de Alcance** (no Rechazado).
- Backend SQL para confirmar:
  ```sql
  SELECT id_traza, id_estado, COUNT(*) FROM partes_diarios_procesados
  WHERE id_traza=14 GROUP BY id_estado;
  ```
  Esperado: todas las filas con `id_estado=4`.

---

## 5. Tareas pendientes (post-validación)

### Cuando confirmes que Traza 14 funciona end-to-end:
1. **Remover los `[DIAG]` temporales** de `src/etapa3_core.py:846-862` (líneas marcadas `DIAGNÓSTICO TEMPORAL`).
2. **Decidir si revertir el `print(..., flush=True)` del WORKER ERROR** en `api/services/worker.py:138`. El `log.exception` original sigue presente, así que tenés cobertura doble. Mi recomendación: dejá el `print` — tener el traceback duplicado en stdout es barato y ya nos salvó una vez.

### Cuando quieras volver a reprocesar lotes (sin recrearlos):
3. **Arreglar W-5 self-overlap** (sección 2). Sin esto, cualquier reproceso de un lote ya importado romperá.

### Limpieza opcional:
4. Borrar scripts auxiliares de esta sesión si no los querés conservar:
   - `python-version/_diag_traza14.py` (consultas SQL ad-hoc)
   - `python-version/_limpiar_db_lotes.py` (script de wipe que usé hoy)
5. Borrar `python-version/docs/resultado_powershell_bug.md` (es el archivo donde fuimos pegando outputs de PowerShell — sólo útil para esta sesión).

---

## 6. Archivos modificados/creados en esta sesión

```
api/services/worker.py      — fixes B.2 (traceback) y cast Suministro
src/etapa3_core.py          — DIAG via print
run_api_dev.ps1             — script nuevo de arranque uvicorn
_diag_traza14.py            — script auxiliar (borrable)
_limpiar_db_lotes.py        — script auxiliar (borrable)
docs/resultado_powershell_bug.md — log de la sesión (borrable)
docs/handoff_traza14_2026-05-13.md — este archivo
```

Plan original en `C:\Users\pberecibar\.claude\plans\handoff-bug-traza-cryptic-sloth.md` (sigue siendo referencia válida — Fases A, B y D ejecutadas; Fase C parcial — sólo causa #1 confirmada, queda por validar resto con DB limpia).

— Fin del handoff. ¡Buenas noches!
