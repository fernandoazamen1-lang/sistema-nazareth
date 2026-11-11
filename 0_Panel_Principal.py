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
# ENCABEZADO Y SELECTOR DE CORTE
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
@st.cache_data(ttl=86400, show_spinner=False)
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

@st.cache_data(ttl=180, show_spinner=False)
def cargar_datos_periodo(corte_str):
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

df_miembros, fondos_list, cfg_dict = cargar_catalogos_fijos()
df_mov, df_dz, df_act_mov, df_act = cargar_datos_periodo(fecha_corte_str)

nom_iglesia = cfg_dict.get("nombre_iglesia", "IGLESIA EVANGÉLICA NAZARETH")
denominacion = cfg_dict.get("denominacion", "ASAMBLEAS DE DIOS DEL PERÚ")
pastor_tit = cfg_dict.get("pastor_principal", "Pastor Principal")
tesorero_tit = cfg_dict.get("tesorero_general", "Tesorero General")

# ==============================================================================
# CÁLCULOS HISTÓRICOS ACUMULADOS
# ==============================================================================
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

cred_tesoreria = float(df_mov_corte[(df_mov_corte["tipo"] == "Ingreso") & (df_mov_corte["estado_credito"] == "A Credito")]["monto"].sum()) if not df_mov_corte.empty else 0.0
deuda_actividades = float(df_act_corte[(df_act_corte["condicion"] == "Credito") & (df_act_corte["estado_cobro"] == "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
total_adeudos = cred_tesoreria + deuda_actividades

ing_act_cobradas = float(df_act_corte[(df_act_corte["tipo"] == "Ingreso") & (df_act_corte["estado_cobro"] != "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
egr_act_ejecutadas = float(df_act_corte[df_act_corte["tipo"] == "Egreso"]["monto"].sum()) if not df_act_corte.empty else 0.0
utilidad_neta_act = ing_act_cobradas - egr_act_ejecutadas

# ==============================================================================
# CÁLCULOS ESPECÍFICOS DEL MES AISLADO
# ==============================================================================
df_mov_mes = pd.DataFrame()
if not df_mov.empty and "fecha" in df_mov.columns:
    df_mov_temp = df_mov.copy()
    df_mov_temp["periodo"] = df_mov_temp["fecha"].astype(str).str[:7]
    df_mov_mes = df_mov_temp[df_mov_temp["periodo"] == periodo_actual_str].copy()

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
r1.metric("🟢 Nuevos Ingresos del Mes", f"S/. {ing_periodo:,.2f}")
r2.metric("🔴 Gastos y Egresos del Mes", f"S/. {egr_periodo:,.2f}")
r3.metric(
    "⚖️ Resultado Neto del Mes", 
    f"S/. {superavit_periodo:,.2f}", 
    delta="Superávit Operativo" if superavit_periodo >= 0 else "Déficit Operativo",
    delta_color="normal" if superavit_periodo >= 0 else "inverse"
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
                st.dataframe(res_act.rename(columns={"nombre": "Actividad"}).style.format({"Ingresos_Cobrados": "S/. {:,.2f}", "Egresos": "S/. {:,.2f}", "Por_Cobrar": "S/. {:,.2f}", "Utilidad_Neta": "S/. {:,.2f}"}), use_container_width=True, hide_index=True)
        
        with col_deud_tab:
            st.markdown("##### 👥 Deudas Pendientes:")
            deudores_df = df_act_corte[(df_act_corte["condicion"] == "Credito") & (df_act_corte["estado_cobro"] == "Pendiente")][["cliente_deudor", "concepto", "monto"]]
            if not deudores_df.empty:
                st.dataframe(deudores_df.rename(columns={"cliente_deudor": "Hermano / Deudor", "concepto": "Concepto", "monto": "Deuda"}).style.format({"Deuda": "S/. {:,.2f}"}), use_container_width=True, hide_index=True)
            else:
                st.success("✅ No se registran deudas pendientes.")

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
d2.metric(f"Hermanos Diezmantes ({mes_sel})", f"{diez_mes} personas")
d3.metric("Aporte Promedio / Hermano", f"S/. {ticket_mes:,.2f}")
d4.metric("Cobertura sobre el Padrón", f"{cobertura_padron:.1f}%")

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
            df_mov_mes.groupby(["tipo", "categoria", "subcategoria"])["monto"].sum().reset_index().to_excel(writer, sheet_name=f"Ingresos_Egresos_{mes_sel}", index=False)
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

    t_head = Table([
        [
            Paragraph(f"<b>{nom_iglesia.upper()}</b><br/><font size=7.5>{denominacion.upper()}</font>", ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_prim)),
            Paragraph(f"<b>INFORME FINANCIERO MENSUAL GERENCIAL</b><br/><font size=8.5 color='#B45309'><b>CORTE AL: {u_dia:02d} DE {mes_sel.upper()} {anio_sel}</b></font>", ParagraphStyle('HD', fontName='Helvetica', fontSize=7.5, alignment=2))
        ]
    ], colWidths=[330, 212])
    t_head.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, c_prim), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")), ('PADDING', (0,0), (-1,-1), 5)]))
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
        ('BACKGROUND', (0,0), (-1,0), c_prim), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#EFF6FF")), ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#FEF2F2")), ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'),
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5), ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('BACKGROUND', (0,3), (1,3), colors.HexColor("#FEF08A") if superavit_periodo >= 0 else colors.HexColor("#FECACA")),
        ('FONTNAME', (0,3), (1,3), 'Helvetica-Bold'), ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    story.extend([t_er, Spacer(1, 20)])

    t_firmas = Table([
        ["__________________________________________", "__________________________________________"],
        [f"{tesorero_tit.upper()}", f"{pastor_tit.upper()}"],
        ["Tesorero(a) General Titular", "Pastor(a) Principal Titular"],
        [f"{nom_iglesia}", f"{denominacion}"]
    ], colWidths=[271, 271])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5), ('PADDING', (0,0), (-1,-1), 2)
    ]))
    story.append(t_firmas)
    doc.build(story)
    return buf.getvalue()

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    st.download_button("📊 Descargar Informe Mensual (Excel)", data=generar_excel_integral_mensual(), file_name=f"Reporte_Mensual_{periodo_actual_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with col_btn2:
    st.download_button("📄 Descargar Informe Mensual (PDF)", data=generar_pdf_gerencial_mensual(), file_name=f"Reporte_Mensual_{periodo_actual_str}.pdf", mime="application/pdf", use_container_width=True)

# ==============================================================================
# 6. GENERADOR DE REPORTES ANUALES MULTI-PÁGINAS (EXCEL Y PDF AVANZADO)
# ==============================================================================
st.markdown("---")
st.markdown("#### 📊 Informes de Gestión Anual (Presentación Gerencial)")
st.caption(f"Descarga la recopilación exhaustiva del año **{anio_sel}**. El PDF contiene más de 10 secciones de análisis detallado, tablas mes a mes y conclusiones financieras automáticas.")

# Preparamos la data anual
df_mov_anio = df_mov[df_mov["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_mov.empty else pd.DataFrame()
df_dz_anio = df_dz[df_dz["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_dz.empty else pd.DataFrame()
df_act_mov_anio = df_act_mov[df_act_mov["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_act_mov.empty else pd.DataFrame()
df_act_anio = df_act[df_act["fecha"].astype(str).str.startswith(str(anio_sel))].copy() if not df_act.empty else pd.DataFrame()

# Cálculos Totales Anuales
ing_anio_tot = float(df_mov_anio[df_mov_anio["tipo"]=="Ingreso"]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_anio_tot = float(df_mov_anio[df_mov_anio["tipo"]=="Egreso"]["monto"].sum()) if not df_mov_anio.empty else 0.0
dz_anio_tot = float(df_dz_anio["monto"].sum()) if not df_dz_anio.empty else 0.0
saldo_neto_anio = ing_anio_tot - egr_anio_tot

# Bancarización Anual
ing_efe_a = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
ing_ban_a = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_efe_a = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
egr_ban_a = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0

# Arrays Mes a Mes
ing_meses_arr, egr_meses_arr, dz_meses_arr = [], [], []
ing_efe_mes, ing_ban_mes, egr_efe_mes, egr_ban_mes = [], [], [], []

if not df_mov_anio.empty: df_mov_anio["mes_idx"] = df_mov_anio["fecha"].astype(str).str[5:7].astype(int)
if not df_dz_anio.empty: df_dz_anio["mes_idx"] = df_dz_anio["fecha"].astype(str).str[5:7].astype(int)

for m in range(1, 13):
    i_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["mes_idx"]==m)]["monto"].sum()) if not df_mov_anio.empty else 0.0
    e_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["mes_idx"]==m)]["monto"].sum()) if not df_mov_anio.empty else 0.0
    d_m = float(df_dz_anio[df_dz_anio["mes_idx"]==m]["monto"].sum()) if not df_dz_anio.empty else 0.0
    
    ie_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["mes_idx"]==m) & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
    ib_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Ingreso") & (df_mov_anio["mes_idx"]==m) & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
    ee_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["mes_idx"]==m) & (df_mov_anio["medio"]=="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
    eb_m = float(df_mov_anio[(df_mov_anio["tipo"]=="Egreso") & (df_mov_anio["mes_idx"]==m) & (df_mov_anio["medio"]!="Efectivo")]["monto"].sum()) if not df_mov_anio.empty else 0.0
    
    ing_meses_arr.append(i_m)
    egr_meses_arr.append(e_m)
    dz_meses_arr.append(d_m)
    ing_efe_mes.append(ie_m); ing_ban_mes.append(ib_m)
    egr_efe_mes.append(ee_m); egr_ban_mes.append(eb_m)

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

    # CORRECCIÓN DEL CÁLCULO MÁXIMO (Evita el TypeError de la lista)
    m1 = max(y_vals1) if y_vals1 else 0
    m2 = max(y_vals2) if y_vals2 else 0
    max_val = max(m1, m2)
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

def generar_pdf_anual_detallado():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story = []

    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")
    s_tit = ParagraphStyle('T1', fontName='Helvetica-Bold', fontSize=14, textColor=c_prim, alignment=1, spaceAfter=20)
    s_sec = ParagraphStyle('S1', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor("#0F172A"), spaceBefore=15, spaceAfter=8)
    s_bod = ParagraphStyle('B1', fontName='Helvetica', fontSize=9, leading=12, alignment=4, spaceAfter=15)
    s_concl = ParagraphStyle('C1', fontName='Helvetica-Oblique', fontSize=9, leading=12, textColor=colors.HexColor("#475569"), alignment=4, leftIndent=10, rightIndent=10, spaceBefore=5, spaceAfter=20)

    # ================= PÁGINA 1: PORTADA Y RESUMEN =================
    t_head = Table([
        [
            Paragraph(f"<b>{nom_iglesia.upper()}</b><br/><font size=9>{denominacion.upper()}</font>", ParagraphStyle('H', fontName='Helvetica-Bold', fontSize=12, textColor=c_prim)),
            Paragraph(f"<b>INFORME FINANCIERO ANUAL {anio_sel}</b><br/><font size=8>Emisión: {date.today().strftime('%d/%m/%Y')}</font>", ParagraphStyle('HD', fontName='Helvetica', fontSize=9, alignment=2))
        ]
    ], colWidths=[300, 230])
    t_head.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, c_prim), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")), ('PADDING', (0,0), (-1,-1), 10)]))
    story.extend([t_head, Spacer(1, 30)])

    story.append(Paragraph(f"MEMORIA FINANCIERA Y ADMINISTRATIVA — AÑO FISCAL {anio_sel}", s_tit))
    story.append(Paragraph("1. RESUMEN EJECUTIVO Y MACRO INDICADORES", s_sec))
    
    t_kpi = Table([
        ["TOTAL INGRESOS", "TOTAL EGRESOS", "SUPERÁVIT NETO", "TOTAL DIEZMOS"],
        [f"S/. {ing_anio_tot:,.2f}", f"S/. {egr_anio_tot:,.2f}", f"S/. {saldo_neto_anio:,.2f}", f"S/. {dz_anio_tot:,.2f}"]
    ], colWidths=[132, 132, 132, 134])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_prim), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 8), ('FONTSIZE', (0,1), (-1,1), 11),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor("#166534")), ('TEXTCOLOR', (1,1), (1,1), colors.HexColor("#991B1B")),
        ('BACKGROUND', (2,1), (2,1), colors.HexColor("#FEF08A") if saldo_neto_anio >= 0 else colors.HexColor("#FECACA")),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    story.extend([t_kpi, Spacer(1, 20)])

    txt_res = f"El presente informe detalla el comportamiento económico consolidado de la congregación durante los 12 meses del año {anio_sel}. En este periodo, los ingresos brutos alcanzaron la cifra de S/. {ing_anio_tot:,.2f}, frente a unos gastos operativos de S/. {egr_anio_tot:,.2f}. Esto resulta en un balance neto {'positivo (superávit)' if saldo_neto_anio >=0 else 'negativo (déficit)'} de S/. {saldo_neto_anio:,.2f}."
    story.append(Paragraph(txt_res, s_bod))
    story.append(PageBreak())

    # ================= PÁGINA 2: INGRESOS =================
    story.append(Paragraph("2. ANÁLISIS MENSUAL DE INGRESOS OPERATIVOS", s_sec))
    filas_i = [["MES", "INGRESOS (S/.)", "% DEL TOTAL"]]
    for i, m in enumerate(core.MESES):
        pct = (ing_meses_arr[i] / ing_anio_tot * 100) if ing_anio_tot > 0 else 0
        filas_i.append([m, f"S/. {ing_meses_arr[i]:,.2f}", f"{pct:.1f}%"])
    filas_i.append(["TOTAL ANUAL", f"S/. {ing_anio_tot:,.2f}", "100%"])
    t_i = Table(filas_i, colWidths=[176, 176, 178])
    t_i.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
    ]))
    story.extend([t_i, Spacer(1, 15)])
    story.append(dibujar_grafico_vectorial_pdf_anual(f"Comportamiento de Ingresos {anio_sel}", core.MESES, ing_meses_arr, "#10B981", "Ingresos"))
    
    max_ing_mes = core.MESES[np.argmax(ing_meses_arr)] if sum(ing_meses_arr) > 0 else "N/A"
    prom_ing = ing_anio_tot / 12
    concl_i = f"<b>Conclusión Financiera:</b> El promedio de recaudación mensual se ubicó en S/. {prom_ing:,.2f}. El mes con mayor captación de ingresos fue {max_ing_mes} con S/. {max(ing_meses_arr):,.2f}, lo cual marca una pauta estacional importante para la proyección de presupuestos del próximo año."
    story.extend([Spacer(1, 10), Paragraph(concl_i, s_concl), PageBreak()])

    # ================= PÁGINA 3: EGRESOS =================
    story.append(Paragraph("3. ANÁLISIS MENSUAL DE EGRESOS Y GASTOS", s_sec))
    filas_e = [["MES", "GASTOS (S/.)", "% DEL TOTAL"]]
    for i, m in enumerate(core.MESES):
        pct = (egr_meses_arr[i] / egr_anio_tot * 100) if egr_anio_tot > 0 else 0
        filas_e.append([m, f"S/. {egr_meses_arr[i]:,.2f}", f"{pct:.1f}%"])
    filas_e.append(["TOTAL ANUAL", f"S/. {egr_anio_tot:,.2f}", "100%"])
    t_e = Table(filas_e, colWidths=[176, 176, 178])
    t_e.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
    ]))
    story.extend([t_e, Spacer(1, 15)])
    story.append(dibujar_grafico_vectorial_pdf_anual(f"Comportamiento de Egresos {anio_sel}", core.MESES, egr_meses_arr, "#EF4444", "Egresos"))
    
    max_egr_mes = core.MESES[np.argmax(egr_meses_arr)] if sum(egr_meses_arr) > 0 else "N/A"
    prom_egr = egr_anio_tot / 12
    concl_e = f"<b>Conclusión Financiera:</b> La iglesia mantuvo un ritmo de gasto promedio de S/. {prom_egr:,.2f} al mes. El pico máximo de egresos ocurrió en {max_egr_mes} alcanzando S/. {max(egr_meses_arr):,.2f}, requiriendo especial atención preventiva en dicho periodo para evitar estrés de liquidez futuro."
    story.extend([Spacer(1, 10), Paragraph(concl_e, s_concl), PageBreak()])

    # ================= PÁGINA 4: BALANCE OPERATIVO =================
    story.append(Paragraph("4. BALANCE OPERATIVO NETO (INGRESOS VS EGRESOS)", s_sec))
    filas_b = [["MES", "INGRESOS", "EGRESOS", "SALDO LÍQUIDO", "ESTADO"]]
    meses_positivos = 0
    for i, m in enumerate(core.MESES):
        sn = ing_meses_arr[i] - egr_meses_arr[i]
        estado = "Superávit" if sn >= 0 else "Déficit"
        if sn >= 0: meses_positivos += 1
        filas_b.append([m, f"{ing_meses_arr[i]:,.2f}", f"{egr_meses_arr[i]:,.2f}", f"{sn:,.2f}", estado])
    t_b = Table(filas_b, colWidths=[100, 100, 100, 100, 130])
    t_b.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (3,-1), 'RIGHT'), ('ALIGN', (4,1), (4,-1), 'CENTER')
    ]))
    story.extend([t_b, Spacer(1, 15)])
    story.append(dibujar_grafico_vectorial_pdf_anual(f"Comparativo {anio_sel}", core.MESES, ing_meses_arr, "#10B981", "Ingresos", egr_meses_arr, "#EF4444", "Egresos"))
    
    concl_b = f"<b>Conclusión Financiera:</b> De los 12 meses evaluados, la congregación logró {meses_positivos} meses con saldo operativo positivo (Superávit) y {12 - meses_positivos} meses en negativo (Déficit). La consolidación anual es {'saludable' if saldo_neto_anio >= 0 else 'crítica'}, requiriendo ajustes estratégicos si se presentan déficits prolongados."
    story.extend([Spacer(1, 10), Paragraph(concl_b, s_concl), PageBreak()])

    # ================= PÁGINA 5: DIEZMOS =================
    story.append(Paragraph("5. FIDELIDAD Y RECAUDACIÓN DE DIEZMOS", s_sec))
    filas_d = [["MES", "RECAUDACIÓN DE DIEZMOS (S/.)"]]
    for i, m in enumerate(core.MESES):
        filas_d.append([m, f"S/. {dz_meses_arr[i]:,.2f}"])
    filas_d.append(["TOTAL ANUAL", f"S/. {dz_anio_tot:,.2f}"])
    t_d = Table(filas_d, colWidths=[265, 265])
    t_d.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
    ]))
    story.extend([t_d, Spacer(1, 15)])
    story.append(dibujar_grafico_vectorial_pdf_anual(f"Diezmos Recaudados {anio_sel}", core.MESES, dz_meses_arr, "#6366F1", "Diezmos Mensuales"))
    
    pct_diezmos = (dz_anio_tot / ing_anio_tot * 100) if ing_anio_tot > 0 else 0
    prom_dz = dz_anio_tot / 12
    concl_d = f"<b>Conclusión Financiera:</b> Los diezmos representan el {pct_diezmos:.1f}% de la totalidad de ingresos anuales de la iglesia. Mantener un promedio de S/. {prom_dz:,.2f} mensuales en este rubro es el pilar fundamental que garantiza la sostenibilidad del ministerio."
    story.extend([Spacer(1, 10), Paragraph(concl_d, s_concl), PageBreak()])

    # ================= PÁGINA 6: BANCARIZACIÓN =================
    story.append(Paragraph("6. COMPOSICIÓN DE FLUJO (EFECTIVO VS BANCOS)", s_sec))
    filas_bk = [["MES", "ING. EFECTIVO", "ING. BANCO", "EGR. EFECTIVO", "EGR. BANCO"]]
    for i, m in enumerate(core.MESES):
        filas_bk.append([m, f"{ing_efe_mes[i]:,.2f}", f"{ing_ban_mes[i]:,.2f}", f"{egr_efe_mes[i]:,.2f}", f"{egr_ban_mes[i]:,.2f}"])
    filas_bk.append(["TOTAL", f"{ing_efe_a:,.2f}", f"{ing_ban_a:,.2f}", f"{egr_efe_a:,.2f}", f"{egr_ban_a:,.2f}"])
    t_bk = Table(filas_bk, colWidths=[110, 105, 105, 105, 105])
    t_bk.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#F1F5F9")), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
    ]))
    story.extend([t_bk, Spacer(1, 15)])
    
    pct_banco = ((ing_ban_a + egr_ban_a) / (ing_anio_tot + egr_anio_tot) * 100) if (ing_anio_tot + egr_anio_tot) > 0 else 0
    concl_bk = f"<b>Conclusión Financiera:</b> El volumen operado mediante transferencias y depósitos bancarios representa un {pct_banco:.1f}% de las transacciones totales. A mayor porcentaje bancarizado, mayor transparencia fiscal y seguridad se obtiene para los fondos eclesiásticos frente a auditorías."
    story.extend([Paragraph(concl_bk, s_concl), PageBreak()])

    # ================= PÁGINA 7: CLASIFICACIÓN DE INGRESOS =================
    story.append(Paragraph("7. CLASIFICACIÓN DETALLADA DE INGRESOS", s_sec))
    if not df_mov_anio.empty:
        df_ing_cat = df_mov_anio[df_mov_anio["tipo"]=="Ingreso"].groupby(["categoria", "subcategoria"])["monto"].sum().reset_index().sort_values(by="monto", ascending=False)
        if not df_ing_cat.empty:
            filas_ic = [["CATEGORÍA", "RUBRO / SUBCATEGORÍA", "MONTO TOTAL (S/.)", "%"]]
            for _, r in df_ing_cat.iterrows():
                p_c = (r['monto'] / ing_anio_tot * 100) if ing_anio_tot > 0 else 0
                filas_ic.append([str(r["categoria"])[:25], str(r["subcategoria"])[:25], f"{r['monto']:,.2f}", f"{p_c:.1f}%"])
            t_ic = Table(filas_ic, colWidths=[175, 175, 100, 80])
            t_ic.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ('FONTSIZE', (0,0), (-1,-1), 8)
            ]))
            story.extend([t_ic, Spacer(1, 15)])
            top_cat_i = df_ing_cat.iloc[0]['categoria'] if len(df_ing_cat) > 0 else "N/A"
            concl_ic = f"<b>Conclusión Financiera:</b> La fuente principal de ingresos recae sobre la categoría '{top_cat_i}'. Se recomienda diversificar las actividades pro-fondos para reducir la dependencia de un solo rubro operativo."
            story.append(Paragraph(concl_ic, s_concl))
    story.append(PageBreak())

    # ================= PÁGINA 8: CLASIFICACIÓN DE EGRESOS =================
    story.append(Paragraph("8. CLASIFICACIÓN DETALLADA DE GASTOS Y EGRESOS", s_sec))
    if not df_mov_anio.empty:
        df_egr_cat2 = df_mov_anio[df_mov_anio["tipo"]=="Egreso"].groupby(["categoria", "subcategoria"])["monto"].sum().reset_index().sort_values(by="monto", ascending=False)
        if not df_egr_cat2.empty:
            filas_ec = [["CATEGORÍA", "RUBRO / SUBCATEGORÍA", "MONTO TOTAL (S/.)", "%"]]
            for _, r in df_egr_cat2.iterrows():
                p_c = (r['monto'] / egr_anio_tot * 100) if egr_anio_tot > 0 else 0
                filas_ec.append([str(r["categoria"])[:25], str(r["subcategoria"])[:25], f"{r['monto']:,.2f}", f"{p_c:.1f}%"])
            t_ec = Table(filas_ec, colWidths=[175, 175, 100, 80])
            t_ec.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ('FONTSIZE', (0,0), (-1,-1), 8)
            ]))
            story.extend([t_ec, Spacer(1, 15)])
            top_cat_e = df_egr_cat2.iloc[0]['categoria'] if len(df_egr_cat2) > 0 else "N/A"
            concl_ec = f"<b>Conclusión Financiera:</b> La categoría '{top_cat_e}' ha absorbido la mayor cantidad de recursos de tesorería este año. La Junta Administrativa debe revisar estas partidas mayores para identificar posibles ahorros y optimizar las compras futuras."
            story.append(Paragraph(concl_ec, s_concl))
    story.append(PageBreak())

    # ================= PÁGINA 9: ACTIVIDADES =================
    story.append(Paragraph("9. RENDIMIENTO DE ACTIVIDADES ECLESIÁSTICAS", s_sec))
    if not df_act_anio.empty and not df_act_mov_anio.empty:
        df_mrg_act_a = pd.merge(df_act_mov_anio, df_act_anio, left_on="id_actividad", right_on="id")
        res_act_a = df_mrg_act_a.groupby("nombre").agg(
            Ingresos=("monto", lambda x: x[(df_mrg_act_a.loc[x.index, "tipo"] == "Ingreso") & (df_mrg_act_a.loc[x.index, "estado_cobro"] != "Pendiente")].sum()),
            Egresos=("monto", lambda x: x[df_mrg_act_a.loc[x.index, "tipo"] == "Egreso"].sum()),
        ).reset_index()
        filas_a = [["NOMBRE DE ACTIVIDAD", "INGRESOS (S/.)", "EGRESOS (S/.)", "GANANCIA NETA"]]
        act_positivas = 0
        tot_ganancia_act = 0
        for _, r in res_act_a.iterrows():
            gn = r['Ingresos'] - r['Egresos']
            if gn > 0: act_positivas += 1
            tot_ganancia_act += gn
            filas_a.append([str(r["nombre"])[:35], f"{r['Ingresos']:,.2f}", f"{r['Egresos']:,.2f}", f"{gn:,.2f}"])
        t_a = Table(filas_a, colWidths=[230, 100, 100, 100])
        t_a.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, c_borde), ('ALIGN', (1,0), (-1,-1), 'RIGHT')
        ]))
        story.extend([t_a, Spacer(1, 15)])
        
        concl_act = f"<b>Conclusión Financiera:</b> De los {len(res_act_a)} eventos desarrollados en el año, {act_positivas} arrojaron un saldo a favor. Las actividades inyectaron una liquidez libre de S/. {tot_ganancia_act:,.2f} a las arcas generales."
        story.append(Paragraph(concl_act, s_concl))
    else:
        story.append(Paragraph("No se registraron movimientos en actividades durante este periodo.", s_bod))
    story.append(PageBreak())

    # ================= PÁGINA 10: DICTAMEN =================
    story.append(Paragraph("10. DICTAMEN FINAL, RECOMENDACIONES Y FIRMAS", s_sec))
    diag_anual = "saludable, evidenciando un manejo responsable de las finanzas y un compromiso sólido de los miembros" if saldo_neto_anio >= 0 else "de alerta técnica, requiriendo un urgente recorte de gastos ordinarios y un fortalecimiento agresivo en la recaudación pro-fondos"
    
    dictamen_final = f"""
    Tras evaluar minuciosamente todos los libros contables, movimientos bancarios y efectivos, registro de diezmos y actividades pro-templo correspondientes al año fiscal {anio_sel}, el Departamento de Administración dictamina que la posición general es <b>{diag_anual}</b>.<br/><br/>
    <b>Recomendaciones a la Junta Directiva:</b><br/>
    1. Mantener un fondo de contingencia líquido equivalente a 2 meses de gastos operativos promedios (S/. {prom_egr*2:,.2f}).<br/>
    2. Minimizar el índice de cuentas por cobrar en los eventos gastronómicos, exigiendo pagos anticipados en un mayor porcentaje.<br/>
    3. Fomentar la bancarización de ofrendas para blindar a la congregación ante cualquier requerimiento tributario estatal en el futuro.
    """
    story.extend([Paragraph(dictamen_final, s_bod), Spacer(1, 60)])

    t_firmas = Table([
        ["__________________________________________", "__________________________________________"],
        [f"{tesorero_tit.upper()}", f"{pastor_tit.upper()}"],
        ["Tesorero(a) General Titular", "Pastor(a) Principal Titular"],
        [f"DNI/ID:", f"DNI/ID:"]
    ], colWidths=[265, 265])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5), ('PADDING', (0,0), (-1,-1), 4)
    ]))
    story.append(t_firmas)

    doc.build(story)
    return buf.getvalue()

def generar_excel_anual():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df_resumen = pd.DataFrame([
            {"Métrica": "Año Fiscal", "Valor": anio_sel},
            {"Métrica": "Total Ingresos Operativos", "Valor": ing_anio_tot},
            {"Métrica": "Total Egresos y Gastos", "Valor": egr_anio_tot},
            {"Métrica": "Resultado Neto del Año (Ganancia/Pérdida)", "Valor": saldo_neto_anio},
            {"Métrica": "Total Diezmos Recaudados", "Valor": dz_anio_tot},
            {"Métrica": "Ingresos por Efectivo", "Valor": ing_efe_a},
            {"Métrica": "Ingresos por Banco", "Valor": ing_ban_a},
            {"Métrica": "Egresos por Efectivo", "Valor": egr_efe_a},
            {"Métrica": "Egresos por Banco", "Valor": egr_ban_a},
        ])
        df_resumen.to_excel(writer, sheet_name="Resumen_Anual", index=False)
        
        df_meses = pd.DataFrame({
            "Mes": core.MESES,
            "Ingresos Totales": ing_meses_arr,
            "Egresos Totales": egr_meses_arr,
            "Saldo Neto": [i - e for i, e in zip(ing_meses_arr, egr_meses_arr)],
            "Diezmos Recaudados": dz_meses_arr
        })
        df_meses.to_excel(writer, sheet_name="Comportamiento_Mensual", index=False)
        
        if not df_mov_anio.empty:
            df_cat = df_mov_anio.groupby(["tipo", "categoria", "subcategoria"])["monto"].sum().reset_index().sort_values(by=["tipo", "monto"], ascending=[True, False])
            df_cat.to_excel(writer, sheet_name="Clasificacion_Categorias", index=False)
            
        if not df_act_anio.empty and not df_act_mov_anio.empty:
            df_mrg_act_a = pd.merge(df_act_mov_anio, df_act_anio, left_on="id_actividad", right_on="id")
            res_act_a = df_mrg_act_a.groupby("nombre").agg(
                Ingresos_Cobrados=("monto", lambda x: x[(df_mrg_act_a.loc[x.index, "tipo"] == "Ingreso") & (df_mrg_act_a.loc[x.index, "estado_cobro"] != "Pendiente")].sum()),
                Egresos=("monto", lambda x: x[df_mrg_act_a.loc[x.index, "tipo"] == "Egreso"].sum()),
            ).reset_index()
            res_act_a["Ganancia Neta"] = res_act_a["Ingresos_Cobrados"] - res_act_a["Egresos"]
            res_act_a.to_excel(writer, sheet_name="Actividades_Anual", index=False)

    return out.getvalue()

col_btn3, col_btn4 = st.columns(2)
with col_btn3:
    st.download_button(
        label="📊 Descargar Reporte Anual en Excel (.xlsx)",
        data=generar_excel_anual(),
        file_name=f"Auditoria_Anual_Nazareth_{anio_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )

with col_btn4:
    st.download_button(
        label="📄 Descargar Presentación Anual Gerencial (PDF de 10 hojas)",
        data=generar_pdf_anual_detallado(),
        file_name=f"Memoria_Anual_Financiera_{anio_sel}.pdf",
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
