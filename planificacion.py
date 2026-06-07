import math

from config import get_hoy
from helpers import mes_key


def calcular_stock_objetivo(art, regla, fc_df, mes_act_key):
    """Calcula stock objetivo según regla: Nm (meses), N% (del forecast), o número fijo."""
    row = fc_df[fc_df["articulo"] == art]
    fc_mes = 0.0
    if not row.empty and mes_act_key in fc_df.columns:
        fc_mes = float(row.iloc[0].get(mes_act_key, 0) or 0)
    hoy   = get_hoy()
    regla = str(regla).strip().lower()
    if regla.endswith("m"):
        try:
            n = float(regla[:-1])
        except ValueError:
            n = 1.0
        n_meses = max(1, int(math.ceil(n)))
        futuros = []
        for m in range(1, n_meses + 1):
            mes0  = (hoy.month - 1 + m) % 12
            año_f = hoy.year + (hoy.month - 1 + m) // 12
            k = mes_key(año_f, mes0)
            if k in fc_df.columns and not row.empty:
                v = float(row.iloc[0].get(k, 0) or 0)
                futuros.append(v)
        if futuros:
            return (sum(futuros) / len(futuros)) * n
        return fc_mes * n
    elif regla.endswith("%"):
        try:
            pct = float(regla[:-1]) / 100
        except ValueError:
            pct = 0.0
        return fc_mes * pct
    else:
        try:
            return max(0.0, float(regla))
        except ValueError:
            return 0.0
