import os
import io

path = r'd:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\src\etapa3_core.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_def = '''def ejecutar_core_para_contratista(
    contratista: str,
    mapa_archivos: dict[str, int],
    df_dim_traza: pd.DataFrame,
) -> tuple[pd.DataFrame | None, dict | None]:'''

new_def = '''def ejecutar_core_para_contratista(
    contratista: str,
    mapa_archivos: dict[str, int],
    df_dim_traza: pd.DataFrame,
    df_pd_input: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame | None, dict | None]:'''

content = content.replace(old_def, new_def)

old_read = '''    tabla_input = f"pd_{contratista.lower()}_aux"
    if not io.table_exists(tabla_input, capa="stage"):
        log.warning("Tabla %s no existe. Saltando.", tabla_input)
        return None, None

    df_pd = io.read_table(tabla_input, capa="stage")
    if df_pd.empty:
        log.warning("Tabla %s vacía. Saltando.", tabla_input)
        return None, None'''

new_read = '''    if df_pd_input is not None:
        df_pd = df_pd_input.copy()
    else:
        tabla_input = f"pd_{contratista.lower()}_aux"
        if not io.table_exists(tabla_input, capa="stage"):
            log.warning("Tabla %s no existe. Saltando.", tabla_input)
            return None, None

        df_pd = io.read_table(tabla_input, capa="stage")
        
    if df_pd.empty:
        log.warning("DataFrame de entrada vacío para %s. Saltando.", contratista)
        return None, None'''

content = content.replace(old_read, new_read)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Etapa 3 Refactor OK')
