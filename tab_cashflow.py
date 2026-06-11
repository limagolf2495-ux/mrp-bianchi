from datetime import timedelta
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import tema
from config import get_hoy
from gsheets import _gs_client, guardar_pagos_oc


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

    if _gs_client() is None:
        st.markdown(tema.banner(
            "Las credenciales GCP no están configuradas — los estados <strong>Pagada</strong> "
            "no se cargan ni guardan. Todas las OC vigentes aparecen como pendientes de pago "
            "hasta que se configure <code>.streamlit/secrets.toml</code> con la sección "
            "<code>[gcp_service_account]</code>.", "warn"), unsafe_allow_html=True)

    res_cf  = st.session_state.mrp_result
    s_hd_cf = st.session_state.mrp_sem_headers

    precio_map = {
        str(r["codigo"]): float(r["precio_unitario"])
        for _, r in st.session_state.precios.iterrows()
    }
    arts_map      = {str(r["Código"]): r.get("_arts", [])      for r in res_cf}
    arts_desc_map = {str(r["Código"]): r.get("_arts_desc", []) for r in res_cf}

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
            "_arts": r.get("_arts", []), "_arts_desc": r.get("_arts_desc", []),
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

    # Capa 2: compromisos a activar (OC abiertas sin pagar)
    todas_s = st.session_state.get("mrp_todas_sems", [])
    oc_no_pagada_ss = st.session_state.get("mrp_oc_no_pagada", {})
    semana_actual_inicio = todas_s[0][1] if todas_s else None
    compromiso_sem = {h: 0.0 for h in s_hd_cf}
    for cod, entradas in oc_no_pagada_ss.items():
        precio = precio_map.get(cod, 0)
        if precio == 0:
            continue
        for entrada in entradas:
            tipo  = entrada["tipo"]
            lead  = st.session_state.lead_times.get(tipo, 15)
            fecha_pago = entrada["fec"] - timedelta(days=lead)
            importe    = entrada["qty"] * precio
            sem_asignada = None
            if semana_actual_inicio and fecha_pago <= semana_actual_inicio:
                sem_asignada = s_hd_cf[0]
            else:
                for lbl, ss, se in todas_s:
                    if ss <= fecha_pago <= se:
                        sem_asignada = lbl
                        break
            if sem_asignada and sem_asignada in compromiso_sem:
                compromiso_sem[sem_asignada] += importe
    total_compromisos = sum(compromiso_sem.values())

    st.markdown(tema.cards([
        {"lbl": "Total período",      "val": fmt_money(total_periodo),
         "unit": moneda_str, "sub": f"{n_insumos_cf} insumos con precio"},
        {"lbl": "Semana pico",        "val": fmt_money(sem_max_val),
         "unit": moneda_str, "sub": sem_max_name},
        {"lbl": "OC emitidas sin pagar", "val": fmt_money(total_compromisos),
         "unit": moneda_str, "sub": "pagos pendientes de OC existentes", "kind": "warn"},
        {"lbl": "Insumos sin precio", "val": len(sin_precio),
         "sub": "sin cobertura monetaria", "kind": "warn" if sin_precio else "ok"},
    ]), unsafe_allow_html=True)
    st.markdown("")

    cf_tipos = sorted(df_cf["Tipo"].unique().tolist())
    _pt_pairs: dict = {}
    for _row in cf_rows:
        for _a, _d in zip(_row.get("_arts", []), _row.get("_arts_desc", [])):
            if _a and _a not in _pt_pairs:
                _pt_pairs[_a] = _d or ""
    _all_pt_opts = ["Todos"] + [
        f"{_a} — {_d}" if _d else _a for _a, _d in sorted(_pt_pairs.items())
    ]
    _ins_opts_det = ["Todos"] + [
        f"{_r['Código']} — {_r['Descripción']}" if _r.get("Descripción") else _r["Código"]
        for _r in cf_rows
    ]
    cf_f1, cf_f2, cf_f3 = st.columns([2, 3, 3])
    with cf_f1:
        f_cf_tipo = st.selectbox("Tipo de insumo", ["Todos"] + cf_tipos, key="cf_tipo")
    with cf_f2:
        f_cf_pt = st.selectbox("Producto terminado", _all_pt_opts, key="cf_pt")
    with cf_f3:
        f_cf_ins = st.selectbox("Insumo", _ins_opts_det, key="cf_ins")
    df_cf_f = df_cf.copy()
    if f_cf_tipo != "Todos":
        df_cf_f = df_cf_f[df_cf_f["Tipo"] == f_cf_tipo]
    if f_cf_pt != "Todos":
        _sel_pt_cod = f_cf_pt.split(" — ")[0]
        df_cf_f = df_cf_f[df_cf_f["_arts"].apply(lambda _a: _sel_pt_cod in (_a or []))]
    if f_cf_ins != "Todos":
        df_cf_f = df_cf_f[df_cf_f["Código"] == f_cf_ins.split(" — ")[0]]

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
    fig_cf.add_trace(go.Bar(
        name="OC emitidas sin pagar",
        x=s_hd_cf,
        y=[compromiso_sem.get(h, 0) for h in s_hd_cf],
        marker_color="#e67e22",
        hovertemplate="%{x}<br>OC emitidas sin pagar: %{y:,.0f} " + moneda_str + "<extra></extra>",
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
    df_cf_show   = df_cf_f.drop(columns=[c for c in ["_arts", "_arts_desc"] if c in df_cf_f.columns]).copy()

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

    st.subheader("OC emitidas sin pagar")
    todas_s_cf = st.session_state.get("mrp_todas_sems", [])
    stock_map_cf = {
        str(r["Código"]): r["Descripción"]
        for r in res_cf
    }
    oc_df_cf = st.session_state.oc
    oc_nopag_rows = []
    if oc_df_cf is not None:
        hoy_cf         = get_hoy()
        oc_estados_cf  = st.session_state.mrp_oc_estados
        oc_pagada_cf   = st.session_state.mrp_oc_pagada
        oc_nuevas_cf   = st.session_state.mrp_oc_nueva_fecha
        tipo_ins_map   = {}
        if st.session_state.stock is not None:
            for _, rs in st.session_state.stock.iterrows():
                tipo_ins_map[str(rs["codigo"])] = str(rs.get("tipo_insumo", ""))
        _has_id = "id" in oc_df_cf.columns
        oc_by_cod_cf   = {}
        for _, r in oc_df_cf.iterrows():
            cod = str(r["codigo"]); qty = float(r["cantidad_oc"]); fec = r["fecha_entrega"]
            if pd.isna(fec): continue
            oc_id = str(r["id"]) if _has_id and pd.notna(r["id"]) else ""
            oc_by_cod_cf.setdefault(cod, []).append((fec, qty, oc_id))
        for cod, entries in oc_by_cod_cf.items():
            if not stock_map_cf.get(cod):
                continue
            precio = precio_map.get(cod, None)
            if precio is None or precio == 0:
                continue
            estados_cod = oc_estados_cf.get(cod, {})
            pagos_cod   = oc_pagada_cf.get(cod, {})
            nuevas_cod  = oc_nuevas_cf.get(cod, {})
            for i, (fec, qty, oc_id) in enumerate(entries):
                pagada_val = pagos_cod.get(i, False)
                if pagada_val:
                    continue
                # misma fecha efectiva que usa mrp_calc para la Capa 2 del gráfico
                fec_efectiva = nuevas_cod.get(i) or fec
                es_vigente  = fec_efectiva >= hoy_cf
                es_pendiente = (fec_efectiva < hoy_cf and estados_cod.get(i) == "🕐 Pendiente")
                if not es_vigente and not es_pendiente:
                    continue
                tipo_ins = tipo_ins_map.get(cod, "")
                lead_cf = st.session_state.lead_times.get(tipo_ins, 15)
                fec_pago = fec_efectiva - timedelta(days=lead_cf)
                monto = round(qty * precio)
                sem_label = "⚠️ Vencido" if fec_pago < hoy_cf else "—"
                for lbl, ss, se in todas_s_cf:
                    if ss <= fec_pago <= se:
                        sem_label = lbl; break
                oc_nopag_rows.append({
                    "N° OC":          oc_id,
                    "Código":         cod,
                    "Descripción":    stock_map_cf.get(cod, cod),
                    "Fecha entrega":  fec_efectiva,
                    "Semana de pago": sem_label,
                    "Cantidad":       int(qty),
                    f"Monto ({moneda_str})": monto,
                    "Pagada":         False,
                    "_cod":           cod,
                    "_idx":           i,
                    "_arts":          arts_map.get(cod, []),
                    "_arts_desc":     arts_desc_map.get(cod, []),
                })

    if oc_nopag_rows:
        df_nopag = pd.DataFrame(oc_nopag_rows)

        _oc_pt_pairs: dict = {}
        for _row in oc_nopag_rows:
            for _a, _d in zip(_row.get("_arts", []), _row.get("_arts_desc", [])):
                if _a and _a not in _oc_pt_pairs:
                    _oc_pt_pairs[_a] = _d or ""
        _all_oc_pt_opts = ["Todos"] + [
            f"{_a} — {_d}" if _d else _a for _a, _d in sorted(_oc_pt_pairs.items())
        ]
        _oc_ins_opts = ["Todos"] + sorted({
            f"{_r['Código']} — {_r['Descripción']}" if _r.get("Descripción") else _r["Código"]
            for _r in oc_nopag_rows
        })
        oc_f1, oc_f2 = st.columns([3, 3])
        with oc_f1:
            f_oc_pt = st.selectbox("Producto terminado", _all_oc_pt_opts, key="oc_cf_pt")
        with oc_f2:
            f_oc_ins = st.selectbox("Insumo", _oc_ins_opts, key="oc_cf_ins")

        _oc_mask = pd.Series([True] * len(df_nopag), dtype=bool)
        if f_oc_pt != "Todos":
            _sel_oc_pt = f_oc_pt.split(" — ")[0]
            _oc_mask &= df_nopag["_arts"].apply(lambda _a: _sel_oc_pt in (_a or []))
        if f_oc_ins != "Todos":
            _oc_mask &= df_nopag["Código"] == f_oc_ins.split(" — ")[0]

        df_nopag_f    = df_nopag[_oc_mask].reset_index(drop=True)
        _orig_indices = df_nopag[_oc_mask].index.tolist()

        edited_nopag = st.data_editor(
            df_nopag_f.drop(columns=["_cod", "_idx", "_arts", "_arts_desc"]),
            column_config={
                "N° OC":          st.column_config.TextColumn("N° OC", disabled=True, width="small"),
                "Código":         st.column_config.TextColumn("Código", width="small", disabled=True),
                "Descripción":    st.column_config.TextColumn("Descripción", disabled=True),
                "Fecha entrega":  st.column_config.DateColumn("Fecha entrega", disabled=True, width="small"),
                "Semana de pago": st.column_config.TextColumn("Semana de pago", disabled=True, width="small"),
                "Cantidad":       st.column_config.NumberColumn("Cantidad", format="%d", disabled=True, width="small"),
                f"Monto ({moneda_str})": st.column_config.NumberColumn(f"Monto ({moneda_str})", format="%.0f", disabled=True, width="small"),
                "Pagada":         st.column_config.CheckboxColumn("Pagada", help="Marcá si el pago fue enviado al proveedor"),
            },
            use_container_width=True, hide_index=True,
            column_order=["N° OC", "Código", "Descripción", "Fecha entrega", "Semana de pago",
                          "Cantidad", f"Monto ({moneda_str})", "Pagada"],
            key="cf_oc_nopag_editor",
        )
        col_save_cf, _ = st.columns([2, 6])
        with col_save_cf:
            if st.button("💾 Guardar pagos", key="btn_cf_guardar_pagos", type="primary",
                         use_container_width=True):
                for idx_row, edited_row in edited_nopag.iterrows():
                    original = oc_nopag_rows[_orig_indices[idx_row]]
                    cod_r = original["_cod"]; i_r = original["_idx"]
                    nuevo_pago = bool(edited_row["Pagada"])
                    if nuevo_pago:
                        st.session_state.mrp_oc_pagada.setdefault(cod_r, {})[i_r] = True
                    else:
                        st.session_state.mrp_oc_pagada.get(cod_r, {}).pop(i_r, None)
                guardar_pagos_oc()
                st.session_state.mrp_desactualizado = True
                st.success("✓ Pagos guardados")
                st.rerun()
        _total_vis = len(df_nopag_f)
        _total_all = len(oc_nopag_rows)
        _cap = f"{_total_vis} OC sin pagar" + (f" (de {_total_all} totales)" if _total_vis < _total_all else "")
        st.caption(_cap + " · marcá como Pagada y guardá para actualizar el cash-flow")
    else:
        st.info("No hay OC emitidas con pagos pendientes en el horizonte.")

    if sin_precio:
        with st.expander(f"⚠️ {len(sin_precio)} insumos con sugerencia sin precio cargado"):
            sp_rows = [{"Código": c,
                        "Descripción": next((r["Descripción"] for r in res_cf if r["Código"]==c), ""),
                        "Sugerencia":  next((r["Sugerencia"]  for r in res_cf if r["Código"]==c), 0)}
                       for c in sin_precio]
            st.dataframe(pd.DataFrame(sp_rows), use_container_width=True, hide_index=True)
