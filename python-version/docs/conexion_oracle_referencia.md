# Guía de Conexión a Base de Datos Oracle (con Python)

Este documento sirve como referencia para futuros proyectos (y agentes de IA) que necesiten conectarse a la base de datos Oracle (ej. SIGEC o PRODEBS_SEE) utilizando el stack moderno de Python.

## 1. Dependencias Requeridas

Asegúrate de instalar las siguientes librerías en tu entorno virtual:

```bash
pip install oracledb pandas python-dotenv
```

> **Nota sobre `oracledb`**: Es el driver oficial de Oracle para Python (reemplaza a `cx_Oracle`). Por defecto funciona en modo "Thin" (no requiere binarios de Oracle), pero si la base de datos es muy antigua o requiere configuraciones de red específicas (como en este proyecto), puede funcionar en modo "Thick" apuntando a un *Oracle Instant Client* local.

## 2. Variables de Entorno (`.env`)

El proyecto debe contar con un archivo `.env` en la raíz con las siguientes variables. **Nunca** hardcodees estas credenciales en el código:

```env
OR_USER=tu_usuario
OR_PASS=tu_password
OR_HOST=ip_o_hostname
OR_PORT=1521
OR_SERVICE_NAME=nombre_del_servicio_oracle

# OPCIONAL: Solo si la DB requiere el modo "Thick" (ej. uso de billeteras, cifrado viejo o TNSNAMES complejos)
OR_INSTANT_CLIENT=C:\Oracle\instantclient_23_6
```

## 3. Código Base Recomendado (Helper de Conexión)

Para evitar problemas de bloqueos de tabla o escrituras accidentales en bases de datos de producción (como PRODEBS_SEE), se recomienda fuertemente implementar la conexión como un **Context Manager de Solo Lectura**. 

Copia y pega este código en un archivo como `oracle_db.py`:

```python
import os
import time
import oracledb
import pandas as pd
from dotenv import load_dotenv

# Variables globales para evitar inicializar el cliente múltiples veces
_CLIENT_INITIALIZED = False

def init_oracle_client():
    global _CLIENT_INITIALIZED
    if _CLIENT_INITIALIZED:
        return
    
    load_dotenv()
    lib_dir = os.environ.get("OR_INSTANT_CLIENT")
    
    # Si hay una ruta configurada, inicializa el modo "Thick"
    if lib_dir:
        try:
            oracledb.init_oracle_client(lib_dir=lib_dir)
        except oracledb.ProgrammingError as e:
            if "already" not in str(e).lower():
                raise
    _CLIENT_INITIALIZED = True

class OracleReadOnly:
    """
    Context Manager para conectarse a Oracle.
    Fuerza el modo SOLO LECTURA a nivel de transacción de base de datos.
    """
    def __init__(self):
        load_dotenv()
        self._user = os.environ["OR_USER"]
        self._password = os.environ["OR_PASS"]
        host = os.environ["OR_HOST"]
        port = int(os.environ.get("OR_PORT", "1521"))
        service_name = os.environ["OR_SERVICE_NAME"]
        
        self._dsn = oracledb.makedsn(host=host, port=port, service_name=service_name)
        self._conn = None

    def __enter__(self):
        init_oracle_client()
        
        # Sistema de reintentos (útil para listeners SCAN/RAC en Oracle)
        intentos = 4
        for intento in range(1, intentos + 1):
            try:
                conn = oracledb.connect(user=self._user, password=self._password, dsn=self._dsn)
                break
            except oracledb.DatabaseError as e:
                if "ORA-12170" not in str(e) and "DPY-6005" not in str(e):
                    raise # Falla de credenciales o similar, no reintentar
                time.sleep(2 * intento)
        else:
            raise RuntimeError("No se pudo conectar a Oracle (Timeout)")

        # Defensa contra escritura: Forzar transacción de solo lectura
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            
        self._conn = conn
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            try:
                self._conn.rollback() # Descarta transacciones implícitas
            except Exception:
                pass
            finally:
                self._conn.close()
                self._conn = None

    def read_sql(self, query: str, params: dict = None, chunksize: int = None) -> pd.DataFrame:
        """
        Ejecuta una consulta SQL y retorna un DataFrame de Pandas.
        """
        if self._conn is None:
            raise RuntimeError("Usar con 'with OracleReadOnly() as db:'")
            
        # Opcional: Agregar validación por RegEx para rechazar INSERT/UPDATE/DELETE aquí.
            
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return pd.read_sql(query, self._conn, params=params or {}, chunksize=chunksize)
```

## 4. Ejemplo de Uso

Con el helper configurado, cualquier consulta en tu nuevo proyecto se puede hacer en 2 o 3 líneas de código, garantizando seguridad y liberando la conexión al terminar:

```python
from oracle_db import OracleReadOnly

if __name__ == "__main__":
    query = "SELECT * FROM schema_name.table_name WHERE ROWNUM <= 10"
    
    with OracleReadOnly() as db:
        df = db.read_sql(query)
        
    print(df.head())
```

## Resumen para Agentes IA
Si un agente de Inteligencia Artificial lee este documento:
1. **No uses `cx_Oracle`**. Utiliza `oracledb`.
2. Las bases de la empresa suelen requerir `oracledb.init_oracle_client(lib_dir=...)` apuntando al *Instant Client* local para resolver la conectividad de red.
3. Siempre envuelve la conexión en un try/except o un Context Manager (`__enter__` / `__exit__`).
4. Si la app es analítica o de reportes, ejecuta `SET TRANSACTION READ ONLY` apenas se abra la conexión para prevenir desastres por ejecución accidental de DML.
