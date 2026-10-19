import streamlit as st
import core
import io
import pandas as pd
from datetime import date, datetime
import plotly.graph_objects as go
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

st.set_page_config(
    page_title="Tesorería y Movimientos", 
    page_icon="🏛️", 
    layout="wide",
    initial_sidebar_state="expanded"
)
core.requerir_login()
core.aplicar_estilos_base()

# Catálogo de fondos
df_fondos = core.read_db("SELECT nombre FROM public.fondos_catalogo")
fondos = df_fondos["nombre"].tolist() if not df_fondos.empty else ["General"]

# ==============================================================================
# GENERADORES DE REPORTES PDF Y EXCEL
# ==============================================================================
def generar_pdf_libro_caja(df_reporte, tot_i, tot_e, saldo_n):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    t_head = Table([[
        Paragraph(
            "<b>IGLESIA EVANGÉLICA \"NAZARETH\" — ASAMBLEAS DE DIOS DEL PERÚ</b><br/>"
            "<font size=9 color='#1E3A8A'>LIBRO OFICIAL DE CAJA Y MOVIMIENTOS DE TESORERÍA</font>",
            ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=11, textColor=c_prim)
        ),
        Paragraph(
            f"<b>Emisión:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
            f"<font size=8>Registros listados: {len(df_reporte)}</font>",
            ParagraphStyle('H2', fontName='Helvetica', fontSize=8, alignment=2)
        )
    ]], colWidths=[540, 200])
    t_head.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1D4ED8")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    elem.extend([t_head, Spacer(1, 10)])

    t_resumen = Table([
        ["TOTAL INGRESOS", "TOTAL EGRESOS", "SALDO NETO DISPONIBLE"],
        [f"S/. {tot_i:,.2f}", f"S/. {tot_e:,.2f}", f"S/. {saldo_n:,.2f}"]
    ], colWidths=[246, 246, 248])
    t_resumen.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,1), 11),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor("#166534")),
        ('TEXTCOLOR', (1,1), (1,1), colors.HexColor("#991B1B")),
        ('TEXTCOLOR', (2,1), (2,1), c_prim),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elem.extend([t_resumen, Spacer(1, 12)])

    filas = [["FECHA", "TIPO", "FONDO", "CATEGORÍA / RUBRO", "COMPROBANTE", "RESPONSABLE", "DETALLE", "MONTO"]]
    for _, r in df_reporte.iterrows():
        filas.append([
            str(r.get("fecha", ""))[:10],
            str(r.get("tipo", "")),
            str(r.get("fondo", ""))[:12],
            f"{r.get('categoria', '')} - {r.get('subcategoria', '')}"[:26],
            str(r.get("comprobante", ""))[:14],
            str(r.get("responsable", ""))[:15],
            str(r.get("detalle", ""))[:35],
            f"S/. {float(r.get('monto', 0)):,.2f}"
        ])

    filas.append(["", "", "", "", "", "", "SALDO NETO DEL PERIODO:", f"S/. {saldo_n:,.2f}"])

    t_tabla = Table(filas, colWidths=[60, 50, 65, 130, 75, 80, 200, 80])
    t_tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-2), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('ALIGN', (0,0), (2,-1), 'CENTER'),
        ('ALIGN', (4,0), (4,-1), 'CENTER'),
        ('ALIGN', (7,1), (7,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FEF08A")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,-1), (-1,-1), 1, colors.HexColor("#CA8A04")),
        ('PADDING', (0,0), (-1,-1), 3)
    ]))
    elem.extend([t_tabla, Spacer(1, 30)])

    t_firmas = Table([
        ["___________________________________", "___________________________________"],
        ["TESORERÍA GENERAL", "PASTORADO PRINCIPAL"],
        ["Iglesia Evangélica Nazareth", "Asambleas de Dios del Perú"]
    ], colWidths=[370, 370])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 2)
    ]))
    elem.append(t_firmas)

    doc.build(elem)
    return buf.getvalue()

def generar_pdf_analisis_financiero(mes_nombre, anio_val, ing_m, egr_m, sal_m, df_fondos_m, conclusiones_txt):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=32, bottomMargin=32)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    t_head = Table([[
        Paragraph(
            f"<b>IGLESIA EVANGÉLICA NAZARETH</b><br/>"
            f"<font size=9 color='#1E3A8A'>DICTAMEN Y ANÁLISIS FINANCIERO MENSUAL: {mes_nombre.upper()} {anio_val}</font>",
            ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10.5, textColor=c_prim)
        ),
        Paragraph(
            f"<b>Fecha:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
            f"<font size=8>Departamento de Tesorería</font>",
            ParagraphStyle('H2', fontName='Helvetica', fontSize=8, alignment=2)
        )
    ]], colWidths=[370, 170])
    t_head.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1D4ED8")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    elem.extend([t_head, Spacer(1, 12)])

    margen_ahorro = ((sal_m / ing_m) * 100) if ing_m > 0 else 0.0
    tasa_gasto = ((egr_m / ing_m) * 100) if ing_m > 0 else 0.0
    estado_mes = "SUPERÁVIT FINANCIERO" if sal_m >= 0 else "DÉFICIT EN EL PERIODO"

    t_resumen = Table([
        ["INDICADOR FINANCIERO", "MONTO / VALOR", "INTERPRETACIÓN CONTABLE"],
        ["Ingresos Totales del Mes", f"S/. {ing_m:,.2f}", "Recaudación neta consolidada"],
        ["Egresos y Gastos Operativos", f"S/. {egr_m:,.2f}", f"Representa el {tasa_gasto:.1f}% de los ingresos"],
        ["SALDO NETO (DIFERENCIA)", f"S/. {sal_m:,.2f}", estado_mes],
        ["Margen de Retención / Ahorro", f"{margen_ahorro:.1f}%", "Capacidad de reserva para proyectos"]
    ], colWidths=[200, 140, 200])
    t_resumen.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#FEF08A") if sal_m >= 0 else colors.HexColor("#FEE2E2")),
        ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (1,-1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 4.5)
    ]))
    elem.extend([t_resumen, Spacer(1, 14)])

    elem.append(Paragraph("<b>DISTRIBUCIÓN Y RENDIMIENTO POR FONDOS:</b>", ParagraphStyle('F', fontName='Helvetica-Bold', fontSize=9, textColor=c_prim)))
    elem.append(Spacer(1, 5))

    filas_fondos = [["FONDO", "INGRESOS", "EGRESOS", "SALDO NETO"]]
    for _, rf in df_fondos_m.iterrows():
        filas_fondos.append([
            str(rf["Fondo"]),
            f"S/. {rf['Ingreso']:,.2f}",
            f"S/. {rf['Egreso']:,.2f}",
            f"S/. {rf['Saldo']:,.2f}"
        ])
    t_fnd = Table(filas_fondos, colWidths=[180, 120, 120, 120])
    t_fnd.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F8FAFC")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('PADDING', (0,0), (-1,-1), 3.5)
    ]))
    elem.extend([t_fnd, Spacer(1, 14)])

    elem.append(Paragraph("<b>CONCLUSIONES Y RECOMENDACIONES TÉCNICAS:</b>", ParagraphStyle('C', fontName='Helvetica-Bold', fontSize=9, textColor=c_prim)))
    elem.append(Spacer(1, 4))
    p_concl = Paragraph(conclusiones_txt.replace("\n", "<br/>"), ParagraphStyle('CTxt', fontName='Helvetica', fontSize=8, leading=11, alignment=4))
    t_box_concl = Table([[p_concl]], colWidths=[540])
    t_box_concl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 8)
    ]))
    elem.extend([t_box_concl, Spacer(1, 35)])

    t_firmas = Table([
        ["___________________________________", "___________________________________"],
        ["TESORERÍA GENERAL", "PASTORADO PRINCIPAL"],
        ["Iglesia Evangélica Nazareth", "Asambleas de Dios del Perú"]
    ], colWidths=[270, 270])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 2)
    ]))
    elem.append(t_firmas)

    doc.build(elem)
    return buf.getvalue()

def generar_excel_tesoreria(df_exp):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Libro_Caja")
    return output.getvalue()

# ==============================================================================
# CABECERA Y MENÚ DE ACCIONES UNIVERSAL (PC Y CELULAR)
# ==============================================================================
core.banner_modulo("🏛️", "Libro de Tesorería y Movimientos", "Control de ingresos, egresos, saldos por fondo y estados financieros")

LISTA_SECCIONES = [
    "📖 Libro Detallado", 
    "📈 Evolución y Gráficos", 
    "➕ Registrar Movimiento", 
    "⚙️ Modificar o Eliminar"
]

if "opcion_tesoreria" not in st.session_state:
    st.session_state["opcion_tesoreria"] = LISTA_SECCIONES[0]

if "mostrar_menu_tesoreria" not in st.session_state:
    st.session_state["mostrar_menu_tesoreria"] = True

col_btn_m, col_info_m = st.columns([1.6, 6])
with col_btn_m:
    label_btn = "🔼 Ocultar Menú" if st.session_state["mostrar_menu_tesoreria"] else "☰ Menú de Opciones"
    if st.button(label_btn, use_container_width=True, type="primary" if not st.session_state["mostrar_menu_tesoreria"] else "secondary"):
        st.session_state["mostrar_menu_tesoreria"] = not st.session_state["mostrar_menu_tesoreria"]
        st.rerun()

with col_info_m:
    if not st.session_state["mostrar_menu_tesoreria"]:
        st.caption(f"Sección activa: **{st.session_state['opcion_tesoreria']}** (Pulsa '☰ Menú de Opciones' para cambiar)")

if st.session_state["mostrar_menu_tesoreria"]:
    idx_def = LISTA_SECCIONES.index(st.session_state["opcion_tesoreria"]) if st.session_state["opcion_tesoreria"] in LISTA_SECCIONES else 0
    sel_sec = st.selectbox(
        "Seleccione la sección de Tesorería:",
        LISTA_SECCIONES,
        index=idx_def
    )
    st.session_state["opcion_tesoreria"] = sel_sec

opcion = st.session_state["opcion_tesoreria"]
st.markdown("---")

# ==============================================================================
# 1. LIBRO DETALLADO
# ==============================================================================
if opcion == "📖 Libro Detallado":
    df_mov = core.read_db("SELECT * FROM public.movimientos ORDER BY date(fecha) DESC, id DESC")
    if df_mov.empty:
        st.info("No hay movimientos registrados en el libro de Tesorería.")
    else:
        with st.expander("🔎 Filtros de Visualización del Libro de Caja", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: f_tipo = st.selectbox("Filtrar por Tipo:", ["Todos", "Ingreso", "Egreso"])
            with c2: f_fondo = st.selectbox("Filtrar por Fondo:", ["Todos"] + fondos)
            with c3: f_txt = st.text_input("Buscar por Detalle, Comprobante o Responsable:")

        df_fil = df_mov.copy()
        if f_tipo != "Todos": 
            df_fil = df_fil[df_fil["tipo"] == f_tipo]
        if f_fondo != "Todos": 
            df_fil = df_fil[df_fil["fondo"] == f_fondo]
        if f_txt.strip():
            txt_l = f_txt.strip().lower()
            df_fil = df_fil[
                df_fil["detalle"].astype(str).str.lower().str.contains(txt_l) |
                df_fil["responsable"].astype(str).str.lower().str.contains(txt_l) |
                df_fil["comprobante"].astype(str).str.lower().str.contains(txt_l)
            ]

        tot_ing = float(df_fil[df_fil["tipo"] == "Ingreso"]["monto"].sum())
        tot_egr = float(df_fil[df_fil["tipo"] == "Egreso"]["monto"].sum())
        saldo_neto = tot_ing - tot_egr

        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos Totales", f"S/. {tot_ing:,.2f}")
        m2.metric("Egresos Totales", f"S/. {tot_egr:,.2f}", delta=f"-S/. {tot_egr:,.2f}", delta_color="inverse")
        m3.metric("Saldo Neto", f"S/. {saldo_neto:,.2f}")

        st.markdown("##### 💼 Distribución por Fondos:")
        cols_fondos = st.columns(min(len(fondos), 5))
        for i, f_nom in enumerate(fondos[:5]):
            ing_f = float(df_mov[(df_mov["fondo"] == f_nom) & (df_mov["tipo"] == "Ingreso")]["monto"].sum())
            egr_f = float(df_mov[(df_mov["fondo"] == f_nom) & (df_mov["tipo"] == "Egreso")]["monto"].sum())
            cols_fondos[i].metric(f_nom, f"S/. {ing_f - egr_f:,.2f}")

        st.markdown("---")
        col_pdf, col_xls, _ = st.columns([3, 3, 4])
        with col_pdf:
            if not df_fil.empty:
                pdf_caja_bytes = generar_pdf_libro_caja(df_fil, tot_ing, tot_egr, saldo_neto)
                st.download_button(
                    label="📄 Descargar Libro de Caja en PDF",
                    data=pdf_caja_bytes,
                    file_name=f"Libro_Caja_Nazareth_{date.today()}.pdf",
                    mime="application/pdf"
                )
        with col_xls:
            if not df_fil.empty:
                excel_caja_bytes = generar_excel_tesoreria(df_fil[["fecha", "tipo", "categoria", "subcategoria", "fondo", "monto", "medio", "comprobante", "responsable", "detalle"]])
                st.download_button(
                    label="📊 Descargar Libro de Caja en Excel (.xlsx)",
                    data=excel_caja_bytes,
                    file_name=f"Libro_Caja_Nazareth_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

        map_cols_ver = {
            "fecha": "Fecha", "tipo": "Tipo", "categoria": "Categoría", "subcategoria": "Rubro",
            "fondo": "Fondo", "monto": "Monto (S/.)", "medio": "Medio",
            "comprobante": "Comprobante / Folio", "responsable": "Responsable", "detalle": "Detalle"
        }
        cols_existentes = [c for c in map_cols_ver.keys() if c in df_fil.columns]
        df_mostrar = df_fil[cols_existentes].rename(columns=map_cols_ver)
        st.dataframe(df_mostrar.style.format({"Monto (S/.)": "S/. {:,.2f}"}), use_container_width=True, hide_index=True)

# ==============================================================================
# 2. EVOLUCIÓN Y GRÁFICOS
# ==============================================================================
elif opcion == "📈 Evolución y Gráficos":
    df_mov = core.read_db("SELECT fecha, tipo, monto, fondo FROM public.movimientos WHERE comprobante NOT IN ('ASIENTO-APERTURA') AND estado_credito != 'A Credito' AND fecha IS NOT NULL")
    
    if df_mov.empty:
        st.info("No hay suficientes datos registrados para generar gráficas.")
    else:
        df_mov["fecha_dt"] = pd.to_datetime(df_mov["fecha"], errors="coerce")
        df_mov = df_mov.dropna(subset=["fecha_dt"])
        df_mov["Anio"] = df_mov["fecha_dt"].dt.year
        df_mov["MesNum"] = df_mov["fecha_dt"].dt.month
        df_mov["Mes"] = df_mov["MesNum"].map(core.MESES_NOMBRES)

        anios_graf = sorted(list(df_mov["Anio"].unique()), reverse=True)
        col_g1, col_g2 = st.columns([2, 2])
        with col_g1:
            anio_graf = st.selectbox("Año de Análisis:", anios_graf, index=0)
        with col_g2:
            mes_analisis = st.selectbox("Mes para Informe y Dictamen PDF:", core.MESES, index=date.today().month - 1)

        df_anio = df_mov[df_mov["Anio"] == anio_graf].copy()

        pivot = df_anio.pivot_table(index="Mes", columns="tipo", values="monto", aggfunc="sum", fill_value=0.0).reindex(core.MESES).fillna(0.0)
        if "Ingreso" not in pivot.columns: pivot["Ingreso"] = 0.0
        if "Egreso" not in pivot.columns: pivot["Egreso"] = 0.0

        pivot["Saldo"] = pivot["Ingreso"] - pivot["Egreso"]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="1. Ingresos", x=core.MESES, y=pivot["Ingreso"],
            marker_color="#10B981", text=pivot["Ingreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        fig.add_trace(go.Bar(
            name="2. Egresos", x=core.MESES, y=pivot["Egreso"],
            marker_color="#EF4444", text=pivot["Egreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        fig.add_trace(go.Bar(
            name="3. Saldo (Diferencia)", x=core.MESES, y=pivot["Saldo"],
            marker_color="#1E3A8A", text=pivot["Saldo"].apply(lambda v: f"S/. {v:,.0f}" if v != 0 else ""),
            textposition="auto"
        ))
        fig.add_trace(go.Scatter(
            name="Tendencia de Saldo", x=core.MESES, y=pivot["Saldo"],
            mode="lines+markers", line=dict(color="#F59E0B", width=3),
            marker=dict(size=7)
        ))

        fig.update_layout(
            barmode="group",
            title=f"Comparativa Mensual de Tesorería ({anio_graf}): Ingresos vs. Egresos vs. Saldo Neto",
            xaxis_title="Mes",
            yaxis_title="Monto (S/.)",
            height=480,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown(f"#### 📊 Diagnóstico y Estadísticas de: **{mes_analisis} {anio_graf}**")
        
        mes_num_sel = core.MESES.index(mes_analisis) + 1
        df_mes_sel = df_anio[df_anio["MesNum"] == mes_num_sel]

        ing_mes = float(df_mes_sel[df_mes_sel["tipo"] == "Ingreso"]["monto"].sum())
        egr_mes = float(df_mes_sel[df_mes_sel["tipo"] == "Egreso"]["monto"].sum())
        sal_mes = ing_mes - egr_mes
        tasa_ahorro = ((sal_mes / ing_mes) * 100) if ing_mes > 0 else 0.0
        relacion_gasto = ((egr_mes / ing_mes) * 100) if ing_mes > 0 else 0.0

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("Ingresos del Mes", f"S/. {ing_mes:,.2f}")
        c_m2.metric("Egresos del Mes", f"S/. {egr_mes:,.2f}")
        c_m3.metric("Saldo Neto (Diferencia)", f"S/. {sal_mes:,.2f}", delta="Superávit" if sal_mes >= 0 else "Déficit")
        c_m4.metric("Margen de Retención / Ahorro", f"{tasa_ahorro:.1f}%")

        df_fondos_res = []
        for fn in fondos:
            i_f = float(df_mes_sel[(df_mes_sel["fondo"] == fn) & (df_mes_sel["tipo"] == "Ingreso")]["monto"].sum())
            e_f = float(df_mes_sel[(df_mes_sel["fondo"] == fn) & (df_mes_sel["tipo"] == "Egreso")]["monto"].sum())
            df_fondos_res.append({"Fondo": fn, "Ingreso": i_f, "Egreso": e_f, "Saldo": i_f - e_f})
        df_fondos_m = pd.DataFrame(df_fondos_res)

        if sal_mes > 0:
            conclusion_auto = (
                f"1. El mes de {mes_analisis} {anio_graf} cerró con un superávit neto de S/. {sal_mes:,.2f}, registrando una tasa de retención del {tasa_ahorro:.1f}% sobre los ingresos.\n"
                f"2. El gasto operativo representó el {relacion_gasto:.1f}% de la recaudación total, manteniéndose dentro de márgenes saludables de sostenibilidad.\n"
                f"3. Se recomienda destinar el remanente disponible al fondo Pro-Templo o a provisiones para compromisos fijos del siguiente periodo."
            )
        elif sal_mes < 0:
            conclusion_auto = (
                f"1. El mes de {mes_analisis} {anio_graf} registró un déficit operativo de S/. {abs(sal_mes):,.2f}, superando los gastos a los ingresos en un {relacion_gasto:.1f}%.\n"
                f"2. Esta variación negativa requiere amortización con los fondos de reserva acumulados de periodos anteriores.\n"
                f"3. Se aconseja priorizar los pagos indispensables y evaluar campañas extraordinarias pro-fondos para restituir el saldo de caja."
            )
        else:
            conclusion_auto = (
                f"1. El mes de {mes_analisis} {anio_graf} finalizó en equilibrio financiero exacto (S/. 0.00 de diferencia neta).\n"
                f"2. Los ingresos recaudados financiaron en su totalidad los gastos ejecutados en el periodo.\n"
                f"3. Se recomienda incrementar la captación de aportes para generar reservas ante contingencias futuras."
            )

        with st.expander("📝 Conclusiones y Diagnóstico Financiero (Editable para el Informe):", expanded=True):
            conclusiones_edit = st.text_area("Dictamen de Tesorería:", value=conclusion_auto, height=110)

        pdf_analisis_bytes = generar_pdf_analisis_financiero(
            mes_analisis, anio_graf, ing_mes, egr_mes, sal_mes, df_fondos_m, conclusiones_edit
        )
        col_desc, _ = st.columns([3, 4])
        with col_desc:
            st.download_button(
                label=f"📄 Descargar Análisis Financiero en PDF ({mes_analisis} {anio_graf})",
                data=pdf_analisis_bytes,
                file_name=f"Analisis_Financiero_{mes_analisis}_{anio_graf}.pdf",
                mime="application/pdf",
                type="primary"
            )

# ==============================================================================
# 3. REGISTRAR MOVIMIENTO MANUAL
# ==============================================================================
elif opcion == "➕ Registrar Movimiento":
    t_mov = st.radio("Tipo:", ["Egreso (Gasto)", "Ingreso"], horizontal=True)
    tipo_cl = "Egreso" if "Egreso" in t_mov else "Ingreso"

    cats = core.read_db("SELECT categoria, subcategoria FROM public.rubros_catalogo WHERE tipo=?", (tipo_cl,))
    dict_c = {}
    if not cats.empty:
        for c, g in cats.groupby("categoria"): 
            dict_c[c] = g["subcategoria"].tolist()
    else:
        dict_c = {"General": ["General"]}

    df_r = core.read_db("SELECT nombre FROM public.responsables_catalogo")
    resps = df_r["nombre"].tolist() if not df_r.empty else ["Tesorero"]

    anio, mes, num_m, f_sug = core.selector_periodo("mov_reg")

    with st.form("form_reg_mov", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha:", value=f_sug)
            cat = st.selectbox("Categoría:", list(dict_c.keys()))
            subcat = st.selectbox("Rubro / Subcategoría:", dict_c.get(cat, ["General"]))
            fondo = st.selectbox("Fondo:", fondos)
            monto = st.number_input("Monto (S/.):", min_value=0.01, step=10.0, format="%.2f")
        with c2:
            medio = st.selectbox("Medio de Pago / Entrega:", core.MEDIOS)
            comp = st.text_input("Comprobante / N° Recibo / Voucher:", placeholder="Ej. B001-00124 o OP-49210")
            resp = st.selectbox("Responsable:", resps)
            det = st.text_area("Detalle / Concepto:")

        if st.form_submit_button("💾 Guardar Transacción", type="primary"):
            core.query_db("""
                INSERT INTO public.movimientos (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'Cobrado')
            """, (str(fecha), tipo_cl, cat, subcat, fondo, round(float(monto), 2), medio, comp.strip(), det.strip(), resp))
            core.registrar_log("Tesorería", "Registro", f"{tipo_cl} S/. {monto:,.2f} - {det.strip()} ({comp.strip()})")
            st.toast("✅ Movimiento guardado en Tesorería.")
            st.rerun()

# ==============================================================================
# 4. MODIFICAR O ELIMINAR (UNIFICADO CON FILTROS INTELIGENTES)
# ==============================================================================
elif opcion == "⚙️ Modificar o Eliminar":
    st.markdown("#### ⚙️ Gestión de Asientos de Tesorería (Modificar o Eliminar)")
    df_todos_mov = core.read_db("SELECT * FROM public.movimientos ORDER BY date(fecha) DESC, id DESC")

    if df_todos_mov.empty:
        st.info("No hay transacciones registradas en Tesorería.")
    else:
        df_todos_mov["dt"] = pd.to_datetime(df_todos_mov["fecha"], errors="coerce")
        df_todos_mov["anio"] = df_todos_mov["dt"].dt.year
        df_todos_mov["mes"] = df_todos_mov["dt"].dt.month

        with st.expander("🔎 Filtros para Localizar Asiento Contable", expanded=True):
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                b_txt = st.text_input("Buscar por Detalle / Comprobante / Responsable:", placeholder="Ej. Luz, CORTE-1, Enel...")
            with col_f2:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_todos_mov["anio"].dropna().unique()], reverse=True)
                b_anio = st.selectbox("Año:", anios_disp, index=0)
            with col_f3:
                b_mes = st.selectbox("Mes:", ["Todos"] + core.MESES, index=0)
            with col_f4:
                b_tipo = st.selectbox("Tipo:", ["Todos", "Ingreso", "Egreso"], index=0)

        df_filtrado_mov = df_todos_mov.copy()
        if b_txt.strip():
            t_l = b_txt.strip().lower()
            df_filtrado_mov = df_filtrado_mov[
                df_filtrado_mov["detalle"].astype(str).str.lower().str.contains(t_l) |
                df_filtrado_mov["comprobante"].astype(str).str.lower().str.contains(t_l) |
                df_filtrado_mov["responsable"].astype(str).str.lower().str.contains(t_l)
            ]
        if b_anio != "Todos":
            df_filtrado_mov = df_filtrado_mov[df_filtrado_mov["anio"] == b_anio]
        if b_mes != "Todos":
            mes_num_f = core.MESES.index(b_mes) + 1
            df_filtrado_mov = df_filtrado_mov[df_filtrado_mov["mes"] == mes_num_f]
        if b_tipo != "Todos":
            df_filtrado_mov = df_filtrado_mov[df_filtrado_mov["tipo"] == b_tipo]

        st.caption(f"Coincidencias encontradas: **{len(df_filtrado_mov)}** de {len(df_todos_mov)} transacciones.")

        if df_filtrado_mov.empty:
            st.warning("⚠️ No se encontraron movimientos con los filtros especificados.")
        else:
            def label_mov(r):
                c_str = f" | Comp: {r['comprobante']}" if r.get('comprobante') else ""
                return f"ID #{r['id']} [{r['fecha']}] {r['tipo']} — S/. {r['monto']:,.2f} ({r['detalle'][:30]}){c_str}"

            opciones_mov_dict = {label_mov(r): r["id"] for _, r in df_filtrado_mov.iterrows()}
            st.markdown("---")
            sel_asiento = st.selectbox("📌 Selecciona la transacción que deseas gestionar:", list(opciones_mov_dict.keys()))
            id_mov_sel = opciones_mov_dict[sel_asiento]
            reg_mov = df_filtrado_mov[df_filtrado_mov["id"] == id_mov_sel].iloc[0]

            accion_m = st.radio("Acción a realizar:", ["✏️ Editar Asiento", "🗑️ Eliminar Transacción"], horizontal=True)

            if accion_m == "✏️ Editar Asiento":
                try: 
                    f_val_m = datetime.strptime(str(reg_mov["fecha"]), "%Y-%m-%d").date()
                except Exception: 
                    f_val_m = date.today()

                idx_fnd = fondos.index(reg_mov["fondo"]) if reg_mov["fondo"] in fondos else 0
                idx_med = core.MEDIOS.index(reg_mov["medio"]) if reg_mov["medio"] in core.MEDIOS else 0

                df_r_act = core.read_db("SELECT nombre FROM public.responsables_catalogo")
                resps_act = df_r_act["nombre"].tolist() if not df_r_act.empty else ["Tesorero"]
                idx_resp = resps_act.index(reg_mov["responsable"]) if reg_mov["responsable"] in resps_act else 0

                with st.form("form_editar_mov"):
                    st.info(f"Modificando Asiento ID #{reg_mov['id']} — Tipo actual: **{reg_mov['tipo']}**")
                    c1, c2 = st.columns(2)
                    with c1:
                        e_fecha = st.date_input("Fecha:", value=f_val_m)
                        e_tipo = st.selectbox("Tipo de Movimiento:", ["Ingreso", "Egreso"], index=0 if reg_mov["tipo"] == "Ingreso" else 1)
                        e_cat = st.text_input("Categoría:", value=str(reg_mov["categoria"]))
                        e_subcat = st.text_input("Subcategoría / Rubro:", value=str(reg_mov["subcategoria"]))
                        e_monto = st.number_input("Monto (S/.):", min_value=0.01, value=float(reg_mov["monto"]), step=10.0, format="%.2f")
                    with c2:
                        e_fondo = st.selectbox("Fondo:", fondos, index=idx_fnd)
                        e_medio = st.selectbox("Medio de Pago:", core.MEDIOS, index=idx_med)
                        e_comp = st.text_input("Comprobante / N° Recibo / Voucher:", value=str(reg_mov.get("comprobante", "") or ""))
                        e_resp = st.selectbox("Responsable:", resps_act, index=idx_resp)
                        e_det = st.text_area("Detalle / Observación:", value=str(reg_mov.get("detalle", "") or ""))

                    btn_guardar_mov = st.form_submit_button("💾 Guardar Cambios en Tesorería", type="primary")

                if btn_guardar_mov:
                    core.query_db("""
                        UPDATE public.movimientos SET
                            fecha = ?, tipo = ?, categoria = ?, subcategoria = ?,
                            fondo = ?, monto = ?, medio = ?, comprobante = ?,
                            responsable = ?, detalle = ?
                        WHERE id = ?
                    """, (str(e_fecha), e_tipo, e_cat.strip(), e_subcat.strip(), e_fondo, round(float(e_monto), 2), e_medio, e_comp.strip(), e_resp, e_det.strip(), id_mov_sel))

                    core.registrar_log("Tesorería", "Edición", f"Actualizado asiento ID #{id_mov_sel} por S/. {e_monto:,.2f}")
                    st.toast("✅ Asiento contable actualizado correctamente.")
                    st.rerun()

            elif accion_m == "🗑️ Eliminar Transacción":
                st.warning(f"⚠️ ¿Confirma eliminar definitivamente la transacción **ID #{reg_mov['id']}** por **S/. {reg_mov['monto']:,.2f}** ({reg_mov['detalle']})?")
                if st.button("Eliminar Definitivamente", type="primary"):
                    core.query_db("DELETE FROM public.movimientos WHERE id=?", (id_mov_sel,))
                    core.registrar_log("Tesorería", "Eliminación", f"Eliminado asiento ID #{id_mov_sel} de S/. {reg_mov['monto']:,.2f}")
                    st.toast("🗑️ Transacción eliminada de Tesorería.")
                    st.rerun()
