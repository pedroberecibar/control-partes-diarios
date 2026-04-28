# Workflow recomendado para Fase 3 (Core Waterfall)

> Esta es la fase más sensible: 80% del riesgo del proyecto. La paridad numérica
> con Fabric tiene que ser **exacta** (mismo conteo por `TRAZA_CALIDAD`,
> mismo `sum(cant_USE_unitario)` con 4 decimales). Para no romper nada en silencio,
> el workflow se apoya fuerte en herramientas de Claude Code que evitan errores
> mecánicos. Concreto y aplicable, sin teoría.

---

## 1. Setup one-time (15 min, antes de tocar `etapa3_core.py`)

### 1.1 `CLAUDE.md` en `python-version/` con invariantes pegados al código

Las reglas técnicas que el plan menciona en §3.1–§3.3, pero que se pierden
si quedan solo en un md largo. En CLAUDE.md aparecen en cada turno:

```markdown
# Reglas técnicas Fase 3 (Core Waterfall)

- NUNCA usar `df.apply(axis=1)` en hot loops. Vectorizar con `np.where`,
  `np.select`, o operaciones de columna.
- Sort para reproducir `Window.orderBy` de Spark: SIEMPRE `kind="mergesort"`
  + tie-breakers explícitos (`_DECL_DESC`, `_REGLA_DESCRIPCION`, `_row_id`).
- `_row_id` se genera con `np.arange(len(df), dtype=np.int64)`. Nunca
  `monotonically_increasing_id` ni equivalente.
- Cuando una regla diga `FASE == "AMBAS"`: pre-expandir a dos filas
  (MON y TRI) antes del merge. NO usar OR en la condición de join.
- `merge_table` por `ID_PARTE_HASH` es la única forma de upsertear la fact.
  Nunca escribir directamente con `to_parquet` sobre `gold/fact_*`.
- Antes de tocar cualquier sub-bloque, leer la sección equivalente del
  PySpark original (`pyspark-version/procesar_pd_gral_refactor (5).py`).
  El diff debe ser justificable línea a línea.
```

### 1.2 Hook pre-edit que bloquea pyspark/spark leftovers en `src/`

`/update-config` con un `PreToolUse` hook (Edit/Write) que rechaza el
write si el `new_string` contiene `pyspark`, `spark.`, `F.col`, `F.when`,
`monotonically_increasing_id`, `delta.tables`, o `mssparkutils`. Dos líneas
de bash; corta una clase entera de bugs.

### 1.3 Allowlist de comandos read-only con `/fewer-permission-prompts`

Para no aprobar 50 veces el mismo `python -m pytest`, `python run_pipeline.py
--solo-etapa 3 --reproceso`, `python -c "import pandas..."`. Drop-in.

---

## 2. Workflow por sub-ticket (3.1 → 3.5)

El plan ya tiene los sub-tickets divididos. Para cada uno:

### Paso A — Plan mode (`Shift+Tab` → Plan)

Especialmente para 3.3 (cruces A/B/C) y la dedup `Repetido X Sumi`:

1. Leer la sección del PySpark original.
2. En plan mode, escribir el equivalente Pandas SIN ejecutar. Discutir
   tipos, claves de join, tie-breakers.
3. Recién al aprobar, salir de plan mode y editar.

Esto evita el ciclo "escribo → corre → no da el mismo número → debugging
mediante prints" que es lento y opaco.

### Paso B — TodoWrite con los 5 sub-tickets

```
[3.1] Dimensiones estáticas (literales)        — chico
[3.2] actualizar_dim_archivo (idempotente)    — chico
[3.3] Cruces A/B/C + ensamblado + dedup       — GRANDE (subdividir)
[3.4] dim_suministros_geo + dim_calendario    — medio
[3.5] Panel KPIs                              — chico
```

Cada paso completado se cierra inmediatamente. Si 3.3 explota en cinco
sub-tareas, también van al todo.

### Paso C — Verificación obligatoria antes de cerrar el ticket

No se cierra ningún sub-ticket de 3.3 sin correr el harness de §3.

---

## 3. Harness de validación (KPI-only — Fabric ya no está disponible)

> **Cambio de estrategia (2026-04-24):** no hay capacidad para correr Fabric,
> así que no podemos generar un baseline row-level del fact. La validación se
> hace contra los KPIs del Power BI local del usuario.

### 3.1 Panel de KPIs (sub-ticket 3.5)

Reproducir **exacto** el "Panel de Control" de PySpark (Celda 7 de
`procesar_pd_gral_refactor.py`, líneas ~970-1050). Se traduce 1:1 a Pandas
y se imprime después de cada corrida del Core. El usuario mira el panel y
lo compara contra los mosaicos de su Power BI.

KPIs esperados (todos los que hoy ya están validados en Power BI):

- Conteos por `TRAZA_CALIDAD`
- `sum(cant_USE_unitario)` total + por traza (4 decimales)
- Conteos por `ID_ESTADO`
- Totales por `CODIGO_CONTRATISTA` (CONECTAR vs COOPLYF)
- Totales por mes (`Periodo`)
- Días trabajados, partes pagables vs no pagables

### 3.2 Test de no-regresión (`tests/test_kpis_core.py`)

Aunque no podamos validar contra Fabric, sí podemos detectar **regresiones
internas**: la primera corrida verde se snapshotea como "current truth", y
las siguientes corridas tienen que dar los mismos números (modulo cambios
de input).

```python
def test_kpis_no_regression():
    # 1. Correr etapa3_core.run() sobre el staging actual
    # 2. Calcular KPIs con la función oficial del panel
    # 3. Comparar contra snapshot guardado en tests/fixtures/kpis_snapshot.json
    # 4. Si el usuario aprobó manualmente un cambio → actualizar el snapshot
```

Esto evita que un refactor de la fase 4 rompa silenciosamente la fase 3.

### 3.3 Spot-check manual de partes (`scripts/inspect_parte.py`)

Helper para tomar un `ID_PARTE_HASH` (o un Suministro+Fecha) e imprimir el
trace completo: input crudo → cruce que matcheó → orden detectada →
TRAZA_CALIDAD asignada → cant_USE_unitario. Útil cuando un KPI difiere y
hay que entender por qué.

### 3.4 Loop de validación con el usuario

```
[claude] corre etapa3 → imprime panel
[user]   compara contra Power BI
[user]   "el conteo de Repetido X Sumi me da 350 acá pero 412 en Power BI"
[claude] usa scripts/inspect_parte.py para muestrear casos sospechosos
[claude] ajusta lógica → corre de nuevo
```

Esto es **más lento** que un diff automático pero es lo que hay. Por eso
es tan importante el plan mode (§2 paso A): cada error en el Core cuesta
varias rondas con vos.

---

## 4. Cuándo escalar a herramientas mayores

| Situación                                                | Herramienta                          |
|----------------------------------------------------------|--------------------------------------|
| "Quiero probar 2 implementaciones del Cruce A en paralelo" | `Agent(isolation=worktree)` × 2     |
| "El test de paridad rompió y no sé dónde"                 | `Agent(general-purpose)` para bisecar el commit |
| Antes de cerrar la Fase 3 entera                          | `/review` (skill) sobre el branch    |
| Refactor post-paridad ya verde                            | `/simplify` (skill) por sub-bloque   |
| Necesito entender un .py viejo de Fabric rápido            | `Agent(Explore, "thorough")`         |

NO usar agentes para tareas pequeñas (releer un archivo, un grep) — el
costo de spawn no compensa.

---

## 5. Anti-patrones a evitar en esta fase

1. **Optimizar antes de tener paridad.** El orden es: replicar 1:1 → test pasa → recién ahí simplificar.
2. **Saltarse el plan mode en 3.3.** Los cruces tienen 4 fixes documentados (`FIX-A/B/C/G`) que son fáciles de pasar por alto.
3. **Aceptar "casi igual".** Si el conteo de `Repetido X Sumi` difiere en 1, hay un bug. No promediarlo.
4. **Tocar el schema de `COLS_FACT`** sin actualizar a la vez la lista en `config.py`. Son la única fuente de verdad.
5. **Commitear sin correr `test_paridad_core`.** Hook opcional: PreToolUse Bash que rechace `git commit` si ese test no pasó en los últimos N minutos.
