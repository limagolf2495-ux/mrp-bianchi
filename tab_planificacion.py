import pandas as pd
import streamlit as st

import tema
from config import get_hoy
from gsheets import cargar_reglas_pt, guardar_reglas_pt
from helpers import distribuir, mes_key, semanas_desde_hoy
from planificacion import calcular_stock_objetivo


def render_tab_planificacion():
    hoy = get_hoy()
    mes_nombre_plan = hoy.strftime("%B %Y").capitalize()
    st.header(f"Planificación de Producción — {mes_nombre_plan}")

    if st.session_state.forecast is None or st.session_state.bom is None:
        st.info("Cargá el Forecast y el BOM para habilitar este módulo.")
        return

    fc_plan = st.session_state.forecast
    spt_df  = st.session_state.stock_pt
    ven_df  = st.session_state.ventas_pt
    ped_df  = st.session_state.pedidos_pt

    if not st.session_state.reglas_pt_cargadas:
        cargadas, err_reglas = cargar_reglas_pt()
        if err_reglas:
            st.warning(f"⚠️ No se pudieron cargar las reglas desde Google Sheets: {err_reglas}")
        elif cargadas:
            st.session_state.reglas_pt = cargadas
            st.toast(f"✓ {len(cargadas)} reglas cargadas desde Google Sheets")
        else:
            st.toast("ℹ️ Sin reglas guardadas — usando 1m por defecto")
        st.session_state.reglas_pt_cargadas = True

    mes_act_key_plan = mes_key(hoy.year, hoy.month - 1)

    rows_plan = []
    for _, row in fc_plan.iterrows():
        art  = str(row["articulo"])
        desc = str(row.get("descripcion", art))
        fc_m = float(row[mes_act_key_plan]) if (
            mes_act_key_plan in fc_plan.columns and pd.notna(row.get(mes_act_key_plan))
        ) else 0.0
        if fc_m <= 0:
            continue

        spt_val = 0.0
        if spt_df is not None:
            r = spt_df[spt_df["articulo"].astype(str) == art]
            if not r.empty: spt_val = float(r["stock_pt"].values[0])

        ven_val = 0.0
        if ven_df is not None:
            r = ven_df[ven_df["articulo"].astype(str) == art]
            if not r.empty: ven_val = float(r["ventas_mes"].values[0])

        ped_val = 0.0
        if ped_df is not None:
            r = ped_df[ped_df["articulo"].astype(str) == art]
            if not r.empty: ped_val = float(r["pedidos_mes"].values[0])

        regla   = st.session_state.reglas_pt.get(art, "1m")
        stk_obj = calcular_stock_objetivo(art, regla, fc_plan, mes_act_key_plan)
        plan_v  = max(0.0, ped_val + fc_m - ven_val - spt_val + stk_obj)

        rows_plan.append({
            "Artículo":    art,
            "Descripción": desc,
            "Forecast":    int(fc_m),
            "Ventas":      int(ven_val),
            "Pedidos":     int(ped_val),
            "Stock PT":    int(spt_val),
            "Stock Obj":   int(stk_obj),
            "Plan":        int(plan_v),
            "Regla":       regla,
        })

    df_plan_preview = pd.DataFrame(rows_plan)

    if not df_plan_preview.empty:
        _arts_prod  = int((df_plan_preview["Plan"] > 0).sum())
        _arts_cub   = int((df_plan_preview["Plan"] == 0).sum())
        _total_plan = int(df_plan_preview["Plan"].sum())
        _total_fc   = int(df_plan_preview["Forecast"].sum())
    else:
        _arts_prod = _arts_cub = _total_plan = _total_fc = 0

    st.markdown(tema.cards([
        {"lbl":"A producir",    "val":_arts_prod,        "sub":"artículos con plan > 0",
         "kind":"warn" if _arts_prod > 0 else "ok"},
        {"lbl":"Stock cubre",   "val":_arts_cub,         "sub":"plan = 0", "kind":"ok"},
        {"lbl":"Total plan",    "val":f"{_total_plan:,}", "sub":"unidades planificadas"},
        {"lbl":"Total forecast","val":f"{_total_fc:,}",  "sub":"demanda estimada del mes"},
    ]), unsafe_allow_html=True)
    st.markdown("")

    faltantes = [n for n, k in [("Stock PT","stock_pt"),("Ventas","ventas_pt"),("Pedidos","pedidos_pt")]
                 if st.session_state[k] is None]
    if faltantes:
        st.markdown(tema.banner(
            f"Datos faltantes: <strong>{', '.join(faltantes)}</strong> — se asumen en 0. "
            f"Cargalos desde el panel izquierdo.", "warn"), unsafe_allow_html=True)
    else:
        st.markdown(tema.banner(
            f"Todos los datos cargados · {len(df_plan_preview)} artículos · "
            f"Forecast <strong>{mes_act_key_plan}</strong>", "ok"), unsafe_allow_html=True)

    if st.session_state.plan_calculado:
        n_arts_conf = len(st.session_state.produccion)
        st.markdown(tema.banner(
            f"Plan confirmado · <strong>{n_arts_conf} artículos</strong> cargados al MRP · "
            f"Ir a la tab MRP para calcular", "ok"), unsafe_allow_html=True)

    st.markdown("")

    if df_plan_preview.empty:
        st.info(f"No hay artículos con forecast para {mes_act_key_plan}. "
                f"Verificá que el archivo Forecast tenga columna para el mes actual.")
        return

    plan_manual = st.session_state.get("plan_manual", False)
    if plan_manual:
        df_plan_preview["Plan"] = 0

    col_cfg_plan = {
        "Artículo":    st.column_config.TextColumn("Artículo", width="small", disabled=True),
        "Descripción": st.column_config.TextColumn("Descripción", width="large", disabled=True),
        "Forecast":    st.column_config.NumberColumn("Forecast", format="%d", disabled=True,
                       help="Forecast del mes actual"),
        "Ventas":      st.column_config.NumberColumn("Ventas", format="%d", disabled=True,
                       help="Ventas despachadas en el mes"),
        "Pedidos":     st.column_config.NumberColumn("Pedidos", format="%d", disabled=True,
                       help="OV ingresadas sin despachar"),
        "Stock PT":    st.column_config.NumberColumn("Stock PT", format="%d", disabled=True,
                       help="Stock de producto terminado disponible"),
        "Stock Obj":   st.column_config.NumberColumn("Stock Obj", format="%d", disabled=True,
                       help="Buffer objetivo calculado según la Regla"),
        "Plan":        st.column_config.NumberColumn("Plan", format="%d",
                       disabled=not plan_manual,
                       help="Calculado automáticamente · en modo manual podés editarlo directamente"),
        "Regla":       st.column_config.TextColumn("Regla", width="small",
                       help="1m = 1 mes cobertura, 2m = 2 meses, 30% = 30% del forecast, o número fijo"),
    }

    uk = st.session_state.uploader_key
    edited_plan = st.data_editor(
        df_plan_preview, column_config=col_cfg_plan,
        use_container_width=True, hide_index=True,
        num_rows="fixed", height=480,
        key=f"plan_editor_{uk}",
        column_order=["Artículo","Descripción","Forecast","Ventas","Pedidos",
                      "Stock PT","Stock Obj","Plan","Regla"],
    )

    st.caption(
        "Editá la columna **Regla** por artículo (ej: `1m`, `2m`, `30%`, `5000`) y "
        "hacé click en **Confirmar Plan**. El Plan y Stock Obj se recalculan al confirmar."
    )
    st.markdown("")

    col_conf_p, col_save_r, col_manual, _ = st.columns([2, 2, 2, 2])

    with col_conf_p:
        if st.button("⚡ Confirmar Plan", type="primary", use_container_width=True,
                     help="Aplica las reglas editadas y carga el plan al MRP"):
            new_reglas_plan = {
                str(er["Artículo"]): str(er.get("Regla", "1m")).strip() or "1m"
                for _, er in edited_plan.iterrows()
            }
            st.session_state.reglas_pt = new_reglas_plan

            sems_plan  = semanas_desde_hoy(hoy.year, hoy.month)
            n_sem_plan = len(sems_plan)
            dist_plan  = st.session_state.dist_4 if n_sem_plan <= 4 else st.session_state.dist_5

            nueva_prod_plan = {}
            for _, er in edited_plan.iterrows():
                art    = str(er["Artículo"])
                fc_a   = float(er["Forecast"])
                desc_a = str(er.get("Descripción", art))

                if plan_manual:
                    plan_a = max(0.0, float(er.get("Plan", 0)))
                else:
                    spt_a = 0.0
                    if spt_df is not None:
                        ra = spt_df[spt_df["articulo"].astype(str) == art]
                        if not ra.empty: spt_a = float(ra["stock_pt"].values[0])

                    ven_a = 0.0
                    if ven_df is not None:
                        ra = ven_df[ven_df["articulo"].astype(str) == art]
                        if not ra.empty: ven_a = float(ra["ventas_mes"].values[0])

                    ped_a = 0.0
                    if ped_df is not None:
                        ra = ped_df[ped_df["articulo"].astype(str) == art]
                        if not ra.empty: ped_a = float(ra["pedidos_mes"].values[0])

                    regla_a   = new_reglas_plan.get(art, "1m")
                    stk_obj_a = calcular_stock_objetivo(art, regla_a, fc_plan, mes_act_key_plan)
                    plan_a    = max(0.0, ped_a + fc_a - ven_a - spt_a + stk_obj_a)

                vals_a = distribuir(int(plan_a), n_sem_plan, dist_plan)
                nueva_prod_plan[art] = {
                    "desc": desc_a,
                    "forecast": fc_a,
                    **{f"s{i+1}": vals_a[i] for i in range(n_sem_plan)},
                }

            st.session_state.produccion = nueva_prod_plan
            st.session_state.prod_listo = True
            st.session_state.plan_calculado = True
            st.session_state.plan_manual = False
            st.session_state.mrp_desactualizado = True
            st.rerun()

    with col_save_r:
        if st.button("💾 Guardar Reglas", use_container_width=True,
                     help="Guarda las reglas en Google Sheets para próximas sesiones"):
            new_reglas_save = {
                str(er["Artículo"]): str(er.get("Regla", "1m")).strip() or "1m"
                for _, er in edited_plan.iterrows()
            }
            st.session_state.reglas_pt = new_reglas_save
            if guardar_reglas_pt(new_reglas_save):
                st.success("✓ Reglas guardadas en Google Sheets")
            st.rerun()

    with col_manual:
        if plan_manual:
            if st.button("↩ Recalcular", use_container_width=True,
                         help="Vuelve al plan calculado automáticamente"):
                st.session_state.plan_manual = False
                st.rerun()
        else:
            if st.button("🗑️ Plan en 0", use_container_width=True,
                         help="Pone todos los valores de Plan en 0 para ingreso manual"):
                st.session_state.plan_manual = True
                st.rerun()
