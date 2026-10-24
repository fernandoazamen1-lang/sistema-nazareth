import streamlit as st
import core
import io
import pandas as pd
import numpy as np
from datetime import date, datetime
import plotly.graph_objects as go

# 1. Configuración de página
st.set_page_config(
    page_title="Tesorería y Movimientos", 
    page_icon="🏛️", 
    layout="wide"
)

# 2. Seguridad y validación de permisos
core.requerir_login()
core.verificar_acceso_pagina("Tesorería")
core.aplicar_estilos_base()

st.subheader("🏛️ Libro de Tesorería y Movimientos")

# Navegación limpia
opcion = st.radio(
    "Sección:", 
    ["Libro Detallado", "Evolución y Gráficos", "Registrar Movimiento", "⚙️ Modificar o Eliminar"], 
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# CARGA CENTRALIZADA Y OPTIMIZADA CON CACHÉ (MÁXIMO RENDIMIENTO)
# ==============================================================================
@st.cache_data(ttl=86400, show_spinner=False)
def cargar_catalogos_tesoreria():
    df_f = core.read_db("SELECT nombre FROM public.fondos_catalogo ORDER BY id ASC")
    f_list = df_f["nombre"].tolist() if not df_f.empty else ["General"]
    
    df_r = core.read_db("SELECT nombre FROM public.responsables_catalogo ORDER BY nombre ASC")
    r_list = df_r["nombre"].tolist() if not df_r.empty else ["Tesorero"]
    
    df_rub = core.read_db("SELECT tipo, categoria, subcategoria FROM public.rubros_catalogo")
    return f_list, r_list, df_rub

fondos, resps, df_rubros_cat = cargar_catalogos_tesoreria()

@st.cache_data(ttl=300, show_spinner=False)
def cargar_movimientos_tesoreria():
    """Descarga todo el libro mayor una vez, calculando Año y Mes desde Postgres"""
    return core.read_db("""
        SELECT id, fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable,
               EXTRACT(YEAR FROM CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE)) AS anio,
               EXTRACT(MONTH FROM CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE)) AS mes_num
        FROM public.movimientos 
        ORDER BY CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE) DESC, id DESC
    """)

@st.cache_data(ttl=300, show_spinner=False)
def cargar_diezmos_graficos():
    """Extrae montos y fechas de diezmos sin saturar memoria para el Cuadro 3"""
    return core.read_db("""
        SELECT monto, 
               EXTRACT(YEAR FROM CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE)) AS anio,
               EXTRACT(MONTH FROM CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE)) AS mes_num
        FROM public.diezmos 
        WHERE fecha IS NOT NULL AND fecha != ''
    """)

def limpiar_caches_tesoreria():
    cargar_movimientos_tesoreria.clear()
    st.cache_data.clear() # Limpia también core.read_db genérico

# Alimentamos la memoria principal
df_mov_global = cargar_movimientos_tesoreria()

# ==============================================================================
# MOTOR DE REPORTES PDF Y EXCEL (BAJO DEMANDA)
# ==============================================================================
MAP_COLUMNAS_INFO = {
    "Fecha": ("fecha", 60, 'CENTER'),
    "Tipo": ("tipo", 45, 'CENTER'),
    "Medio": ("medio", 75, 'CENTER'),
    "Fondo": ("fondo", 55, 'CENTER'),
    "Categoría": ("categoria", 85, 'LEFT'),
    "Rubro": ("subcategoria", 85, 'LEFT'),
    "Comprobante": ("comprobante", 75, 'CENTER'),
    "Responsable": ("responsable", 80, 'LEFT'),
    "Detalle": ("detalle", 140, 'LEFT'),
    "Monto (S/.)": ("monto", 75, 'RIGHT'),
}

def generar_pdf_libro_caja_dinamico(df_reporte, cols_visibles, tot_i, tot_e, saldo_n, filtros_txt=""):
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    subt_filtro = f"<font size=8 color='#475569'>Filtros aplicados: {filtros_txt}</font>" if filtros_txt else ""

    t_head = Table([[
        Paragraph(
            "<b>IGLESIA EVANGÉLICA \"NAZARETH\" — ASAMBLEAS DE DIOS DEL PERÚ</b><br/>"
            f"<font size=9 color='#1E3A8A'>LIBRO OFICIAL DE CAJA Y MOVIMIENTOS DE TESORERÍA</font><br/>{subt_filtro}",
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

    pesos_cols = [MAP_COLUMNAS_INFO[c][1] for c in cols_visibles]
    suma_pesos = sum(pesos_cols) if pesos_cols else 1
    col_widths = [int((p / suma_pesos) * 742) for p in pesos_cols]

    filas = [cols_visibles]
    for _, r in df_reporte.iterrows():
        fila_item = []
        for c in cols_visibles:
            col_key = MAP_COLUMNAS_INFO[c][0]
            val = r.get(col_key, "")
            if col_key == "monto":
                fila_item.append(f"S/. {float(val):,.2f}")
            elif col_key == "fecha":
                fila_item.append(str(val)[:10])
            else:
                fila_item.append(str(val)[:30])
        filas.append(fila_item)

    if "Monto (S/.)" in cols_visibles:
        idx_monto = cols_visibles.index("Monto (S/.)")
        fila_total = ["" for _ in cols_visibles]
        if idx_monto > 0:
            fila_total[idx_monto - 1] = "SALDO NETO:"
        else:
            fila_total[0] = "TOTAL:"
        fila_total[idx_monto] = f"S/. {saldo_n:,.2f}"
        filas.append(fila_total)

    t_tabla = Table(filas, colWidths=col_widths)
    t_style = [
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.2),
        ('PADDING', (0,0), (-1,-1), 3),
    ]

    for i, c in enumerate(cols_visibles):
        t_style.append(('ALIGN', (i, 1), (i, -1), MAP_COLUMNAS_INFO[c][2]))

    if "Monto (S/.)" in cols_visibles:
        t_style.extend([
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FEF08A")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,-1), (-1,-1), 1, colors.HexColor("#CA8A04")),
        ])

    t_tabla.setStyle(TableStyle(t_style))
    elem.extend([t_tabla, Spacer(1, 26)])

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

def generar_excel_dinamico(df_exp, cols_visibles):
    output = io.BytesIO()
    cols_map_db = {MAP_COLUMNAS_INFO[c][0]: c for c in cols_visibles}
    cols_df = [c for c in cols_map_db.keys() if c in df_exp.columns]
    df_descarga = df_exp[cols_df].rename(columns=cols_map_db)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_descarga.to_excel(writer, index=False, sheet_name="Libro_Caja")
    return output.getvalue()

# ==============================================================================
# MOTOR DE GRÁFICOS Y EXPORTACIÓN A PDF
# ==============================================================================
def calcular_tendencia_lineal(y_vals):
    y_arr = np.array(y_vals, dtype=float)
    x_idx = np.arange(len(y_vals))
    if np.any(y_arr != 0):
        try:
            coefs = np.polyfit(x_idx, y_arr, 1)
            return np.polyval(coefs, x_idx)
        except Exception:
            pass
    return y_arr

def agregar_tendencia_plotly(fig, x_labels, y_vals, nombre="Tendencia / Proyección"):
    y_trend = calcular_tendencia_lineal(y_vals)
    fig.add_trace(go.Scatter(
        x=x_labels, 
        y=y_trend,
        mode="lines",
        name=nombre,
        line=dict(color="#F59E0B", width=2.5, dash="dash")
    ))

def dibujar_grafico_vectorial_pdf(titulo, x_labels, y_vals, color_hex, y_tendencia=None):
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.lib import colors

    d = Drawing(740, 185)
    d.add(Rect(0, 0, 740, 185, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1"), strokeWidth=1, rx=6, ry=6))
    d.add(String(20, 165, titulo, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#0F172A")))

    vals_abs = [abs(v) for v in y_vals]
    max_val = max(vals_abs) if vals_abs and max(vals_abs) > 0 else 1.0

    base_y = 38
    chart_h = 100
    bar_w = 30
    spacing = 58
    start_x = 42

    d.add(Line(25, base_y, 715, base_y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=1))

    pts_tendencia = []
    for i, (mes, val) in enumerate(zip(x_labels, y_vals)):
        bx = start_x + (i * spacing)
        bh = (abs(val) / max_val) * chart_h
        by = base_y if val >= 0 else base_y - bh
        c_fill = colors.HexColor(color_hex) if val >= 0 else colors.HexColor("#DC2626")

        d.add(Rect(bx, by, bar_w, max(bh, 1), fillColor=c_fill, strokeColor=None))

        if abs(val) > 0:
            d.add(String(bx - 3, by + bh + 3 if val >= 0 else by - 10, f"S/.{val:,.0f}", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor("#334155")))
        d.add(String(bx + 4, base_y - 12, mes[:3], fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#64748B")))

        if y_tendencia is not None and len(y_tendencia) > i:
            ty = base_y + ((y_tendencia[i] / max_val) * chart_h)
            pts_tendencia.append((bx + bar_w / 2, ty))

    for i in range(len(pts_tendencia) - 1):
        d.add(Line(pts_tendencia[i][0], pts_tendencia[i][1], pts_tendencia[i+1][0], pts_tendencia[i+1][1], strokeColor=colors.HexColor("#F59E0B"), strokeWidth=2))

    return d

def render_chart_para_pdf(fig, titulo, x_labels, y_vals, color_hex, y_tendencia):
    try:
        img_bytes = fig.to_image(format="png", width=950, height=320, scale=2)
        from reportlab.platypus import Image as RLImage
        return RLImage(io.BytesIO(img_bytes), width=740, height=200)
    except Exception:
        return dibujar_grafico_vectorial_pdf(titulo, x_labels, y_vals, color_hex, y_tendencia)

def generar_pdf_cuadros_graficos(anio_sel, medio_sel, fig1, fig2, fig3, fig4, y1, y2, y3, y4, tot_i, tot_e, tot_dz, sal_acum):
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")

    t_head = Table([[
        Paragraph(
            "<b>IGLESIA EVANGÉLICA \"NAZARETH\" — ASAMBLEAS DE DIOS DEL PERÚ</b><br/>"
            f"<font size=9 color='#1E3A8A'>INFORME ANUAL DE EVOLUCIÓN FINANCIERA Y PROYECCIONES: {anio_sel}</font><br/>"
            f"<font size=8 color='#475569'>Filtro de Medio: {medio_sel}</font>",
            ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10.5, textColor=c_prim)
        ),
        Paragraph(
            f"<b>Emisión:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
            f"<font size=8>Departamento de Tesorería</font>",
            ParagraphStyle('H2', fontName='Helvetica', fontSize=8, alignment=2)
        )
    ]], colWidths=[540, 200])
    t_head.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1D4ED8")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    elem.extend([t_head, Spacer(1, 8)])

    t_kpis = Table([
        ["TOTAL INGRESOS", "TOTAL EGRESOS", "TOTAL DIEZMOS", "SALDO REMANENTE ACUMULADO"],
        [f"S/. {tot_i:,.2f}", f"S/. {tot_e:,.2f}", f"S/. {tot_dz:,.2f}", f"S/. {sal_acum:,.2f}"]
    ], colWidths=[185, 185, 185, 187])
    t_kpis.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('FONTSIZE', (0,1), (-1,1), 10.5),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor("#166534")),
        ('TEXTCOLOR', (1,1), (1,1), colors.HexColor("#991B1B")),
        ('TEXTCOLOR', (2,1), (2,1), colors.HexColor("#4338CA")),
        ('TEXTCOLOR', (3,1), (3,1), c_prim),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elem.extend([t_kpis, Spacer(1, 10)])

    g1_item = render_chart_para_pdf(fig1, f"1. EVOLUCIÓN MENSUAL DE INGRESOS ({anio_sel})", core.MESES, y1, "#10B981", calcular_tendencia_lineal(y1))
    g2_item = render_chart_para_pdf(fig2, f"2. EVOLUCIÓN MENSUAL DE EGRESOS Y GASTOS ({anio_sel})", core.MESES, y2, "#EF4444", calcular_tendencia_lineal(y2))
    elem.extend([g1_item, Spacer(1, 8), g2_item, PageBreak()])

    g3_item = render_chart_para_pdf(fig3, f"3. EVOLUCIÓN HISTÓRICA DE DIEZMOS ({anio_sel})", core.MESES, y3, "#6366F1", calcular_tendencia_lineal(y3))
    g4_item = render_chart_para_pdf(fig4, f"4. SALDOS NETOS REMANENTES POR MES ({anio_sel})", core.MESES, y4, "#1E3A8A", calcular_tendencia_lineal(y4))
    
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
    elem.extend([g3_item, Spacer(1, 8), g4_item, Spacer(1, 14), t_firmas])

    doc.build(elem)
    return buf.getvalue()

# ==============================================================================
# 1. LIBRO DETALLADO CON FILTROS Y SELECTOR DE COLUMNAS
# ==============================================================================
if opcion == "Libro Detallado":
    if df_mov_global.empty:
        st.info("No hay movimientos registrados en el libro de Tesorería.")
    else:
        with st.expander("🔎 Opciones de Filtrado de Movimientos (Filas)", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_mov_global["anio"].dropna().unique()], reverse=True)
                filtro_anio = st.selectbox("Año:", anios_disp, index=0)
            with f2:
                filtro_mes = st.selectbox("Mes:", ["Todos"] + core.MESES, index=0)
            with f3:
                filtro_tipo = st.selectbox("Tipo:", ["Todos", "Ingreso", "Egreso"])
            with f4:
                filtro_medio = st.selectbox("Medio de Entrega:", ["Ambos (Todos)", "Efectivo", "Depósito / Transferencia (Bancos)"])

            f5, f6, f7 = st.columns([1.5, 1.5, 3])
            with f5:
                filtro_fondo = st.selectbox("Fondo:", ["Todos"] + fondos)
            with f6:
                cats_existentes = ["Todas"] + sorted([str(c) for c in df_mov_global["categoria"].dropna().unique() if str(c).strip()])
                filtro_cat = st.selectbox("Categoría:", cats_existentes)
            with f7:
                filtro_txt = st.text_input("Búsqueda Rápida:", placeholder="Buscar por detalle, comprobante o responsable...")

        with st.expander("👁️ Selector Flotante de Columnas Visibles", expanded=True):
            todas_las_columnas = list(MAP_COLUMNAS_INFO.keys())
            cols_seleccionadas = st.multiselect(
                "Marca o desmarca las columnas que deseas visualizar y exportar:",
                options=todas_las_columnas,
                default=["Fecha", "Tipo", "Medio", "Fondo", "Categoría", "Rubro", "Comprobante", "Monto (S/.)"]
            )

        if not cols_seleccionadas:
            st.warning("⚠️ Debes seleccionar al menos una columna para mostrar la tabla.")
            cols_seleccionadas = ["Fecha", "Tipo", "Monto (S/.)"]

        df_fil = df_mov_global
        filtros_activos = []

        if filtro_anio != "Todos":
            df_fil = df_fil[df_fil["anio"] == filtro_anio]
            filtros_activos.append(f"Año {filtro_anio}")
        if filtro_mes != "Todos":
            m_num = core.MESES.index(filtro_mes) + 1
            df_fil = df_fil[df_fil["mes_num"] == m_num]
            filtros_activos.append(f"Mes {filtro_mes}")
        if filtro_tipo != "Todos":
            df_fil = df_fil[df_fil["tipo"] == filtro_tipo]
            filtros_activos.append(filtro_tipo)
        if filtro_medio == "Efectivo":
            df_fil = df_fil[df_fil["medio"] == "Efectivo"]
            filtros_activos.append("Solo Efectivo")
        elif filtro_medio == "Depósito / Transferencia (Bancos)":
            df_fil = df_fil[df_fil["medio"] != "Efectivo"]
            filtros_activos.append("Solo Bancos")
        if filtro_fondo != "Todos":
            df_fil = df_fil[df_fil["fondo"] == filtro_fondo]
            filtros_activos.append(f"Fondo {filtro_fondo}")
        if filtro_cat != "Todas":
            df_fil = df_fil[df_fil["categoria"] == filtro_cat]
            filtros_activos.append(f"Cat: {filtro_cat}")
        if filtro_txt.strip():
            t_low = filtro_txt.strip().lower()
            df_fil = df_fil[
                df_fil["detalle"].astype(str).str.lower().str.contains(t_low) |
                df_fil["comprobante"].astype(str).str.lower().str.contains(t_low) |
                df_fil["responsable"].astype(str).str.lower().str.contains(t_low)
            ]
            filtros_activos.append(f"Texto '{filtro_txt}'")

        txt_filtros_resumen = ", ".join(filtros_activos) if filtros_activos else "Todos los registros"

        tot_ing = float(df_fil[df_fil["tipo"] == "Ingreso"]["monto"].sum()) if not df_fil.empty else 0.0
        tot_egr = float(df_fil[df_fil["tipo"] == "Egreso"]["monto"].sum()) if not df_fil.empty else 0.0
        saldo_neto = tot_ing - tot_egr

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ingresos Filtrados", f"S/. {tot_ing:,.2f}")
        m2.metric("Egresos Filtrados", f"S/. {tot_egr:,.2f}", delta=f"-S/. {tot_egr:,.2f}", delta_color="inverse")
        m3.metric("Saldo Neto", f"S/. {saldo_neto:,.2f}")
        m4.metric("Movimientos Listados", f"{len(df_fil)} reg.")

        col_pdf, col_xls, col_info = st.columns([2.5, 2.5, 4])
        with col_pdf:
            if not df_fil.empty:
                st.download_button(
                    label="📄 Descargar PDF (Columnas y Filtros Actuales)",
                    data=lambda: generar_pdf_libro_caja_dinamico(df_fil, cols_seleccionadas, tot_ing, tot_egr, saldo_neto, txt_filtros_resumen),
                    file_name=f"Libro_Caja_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        with col_xls:
            if not df_fil.empty:
                st.download_button(
                    label="📊 Descargar Excel (Columnas y Filtros Actuales)",
                    data=lambda: generar_excel_dinamico(df_fil, cols_seleccionadas),
                    file_name=f"Libro_Caja_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
        with col_info:
            st.caption(f"Visualizando **{len(cols_seleccionadas)}** columnas seleccionadas.")

        st.markdown("---")

        cols_db_mostrar = [MAP_COLUMNAS_INFO[c][0] for c in cols_seleccionadas]
        renombrar_dict = {MAP_COLUMNAS_INFO[c][0]: c for c in cols_seleccionadas}
        df_mostrar = df_fil[cols_db_mostrar].rename(columns=renombrar_dict)

        format_dict = {}
        if "Monto (S/.)" in cols_seleccionadas:
            format_dict["Monto (S/.)"] = "S/. {:,.2f}"

        st.dataframe(
            df_mostrar.style.format(format_dict),
            use_container_width=True,
            hide_index=True
        )

# ==============================================================================
# 2. EVOLUCIÓN Y GRÁFICOS
# ==============================================================================
elif opcion == "Evolución y Gráficos":
    # Excluímos los asientos de apertura usando Pandas filtrando el df global ya descargado
    df_graf = df_mov_global[~df_mov_global["comprobante"].astype(str).str.startswith("ASIENTO-APERTURA")].copy()
    
    if df_graf.empty:
        st.info("No hay suficientes registros para proyectar gráficas estadísticas.")
    else:
        # Enlaza las columnas de SQL a las que necesita el reporte
        df_graf["Anio"] = df_graf["anio"]
        df_graf["MesNum"] = df_graf["mes_num"]
        df_graf["Mes"] = df_graf["MesNum"].map(core.MESES_NOMBRES)

        anios_graf = sorted(list(df_graf["Anio"].dropna().unique()), reverse=True)
        
        c_g1, c_g2 = st.columns([2, 2])
        with c_g1:
            anio_graf = st.selectbox("Año a Graficar:", anios_graf, index=0)
        with c_g2:
            filtro_medio_graf = st.selectbox("Medio de Pago para Ingresos y Egresos:", ["Ambos (Efectivo y Bancos)", "Solo Efectivo", "Solo Depósito / Transferencia (Bancos)"])

        df_anio = df_graf[df_graf["Anio"] == anio_graf].copy()

        if filtro_medio_graf == "Solo Efectivo":
            df_anio_medio = df_anio[df_anio["medio"] == "Efectivo"]
        elif filtro_medio_graf == "Solo Depósito / Transferencia (Bancos)":
            df_anio_medio = df_anio[df_anio["medio"] != "Efectivo"]
        else:
            df_anio_medio = df_anio

        pivot_m = df_anio_medio.pivot_table(index="Mes", columns="tipo", values="monto", aggfunc="sum", fill_value=0.0).reindex(core.MESES).fillna(0.0)
        if "Ingreso" not in pivot_m.columns: pivot_m["Ingreso"] = 0.0
        if "Egreso" not in pivot_m.columns: pivot_m["Egreso"] = 0.0
        pivot_m["Saldo"] = pivot_m["Ingreso"] - pivot_m["Egreso"]

        y_ingresos = pivot_m["Ingreso"].values
        y_egresos = pivot_m["Egreso"].values
        y_saldos = pivot_m["Saldo"].values

        # CUADRO 1: INGRESOS
        fig_ing = go.Figure()
        fig_ing.add_trace(go.Bar(
            name="Ingresos Mensuales", 
            x=core.MESES, 
            y=y_ingresos,
            marker_color="#10B981", 
            text=pivot_m["Ingreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_plotly(fig_ing, core.MESES, y_ingresos, "Proyección / Tendencia Ingresos")
        fig_ing.update_layout(
            title=f"1. Ingresos Operativos Mensuales ({anio_graf}) — {filtro_medio_graf}",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=370,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_ing, use_container_width=True)

        # CUADRO 2: EGRESOS
        fig_egr = go.Figure()
        fig_egr.add_trace(go.Bar(
            name="Egresos Mensuales", 
            x=core.MESES, 
            y=y_egresos,
            marker_color="#EF4444", 
            text=pivot_m["Egreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_plotly(fig_egr, core.MESES, y_egresos, "Proyección / Tendencia Gastos")
        fig_egr.update_layout(
            title=f"2. Egresos y Gastos Mensuales ({anio_graf}) — {filtro_medio_graf}",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=370,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_egr, use_container_width=True)

        # CUADRO 3: DIEZMOS
        df_dz_bd = cargar_diezmos_graficos()
        if not df_dz_bd.empty:
            df_dz_anio = df_dz_bd[df_dz_bd["anio"] == anio_graf].copy()
            df_dz_anio["Mes"] = df_dz_anio["mes_num"].map(core.MESES_NOMBRES)
            s_dz = df_dz_anio.groupby("Mes")["monto"].sum().reindex(core.MESES).fillna(0.0)
            y_diezmos = s_dz.values
        else:
            y_diezmos = np.zeros(12)

        fig_dz = go.Figure()
        fig_dz.add_trace(go.Bar(
            name="Diezmos Recaudados",
            x=core.MESES,
            y=y_diezmos,
            marker_color="#6366F1",
            text=[f"S/. {v:,.0f}" if v > 0 else "" for v in y_diezmos],
            textposition="auto"
        ))
        agregar_tendencia_plotly(fig_dz, core.MESES, y_diezmos, "Proyección de Fidelidad / Diezmos")
        fig_dz.update_layout(
            title=f"3. Comportamiento de Diezmos ({anio_graf})",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=370,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_dz, use_container_width=True)

        # CUADRO 4: SALDOS OPERATIVOS
        colores_sal = ["#1E3A8A" if s >= 0 else "#DC2626" for s in y_saldos]
        fig_sal = go.Figure()
        fig_sal.add_trace(go.Bar(
            name="Saldo Neto del Mes",
            x=core.MESES,
            y=y_saldos,
            marker_color=colores_sal,
            text=pivot_m["Saldo"].apply(lambda v: f"S/. {v:,.0f}" if v != 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_plotly(fig_sal, core.MESES, y_saldos, "Tendencia de Superávit")
        fig_sal.update_layout(
            title=f"4. Saldos Operativos Netos por Periodo ({anio_graf})",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=370,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_sal, use_container_width=True)

        # DESCARGA DE REPORTE GRÁFICO (BAJO DEMANDA)
        st.markdown("---")
        tot_i_graf = float(np.sum(y_ingresos))
        tot_e_graf = float(np.sum(y_egresos))
        tot_dz_graf = float(np.sum(y_diezmos))
        sal_acum_graf = tot_i_graf - tot_e_graf

        col_b_g, _ = st.columns([3, 4])
        with col_b_g:
            st.download_button(
                label=f"📄 Descargar los 4 Gráficos y Proyecciones en PDF ({anio_graf})",
                data=lambda: generar_pdf_cuadros_graficos(
                    anio_graf, filtro_medio_graf, 
                    fig_ing, fig_egr, fig_dz, fig_sal,
                    y_ingresos, y_egresos, y_diezmos, y_saldos,
                    tot_i_graf, tot_e_graf, tot_dz_graf, sal_acum_graf
                ),
                file_name=f"Reporte_Graficos_Tesoreria_{anio_graf}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )

# ==============================================================================
# 3. REGISTRAR MOVIMIENTO MANUAL
# ==============================================================================
elif opcion == "Registrar Movimiento":
    t_mov = st.radio("Tipo:", ["Egreso (Gasto)", "Ingreso"], horizontal=True)
    tipo_cl = "Egreso" if "Egreso" in t_mov else "Ingreso"

    dict_c = {}
    if not df_rubros_cat.empty:
        cats = df_rubros_cat[df_rubros_cat["tipo"] == tipo_cl]
        for c, g in cats.groupby("categoria"): 
            dict_c[c] = g["subcategoria"].tolist()
    else:
        dict_c = {"General": ["General"]}

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
                INSERT INTO public.movimientos 
                (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'Cobrado')
            """, (str(fecha), tipo_cl, cat, subcat, fondo, round(float(monto), 2), medio, comp.strip(), det.strip(), resp))
            core.registrar_log("Tesorería", "Registro", f"{tipo_cl} S/. {monto:,.2f} - {det.strip()} ({comp.strip()})")
            
            limpiar_caches_tesoreria()
            
            st.toast("✅ Movimiento guardado en Tesorería.")
            st.rerun()

# ==============================================================================
# 4. MODIFICAR O ELIMINAR
# ==============================================================================
elif opcion == "⚙️ Modificar o Eliminar":
    st.markdown("#### ⚙️ Gestión de Asientos de Tesorería (Modificar o Eliminar)")
    
    if df_mov_global.empty:
        st.info("No hay transacciones registradas en Tesorería.")
    else:
        with st.expander("🔎 Filtros para Localizar Asiento Contable", expanded=True):
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                b_txt = st.text_input("Buscar por Detalle / Comprobante / Responsable:", placeholder="Ej. Luz, CORTE-1, Enel...")
            with col_f2:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_mov_global["anio"].dropna().unique()], reverse=True)
                b_anio = st.selectbox("Año:", anios_disp, index=0)
            with col_f3:
                b_mes = st.selectbox("Mes:", ["Todos"] + core.MESES, index=0)
            with col_f4:
                b_tipo = st.selectbox("Tipo:", ["Todos", "Ingreso", "Egreso"], index=0)

        df_filtrado_mov = df_mov_global
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
            df_filtrado_mov = df_filtrado_mov[df_filtrado_mov["mes_num"] == mes_num_f]
        if b_tipo != "Todos":
            df_filtrado_mov = df_filtrado_mov[df_filtrado_mov["tipo"] == b_tipo]

        st.caption(f"Coincidencias encontradas: **{len(df_filtrado_mov)}** de {len(df_mov_global)} transacciones.")

        if df_filtrado_mov.empty:
            st.warning("⚠️ No se encontraron movimientos con los filtros especificados.")
        else:
            def label_mov(r):
                c_str = f" | Comp: {r['comprobante']}" if r.get('comprobante') else ""
                return f"ID #{r['id']} [{r['fecha']}] {r['tipo']} — S/. {float(r['monto']):,.2f} ({str(r['detalle'])[:30]}){c_str}"

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
                idx_resp = resps.index(reg_mov["responsable"]) if reg_mov["responsable"] in resps else 0

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
                        e_resp = st.selectbox("Responsable:", resps, index=idx_resp)
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
                    
                    limpiar_caches_tesoreria()
                    
                    st.toast("✅ Asiento contable actualizado correctamente.")
                    st.rerun()

            elif accion_m == "🗑️ Eliminar Transacción":
                st.warning(f"⚠️ ¿Confirma eliminar definitivamente la transacción **ID #{reg_mov['id']}** por **S/. {float(reg_mov['monto']):,.2f}** ({reg_mov['detalle']})?")
                if st.button("Eliminar Definitivamente", type="primary"):
                    core.query_db("DELETE FROM public.movimientos WHERE id=?", (id_mov_sel,))
                    core.registrar_log("Tesorería", "Eliminación", f"Eliminado asiento ID #{id_mov_sel} de S/. {float(reg_mov['monto']):,.2f}")
                    
                    limpiar_caches_tesoreria()
                    
                    st.toast("🗑️ Transacción eliminada de Tesorería.")
                    st.rerun()

core.mostrar_pie_pagina()
