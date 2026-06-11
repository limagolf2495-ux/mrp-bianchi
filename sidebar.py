import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DEFAULTS, get_hoy, MESES, COLS_STOCK_REQ, COLS_OC_REQ, COLS_BOM_REQ
from gsheets import merge_oc_estados
from helpers import filtrar_oc_relevantes, validar_columnas
from precios import procesar_precios_pbi


def _help_drive(key, fallback=None):
    """Tooltip con la fecha de última actualización del archivo en Drive."""
    f = st.session_state.gd_fechas.get(key)
    if f:
        return f"Última actualización en Drive: {f.strftime('%d/%m/%Y %H:%M')}"
    return fallback


def _refiltrar_oc():
    """Re-aplica el filtro de OC relevantes y reconstruye estados."""
    if st.session_state.oc_raw is None:
        return
    oc_filtrado, n_desc = filtrar_oc_relevantes(
        st.session_state.oc_raw, st.session_state.bom, st.session_state.forecast)
    st.session_state.oc = oc_filtrado
    st.session_state.oc_descartadas = n_desc
    merge_oc_estados(oc_filtrado)


def render_sidebar():
    hoy = get_hoy()
    uk = st.session_state.uploader_key
    with st.sidebar:
        _logo = Path(__file__).parent / "logo_bianchi.png"
        if _logo.exists():
            _b64 = base64.b64encode(_logo.read_bytes()).decode()
            st.markdown(
                f'<img src="data:image/png;base64,{_b64}" '
                f'style="width:170px;display:block;margin:0 0 4px -6px;">',
                unsafe_allow_html=True,
            )
        else:
            st.markdown("### 🍷 Bodegas Bianchi")
        st.caption("MRP · Plan de Compras de Insumos")
        st.markdown("---")

        f = st.file_uploader("📦 stock.csv", type=["csv"], key=f"up_stock_{uk}",
                             help=_help_drive("stock"))
        if f and f.file_id != st.session_state.fid_stock:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                validar_columnas(df, COLS_STOCK_REQ, "stock.csv")
                df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
                st.session_state.stock = df
                st.session_state.fid_stock = f.file_id
                st.session_state.fecha_corte_stock = hoy
                st.session_state.mrp_desactualizado = True
                st.success(f"✓ {len(df):,} insumos")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No se pudo leer '{f.name}': {e}")

        f = st.file_uploader("🛒 ordenes.csv", type=["csv"], key=f"up_oc_{uk}",
                             help=_help_drive("ordenes"))
        if f and f.file_id != st.session_state.fid_oc:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                validar_columnas(df, COLS_OC_REQ, "ordenes.csv")
                df["cantidad_oc"] = pd.to_numeric(df["cantidad_oc"], errors="coerce").fillna(0)
                df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce").dt.date
                st.session_state.oc_raw = df
                st.session_state.fid_oc = f.file_id
                st.session_state.mrp_desactualizado = True
                _refiltrar_oc()
                n_desc = st.session_state.oc_descartadas
                msg = f"✓ {len(st.session_state.oc):,} líneas OC"
                if n_desc:
                    msg += f" ({n_desc:,} descartadas: insumos sin demanda en forecast)"
                st.success(msg)
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No se pudo leer '{f.name}': {e}")

        f = st.file_uploader("🔗 bom.csv", type=["csv"], key=f"up_bom_{uk}",
                             help=_help_drive("bom"))
        if f and f.file_id != st.session_state.fid_bom:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                validar_columnas(df, COLS_BOM_REQ, "bom.csv")
                df["cantidad_por_unidad"] = pd.to_numeric(df["cantidad_por_unidad"], errors="coerce").fillna(0)
                st.session_state.bom = df
                st.session_state.fid_bom = f.file_id
                st.session_state.mrp_desactualizado = True
                _refiltrar_oc()
                st.success(f"✓ {len(df):,} relaciones BOM")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No se pudo leer '{f.name}': {e}")

        f = st.file_uploader("📊 forecast.xlsx", type=["xlsx","xls"], key=f"up_fc_{uk}",
                             help=_help_drive("forecast"))
        if f and f.file_id != st.session_state.fid_fc:
            try:
                df = pd.read_excel(f)
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
                    if col not in ["articulo","descripcion"]:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                st.session_state.forecast = df
                st.session_state.fid_fc = f.file_id
                st.session_state.prod_listo = False
                st.session_state.mrp_desactualizado = True
                _refiltrar_oc()
                meses_det = [c for c in df.columns if c not in ["articulo","descripcion"]]
                st.success(f"✓ {len(df):,} artículos | {', '.join(meses_det)}")
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No se pudo leer '{f.name}': {e}")

        st.markdown("---")
        st.caption("📊 Planificación")

        f = st.file_uploader("🏭 stock_pt.csv", type=["csv"], key=f"up_spt_{uk}",
                             help="Columnas: articulo, stock_pt")
        if f and f.file_id != st.session_state.fid_spt:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                df["stock_pt"] = pd.to_numeric(df["stock_pt"], errors="coerce").fillna(0)
                df["articulo"] = df["articulo"].astype(str).str.strip()
                st.session_state.stock_pt = df
                st.session_state.fid_spt = f.file_id
                st.session_state.plan_calculado = False
                st.success(f"✓ {len(df):,} artículos PT")
            except Exception as e: st.error(str(e))

        f = st.file_uploader("💰 ventas.csv", type=["csv"], key=f"up_ven_{uk}",
                             help="Columnas: articulo, fecha, cantidad")
        if f and f.file_id != st.session_state.fid_ven:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                df["articulo"] = df["articulo"].astype(str).str.strip()
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=False)
                df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                total_filas = len(df)
                df = df[df["fecha"].dt.month == hoy.month]
                df = df[df["fecha"].dt.year == hoy.year]
                df = df.groupby("articulo", as_index=False)["cantidad"].sum()
                df = df.rename(columns={"cantidad": "ventas_mes"})
                st.session_state.ventas_pt = df
                st.session_state.fid_ven = f.file_id
                st.session_state.plan_calculado = False
                st.success(f"✓ {len(df):,} artículos · {int(df['ventas_mes'].sum()):,} uds "
                           f"({total_filas:,} líneas → filtro {hoy.strftime('%b %Y')})")
            except Exception as e: st.error(str(e))

        f = st.file_uploader("📋 pedidos.csv", type=["csv"], key=f"up_ped_{uk}",
                             help="Columnas: articulo, fecha, cantidad")
        if f and f.file_id != st.session_state.fid_ped:
            try:
                df = pd.read_csv(f, dtype=str)
                df.columns = df.columns.str.strip().str.lower()
                df["articulo"] = df["articulo"].astype(str).str.strip()
                df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
                total_filas = len(df)
                if "fecha" in df.columns:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=False)
                    df = df[df["fecha"].dt.month == hoy.month]
                    df = df[df["fecha"].dt.year == hoy.year]
                    filtro_msg = f" → filtro {hoy.strftime('%b %Y')}"
                else:
                    filtro_msg = " · sin fecha (totales)"
                df = df.groupby("articulo", as_index=False)["cantidad"].sum()
                df = df.rename(columns={"cantidad": "pedidos_mes"})
                st.session_state.pedidos_pt = df
                st.session_state.fid_ped = f.file_id
                st.session_state.plan_calculado = False
                st.success(f"✓ {len(df):,} artículos · {int(df['pedidos_mes'].sum()):,} uds "
                           f"({total_filas:,} líneas{filtro_msg})")
            except Exception as e: st.error(str(e))

        st.markdown("---")
        st.caption("💰 Cash-Flow")

        f = st.file_uploader("💲 precios.csv / .xlsx", type=["csv","xlsx","xls"],
                             key=f"up_precios_{uk}",
                             help="Columnas requeridas: codigo, precio_unitario. Opcional: moneda")
        if f and f.file_id != st.session_state.fid_precios:
            try:
                if f.name.endswith(".csv"):
                    df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
                else:
                    df = pd.read_excel(f, dtype=str)
                df_proc, cols_fail = procesar_precios_pbi(df)
                if df_proc is not None:
                    st.session_state.precios = df_proc
                    st.session_state.fid_precios = f.file_id
                    st.session_state.precios_col_candidatas = None
                    st.success(f"✓ {len(df_proc):,} insumos · último precio por fecha")
                else:
                    st.session_state.precios_col_candidatas = cols_fail
                    st.error(f"No se encontraron las columnas requeridas "
                             f"(articulo, fecha_recepcion, costo_unitario). "
                             f"Columnas del archivo: {cols_fail}")
            except Exception as e:
                st.error(str(e))

        st.markdown("---")
        for nombre, key, gd_key in [("Stock","stock","stock"),("OC","oc","ordenes"),
                                     ("BOM","bom","bom"),("Forecast","forecast","forecast")]:
            ok = st.session_state[key] is not None
            fgd = st.session_state.gd_fechas.get(gd_key)
            sufijo = f" · {fgd.strftime('%d/%m')}" if ok and fgd else ""
            st.markdown(f"{'✅' if ok else '⬜'} {nombre}{sufijo}")
        for nombre, key in [("Stock PT","stock_pt"),("Ventas","ventas_pt"),("Pedidos","pedidos_pt")]:
            ok = st.session_state[key] is not None
            st.markdown(f"{'✅' if ok else '⬜'} {nombre}")
        if st.session_state.precios is not None:
            prec_df = st.session_state.precios
            if "fecha_ultima_oc" in prec_df.columns:
                dias_ant = (pd.Timestamp.today() - prec_df["fecha_ultima_oc"].max()).days
                st.markdown(f"✅ Precios · {dias_ant}d")
            else:
                st.markdown("✅ Precios")
        else:
            st.markdown("⬜ Precios")

        st.markdown("---")
        if st.button("🗑️ Limpiar todo", use_container_width=True):
            for k, v in DEFAULTS.items():
                st.session_state[k] = v
            st.session_state.uploader_key += 1
            st.rerun()
