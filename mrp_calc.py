from datetime import date, timedelta

import pandas as pd
import streamlit as st

from config import (get_hoy,
                    COL_STOCK_COD, COL_STOCK_DESC, COL_STOCK_TIPO, COL_STOCK_QTY,
                    COL_OC_COD, COL_OC_QTY, COL_OC_FECHA,
                    COL_BOM_ART, COL_BOM_INS, COL_BOM_QTY)
from helpers import mes_key, semanas_desde_hoy, semanas_del_mes, distribuir, ceil_multiplo, semaforo


def calcular_mrp():
    stock_df  = st.session_state.stock
    oc_df     = st.session_state.oc
    bom_df    = st.session_state.bom
    fc_df     = st.session_state.forecast
    prod      = st.session_state.produccion
    horizonte = st.session_state.horizonte
    multiplo  = st.session_state.multiplo

    hoy        = get_hoy()
    todas_sems = []
    sems_actual = semanas_desde_hoy(hoy.year, hoy.month)
    mes_n_act   = hoy.strftime("%b")
    for sl, ss, se in sems_actual:
        todas_sems.append((f"{mes_n_act} {sl}", ss, se))
    for m in range(1, horizonte + 1):
        mes0  = (hoy.month - 1 + m) % 12
        año_f = hoy.year + (hoy.month - 1 + m) // 12
        sems_f  = semanas_del_mes(año_f, mes0 + 1)
        mes_n_f = date(año_f, mes0 + 1, 1).strftime("%b")
        for sl, ss, se in sems_f:
            todas_sems.append((f"{mes_n_f} {sl}", ss, se))

    n_sems = len(todas_sems)
    if n_sems == 0:
        st.error(
            "El horizonte de planificación no contiene semanas. "
            "Revisá el parámetro 'Horizonte (meses)' en la configuración, "
            "o ejecutá el MRP antes del último día del mes."
        )
        return
    sem_headers = [s[0] for s in todas_sems]
    limite_hz   = todas_sems[-1][2]

    stock_map = {
        str(r[COL_STOCK_COD]): {"stock": float(r[COL_STOCK_QTY]),
                                 "desc": str(r[COL_STOCK_DESC]),
                                 "tipo": str(r[COL_STOCK_TIPO])}
        for _, r in stock_df.iterrows()
    }

    oc_vigente = {}
    oc_vencida_total = {}
    oc_venc_parcial_local = {}
    oc_no_pagada = {}
    oc_detalle = {}
    if oc_df is not None:
        oc_estados_ss = st.session_state.mrp_oc_estados
        oc_pagada_ss  = st.session_state.mrp_oc_pagada
        oc_nuevas_ss  = st.session_state.mrp_oc_nueva_fecha

        oc_by_cod = {}
        for _, r in oc_df.iterrows():
            cod = str(r[COL_OC_COD])
            qty = float(r[COL_OC_QTY])
            fec = r[COL_OC_FECHA]
            oc_id = str(r["id"]) if "id" in r.index and pd.notna(r["id"]) else ""
            if pd.isna(fec): continue
            oc_by_cod.setdefault(cod, []).append((fec, qty, oc_id))

        for cod, entries in oc_by_cod.items():
            tipo       = stock_map.get(cod, {}).get("tipo", "")
            estados_cod = oc_estados_ss.get(cod, {})
            pagos_cod   = oc_pagada_ss.get(cod, {})
            nuevas_cod  = oc_nuevas_ss.get(cod, {})
            for i, (fec, qty, oc_id) in enumerate(entries):
                nueva_fec    = nuevas_cod.get(i)
                fec_efectiva = nueva_fec if nueva_fec else fec
                raw_estado = "⚠️ Vencida" if fec < hoy else "✅ Vigente"
                oc_detalle.setdefault(cod, []).append({
                    "N° OC": oc_id,
                    "Fecha entrega": fec, "Cantidad OC": qty,
                    "Estado": raw_estado, "Nueva fecha": nueva_fec,
                })
                pagada = pagos_cod.get(i, False)
                if fec_efectiva < hoy:
                    oc_vencida_total[cod] = oc_vencida_total.get(cod, 0) + qty
                    if estados_cod.get(i) == "🕐 Pendiente":
                        oc_venc_parcial_local[cod] = oc_venc_parcial_local.get(cod, 0) + qty
                        if not pagada:
                            oc_no_pagada.setdefault(cod, []).append(
                                {"fec": fec_efectiva, "qty": qty, "tipo": tipo})
                elif fec_efectiva <= limite_hz:
                    if fec < hoy:
                        # vencida reprogramada a futuro: cuenta como vigente
                        oc_vencida_total[cod] = oc_vencida_total.get(cod, 0) + qty
                    oc_vigente[cod] = oc_vigente.get(cod, 0) + qty
                    if not pagada:
                        oc_no_pagada.setdefault(cod, []).append(
                            {"fec": fec_efectiva, "qty": qty, "tipo": tipo})

    dem = {}
    mes_act_key = mes_key(hoy.year, hoy.month - 1)
    arts_en_prod = set(prod.keys())
    for art, datos in prod.items():
        for i in range(len(sems_actual)):
            q = datos.get(f"s{i+1}", 0)
            if q: dem[(art, i)] = dem.get((art, i), 0) + q

    if fc_df is not None and mes_act_key in fc_df.columns:
        n_sa = len(sems_actual)
        dist_act = st.session_state.dist_4 if n_sa <= 4 else st.session_state.dist_5
        for _, r in fc_df.iterrows():
            art = str(r["articulo"])
            if art in arts_en_prod: continue
            fc_q = float(r[mes_act_key]) if pd.notna(r.get(mes_act_key, 0)) else 0
            if fc_q <= 0: continue
            vals = distribuir(fc_q, n_sa, dist_act)
            for j, v in enumerate(vals):
                if v: dem[(art, j)] = dem.get((art, j), 0) + v

    if fc_df is not None:
        offset = len(sems_actual)
        for m in range(1, horizonte + 1):
            mes0   = (hoy.month - 1 + m) % 12
            año_f  = hoy.year + (hoy.month - 1 + m) // 12
            key_fc = mes_key(año_f, mes0)
            sems_f = semanas_del_mes(año_f, mes0 + 1)
            n_sf   = len(sems_f)
            dist_f = st.session_state.dist_4 if n_sf <= 4 else st.session_state.dist_5
            if key_fc in fc_df.columns:
                for _, r in fc_df.iterrows():
                    art  = str(r["articulo"])
                    fc_q = float(r[key_fc]) if pd.notna(r[key_fc]) else 0
                    if fc_q <= 0: continue
                    vals = distribuir(fc_q, n_sf, dist_f)
                    for j, v in enumerate(vals):
                        if v: dem[(art, offset + j)] = dem.get((art, offset + j), 0) + v
            offset += n_sf

    bom_idx = {}
    marca_idx = {}
    art_desc_idx = {}
    bom_invalidas = []
    for _, r in bom_df.iterrows():
        art   = str(r[COL_BOM_ART])
        ins   = str(r[COL_BOM_INS])
        qty_u = float(r[COL_BOM_QTY])
        if qty_u <= 0:
            bom_invalidas.append(f"{art}/{ins}")
            continue
        bom_idx.setdefault(art, []).append((ins, qty_u))
        marca_val = str(r.get("marca", "")).strip()
        if marca_val:
            marca_idx.setdefault(ins, set()).add(marca_val)
        desc_art = str(r.get("descripcion_articulo", "")).strip()
        if desc_art:
            art_desc_idx[art] = desc_art
    if bom_invalidas:
        st.warning(
            f"BOM: {len(bom_invalidas)} relación(es) con 'cantidad_por_unidad' ≤ 0 ignoradas — "
            f"no generan demanda de insumo. "
            f"Verificá las filas: {', '.join(bom_invalidas[:8])}"
            + (" ..." if len(bom_invalidas) > 8 else "")
        )

    ins_arts = {}
    nec = {}
    for (art, si), q in dem.items():
        if q <= 0 or art not in bom_idx: continue
        for cod, qty_u in bom_idx[art]:
            ins_arts.setdefault(cod, set()).add(art)
            k = (cod, si)
            nec[k] = nec.get(k, 0) + q * qty_u

    resultados = []
    for cod in set(c for c, _ in nec):
        s    = stock_map.get(cod, {"stock":0,"desc":cod,"tipo":"—"})
        stk  = s["stock"]
        oc_v = oc_vigente.get(cod, 0)
        oc_ve_total   = oc_vencida_total.get(cod, 0)
        oc_ve_parcial = oc_venc_parcial_local.get(cod, 0.0)
        cobert = stk + oc_v + oc_ve_parcial

        nec_sem   = [round(nec.get((cod, i), 0)) for i in range(n_sems)]
        total_nec = sum(nec_sem)

        cob_acum = cobert
        sems_cub = 0
        compra_sem = []
        for n in nec_sem:
            if n == 0:
                sems_cub += 1
                compra_sem.append(0)
            elif cob_acum >= n:
                cob_acum -= n
                sems_cub += 1
                compra_sem.append(0)
            else:
                compra_sem.append(max(0, n - round(cob_acum)))
                cob_acum = 0

        lt = st.session_state.lead_times.get(s["tipo"], 15)

        pedido_sem = [0] * n_sems
        for i, qty in enumerate(compra_sem):
            if qty <= 0:
                continue
            fec_nec_i = todas_sems[i][1]
            fec_ped_i = fec_nec_i - timedelta(days=lt)
            j_ped = None
            for j, (_sh, ss_j, se_j) in enumerate(todas_sems):
                if ss_j <= fec_ped_i <= se_j:
                    j_ped = j; break
            if j_ped is None:
                j_ped = 0
            pedido_sem[j_ped] += qty

        fecha_pedido   = "—"
        dias_cobertura = 0
        if sems_cub < n_sems:
            fec_nec = todas_sems[sems_cub][1]
            dias_cobertura = (fec_nec - hoy).days
            fec_ped = fec_nec - timedelta(days=lt)
            for sh, ss, se in todas_sems:
                if ss <= fec_ped <= se:
                    fecha_pedido = sh; break
            if fecha_pedido == "—":
                fecha_pedido = "⚠️ Atrasado"

        sem_ic, sem_lb, sem_kind = semaforo(sems_cub, n_sems, dias_cobertura, lt)
        dias_quiebre_num   = dias_cobertura if sems_cub < n_sems else 9999
        dias_quiebre_label = dias_cobertura if sems_cub < n_sems else None
        neta = max(0, total_nec - cobert)
        sug  = ceil_multiplo(neta, multiplo)

        oc_disp = round(oc_v + oc_ve_parcial)
        oc_disp_label = (f"{oc_disp:,} (incl. {round(oc_ve_parcial):,} venc.)"
                         if oc_ve_parcial > 0 else str(oc_disp))

        resultados.append({
            "sem_ic": sem_ic, "sem_lb": sem_lb, "sem_kind": sem_kind, "sems_cub": sems_cub,
            "Días al quiebre": dias_quiebre_label, "_dias_quiebre": dias_quiebre_num,
            "Tipo": s["tipo"], "Código": cod, "Descripción": s["desc"],
            "Stock": round(stk), "OC disp.": oc_disp, "_oc_label": oc_disp_label,
            "OC vencidas": round(oc_ve_total), "_oc_ve_parcial": round(oc_ve_parcial),
            "Nec. total": round(total_nec), "Nec. neta": round(neta),
            "Sugerencia": sug, "Pedir en": fecha_pedido,
            "Cobertura": nec_sem,
            "_compra_sem": compra_sem,
            **{sem_headers[i]: pedido_sem[i] for i in range(n_sems)},
            "_arts": list(ins_arts.get(cod, [])),
            "_arts_desc": [art_desc_idx.get(a, "") for a in ins_arts.get(cod, [])],
            "_oc_det": oc_detalle.get(cod, []),
            "_marcas": marca_idx.get(cod, set()),
        })

    orden = {"🔴":0,"🟡":1,"🟢":2}
    resultados.sort(key=lambda r: (orden.get(r["sem_ic"],3), r["_dias_quiebre"]))

    st.session_state.mrp_result         = resultados
    st.session_state.mrp_sem_headers    = sem_headers
    st.session_state.mrp_todas_sems     = todas_sems
    st.session_state.mrp_oc_no_pagada   = oc_no_pagada
    st.session_state.mrp_desactualizado = False
