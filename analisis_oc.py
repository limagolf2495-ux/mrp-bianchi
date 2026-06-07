import pandas as pd
from datetime import date

HOY = date(2026, 5, 30)
MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

def mes_key(anio, mes_0):
    return f'{MESES[mes_0]}_{str(anio)[-2:]}'

stock_df = pd.read_csv('Archivos/stock.csv', dtype=str)
stock_df.columns = stock_df.columns.str.strip().str.lower()
stock_df['stock'] = pd.to_numeric(stock_df['stock'], errors='coerce').fillna(0)

oc_df = pd.read_csv('Archivos/ordenes.csv', dtype=str)
oc_df.columns = oc_df.columns.str.strip().str.lower()
oc_df['cantidad_oc'] = pd.to_numeric(oc_df['cantidad_oc'], errors='coerce').fillna(0)
oc_df['fecha_entrega'] = pd.to_datetime(oc_df['fecha_entrega'], errors='coerce').dt.date

bom_df = pd.read_csv('Archivos/bom.csv', dtype=str)
bom_df.columns = bom_df.columns.str.strip().str.lower()
bom_df['cantidad_por_unidad'] = pd.to_numeric(bom_df['cantidad_por_unidad'], errors='coerce').fillna(0)

fc_df = pd.read_excel('Archivos/forecast.xlsx')
new_cols = []
for col in fc_df.columns:
    if hasattr(col, 'month'):
        new_cols.append(f'{MESES[col.month-1]}_{str(col.year)[-2:]}')
    else:
        new_cols.append(str(col).strip().lower())
fc_df.columns = new_cols
fc_df = fc_df.loc[:, ~fc_df.columns.duplicated()]
fc_df = fc_df.dropna(how='all')

COD = '11070300122059'

row_s = stock_df[stock_df['codigo'] == COD].iloc[0]
print("Insumo :", row_s['descripcion'])
print("Tipo   :", row_s['tipo_insumo'])
print("Stock  :", f"{int(row_s['stock']):,}")
print()

oc_item = oc_df[oc_df['codigo'] == COD]
print("OC:")
total_venc = 0
total_vig  = 0
for _, r in oc_item.iterrows():
    estado = 'VENCIDA' if r['fecha_entrega'] < HOY else 'VIGENTE'
    if estado == 'VENCIDA':
        total_venc += r['cantidad_oc']
    else:
        total_vig += r['cantidad_oc']
    print(f"  {r['fecha_entrega']}  {int(r['cantidad_oc']):>10,}  {estado}")
print(f"  Total vencidas : {int(total_venc):,}")
print(f"  Total vigentes : {int(total_vig):,}")
print()

bom_item = bom_df[bom_df['codigo_insumo'] == COD]
arts = bom_item['articulo'].unique().tolist()
print(f"Articulos BOM que usan este insumo: {len(arts)}")
print()

# Horizonte: mes actual (may) + 2 meses siguientes (jun, jul)
meses_hz = [mes_key(2026, 4), mes_key(2026, 5), mes_key(2026, 6)]
print("Demanda por mes (forecast x BOM):")
total_dem = 0
for mk in meses_hz:
    dem_mes = 0
    if mk in fc_df.columns:
        for art in arts:
            bom_rows = bom_item[bom_item['articulo'] == art]
            fc_rows  = fc_df[fc_df['articulo'] == art]
            for _, br in bom_rows.iterrows():
                qty_u = float(br['cantidad_por_unidad'])
                for _, fr in fc_rows.iterrows():
                    fc_q = float(fr[mk]) if pd.notna(fr.get(mk, 0)) else 0
                    dem_mes += fc_q * qty_u
    print(f"  {mk}: {int(dem_mes):,}")
    total_dem += dem_mes

print(f"  TOTAL horizonte: {int(total_dem):,}")
print()

stk = int(row_s['stock'])
with_250 = stk + 250000
neta_sin = max(0, int(total_dem) - stk)
neta_con = max(0, int(total_dem) - with_250)

print(f"Cobertura SIN OC pendiente  : {stk:,}")
print(f"Cobertura CON 250k pendiente: {with_250:,}")
print(f"Necesidad neta SIN          : {neta_sin:,}")
print(f"Necesidad neta CON          : {neta_con:,}")
print(f"Total OC vencidas            : {int(total_venc):,}")
print(f"Si se habilitan TODAS las OC : {stk + int(total_venc):,} de cobertura")
print(f"Necesidad neta con todas OC  : {max(0, int(total_dem) - stk - int(total_venc)):,}")
