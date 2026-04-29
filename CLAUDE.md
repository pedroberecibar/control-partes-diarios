# Output Style & Token Reduction
Reply in the most concise form possible. Skip pleasantries, preambles, and recaps of my question. No phrases like "I'd be happy to", "Great question", or "Let me explain". Drop articles and filler words wherever the meaning stays clear. Prefer short declarative sentences. If a tool call is needed, run it first and show only the result. Do not narrate your steps.

## MCP Tools: code-review-graph
**IMPORTANT: This project has a knowledge graph. ALWAYS use the code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore the codebase.** The graph is faster, cheaper (fewer tokens), and gives you structural context (callers, dependents, test coverage) that file scanning cannot.

### Key Tools
* `detect_changes`: Reviewing code changes — gives risk-scored analysis
* `get_review_context`: Need source snippets for review — token-efficient
* `get_impact_radius`: Understanding blast radius of a change
* `get_affected_flows`: Finding which execution paths are impacted
* `query_graph`: Tracing callers, callees, imports, tests, dependencies
* `semantic_search_nodes`: Finding functions/classes by name or keyword
* `get_architecture_overview`: Understanding high-level codebase structure

### Graph Workflow
1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

## Reglas técnicas — migración PySpark → Pandas
> Este archivo se carga en cada turno. Documentado en `pyspark-version/plan_migracion_local.md`. No repetir errores conocidos.

### Invariantes del Core (Fase 3)
1. **NUNCA** `df.apply(axis=1)` en hot loops. Vectorizar con `np.where`, `np.select`, `Series.where/mask`, o operaciones de columna.
2. **Sort para reproducir `Window.orderBy`**: SIEMPRE `kind="mergesort"` + tie-breakers explícitos (ej. `_DECL_DESC`, `_REGLA_DESCRIPCION`, `_row_id`).
3. **`_row_id`** se genera con `np.arange(len(df), dtype=np.int64)`. Nunca `monotonically_increasing_id` ni equivalente.
4. **`FASE == "AMBAS"`**: pre-expandir `df_mc` a dos filas (`MON` y `TRI`) ANTES del merge. NO usar OR en la condición de join.
5. **MERGE de la fact table**: solo vía `io.merge_table(..., key="ID_PARTE_HASH")`. Nunca `to_parquet` directo sobre `gold/fact_*`.
6. **TRUNCATE del staging**: solo DESPUÉS de confirmar el write/MERGE. Nunca antes.
7. **Schema de la fact**: orden y tipos exactos según `config.COLS_FACT`.

### Restricciones de Red (Firewall Corporativo)
1. **NUNCA** uses `curl`, `wget`, `ping` ni intentes hacer peticiones HTTP a `localhost` (ej. puerto 5173 de Vite).
2. El firewall corporativo (Fortinet) bloquea conexiones de red salientes desde la terminal (ej. `curl.exe`). Intentarlo genera time-outs que consumen miles de tokens de forma inútil.
3. **Validación del Frontend:** Para verificar cambios en la UI, limitate estrictamente a leer/editar el código fuente (React/Vite). NO levantes el servidor de desarrollo ni intentes probar la UI por red. Yo haré la validación visual manualmente en mi navegador.


### Flujo de Trabajo y Validación
* Leer la sección equivalente del PySpark original (`pyspark-version/procesar_pd_gral_refactor (5).py`).
* El diff Pandas-vs-PySpark debe ser justificable línea a línea.
* Para sub-bloques sensibles (cruces A/B/C, dedup, paso 4a/4b): usar plan mode antes de editar.
* Validación: Corro pipeline → imprimo panel → usuario compara con Power BI local → si difiere, uso `scripts/inspect_parte.py`.

### Convenciones del repo
* IO con `src/io_lakehouse.py`. Nunca leer/escribir Parquet directo.
* Conexión Oracle solo vía `src/oracle_io.OracleReadOnly`.
* Constantes y rutas en `src/config.py`.
* Hashes deterministas en `src/hashing.py`.

### Estado Actual
* Hecho: Etapas 0 a 4 (seeds, maestros, adapters, core waterfall, panel KPIs, observaciones).
* Pipeline E2E activo vía `python run_pipeline.py`.