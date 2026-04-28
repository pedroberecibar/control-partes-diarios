"""Rutas, capas y constantes globales del pipeline local.

Portado desde los scripts de Fabric — los valores aquí deben coincidir 1:1
con los del original. Cualquier cambio de constante aquí afecta el pipeline
completo, así que esta es la única fuente de verdad.
"""

from __future__ import annotations

from pathlib import Path

# =============================================================================
# Rutas base
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

CAPAS: dict[str, Path] = {
    "input":  DATA / "input",
    "seed":   DATA / "seed",
    "stage":  DATA / "stage",
    "master": DATA / "master",
    "dim":    DATA / "dim",
    "gold":   DATA / "gold",
    "logs":   DATA / "logs",
}

INPUT_MAESTROS = CAPAS["input"] / "maestros"
INPUT_CONECTAR = CAPAS["input"] / "conectar"
INPUT_COOPLYF  = CAPAS["input"] / "cooplyf"

FILE_MAPEO = INPUT_MAESTROS / "conversion_codigos_contratista_a_PD_PBI (1).xlsx"
HOJA_MAPEO = "tabla master"
FILE_USES  = INPUT_MAESTROS / "OP_MI (1).xlsx"
HOJA_USES  = "Hoja2"

# =============================================================================
# Parámetros de negocio (portados del Core v27.3)
# =============================================================================

LISTA_CONTRATISTAS = ["CONECTAR", "COOPLYF"]
DIAS_TOLERANCIA    = 15
VALOR_USES_COD_11  = 0.0100

# Trazas — única fuente de verdad (mover de ajuste aquí se propaga al pipeline)
TRAZAS_OK = [
    "Original OK",
    "Corregido Nro EQP Invertidos",
    "Corregido Nro Medidor",
    "Corregido Sumi",
    "Corregido Medidor Vacio",
]
TRAZAS_OCR = [
    "Corregido Sumi Nro EQP",
]
TRAZAS_RECHAZO = [
    "No Corresponde TOR CE",
    "Sin Orden Asociada",
    "Error Sumi Sin Nro Medidor",
    "Error Sumi Y Nro Medidor",
    "Informados con ORD-SUMI aprobado",
    "Informado - No Ejecutado",
    "Otro Origen",
]
TRAZAS_DESCARTE_TECNICO = [
    "No Corresponde TOR CE",
    "Sin Orden Asociada",
    "Error Sumi Sin Nro Medidor",
    "Error Sumi Y Nro Medidor",
    "Otro Origen",
]
TRAZAS_CORRECCION_MEDIDOR = [
    "Corregido Nro EQP Invertidos",
    "Corregido Nro Medidor",
    "Corregido Sumi Nro EQP",
    "Corregido Medidor Vacio",
]

# Schema canónico de la fact table — orden exacto
COLS_FACT = [
    "ID_EXTERNO", "FECHA", "ESTADO_PROCESO", "ID_ARCHIVO",
    "SRV_CODIGO", "SUMINISTRO_RAW", "NRO_EQP_COLOCADO", "NRO_EQP_RETIRADO",
    "CODIGO_CONTRATISTA", "CODIGO_EPEC", "ORD_NRO", "ORD_FECHA_FIN", "es_pagable",
    "ID_EMPRESA", "ID_ESTADO", "TIMESTAMP_ETL", "SEC_CODIGO_ORIGEN",
    "USR_ID", "ID_TRAZA", "ID_PARTE_HASH", "FUE_CORREGIDO", "ORD_TIPO_DETECTADO",
]

# Columnas de observación — pares (nombre en app movil, nombre en tabla de reglas)
# El orden importa: el Hamming se calcula columna-a-columna en este orden.
OBS_COLS: list[tuple[str, str]] = [
    ("'APP4SITIO_3'", "GABINETE"),
    ("'APP4SITIO_4'", "SUBTERRANEO"),
    ("'APP4SITIO_2'", "ALTURA"),
    ("'APP4SITIO_1'", "AEREO"),
    ("'APP4TRAB_1'",  "EQUIPO_MEDICION_REEMPLAZADO"),
    ("'APP4TRAB_2'",  "ACOMETIDA_REALIZADA"),
    ("'APP4TRAB_3'",  "TAPA_REEMPLAZADA"),
    ("'APP4TRAB_4'",  "EQUIPO_DE_MEDICION_INSTALADO"),
]


def ensure_layout() -> None:
    """Crea las carpetas base si no existen. Idempotente."""
    for p in CAPAS.values():
        p.mkdir(parents=True, exist_ok=True)
    INPUT_MAESTROS.mkdir(parents=True, exist_ok=True)
    INPUT_CONECTAR.mkdir(parents=True, exist_ok=True)
    INPUT_COOPLYF.mkdir(parents=True, exist_ok=True)
