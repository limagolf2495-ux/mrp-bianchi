import pandas as pd
import streamlit as st

import tema
from config import GD_IDS, MESES, get_hoy, DEFAULTS, COLS_STOCK_REQ, COLS_OC_REQ, COLS_BOM_REQ
from gsheets import cargar_lead_times, cargar_plan_produccion, merge_oc_estados, obtener_fechas_drive
from helpers import filtrar_oc_relevantes, gsheet_url, validar_columnas
from precios import procesar_precios_pbi
from sidebar import render_sidebar
from tab_cashflow import render_tab_cashflow
from tab_configuracion import render_tab_configuracion
from tab_datos import render_tab_datos
from tab_mrp import render_tab_mrp
from tab_oc import render_tab_oc
from tab_planificacion import render_tab_planificacion
from tab_produccion import render_tab_produccion

st.set_page_config(page_title="MRP — Bodegas Bianchi", page_icon="🍷", layout="wide")
tema.inject()

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-load Google Drive ─────────────────────────────────────────────────────
if not st.session_state.gd_cargado:
    with st.spinner("Cargando datos desde Google Drive..."):
        st.session_state.gd_fechas = obtener_fechas_drive()

        _url = gsheet_url(GD_IDS["stock"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_STOCK_REQ, "stock (Google Drive)")
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
            st.session_state.stock = df
            _f_stock = st.session_state.gd_fechas.get("stock")
            st.session_state.fecha_corte_stock = _f_stock.date() if _f_stock else get_hoy()
        except ValueError as e:
            st.error(f"⚠️ Stock — {e}")
        except Exception as e:
            st.error(f"⚠️ Stock — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["ordenes"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_OC_REQ, "ordenes (Google Drive)")
            df["cantidad_oc"] = pd.to_numeric(df["cantidad_oc"], errors="coerce").fillna(0)
            df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce").dt.date
            st.session_state.oc_raw = df
        except ValueError as e:
            st.error(f"⚠️ Órdenes de compra — {e}")
        except Exception as e:
            st.error(f"⚠️ Órdenes de compra — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["bom"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_BOM_REQ, "bom (Google Drive)")
            df["cantidad_por_unidad"] = pd.to_numeric(df["cantidad_por_unidad"], errors="coerce").fillna(0)
            st.session_state.bom = df
        except ValueError as e:
            st.error(f"⚠️ BOM — {e}")
        except Exception as e:
            st.error(f"⚠️ BOM — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["forecast"], "xlsx")
        try:
            df = pd.read_excel(_url)
            new_cols = []
            for col in df.columns:
                if hasattr(col, "month"):
                    new_cols.append(f"{MESES[col.month-1]}_{str(col.year)[-2:]}")
                else:
                    new_cols.append(str(col).strip().lower())
            df.columns = new_cols
            df = df.loc[:, ~df.columns.duplicated()]
            df = df.loc[:, df.columns != "nan"]
            df = df.dropna(how="all")
            df["articulo"] = df["articulo"].astype(str).str.strip()
            for col in df.columns:
                if col not in ["articulo", "descripcion"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            st.session_state.forecast = df
            st.session_state.prod_listo = False
        except ValueError as e:
            st.error(f"⚠️ Forecast — {e}")
        except Exception as e:
            st.error(f"⚠️ Forecast — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["stock_pt"])
        try:
            df = pd.read_csv(_url, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["stock_pt"] = pd.to_numeric(df["stock_pt"], errors="coerce").fillna(0)
            df["articulo"] = df["articulo"].astype(str).str.strip()
            st.session_state.stock_pt = df
        except Exception as e:
            st.warning(f"⚠️ Stock PT — no se pudo cargar desde Google Drive: {e}")

        _hoy_gd = get_hoy()
        _url = gsheet_url(GD_IDS["ventas"])
        try:
            df = pd.read_csv(_url, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["articulo"] = df["articulo"].astype(str).str.strip()
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=False)
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
            df = df[(df["fecha"].dt.month == _hoy_gd.month) & (df["fecha"].dt.year == _hoy_gd.year)]
            df = df.groupby("articulo", as_index=False)["cantidad"].sum()
            df = df.rename(columns={"cantidad": "ventas_mes"})
            st.session_state.ventas_pt = df
        except Exception as e:
            st.warning(f"⚠️ Ventas — no se pudo cargar desde Google Drive: {e}")

        _url = gsheet_url(GD_IDS["pedidos"])
        try:
            df = pd.read_csv(_url, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["articulo"] = df["articulo"].astype(str).str.strip()
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=False)
                df = df[(df["fecha"].dt.month == _hoy_gd.month) & (df["fecha"].dt.year == _hoy_gd.year)]
            df = df.groupby("articulo", as_index=False)["cantidad"].sum()
            df = df.rename(columns={"cantidad": "pedidos_mes"})
            st.session_state.pedidos_pt = df
        except Exception as e:
            st.warning(f"⚠️ Pedidos — no se pudo cargar desde Google Drive: {e}")

        _url = gsheet_url(GD_IDS["precios"])
        try:
            df = pd.read_csv(_url, dtype=str)
            df_proc, cols_fail = procesar_precios_pbi(df)
            if df_proc is not None:
                st.session_state.precios = df_proc
            else:
                st.warning(f"⚠️ Precios — columnas requeridas no encontradas "
                           f"(articulo, fecha_recepcion, costo_unitario). Columnas: {cols_fail}")
        except Exception as e:
            st.warning(f"⚠️ Precios — no se pudo cargar desde Google Drive: {e}")

        # OC: filtrar por insumos con demanda en el forecast y recién ahí mergear estados
        if st.session_state.oc_raw is not None:
            oc_filtrado, n_desc = filtrar_oc_relevantes(
                st.session_state.oc_raw, st.session_state.bom, st.session_state.forecast)
            st.session_state.oc = oc_filtrado
            st.session_state.oc_descartadas = n_desc
            merge_oc_estados(oc_filtrado)

    st.session_state.gd_cargado = True

# ── Auto-cargar plan de producción guardado ────────────────────────────────────
if not st.session_state.plan_produccion_cargado:
    plan_gs, err_plan = cargar_plan_produccion()
    if plan_gs and not st.session_state.produccion:
        st.session_state.produccion = plan_gs
        st.session_state.prod_listo = True
        st.session_state.plan_calculado = True
    st.session_state.plan_produccion_cargado = True

# ── Auto-cargar lead times guardados ───────────────────────────────────────────
if not st.session_state.lead_times_cargados:
    lt_gs, err_lt = cargar_lead_times()
    if lt_gs:
        st.session_state.lead_times = lt_gs
    st.session_state.lead_times_cargados = True

# ── Sidebar ────────────────────────────────────────────────────────────────────
render_sidebar()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_datos, tab_oc, tab_plan, tab_prod, tab_mrp, tab_cf, tab_cfg = st.tabs(
    ["📋 Datos", "🧾 OC", "📊 Planificación", "🏭 Producción", "📦 MRP", "💰 Cash-Flow", "⚙️ Configuración"]
)

with tab_datos:
    render_tab_datos()
with tab_oc:
    render_tab_oc()
with tab_plan:
    render_tab_planificacion()
with tab_prod:
    render_tab_produccion()
with tab_mrp:
    render_tab_mrp()
with tab_cf:
    render_tab_cashflow()
with tab_cfg:
    render_tab_configuracion()
