import streamlit as st
import pandas as pd
import math
import base64
from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
import calendar
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import tema

st.set_page_config(page_title="MRP — Bodegas Bianchi", page_icon="🍷", layout="wide")
tema.inject()

GD_IDS = {
    "stock":    "17TsFVJw12V5ndLP_TfVaeMvy-rRA1ScUGZCJIlifM38",
    "ordenes":  "11b__i6OcJUz1Duwzbyo6cy0pEXySob6oOXFpiS0lMCU",
    "bom":      "1CH7jaqmfYiefoGRkHj_n4PwDDnHy1fLX9cEz7dzgqCg",
    "forecast": "1TUEwHs4S7lVJWLAHGJNZd0ZoRDBO5VMGQ4wvq816cqo",
}
GD_ESTADOS_ID = "1CpDx8apuRtI4G3RfN1QXLqp-pEdkATX3haj6iIfCfyE"

def gsheet_url(sid, fmt="csv"):
    return f"https://docs.google.com/spreadsheets/d/{sid}/export?format={fmt}"

def _gs_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        return gspread.authorize(creds)
    except Exception:
        return None

def _oc_key(cod, fec, qty):
    return (str(cod), str(fec), str(int(round(float(qty)))))

def cargar_oc_estados_sheet():
    """Devuelve set de keys (cod, fecha, qty) que están en estado Pendiente."""
    gc = _gs_client()
    if gc is None:
        return set()
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        records = ws.get_all_records()
        return {_oc_key(r["codigo"], r["fecha_entrega"], r["cantidad_oc"])
                for r in records if r.get("estado") == "🕐 Pendiente"}
    except Exception:
        return set()

def guardar_oc_estados():
    """Escribe en el Sheet todos los estados Pendiente actuales."""
    gc = _gs_client()
    if gc is None or st.session_state.oc is None:
        return
    oc_df = st.session_state.oc
    # Mapa cod → [(fec, qty), ...] en orden de aparición
    oc_idx = {}
    for _, r in oc_df.iterrows():
        cod = str(r["codigo"]); fec = r["fecha_entrega"]; qty = float(r["cantidad_oc"])
        if pd.isna(fec): continue
        oc_idx.setdefault(cod, []).append((fec, qty))
    rows = [["codigo", "fecha_entrega", "cantidad_oc", "estado"]]
    for cod, estados in st.session_state.mrp_oc_estados.items():
        entries = oc_idx.get(cod, [])
        for i, est in estados.items():
            if est == "🕐 Pendiente" and i < len(entries):
                fec, qty = entries[i]
                rows.append([cod, str(fec), str(int(round(qty))), est])
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        ws.clear()
        ws.update("A1", rows)
    except Exception as e:
        st.toast(f"⚠️ No se pudieron guardar los estados: {e}", icon="⚠️")

def merge_oc_estados(oc_df):
    """Reconstruye mrp_oc_estados aplicando los estados guardados en el Sheet."""
    pendientes = cargar_oc_estados_sheet()
    new_estados = {}
    new_venc_parcial = {}
    oc_idx = {}
    for _, r in oc_df.iterrows():
        cod = str(r["codigo"]); fec = r["fecha_entrega"]; qty = float(r["cantidad_oc"])
        if pd.isna(fec): continue
        oc_idx.setdefault(cod, []).append((fec, qty))
    for cod, entries in oc_idx.items():
        estados_cod = {}
        total_pend = 0.0
        for i, (fec, qty) in enumerate(entries):
            if fec < HOY and _oc_key(cod, fec, qty) in pendientes:
                estados_cod[i] = "🕐 Pendiente"
                total_pend += qty
        if estados_cod:
            new_estados[cod] = estados_cod
        if total_pend > 0:
            new_venc_parcial[cod] = total_pend
    st.session_state.mrp_oc_estados = new_estados
    st.session_state.mrp_oc_venc_parcial = new_venc_parcial

MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
HOY   = date.today()

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def mes_key(año, mes_0):
    return f"{MESES[mes_0]}_{str(año)[-2:]}"

def semanas_del_mes(año, mes):
    """Sem 1: día 1 → día antes del primer lunes. Sem 2+: lunes→domingo."""
    primer = date(año, mes, 1)
    ultimo = date(año, mes, calendar.monthrange(año, mes)[1])
    semanas = []
    dia = primer
    while dia.weekday() != 0:
        dia += timedelta(days=1)
    primer_lunes = dia
    fin1 = min(primer_lunes - timedelta(days=1) if primer_lunes != primer
               else primer + timedelta(days=6), ultimo)
    semanas.append((f"Sem 1 ({primer.day}/{mes}–{fin1.day}/{mes})", primer, fin1))
    sig = fin1 + timedelta(days=1)
    n = 2
    while sig <= ultimo:
        fin = min(sig + timedelta(days=6), ultimo)
        semanas.append((f"Sem {n} ({sig.day}/{mes}–{fin.day}/{mes})", sig, fin))
        sig = fin + timedelta(days=1)
        n += 1
    return semanas

def semanas_desde_hoy(año, mes):
    todas = semanas_del_mes(año, mes)
    return [(lb, ss, se) for lb, ss, se in todas if se >= HOY]

def distribuir(total, n_sem, pcts):
    total = int(round(total))
    if total == 0 or n_sem == 0:
        return [0] * n_sem
    p = pcts[:n_sem]
    sp = sum(p)
    vals = [int(round(total * x / sp)) for x in p] if sp else [total // n_sem] * n_sem
    diff = total - sum(vals)
    if diff:
        vals[-1] += diff
    return vals

def ceil_multiplo(val, mult):
    if val <= 0: return 0
    return math.ceil(val / mult) * mult

def semaforo(sems_cub, total_sems, dias_cobertura=0, lead_time=0):
    if sems_cub >= total_sems:      return "🟢", "Cubierto", "ok"
    if dias_cobertura >= lead_time: return "🟡", "Parcial", "warn"
    return "🔴", "Crítico", "crit"

def exportar_excel(df):
    df = df.fillna("")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="MRP")
        wb = writer.book
        ws = writer.sheets["MRP"]
        fmt_hdr = wb.add_format({"bold":True,"bg_color":"#1f2733","font_color":"#ffffff","border":1})
        fmt_red = wb.add_format({"bg_color":"#fbecea","font_color":"#7a221c"})
        fmt_yel = wb.add_format({"bg_color":"#fbf3e1","font_color":"#6b4d10"})
        fmt_grn = wb.add_format({"bg_color":"#e8f4ec","font_color":"#1e5e3a"})
        col_estado = df.columns.tolist().index("Estado") if "Estado" in df.columns else None
        for i, col in enumerate(df.columns):
            ws.write(0, i, col, fmt_hdr)
            ws.set_column(i, i, max(14, len(str(col)) + 4))
        for row_idx, row in df.iterrows():
            if col_estado is not None:
                est = str(row.get("Estado",""))
                fmt = fmt_red if "🔴" in est else fmt_yel if "🟡" in est else fmt_grn if "🟢" in est else None
                if fmt:
                    for ci in range(len(df.columns)):
                        ws.write(row_idx + 1, ci, row.iloc[ci], fmt)
    return buf.getvalue()

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "stock": None, "oc": None, "bom": None, "forecast": None,
    "produccion": {},
    "horizonte": 2, "multiplo": 500,
    "lead_times": {},
    "mrp_result": None, "mrp_sem_headers": [], "mrp_todas_sems": [],
    "mrp_oc_venc_parcial": {},
    "mrp_oc_estados": {},
    "fecha_corte_stock": None,
    "dist_4": [30, 30, 30, 10],
    "dist_5": [25, 25, 25, 15, 10],
    "prod_listo": False,
    "mrp_desactualizado": False,
    "uploader_key": 0,
    "fid_stock": None, "fid_oc": None, "fid_bom": None, "fid_fc": None,
    "gd_cargado": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.gd_cargado:
    try:
        with st.spinner("Cargando datos desde Google Drive..."):
            df = pd.read_csv(gsheet_url(GD_IDS["stock"]))
            df.columns = df.columns.str.strip().str.lower()
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
            st.session_state.stock = df
            st.session_state.fecha_corte_stock = HOY

            df = pd.read_csv(gsheet_url(GD_IDS["ordenes"]))
            df.columns = df.columns.str.strip().str.lower()
            df["cantidad_oc"] = pd.to_numeric(df["cantidad_oc"], errors="coerce").fillna(0)
            df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce").dt.date
            st.session_state.oc = df
            merge_oc_estados(df)

            df = pd.read_csv(gsheet_url(GD_IDS["bom"]))
            df.columns = df.columns.str.strip().str.lower()
            df["cantidad_por_unidad"] = pd.to_numeric(df["cantidad_por_unidad"], errors="coerce").fillna(0)
            st.session_state.bom = df

            df = pd.read_excel(gsheet_url(GD_IDS["forecast"], "xlsx"))
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
    except Exception as e:
        st.warning(f"⚠️ No se pudieron cargar los datos desde Google Drive: {e}")
    finally:
        st.session_state.gd_cargado = True

uk = st.session_state.uploader_key

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
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

    f = st.file_uploader("📦 stock.csv", type=["csv"], key=f"up_stock_{uk}")
    if f and f.file_id != st.session_state.fid_stock:
        try:
            df = pd.read_csv(f, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
            st.session_state.stock = df
            st.session_state.fid_stock = f.file_id
            st.session_state.fecha_corte_stock = HOY
            st.session_state.mrp_desactualizado = True
            st.success(f"✓ {len(df):,} insumos")
        except Exception as e: st.error(str(e))

    if st.session_state.stock is not None and st.session_state.fecha_corte_stock:
        nueva_fc = st.date_input("📅 Fecha de corte del stock",
            value=st.session_state.fecha_corte_stock, max_value=HOY, key=f"fc_stock_{uk}")
        if nueva_fc != st.session_state.fecha_corte_stock:
            st.session_state.fecha_corte_stock = nueva_fc
            st.session_state.mrp_desactualizado = True

    f = st.file_uploader("🛒 ordenes.csv", type=["csv"], key=f"up_oc_{uk}")
    if f and f.file_id != st.session_state.fid_oc:
        try:
            df = pd.read_csv(f, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["cantidad_oc"] = pd.to_numeric(df["cantidad_oc"], errors="coerce").fillna(0)
            df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce").dt.date
            st.session_state.oc = df
            st.session_state.fid_oc = f.file_id
            st.session_state.mrp_desactualizado = True
            merge_oc_estados(df)
            st.success(f"✓ {len(df):,} líneas OC")
        except Exception as e: st.error(str(e))

    f = st.file_uploader("🔗 bom.csv", type=["csv"], key=f"up_bom_{uk}")
    if f and f.file_id != st.session_state.fid_bom:
        try:
            df = pd.read_csv(f, dtype=str)
            df.columns = df.columns.str.strip().str.lower()
            df["cantidad_por_unidad"] = pd.to_numeric(df["cantidad_por_unidad"], errors="coerce").fillna(0)
            st.session_state.bom = df
            st.session_state.fid_bom = f.file_id
            st.session_state.mrp_desactualizado = True
            st.success(f"✓ {len(df):,} relaciones BOM")
        except Exception as e: st.error(str(e))

    f = st.file_uploader("📊 forecast.xlsx", type=["xlsx","xls"], key=f"up_fc_{uk}")
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
            meses_det = [c for c in df.columns if c not in ["articulo","descripcion"]]
            st.success(f"✓ {len(df):,} artículos | {', '.join(meses_det)}")
        except Exception as e: st.error(str(e))

    st.markdown("---")
    for nombre, key in [("Stock","stock"),("OC","oc"),("BOM","bom"),("Forecast","forecast")]:
        ok = st.session_state[key] is not None
        st.markdown(f"{'✅' if ok else '⬜'} {nombre}")

    st.markdown("---")
    if st.button("🗑️ Limpiar todo", use_container_width=True):
        for k, v in DEFAULTS.items():
            st.session_state[k] = v
        st.session_state.uploader_key += 1
        st.rerun()

# ─── TABS ──────────────────────────────────────────────────────────────────────
tab_datos, tab_prod, tab_mrp, tab_cfg = st.tabs(
    ["📋 Datos", "🏭 Producción", "📦 MRP", "⚙️ Configuración"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB DATOS
# ══════════════════════════════════════════════════════════════════════════════
with tab_datos:
    st.header("Datos cargados")
    c1,c2,c3,c4 = st.columns(4)
    for col, key, label in [(c1,"stock","Insumos"),(c2,"oc","Líneas OC"),
                             (c3,"bom","Relaciones BOM"),(c4,"forecast","Artículos FC")]:
        d = st.session_state[key]
        col.metric(label, f"{len(d):,}" if d is not None else "—")

    st.markdown("")
    any_data = any(st.session_state[k] is not None for k in ["stock","oc","bom","forecast"])
    if not any_data:
        st.info("Cargá los archivos desde el panel izquierdo para comenzar.")
    else:
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
            venc = (oc["fecha_entrega"] < HOY).sum()
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB PRODUCCIÓN
# ══════════════════════════════════════════════════════════════════════════════
with tab_prod:
    mes_nombre = HOY.strftime("%B %Y").capitalize()
    st.header(f"Plan de Producción — {mes_nombre}")

    if st.session_state.forecast is None or st.session_state.bom is None:
        st.info("Cargá el BOM y el Forecast para habilitar este módulo.")
    else:
        fc  = st.session_state.forecast
        bom = st.session_state.bom

        semanas    = semanas_desde_hoy(HOY.year, HOY.month)
        n_sem      = len(semanas)
        sem_labels = [s[0] for s in semanas]
        mes_act_key = mes_key(HOY.year, HOY.month - 1)
        dist = st.session_state.dist_4 if n_sem <= 4 else st.session_state.dist_5

        if not st.session_state.prod_listo:
            prod = {}
            for _, row in fc.iterrows():
                art   = str(row["articulo"])
                desc  = str(row.get("descripcion", art))
                fc_val = float(row[mes_act_key]) if mes_act_key in row.index and pd.notna(row[mes_act_key]) else 0
                if fc_val <= 0: continue
                vals = distribuir(fc_val, n_sem, dist)
                prod[art] = {"desc": desc, "forecast": fc_val,
                             **{f"s{i+1}": vals[i] for i in range(n_sem)}}
            st.session_state.produccion = prod
            st.session_state.prod_listo = True

        prod = st.session_state.produccion

        # ── Resumen ejecutivo (tarjetas) — placeholder, se llena después del editor ──
        cards_placeholder = st.empty()
        st.markdown("")

        # ── Controles ──
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
                arts_bom = sorted(bom["articulo"].unique().tolist())
                arts_disponibles = [a for a in arts_bom if a not in prod]
                col_sel, col_ok, col_cancel = st.columns([5, 1, 1])
                with col_sel:
                    art_nuevo = st.selectbox("Artículo", [""] + arts_disponibles, label_visibility="collapsed")
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

        # ── Tabla editable ──
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
        else:
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
                "Distribución": st.column_config.BarChartColumn("Distribución", help="Reparto por semana",
                                                                width="small"),
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

            # Llenar tarjetas con valores actualizados (después de guardar cambios)
            _tp = sum(sum(d.get(f"s{i+1}",0) for i in range(n_sem))
                      for d in st.session_state.produccion.values())
            _fc = sum(int(d.get("forecast",0)) for d in st.session_state.produccion.values())
            _dv = _tp - _fc
            _kd = "ok" if _dv == 0 else ("warn" if abs(_dv) / (_fc or 1) > 0.05 else "")
            cards_placeholder.markdown(tema.cards([
                {"lbl":"Artículos en plan","val":f"{len(st.session_state.produccion):,}","sub":"a producir este mes"},
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB MRP
# ══════════════════════════════════════════════════════════════════════════════
with tab_mrp:
    st.header("Plan de Compras — MRP")

    if st.session_state.stock is None or st.session_state.bom is None:
        st.info("Cargá stock y BOM para calcular el MRP.")
    else:
        # Banner fecha de corte
        if st.session_state.fecha_corte_stock:
            dias_stock = (HOY - st.session_state.fecha_corte_stock).days
            fc_str = st.session_state.fecha_corte_stock.strftime("%d/%m/%Y")
            if dias_stock == 0:
                st.markdown(tema.banner(f"Stock al corte de hoy · <strong>{fc_str}</strong> &nbsp;·&nbsp; Horizonte: {st.session_state.horizonte} meses", "ok"), unsafe_allow_html=True)
            elif dias_stock <= 3:
                st.markdown(tema.banner(f"Stock con <strong>{dias_stock} día(s)</strong> de antigüedad (corte: {fc_str}). Verificá consumos recientes.", "warn"), unsafe_allow_html=True)
            else:
                st.markdown(tema.banner(f"Stock con <strong>{dias_stock} días</strong> de antigüedad (corte: {fc_str}). Los resultados pueden no reflejar la realidad.", "crit"), unsafe_allow_html=True)

        if not st.session_state.produccion:
            st.warning("⚠️ El plan de producción está vacío. El MRP usará solo el forecast de meses futuros.")
        if st.session_state.mrp_desactualizado and st.session_state.mrp_result:
            st.markdown(tema.banner("Los parámetros o datos cambiaron. <strong>Recalculá el MRP</strong> para actualizar los resultados.", "warn"), unsafe_allow_html=True)

        col_calc, _ = st.columns([2, 6])
        with col_calc:
            calcular = st.button("▶ Calcular MRP", type="primary", use_container_width=True)

        if calcular:
            stock_df  = st.session_state.stock
            oc_df     = st.session_state.oc
            bom_df    = st.session_state.bom
            fc_df     = st.session_state.forecast
            prod      = st.session_state.produccion
            horizonte = st.session_state.horizonte
            multiplo  = st.session_state.multiplo

            with st.spinner("Calculando MRP..."):
                todas_sems = []
                sems_actual = semanas_desde_hoy(HOY.year, HOY.month)
                mes_n_act   = HOY.strftime("%b")
                for sl, ss, se in sems_actual:
                    todas_sems.append((f"{mes_n_act} {sl}", ss, se))
                for m in range(1, horizonte + 1):
                    mes0  = (HOY.month - 1 + m) % 12
                    año_f = HOY.year + (HOY.month - 1 + m) // 12
                    sems_f = semanas_del_mes(año_f, mes0 + 1)
                    mes_n_f = date(año_f, mes0 + 1, 1).strftime("%b")
                    for sl, ss, se in sems_f:
                        todas_sems.append((f"{mes_n_f} {sl}", ss, se))

                n_sems     = len(todas_sems)
                sem_headers = [s[0] for s in todas_sems]
                limite_hz   = todas_sems[-1][2]

                stock_map = {
                    str(r["codigo"]): {"stock": float(r["stock"]),
                                       "desc": str(r["descripcion"]),
                                       "tipo": str(r["tipo_insumo"])}
                    for _, r in stock_df.iterrows()
                }

                oc_vigente = {}
                oc_vencida_total = {}
                oc_detalle = {}
                if oc_df is not None:
                    for _, r in oc_df.iterrows():
                        cod = str(r["codigo"])
                        qty = float(r["cantidad_oc"])
                        fec = r["fecha_entrega"]
                        if pd.isna(fec): continue
                        oc_detalle.setdefault(cod, []).append({
                            "Fecha entrega": fec, "Cantidad OC": qty,
                            "Estado": "⚠️ Vencida" if fec < HOY else "✅ Vigente"
                        })
                        if fec < HOY:
                            oc_vencida_total[cod] = oc_vencida_total.get(cod, 0) + qty
                        elif fec <= limite_hz:
                            oc_vigente[cod] = oc_vigente.get(cod, 0) + qty

                dem = {}
                mes_act_key = mes_key(HOY.year, HOY.month - 1)
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
                        mes0  = (HOY.month - 1 + m) % 12
                        año_f = HOY.year + (HOY.month - 1 + m) // 12
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
                for _, r in bom_df.iterrows():
                    art = str(r["articulo"])
                    bom_idx.setdefault(art, []).append(
                        (str(r["codigo_insumo"]), float(r["cantidad_por_unidad"])))

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
                    oc_ve_total = oc_vencida_total.get(cod, 0)
                    oc_ve_parcial = st.session_state.mrp_oc_venc_parcial.get(cod, 0.0)
                    cobert = stk + oc_v + oc_ve_parcial

                    nec_sem   = [round(nec.get((cod, i), 0)) for i in range(n_sems)]
                    total_nec = sum(nec_sem)

                    cob_acum = cobert
                    sems_cub = 0
                    for n in nec_sem:
                        if n == 0: sems_cub += 1; continue
                        if cob_acum >= n: cob_acum -= n; sems_cub += 1
                        else: break

                    lt = st.session_state.lead_times.get(s["tipo"], 15)
                    fecha_pedido = "—"
                    dias_cobertura = 0
                    if sems_cub < n_sems:
                        fec_nec = todas_sems[sems_cub][1]
                        dias_cobertura = (fec_nec - HOY).days
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
                        **{sem_headers[i]: nec_sem[i] for i in range(n_sems)},
                        "_arts": list(ins_arts.get(cod, [])), "_oc_det": oc_detalle.get(cod, []),
                    })

                orden = {"🔴":0,"🟡":1,"🟢":2}
                resultados.sort(key=lambda r: (orden.get(r["sem_ic"],3), r["_dias_quiebre"]))
                st.session_state.mrp_result = resultados
                st.session_state.mrp_sem_headers = sem_headers
                st.session_state.mrp_todas_sems = todas_sems
                st.session_state.mrp_desactualizado = False

        # ── Mostrar resultados ──
        if st.session_state.mrp_result:
            res  = st.session_state.mrp_result
            s_hd = st.session_state.mrp_sem_headers

            rojos = sum(1 for r in res if r["sem_ic"]=="🔴")
            amar  = sum(1 for r in res if r["sem_ic"]=="🟡")
            verd  = sum(1 for r in res if r["sem_ic"]=="🟢")
            sug_total = sum(r["Sugerencia"] for r in res)
            lineas = sum(1 for r in res if r["Sugerencia"] > 0)
            prox = sorted([r for r in res if r["_dias_quiebre"] < 9999],
                          key=lambda r: r["_dias_quiebre"])
            prox0 = prox[0] if prox else None

            st.markdown(tema.cards([
                {"lbl":"Críticos","val":rojos,"sub":"sin cobertura","kind":"crit"},
                {"lbl":"Parciales","val":amar,"sub":"cobertura a riesgo","kind":"warn"},
                {"lbl":"Cubiertos","val":verd,"sub":"ok al horizonte","kind":"ok"},
                {"lbl":"Compra sugerida","val":f"{sug_total:,}","sub":f"{lineas} líneas a pedir"},
                {"lbl":"Próximo quiebre","val":(prox0["_dias_quiebre"] if prox0 else "—"),
                 "unit":"días" if prox0 else "", "sub":(prox0["Descripción"] if prox0 else "Todo cubierto")},
            ]), unsafe_allow_html=True)
            st.markdown("")

            fc1, fc2, _ = st.columns([2, 2, 4])
            with fc1:
                f_est  = st.selectbox("Estado", ["Todos","🔴 Crítico","🟡 Parcial","🟢 Cubierto"])
            with fc2:
                tipos_u = sorted(set(r["Tipo"] for r in res))
                f_tipo  = st.selectbox("Tipo de insumo", ["Todos"] + tipos_u)

            res_f = res[:]
            if f_est != "Todos":
                ic = f_est.split()[0]
                res_f = [r for r in res_f if r["sem_ic"] == ic]
            if f_tipo != "Todos":
                res_f = [r for r in res_f if r["Tipo"] == f_tipo]

            df_show = pd.DataFrame([{
                "Estado": f"{r['sem_ic']} {r['sem_lb']}",
                "Días al quiebre": r["Días al quiebre"], "Tipo": r["Tipo"],
                "Descripción": r["Descripción"], "Código": r["Código"], "Stock": r["Stock"],
                "OC disp.": r["_oc_label"], "Nec. total": r["Nec. total"], "Nec. neta": r["Nec. neta"],
                "Sugerencia": r["Sugerencia"], "Pedir en": r["Pedir en"],
                **{h: r[h] for h in s_hd},
            } for r in res_f])

            col_cfg_mrp = {
                "Estado": st.column_config.TextColumn("Estado", width="small"),
                "Días al quiebre": st.column_config.NumberColumn("Días", format="%d", width="small"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Descripción": st.column_config.TextColumn("Descripción", width="large"),
                "Stock": st.column_config.NumberColumn("Stock", format="%d"),
                "OC disp.": st.column_config.TextColumn("OC disp."),
                "Nec. total": st.column_config.NumberColumn("Nec. total", format="%d"),
                "Nec. neta": st.column_config.NumberColumn("Nec. neta", format="%d"),
                "Sugerencia": st.column_config.NumberColumn("Sugerencia", format="%d"),
                **{h: st.column_config.NumberColumn(h, format="%d", width="small") for h in s_hd},
            }
            sel = st.dataframe(
                df_show, use_container_width=True, hide_index=True, height=440,
                on_select="rerun", selection_mode="single-row",
                column_config=col_cfg_mrp,
            )

            col_dl, _ = st.columns([2, 6])
            with col_dl:
                st.download_button("⬇️ Exportar Excel", exportar_excel(df_show),
                    f"MRP_{HOY.isoformat()}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # ── Detalle ──
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
            cod_activo = st.session_state.get("mrp_cod_sel")
            if cod_por_click:
                cod_activo = cod_por_click
            elif codigos_det and (not cod_activo or cod_activo not in codigos_det):
                cod_activo = codigos_det[0]

            if codigos_det:
                idx_default = codigos_det.index(cod_activo) if cod_activo in codigos_det else 0
                cod_sel = st.selectbox("Insumo seleccionado", codigos_det, index=idx_default,
                    format_func=lambda c: next((f"{c} — {r['Descripción']}" for r in res if r["Código"] == c), c))
                st.session_state["mrp_cod_sel"] = cod_sel
            else:
                st.info("Ningún insumo coincide con el filtro.")
                cod_sel = None

            if cod_sel:
                r = next((x for x in res if x["Código"] == cod_sel), None)
                if r:
                    with st.container(border=True):
                        st.markdown(tema.pill(r["sem_kind"], r["sem_lb"]) +
                            f'<div class="det-title">{r["Descripción"]}</div>'
                            f'<div class="det-sub">{r["Código"]} · {r["Tipo"]} · '
                            f'{r["sems_cub"]}/{len(s_hd)} semanas cubiertas</div>',
                            unsafe_allow_html=True)
                        st.markdown("")

                        c1,c2,c3 = st.columns(3)
                        c1.metric("Stock", f"{r['Stock']:,}")
                        c2.metric("OC disponibles", r["_oc_label"])
                        c3.metric("OC vencidas", f"{r['OC vencidas']:,}")
                        c1,c2,c3 = st.columns(3)
                        c1.metric("Nec. total", f"{r['Nec. total']:,}")
                        c2.metric("Nec. neta", f"{r['Nec. neta']:,}")
                        c3.metric("Sugerencia compra", f"{r['Sugerencia']:,}")

                        if r["Pedir en"] != "—":
                            if "⚠️" in str(r["Pedir en"]):
                                st.markdown(tema.banner("Ya debería haberse pedido — emitir OC cuanto antes", "crit"), unsafe_allow_html=True)
                            else:
                                st.markdown(tema.banner(f"Emitir pedido en <strong>{r['Pedir en']}</strong>", "ok"), unsafe_allow_html=True)

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

                            estados_guardados = st.session_state.mrp_oc_estados.get(cod_sel, {})
                            rows_oc = []
                            for i, o in enumerate(oc_det):
                                es_vencida = o["Estado"] == "⚠️ Vencida"
                                estado_actual = estados_guardados.get(i, o["Estado"]) if es_vencida else o["Estado"]
                                rows_oc.append({"Fecha entrega": o["Fecha entrega"],
                                                "Cantidad OC": int(o["Cantidad OC"]), "Estado": estado_actual})
                            df_oc = pd.DataFrame(rows_oc)
                            edited_oc = st.data_editor(df_oc, column_config={
                                "Fecha entrega": st.column_config.DateColumn("Fecha entrega", disabled=True),
                                "Cantidad OC": st.column_config.NumberColumn("Cantidad OC", disabled=True, format="%d"),
                                "Estado": st.column_config.SelectboxColumn("Estado",
                                    options=["✅ Vigente", "⚠️ Vencida", "🕐 Pendiente"], required=True,
                                    help="Cambiá a 🕐 Pendiente para incluir la cantidad en la cobertura"),
                            }, use_container_width=True, hide_index=True, key=f"oc_editor_{cod_sel}")

                            nuevos_estados = {}
                            total_pendiente = 0.0
                            for i, row in edited_oc.iterrows():
                                if oc_det[i]["Estado"] == "⚠️ Vencida":
                                    nuevos_estados[i] = row["Estado"]
                                    if row["Estado"] == "🕐 Pendiente":
                                        total_pendiente += float(oc_det[i]["Cantidad OC"])
                            st.session_state.mrp_oc_estados[cod_sel] = nuevos_estados
                            prev_parcial = st.session_state.mrp_oc_venc_parcial.get(cod_sel, 0.0)
                            if total_pendiente != prev_parcial:
                                st.session_state.mrp_oc_venc_parcial[cod_sel] = total_pendiente
                                st.session_state.mrp_desactualizado = True
                                guardar_oc_estados()
                            if total_pendiente > 0:
                                st.caption(f"Suma a cobertura: {round(total_pendiente):,} en estado Pendiente. Recalculá el MRP para aplicar.")
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
                                        f"Insumo_{cod_sel}_{HOY.isoformat()}.xlsx",
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        key=f"dl_ins_{cod_sel}",
                                    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
with tab_cfg:
    st.header("Configuración")

    col1, col2 = st.columns(2)
    with col1:
        nuevo_hz = st.number_input("Horizonte de planificación (meses)", 1, 6, st.session_state.horizonte)
        if nuevo_hz != st.session_state.horizonte:
            st.session_state.horizonte = nuevo_hz
            st.session_state.mrp_desactualizado = True
    with col2:
        nuevo_mp = st.number_input("Múltiplo de compra (unidades)", 1, value=st.session_state.multiplo)
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
        nd4 = [cols4[i].number_input(f"S{i+1}", 0, 100, st.session_state.dist_4[i], key=f"d4_{i}") for i in range(4)]
        if sum(nd4) == 100:
            if nd4 != st.session_state.dist_4:
                st.session_state.dist_4 = nd4
                st.session_state.mrp_desactualizado = True
        else:
            st.warning(f"Suma: {sum(nd4)}% — debe ser 100%")
    with c2:
        st.markdown("**Meses de 5 semanas** (default: 25/25/25/15/10)")
        cols5 = st.columns(5)
        nd5 = [cols5[i].number_input(f"S{i+1}", 0, 100, st.session_state.dist_5[i], key=f"d5_{i}") for i in range(5)]
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
        tipos = sorted(st.session_state.stock["tipo_insumo"].dropna().unique().tolist())
        new_lt = {}
        cols_lt = st.columns(min(3, len(tipos)))
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
