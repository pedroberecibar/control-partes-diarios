# Reporte de bugs del backend — decisiones pendientes

> **Fecha:** 2026-04-28
> **Contexto:** Auditoría del backend `python-version/api/` previa a integrar el prototipo del frontend. Algunos bugs los resolví autónomamente; los listados aquí requieren tu criterio porque implican decisiones de diseño (modelo de datos, persistencia de archivos, semántica de edición).

---

## Bugs ya resueltos (referencia, no requieren acción)

### Primera pasada (autónomos)
1. **`api/services/parte_service.py`** — faltaba `import pandas as pd` (la función `crear_partes_desde_df` lo usa). Resuelto.
2. **`api/routers/lotes.py:35`** — `obtener_lote` (GET) lanzaba el worker de procesamiento usando un parámetro `background_tasks` no declarado en la firma → 500 garantizado. Resuelto: removida la línea (un GET no debe disparar procesamiento).
3. **`api/routers/lotes.py:86`** — `actualizar_estado_lote` (PATCH) tenía el mismo bug. Resuelto: removida la línea.
4. **`api/services/worker.py`** — strings con mojibake (`vac?o`, `result?`). Resuelto: corregidos los caracteres.

### Segunda pasada (post-decisiones — implementación 2026-04-28)
5. **Bug 1** (persistencia de binario) → carpeta `data/uploads/` con naming `<sha256><ext>`, retención permanente. `LoteArchivo.ruta_archivo` agregado.
6. **Bug 2** (campos faltantes en modelos) → 14 campos agregados a `ParteDiarioProcesado` (sin `operario_nombre` por separación de capas). Tabla nueva `parte_imagenes` (1-5 filas por parte, con `orden`). `traza_calidad: String` reemplazada por `id_traza: Integer`. Servicio nuevo `dimensiones_service` que cachea las dim Parquet en memoria y traduce `id_traza`/`id_estado`/`usr_id`/`id_empresa` a labels al construir los DTOs.
7. **Bug 2 (worker)** → creación correcta de `ParteDiarioRaw` con `id_parte_hash` consistente con el motor (computado por el motor sobre `Suministro_Final`, no recomputado en el worker) y `fila_excel` 0-based. Matching raw↔procesado por `id_parte_hash`.
8. **Bug 2 (parte_service)** → `crear_partes_desde_df` extraída a un servicio dedicado `ParteImportService` (SRP). `ParteService` queda solo con consulta/edición y devuelve DTOs ya enriquecidos. Endpoint nuevo `GET /partes/{id}/visor` para el modal del visor de imágenes.
9. **Bug 3** (NULL en edit) → política A confirmada en `ParteService.editar_parte`. NULL = no tocar. Documentado.
10. **Bug 4** → resuelto junto con bug 2 (worker pasa `lote_id` y `contratista_id` correctamente al import service).
11. **Migración Alembic** `e3ff7d8f9492_add_uploads_path_observaciones_imagenes.py` generada y aplicada (DB SQLite vacía al momento de aplicar, sin pérdida de datos). Usa `op.batch_alter_table` para que sea compatible tanto con SQLite como con Postgres futuro.

### Bugs preexistentes detectados durante la implementación

12. **`src/etapa4_control_obs.py:run()`** — usaba `df_fact_input` en línea 497 sin tenerlo como parámetro de la función → `NameError` garantizado al invocar `run()`. Era el motivo de que el flow CLI E4 esté roto.
    - **Resolución:** agregado `df_fact_input: pd.DataFrame | None = None` como parámetro opcional. Si es None, lee Parquet (modo CLI original); si se pasa, ejecuta in-memory. Comportamiento CLI preservado, modo in-memory habilitado.
13. **`src/etapa4_control_obs.py`** — el worker original importaba `procesar_etapa4` que **no existía** como función pública, solo `run()`. El refactor in-memory mencionado en `progreso_diario.md` estaba a medias.
    - **Resolución:** agregada la función pública `procesar_etapa4(df_fact_input) -> (df_final, df_img, metricas)` como entrypoint limpio para el worker. Cumple OCP — extiende sin modificar la API existente.

---

## Bugs que requieren tu decisión

Los enumero en orden de bloqueo: el bug 1 y el 2 impiden cualquier corrida end-to-end del worker. El 3 y el 4 son refinamientos de semántica.

---

### Bug 1 — `LoteArchivo` no persiste el binario del archivo Excel (CRÍTICO)

**Dónde:**
- `api/db/models/base_models.py:23-37` — modelo `LoteArchivo` no tiene campo para la ruta/binario.
- `api/services/lote_service.py:74-83` — `crear_lote` recibe `contenido_bytes` pero **no lo guarda en ningún lado**.
- `api/services/worker.py:32` — `path = Path(lote.ruta_archivo)` lee un atributo `ruta_archivo` **que no existe** en el modelo → `AttributeError` al primer procesamiento.

**Síntoma:** subir un Excel desde el endpoint `POST /api/v1/lotes` crea la fila en `lotes_archivos`, pero el worker explota apenas intenta leerlo.

**Decisiones que necesito de vos:**

1. **¿Dónde se persiste el binario del Excel subido?** Tres opciones:
   - **A)** Carpeta local en disco (ej. `python-version/data/uploads/<lote_id>_<sha256>.xlsx`). Simple, funciona en dev y en on-prem inicial. Requiere agregar campo `ruta_archivo: String` al modelo.
   - **B)** MinIO local (compatible S3) — alineado con el plan de arquitectura objetivo. Más infra, pero futuro-compatible.
   - **C)** Postgres como BLOB / SQLite como BLOB (`LargeBinary`). Simple pero ineficiente para archivos de 50 MB.

   **Mi recomendación:** opción A para esta fase (más simple y reversible), agregando campo `ruta_archivo` al modelo. Migrar a MinIO cuando se corte hacia Postgres.

   **Decisión Final:** Opcion A (como tu recomendación)

2. **¿Querés que use el SHA256 ya calculado como nombre de archivo (idempotencia)?** O preferís un nombre con el `lote_id` + nombre original?
   
   **Decisión Final:** Lo que te parezca mejor (mas seguro y confiable)

3. **Política de retención:** ¿borrás el binario después de procesar OK, o lo conservás siempre (auditoría legal)? Esto afecta si el modelo necesita un flag `binario_disponible` o no.

   **Decisión Final:** Conservarlo siempre para auditoría

---

### Bug 2 — `ParteDiarioProcesado` y `ParteDiarioRaw` con campos incompatibles (CRÍTICO)

**Dónde:**
- `api/services/parte_service.py:146-165` — el constructor de `ParteDiarioProcesado` referencia campos **inexistentes en el modelo**:
  - `lote_id` ❌
  - `valor_uses` ❌
  - `url_foto_1`, `url_foto_2`, `url_foto_3` ❌
  - `metricas_analitica` ❌
- Además usa `int(row.get("ID_TRAZA"))` pero el modelo declara `traza_calidad` como `String(100)` → type mismatch.
- También: `id_parte_hash` y `id_estado` son `nullable=False` en el modelo, pero el constructor no los está pasando explícitamente.

- `api/services/worker.py:48-56` — al crear `ParteDiarioRaw`:
  - Pasa `ordenativo=...` y `raw_data=...` ❌ (el modelo tiene `id_externo`, `datos_crudos`, `id_parte_hash`, `fila_excel`)
  - **No setea** `id_parte_hash` ni `fila_excel`, que son `nullable=False` → la transacción va a fallar al `flush()`.

**Síntoma:** el worker termina en el `except` con `TypeError: 'lote_id' is an invalid keyword argument` (o similar) en cuanto llega a `crear_partes_desde_df`. Antes de eso, falla al insertar el primer raw.

**Decisiones que necesito de vos:**

1. **`traza_calidad` — ¿int o string?**
   - El motor analítico (Etapa 3) genera tanto `ID_TRAZA` (int, FK lógica a `dim_traza_calidad_bi`) como `TRAZA_CALIDAD` (string, ej. `"Original OK"`).
   - **Mi recomendación:** guardar **ambas** en el modelo: `id_traza` (Integer, FK lógica) + `traza_calidad` (String(100), denormalizado para mostrar sin join). Esto evita joins en cada listado de la bandeja.
   - ¿Lo hacemos así, o preferís solo el `id_traza` y joineás con la dim cuando muestres?

   **Decisión Final:** Guardar solo el id_traza, y unir cuando se muestre (desde el punto de vista de la ingenieria en sistemas, esto lo deberia hacer el service cuando el controller se lo pida al recibir una peticion del frontend, de esta manera el controller y el frontend no necesitan saber nada de la base de datos, solo necesitan saber que el service les va a devolver los datos que necesitan para mostrar en la pantalla, de esta manera se cumple con el principio de separacion de capas)

2. **Campos a agregar al modelo `ParteDiarioProcesado`** (alineado con los DTOs del prompt del visor de imágenes que ya pasamos a Claude Design):

   | Campo | Tipo | Necesario para |
   |---|---|---|
   | `lote_id` | `Integer FK lotes_archivos` | Filtrar bandeja por lote (B5) |
   | `contratista_id` | `Integer FK contratistas` | Filtros y dashboards | 
   | `operario_nombre` | `String(200)` | Modal del visor + bandeja | 
   | `usr_id` | `Integer` | FK lógica a usuarios SIGEC |
   | `valor_uses_origen` | `Float` | Dashboards módulo C |
   | `valor_uses_obs` | `Float` | Dashboards módulo C |
   | `imagenes_urls` | `JSON` (lista de strings) | Modal del visor (1-5 fotos) |
   | `obs_gabinete` | `Boolean` | Modal del visor — observaciones app |
   | `obs_subterraneo` | `Boolean` | idem |
   | `obs_altura` | `Boolean` | idem |
   | `obs_aereo` | `Boolean` | idem |
   | `obs_equipo_reemplazado` | `Boolean` | idem |
   | `obs_acometida_realizada` | `Boolean` | idem |
   | `obs_tapa_reemplazada` | `Boolean` | idem |
   | `obs_mediciones_registradas` | `Boolean` | idem |
   | `metricas_analitica` | `JSON` | Snapshot completo del DataFrame para debugging/export |

   ¿Aprobás esta lista completa? ¿Falta o sobra algo?

   **Decisión Final:** No agregar operario_nombre. Misma decision y justificacion que con trza_calidad (mantenemos el usr_id)

3. **`ParteDiarioRaw` — campos faltantes del worker:**
   - El worker necesita setear `id_parte_hash` y `fila_excel` al crear cada raw. ¿Cómo se computa el hash en este punto del flujo? Hay dos opciones:
     - **A)** Usar `src/hashing.id_parte_hash(...)` (ya existe en el motor) sobre los campos clave de cada fila. **Mi recomendación.**
     - **B)** Usar el hash del `payload` JSON entero (más débil pero más simple).
   - ¿`fila_excel` debe ser el índice 0-based del DataFrame, o el número de fila real del Excel original (1-based, salteando header)?

   **Decisión Final:** Opcion A. 0-based.

4. **Imágenes — esquema de almacenamiento:**
   - El motor genera `dim_img_app_pd` con columnas `IMAGEN_1`...`IMAGEN_5`. ¿Las traemos al modelo como un JSON array (mi recomendación), o creamos una tabla separada `parte_imagenes` con una fila por imagen + orden?
   - Tabla separada da flexibilidad (rotación persistida, metadata por imagen) pero agrega un join. Para 1-5 fotos, JSON array es más práctico.

   **Decisión Final:** Tabla separada con un registro por imagen + orden.

5. **`raw_id` en `ParteDiarioProcesado`:** el worker hoy crea los raw, hace `flush()`, y después llama a `crear_partes_desde_df(...)` que **no asocia el `raw_id`** correspondiente a cada fila procesada. ¿Cómo querés que se haga el matching raw ↔ procesado?
   - **A)** Por `id_parte_hash` (ambas tablas lo tienen).
   - **B)** Por `fila_excel` y `lote_id`.
   - **Mi recomendación: A**, pero requiere que el motor analítico devuelva el `id_parte_hash` en el `df_final` (verificar).

   **Decisión Final:** Opcion A (Por `id_parte_hash`).

---

### Bug 3 — `editar_parte` no permite limpiar campos a NULL

**Dónde:** `api/services/parte_service.py:81-100`.

**Síntoma:** la condición `if nuevo_valor is not None` significa que un auditor **nunca puede borrar** un valor existente (ej. quitar un `ord_nro` mal asociado dejándolo en NULL). Tendría que enviar el campo con un valor "dummy" para forzar el cambio.

**Decisión que necesito de vos:**
- **A)** Aceptar el comportamiento actual: en la edición, NULL = "no tocar este campo". Si el auditor quiere limpiar, debe usar un endpoint distinto (ej. `DELETE /partes/{id}/ord_nro`).
- **B)** Cambiar la semántica a: "el frontend siempre envía todos los campos editables, y NULL = limpiar". Más explícito pero el frontend tiene que mandar más data.
- **C)** Usar un sentinel especial (ej. envolver cada campo en `{value: ..., explicit_null: bool}`). Verboso pero inequívoco.

**Mi recomendación:** **A** por simplicidad. Los casos de "limpiar campo" son raros y un endpoint específico los hace explícitos en la auditoría.

**Decisión Final:** Aceptar el comportamiento actual, en la edición, NULL = "no tocar este campo". Si el auditor quiere limpiar, debe usar un endpoint distinto

---

### Bug 4 — `worker.py` no asocia el `lote_id` ni el `contratista_id` a los partes procesados

**Dónde:** `api/services/worker.py:79` — `crear_partes_desde_df(db, lote.id, df_final, df_img)`.

La función **recibe** el `lote_id`, pero el constructor de `ParteDiarioProcesado` (con los bugs del Bug 2) intenta setearlo en un campo que no existe.

Una vez se resuelva el Bug 2 con la lista de campos aprobada, esto se desbloquea solo. Solo dejo la nota acá para que sepas que **están relacionados**: cuando me confirmes los campos, los implemento juntos.

---

## Resumen — qué necesito de vos para destrabar

Puede ser todo en una sola respuesta:

1. **Bug 1:** confirmar opción **A** (carpeta local `data/uploads/`) + nombre con SHA256, o decir cuál preferís.
2. **Bug 2.1:** confirmar que `traza_calidad` se guarda como `id_traza` (int) + `traza_calidad` (string denormalizada).
3. **Bug 2.2:** aprobar (o ajustar) la lista de 15 campos a agregar a `ParteDiarioProcesado`.
4. **Bug 2.3:** confirmar uso de `src.hashing.id_parte_hash` para el raw + criterio de `fila_excel` (índice del DF vs nro real del Excel).
5. **Bug 2.4:** confirmar JSON array para imágenes (vs. tabla separada).
6. **Bug 2.5:** confirmar matching raw↔procesado por `id_parte_hash`.
7. **Bug 3:** confirmar opción **A** (NULL = no tocar) o elegir B/C.

Con esas respuestas implemento de una todos los bugs restantes en un solo PR (incluye migración Alembic, ajustes de modelo, refactor de `worker.py` y `crear_partes_desde_df`, y actualización de los DTOs del visor de imágenes).

**ACLARACION FINAL**: Como regla de oro, siempre pensar las soluciones (estas y todas las que vengan) priorizando los principios SOLID y las buenas practicas de desarrollo de software, no busques la forma mas rapida de resolver los problemas, busca la forma mas correcta y mantenible (teniendo en cuenta el contexto y las restricciones del proyecto).