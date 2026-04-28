# Pipeline Partes Diarios — Versión Local (Python/Pandas)

Migración del pipeline de procesamiento de Partes Diarios desde PySpark/Fabric hacia
Python local con Pandas. Produce las mismas tablas (fact + dimensiones + control de
observaciones) que la versión Fabric, validadas contra Power BI.

## Requisitos

- Python 3.12+
- Dependencias: `pip install -r requirements.txt`
- Oracle Instant Client (solo para refrescar seeds desde SIGEC/GEOREF)
- Archivo `.env` con credenciales Oracle (ver `.env.example`)

## Estructura del proyecto

```
python-version/
├── run_pipeline.py          # Orquestador principal (CLI)
├── src/
│   ├── config.py            # Constantes, rutas, parámetros de negocio
│   ├── io_lakehouse.py      # Capa IO (Parquet con escritura atómica)
│   ├── oracle_io.py         # Conexión Oracle (read-only, 4 capas de protección)
│   ├── hashing.py           # Hashes deterministas (ID_PARTE_HASH)
│   ├── adapters_common.py   # Helpers comunes de adapters
│   ├── etapa0_seeds.py      # Extracción de seeds desde Oracle
│   ├── etapa1_maestros.py   # Maestros (mapeo códigos + reglas obs)
│   ├── etapa2_adapter_*.py  # Adapters CONECTAR y COOPLYF
│   ├── etapa3_core.py       # Core waterfall (cruces A/B/C + dedup)
│   ├── etapa3_dims_bi.py    # Dimensiones BI estáticas
│   ├── etapa3_dims_geo_calendario.py  # dim_suministros_geo + dim_calendario
│   ├── etapa3_panel_kpis.py # Panel de KPIs (validación contra Power BI)
│   └── etapa4_control_obs.py # Control de observaciones + valoración USES
├── scripts/
│   ├── inspect_parte.py     # Helper de debugging (traza individual)
│   └── test_oracle_seeds.py # Test de conectividad Oracle
├── tests/
│   ├── conftest.py
│   └── test_kpis_core.py    # Tests de no-regresión (snapshots)
├── data/                    # Data lake local (Parquet)
│   ├── input/               # Archivos Excel/CSV de entrada
│   ├── seed/                # Seeds desde Oracle (dim_ord, sigec, etc.)
│   ├── stage/               # Staging (partes normalizados)
│   ├── master/              # Maestros (mapeo códigos, reglas obs)
│   ├── dim/                 # Dimensiones (estado, traza, empresa, etc.)
│   └── gold/                # Tablas finales (fact + control_obs)
└── docs/                    # Documentación del proyecto
```

## Uso

### Corrida completa (etapas 1-4)

```bash
python run_pipeline.py
```

### Etapas individuales

```bash
python run_pipeline.py --solo-etapa 1    # Maestros
python run_pipeline.py --solo-etapa 2    # Adapters (leer Excels → staging)
python run_pipeline.py --solo-etapa 3    # Core (waterfall + dims + KPIs)
python run_pipeline.py --solo-etapa 4    # Control de observaciones
```

### Refrescar seeds desde Oracle

```bash
python run_pipeline.py --refrescar-seeds           # Todo incluyendo seeds
python run_pipeline.py --solo-seeds                 # Solo seeds (todas)
python run_pipeline.py --solo-seeds dim_ord         # Solo dim_ord
```

### Reproceso (ignorar bitácora)

```bash
python run_pipeline.py --solo-etapa 2 --reproceso
```

## Herramientas de validación

### Panel de KPIs (comparar contra Power BI)

```bash
python -m src.etapa3_panel_kpis
```

Imprime un panel con los mismos KPIs que la Celda 7 del PySpark original:
totales por estado, efectividad, desglose por traza, USES por contratista,
detalle mensual, etc.

### Control de observaciones

```bash
python -m src.etapa4_control_obs
```

Panel de discrepancias: sobrevaloración, subvaloración, error operativo,
índice de asimetría, impacto económico por tipo.

### Inspeccionar un parte individual

```bash
python scripts/inspect_parte.py --hash <ID_PARTE_HASH>
python scripts/inspect_parte.py --suministro 419389
python scripts/inspect_parte.py --suministro 419389 --fecha 2026-02-12
python scripts/inspect_parte.py --ord-nro 80101830
```

Muestra la traza completa: input crudo → fact → control de observaciones.
Útil cuando un KPI no coincide con Power BI y hay que investigar.

### Tests de no-regresión

```bash
python -m pytest tests/ -v                       # Comparar contra snapshot
python -m pytest tests/ -v --update-snapshot     # Regenerar snapshot
```

20 tests que verifican que los KPIs del Core y Control de Obs no cambien
entre corridas (mismos datos de input → mismos números de salida).

## Flujo del pipeline

```
Etapa 1: Maestros (Excel → Parquet)
    ↓
Etapa 2: Adapters CONECTAR + COOPLYF (Excel → staging normalizado)
    ↓
(Etapa 0: Seeds Oracle → seed/) ← opcional, para actualizar datos SIGEC
    ↓
Etapa 3: Core Waterfall
    3.1-3.2  Dimensiones BI estáticas
    3.3      Cruces A/B/C + ensamblado + dedup → fact_partes_diarios_full
    3.4      dim_suministros_geo + dim_calendario
    3.5      Panel de KPIs
    ↓
Etapa 4: Control de Observaciones
    7 pasos de análisis → control_obs_app + dim_img_app_pd
```

## Invariantes técnicas

Ver [CLAUDE.md](CLAUDE.md) para las reglas técnicas del proyecto:
- Vectorización obligatoria (nunca `df.apply(axis=1)`)
- `mergesort` + tie-breakers para reproducir `Window.orderBy` de Spark
- Merge de la fact solo vía `io.merge_table(key="ID_PARTE_HASH")`
- Schema canónico en `config.COLS_FACT`
