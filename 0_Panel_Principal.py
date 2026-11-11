import streamlit as st
import core
import io
import pandas as pd
import numpy as np
from datetime import date, datetime
import calendar

# 1. Configuración de página
st.set_page_config(
    page_title="Tablero Ejecutivo y Financiero - Iglesia Nazareth", 
    page_icon="⛪", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# 2. Bloquear si no hay login y verificar permiso
core.verificar_acceso_pagina("Panel Principal")

# 3. Estilos visuales y banner institucional
core.aplicar_estilos_base()

# ==============================================================================
# ENCABEZADO Y SELECTOR DE CORTE (MOVIDO ARRIBA PARA OPTIMIZAR SQL)
# ==============================================================================
col_tit, col_per = st.columns([7, 3])
with col_tit:
    st.markdown("### 📈 Panel de Control Gerencial y Estados Financieros")
    st.caption("Visión económica consolidada para la toma de decisiones pastorales y administrativas.")

with col_per:
    anio_sel, mes_sel, num_m_sel, _ = core.selector_periodo("dash_report")
    u_dia = calendar.monthrange(anio_sel, num_m_sel)[1]
    fecha_corte_str = f"{anio_sel}-{num_m_sel:02d}-{u_dia:02d}"
    periodo_actual_str = f"{anio_sel}-{num_m_sel:02d}"

# ==============================================================================
# CARGA Y CACHÉ GRANULAR (SEPARADO PARA MÁXIMA VELOCIDAD)
# ==============================================================================
@st.cache_data(ttl=86400, show_spinner=False)  # Caché de 24 horas para catálogos pesados
def cargar_catalogos_fijos():
    try:
        df_miem = core.read_db("SELECT id_miembro, nombre FROM public.miembros")
        df_f = core.read_db("SELECT nombre FROM public.fondos_catalogo")
        df_c = core.read_db("SELECT clave, valor FROM public.config_iglesia")
        
        f_list = df_f["nombre"].tolist() if not df_f.empty else ["General"]
        cfg = dict(zip(df_c["clave"], df_c["valor"])) if not df_c.empty else {}
        return df_miem, f_list, cfg
    except Exception:
        return pd.DataFrame(), ["General"], {}

@st.cache_data(ttl=180, show_spinner=False) # Caché de 3 minutos para transacciones
def cargar_datos_periodo(corte_str):
    # 🚀 OPTIMIZACIÓN V2: Para el cálculo histórico correcto, extraemos TODO hasta la fecha de corte,
    # pero EXCLUIMOS radicalmente los asientos de apertura para NUNCA duplicar saldos arrastrados.
    try:
        df_m = core.read_db("""
            SELECT id, fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, estado_credito 
            FROM public.movimientos 
            WHERE comprobante NOT LIKE 'ASIENTO-APERTURA%%' AND fecha <= %s
        """, (corte_str,))
    except Exception:
        df_m = pd.DataFrame()

    try:
        df_d = core.read_db("SELECT id, fecha, id_miembro, nombre_miembro, mes, medio, monto FROM public.diezmos WHERE fecha <= %s", (corte_str,))
    except Exception:
        df_d = pd.DataFrame()

    try:
        df_am = core.read_db("SELECT id, id_actividad, fecha, tipo, concepto, monto, condicion, cliente_deudor, estado_cobro, medio, fondo_destino, liquidado FROM public.actividad_movimientos WHERE fecha <= %s", (corte_str,))
    except Exception:
        df_am = pd.DataFrame()

    try:
        df_a = core.read_db("SELECT id, nombre, fecha, responsable, estado FROM public.actividades WHERE fecha <= %s", (corte_str,))
    except Exception:
        df_a = pd.DataFrame()

    return df_m, df_d, df_am, df_a

# Llamada a las funciones de datos optimizadas
df_miembros, fondos_list, cfg_dict = cargar_catalogos_fijos()
df_mov, df_dz, df_act_mov, df_act = cargar_datos_periodo(fecha_corte_str)

nom_iglesia = cfg_dict.get("nombre_iglesia", "IGLESIA EVANGÉLICA NAZARETH")
denominacion = cfg_dict.get("denominacion", "ASAMBLEAS DE DIOS DEL PERÚ")
pastor_tit = cfg_dict.get("pastor_principal", "Pastor Principal")
tesorero_tit = cfg_dict.get("tesorero_general", "Tesorero General")

# ==============================================================================
# CÁLCULOS HISTÓRICOS ACUMULADOS (LIQUIDEZ REAL DE LA IGLESIA AL DÍA DE HOY)
# ==============================================================================
# Verificamos si en la BD ya se asentaron los diezmos como "Diezmos Consolidado" para no sumarlos doble
tiene_asientos_dz = not df_mov[df_mov["comprobante"].str.startswith("ASIENTO-DZ-", na=False)].empty if not df_mov.empty and "comprobante" in df_mov.columns else False

mov_disp = df_mov[df_mov["estado_credito"] != "A Credito"].copy() if not df_mov.empty else pd.DataFrame()

if tiene_asientos_dz:
    ing_efe = float(mov_disp[(mov_disp["tipo"] == "Ingreso") & (mov_disp["medio"] == "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0
    ing_ban = float(mov_disp[(mov_disp["tipo"] == "Ingreso") & (mov_disp["medio"] != "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0
else:
    dz_efe = float(df_dz[df_dz["medio"] == "Efectivo"]["monto"].sum()) if not df_dz.empty else 0.0
    dz_ban = float(df_dz[df_dz["medio"] != "Efectivo"]["monto"].sum()) if not df_dz.empty else 0.0
    ing_efe = (float(mov_disp[(mov_disp["tipo"] == "Ingreso") & (mov_disp["medio"] == "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0) + dz_efe
    ing_ban = (float(mov_disp[(mov_disp["tipo"] == "Ingreso") & (mov_disp["medio"] != "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0) + dz_ban

egr_efe = float(mov_disp[(mov_disp["tipo"] == "Egreso") & (mov_disp["medio"] == "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0
egr_ban = float(mov_disp[(mov_disp["tipo"] == "Egreso") & (mov_disp["medio"] != "Efectivo")]["monto"].sum()) if not mov_disp.empty else 0.0

saldo_caja = ing_efe - egr_efe
saldo_banco = ing_ban - egr_ban
total_disp = saldo_caja + saldo_banco

df_mov_corte = df_mov 
df_act_corte = df_act_mov 

# 1. Fondos restringidos (Acumulado Histórico)
fondos_saldos_corte = {}
if not df_mov_corte.empty:
    for fn in fondos_list:
        i_fn = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Ingreso")]["monto"].sum())
        e_fn = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Egreso")]["monto"].sum())
        fondos_saldos_corte[fn] = i_fn - e_fn
else:
    for fn in fondos_list:
        fondos_saldos_corte[fn] = 0.0

efectivo_libre_operativo = max(fondos_saldos_corte.get("General", 0.0), 0.0)
efectivo_no_disponible = sum([saldo for fn, saldo in fondos_saldos_corte.items() if fn != "General" and saldo > 0])

# 2. Deudas y cuentas por cobrar (Acumulado Histórico)
cred_tesoreria = float(df_mov_corte[(df_mov_corte["tipo"] == "Ingreso") & (df_mov_corte["estado_credito"] == "A Credito")]["monto"].sum()) if not df_mov_corte.empty else 0.0
deuda_actividades = float(df_act_corte[(df_act_corte["condicion"] == "Credito") & (df_act_corte["estado_cobro"] == "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
total_adeudos = cred_tesoreria + deuda_actividades

# 3. Resumen de Actividades (Acumulado Histórico)
ing_act_cobradas = float(df_act_corte[(df_act_corte["tipo"] == "Ingreso") & (df_act_corte["estado_cobro"] != "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
egr_act_ejecutadas = float(df_act_corte[df_act_corte["tipo"] == "Egreso"]["monto"].sum()) if not df_act_corte.empty else 0.0
utilidad_neta_act = ing_act_cobradas - egr_act_ejecutadas

# ==============================================================================
# CÁLCULOS ESPECÍFICOS DEL MES AISLADO (PARA EVALUAR RENDIMIENTO MENSUAL)
# ==============================================================================
df_mov_mes = pd.DataFrame()
if not df_mov.empty and "fecha" in df_mov.columns:
    df_mov_temp = df_mov.copy()
    # Extraemos solo el YYYY-MM para filtrar
    df_mov_temp["periodo"] = df_mov_temp["fecha"].astype(str).str[:7]
    # Aislamos solo los movimientos del mes seleccionado
    df_mov_mes = df_mov_temp[df_mov_temp["periodo"] == periodo_actual_str].copy()

# OJO: df_mov_mes ya no incluye 'ASIENTO-APERTURA' porque la carga inicial lo limpió.
ing_periodo = float(df_mov_mes[df_mov_mes["tipo"] == "Ingreso"]["monto"].sum()) if not df_mov_mes.empty else 0.0
egr_periodo = float(df_mov_mes[df_mov_mes["tipo"] == "Egreso"]["monto"].sum()) if not df_mov_mes.empty else 0.0
superavit_periodo = ing_periodo - egr_periodo

# ==============================================================================
# VISTA 1: MÉTRICAS DE LIQUIDEZ Y ADEUDOS (HISTÓRICO ACUMULADO)
# ==============================================================================
st.markdown(f"#### 🏛️ Situación de Liquidez y Adeudos (Acumulado Histórico al {u_dia:02d} de {mes_sel} {anio_sel})")
st.caption("Muestra el dinero real físico y en bancos con el que cuenta la iglesia hoy (excluye duplicidades de asientos de apertura).")

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "💵 Efectivo Disponible (Libre)", 
    f"S/. {efectivo_libre_operativo:,.2f}", 
    help="Dinero del Fondo General apto para gastos corrientes y operativos inmediatos."
)
c2.metric(
    "🔒 Efectivo No Disponible", 
    f"S/. {efectivo_no_disponible:,.2f}", 
    help="Dinero comprometido en Fondos Específicos (Pro-Templo, Misiones, etc.).",
    delta="Fondos Restringidos",
    delta_color="off"
)
c3.metric(
    "⏳ Total por Cobrar (Se Adeuda)", 
    f"S/. {total_adeudos:,.2f}", 
    help="Deudas pendientes de actividades e ingresos al crédito sin cancelar.",
    delta=f"Actividades: S/. {deuda_actividades:,.2f}",
    delta_color="inverse"
)
c4.metric(
    "🏦 Liquidez Total en Tesorería", 
    f"S/. {total_disp:,.2f}", 
    help="Caja Física + Saldos en Banco consolidados de todos los tiempos."
)

st.markdown("---")

# ==============================================================================
# VISTA 2: RENDIMIENTO ESPECÍFICO DEL MES (INGRESOS VS EGRESOS DEL PERIODO)
# ==============================================================================
st.markdown(f"#### 📅 Rendimiento Operativo del Mes ({mes_sel.upper()} {anio_sel})")
st.caption("Aísla el desempeño financiero de este mes específico para ver si la iglesia generó ganancia o pérdida en el periodo.")

r1, r2, r3 = st.columns(3)
r1.metric(
    "🟢 Nuevos Ingresos del Mes", 
    f"S/. {ing_periodo:,.2f}", 
    help="Dinero fresco que ingresó este mes (Diezmos, Ofrendas, etc)."
)
r2.metric(
    "🔴 Gastos y Egresos del Mes", 
    f"S/. {egr_periodo:,.2f}", 
    help="Salidas de dinero ejecutadas durante este mes."
)
r3.metric(
    "⚖️ Resultado Neto del Mes", 
    f"S/. {superavit_periodo:,.2f}", 
    delta="Superávit Operativo" if superavit_periodo >= 0 else "Déficit Operativo",
    delta_color="normal" if superavit_periodo >= 0 else "inverse",
    help="Diferencia entre los ingresos frescos y los gastos del mes seleccionado."
)

st.markdown("---")

# ==============================================================================
# 3. AUDITORÍA FINANCIERA DE ACTIVIDADES
# ==============================================================================
st.markdown("#### 🎯 Rendición Financiera de Actividades Eclesiásticas (Histórico)")

act1, act2, act3, act4 = st.columns(4)
act1.metric("Ingresos Cobrados", f"S/. {ing_act_cobradas:,.2f}")
act2.metric("Gastos / Inversión", f"S/. {egr_act_ejecutadas:,.2f}")
act3.metric("Ganancia Neta Líquida", f"S/. {utilidad_neta_act:,.2f}", delta="Superávit" if utilidad_neta_act >= 0 else "Déficit")
act4.metric("Deudores de Actividades", f"S/. {deuda_actividades:,.2f}", delta="Pendiente de Cobro", delta_color="inverse")

if not df_act_corte.empty:
    with st.expander("🔍 Ver Desglose por Cada Actividad y Lista de Deudores"):
        col_act_tab, col_deud_tab = st.columns([6, 4])
        with col_act_tab:
            st.markdown("##### Resumen por Actividad:")
            df_mrg_act = pd.merge(df_act_corte, df_act, left_on="id_actividad", right_on="id", suffixes=("", "_act"))
            if not df_mrg_act.empty:
                res_act = df_mrg_act.groupby("nombre").agg(
                    Ingresos_Cobrados=("monto", lambda x: x[(df_mrg_act.loc[x.index, "tipo"] == "Ingreso") & (df_mrg_act.loc[x.index, "estado_cobro"] != "Pendiente")].sum()),
                    Egresos=("monto", lambda x: x[df_mrg_act.loc[x.index, "tipo"] == "Egreso"].sum()),
                    Por_Cobrar=("monto", lambda x: x[(df_mrg_act.loc[x.index, "condicion"] == "Credito") & (df_mrg_act.loc[x.index, "estado_cobro"] == "Pendiente")].sum())
                ).reset_index()
                res_act["Utilidad_Neta"] = res_act["Ingresos_Cobrados"] - res_act["Egresos"]
                st.dataframe(
                    res_act.rename(columns={"nombre": "Actividad"}).style.format({
                        "Ingresos_Cobrados": "S/. {:,.2f}",
                        "Egresos": "S/. {:,.2f}",
                        "Por_Cobrar": "S/. {:,.2f}",
                        "Utilidad_Neta": "S/. {:,.2f}"
                    }),
                    use_container_width=True, hide_index=True
                )
        
        with col_deud_tab:
            st.markdown("##### 👥 Deudas Pendientes:")
            deudores_df = df_act_corte[(df_act_corte["condicion"] == "Credito") & (df_act_corte["estado_cobro"] == "Pendiente")][["cliente_deudor", "concepto", "monto"]]
            if not deudores_df.empty:
                st.dataframe(
                    deudores_df.rename(columns={"cliente_deudor": "Hermano / Deudor", "concepto": "Concepto", "monto": "Deuda"}).style.format({"Deuda": "S/. {:,.2f}"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.success("✅ No se registran deudas pendientes en actividades a esta fecha.")

st.markdown("---")

# ==============================================================================
# 4. ANÁLISIS DE DIEZMANTE Y FIDELIDAD MENSUAL
# ==============================================================================
st.markdown("#### 📖 Análisis de Fidelidad y Recaudación de Diezmos")
df_dz_analisis = pd.DataFrame()
if not df_dz.empty and "fecha" in df_dz.columns:
    df_dz_temp = df_dz.copy()
    df_dz_temp["periodo"] = df_dz_temp["fecha"].astype(str).str[:7]
    df_dz_analisis = df_dz_temp.groupby("periodo").agg(
        total_recaudado=("monto", "sum"),
        cant_diezmantes=("id_miembro", "nunique"),
        cant_sobres=("id", "count")
    ).reset_index()
    df_dz_analisis["ticket_promedio"] = df_dz_analisis["total_recaudado"] / df_dz_analisis["cant_diezmantes"].replace(0, 1)
    df_dz_analisis = df_dz_analisis.sort_values("periodo", ascending=False)

dz_mes_actual = df_dz_analisis[df_dz_analisis["periodo"] == periodo_actual_str] if not df_dz_analisis.empty else pd.DataFrame()
rec_mes = float(dz_mes_actual.iloc[0]["total_recaudado"]) if not dz_mes_actual.empty else 0.0
diez_mes = int(dz_mes_actual.iloc[0]["cant_diezmantes"]) if not dz_mes_actual.empty else 0
ticket_mes = float(dz_mes_actual.iloc[0]["ticket_promedio"]) if not dz_mes_actual.empty else 0.0
total_padron = len(df_miembros)
cobertura_padron = (diez_mes / total_padron * 100) if total_padron > 0 else 0.0

d1, d2, d3, d4 = st.columns(4)
d1.metric(f"Recaudación ({mes_sel})", f"S/. {rec_mes:,.2f}")
d2.metric(f"Hermanos Diezmantes ({mes_sel})", f"{diez_mes} personas", help=f"Miembros con al menos 1 aporte en {mes_sel}")
d3.metric("Aporte Promedio / Hermano", f"S/. {ticket_mes:,.2f}")
d4.metric("Cobertura sobre el Padrón", f"{cobertura_padron:.1f}%", help=f"Representa {diez_mes} de {total_padron} miembros registrados")

st.markdown("---")

# ==============================================================================
# 5. GENERADORES DE REPORTES MENSUALES (EXCEL Y PDF)
# ==============================================================================
st.markdown("#### 📂 Informes Operativos Mensuales (Del Periodo)")
st.caption(f"Genera la rendición focalizada para el mes de **{mes_sel} {anio_sel}** con balance de liquidez y actividades.")

def generar_excel_integral_mensual():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df_ratios = pd.DataFrame([
            {"Indicador": "Fecha de Corte", "Valor": fecha_corte_str},
            {"Indicador": "Periodo Evaluado", "Valor": f"{mes_sel} {anio_sel}"},
            {"Indicador": "=== HISTÓRICO ACUMULADO ===", "Valor": ""},
            {"Indicador": "Efectivo Disponible (Fondo General Libre)", "Valor": f"S/. {efectivo_libre_operativo:,.2f}"},
            {"Indicador": "Efectivo No Disponible (Fondos Restringidos)", "Valor": f"S/. {efectivo_no_disponible:,.2f}"},
            {"Indicador": "Total Liquidez Histórica en Tesorería", "Valor": f"S/. {total_disp:,.2f}"},
            {"Indicador": "Cuentas por Cobrar Totales (Adeudos)", "Valor": f"S/. {total_adeudos:,.2f}"},
            {"Indicador": "Deuda de Actividades por Cobrar", "Valor": f"S/. {deuda_actividades:,.2f}"},
            {"Indicador": "Ganancia Neta Histórica en Actividades", "Valor": f"S/. {utilidad_neta_act:,.2f}"},
            {"Indicador": "=== RENDIMIENTO DEL MES AISLADO ===", "Valor": ""},
            {"Indicador": f"Nuevos Ingresos del Mes ({mes_sel})", "Valor": f"S/. {ing_periodo:,.2f}"},
            {"Indicador": f"Gastos y Egresos del Mes ({mes_sel})", "Valor": f"S/. {egr_periodo:,.2f}"},
            {"Indicador": f"Resultado Neto del Mes ({mes_sel})", "Valor": f"S/. {superavit_periodo:,.2f}"},
            {"Indicador": "=== DIEZMOS ===", "Valor": ""},
            {"Indicador": "Hermanos Diezmantes", "Valor": diez_mes},
            {"Indicador": "Cobertura sobre el Padrón", "Valor": f"{cobertura_padron:.1f}%"},
            {"Indicador": "Ticket Promedio por Diezmante", "Valor": f"S/. {ticket_mes:,.2f}"}
        ])
        df_ratios.to_excel(writer, sheet_name="Resumen_Ejecutivo", index=False)

        if not df_mov_mes.empty:
            er_agrupado = df_mov_mes.groupby(["tipo", "categoria", "subcategoria"])["monto"].sum().reset_index()
            er_agrupado.to_excel(writer, sheet_name=f"Ingresos_Egresos_{mes_sel}", index=False)
        else:
            pd.DataFrame({"Mensaje": ["Sin movimientos registrados en este mes"]}).to_excel(writer, sheet_name=f"Ingresos_Egresos_{mes_sel}", index=False)

        if not df_act_corte.empty:
            df_act_corte.to_excel(writer, sheet_name="Actividades_Historico", index=False)
        else:
            pd.DataFrame({"Mensaje": ["Sin actividades a la fecha de corte"]}).to_excel(writer, sheet_name="Actividades_Historico", index=False)

        saldos_fondos_data = []
        for fn in fondos_list:
            i_f = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Ingreso")]["monto"].sum()) if not df_mov_corte.empty else 0.0
            e_f = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Egreso")]["monto"].sum()) if not df_mov_corte.empty else 0.0
            saldos_fondos_data.append({
                "Fondo": fn, 
                "Condición": "Libre Disponibilidad" if fn == "General" else "Fondo Restringido",
                "Total Ingresos": i_f, 
                "Total Egresos": e_f, 
                "Saldo Acumulado al Corte": i_f - e_f
            })
        pd.DataFrame(saldos_fondos_data).to_excel(writer, sheet_name="Balance_Fondos_Historico", index=False)

        if not df_dz_analisis.empty:
            df_dz_analisis.to_excel(writer, sheet_name="Analisis_Diezmos", index=False)

    return out.getvalue()

def generar_pdf_gerencial_mensual():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=35, rightMargin=35, topMargin=30, bottomMargin=30)
    story = []

    c_prim = colors.HexColor("#1E3A8A")
    c_sec = colors.HexColor("#0F172A")
    c_borde = colors.HexColor("#CBD5E1")

    style_sec = ParagraphStyle('S1', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_prim, spaceBefore=7, spaceAfter=3)
    style_body = ParagraphStyle('B1', fontName='Helvetica', fontSize=7.8, leading=10.5, textColor=c_sec, alignment=4)

    t_head = Table([
        [
            Paragraph(f"<b>{nom_iglesia.upper()}</b><br/><font size=7.5>{denominacion.upper()}</font><br/><font size=7 color='#64748B'>DEPARTAMENTO DE ADMINISTRACIÓN Y TESORERÍA GENERAL</font>", ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_prim)),
            Paragraph(f"<b>INFORME FINANCIERO MENSUAL GERENCIAL</b><br/><font size=8.5 color='#B45309'><b>CORTE AL: {u_dia:02d} DE {mes_sel.upper()} {anio_sel}</b></font><br/><font size=7>Emisión: {date.today().strftime('%d/%m/%Y')}</font>", ParagraphStyle('HD', fontName='Helvetica', fontSize=7.5, alignment=2))
        ]
    ], colWidths=[330, 212])
    t_head.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, c_prim),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 5)
    ]))
    story.extend([t_head, Spacer(1, 8)])

    story.append(Paragraph("1. ESTADO DE DISPONIBILIDAD LÍQUIDA Y ADEUDOS PENDIENTES (ACUMULADO HISTÓRICO)", style_sec))
    t_liq = Table([
        ["CONCEPTO FINANCIERO", "CLASIFICACIÓN TÉCNICA", "MONTO AL CORTE (S/.)"],
        ["EFECTIVO DISPONIBLE OPERATIVO", "Fondo General (Uso libre para operación)", f"S/. {efectivo_libre_operativo:,.2f}"],
        ["EFECTIVO NO DISPONIBLE (RESTRINGIDO)", "Fondos Específicos (Pro-Templo, Misiones, etc.)", f"S/. {efectivo_no_disponible:,.2f}"],
        ["TOTAL LIQUIDEZ HISTÓRICA CONSOLIDADA", "Suma en Caja Física y Cuentas Bancarias", f"S/. {total_disp:,.2f}"],
        ["CUENTAS POR COBRAR (SE ADEUDA)", "Pendiente en Actividades y Créditos", f"S/. {total_adeudos:,.2f}"]
    ], colWidths=[230, 202, 110])
    t_liq.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_prim),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#EFF6FF")),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#FEF2F2")),
        ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    story.extend([t_liq, Spacer(1, 8)])

    story.append(Paragraph(f"2. RENDIMIENTO FINANCIERO AISLADO DEL MES ({mes_sel.upper()} {anio_sel})", style_sec))
    t_er = Table([
        ["PARTIDA", "IMPORTE", "PARTIDA DE DIEZMOS", "RESULTADO"],
        [f"Ingresos Nuevos del Mes:", f"S/. {ing_periodo:,.2f}", "Recaudación en Diezmos:", f"S/. {rec_mes:,.2f}"],
        [f"Gastos Ejecutados del Mes:", f"S/. {egr_periodo:,.2f}", "Hermanos Diezmantes:", f"{diez_mes} de {total_padron}"],
        [f"Resultado Neto Operativo del Mes:", f"S/. {superavit_periodo:,.2f}", "Ticket Promedio:", f"S/. {ticket_mes:,.2f}"]
    ], colWidths=[150, 120, 152, 120])
    t_er.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('BACKGROUND', (0,3), (1,3), colors.HexColor("#FEF08A") if superavit_periodo >= 0 else colors.HexColor("#FECACA")),
        ('FONTNAME', (0,3), (1,3), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    story.extend([t_er, Spacer(1, 8)])

    story.append(Paragraph("3. BALANCE Y AUDITORÍA DE ACTIVIDADES ECLESIÁSTICAS (HISTÓRICO)", style_sec))
    t_act = Table([
        ["CONCEPTO DE ACTIVIDADES", "RESULTADO OBTENIDO", "OBSERVACIÓN / DESTINO"],
        ["Ingresos Efectivamente Cobrados", f"S/. {ing_act_cobradas:,.2f}", "Recaudado en eventos y proyectos"],
        ["Gastos Operativos Ejecutados", f"S/. {egr_act_ejecutadas:,.2f}", "Costos de mercadería, insumos y logística"],
        ["Ganancia Neta Obtenida", f"S/. {utilidad_neta_act:,.2f}", "Superávit neto de actividades"],
        ["Adeudos Pendientes de Cobro", f"S/. {deuda_actividades:,.2f}", "Créditos por cobrar a comensales/miembros"]
    ], colWidths=[230, 110, 202])
    t_act.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    story.extend([t_act, Spacer(1, 8)])

    story.append(Paragraph("4. DICTAMEN FINANCIERO E INTERPRETACIÓN PARA LA JUNTA DIRECTIVA", style_sec))
    diag_liquidez = "favorable y autosuficiente" if efectivo_libre_operativo > 500 else "ajustada, recomendando cautela"
    texto_dictamen = f"""
    <b>A. Disponibilidad y Salvaguarda de Fondos:</b> Al corte del {u_dia:02d} de {mes_sel} de {anio_sel}, la congregación posee una liquidez física e histórica operativa de <b>S/. {efectivo_libre_operativo:,.2f}</b> de libre disponibilidad. Los fondos restringidos ascienden a <b>S/. {efectivo_no_disponible:,.2f}</b>, los cuales no deben comprometerse en gastos corrientes.<br/>
    <b>B. Diagnóstico Mensual y Adeudos:</b> Evaluando únicamente el mes de {mes_sel} {anio_sel}, la iglesia generó un resultado operativo neto de <b>S/. {superavit_periodo:,.2f}</b>. Asimismo, se arrastra un adeudo total histórico de <b>S/. {total_adeudos:,.2f}</b> por cobrar. La posición general se evalúa como <b>{diag_liquidez}</b>.<br/>
    <b>C. Rendimiento de Actividades:</b> A lo largo del tiempo, las actividades desarrolladas han producido una ganancia neta consolidada de <b>S/. {utilidad_neta_act:,.2f}</b>, demostrando un margen de contribución positivo.
    """
    story.extend([Paragraph(texto_dictamen, style_body), Spacer(1, 18)])

    t_firmas = Table([
        ["__________________________________________", "__________________________________________"],
        [f"{tesorero_tit.upper()}", f"{pastor_tit.upper()}"],
        ["Tesorero(a) General Titular", "Pastor(a) Principal Titular"],
        [f"{nom_iglesia}", f"{denominacion}"]
    ], colWidths=[271, 271])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('PADDING', (0,0), (-1,-1), 2)
    ]))
    story.append(t_firmas)

    doc.build(story)
    return buf.getvalue()

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    st.download_button(
        label="📊 Descargar Informe Mensual (Excel)",
        data=generar_excel_integral_mensual,
        file_name=f"Reporte_Mensual_Nazareth_{periodo_actual_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col_btn2:
    st.download_button(
        label="📄 Descargar Informe Mensual (PDF)",
        data=generar_pdf_gerencial_mensual,
        file_name=f"Reporte_Mensual_Nazareth_{periodo_actual_str}.pdf",
        mime="application/pdf",
        use_container_width=True
    )


# ==============================================================================
# 6. GENERADOR DE REPORTES ANUALES (EXCEL Y PDF CON GRÁFICOS)
# ==============================================================================
st.markdown("---")
st.markdown("#### 📊 Informes de Gestión Anual (Presentación Gerencial)")
st.caption(f"Descarga la recopilación completa de todo el año **{anio_sel}**, incluyendo gráficos, clasificación de gastos, ingresos, diezmos mensuales y actividades consolidadas del año.")

# Preparamos la data anual
df_mov_anio = df_mov[df_mov["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_mov.empty else pd.DataFrame()
df_dz_anio = df_dz[df_dz["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_dz.empty else pd.DataFrame()
df_act_mov_anio = df_act_mov[df_act_mov["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_act_mov.empty else pd.DataFrame()
df_act_anio = df_act[df_act["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_act.empty else pd.DataFrame()

# Totales Generales Anuales
ing_anio_tot = float(df_mov_anio[df_mov_anio["tipo"]=="Ingreso"]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_anio_tot = float(df_mov_anio[df_mov_anio["tipo"]=="Egreso"]["monto"].sum()) if not df_mov_anio.empty else 0.0
dz_anio_tot = float(df_dz_anio["monto"].sum()) if not df_dz_anio.empty else 0.0

# Medio de Pago (Efectivo vs Bancos) Anual
ing_efe_anio = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
ing_ban_anio = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_efe_anio = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_ban_anio = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0

# Arrays Mes a Mes para el gráfico PDF
ing_meses_arr = []
egr_meses_arr = []
dz_meses_arr = []

if not df_mov_anio.empty:
    df_mov_anio["mes_idx"] = df_mov_anio["fecha"].astype(str).str[5:7].astype(int)
if not df_dz_anio.empty:
    df_dz_anio["mes_idx"] = df_dz_anio["fecha"].astype(str).str[5:7].astype(int)

for m in range(1, 13):
    i_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["mes_idx"]==m)]["monto"].sum()) if not df_mov_anio.empty else 0.0
    e_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["mes_idx"]==m)]["monto"].sum()) if not df_mov_anio.empty else 0.0
    d_m = float(df_dz_anio[df_dz_anio["mes_idx"]==m]["monto"].sum()) if not df_dz_anio.empty else 0.0
    ing_meses_arr.append(i_m)
    egr_meses_arr.append(e_m)
    dz_meses_arr.append(d_m)

def dibujar_grafico_vectorial_pdf_anual(titulo, x_labels, y_vals1, c_hex1, legend1, y_vals2=None, c_hex2=None, legend2=None):
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.lib import colors
    d = Drawing(520, 160)
    d.add(Rect(0, 0, 520, 160, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1"), strokeWidth=1, rx=6, ry=6))
    d.add(String(15, 145, titulo, fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#0F172A")))

    d.add(Rect(270, 145, 8, 8, fillColor=colors.HexColor(c_hex1), strokeColor=None))
    d.add(String(282, 145, legend1, fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#334155")))
    if y_vals2 and c_hex2 and legend2:
        d.add(Rect(380, 145, 8, 8, fillColor=colors.HexColor(c_hex2), strokeColor=None))
        d.add(String(392, 145, legend2, fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#334155")))

    max_val = max(max(y_vals1) if y_vals1 else [0], max(y_vals2) if y_vals2 else [0])
    if max_val == 0: max_val = 1.0

    base_y = 25
    chart_h = 95
    spacing = 40
    start_x = 35

    d.add(Line(20, base_y, 500, base_y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1))

    for i, mes in enumerate(x_labels):
        bx = start_x + (i * spacing)
        v1 = y_vals1[i] if i < len(y_vals1) else 0
        bh1 = (v1 / max_val) * chart_h
        d.add(Rect(bx, base_y, 12, max(bh1, 1), fillColor=colors.HexColor(c_hex1), strokeColor=None))
        
        if y_vals2:
            v2 = y_vals2[i] if i < len(y_vals2) else 0
            bh2 = (v2 / max_val) * chart_h
            d.add(Rect(bx + 12, base_y, 12, max(bh2, 1), fillColor=colors.HexColor(c_hex2), strokeColor=None))

        d.add(String(bx + 4, base_y - 12, mes[:3], fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#64748B")))

    return d


def generar_excel_anual():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        
        # 1. Resumen Anual
        df_resumen = pd.DataFrame([
            {"Métrica": "Año Fiscal", "Valor": anio_sel},
            {"Métrica": "Total Ingresos Operativos", "Valor": ing_anio_tot},
            {"Métrica": "Total Egresos y Gastos", "Valor": egr_anio_tot},
            {"Métrica": "Resultado Neto del Año (Ganancia/Pérdida)", "Valor": ing_anio_tot - egr_anio_tot},
            {"Métrica": "Total Diezmos Recaudados", "Valor": dz_anio_tot},
            {"Métrica": "Ingresos por Efectivo", "Valor": ing_efe_anio},
            {"Métrica": "Ingresos por Banco", "Valor": ing_ban_anio},
            {"Métrica": "Egresos por Efectivo", "Valor": egr_efe_anio},
            {"Métrica": "Egresos por Banco", "Valor": egr_ban_anio},
        ])
        df_resumen.to_excel(writer, sheet_name="Resumen_Anual", index=False)
        
        # 2. Mes a Mes
        df_meses = pd.DataFrame({
            "Mes": core.MESES,
            "Ingresos Totales": ing_meses_arr,
            "Egresos Totales": egr_meses_arr,
            "Saldo Neto": [i - e for i, e in zip(ing_meses_arr, egr_meses_arr)],
            "Diezmos Recaudados": dz_meses_arr
        })
        df_meses.to_excel(writer, sheet_name="Comportamiento_Mensual", index=False)
        
        # 3. Clasificación de Gastos e Ingresos
        if not df_mov_anio.empty:
            df_cat = df_mov_anio.groupby(["tipo", "categoria", "subcategoria"])["monto"].sum().reset_index().sort_values(by=["tipo", "monto"], ascending=[True, False])
            df_cat.to_excel(writer, sheet_name="Clasificacion_Categorias", index=False)
            
        # 4. Actividades del año
        if not df_act_anio.empty and not df_act_mov_anio.empty:
            df_mrg_act_a = pd.merge(df_act_mov_anio, df_act_anio, left_on="id_actividad", right_on="id")
            res_act_a = df_mrg_act_a.groupby("nombre").agg(
                Ingresos_Cobrados=("monto", lambda x: x[(df_mrg_act_a.loc[x.index, "tipo"] == "Ingreso") & (df_mrg_act_a.loc[x.index, "estado_cobro"] != "Pendiente")].sum()),
                Egresos=("monto", lambda x: x[df_mrg_act_a.loc[x.index, "tipo"] == "Egreso"].sum()),
            ).reset_index()
            res_act_a["Ganancia Neta"] = res_act_a["Ingresos_Cobrados"] - res_act_a["Egresos"]
            res_act_a.to_excel(writer, sheet_name="Actividades_Anual", index=False)

    return out.getvalue()

def generar_pdf_anual():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=35, rightMargin=35, topMargin=30, bottomMargin=30)
    story = []

    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")
    style_sec = ParagraphStyle('S1', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_prim, spaceBefore=7, spaceAfter=3)

    t_head = Table([
        [
            Paragraph(f"<b>{nom_iglesia.upper()}</b><br/><font size=7.5>{denominacion.upper()}</font>", ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_prim)),
            Paragraph(f"<b>INFORME ANUAL DE GESTIÓN Y ESTADOS FINANCIEROS {anio_sel}</b><br/><font size=7>Emisión: {date.today().strftime('%d/%m/%Y')}</font>", ParagraphStyle('HD', fontName='Helvetica', fontSize=8, alignment=2))
        ]
    ], colWidths=[300, 242])
    t_head.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, c_prim), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")), ('PADDING', (0,0), (-1,-1), 5)]))
    story.extend([t_head, Spacer(1, 10)])

    # 1. Kpis Anuales
    story.append(Paragraph("1. RESUMEN EJECUTIVO ANUAL", style_sec))
    t_liq = Table([
        ["TOTAL INGRESOS AÑO", "TOTAL EGRESOS AÑO", "SUPERÁVIT / DÉFICIT NETO", "TOTAL DIEZMOS AÑO"],
        [f"S/. {ing_anio_tot:,.2f}", f"S/. {egr_anio_tot:,.2f}", f"S/. {ing_anio_tot - egr_anio_tot:,.2f}", f"S/. {dz_anio_tot:,.2f}"]
    ], colWidths=[135, 135, 135, 137])
    t_liq.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_prim), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 7.5), ('FONTSIZE', (0,1), (-1,1), 9.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor("#166534")), ('TEXTCOLOR', (1,1), (1,1), colors.HexColor("#991B1B")),
        ('BACKGROUND', (2,1), (2,1), colors.HexColor("#FEF08A") if (ing_anio_tot - egr_anio_tot) >= 0 else colors.HexColor("#FECACA")),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    story.extend([t_liq, Spacer(1, 10)])

    # Grafico Anual
    story.append(Paragraph("2. EVOLUCIÓN MENSUAL DE INGRESOS VS EGRESOS", style_sec))
    chart = dibujar_grafico_vectorial_pdf_anual(f"Comportamiento Financiero {anio_sel}", core.MESES, ing_meses_arr, "#10B981", "Ingresos", egr_meses_arr, "#EF4444", "Egresos")
    story.extend([chart, Spacer(1, 10)])

    # 3. Comportamiento Mensual Tabla
    story.append(Paragraph("3. COMPORTAMIENTO MENSUAL DETALLADO", style_sec))
    filas_m = [["MES", "INGRESOS (S/.)", "EGRESOS (S/.)", "SALDO NETO (S/.)", "DIEZMOS (S/.)"]]
    for m in range(12):
        s_n = ing_meses_arr[m] - egr_meses_arr[m]
        filas_m.append([core.MESES[m], f"{ing_meses_arr[m]:,.2f}", f"{egr_meses_arr[m]:,.2f}", f"{s_n:,.2f}", f"{dz_meses_arr[m]:,.2f}"])
    
    t_m = Table(filas_m, colWidths=[108, 108, 108, 109, 109])
    t_m.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 3)
    ]))
    story.extend([t_m, Spacer(1, 10)])

    # 4. Clasificacion Gastos Top
    if not df_mov_anio.empty:
        story.append(Paragraph("4. PRINCIPALES CATEGORÍAS DE EGRESOS (TOP 5)", style_sec))
        df_egr_cat = df_mov_anio[df_mov_anio["tipo"]=="Egreso"].groupby("categoria")["monto"].sum().reset_index().sort_values(by="monto", ascending=False).head(5)
        filas_c = [["CATEGORÍA DE GASTO", "MONTO TOTAL INVERTIDO (S/.)"]]
        for _, r in df_egr_cat.iterrows():
            filas_c.append([str(r["categoria"]), f"{r['monto']:,.2f}"])
        t_c = Table(filas_c, colWidths=[400, 142])
        t_c.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7.5), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (1,-1), 'RIGHT')
        ]))
        story.extend([t_c, Spacer(1, 10)])

    # 5. Actividades
    if not df_act_anio.empty and not df_act_mov_anio.empty:
        story.append(Paragraph("5. RESUMEN ANUAL DE ACTIVIDADES ECLESIÁSTICAS", style_sec))
        df_mrg_act_a = pd.merge(df_act_mov_anio, df_act_anio, left_on="id_actividad", right_on="id")
        res_act_a = df_mrg_act_a.groupby("nombre").agg(
            Ingresos=("monto", lambda x: x[(df_mrg_act_a.loc[x.index, "tipo"] == "Ingreso") & (df_mrg_act_a.loc[x.index, "estado_cobro"] != "Pendiente")].sum()),
            Egresos=("monto", lambda x: x[df_mrg_act_a.loc[x.index, "tipo"] == "Egreso"].sum()),
        ).reset_index()
        filas_a = [["NOMBRE DE ACTIVIDAD", "INGRESOS (S/.)", "EGRESOS (S/.)", "GANANCIA NETA (S/.)"]]
        for _, r in res_act_a.iterrows():
            gn = r['Ingresos'] - r['Egresos']
            filas_a.append([str(r["nombre"])[:35], f"{r['Ingresos']:,.2f}", f"{r['Egresos']:,.2f}", f"{gn:,.2f}"])
        t_a = Table(filas_a, colWidths=[242, 100, 100, 100])
        t_a.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 7.5), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT')
        ]))
        story.extend([t_a, Spacer(1, 20)])
    else:
        story.extend([Spacer(1, 20)])

    # Firmas
    t_firmas = Table([
        ["__________________________________________", "__________________________________________"],
        [f"{tesorero_tit.upper()}", f"{pastor_tit.upper()}"],
        ["Tesorero(a) General Titular", "Pastor(a) Principal Titular"]
    ], colWidths=[271, 271])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5), ('PADDING', (0,0), (-1,-1), 2)
    ]))
    story.append(t_firmas)

    doc.build(story)
    return buf.getvalue()

col_btn3, col_btn4 = st.columns(2)
with col_btn3:
    st.download_button(
        label="📊 Descargar Reporte Anual Completo (Excel)",
        data=generar_excel_anual,
        file_name=f"Reporte_Anual_Nazareth_{anio_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )

with col_btn4:
    st.download_button(
        label="📄 Descargar Presentación Anual (PDF)",
        data=generar_pdf_anual,
        file_name=f"Presentacion_Anual_Nazareth_{anio_sel}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary"
    )

st.markdown("---")

# ==============================================================================
# 7. SALDOS POR FONDO Y COMPOSICIÓN (HISTÓRICO ACUMULADO)
# ==============================================================================
st.markdown("##### 💼 Distribución por Fondos Institucionales (Acumulado Histórico)")
cols_f = st.columns(min(len(fondos_list), 5))
for idx, f_nom in enumerate(fondos_list[:5]):
    s_f = fondos_saldos_corte.get(f_nom, 0.0)
    cols_f[idx].metric(f_nom, f"S/. {s_f:,.2f}", delta="Libre" if f_nom == "General" else "Restringido", delta_color="off")

# ==============================================================================
# 8. ÚLTIMOS ASIENTOS REGISTRADOS
# ==============================================================================
st.markdown("##### 📋 Últimas Transacciones Registradas en Tesorería")
if not df_mov.empty:
    df_recientes = df_mov.sort_values(by=["fecha", "id"], ascending=[False, False]).head(8)
    map_rec = {
        "fecha": "Fecha", "tipo": "Tipo", "categoria": "Categoría",
        "fondo": "Fondo", "monto": "Monto", "medio": "Medio",
        "comprobante": "Comprobante", "detalle": "Detalle"
    }
    cols_mostrar = [c for c in map_rec.keys() if c in df_recientes.columns]
    st.dataframe(
        df_recientes[cols_mostrar].rename(columns=map_rec).style.format({"Monto": "S/. {:,.2f}"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Aún no hay movimientos registrados en Tesorería.")

# Pie de página colocado al final absoluto de la pantalla
core.mostrar_pie_pagina()
