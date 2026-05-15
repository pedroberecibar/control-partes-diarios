# Auditoría Estática del Motor de Procesamiento — `python-version/src/`

**Rol:** Senior Data Engineer / Experto en arquitecturas de datos y Pandas  
**Alcance:** Solo lectura. Sin modificaciones al código fuente.  
**Fecha:** 2026-05-13  
**Archivos revisados:** `etapa3_core.py`, `config.py`, `hamming.py`, `io_lakehouse.py`, `etapa4_control_obs.py`, `etapa3_panel_kpis.py`

---

## Resumen Ejecutivo

| Severidad | Cantidad | Impacto principal |
|-----------|----------|-------------------|
| 🔴 CRÍTICO | 3 | Pérdida de datos silenciosa / corrupción de FK / comportamiento incorrecto no documentado |
| 🟡 ADVERTENCIA | 5 | Código frágil o inconsistente que puede producir resultados incorrectos en edge cases |
| 🟢 SUGERENCIA | 3 | Optimizaciones de rendimiento o claridad sin impacto en correctitud |

---

## 🔴 CRÍTICOS

### C-1 — `RESCATE_DIAS_TOLERANCIA` definido pero **nunca usado** (cruce_C opera con 15 días en vez de 7)

**Archivo:** `config.py:48` / `etapa3_core.py:541-543`

**Evidencia:**
```python
# config.py:48
RESCATE_DIAS_TOLERANCIA = 7   # ← definido

# etapa3_core.py:541-543  — cruce_C
df_con_orden = rank_one_by_dias(df_con_orden)
# rank_one_by_dias usa internamente: out["dias_diff"] <= config.DIAS_TOLERANCIA (15)
# NUNCA referencia RESCATE_DIAS_TOLERANCIA
log.info("    Cruce C: 0 órdenes CE para los suministros rescatados (ventana 15d).")
#                                                                             ^^^^^
# El mismo log lo dice: usa 15d, no 7d.
```

**Grep confirma:** `RESCATE_DIAS_TOLERANCIA` aparece solo en `config.py:48`. No existe ninguna otra referencia en todo `src/`.

**Impacto:** El rescate técnico (Cruce C) acepta candidatos a hasta 15 días de diferencia cuando el diseño especifica 7. Produce matches espurios: un parte puede ser "rescatado" y marcado como "Corregido Sumi" / "Corregido Sumi Nro EQP" con una orden que en realidad no corresponde por el tiempo transcurrido. Estos partes quedan aprobados o en revisión incorrectamente.

**Fix necesario:** En `cruce_C`, pasar la tolerancia explícita a `rank_one_by_dias`:
```python
df_con_orden = rank_one_by_dias(
    df_con_orden,
    tolerancia=config.RESCATE_DIAS_TOLERANCIA,  # 7 días
)
# + agregar parámetro `tolerancia` a rank_one_by_dias con default=config.DIAS_TOLERANCIA
```

---

### C-2 — `ID_TRAZA` puede quedar `<NA>` silenciosamente (FK rota en la fact table)

**Archivo:** `etapa3_core.py:829-835`

**Evidencia:**
```python
# etapa3_core.py:829-835
df = df.merge(
    df_dim_traza[["ID_TRAZA", "DESC_TRAZA"]],
    left_on="TRAZA_CALIDAD", right_on="DESC_TRAZA",
    how="left",    # ← LEFT JOIN: si TRAZA_CALIDAD no existe en dim_traza → ID_TRAZA = <NA>
)
df["ID_TRAZA"] = df["ID_TRAZA"].astype("Int64")  # ← <NA> permanece como <NA>
```

Sin `assert`, sin `log.warning`, sin `raise`. Si se agrega una traza nueva al waterfall sin actualizar `dim_traza_calidad_bi`, esas filas van a la fact table con `ID_TRAZA = <NA>`.

**Impacto en downstream:**
- `etapa3_panel_kpis.py:60`: `.merge(df_traza, on="ID_TRAZA", how="left")` — filas con `ID_TRAZA = <NA>` no matchean nada (Pandas: `<NA> != <NA>`) y quedan con `DESC_TRAZA = NaN`. El panel las cuenta en el total pero no las categoriza.
- La fact table tiene una FK lógica rota. Cualquier query SQL sobre `fact JOIN dim_traza` produce filas huérfanas.

**Fix necesario:** Post-merge, agregar validación:
```python
n_sin_traza = df["ID_TRAZA"].isna().sum()
if n_sin_traza > 0:
    trazas_faltantes = df.loc[df["ID_TRAZA"].isna(), "TRAZA_CALIDAD"].unique().tolist()
    raise ValueError(
        f"{n_sin_traza} partes sin ID_TRAZA. "
        f"Trazas no encontradas en dim_traza: {trazas_faltantes}"
    )
```

---

### C-3 — `config.TRAZAS_RECHAZO` es dead code con semántica **incorrecta** (confusión de ID_ESTADO)

**Archivo:** `config.py:70-79` / `etapa3_core.py:805-811`

**Evidencia:**
```python
# config.py:70-79 — TRAZAS_RECHAZO incluye:
TRAZAS_RECHAZO = [
    "No Corresponde TOR CE",   # ← línea 71
    ...
    "Otro Origen",             # ← línea 77
    ...
]

# etapa3_core.py:805-811 — normalizar_a_fact_schema
cond_estado = [
    df["TRAZA_CALIDAD"].isin(config.TRAZAS_OK),
    df["TRAZA_CALIDAD"].isin(config.TRAZAS_REVISION),
    df["TRAZA_CALIDAD"].isin(["No Corresponde TOR CE", "Otro Origen"]),  # → ID_ESTADO=4
]
choice_estado = [1, 2, 4]
df["ID_ESTADO"] = np.select(cond_estado, choice_estado, default=3)
# config.TRAZAS_RECHAZO NUNCA SE REFERENCIA AQUÍ NI EN NINGÚN OTRO MÓDULO
```

**Grep confirma:** `TRAZAS_RECHAZO` aparece solo en `config.py`. Cero usos en `src/`.

**Doble problema:**
1. `TRAZAS_RECHAZO` sugiere que "No Corresponde TOR CE" y "Otro Origen" son Rechazado (ID_ESTADO=3), pero el código correcto las asigna a Fuera de Alcance (ID_ESTADO=4). La constante da información falsa.
2. `TRAZAS_DESCARTE_TECNICO` (línea 81 de config.py) es la que realmente se usa. Tiene overlap semántico con `TRAZAS_RECHAZO` pero no son iguales: `TRAZAS_RECHAZO` incluye "Informados con ORD-SUMI aprobado" e "Informado - No Ejecutado" que no están en `TRAZAS_DESCARTE_TECNICO`.

**Impacto:** Si un desarrollador usa `TRAZAS_RECHAZO` para filtrar en el API (ej. para el OVERLAP_WARNING check), incluiría partes de "Fuera de Alcance" en la cuenta de rechazos, distorsionando el umbral del 50%.

---

## 🟡 ADVERTENCIAS

### W-1 — NaT doble en fechas de órdenes → partes silenciosamente clasificados como "Sin Orden Asociada"

**Archivo:** `etapa3_core.py:103-111, 197, 231`

**Evidencia:**
```python
# _clip_fecha_orden: convierte sentinels (año 2919, etc.) a NaT
def _clip_fecha_orden(s: pd.Series) -> pd.Series:
    mask = s.notna() & ((s < _FECHA_MIN_ORD) | (s > _FECHA_MAX_ORD))
    s = s.mask(mask)  # → NaT para sentinels

# _construir_df_ord_ce — línea 197:
"ord_fecha_ref": sub["ORD_FECHA_FIN"].dt.normalize(),  # NaT si ORD_FECHA_FIN fue sentinel

# _construir_df_ord_rechazo_tor — línea 231:
fecha_ref = sub["ORD_FECHA_FIN"].fillna(sub["ORD_FECHA_INICIO"]).dt.normalize()
# Si AMBAS son sentinel → NaT → fillna(NaT) → sigue siendo NaT
```

**Flujo del bug:**
1. Oracle envía `ORD_FECHA_FIN = año 2919` y `ORD_FECHA_INICIO = NaT`.
2. `_clip_fecha_orden` convierte ambas a `NaT`.
3. `ord_fecha_ref = NaT`.
4. En `rank_one_by_dias`: `dias_diff = |Fecha_Norm - NaT| = NaT`.
5. `NaT <= 15` → `False` → esa orden se descarta del pool de candidatos.
6. El parte termina en huérfanos con "Sin Orden Asociada" (Rechazado).

**Impacto:** Un parte con orden CE válida pero con fecha corrupta en Oracle aparece como "Sin Orden Asociada". No hay log de advertencia. El diagnóstico vía `scripts/inspect_parte.py` mostraría la orden pero no el motivo del descarte.

---

### W-2 — Tie-breaker condicional en `rank_one_by_dias`: sin `NUMERO_ORDEN`, el desempate es no-determinista

**Archivo:** `etapa3_core.py:65-68`

**Evidencia:**
```python
sort_cols: list[str] = [key, "dias_diff"]
if "NUMERO_ORDEN" in out.columns:
    sort_cols.append("NUMERO_ORDEN")  # tie-breaker determinista
out = out.sort_values(sort_cols, kind="mergesort", na_position="last")
```

**Escenario de falla:** Si se llama `rank_one_by_dias` con un DataFrame sin `NUMERO_ORDEN`, y dos órdenes tienen exactamente el mismo `dias_diff` para el mismo `_row_id`, el `mergesort` preserva el orden de entrada del DataFrame, que depende del orden de lectura de `dim_ord` (no garantizado entre runs). El parte puede cruzar con órdenes distintas en diferentes ejecuciones.

**Estado actual:** En los cruces A y C actuales, `NUMERO_ORDEN` siempre existe (viene de `_construir_df_ord_ce`). Pero es frágil: ninguna aserción lo valida.

**Fix sugerido:**
```python
# Opción A — assert explícito
assert "NUMERO_ORDEN" in out.columns, "tie-breaker NUMERO_ORDEN ausente — sort no determinista"

# Opción B — usar _row_id como fallback explícito
sort_cols = [key, "dias_diff", "NUMERO_ORDEN"] if "NUMERO_ORDEN" in out.columns else [key, "dias_diff", "_row_id"]
```

---

### W-3 — `etapa4_control_obs._normalizar_obs`: whitespace-only strings tratados como observación positiva

**Archivo:** `etapa4_control_obs.py:153`

**Evidencia:**
```python
def _normalizar_obs(df: pd.DataFrame) -> pd.DataFrame:
    for col_app, col_regla in OBS_COLS:
        df[f"_APP_{col_regla}"] = df[col_app].notna().astype("int8")
        # ↑ .notna() = True para "   " (espacios), "" (string vacío), "0", etc.
```

**Impacto:** Si la app móvil envía `"   "` (spacebar) en un campo de observación en lugar de `null`, se computa `_APP_GABINETE = 1` en vez de 0. El vector de Hamming difiere del esperado → asignación incorrecta de código EPEC → pago incorrecto.

**Escenario real:** Los Excel de los contratistas pueden venir con celdas que tienen espacios residuales en vez de vacías, especialmente si el formulario se exporta desde otra app.

**Fix:**
```python
col_clean = df[col_app]
if pd.api.types.is_string_dtype(col_clean) or pd.api.types.is_object_dtype(col_clean):
    col_clean = col_clean.str.strip().replace("", pd.NA)
df[f"_APP_{col_regla}"] = col_clean.notna().astype("int8")
```

---

### W-4 — Regla "Otro Origen" sobreescribe silenciosamente trazas válidas (sin log de advertencia)

**Archivo:** `etapa3_core.py:636-641`

**Evidencia:**
```python
# 5. Regla "Otro Origen" — pisa lo que sea que tenga TRAZA.
mask_otro_origen = (
    df_full["SEC_CODIGO_ORIGEN"].notna()
    & (df_full["SEC_CODIGO_ORIGEN"].astype("string") != "PROTELEM")
)
df_full.loc[mask_otro_origen, "TRAZA_CALIDAD"] = "Otro Origen"
# ↑ Sin log. Un parte con TRAZA="Original OK" puede convertirse en "Otro Origen"
#   si su orden proviene de un sistema distinto a PROTELEM.
```

**Impacto:** Un parte legítimo (medidores correctos, orden CE válida) cuya orden fue creada en un sistema no-PROTELEM aparece como "Fuera de Alcance" sin ninguna traza del porqué. En auditorías es confuso: `inspect_parte.py` mostrará la orden válida pero la traza dice "Otro Origen".

**Fix sugerido:** Agregar log de count antes del override:
```python
n_otro = mask_otro_origen.sum()
if n_otro > 0:
    log.warning("  Regla Otro Origen: %d partes override (SEC_CODIGO_ORIGEN != PROTELEM)", n_otro)
```

---

### W-5 — `OVERLAP_WARNING_THRESHOLD` no implementado en el pipeline

**Archivo:** `config.py:55`

```python
# config.py:55
OVERLAP_WARNING_THRESHOLD = 0.5
# Grep en src/ → cero usos fuera de config.py
```

La feature de antiduplicidad histórica (protección contra re-billing — Traza 18: "Registro Ya Procesado en Lote Anterior") **no tiene implementación** en el pipeline actual. No hay ningún punto del waterfall que consulte lotes históricos.

**Impacto:** Un lote duplicado (reenvío accidental del mismo mes) pasaría el pipeline completo sin advertencia, resultando en pagos duplicados. Traza 18 nunca se asignaría.

---

## 🟢 SUGERENCIAS DE RENDIMIENTO / CLARIDAD

### S-1 — `df_join.copy()` innecesario en `rank_one_by_dias` (`etapa3_core.py:57`)

```python
out = df_join.copy()   # innecesario — ninguna operación posterior modifica df_join
```

Las operaciones posteriores (`out["dias_diff"] = ...`, `out = out.loc[...]`) no hacen in-place sobre `df_join`. El `copy()` fuerza una copia completa del resultado del cartesian product (potencialmente millones de filas). Eliminarla reduciría uso de RAM ~50% durante el ranking.

---

### S-2 — `_expandir_mc_ambas(df_mc)` re-ejecutada en cada llamada a `enriquecer_y_deduplicar` (`etapa3_core.py:732`)

`df_mc` es un maestro estático que no cambia entre llamadas. Si en el futuro se procesa más de una contratista por run, la expansión se repite inútilmente. Cachear o pre-expandir en el entrypoint.

---

### S-3 — `TRAZAS_RECHAZO` debería eliminarse o corregirse (`config.py:70-79`)

(Ver C-3.) La constante es dead code con semántica incorrecta para 2 de sus 9 miembros. Opciones:
- **Opción A:** Eliminar `TRAZAS_RECHAZO`.
- **Opción B:** Corregir para reflejar exactamente qué trazas dan `ID_ESTADO=3` (excluir "No Corresponde TOR CE" y "Otro Origen") y usarla en `normalizar_a_fact_schema`.

---

## Verificación de los 5 Pilares Solicitados

### Pilar 1 — Cruces de Fechas y Timezones

| Punto | Resultado |
|-------|-----------|
| Fechas sentinel año 2919 | ✅ `_clip_fecha_orden` las convierte a NaT antes de cualquier cruce |
| `abs()` da float (15.01 días) | ✅ Se usa `.dt.days` (entero). No hay riesgo de 15.01 > 15. |
| NaT en fechas → descarte silencioso | 🔴 **C-1 / W-1**: `NaT <= 15 = False` → orden descartada sin traza |
| `RESCATE_DIAS_TOLERANCIA` aplicado | 🔴 **C-1**: No aplicado. Cruce C usa 15 días en vez de 7. |
| Diferencias de Timezone | ✅ Fechas del parte normalizadas vía adapter; fechas de ord son `datetime64[us]` sin tz. No hay mixing naive/aware. |

### Pilar 2 — Propagación de Trazas y Estados

| Punto | Resultado |
|-------|-----------|
| Toda fila termina con `ID_ESTADO` | ✅ `np.select(..., default=3)` garantiza ninguna fila sin estado. |
| Toda fila termina con `ID_TRAZA` | 🔴 **C-2**: Left join sin validación → `ID_TRAZA = <NA>` posible. |
| Trazas 5, 19, 20 → Revisión | ✅ "Corregido Sumi Nro EQP" (T5), "Rescatado por Oracle" (T19), "Múltiples Candidatos Oracle" (T20) están en `config.TRAZAS_REVISION` → `ID_ESTADO=2`. |
| Left joins huérfanos | ✅ `ensamblar_y_reglas_huerfano` usa `fillna` para asignar traza a filas sin match. Ninguna fila queda sin `TRAZA_CALIDAD`. |
| Override `TRAZA_ADAPTER` tiene máxima prioridad | ✅ Paso 7 del ensamblado sobreescribe cualquier traza del waterfall. |

### Pilar 3 — Manejo de Nulls y Tipos de Datos

| Punto | Resultado |
|-------|-----------|
| `_to_int64_nullable` robustez | ✅ `pd.to_numeric(errors="coerce")` + `np.trunc` + `.astype("Int64")` maneja NaN/strings/floats. |
| Merge key `Int64` vs `float64` | ✅ `ID_PARTE_HASH` es siempre `string` en ambos lados. Sin riesgo de tipo. |
| OBS_COLS columna vacía en Hamming | 🟡 **W-3**: `etapa4_control_obs` hace `fillna(0)` antes de la matriz (líneas 308-309), protege de NaN. Pero whitespace-only strings siguen siendo problema. |
| `hamming_matrix` con NaN | ✅ Las líneas 308-309 hacen `.fillna(0).to_numpy(dtype="int8")` previo. No hay propagación de NaN al cálculo. |

### Pilar 4 — Lógica de Deduplicación

| Punto | Resultado |
|-------|-----------|
| Sort estable en dedup | ✅ `kind="mergesort"` en línea 762. |
| Criterios de dedup (mejor candidato) | ✅ Ordena por `prioridad_cod desc`, `Fecha_Norm desc`, `_row_id desc`. Determinista gracias a `_row_id` único. |
| "Perdedores" marcados como Traza 10 | ✅ `posicion > 1 → "Informados con ORD-SUMI aprobado"`. |
| Lotes "Rechazados" excluidos de OVERLAP check | ⚠️ **W-5**: El OVERLAP check no existe. |
| Traza 16/18 (duplicado exacto / ya procesado) | ⚠️ **W-5**: Traza 18 nunca se asigna. Traza 16 no encontrada en el código analizado. |

### Pilar 5 — Lógica "No Ejecutado" (Traza 13)

| Punto | Resultado |
|-------|-----------|
| `ORD_RESULTADO == "IN"` evaluado primero | ✅ Primera condición del `np.select` en cruce_A línea 344. Primera match gana. |
| No hay riesgo de aprobación accidental | ✅ Un parte con orden "IN" nunca llega a comparar medidores. |
| Otros resultados fallidos ("FT", "FF") | ✅ Solo "E", "IN", "D", "EH", "EI" entran al universo CE (línea 188-189). Si "FT"/"FF" existen en Oracle, el parte terminaría como huérfano "Sin Orden Asociada". **Requiere verificar valores reales de `ORD_RESULTADO` en Oracle.** |

---

## Tabla Consolidada de Hallazgos

| ID | Archivo:Línea | Descripción | Severidad |
|----|--------------|-------------|-----------|
| C-1 | `etapa3_core.py:541` / `config.py:48` | `RESCATE_DIAS_TOLERANCIA=7` nunca usado — cruce_C opera a 15 días | 🔴 CRÍTICO |
| C-2 | `etapa3_core.py:829-835` | Left join con dim_traza sin validación → `ID_TRAZA=<NA>` silencioso | 🔴 CRÍTICO |
| C-3 | `config.py:70-79` / `etapa3_core.py:808` | `TRAZAS_RECHAZO` dead code con semántica incorrecta para 2 trazas | 🔴 CRÍTICO |
| W-1 | `etapa3_core.py:103-111, 231` | Fechas sentinel doble → NaT → parte rechazado como huérfano sin log | 🟡 ADVERTENCIA |
| W-2 | `etapa3_core.py:65-68` | Tie-breaker `NUMERO_ORDEN` condicional — no-determinismo si columna ausente | 🟡 ADVERTENCIA |
| W-3 | `etapa4_control_obs.py:153` | `.notna()` no detecta whitespace-only → Hamming incorrecto | 🟡 ADVERTENCIA |
| W-4 | `etapa3_core.py:636-641` | Regla "Otro Origen" sobreescribe trazas válidas sin log | 🟡 ADVERTENCIA |
| W-5 | `config.py:55` | `OVERLAP_WARNING_THRESHOLD` definido pero feature no implementada | 🟡 ADVERTENCIA |
| S-1 | `etapa3_core.py:57` | `df_join.copy()` innecesario en hot path — doble uso de RAM | 🟢 SUGERENCIA |
| S-2 | `etapa3_core.py:732` | `_expandir_mc_ambas` re-ejecutada por run sin caching | 🟢 SUGERENCIA |
| S-3 | `config.py:70-79` | `TRAZAS_RECHAZO` debería eliminarse o corregirse | 🟢 SUGERENCIA |

---

## Próximos Pasos Recomendados (en orden de prioridad)

1. **C-1 (Fix urgente):** Agregar parámetro `tolerancia` a `rank_one_by_dias` y pasarle `config.RESCATE_DIAS_TOLERANCIA` desde `cruce_C`. Validar con test unitario que partes a 10 días sean aceptados en cruce_A pero rechazados en cruce_C.

2. **C-2 (Fix defensivo):** Post-merge con `dim_traza`, agregar `raise ValueError` con las trazas faltantes. Previene FK silenciosamente rota.

3. **C-3 (Limpieza):** Eliminar `TRAZAS_RECHAZO` o corregirla para reflejar exactamente qué trazas dan `ID_ESTADO=3`. Usarla en `normalizar_a_fact_schema` en vez del `default=3` implícito.

4. **W-3 (Fix preventivo):** En `_normalizar_obs`, normalizar strings whitespace-only a `pd.NA` antes de `.notna()`.

5. **W-5 (Feature pendiente):** Implementar el check de antiduplicidad histórica (Traza 18) antes de que el sistema reciba lotes duplicados en producción.

---

*Entregable generado en modo auditoría estática (solo lectura). El código fuente no fue modificado.*
