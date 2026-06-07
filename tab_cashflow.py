from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import tema
from config import get_hoy


def _exportar_cf(df_export):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="CashFlow")
        wb = writer.book
        ws = writer.sheets["CashFlow"]
        fmt_hdr = wb.add_format({"bold": True, "bg_color": "#1f2733",
                                 "font_color": "#ffffff", "border": 1})
        fmt_num = wb.add_format({"num_format": "#,##0"})
        fmt_tot = wb.add_format({"bold": True, "num_format": "#,##0",
                                 "bg_color": "#e8f4ec"})
        for i, col in enumerate(df_export.columns):
            ws.write(0, i, col, fmt_hdr)
            ws.set_column(i, i, max(12, len(str(col)) + 4))
        last_row = len(df_export)
        for row_idx in range(1, last_row + 1):
            is_total = str(df_export.iloc[row_idx - 1].get("Descripción", "")) == "TOTAL"
            fmt = fmt_tot if is_total else fmt_num
            for ci in range(len(df_export.columns)):
                val = df_export.iloc[row_idx - 1, ci]
                ws.write(row_idx, ci, val if pd.notna(val) else "", fmt)
    return buf.getvalue()


def render_tab_cashflow():
    st.header("Cash-Flow Semanal de Compras")

    if not st.session_state.mrp_result:
        st.info("Primero calculá el MRP en la pestaña 📦 MRP.")
        return
    if st.session_state.precios is None:
        st.info("Cargá el archivo de precios (💲 precios.csv) desde el panel lateral.")
        return

    res_cf  = st.session_state.mrp_result
    s_hd_cf = st.session_state.mrp_sem_headers

    precio_map = {
        str(r["codigo"]): float(r["precio_unitario"])
        for _, r in st.session_state.precios.iterrows()
    }

    moneda_col = "moneda" in st.session_state.precios.columns
    monedas    = st.session_state.precios["moneda"].dropna().unique().tolist() if moneda_col else []
    moneda_str = monedas[0] if len(monedas) == 1 else ("$" if not monedas else "mix")

    cf_rows = []
    for r in res_cf:
        cod    = r["Código"]
        precio = precio_map.get(cod, None)
        if precio is None or precio == 0:
            continue
        semanas_val  = {h: round(r.get(h, 0) * precio, 2) for h in s_hd_cf}
        total_insumo = sum(semanas_val.values())
        if total_insumo == 0:
            continue
        cf_rows.append({
            "Código": cod, "Descripción": r["Descripción"], "Tipo": r["Tipo"],
            "Precio unit.": precio, "Total": total_insumo,
            **semanas_val,
        })

    sin_precio = [r["Código"] for r in res_cf
                  if r["Sugerencia"] > 0 and precio_map.get(r["Código"]) is None]

    if not cf_rows:
        st.warning("No hay erogaciones calculables. Verificá que los códigos del archivo de precios "
                   "coincidan con los del MRP, y que haya sugerencias de compra.")
        if sin_precio:
            st.caption(f"Insumos con sugerencia sin precio: {', '.join(sin_precio[:10])}"
                       + (" ..." if len(sin_precio) > 10 else ""))
        return

    df_cf = pd.DataFrame(cf_rows)

    total_periodo = df_cf["Total"].sum()
    sem_totales   = df_cf[s_hd_cf].sum()
    sem_max_val   = sem_totales.max()
    sem_max_name  = sem_totales.idxmax() if sem_max_val > 0 else "—"
    n_insumos_cf  = len(df_cf)

    def fmt_money(v):
        if v >= 1_000_000: return f"{v/1_000_000:.1f} M"
        if v >= 1_000:     return f"{v/1_000:.0f} K"
        return f"{v:,.0f}"

    st.markdown(tema.cards([
        {"lbl": "Total período",      "val": fmt_money(total_periodo),
         "unit": moneda_str, "sub": f"{n_insumos_cf} insumos con precio"},
        {"lbl": "Semana pico",        "val": fmt_money(sem_max_val),
         "unit": moneda_str, "sub": sem_max_name},
        {"lbl": "Insumos sin precio", "val": len(sin_precio),
         "sub": "sin cobertura monetaria", "kind": "warn" if sin_precio else "ok"},
    ]), unsafe_allow_html=True)
    st.markdown("")

    cf_tipos = sorted(df_cf["Tipo"].unique().tolist())
    cf_f1, _ = st.columns([2, 6])
    with cf_f1:
        f_cf_tipo = st.selectbox("Tipo de insumo", ["Todos"] + cf_tipos, key="cf_tipo")
    df_cf_f = df_cf if f_cf_tipo == "Todos" else df_cf[df_cf["Tipo"] == f_cf_tipo]

    st.subheader("Erogaciones por semana")
    tipos_plot = sorted(df_cf_f["Tipo"].unique().tolist())
    COLORS = [
        "#2ecc71","#3498db","#e74c3c","#f39c12","#9b59b6",
        "#1abc9c","#e67e22","#34495e","#e91e63","#00bcd4",
    ]
    fig_cf = go.Figure()
    for i, tipo in enumerate(tipos_plot):
        sub         = df_cf_f[df_cf_f["Tipo"] == tipo]
        totales_sem = sub[s_hd_cf].sum()
        fig_cf.add_trace(go.Bar(
            name=tipo, x=s_hd_cf, y=totales_sem.values,
            marker_color=COLORS[i % len(COLORS)],
            hovertemplate="%{x}<br>" + tipo + ": %{y:,.0f} " + moneda_str + "<extra></extra>",
        ))
    fig_cf.update_layout(
        barmode="stack",
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        font=dict(color="#fafafa"),
        xaxis=dict(title="", gridcolor="#2a2d35"),
        yaxis=dict(title=f"Importe ({moneda_str})", gridcolor="#2a2d35", tickformat=",.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=40, b=10), height=380,
    )
    st.plotly_chart(fig_cf, use_container_width=True)

    st.subheader("Detalle por insumo")
    col_cfg_cf = {
        "Código":       st.column_config.TextColumn("Código", width="small"),
        "Descripción":  st.column_config.TextColumn("Descripción", width="large"),
        "Tipo":         st.column_config.TextColumn("Tipo", width="small"),
        "Precio unit.": st.column_config.NumberColumn("Precio unit.", format="%.2f", width="small"),
        "Total":        st.column_config.NumberColumn(f"Total ({moneda_str})", format="%.0f"),
        **{h: st.column_config.NumberColumn(h, format="%.0f", width="small") for h in s_hd_cf},
    }
    col_order_cf = ["Código", "Descripción", "Tipo", "Precio unit.", "Total"] + s_hd_cf
    df_cf_show   = df_cf_f.copy()

    totals_row = {"Código": "—", "Descripción": "TOTAL", "Tipo": "", "Precio unit.": None,
                  "Total": df_cf_show["Total"].sum(),
                  **{h: df_cf_show[h].sum() for h in s_hd_cf}}
    df_cf_show = pd.concat([df_cf_show, pd.DataFrame([totals_row])], ignore_index=True)

    st.dataframe(df_cf_show, use_container_width=True, hide_index=True,
                 column_config=col_cfg_cf, column_order=col_order_cf, height=400)

    col_dl_cf, _ = st.columns([2, 6])
    with col_dl_cf:
        st.download_button(
            "⬇️ Exportar Cash-Flow Excel",
            _exportar_cf(df_cf_show),
            f"CashFlow_{get_hoy().isoformat()}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if sin_precio:
        with st.expander(f"⚠️ {len(sin_precio)} insumos con sugerencia sin precio cargado"):
            sp_rows = [{"Código": c,
                        "Descripción": next((r["Descripción"] for r in res_cf if r["Código"]==c), ""),
                        "Sugerencia":  next((r["Sugerencia"]  for r in res_cf if r["Código"]==c), 0)}
                       for c in sin_precio]
            st.dataframe(pd.DataFrame(sp_rows), use_container_width=True, hide_index=True)
