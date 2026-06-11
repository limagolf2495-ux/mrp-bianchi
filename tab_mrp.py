import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import tema
from config import get_hoy
from gsheets import guardar_oc_estados, guardar_pagos_oc
from helpers import exportar_excel
from mrp_calc import calcular_mrp


def render_tab_mrp():
    hoy = get_hoy()
    st.header("Plan de Compras — MRP")

    if st.session_state.stock is None or st.session_state.bom is None:
        st.info("Cargá stock y BOM para calcular el MRP.")
        return

    if st.session_state.fecha_corte_stock:
        dias_stock = (hoy - st.session_state.fecha_corte_stock).days
        fc_str = st.session_state.fecha_corte_stock.strftime("%d/%m/%Y")
        if dias_stock == 0:
            st.markdown(tema.banner(
                f"Stock al corte de hoy · <strong>{fc_str}</strong> &nbsp;·&nbsp; "
                f"Horizonte: {st.session_state.horizonte} meses", "ok"),
                unsafe_allow_html=True)
        elif dias_stock <= 3:
            st.markdown(tema.banner(
                f"Stock con <strong>{dias_stock} día(s)</strong> de antigüedad (corte: {fc_str}). "
                f"Verificá consumos recientes.", "warn"), unsafe_allow_html=True)
        else:
            st.markdown(tema.banner(
                f"Stock con <strong>{dias_stock} días</strong> de antigüedad (corte: {fc_str}). "
                f"Los resultados pueden no reflejar la realidad.", "crit"),
                unsafe_allow_html=True)

    if st.session_state.mrp_desactualizado and st.session_state.mrp_result:
        st.markdown(tema.banner(
            "Los parámetros o datos cambiaron. <strong>Recalculá el MRP</strong> para actualizar los resultados.",
            "warn"), unsafe_allow_html=True)

    if not st.session_state.produccion:
        st.warning("⚠️ El plan de producción está vacío. El MRP usará solo el forecast de meses futuros.")

    col_calc, _ = st.columns([2, 6])
    with col_calc:
        if st.button("▶ Calcular MRP", type="primary", use_container_width=True):
            with st.spinner("Calculando MRP..."):
                calcular_mrp()

    if not st.session_state.mrp_result:
        return

    res  = st.session_state.mrp_result
    s_hd = st.session_state.mrp_sem_headers

    rojos     = sum(1 for r in res if r["sem_ic"]=="🔴")
    amar      = sum(1 for r in res if r["sem_ic"]=="🟡")
    verd      = sum(1 for r in res if r["sem_ic"]=="🟢")
    sug_total = sum(r["Sugerencia"] for r in res)
    lineas    = sum(1 for r in res if r["Sugerencia"] > 0)
    prox      = sorted([r for r in res if r["_dias_quiebre"] < 9999],
                       key=lambda r: r["_dias_quiebre"])
    prox0     = prox[0] if prox else None

    st.markdown(tema.cards([
        {"lbl":"Críticos","val":rojos,"sub":"sin cobertura","kind":"crit"},
        {"lbl":"Parciales","val":amar,"sub":"cobertura a riesgo","kind":"warn"},
        {"lbl":"Cubiertos","val":verd,"sub":"ok al horizonte","kind":"ok"},
        {"lbl":"Compra sugerida","val":f"{sug_total:,}","sub":f"{lineas} líneas a pedir"},
        {"lbl":"Próximo quiebre",
         "val":(prox0["_dias_quiebre"] if prox0 else "—"),
         "unit":"días" if prox0 else "",
         "sub":(prox0["Descripción"] if prox0 else "Todo cubierto")},
    ]), unsafe_allow_html=True)
    st.markdown("")

    _ac_pts = sorted(set(
        v for r in res for v in r["_arts"] + [d for d in r["_arts_desc"] if d]
    ))
    _ac_ins = sorted(set(v for r in res for v in [r["Código"], r["Descripción"]]))
    f_texto = st.selectbox(
        "", options=_ac_pts + _ac_ins, index=None,
        placeholder="🔍 Buscar por insumo o producto terminado...",
        label_visibility="collapsed",
    )

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        f_est = st.selectbox("Estado", ["Todos","🔴 Crítico","🟡 Parcial","🟢 Cubierto"])
    with fc2:
        tipos_u = sorted(set(r["Tipo"] for r in res))
        f_tipo  = st.selectbox("Tipo de insumo", ["Todos"] + tipos_u)
    with fc3:
        marcas_u = sorted(set(m for r in res for m in r["_marcas"]))
        f_marca  = st.selectbox("Marca", ["Todas"] + marcas_u)
    with fc4:
        pedir_set = set(r["Pedir en"] for r in res)
        pedir_ord = [v for v in s_hd if v in pedir_set]
        pedir_ext = [v for v in ["⚠️ Atrasado", "—"] if v in pedir_set]
        f_pedir   = st.selectbox("Pedir en", ["Todas"] + pedir_ord + pedir_ext)

    res_f = res[:]
    if f_texto:
        t = f_texto.lower()
        res_f = [r for r in res_f if
                 t in r["Código"].lower() or t in r["Descripción"].lower() or
                 any(t in a.lower() for a in r["_arts"]) or
                 any(t in d.lower() for d in r["_arts_desc"])]
    if f_est != "Todos":
        ic = f_est.split()[0]
        res_f = [r for r in res_f if r["sem_ic"] == ic]
    if f_tipo != "Todos":
        res_f = [r for r in res_f if r["Tipo"] == f_tipo]
    if f_marca != "Todas":
        res_f = [r for r in res_f if f_marca in r["_marcas"]]
    if f_pedir != "Todas":
        res_f = [r for r in res_f if r["Pedir en"] == f_pedir]

    df_show = pd.DataFrame([{
        "Estado": f"{r['sem_ic']} {r['sem_lb']}",
        "Pedir en": r["Pedir en"],
        "Descripción": r["Descripción"], "Código": r["Código"], "Tipo": r["Tipo"],
        "Stock": r["Stock"],
        "OC en tránsito": r["_oc_label"],
        "Demanda total": r["Nec. total"],
        "Brecha": r["Nec. neta"],
        "Sugerencia": r["Sugerencia"],
        "Días al quiebre": r["Días al quiebre"],
        **{h: r[h] for h in s_hd},
    } for r in res_f])

    col_cfg_mrp = {
        "Estado": st.column_config.TextColumn("Estado", width="small"),
        "Pedir en": st.column_config.TextColumn("Pedir en", width="medium"),
        "Descripción": st.column_config.TextColumn("Descripción", width="large"),
        "Código": st.column_config.TextColumn("Código", width="small"),
        "Tipo": st.column_config.TextColumn("Tipo", width="small"),
        "Stock": st.column_config.NumberColumn("Stock", format="%d",
            help="Stock físico disponible al corte informado"),
        "OC en tránsito": st.column_config.TextColumn("OC en tránsito",
            help="OC abiertas con entrega futura. Incluye OC vencidas marcadas como Pendiente."),
        "Demanda total": st.column_config.NumberColumn("Demanda total", format="%d",
            help="Necesidad bruta acumulada en el horizonte de planificación"),
        "Brecha": st.column_config.NumberColumn("Brecha", format="%d",
            help="= Demanda total − Stock − OC en tránsito. Cantidad que efectivamente falta cubrir."),
        "Sugerencia": st.column_config.NumberColumn("Sugerencia", format="%d",
            help="Brecha redondeada al múltiplo de compra configurado."),
        "Días al quiebre": st.column_config.NumberColumn("Días", format="%d", width="small",
            help="Días hasta el primer quiebre de stock si no se compra"),
        **{h: st.column_config.NumberColumn(h, format="%d", width="small") for h in s_hd},
    }
    col_order_mrp = (
        ["Estado", "Pedir en", "Descripción", "Código", "Tipo",
         "Stock", "OC en tránsito", "Demanda total", "Brecha", "Sugerencia",
         "Días al quiebre"] + s_hd
    )
    sel = st.dataframe(
        df_show, use_container_width=True, hide_index=True, height=440,
        on_select="rerun", selection_mode="single-row",
        column_config=col_cfg_mrp, column_order=col_order_mrp,
    )

    col_dl, _ = st.columns([2, 6])
    with col_dl:
        st.download_button("⬇️ Exportar Excel", exportar_excel(df_show),
            f"MRP_{hoy.isoformat()}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.subheader("Detalle de insumo")

    cod_por_click = None
    filas_sel = sel.selection.get("rows", []) if sel and sel.selection else []
    if filas_sel:
        idx = filas_sel[0]
        if idx < len(df_show):
            cod_por_click = df_show.iloc[idx]["Código"]
            st.session_state["mrp_cod_sel"] = cod_por_click

    col_fc, col_fd, col_info = st.columns([2, 3, 3])
    with col_fc:
        busq_cod = st.text_input("Buscar código", placeholder="🔍 Código...",
                                 label_visibility="collapsed")
    with col_fd:
        busq_desc = st.text_input("Buscar descripción", placeholder="🔍 Descripción...",
                                  label_visibility="collapsed")
    with col_info:
        st.caption("💡 También podés hacer click en una fila de la tabla para ver el detalle.")

    res_det = res_f[:]
    if busq_cod:
        res_det = [r for r in res_det if busq_cod.lower() in r["Código"].lower()]
    if busq_desc:
        res_det = [r for r in res_det if busq_desc.lower() in r["Descripción"].lower()]

    codigos_det = [r["Código"] for r in res_det]
    cod_activo  = st.session_state.get("mrp_cod_sel")
    if cod_por_click:
        cod_activo = cod_por_click
    elif codigos_det and (not cod_activo or cod_activo not in codigos_det):
        cod_activo = codigos_det[0]

    if codigos_det:
        idx_default = codigos_det.index(cod_activo) if cod_activo in codigos_det else 0
        cod_sel = st.selectbox("Insumo seleccionado", codigos_det, index=idx_default,
            format_func=lambda c: next(
                (f"{c} — {r['Descripción']}" for r in res if r["Código"] == c), c))
        st.session_state["mrp_cod_sel"] = cod_sel
    else:
        st.info("Ningún insumo coincide con el filtro.")
        return

    r = next((x for x in res if x["Código"] == cod_sel), None)
    if not r:
        return

    with st.container(border=True):
        st.markdown(tema.pill(r["sem_kind"], r["sem_lb"]) +
            f'<div class="det-title">{r["Descripción"]}</div>'
            f'<div class="det-sub">{r["Código"]} · {r["Tipo"]} · '
            f'{r["sems_cub"]}/{len(s_hd)} semanas cubiertas</div>',
            unsafe_allow_html=True)
        st.markdown("")

        c1,c2,c3 = st.columns(3)
        c1.metric("Stock actual", f"{r['Stock']:,}",
                  help="Stock físico al corte informado")
        c2.metric("OC en tránsito", r["_oc_label"],
                  help="OC abiertas con entrega futura + vencidas marcadas como Pendiente")
        c3.metric("Demanda total", f"{r['Nec. total']:,}",
                  help="Necesidad bruta acumulada en el horizonte de planificación")
        c1,c2,c3 = st.columns(3)
        c1.metric("Brecha", f"{r['Nec. neta']:,}",
                  help="= Demanda total − Stock − OC en tránsito")
        c2.metric("Sugerencia de compra", f"{r['Sugerencia']:,}",
                  help="Brecha redondeada al múltiplo de compra configurado")
        c3.metric("Días al quiebre",
                  f"{r['_dias_quiebre']}" if r['_dias_quiebre'] < 9999 else "—",
                  help="Días hasta el primer quiebre si no se compra")

        if r["Pedir en"] != "—":
            if "⚠️" in str(r["Pedir en"]):
                st.markdown(tema.banner(
                    "Ya debería haberse pedido — emitir OC cuanto antes", "crit"),
                    unsafe_allow_html=True)
            else:
                st.markdown(tema.banner(
                    f"Emitir pedido en <strong>{r['Pedir en']}</strong>", "ok"),
                    unsafe_allow_html=True)

        col_iz, col_de = st.columns([3, 2])
        with col_iz:
            st.markdown("**Cobertura / necesidad semanal**")
            stk_rem = float(r["Stock"])
            oc_rem  = float(r["OC disp."])
            greens, yellows, reds = [], [], []
            for need in r["Cobertura"]:
                need = float(need)
                if stk_rem >= need:
                    greens.append(need); yellows.append(0); reds.append(0)
                    stk_rem -= need
                elif stk_rem + oc_rem >= need:
                    greens.append(stk_rem)
                    yellows.append(need - stk_rem)
                    reds.append(0)
                    oc_rem  -= (need - stk_rem)
                    stk_rem  = 0
                else:
                    greens.append(max(0.0, stk_rem))
                    yellows.append(max(0.0, oc_rem))
                    reds.append(max(0.0, need - max(0.0, stk_rem) - max(0.0, oc_rem)))
                    stk_rem = 0.0; oc_rem = 0.0
            fig_det = go.Figure()
            fig_det.add_trace(go.Bar(name="Stock", x=s_hd, y=greens,
                                     marker_color=tema.OK))
            fig_det.add_trace(go.Bar(name="OC vigente/pendiente", x=s_hd, y=yellows,
                                     marker_color=tema.WARN))
            fig_det.add_trace(go.Bar(name="Sin cobertura", x=s_hd, y=reds,
                                     marker_color=tema.CRIT))
            fig_det.update_layout(
                barmode="stack", height=240,
                margin=dict(l=0, r=0, t=4, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="left", x=0, font=dict(size=11)),
                xaxis=dict(categoryorder="array", categoryarray=s_hd,
                           tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10)),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_det, use_container_width=True)
        with col_de:
            st.markdown("**Artículos que usan este insumo:**")
            fc_ref = st.session_state.forecast
            for a in r["_arts"]:
                desc_a = ""
                if fc_ref is not None and "descripcion" in fc_ref.columns:
                    row_a = fc_ref[fc_ref["articulo"] == a]
                    if not row_a.empty:
                        desc_a = str(row_a["descripcion"].values[0])
                st.markdown(f"- `{a}` {desc_a}")

        st.markdown("**Órdenes de compra:**")
        oc_det = r["_oc_det"]
        if oc_det:
            vencidas_idx = [i for i, o in enumerate(oc_det) if o["Estado"] == "⚠️ Vencida"]
            if vencidas_idx:
                col_bp, col_br, _ = st.columns([1.8, 1.8, 5])
                with col_bp:
                    if st.button("🕐 Todas en Pendiente", key=f"btn_all_pend_{cod_sel}",
                                 use_container_width=True):
                        nuevos = {i: "🕐 Pendiente" for i in vencidas_idx}
                        st.session_state.mrp_oc_estados[cod_sel] = nuevos
                        total_p = sum(float(oc_det[i]["Cantidad OC"]) for i in vencidas_idx)
                        st.session_state.mrp_oc_venc_parcial[cod_sel] = total_p
                        st.session_state.mrp_desactualizado = True
                        guardar_oc_estados()
                        st.rerun()
                with col_br:
                    if st.button("↺ Restablecer vencidas", key=f"btn_all_reset_{cod_sel}",
                                 use_container_width=True):
                        st.session_state.mrp_oc_estados[cod_sel] = {}
                        st.session_state.mrp_oc_venc_parcial[cod_sel] = 0.0
                        st.session_state.mrp_desactualizado = True
                        guardar_oc_estados()
                        st.rerun()

            col_bp2, col_br2, _ = st.columns([1.8, 1.8, 5])
            with col_bp2:
                if st.button("💲 Marcar todas pagadas", key=f"btn_all_pag_{cod_sel}",
                             use_container_width=True):
                    st.session_state.mrp_oc_pagada[cod_sel] = {i: True for i in range(len(oc_det))}
                    st.session_state.mrp_desactualizado = True
                    guardar_pagos_oc()
                    st.rerun()
            with col_br2:
                if st.button("↺ Restablecer pagos", key=f"btn_all_nopag_{cod_sel}",
                             use_container_width=True):
                    st.session_state.mrp_oc_pagada[cod_sel] = {}
                    st.session_state.mrp_desactualizado = True
                    guardar_pagos_oc()
                    st.rerun()

            estados_guardados = st.session_state.mrp_oc_estados.get(cod_sel, {})
            nuevas_guardadas  = st.session_state.mrp_oc_nueva_fecha.get(cod_sel, {})
            rows_oc = []
            for i, o in enumerate(oc_det):
                es_vencida    = o["Estado"] == "⚠️ Vencida"
                estado_actual = estados_guardados.get(i, o["Estado"]) if es_vencida else o["Estado"]
                rows_oc.append({
                    "N° OC": o.get("N° OC", ""),
                    "Fecha entrega": o["Fecha entrega"],
                    "Cantidad OC": int(o["Cantidad OC"]),
                    "Estado": estado_actual,
                    "Nueva fecha": nuevas_guardadas.get(i),
                    "Pagada": st.session_state.mrp_oc_pagada.get(cod_sel, {}).get(i, False),
                })
            df_oc     = pd.DataFrame(rows_oc)
            edited_oc = st.data_editor(df_oc, column_config={
                "N° OC": st.column_config.TextColumn("N° OC", disabled=True, width="small"),
                "Fecha entrega": st.column_config.DateColumn("Fecha entrega", disabled=True),
                "Cantidad OC": st.column_config.NumberColumn("Cantidad OC", disabled=True, format="%d"),
                "Estado": st.column_config.SelectboxColumn("Estado",
                    options=["✅ Vigente", "⚠️ Vencida", "🕐 Pendiente"], required=True,
                    help="Cambiá a 🕐 Pendiente para incluir la cantidad en la cobertura"),
                "Nueva fecha": st.column_config.DateColumn("Nueva fecha", min_value=hoy,
                    help="Nueva fecha de entrega confirmada por el proveedor (solo OC vencidas). "
                         "Al cargarla, la línea pasa a 🕐 Pendiente y cuenta como vigente en esa semana."),
                "Pagada": st.column_config.CheckboxColumn(
                    "Pagada",
                    help="Marcá si el pago fue enviado al proveedor. Las OC pagadas se excluyen del cash-flow de compromisos pendientes."),
            }, use_container_width=True, hide_index=True, key=f"oc_editor_{cod_sel}")

            nuevos_estados  = {}
            nuevas_fechas   = {}
            fechas_cambiaron = False
            total_pendiente = 0.0
            nuevos_pagos    = {}
            pagos_cambiaron = False
            for i, row in edited_oc.iterrows():
                if oc_det[i]["Estado"] == "⚠️ Vencida":
                    nf = row["Nueva fecha"]
                    nf = None if pd.isna(nf) else (nf.date() if hasattr(nf, "date") else nf)
                    estado_fila = row["Estado"]
                    if nf:
                        estado_fila = "🕐 Pendiente"  # nueva fecha implica Pendiente
                        nuevas_fechas[i] = nf
                    if nf != nuevas_guardadas.get(i):
                        fechas_cambiaron = True
                    nuevos_estados[i] = estado_fila
                    if estado_fila == "🕐 Pendiente":
                        total_pendiente += float(oc_det[i]["Cantidad OC"])
                nuevo_pago = bool(row["Pagada"])
                prev_pago  = st.session_state.mrp_oc_pagada.get(cod_sel, {}).get(i, False)
                if nuevo_pago:
                    nuevos_pagos[i] = True
                if nuevo_pago != prev_pago:
                    pagos_cambiaron = True
            st.session_state.mrp_oc_estados[cod_sel] = nuevos_estados
            st.session_state.mrp_oc_nueva_fecha[cod_sel] = nuevas_fechas
            prev_parcial = st.session_state.mrp_oc_venc_parcial.get(cod_sel, 0.0)
            if total_pendiente != prev_parcial or fechas_cambiaron:
                st.session_state.mrp_oc_venc_parcial[cod_sel] = total_pendiente
                st.session_state.mrp_desactualizado = True
                guardar_oc_estados()
            st.session_state.mrp_oc_pagada[cod_sel] = nuevos_pagos
            if pagos_cambiaron:
                st.session_state.mrp_desactualizado = True
                guardar_pagos_oc()
            if total_pendiente > 0:
                st.caption(f"Suma a cobertura: {round(total_pendiente):,} en estado Pendiente. "
                           f"Recalculá el MRP para aplicar.")
        else:
            st.info("Sin OC abiertas para este insumo.")

        todas_s = st.session_state.mrp_todas_sems
        if todas_s and r.get("Cobertura"):
            rows_ins = []
            for i, (lbl, fec_ini, fec_fin) in enumerate(todas_s):
                qty = r["Cobertura"][i] if i < len(r["Cobertura"]) else 0
                if qty > 0:
                    rows_ins.append({
                        "N° Artículo": cod_sel,
                        "Cantidad necesaria": qty,
                        "Fecha necesaria": fec_ini.strftime("%d/%m/%Y"),
                    })
            if rows_ins:
                st.markdown("")
                col_dl_ins, _ = st.columns([2, 6])
                with col_dl_ins:
                    st.download_button(
                        "⬇️ Exportar este insumo",
                        exportar_excel(pd.DataFrame(rows_ins)),
                        f"Insumo_{cod_sel}_{hoy.isoformat()}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_ins_{cod_sel}",
                    )
