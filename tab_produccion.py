import pandas as pd
import streamlit as st

import tema
from config import get_hoy
from helpers import distribuir, mes_key, semanas_desde_hoy


def render_tab_produccion():
    hoy = get_hoy()
    mes_nombre = hoy.strftime("%B %Y").capitalize()
    st.header(f"Plan de Producción — {mes_nombre}")

    if st.session_state.forecast is None or st.session_state.bom is None:
        st.info("Cargá el BOM y el Forecast para habilitar este módulo.")
        return

    fc  = st.session_state.forecast
    bom = st.session_state.bom
    uk  = st.session_state.uploader_key

    semanas     = semanas_desde_hoy(hoy.year, hoy.month)
    n_sem       = len(semanas)
    sem_labels  = [s[0] for s in semanas]
    mes_act_key = mes_key(hoy.year, hoy.month - 1)
    dist        = st.session_state.dist_4 if n_sem <= 4 else st.session_state.dist_5

    if not st.session_state.prod_listo:
        prod = {}
        for _, row in fc.iterrows():
            art    = str(row["articulo"])
            desc   = str(row.get("descripcion", art))
            fc_val = float(row[mes_act_key]) if (
                mes_act_key in row.index and pd.notna(row[mes_act_key])
            ) else 0
            if fc_val <= 0: continue
            vals = distribuir(fc_val, n_sem, dist)
            prod[art] = {"desc": desc, "forecast": fc_val,
                         **{f"s{i+1}": vals[i] for i in range(n_sem)}}
        st.session_state.produccion = prod
        st.session_state.prod_listo = True

    prod = st.session_state.produccion

    cards_placeholder = st.empty()
    st.markdown("")

    col_b, col_add, col_r = st.columns([5, 1.3, 1.3])
    with col_b:
        busqueda = st.text_input("Buscar", placeholder="🔍 Buscar por descripción o código...",
                                 label_visibility="collapsed")
    with col_add:
        if st.button("➕ Agregar", use_container_width=True):
            st.session_state["show_add"] = True
    with col_r:
        if st.button("↺ Redistribuir", use_container_width=True):
            st.session_state["confirm_redist"] = True

    if st.session_state.get("show_add"):
        with st.container(border=True):
            st.markdown("**Agregar artículo al plan**")
            arts_bom       = sorted(bom["articulo"].unique().tolist())
            arts_disponibles = [a for a in arts_bom if a not in prod]
            col_sel, col_ok, col_cancel = st.columns([5, 1, 1])
            with col_sel:
                art_nuevo = st.selectbox("Artículo", [""] + arts_disponibles,
                                         label_visibility="collapsed")
            with col_ok:
                if st.button("✓ Agregar", key="btn_add_ok", type="primary"):
                    if art_nuevo:
                        desc_n = ""
                        if fc is not None and "descripcion" in fc.columns:
                            r = fc[fc["articulo"] == art_nuevo]
                            if not r.empty: desc_n = str(r["descripcion"].values[0])
                        fc_val_n = 0
                        if fc is not None and mes_act_key in fc.columns:
                            r = fc[fc["articulo"] == art_nuevo]
                            if not r.empty: fc_val_n = float(r[mes_act_key].values[0])
                        st.session_state.produccion[art_nuevo] = {
                            "desc": desc_n, "forecast": fc_val_n,
                            **{f"s{i+1}": 0 for i in range(n_sem)}}
                        st.session_state.mrp_desactualizado = True
                        st.session_state["show_add"] = False
                        st.rerun()
            with col_cancel:
                if st.button("✕", key="btn_add_cancel"):
                    st.session_state["show_add"] = False
                    st.rerun()

    if st.session_state.get("confirm_redist"):
        with st.container(border=True):
            st.warning("⚠️ Esto reemplaza todos los valores manuales con la distribución automática. ¿Confirmás?")
            col_si, col_no, _ = st.columns([1.4, 1, 5])
            with col_si:
                if st.button("✓ Sí, redistribuir", key="btn_redist_ok", type="primary"):
                    for art, datos in st.session_state.produccion.items():
                        vals = distribuir(datos["forecast"], n_sem, dist)
                        for i in range(n_sem):
                            datos[f"s{i+1}"] = vals[i]
                    st.session_state.mrp_desactualizado = True
                    st.session_state["confirm_redist"] = False
                    st.rerun()
            with col_no:
                if st.button("✕ Cancelar", key="btn_redist_cancel"):
                    st.session_state["confirm_redist"] = False
                    st.rerun()

    rows_all = []
    for art, dd in prod.items():
        rows_all.append({
            "Código": art, "Descripción": dd.get("desc",""),
            **{sem_labels[i]: dd.get(f"s{i+1}",0) for i in range(n_sem)},
            "Distribución": [dd.get(f"s{i+1}",0) for i in range(n_sem)],
            "_forecast": int(dd.get("forecast",0)),
        })
    df_all = pd.DataFrame(rows_all) if rows_all else pd.DataFrame()

    if df_all.empty:
        st.info("No hay artículos en el plan. Cargá el forecast o agregá artículos manualmente.")
        return

    if busqueda:
        mask = (df_all["Descripción"].str.contains(busqueda, case=False, na=False) |
                df_all["Código"].str.contains(busqueda, case=False, na=False))
        df_show = df_all[mask].copy()
    else:
        df_show = df_all.copy()

    df_editor = df_show.drop(columns=["_forecast"])

    col_cfg = {
        "Código":      st.column_config.TextColumn("Código", width="small", disabled=True),
        "Descripción": st.column_config.TextColumn("Descripción", width="large", disabled=True),
        "Distribución": st.column_config.BarChartColumn("Distribución",
                                                        help="Reparto por semana", width="small"),
    }
    for sl in sem_labels:
        col_cfg[sl] = st.column_config.NumberColumn(sl, min_value=0, step=1, format="%d")

    editor_key = f"prod_editor_{hash(busqueda)}_{uk}"
    edited = st.data_editor(
        df_editor, column_config=col_cfg, use_container_width=True,
        hide_index=True, num_rows="fixed", key=editor_key, height=520,
        column_order=["Código","Descripción"] + sem_labels + ["Distribución"],
    )

    changed = False
    for _, row in edited.iterrows():
        art = row["Código"]
        if art in st.session_state.produccion:
            for i in range(n_sem):
                new_val = int(row.get(sem_labels[i], 0) or 0)
                if st.session_state.produccion[art].get(f"s{i+1}", 0) != new_val:
                    st.session_state.produccion[art][f"s{i+1}"] = new_val
                    changed = True
    if changed:
        st.session_state.mrp_desactualizado = True

    _tp = sum(sum(d.get(f"s{i+1}",0) for i in range(n_sem))
              for d in st.session_state.produccion.values())
    _fc = sum(int(d.get("forecast",0)) for d in st.session_state.produccion.values())
    _dv = _tp - _fc
    _kd = "ok" if _dv == 0 else ("warn" if abs(_dv) / (_fc or 1) > 0.05 else "")
    cards_placeholder.markdown(tema.cards([
        {"lbl":"Artículos en plan","val":f"{len(st.session_state.produccion):,}",
         "sub":"a producir este mes"},
        {"lbl":"Total plan","val":f"{_tp:,}","sub":"unidades programadas"},
        {"lbl":"Forecast del mes","val":f"{_fc:,}","sub":"demanda estimada"},
        {"lbl":"Desvío plan","val":f"{_dv:+,}",
         "sub":"alineado al forecast" if _dv==0 else ("por encima" if _dv>0 else "por debajo"),
         "kind":_kd},
    ]), unsafe_allow_html=True)

    if busqueda:
        total_vista = int(edited[[sl for sl in sem_labels]].sum().sum())
        st.caption(f"Vista filtrada: {len(df_show):,} artículos · {total_vista:,} uds en pantalla")
    else:
        st.caption(f"{len(prod):,} artículos en el plan · editá cualquier celda para ajustar la carga semanal")
