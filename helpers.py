import math
import calendar
from io import BytesIO
from datetime import date, timedelta

import pandas as pd

from config import MESES, get_hoy


def validar_columnas(df, cols_requeridas, nombre):
    """Lanza ValueError con mensaje descriptivo si faltan columnas requeridas."""
    faltantes = [c for c in cols_requeridas if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"'{nombre}' — columnas faltantes: {faltantes}. "
            f"Columnas encontradas: {list(df.columns)}"
        )


def filtrar_oc_relevantes(oc_df, bom_df, fc_df):
    """Filtra las OC dejando solo insumos demandados por artículos del forecast.
    Devuelve (df_filtrado, n_descartadas). Sin BOM o forecast no filtra."""
    if oc_df is None or bom_df is None or fc_df is None:
        return oc_df, 0
    cols_mes = [c for c in fc_df.columns if c not in ("articulo", "descripcion")]
    if not cols_mes:
        return oc_df, 0
    demanda = fc_df[cols_mes].sum(axis=1)
    arts_dem = set(fc_df.loc[demanda > 0, "articulo"].astype(str).str.strip())
    insumos_rel = set(
        bom_df.loc[bom_df["articulo"].astype(str).str.strip().isin(arts_dem),
                   "codigo_insumo"].astype(str).str.strip())
    mask = oc_df["codigo"].astype(str).str.strip().isin(insumos_rel)
    return oc_df[mask].reset_index(drop=True), int((~mask).sum())


def gsheet_url(sid, fmt="csv"):
    return f"https://docs.google.com/spreadsheets/d/{sid}/export?format={fmt}"


def mes_key(año, mes_0):
    return f"{MESES[mes_0]}_{str(año)[-2:]}"


def semanas_del_mes(año, mes):
    """Sem 1: día 1 → día antes del primer lunes. Sem 2+: lunes→domingo."""
    primer = date(año, mes, 1)
    ultimo = date(año, mes, calendar.monthrange(año, mes)[1])
    semanas = []
    dia = primer
    while dia.weekday() != 0:
        dia += timedelta(days=1)
    primer_lunes = dia
    fin1 = min(primer_lunes - timedelta(days=1) if primer_lunes != primer
               else primer + timedelta(days=6), ultimo)
    semanas.append((f"Sem 1 ({primer.day}/{mes}–{fin1.day}/{mes})", primer, fin1))
    sig = fin1 + timedelta(days=1)
    n = 2
    while sig <= ultimo:
        fin = min(sig + timedelta(days=6), ultimo)
        semanas.append((f"Sem {n} ({sig.day}/{mes}–{fin.day}/{mes})", sig, fin))
        sig = fin + timedelta(days=1)
        n += 1
    return semanas


def semanas_desde_hoy(año, mes):
    todas = semanas_del_mes(año, mes)
    return [(lb, ss, se) for lb, ss, se in todas if se >= get_hoy()]


def distribuir(total, n_sem, pcts):
    total = int(round(total))
    if total == 0 or n_sem == 0:
        return [0] * n_sem
    p = list(pcts[:n_sem])
    # Si hay más semanas que pesos definidos (ej. mes de 6 semanas con dist_5),
    # repetir el último peso para no silenciar la demanda de las semanas extra.
    while len(p) < n_sem:
        p.append(p[-1] if p else 1)
    sp = sum(p)
    vals = [int(round(total * x / sp)) for x in p] if sp else [total // n_sem] * n_sem
    diff = total - sum(vals)
    if diff:
        vals[-1] += diff
    return vals


def ceil_multiplo(val, mult):
    if val <= 0: return 0
    return math.ceil(val / mult) * mult


def semaforo(sems_cub, total_sems, dias_cobertura=0, lead_time=0):
    if sems_cub >= total_sems:      return "🟢", "Cubierto", "ok"
    if dias_cobertura >= lead_time: return "🟡", "Parcial", "warn"
    return "🔴", "Crítico", "crit"


def exportar_excel(df):
    df = df.reset_index(drop=True).fillna("")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="MRP")
        wb = writer.book
        ws = writer.sheets["MRP"]
        fmt_hdr = wb.add_format({"bold":True,"bg_color":"#1f2733","font_color":"#ffffff","border":1})
        fmt_red = wb.add_format({"bg_color":"#fbecea","font_color":"#7a221c"})
        fmt_yel = wb.add_format({"bg_color":"#fbf3e1","font_color":"#6b4d10"})
        fmt_grn = wb.add_format({"bg_color":"#e8f4ec","font_color":"#1e5e3a"})
        col_estado = df.columns.tolist().index("Estado") if "Estado" in df.columns else None
        for i, col in enumerate(df.columns):
            ws.write(0, i, col, fmt_hdr)
            ws.set_column(i, i, max(14, len(str(col)) + 4))
        for row_idx, row in df.iterrows():
            if col_estado is not None:
                est = str(row.get("Estado",""))
                fmt = fmt_red if "🔴" in est else fmt_yel if "🟡" in est else fmt_grn if "🟢" in est else None
                if fmt:
                    for ci in range(len(df.columns)):
                        ws.write(row_idx + 1, ci, row.iloc[ci], fmt)
    return buf.getvalue()
