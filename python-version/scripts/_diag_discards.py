"""Script de diagnostico: cuenta exactamente cuantas filas se descartan en cada etapa."""
import sys
import warnings
from pathlib import Path

# Asegurar que el root del proyecto este en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

UPLOADS = Path(__file__).resolve().parents[1] / "data" / "uploads"

COOPLYF_FILE = UPLOADS / "b5a80934b8c5216bf8cac9898ba46c8443cb8035b1a54363cc3b0e0abb62ac2d.xlsx"
CONECTAR_FILE = UPLOADS / "fdc84ed8e3b5d8014a647f6962ee2e6f82b4c0bb252cfeda63466f9c4cf1dcdb.xlsx"

_MAPA_KEYS = {
    "ID", "Id", "id", "Nro", "N°", "Numero", "Nro Parte", "N° Parte",
    "Fecha", "fecha", "FECHA", "Fecha Trabajo", "FechaTrabajo",
    "Suministro", "Suministros", "NIS", "Cuenta",
    "Codigo", "Código", "código", "codigo", "Tarea", "Cod Tarea", "Cod. Tarea",
}

# ─── helpers ───────────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, *candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
        for col in df.columns:
            if col.strip().lower() == c.lower():
                return col
    return None


def diag_cooplyf(path: Path) -> None:
    sep = "=" * 60
    print(sep)
    print(f"COOPLYF  {path.name[:40]}")
    print(sep)

    df = pd.read_excel(path, engine="openpyxl", dtype=str)
    print(f"  Filas brutas del Excel:          {len(df):>6}")

    fecha_col = _find_col(df, "Fecha", "fecha", "FECHA")
    if fecha_col is None:
        print("  AVISO: columna Fecha no encontrada")
        return

    # 1. Filtro Total
    mask_total = df[fecha_col].astype(str).str.contains("Total", case=False, na=False)
    n_total = int(mask_total.sum())
    print(f"  Filas filtradas (Total):         {n_total:>6}  ** DESCARTADAS del todo **")

    df2 = df.loc[~mask_total].copy()
    print(f"  Filas tras filtro Total:         {len(df2):>6}")

    # 2. Parseo de fechas
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fechas = pd.to_datetime(df2[fecha_col], dayfirst=True, errors="coerce")

    n_nat = int(fechas.isna().sum())
    print(f"  Filas con Fecha invalida (NaT):  {n_nat:>6}  -> TRAZA_ADAPTER = Fecha Invalida")
    print(f"  Filas con Fecha valida:          {int((~fechas.isna()).sum()):>6}")

    print()
    # 3. Hash duplicados — necesito correr el adapter real
    from src.etapa2_adapter_cooplyf import procesar_archivo
    df_out, stats = procesar_archivo(path)
    if df_out is not None:
        n_hashes = len(df_out)
        n_dup_hash = n_hashes - df_out["ID_Externo"].nunique()
        print(f"  Output adapter (filas):          {n_hashes:>6}")
        print(f"  ID_Externo duplicados en output: {n_dup_hash:>6}  → hashdup intra-batch")
    print()


def diag_conectar(path: Path) -> None:
    sep = "=" * 60
    print(sep)
    print(f"CONECTAR  {path.name[:40]}")
    print(sep)

    # Detección automática de header (igual que el adapter)
    best_df = None
    best_score = -1
    for h in [2, 0, 1, 3, 4]:
        try:
            df_h = pd.read_excel(path, header=h, dtype=str)
            df_h.columns = df_h.columns.str.strip()
            score = sum(1 for c in df_h.columns if c in _MAPA_KEYS)
            if score > best_score:
                best_score = score
                best_df = df_h
        except Exception:
            continue

    print(f"  Header detectado (score={best_score}), cols: {list(best_df.columns)[:8]}")
    print(f"  Filas brutas del Excel:          {len(best_df):>6}")

    fecha_col = _find_col(best_df, "Fecha", "fecha", "FECHA", "Fecha Trabajo", "FechaTrabajo")
    if fecha_col is None:
        print("  AVISO: columna Fecha no encontrada")
        return

    # 1. Filtro Total|Fecha
    mask_tf = best_df[fecha_col].astype(str).str.contains("Total|Fecha", case=False, na=False)
    n_tf = int(mask_tf.sum())
    print(f"  Filas filtradas (Total|Fecha):   {n_tf:>6}  ** DESCARTADAS del todo **")

    df2 = best_df.loc[~mask_tf].copy()
    print(f"  Filas tras filtro Total|Fecha:   {len(df2):>6}")

    # 2. Parseo de fechas
    fechas = pd.to_datetime(df2[fecha_col], errors="coerce")
    n_nat = int(fechas.isna().sum())
    print(f"  Filas con Fecha invalida (NaT):  {n_nat:>6}  -> TRAZA_ADAPTER = Fecha Invalida")
    print(f"  Filas con Fecha valida:          {int((~fechas.isna()).sum()):>6}")

    print()
    # 3. Correr el adapter real y contar hash dups
    from src.etapa2_adapter_conectar import obtener_codigos_habilitados, procesar_excel
    codigos = obtener_codigos_habilitados()
    df_out, stats = procesar_excel(path, codigos)
    if df_out is not None:
        print(f"  Output adapter (filas):          {len(df_out):>6}")
        traza_counts = df_out["TRAZA_ADAPTER"].value_counts(dropna=False)
        for val, cnt in traza_counts.items():
            label = str(val) if val is not None else "None (valida)"
            print(f"    TRAZA_ADAPTER = {label:<35}: {cnt:>6}")

        from src import hashing
        hashes = hashing.id_parte_hash(
            origen_archivo=df_out["ORIGEN_ARCHIVO"],
            srv_codigo=df_out["Suministro"],
            fecha=pd.to_datetime(df_out["Fecha"], errors="coerce"),
            medidor_colocado=df_out["medidorColocado"],
            cod_tipos_mano_obra=df_out["codTiposManoObra"],
        )
        n_dup_hash = len(hashes) - hashes.nunique()
        print(f"  Hash duplicados intra-batch:     {n_dup_hash:>6}  -> descartados por ImportService")
    print()


if __name__ == "__main__":
    diag_cooplyf(COOPLYF_FILE)
    diag_conectar(CONECTAR_FILE)

    print("=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print("  Excel total reportado:  21974")
    print("  Bandeja actual:         21494")
    print("  Diferencia:               480")
