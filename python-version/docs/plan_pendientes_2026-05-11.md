# Plan — Pendientes web app (2026-05-11)

## Context
Hay ~3 jornadas de trabajo sin commitear (05-07 y 05-08). Los 5 fallos en `test_kpis_core` son por un Parquet stale (`control_obs_app`) — no es una regresión lógica. Las tareas se ejecutan en orden de dependencia/riesgo.

---

## Tarea 1 — Regenerar `control_obs_app` y snapshots (5 tests failing)

**Causa raíz:** `control_obs_app` Parquet fue generado antes de que la regla `IN` se agregara a Etapa 3. La fact table ahora tiene 40 519 aprobados pero el Parquet tiene 22 483 → `TestIntegridad::test_control_obs_equals_aprobados` falla.

**Pasos:**
1. `cd python-version && python run_pipeline.py --solo-etapa 4`
2. `pytest tests/test_kpis_core.py::TestIntegridad::test_control_obs_equals_aprobados -v`
   - Si pasa (totales iguales): continuar al paso 3
   - Si sigue fallando: investigar con `print(len(df_base))` en `_cargar_base` — posible fan-out residual o diferencia en filtro Aprobado
3. `pytest tests/test_kpis_core.py -v --update-snapshot` — regenera `kpis_obs_snapshot.json`
4. `pytest tests/ -q --tb=short` — confirmar 101/101 verdes

**Archivos afectados:** solo Parquet en `data/gold/control_obs_app.parquet` y `tests/fixtures/kpis_obs_snapshot.json` (autogenerado).

---

## Tarea 2 — Commit del trabajo acumulado

28 archivos nuevos + 28 modificados de jornadas 05-07 y 05-08. Hacer 2 commits para mantener granularidad histórica.

**Commit 1 — jornada 05-07 (Oracle sync + rescate + admin):**
```
feat: oracle sync, rescate huerfanos y admin codigos EPEC

- CRUD reglas/mapeos cod_epec (admin.py, reglas_service.py)
- Auth basica require_admin (api/core/auth.py)
- Sync Oracle SIGEC → SQLite (oracle_sync_service.py)
- Rescate de huerfanos contra DB local (rescate_ordenativos_service.py)
- Auto-rescate batch en worker (trazas 19/20)
- Alembic migration antiduplicidad + progreso
- 51 tests nuevos verdes
```

**Commit 2 — jornada 05-08 (Hamming + sugerencias EPEC):**
```
feat: sugerencias cod_epec por Hamming en DetallePartes

- src/hamming.py: helper compartido motor batch / API
- SugerenciasService: match exacto + top 3 cercanos + lista plana
- sugerencias_schemas.py, endpoints en partes.py y admin.py
- DetallePartes.jsx: tarjetas candidatos, dropdown con preview Hamming, modal confirmacion
- 13 tests nuevos verdes (test_hamming_helper, test_sugerencias_service)
```

---

## Tarea 3 — UI desambiguación ID_TRAZA==20

**Contexto:** partes con `id_traza=20` ("Múltiples Candidatos Oracle") ya tienen sus candidatos en la DB local. El botón "Buscar candidatos" y el flujo de "Asociar" ya funcionan. Solo falta auto-cargar al abrir el parte y mostrar un aviso al auditor.

**Archivo:** `frontend-app/src/pages/DetallePartes.jsx`

### Cambio A — Auto-load candidatos al montar
```jsx
useEffect(() => {
  if (!p || typeof p.id !== 'number') return;
  if (p.id_traza !== 20) return;
  handleConsultarOracle();
}, [p?.id, p?.id_traza]);
```

### Cambio B — Banner ámbar en sección "Ordenativos CE Candidatos"
```jsx
{p.id_traza === 20 && (
  <div style={{ margin: '0 0 10px', padding: '10px 12px', background: '#fff3cd', border: '1px solid #f0d080', borderRadius: 4, fontSize: 12, color: '#7a4a00', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
    <Icon name="alert-circle" size={14} color="#e6910a" />
    <span>
      <strong>Requiere desambiguación.</strong> Este parte fue clasificado con múltiples ordenativos candidatos. Revisá la lista y asociá el correcto para resolverlo.
    </span>
  </div>
)}
```

**Sin cambios en backend.**

---

## Tarea 4 (Opcional) — Recalcular valor_uses_origen + métricas al cambiar cod_epec

**Archivos:** `api/services/parte_service.py`, `api/services/reglas_service.py`

Después del bloque de reclasificación automática en `editar_parte()`:

```python
if "cod_epec" in cambios_realizados and parte.cod_epec is not None:
    uses_nuevo = ReglaService(self.db).valor_uses_para_cod(parte.cod_epec)
    if uses_nuevo is not None:
        parte.valor_uses_origen = uses_nuevo
        v_obs = parte.valor_uses_obs or 0.0
        diff = round(uses_nuevo - v_obs, 4)
        parte.diferencia_uses = diff
        parte.tipo_discrepancia = _calcular_tipo_discrepancia(parte, uses_nuevo, v_obs, diff)
```

Nuevo método en `ReglaService.valor_uses_para_cod(cod_epec)` y helper `_calcular_tipo_discrepancia()` con misma lógica que `np.select` de Etapa 4 (pure Python if/elif).

---

## Tarea 5 (Opcional) — Índice en OrdenativoOracleEquipo.ste_numero

```bash
alembic revision --autogenerate -m "ix_ordenativo_equipo_ste_numero"
# o manualmente:
op.create_index('ix_ordenativo_equipo_ste_numero', 'ordenativos_oracle_equipo', ['ste_numero'])
```

---

## Verificación final

```bash
pytest tests/ -q   # 101 passed
```

Validación visual: parte con `id_traza=20` debe mostrar banner ámbar y candidatos cargados automáticamente.
