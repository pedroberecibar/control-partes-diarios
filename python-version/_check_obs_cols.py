"""Verifica el nuevo SQL del pivot y la función de limpieza antes de re-seedear."""
import sys
sys.path.insert(0, '.')

from src.oracle_io import OracleReadOnly
from src.etapa0_seeds import _SQL_PIVOT_APP_MOVIL
import pandas as pd

print("Ejecutando nuevo pivot SQL (puede tardar ~60s)...")
with OracleReadOnly() as ora:
    df = ora.read_sql(_SQL_PIVOT_APP_MOVIL)

print(f"Shape: {df.shape}")
print(f"Cols: {list(df.columns)}")

# Verificar imágenes
for col in ['IMAGEN_1', 'IMAGEN_2']:
    if col not in df.columns:
        print(f"FALTA columna {col}!")
        continue
    total = df[col].notna().sum()
    sample = df[col].dropna().head(3).tolist()
    print(f"\n{col}: {total} no-nulos")
    for v in sample:
        print(f"  {repr(str(v)[:120])}")

# Probar _limpiar_url_firebase sobre las imágenes
from src.etapa4_control_obs import _limpiar_url_firebase
if 'IMAGEN_1' in df.columns:
    cleaned = _limpiar_url_firebase(df['IMAGEN_1'])
    valid = cleaned.notna().sum()
    firebase_count = cleaned.str.startswith("https://").sum()
    local_count = cleaned.str.startswith("/").sum()
    print(f"\nTras _limpiar_url_firebase:")
    print(f"  Válidas: {valid}  (Firebase: {firebase_count}, ruta local: {local_count})")
    print(f"  Muestra:")
    for v in cleaned.dropna().head(3):
        print(f"  {repr(str(v)[:120])}")
