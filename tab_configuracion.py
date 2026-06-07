import streamlit as st


def render_tab_configuracion():
    st.header("Configuración")

    col1, col2 = st.columns(2)
    with col1:
        nuevo_hz = st.number_input("Horizonte de planificación (meses)", 1, 6,
                                   st.session_state.horizonte)
        if nuevo_hz != st.session_state.horizonte:
            st.session_state.horizonte = nuevo_hz
            st.session_state.mrp_desactualizado = True
    with col2:
        nuevo_mp = st.number_input("Múltiplo de compra (unidades)", 1,
                                   value=st.session_state.multiplo)
        if nuevo_mp != st.session_state.multiplo:
            st.session_state.multiplo = nuevo_mp
            st.session_state.mrp_desactualizado = True

    st.markdown("---")
    st.subheader("Distribución semanal (%)")
    st.caption("Define cómo se distribuye el forecast en semanas. Debe sumar 100.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Meses de 4 semanas** (default: 30/30/30/10)")
        cols4 = st.columns(4)
        nd4 = [cols4[i].number_input(f"S{i+1}", 0, 100,
               st.session_state.dist_4[i], key=f"d4_{i}") for i in range(4)]
        if sum(nd4) == 100:
            if nd4 != st.session_state.dist_4:
                st.session_state.dist_4 = nd4
                st.session_state.mrp_desactualizado = True
        else:
            st.warning(f"Suma: {sum(nd4)}% — debe ser 100%")
    with c2:
        st.markdown("**Meses de 5 semanas** (default: 25/25/25/15/10)")
        cols5 = st.columns(5)
        nd5 = [cols5[i].number_input(f"S{i+1}", 0, 100,
               st.session_state.dist_5[i], key=f"d5_{i}") for i in range(5)]
        if sum(nd5) == 100:
            if nd5 != st.session_state.dist_5:
                st.session_state.dist_5 = nd5
                st.session_state.mrp_desactualizado = True
        else:
            st.warning(f"Suma: {sum(nd5)}% — debe ser 100%")

    st.markdown("---")
    st.subheader("Lead times por tipo de insumo")
    st.caption("Días corridos desde emisión de OC hasta recepción.")
    if st.session_state.stock is not None:
        tipos    = sorted(st.session_state.stock["tipo_insumo"].dropna().unique().tolist())
        new_lt   = {}
        cols_lt  = st.columns(min(3, len(tipos)))
        for i, tipo in enumerate(tipos):
            with cols_lt[i % 3]:
                new_lt[tipo] = st.number_input(tipo, 1, 365,
                    st.session_state.lead_times.get(tipo, 15), key=f"lt_{tipo}")
        if st.button("✓ Guardar lead times", type="primary"):
            if new_lt != st.session_state.lead_times:
                st.session_state.lead_times = new_lt
                st.session_state.mrp_desactualizado = True
            st.success("Lead times guardados.")
    else:
        st.info("Cargá el stock para configurar los lead times.")
