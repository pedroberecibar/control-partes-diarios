import pandas as pd
import oracledb
from pathlib import Path
from pandas_gbq import to_gbq
 
oracledb.init_oracle_client(lib_dir=r"C:\Oracle\instantclient_23_6")
 
conn = oracledb.connect(
    user="smunge",
    password="smunge2024",
    host="epec2-scan2",
    port=1521,
    service_name="PRODEBS_SEE"
)

---------------------------------------------------------------------

import pandas as pd
import oracledb
from pathlib import Path
from pandas_gbq import to_gbq
 
oracledb.init_oracle_client(lib_dir=r"C:\Oracle\instantclient_23_6")
 
conn = oracledb.connect(
    user="smunge",
    password="smunge2024",
    host="epec2-scan2",
    port=1521,
    service_name="PRODEBS_SEE"
)
 
# -------- tabla 1: perfiles ----------
query_perfiles = Path("consultaNico.sql").read_text(encoding="utf-8").strip()
df_perfiles = pd.read_sql(query_perfiles, conn)
 
to_gbq(
    df_perfiles,
    destination_table="demanda_mov_electrica.perfiles_mov_electrica",
    project_id="bigquery-marcos",
    if_exists="replace"
)
 
print("Tabla perfiles_mov_electrica subida.")
 
# -------- tabla 2: clientes / medidores ----------
query_clientes = Path("consultaClientes.sql").read_text(encoding="utf-8").strip()
df_clientes = pd.read_sql(query_clientes, conn)
 
to_gbq(
    df_clientes,
    destination_table="demanda_mov_electrica.clientes_medidores",
    project_id="bigquery-marcos",
    if_exists="replace"
)
 
print("Tabla clientes_medidores subida.")
 
conn.close()
print("Proceso terminado.")

