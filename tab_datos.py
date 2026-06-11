import streamlit as st

from config import get_hoy


def render_tab_datos():
    st.header("Datos cargados")
    c1,c2,c3,c4 = st.columns(4)
    for col, key, label in [(c1,"stock","Insumos"),(c2,"oc","Líneas OC"),
                             (c3,"bom","Relaciones BOM"),(c4,"forecast","Artículos FC")]:
        d = st.session_state[key]
        col.metric(label, f"{len(d):,}" if d is not None else "—")
    if st.session_state.oc_descartadas:
        st.caption(f"🛒 OC: {st.session_state.oc_descartadas:,} líneas descartadas "
                   f"(insumos sin demanda en el forecast)")

    st.markdown("")
    any_data = any(st.session_state[k] is not None for k in ["stock","oc","bom","forecast"])
    if not any_data:
        st.info("Cargá los archivos desde el panel izquierdo para comenzar.")
        return

    st.subheader("Validación")
    stock = st.session_state.stock
    oc    = st.session_state.oc
    bom   = st.session_state.bom
    fc    = st.session_state.forecast

    if bom is not None and stock is not None:
        falta = len(set(bom["codigo_insumo"].astype(str)) - set(stock["codigo"].astype(str)))
        if falta: st.warning(f"⚠️ {falta:,} insumos del BOM sin stock (se asumen en 0)")
        else:     st.success("✅ Todos los insumos del BOM tienen stock registrado")

    if oc is not None:
        venc = (oc["fecha_entrega"] < get_hoy()).sum()
        if venc: st.warning(f"⚠️ {venc:,} OC con fecha anterior a hoy")
        else:    st.success("✅ Sin OC vencidas")

    if fc is not None and bom is not None:
        sin_fc = len(set(bom["articulo"].astype(str)) - set(fc["articulo"].astype(str)))
        if sin_fc: st.warning(f"⚠️ {sin_fc:,} artículos del BOM sin forecast")
        else:      st.success("✅ Todos los artículos del BOM tienen forecast")

    st.markdown("---")
    st.subheader("Previsualización")
    for nombre, df in [("Stock",stock),("OC",oc),("BOM",bom),("Forecast",fc)]:
        if df is not None:
            with st.expander(f"{nombre} — {len(df):,} filas"):
                st.dataframe(df.head(20), use_container_width=True)
