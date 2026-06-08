import logging
import pandas as pd


def _parse_precio_arg(s):
    """Parsea precios en formato argentino: '$749,5', '"$9335,6643"', '$18000'."""
    s = str(s).strip().strip('"').replace('$', '').strip()
    if not s or s.lower() in ('nan', ''):
        return None
    tiene_punto = '.' in s
    tiene_coma  = ',' in s
    if tiene_punto and tiene_coma:
        if s.rfind(',') > s.rfind('.'):   # coma = decimal, punto = miles
            s = s.replace('.', '').replace(',', '.')
        else:                              # punto = decimal, coma = miles
            s = s.replace(',', '')
    elif tiene_coma:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def procesar_precios_pbi(df):
    """
    Espera columnas: articulo, fecha_recepcion, costo_unitario.
    Devuelve (df_procesado, None) o (None, columnas) si faltan columnas.
    """
    required = {"articulo", "fecha_recepcion", "costo_unitario"}
    cols = set(df.columns.str.strip().str.lower())
    if not required.issubset(cols):
        return None, list(df.columns)

    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    result = pd.DataFrame()
    result["codigo"]          = df["articulo"].astype(str).str.strip()
    result["precio_unitario"] = df["costo_unitario"].apply(_parse_precio_arg)
    result["fecha_ultima_oc"] = pd.to_datetime(
        df["fecha_recepcion"], dayfirst=True, errors="coerce"
    )
    nat_count = result["fecha_ultima_oc"].isna().sum()
    if nat_count > 0:
        logging.warning(
            "precios: %d/%d fechas en 'fecha_recepcion' no pudieron parsearse (quedaron NaT). "
            "Verificá el formato del archivo de precios.",
            nat_count, len(result),
        )
    result = result[result["precio_unitario"].notna() & (result["precio_unitario"] > 0)].copy()
    # na_position="first" → NaT queda antes que las fechas válidas; keep="last" toma
    # la fila más reciente, garantizando que precio y fecha vengan del mismo registro.
    result = result.sort_values("fecha_ultima_oc", ascending=True, na_position="first")
    result = result.drop_duplicates(subset=["codigo"], keep="last")
    return result[["codigo", "precio_unitario", "fecha_ultima_oc"]], None
