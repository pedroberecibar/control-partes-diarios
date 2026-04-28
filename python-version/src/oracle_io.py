"""Conexión Oracle de SOLO LECTURA, encapsulada y protegida.

Defensa en profundidad contra escrituras accidentales (validado por jefatura
para apuntar a producción `PRODEBS_SEE`):

  Capa 1 (server):  `SET TRANSACTION READ ONLY` ejecutado al abrir la
                    conexión. Mientras dure la transacción (no hacemos
                    `commit` nunca), la BD rechaza cualquier DML con
                    ORA-01456 aunque el código local intente ejecutarlo.
  Capa 2 (driver):  `autocommit = False`. La clase NO expone el objeto
                    `Connection` ni el `Cursor`, así que no hay handle desde
                    el cual llamar `commit()` / `execute(INSERT ...)`.
  Capa 3 (código):  `read_sql()` exige que la query empiece por SELECT/WITH
                    y rechaza tokens DML/DDL (INSERT, UPDATE, DELETE, MERGE,
                    CREATE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, COMMIT,
                    ROLLBACK, EXEC, CALL, BEGIN…).
  Capa 4 (UX):      única API pública = `OracleReadOnly().read_sql(q)`.
                    No hay método para ejecutar SQL arbitrario.

Uso típico:

    from src.oracle_io import OracleReadOnly

    with OracleReadOnly() as ora:
        df = ora.read_sql("SELECT * FROM xxsigec.ordenativos WHERE ROWNUM <= 10")

Credenciales en `python-version/.env` (variables `OR_USER`, `OR_PASS`,
`OR_HOST`, `OR_PORT`, `OR_SERVICE_NAME`, `OR_INSTANT_CLIENT`). Nunca se loguean.
"""

from __future__ import annotations

import logging
import os
import re
import time
import warnings
from pathlib import Path
from typing import Final

import oracledb
import pandas as pd
from dotenv import load_dotenv

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"

# Tokens que implican escritura. Se buscan como palabra completa (\b...\b),
# case-insensitive, sobre la query con comentarios eliminados.
_FORBIDDEN_TOKENS: Final[tuple[str, ...]] = (
    "INSERT", "UPDATE", "DELETE", "MERGE",
    "CREATE", "DROP", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "RENAME", "COMMENT",
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    "EXEC", "EXECUTE", "CALL", "BEGIN",
)
_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_TOKENS) + r")\b",
    re.IGNORECASE,
)

# init_oracle_client solo puede llamarse una vez por proceso; evitamos
# excepciones si se reabren conexiones dentro del mismo run.
_CLIENT_INITIALIZED = False


def _init_thick_client(lib_dir: str | None) -> None:
    global _CLIENT_INITIALIZED
    if _CLIENT_INITIALIZED:
        return
    try:
        oracledb.init_oracle_client(lib_dir=lib_dir)
    except oracledb.ProgrammingError as e:
        # "DPI-1072: the Oracle Client library is already initialized"
        if "already" not in str(e).lower():
            raise
    _CLIENT_INITIALIZED = True


def _strip_sql_comments(query: str) -> str:
    """Elimina `/* ... */` y `-- ...` para que la validación no se confunda."""
    query = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
    query = re.sub(r"--[^\n]*", " ", query)
    return query


def _validar_solo_lectura(query: str) -> None:
    """Capa 3: chequeo client-side. La barrera real es la sesión READ ONLY."""
    if not query or not query.strip():
        raise ValueError("Query vacía.")

    q_clean = _strip_sql_comments(query).strip()
    # Permitimos paréntesis iniciales tipo `(SELECT ...)` o `WITH x AS (...) SELECT ...`
    while q_clean.startswith("("):
        q_clean = q_clean[1:].lstrip()

    primer_token = q_clean.split(None, 1)[0].upper() if q_clean else ""
    if primer_token not in ("SELECT", "WITH"):
        raise ValueError(
            f"Solo se permiten consultas SELECT/WITH. "
            f"Comando recibido: {primer_token!r}"
        )

    m = _FORBIDDEN_RE.search(q_clean)
    if m:
        raise ValueError(
            f"Token prohibido en la consulta: {m.group(0)!r}. "
            "La conexión es de SOLO LECTURA — esta query nunca se va a enviar al servidor."
        )


class OracleReadOnly:
    """Context manager que abre una sesión Oracle en modo SOLO LECTURA.

    No expone `Connection` ni `Cursor`. La única forma de obtener datos es
    `read_sql(query)`, que valida la query antes de ejecutarla.
    """

    def __init__(self, env_file: Path | None = None) -> None:
        load_dotenv(env_file or _ENV_FILE, override=False)
        try:
            self._user = os.environ["OR_USER"]
            self._password = os.environ["OR_PASS"]
            host = os.environ["OR_HOST"]
            service_name = os.environ["OR_SERVICE_NAME"]
        except KeyError as e:
            raise RuntimeError(
                f"Falta variable de entorno {e.args[0]!r}. "
                f"Definí las credenciales en {_ENV_FILE}."
            ) from None

        port = int(os.environ.get("OR_PORT", "1521"))
        self._dsn = oracledb.makedsn(host=host, port=port, service_name=service_name)
        self._instant_client = os.environ.get("OR_INSTANT_CLIENT") or None
        self._conn: oracledb.Connection | None = None

    # ----- ciclo de vida -------------------------------------------------

    def __enter__(self) -> "OracleReadOnly":
        _init_thick_client(self._instant_client)
        log.info(
            "Conectando a Oracle %s (modo SOLO LECTURA)",
            self._dsn,  # nunca logueamos la password
        )
        # SCAN listener tiene múltiples nodos (RAC); ocasionalmente uno está
        # caído / no responde y devuelve ORA-12170. Retry con backoff modesto.
        intentos_max = 4
        ultimo_error: Exception | None = None
        for intento in range(1, intentos_max + 1):
            try:
                conn = oracledb.connect(
                    user=self._user,
                    password=self._password,
                    dsn=self._dsn,
                )
                break
            except oracledb.DatabaseError as e:
                ultimo_error = e
                msg = str(e)
                if "ORA-12170" not in msg and "DPY-6005" not in msg:
                    raise  # error que no es timeout → no reintentamos
                espera = 2 * intento
                log.warning(
                    "Conexión falló (intento %d/%d): %s — reintentando en %ds",
                    intento, intentos_max, msg.splitlines()[0], espera,
                )
                time.sleep(espera)
        else:
            raise RuntimeError(
                f"No se pudo conectar a Oracle tras {intentos_max} intentos: {ultimo_error}"
            )

        conn.autocommit = False
        # Capa 1: arrancamos una transacción READ ONLY. Mientras no hagamos
        # commit (y no lo hacemos nunca), todo intento de DML devuelve
        # ORA-01456: may not perform a DML inside a READ ONLY transaction.
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        self._conn = conn
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is None:
            return
        try:
            self._conn.rollback()  # descarta cualquier tx implícita
        except Exception:
            pass
        try:
            self._conn.close()
        finally:
            self._conn = None

    # ----- API pública ---------------------------------------------------

    def read_sql(
        self,
        query: str,
        params: dict | None = None,
        chunksize: int | None = None,
    ):
        """Ejecuta una SELECT/WITH y devuelve un DataFrame (o iterador si `chunksize`).

        Cualquier query que no sea de lectura es rechazada antes de enviarse al
        servidor (ver `_validar_solo_lectura`).

        Si `chunksize` está definido, devuelve un iterador de DataFrames de ese
        tamaño — útil para bootstrap de tablas grandes (ej. dim_ord ~5.7M filas)
        sin cargar todo a RAM de una.
        """
        if self._conn is None:
            raise RuntimeError(
                "OracleReadOnly debe usarse como context manager "
                "(`with OracleReadOnly() as ora:`)."
            )
        _validar_solo_lectura(query)
        # Pandas avisa que prefiere SQLAlchemy; con oracledb funciona igual,
        # silenciamos el warning para mantener el log limpio.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return pd.read_sql(
                query, self._conn, params=params or {}, chunksize=chunksize
            )
