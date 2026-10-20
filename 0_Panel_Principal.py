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
# CARGA Y CACHÉ CENTRALIZADO DE DATOS (MÁXIMA VELOCIDAD)
# ==============================================================================
@st.cache_data(ttl=120, show_spinner=False)
def cargar_datos_dashboard():
    try:
        df_m = core.read_db("""
            SELECT id, fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, estado_credito 
            FROM public.movimientos 
            WHERE comprobante NOT LIKE 'ASIENTO-APERTURA%%'
        """)
    except Exception:
        df_m = pd.DataFrame()

    try:
        df_d = core.read_db("SELECT id, fecha, id_miembro, nombre_miembro, mes, medio, monto FROM public.diezmos")
    except Exception:
        df_d = pd.DataFrame()

    try:
        df_am = core.read_db("SELECT id, id_actividad, fecha, tipo, concepto, monto, condicion, cliente_deudor, estado_cobro, medio, fondo_destino, liquidado FROM public.actividad_movimientos")
    except Exception:
        df_am = pd.DataFrame()

    try:
        df_a = core.read_db("SELECT id, nombre, fecha, responsable, estado FROM public.actividades")
    except Exception:
        df_a = pd.DataFrame()

    try:
        df_miem = core.read_db("SELECT id_miembro, nombre FROM public.miembros")
    except Exception:
        df_miem = pd.DataFrame()

    try:
        df_f = core.read_db("SELECT nombre FROM public.fondos_catalogo")
        f_list = df_f["nombre"].tolist() if not df_f.empty else ["General"]
    except Exception:
        f_list = ["General"]

    try:
        df_c = core.read_db("SELECT clave, valor FROM public.config_iglesia")
        cfg_dict = dict(zip(df_c["clave"], df_c["valor"])) if not df_c.empty else {}
    except Exception:
        cfg_dict = {}

    return df_m, df_d, df_am, df_a, df_miem, f_list, cfg_dict

df_mov, df_dz, df_act_mov, df_act, df_miembros, fondos_list, cfg_dict = cargar_datos_dashboard()

nom_iglesia = cfg_dict.get("nombre_iglesia", "IGLESIA EVANGÉLICA NAZARETH")
denominacion = cfg_dict.get("denominacion", "ASAMBLEAS DE DIOS DEL PERÚ")
pastor_tit = cfg_dict.get("pastor_principal", "Pastor Principal")
tesorero_tit = cfg_dict.get("tesorero_general", "Tesorero General")

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
# CÁLCULOS ACUMULADOS HASTA LA FECHA DE CORTE
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

# Filtros por fecha de corte
df_mov_corte = df_mov[df_mov["fecha"] <= fecha_corte_str].copy() if not df_mov.empty and "fecha" in df_mov.columns else pd.DataFrame()
df_act_corte = df_act_mov[df_act_mov["fecha"] <= fecha_corte_str].copy() if not df_act_mov.empty and "fecha" in df_act_mov.columns else pd.DataFrame()

# 1. Fondos restringidos
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

# 2. Deudas y cuentas por cobrar
cred_tesoreria = float(df_mov_corte[(df_mov_corte["tipo"] == "Ingreso") & (df_mov_corte["estado_credito"] == "A Credito")]["monto"].sum()) if not df_mov_corte.empty else 0.0
deuda_actividades = float(df_act_corte[(df_act_corte["condicion"] == "Credito") & (df_act_corte["estado_cobro"] == "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
total_adeudos = cred_tesoreria + deuda_actividades

# 3. Resumen de Actividades
ing_act_cobradas = float(df_act_corte[(df_act_corte["tipo"] == "Ingreso") & (df_act_corte["estado_cobro"] != "Pendiente")]["monto"].sum()) if not df_act_corte.empty else 0.0
egr_act_ejecutadas = float(df_act_corte[df_act_corte["tipo"] == "Egreso"]["monto"].sum()) if not df_act_corte.empty else 0.0
utilidad_neta_act = ing_act_cobradas - egr_act_ejecutadas

# ==============================================================================
# 1. MÉTRICAS DE LIQUIDEZ Y ADEUDOS
# ==============================================================================
st.markdown(f"#### 🏛️ Situación de Liquidez y Adeudos (Al {u_dia:02d} de {mes_sel} {anio_sel})")

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
    help="Caja Física + Saldos en Banco consolidados."
)

st.markdown("---")

# ==============================================================================
# 2. AUDITORÍA FINANCIERA DE ACTIVIDADES
# ==============================================================================
st.markdown("#### 🎯 Rendición Financiera de Actividades Eclesiásticas")

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
# 3. ANÁLISIS DE DIEZMANTE Y FIDELIDAD MENSUAL
# ==============================================================================
st.markdown("#### 📖 Análisis de Fidelidad y Recaudación de Diezmos")
df_dz_analisis = pd.DataFrame()
if not df_dz.empty and "fecha" in df_dz.columns:
    df_dz_temp = df_dz.copy()
    df_dz_temp["dt"] = pd.to_datetime(df_dz_temp["fecha"], errors="coerce")
    df_dz_temp["periodo"] = df_dz_temp["dt"].dt.strftime("%Y-%m")
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
# 4. GENERADOR DE REPORTES (EXCEL Y PDF DIFERIDOS BAJO DEMANDA)
# ==============================================================================
st.markdown("#### 📂 Generador de Informes Oficiales del Periodo")
st.caption(f"Genera la rendición completa para **{mes_sel} {anio_sel}** con balance de liquidez, adeudos y actividades.")

df_mov_mes = pd.DataFrame()
if not df_mov.empty and "fecha" in df_mov.columns:
    df_mov_temp = df_mov.copy()
    df_mov_temp["dt"] = pd.to_datetime(df_mov_temp["fecha"], errors="coerce")
    df_mov_mes = df_mov_temp[(df_mov_temp["dt"].dt.year == anio_sel) & (df_mov_temp["dt"].dt.month == num_m_sel)].copy()

ing_periodo = float(df_mov_mes[df_mov_mes["tipo"] == "Ingreso"]["monto"].sum()) if not df_mov_mes.empty else 0.0
egr_periodo = float(df_mov_mes[df_mov_mes["tipo"] == "Egreso"]["monto"].sum()) if not df_mov_mes.empty else 0.0
superavit_periodo = ing_periodo - egr_periodo

def generar_excel_integral():
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df_ratios = pd.DataFrame([
            {"Indicador": "Fecha de Corte", "Valor": fecha_corte_str},
            {"Indicador": "Periodo Evaluado", "Valor": f"{mes_sel} {anio_sel}"},
            {"Indicador": "Efectivo Disponible (Fondo General Libre)", "Valor": f"S/. {efectivo_libre_operativo:,.2f}"},
            {"Indicador": "Efectivo No Disponible (Fondos Restringidos)", "Valor": f"S/. {efectivo_no_disponible:,.2f}"},
            {"Indicador": "Total Liquidez en Tesorería", "Valor": f"S/. {total_disp:,.2f}"},
            {"Indicador": "Cuentas por Cobrar Totales (Adeudos)", "Valor": f"S/. {total_adeudos:,.2f}"},
            {"Indicador": "Deuda de Actividades por Cobrar", "Valor": f"S/. {deuda_actividades:,.2f}"},
            {"Indicador": "Ganancia Neta en Actividades", "Valor": f"S/. {utilidad_neta_act:,.2f}"},
            {"Indicador": "Ingresos Totales del Mes", "Valor": f"S/. {ing_periodo:,.2f}"},
            {"Indicador": "Egresos Totales del Mes", "Valor": f"S/. {egr_periodo:,.2f}"},
            {"Indicador": "Resultado Operativo del Mes", "Valor": f"S/. {superavit_periodo:,.2f}"},
            {"Indicador": "Hermanos Diezmantes", "Valor": diez_mes},
            {"Indicador": "Cobertura sobre el Padrón", "Valor": f"{cobertura_padron:.1f}%"},
            {"Indicador": "Ticket Promedio por Diezmante", "Valor": f"S/. {ticket_mes:,.2f}"}
        ])
        df_ratios.to_excel(writer, sheet_name="Resumen_Ejecutivo", index=False)

        if not df_mov_mes.empty:
            er_agrupado = df_mov_mes.groupby(["tipo", "categoria", "subcategoria"])["monto"].sum().reset_index()
            er_agrupado.to_excel(writer, sheet_name="Estado_Resultados", index=False)
        else:
            pd.DataFrame({"Mensaje": ["Sin movimientos registrados en este mes"]}).to_excel(writer, sheet_name="Estado_Resultados", index=False)

        if not df_act_corte.empty:
            df_act_corte.to_excel(writer, sheet_name="Actividades_Detalle", index=False)
        else:
            pd.DataFrame({"Mensaje": ["Sin actividades a la fecha de corte"]}).to_excel(writer, sheet_name="Actividades_Detalle", index=False)

        saldos_fondos_data = []
        for fn in fondos_list:
            i_f = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Ingreso")]["monto"].sum()) if not df_mov_corte.empty else 0.0
            e_f = float(df_mov_corte[(df_mov_corte["fondo"] == fn) & (df_mov_corte["tipo"] == "Egreso")]["monto"].sum()) if not df_mov_corte.empty else 0.0
            saldos_fondos_data.append({
                "Fondo": fn, 
                "Condición": "Libre Disponibilidad" if fn == "General" else "Fondo Restringido",
                "Total Ingresos": i_f, 
                "Total Egresos": e_f, 
                "Saldo al Corte": i_f - e_f
            })
        pd.DataFrame(saldos_fondos_data).to_excel(writer, sheet_name="Balance_Fondos", index=False)

        if not df_dz_analisis.empty:
            df_dz_analisis.to_excel(writer, sheet_name="Analisis_Diezmos", index=False)

    return out.getvalue()

def generar_pdf_gerencial():
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
            Paragraph(f"<b>INFORME FINANCIERO MENSUAL Y DE ACTIVIDADES</b><br/><font size=8.5 color='#B45309'><b>CORTE AL: {u_dia:02d} DE {mes_sel.upper()} {anio_sel}</b></font><br/><font size=7>Emisión: {date.today().strftime('%d/%m/%Y')}</font>", ParagraphStyle('HD', fontName='Helvetica', fontSize=7.5, alignment=2))
        ]
    ], colWidths=[330, 212])
    t_head.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, c_prim),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 5)
    ]))
    story.extend([t_head, Spacer(1, 8)])

    story.append(Paragraph("1. ESTADO DE DISPONIBILIDAD LÍQUIDA Y ADEUDOS PENDIENTES", style_sec))
    t_liq = Table([
        ["CONCEPTO FINANCIERO", "CLASIFICACIÓN TÉCNICA", "MONTO AL CORTE (S/.)"],
        ["EFECTIVO DISPONIBLE OPERATIVO", "Fondo General (Uso libre para operación)", f"S/. {efectivo_libre_operativo:,.2f}"],
        ["EFECTIVO NO DISPONIBLE (RESTRINGIDO)", "Fondos Específicos (Pro-Templo, Misiones, etc.)", f"S/. {efectivo_no_disponible:,.2f}"],
        ["TOTAL LIQUIDEZ CONSOLIDADA", "Suma en Caja Física y Cuentas Bancarias", f"S/. {total_disp:,.2f}"],
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

    story.append(Paragraph("2. BALANCE Y AUDITORÍA DE ACTIVIDADES ECLESIÁSTICAS", style_sec))
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

    story.append(Paragraph(f"3. ESTADO OPERATIVO DEL MES ({mes_sel.upper()} {anio_sel}) Y DIEZMOS", style_sec))
    t_er = Table([
        ["PARTIDA", "IMPORTE", "PARTIDA DE DIEZMOS", "RESULTADO"],
        ["Ingresos Totales Mes:", f"S/. {ing_periodo:,.2f}", "Recaudación en Diezmos:", f"S/. {rec_mes:,.2f}"],
        ["Egresos Totales Mes:", f"S/. {egr_periodo:,.2f}", "Hermanos Diezmantes:", f"{diez_mes} de {total_padron}"],
        ["Resultado Neto Mes:", f"S/. {superavit_periodo:,.2f}", "Ticket Promedio:", f"S/. {ticket_mes:,.2f}"]
    ], colWidths=[150, 120, 152, 120])
    t_er.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    story.extend([t_er, Spacer(1, 8)])

    story.append(Paragraph("4. DICTAMEN FINANCIERO E INTERPRETACIÓN PARA LA JUNTA DIRECTIVA", style_sec))
    diag_liquidez = "favorable y autosuficiente" if efectivo_libre_operativo > 500 else "ajustada, recomendando priorizar cobros"
    texto_dictamen = f"""
    <b>A. Disponibilidad y Salvaguarda de Fondos:</b> Al corte del {u_dia:02d} de {mes_sel} de {anio_sel}, la congregación posee una disponibilidad operativa libre de <b>S/. {efectivo_libre_operativo:,.2f}</b>. Los fondos restringidos ascienden a <b>S/. {efectivo_no_disponible:,.2f}</b>, los cuales no deben comprometerse en obligaciones ordinarias por tener asignación específica.<br/>
    <b>B. Diagnóstico de Cuentas por Cobrar:</b> Se registra un adeudo acumulado total de <b>S/. {total_adeudos:,.2f}</b> (donde <b>S/. {deuda_actividades:,.2f}</b> corresponden a actividades eclesiásticas). La posición operativa general se evalúa como <b>{diag_liquidez}</b>. Se instruye a la tesorería agilizar la recuperación de estos adeudos para convertirlos en liquidez real.<br/>
    <b>C. Rendimiento de Actividades:</b> Las actividades desarrolladas han producido una ganancia neta líquida de <b>S/. {utilidad_neta_act:,.2f}</b>, demostrando un margen de contribución positivo a los objetivos de la congregación.
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
        label="📊 Descargar Análisis Completo en Excel (.xlsx)",
        data=generar_excel_integral,
        file_name=f"Analisis_Financiero_Nazareth_{periodo_actual_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

with col_btn2:
    st.download_button(
        label="📄 Descargar Informe Mensual con Dictamen en PDF",
        data=generar_pdf_gerencial,
        file_name=f"Informe_Financiero_Nazareth_{periodo_actual_str}.pdf",
        mime="application/pdf",
        type="secondary"
    )

st.markdown("---")

# ==============================================================================
# 5. SALDOS POR FONDO Y COMPOSICIÓN
# ==============================================================================
st.markdown("##### 💼 Distribución por Fondos Institucionales")
cols_f = st.columns(min(len(fondos_list), 5))
for idx, f_nom in enumerate(fondos_list[:5]):
    s_f = fondos_saldos_corte.get(f_nom, 0.0)
    cols_f[idx].metric(f_nom, f"S/. {s_f:,.2f}", delta="Libre" if f_nom == "General" else "Restringido", delta_color="off")

# ==============================================================================
# 6. ÚLTIMOS ASIENTOS REGISTRADOS
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
