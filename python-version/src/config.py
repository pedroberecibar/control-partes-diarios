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

# Auto-rescate vía DB local sincronizada desde Oracle SIGEC (CE + PROTELEM).
# Ventana de tolerancia para considerar un candidato como "match cercano":
RESCATE_DIAS_TOLERANCIA          = 7
# Fecha de corte del bootstrap del sync. Formato DD/MM/YYYY para coincidir con TO_DATE de la query Oracle.
RESCATE_FECHA_INICIO_BOOTSTRAP   = "31/05/2025"

# Antiduplicidad — Capa 3 (warning blando por overlap de partes).
# Si la fracción de partes del nuevo lote que ya existen en lotes previos
# supera este umbral, el endpoint devuelve 409 OVERLAP_WARN y exige `force=true`.
OVERLAP_WARNING_THRESHOLD        = 0.5

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
    "Fecha Inválida",
    "Código de Tarea No Mapeado",
]
TRAZAS_DESCARTE_TECNICO = [
    "No Corresponde TOR CE",
    "Sin Orden Asociada",
    "Error Sumi Sin Nro Medidor",
    "Error Sumi Y Nro Medidor",
    "Otro Origen",
    "Fecha Inválida",
    "Código de Tarea No Mapeado",
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
    ("GABINETE",                     "GABINETE"),
    ("SUBTERRANEO",                  "SUBTERRANEO"),
    ("ALTURA",                       "ALTURA"),
    ("AEREO",                        "AEREO"),
    ("EQUIPO_MEDICION_REEMPLAZADO",  "EQUIPO_MEDICION_REEMPLAZADO"),
    ("ACOMETIDA_REALIZADA",          "ACOMETIDA_REALIZADA"),
    ("TAPA_REEMPLAZADA",             "TAPA_REEMPLAZADA"),
    ("EQUIPO_DE_MEDICION_INSTALADO", "EQUIPO_DE_MEDICION_INSTALADO"),
]


def ensure_layout() -> None:
    """Crea las carpetas base si no existen. Idempotente."""
    for p in CAPAS.values():
        p.mkdir(parents=True, exist_ok=True)
    INPUT_MAESTROS.mkdir(parents=True, exist_ok=True)
    INPUT_CONECTAR.mkdir(parents=True, exist_ok=True)
    INPUT_COOPLYF.mkdir(parents=True, exist_ok=True)
