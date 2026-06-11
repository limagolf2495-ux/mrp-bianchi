from datetime import date

MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]

# Columnas requeridas en stock.csv / tabla de stock de Google Drive
COL_STOCK_COD  = "codigo"
COL_STOCK_DESC = "descripcion"
COL_STOCK_TIPO = "tipo_insumo"
COL_STOCK_QTY  = "stock"
COLS_STOCK_REQ = [COL_STOCK_COD, COL_STOCK_DESC, COL_STOCK_TIPO, COL_STOCK_QTY]

# Columnas requeridas en ordenes.csv / tabla de OC de Google Drive
COL_OC_COD   = "codigo"
COL_OC_QTY   = "cantidad_oc"
COL_OC_FECHA = "fecha_entrega"
COL_OC_ID    = "id"  # N° de OC JDE (ej. O9-22320) — opcional, no requerida
COLS_OC_REQ  = [COL_OC_COD, COL_OC_QTY, COL_OC_FECHA]

# Columnas requeridas en bom.csv / tabla BOM de Google Drive
COL_BOM_ART  = "articulo"
COL_BOM_INS  = "codigo_insumo"
COL_BOM_QTY  = "cantidad_por_unidad"
COLS_BOM_REQ = [COL_BOM_ART, COL_BOM_INS, COL_BOM_QTY]
def get_hoy():
    return date.today()

GD_IDS = {
    "stock":    "17TsFVJw12V5ndLP_TfVaeMvy-rRA1ScUGZCJIlifM38",
    "ordenes":  "11b__i6OcJUz1Duwzbyo6cy0pEXySob6oOXFpiS0lMCU",
    "bom":      "1CH7jaqmfYiefoGRkHj_n4PwDDnHy1fLX9cEz7dzgqCg",
    "forecast": "1TUEwHs4S7lVJWLAHGJNZd0ZoRDBO5VMGQ4wvq816cqo",
    "stock_pt": "1oFWHsYvfO_wyrHQdmjsgeTt-5yIAb9dx5uvSvV230To",
    "ventas":   "1pst0tT0UwlLnUs0hkyxXKFHN3krazUyPP7Hk3y3p4-4",
    "pedidos":  "1y6MTpwtM4A-VhWZDFzzSzJ1A6RUpk3-f3z9-WgKXBLU",
    "precios":  "1UcbkbrlLNBi7lBicMVjuciZkpUdt8QnPHRBDzSliZ88",
}
GD_ESTADOS_ID = "1CpDx8apuRtI4G3RfN1QXLqp-pEdkATX3haj6iIfCfyE"

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
    "gd_fechas": {},            # {key: datetime} — modifiedTime de archivos en Drive
    "oc_raw": None,             # OC sin filtrar por demanda del forecast
    "oc_descartadas": 0,        # líneas OC descartadas por no tener demanda
    "stock_pt": None, "ventas_pt": None, "pedidos_pt": None,
    "reglas_pt": {},
    "plan_calculado": False,
    "reglas_pt_cargadas": False,
    "fid_spt": None, "fid_ven": None, "fid_ped": None,
    "precios": None, "fid_precios": None, "precios_col_candidatas": None,
    "plan_manual": False,
    "mrp_oc_pagada": {},        # {cod: {i: True}} — OC marcadas como pagadas
    "mrp_oc_nueva_fecha": {},   # {cod: {i: date}} — OC vencidas reprogramadas
    "mrp_oc_no_pagada": {},     # {cod: [{"fec": date, "qty": float, "tipo": str}]} — para cashflow
    "plan_produccion_cargado": False,
    "plan_produccion_fecha": "",
}
