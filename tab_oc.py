import pandas as pd
import streamlit as st

import tema
from config import get_hoy, COL_OC_COD, COL_OC_QTY, COL_OC_FECHA, COL_OC_ID
from gsheets import guardar_oc_estados


def _oc_entries():
    """Lista plana de líneas OC con índice posicional i por código,
    consistente con gsheets.py / mrp_calc.py / tab_mrp.py."""
    oc_df = st.session_state.oc
    tiene_id = COL_OC_ID in oc_df.columns
    por_cod = {}
    lineas = []
    for _, r in oc_df.iterrows():
        cod = str(r[COL_OC_COD]); fec = r[COL_OC_FECHA]; qty = float(r[COL_OC_QTY])
        if pd.isna(fec):
            continue
        i = len(por_cod.setdefault(cod, []))
        por_cod[cod].append((fec, qty))
        oc_id = str(r[COL_OC_ID]) if tiene_id and pd.notna(r[COL_OC_ID]) else ""
        lineas.append({"cod": cod, "i": i, "fec": fec, "qty": qty, "id": oc_id})
    return lineas, tiene_id


def _recalc_venc_parcial(lineas, hoy):
    """Reconstruye mrp_oc_venc_parcial a partir de los estados actuales."""
    parcial = {}
    estados = st.session_state.mrp_oc_estados
    for ln in lineas:
        if ln["fec"] < hoy and estados.get(ln["cod"], {}).get(ln["i"]) == "🕐 Pendiente":
            parcial[ln["cod"]] = parcial.get(ln["cod"], 0.0) + ln["qty"]
    st.session_state.mrp_oc_venc_parcial = parcial


def _set_estado(lineas_sel, estado, hoy, todas):
    """Aplica un estado a un conjunto de líneas vencidas y persiste."""
    for ln in lineas_sel:
        if estado == "🕐 Pendiente":
            st.session_state.mrp_oc_estados.setdefault(ln["cod"], {})[ln["i"]] = estado
        else:
            st.session_state.mrp_oc_estados.get(ln["cod"], {}).pop(ln["i"], None)
            st.session_state.mrp_oc_nueva_fecha.get(ln["cod"], {}).pop(ln["i"], None)
    _recalc_venc_parcial(todas, hoy)
    st.session_state.mrp_desactualizado = True
    guardar_oc_estados()
    st.rerun()


def render_tab_oc():
    hoy = get_hoy()
    st.header("Órdenes de compra")

    if st.session_state.oc is None:
        st.info("Cargá las órdenes de compra para gestionarlas.")
        return

    lineas, tiene_id = _oc_entries()
    vencidas = [ln for ln in lineas if ln["fec"] < hoy]

    estados_ss = st.session_state.mrp_oc_estados
    nuevas_ss  = st.session_state.mrp_oc_nueva_fecha
    n_pend     = sum(1 for ln in vencidas
                     if estados_ss.get(ln["cod"], {}).get(ln["i"]) == "🕐 Pendiente")
    n_repro    = sum(1 for ln in vencidas
                     if nuevas_ss.get(ln["cod"], {}).get(ln["i"]))

    n_desc = st.session_state.oc_descartadas
    cards = [
        {"lbl": "Líneas OC", "val": len(lineas),
         "sub": f"abiertas · {n_desc:,} sin demanda" if n_desc else "abiertas en JDE"},
        {"lbl": "Vencidas", "val": len(vencidas), "sub": "entrega anterior a hoy",
         "kind": "crit" if vencidas else "ok"},
        {"lbl": "Pendientes", "val": n_pend, "sub": "suman a cobertura", "kind": "warn"},
        {"lbl": "Reprogramadas", "val": n_repro, "sub": "con nueva fecha"},
    ]
    precios = st.session_state.precios
    if precios is not None and vencidas:
        pmap = dict(zip(precios["codigo"].astype(str), precios["precio_unitario"]))
        monto = sum(ln["qty"] * pmap.get(ln["cod"], 0) for ln in vencidas)
        cards.append({"lbl": "Monto vencido", "val": f"${monto:,.0f}",
                      "sub": "valorizado a último costo"})
    st.markdown(tema.cards(cards), unsafe_allow_html=True)
    st.markdown("")

    if not vencidas:
        st.success("✅ No hay OC vencidas para gestionar.")
        return

    desc_map = {}
    stock_df = st.session_state.stock
    if stock_df is not None:
        desc_map = dict(zip(stock_df["codigo"].astype(str),
                            stock_df["descripcion"].astype(str)))

    st.subheader("Gestión de OC vencidas")
    st.caption("🕐 **Pendiente** = la entrega sigue en pie y suma a la cobertura del MRP. "
               "⚠️ **Vencida** = no se cuenta con esa mercadería. "
               "Si el proveedor confirmó una nueva fecha, cargala en **Nueva fecha** "
               "(pasa a contar como OC vigente en esa semana).")

    # ── Acción por N° de OC ────────────────────────────────────────────────────
    if tiene_id:
        ids_venc = {}
        for ln in vencidas:
            if ln["id"]:
                d = ids_venc.setdefault(ln["id"], {"n": 0, "qty": 0.0})
                d["n"] += 1; d["qty"] += ln["qty"]
        if ids_venc:
            col_ms, col_bp, col_bi = st.columns([4, 1.6, 1.6])
            with col_ms:
                sel_ids = st.multiselect(
                    "Acción por N° de OC", sorted(ids_venc),
                    format_func=lambda x: f"{x} — {ids_venc[x]['n']} línea(s), "
                                          f"{ids_venc[x]['qty']:,.0f} u.",
                    placeholder="Elegí una o más órdenes...")
            lineas_ids = [ln for ln in vencidas if ln["id"] in sel_ids]
            with col_bp:
                st.markdown("<div style='height:1.8em'></div>", unsafe_allow_html=True)
                if st.button("🕐 Marcar Pendiente", disabled=not sel_ids,
                             use_container_width=True, key="oc_ids_pend"):
                    _set_estado(lineas_ids, "🕐 Pendiente", hoy, lineas)
            with col_bi:
                st.markdown("<div style='height:1.8em'></div>", unsafe_allow_html=True)
                if st.button("↺ Ignorar", disabled=not sel_ids,
                             use_container_width=True, key="oc_ids_ign"):
                    _set_estado(lineas_ids, "⚠️ Vencida", hoy, lineas)

    # ── Botones globales ───────────────────────────────────────────────────────
    col_g1, col_g2, _ = st.columns([1.8, 1.8, 5])
    with col_g1:
        if st.button("🕐 Todas en Pendiente", use_container_width=True, key="oc_all_pend"):
            _set_estado(vencidas, "🕐 Pendiente", hoy, lineas)
    with col_g2:
        if st.button("↺ Restablecer todas", use_container_width=True, key="oc_all_reset"):
            _set_estado(vencidas, "⚠️ Vencida", hoy, lineas)

    # ── Filtros ────────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        ids_u = sorted(set(ln["id"] for ln in vencidas if ln["id"]))
        f_id = st.selectbox("N° de OC", ["Todas"] + ids_u) if tiene_id and ids_u else "Todas"
    with fc2:
        f_txt = st.text_input("Insumo", placeholder="🔍 Código o descripción...")
    with fc3:
        f_est = st.selectbox("Estado", ["Todos", "⚠️ Vencida", "🕐 Pendiente"])

    venc_f = vencidas[:]
    if f_id != "Todas":
        venc_f = [ln for ln in venc_f if ln["id"] == f_id]
    if f_txt:
        t = f_txt.lower()
        venc_f = [ln for ln in venc_f if t in ln["cod"].lower()
                  or t in desc_map.get(ln["cod"], "").lower()]
    if f_est != "Todos":
        venc_f = [ln for ln in venc_f
                  if estados_ss.get(ln["cod"], {}).get(ln["i"], "⚠️ Vencida") == f_est]

    if not venc_f:
        st.info("Ninguna OC vencida coincide con el filtro.")
        return

    # ── Tabla editable ─────────────────────────────────────────────────────────
    rows = []
    for ln in venc_f:
        rows.append({
            "N° OC": ln["id"],
            "Código": ln["cod"],
            "Descripción": desc_map.get(ln["cod"], ""),
            "Fecha entrega": ln["fec"],
            "Cantidad": int(ln["qty"]),
            "Estado": estados_ss.get(ln["cod"], {}).get(ln["i"], "⚠️ Vencida"),
            "Nueva fecha": nuevas_ss.get(ln["cod"], {}).get(ln["i"]),
        })
    df = pd.DataFrame(rows)

    col_cfg = {
        "N° OC": st.column_config.TextColumn("N° OC", disabled=True, width="small"),
        "Código": st.column_config.TextColumn("Código", disabled=True, width="small"),
        "Descripción": st.column_config.TextColumn("Descripción", disabled=True, width="large"),
        "Fecha entrega": st.column_config.DateColumn("Fecha entrega", disabled=True),
        "Cantidad": st.column_config.NumberColumn("Cantidad", disabled=True, format="%d"),
        "Estado": st.column_config.SelectboxColumn("Estado",
            options=["⚠️ Vencida", "🕐 Pendiente"], required=True,
            help="🕐 Pendiente suma a la cobertura del MRP"),
        "Nueva fecha": st.column_config.DateColumn("Nueva fecha", min_value=hoy,
            help="Nueva fecha de entrega confirmada por el proveedor. "
                 "Al cargarla, la línea pasa automáticamente a 🕐 Pendiente."),
    }
    col_order = (["N° OC"] if tiene_id else []) + \
        ["Código", "Descripción", "Fecha entrega", "Cantidad", "Estado", "Nueva fecha"]

    edited = st.data_editor(
        df, use_container_width=True, hide_index=True, height=480,
        column_config=col_cfg, column_order=col_order,
        key=f"oc_lote_editor_{f_id}_{f_txt}_{f_est}",
    )

    # ── Diff y persistencia ────────────────────────────────────────────────────
    cambios = False
    for pos, row in edited.iterrows():
        ln = venc_f[pos]
        cod, i = ln["cod"], ln["i"]
        nf = row["Nueva fecha"]
        nf = None if pd.isna(nf) else (nf.date() if hasattr(nf, "date") else nf)
        est = row["Estado"]
        if nf:
            est = "🕐 Pendiente"  # nueva fecha implica Pendiente

        est_prev = estados_ss.get(cod, {}).get(i, "⚠️ Vencida")
        nf_prev  = nuevas_ss.get(cod, {}).get(i)
        if est == est_prev and nf == nf_prev:
            continue
        cambios = True
        if est == "🕐 Pendiente":
            st.session_state.mrp_oc_estados.setdefault(cod, {})[i] = est
        else:
            st.session_state.mrp_oc_estados.get(cod, {}).pop(i, None)
            nf = None
        if nf:
            st.session_state.mrp_oc_nueva_fecha.setdefault(cod, {})[i] = nf
        else:
            st.session_state.mrp_oc_nueva_fecha.get(cod, {}).pop(i, None)

    if cambios:
        _recalc_venc_parcial(lineas, hoy)
        st.session_state.mrp_desactualizado = True
        guardar_oc_estados()
        st.rerun()

    total_pend = sum(st.session_state.mrp_oc_venc_parcial.values())
    if total_pend > 0:
        st.caption(f"🕐 {round(total_pend):,} unidades vencidas suman a cobertura. "
                   f"Recalculá el MRP en la pestaña 📦 MRP para aplicar.")
