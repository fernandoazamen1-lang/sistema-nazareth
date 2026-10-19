import streamlit as st
import core
import io
import pandas as pd
import numpy as np
from datetime import date, datetime
import plotly.graph_objects as go
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

st.set_page_config(
    page_title="Tesorería y Movimientos", 
    page_icon="🏛️", 
    layout="wide"
)
core.requerir_login()
core.aplicar_estilos_base()

st.subheader("🏛️ Libro de Tesorería y Movimientos")

# Selector principal de puntos limpios (st.radio nativo)
opcion = st.radio(
    "Sección:", 
    ["Libro Detallado", "Evolución y Gráficos", "Registrar Movimiento", "⚙️ Modificar o Eliminar"], 
    horizontal=True
)

st.markdown("---")

# Catálogos base
df_fondos = core.read_db("SELECT nombre FROM public.fondos_catalogo")
fondos = df_fondos["nombre"].tolist() if not df_fondos.empty else ["General"]

# ==============================================================================
# GENERADORES DE REPORTES DINÁMICOS (PDF Y EXCEL)
# ==============================================================================
def generar_pdf_libro_caja(df_reporte, tot_i, tot_e, saldo_n, filtros_txt=""):
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

    filas = [["FECHA", "TIPO", "MEDIO", "FONDO", "CATEGORÍA / RUBRO", "COMPROBANTE", "DETALLE", "MONTO"]]
    for _, r in df_reporte.iterrows():
        filas.append([
            str(r.get("fecha", ""))[:10],
            str(r.get("tipo", "")),
            str(r.get("medio", ""))[:14],
            str(r.get("fondo", ""))[:10],
            f"{r.get('categoria', '')} - {r.get('subcategoria', '')}"[:24],
            str(r.get("comprobante", ""))[:12],
            str(r.get("detalle", ""))[:32],
            f"S/. {float(r.get('monto', 0)):,.2f}"
        ])

    filas.append(["", "", "", "", "", "", "SALDO NETO LISTADO:", f"S/. {saldo_n:,.2f}"])

    t_tabla = Table(filas, colWidths=[55, 45, 75, 55, 125, 70, 235, 80])
    t_tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-2), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.2),
        ('ALIGN', (0,0), (3,-1), 'CENTER'),
        ('ALIGN', (5,0), (5,-1), 'CENTER'),
        ('ALIGN', (7,1), (7,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FEF08A")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,-1), (-1,-1), 1, colors.HexColor("#CA8A04")),
        ('PADDING', (0,0), (-1,-1), 2.8)
    ]))
    elem.extend([t_tabla, Spacer(1, 28)])

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

def generar_excel_tesoreria(df_exp):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Libro_Caja_Filtrado")
    return output.getvalue()

def agregar_tendencia_lineal(fig, x_labels, y_vals, nombre_traza="Línea de Tendencia"):
    y_arr = np.array(y_vals, dtype=float)
    x_idx = np.arange(len(x_labels))
    if np.any(y_arr > 0):
        try:
            coefs = np.polyfit(x_idx, y_arr, 1)
            y_trend = np.polyval(coefs, x_idx)
            fig.add_trace(go.Scatter(
                x=x_labels, 
                y=y_trend,
                mode="lines",
                name=nombre_traza,
                line=dict(color="#F59E0B", width=2.5, dash="dash")
            ))
        except Exception:
            pass

# ==============================================================================
# 1. LIBRO DETALLADO CON FILTROS FLOTANTES Y DESCARGA DINÁMICA
# ==============================================================================
if opcion == "Libro Detallado":
    df_mov = core.read_db("SELECT * FROM public.movimientos ORDER BY date(fecha) DESC, id DESC")
    
    if df_mov.empty:
        st.info("No hay movimientos registrados en el libro de Tesorería.")
    else:
        df_mov["dt"] = pd.to_datetime(df_mov["fecha"], errors="coerce")
        df_mov["anio"] = df_mov["dt"].dt.year
        df_mov["mes_num"] = df_mov["dt"].dt.month

        # PANEL FLOTANTE DE OPCIONES DE FILTRADO
        with st.expander("🔎 Filtros Avanzados de Consulta y Descarga", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_mov["anio"].dropna().unique()], reverse=True)
                filtro_anio = st.selectbox("Año:", anios_disp, index=0)
            with f2:
                filtro_mes = st.selectbox("Mes:", ["Todos"] + core.MESES, index=0)
            with f3:
                filtro_tipo = st.selectbox("Tipo de Movimiento:", ["Todos", "Ingreso", "Egreso"])
            with f4:
                # FILTRO DE MEDIO SOLICITADO: EFECTIVO, BANCOS O AMBOS
                filtro_medio = st.selectbox("Medio de Entrega:", ["Ambos (Todos)", "Efectivo", "Depósito / Transferencia (Bancos)"])

            f5, f6, f7 = st.columns([1.5, 1.5, 3])
            with f5:
                filtro_fondo = st.selectbox("Fondo:", ["Todos"] + fondos)
            with f6:
                cats_existentes = ["Todas"] + sorted([str(c) for c in df_mov["categoria"].dropna().unique() if str(c).strip()])
                filtro_cat = st.selectbox("Categoría:", cats_existentes)
            with f7:
                filtro_txt = st.text_input("Búsqueda Rápida:", placeholder="Buscar por detalle, comprobante o responsable...")

        # Aplicación de los filtros
        df_fil = df_mov.copy()
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

        txt_filtros_resumen = ", ".join(filtros_activos) if filtros_activos else "Sin filtros (Total consolidado)"

        # Cálculos de totales con conversión estricta a float
        tot_ing = float(df_fil[df_fil["tipo"] == "Ingreso"]["monto"].sum()) if not df_fil.empty else 0.0
        tot_egr = float(df_fil[df_fil["tipo"] == "Egreso"]["monto"].sum()) if not df_fil.empty else 0.0
        saldo_neto = tot_ing - tot_egr

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ingresos Filtrados", f"S/. {tot_ing:,.2f}")
        m2.metric("Egresos Filtrados", f"S/. {tot_egr:,.2f}", delta=f"-S/. {tot_egr:,.2f}", delta_color="inverse")
        m3.metric("Saldo Neto", f"S/. {saldo_neto:,.2f}")
        m4.metric("Registros Listados", f"{len(df_fil)} mov.")

        # BOTONES DE DESCARGA SEGÚN LO FILTRADO
        col_pdf, col_xls, col_aviso = st.columns([2.5, 2.5, 4])
        with col_pdf:
            if not df_fil.empty:
                pdf_bytes = generar_pdf_libro_caja(df_fil, tot_ing, tot_egr, saldo_neto, txt_filtros_resumen)
                st.download_button(
                    label="📄 Descargar PDF (Vista Actual)",
                    data=pdf_bytes,
                    file_name=f"Libro_Caja_Filtrado_{date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        with col_xls:
            if not df_fil.empty:
                cols_para_excel = ["fecha", "tipo", "medio", "categoria", "subcategoria", "fondo", "monto", "comprobante", "responsable", "detalle"]
                cols_presentes = [c for c in cols_para_excel if c in df_fil.columns]
                excel_bytes = generar_excel_tesoreria(df_fil[cols_presentes])
                st.download_button(
                    label="📊 Descargar Excel (Vista Actual)",
                    data=excel_bytes,
                    file_name=f"Libro_Caja_Filtrado_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
        with col_aviso:
            st.caption(f"Filtro activo: **{txt_filtros_resumen}**")

        st.markdown("---")

        # Visualización de la tabla
        map_cols = {
            "fecha": "Fecha", "tipo": "Tipo", "medio": "Medio", "fondo": "Fondo",
            "categoria": "Categoría", "subcategoria": "Rubro", "monto": "Monto (S/.)",
            "comprobante": "Comprobante", "responsable": "Responsable", "detalle": "Detalle"
        }
        cols_mostrar = [c for c in map_cols.keys() if c in df_fil.columns]
        st.dataframe(
            df_fil[cols_mostrar].rename(columns=map_cols).style.format({"Monto (S/.)": "S/. {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

# ==============================================================================
# 2. EVOLUCIÓN Y 4 CUADROS GRÁFICOS CON PROYECCIONES
# ==============================================================================
elif opcion == "Evolución y Gráficos":
    df_mov = core.read_db("SELECT fecha, tipo, monto, medio, categoria, comprobante FROM public.movimientos WHERE comprobante NOT IN ('ASIENTO-APERTURA') AND fecha IS NOT NULL")
    
    if df_mov.empty:
        st.info("No hay suficientes registros para proyectar gráficas estadísticas.")
    else:
        df_mov["fecha_dt"] = pd.to_datetime(df_mov["fecha"], errors="coerce")
        df_mov = df_mov.dropna(subset=["fecha_dt"])
        df_mov["Anio"] = df_mov["fecha_dt"].dt.year
        df_mov["MesNum"] = df_mov["fecha_dt"].dt.month
        df_mov["Mes"] = df_mov["MesNum"].map(core.MESES_NOMBRES)

        anios_graf = sorted(list(df_mov["Anio"].unique()), reverse=True)
        
        # Filtro de cabecera para los gráficos
        c_g1, c_g2 = st.columns([2, 2])
        with c_g1:
            anio_graf = st.selectbox("Año a Graficar:", anios_disp := anios_graf, index=0)
        with c_g2:
            filtro_medio_graf = st.selectbox("Medio de Pago para Ingresos y Egresos:", ["Ambos (Efectivo y Bancos)", "Solo Efectivo", "Solo Depósito / Transferencia (Bancos)"])

        df_anio = df_mov[df_mov["Anio"] == anio_graf].copy()

        # Filtrado de medio si corresponde
        if filtro_medio_graf == "Solo Efectivo":
            df_anio_medio = df_anio[df_anio["medio"] == "Efectivo"]
        elif filtro_medio_graf == "Solo Depósito / Transferencia (Bancos)":
            df_anio_medio = df_anio[df_anio["medio"] != "Efectivo"]
        else:
            df_anio_medio = df_anio

        # Tabulación mensual
        pivot_m = df_anio_medio.pivot_table(index="Mes", columns="tipo", values="monto", aggfunc="sum", fill_value=0.0).reindex(core.MESES).fillna(0.0)
        if "Ingreso" not in pivot_m.columns: pivot_m["Ingreso"] = 0.0
        if "Egreso" not in pivot_m.columns: pivot_m["Egreso"] = 0.0
        pivot_m["Saldo"] = pivot_m["Ingreso"] - pivot_m["Egreso"]

        # ----------------------------------------------------------------------
        # CUADRO 1: SOLO INGRESOS + TENDENCIA DE PROYECCIÓN
        # ----------------------------------------------------------------------
        st.markdown("#### 1. Evolución Mensual de Ingresos")
        fig_ing = go.Figure()
        fig_ing.add_trace(go.Bar(
            name="Ingresos Mensuales", 
            x=core.MESES, 
            y=pivot_m["Ingreso"],
            marker_color="#10B981", 
            text=pivot_m["Ingreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_lineal(fig_ing, core.MESES, pivot_m["Ingreso"].values, "Proyección / Tendencia Ingresos")
        fig_ing.update_layout(
            title=f"Ingresos Mensuales ({anio_graf}) — {filtro_medio_graf}",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=390,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_ing, use_container_width=True)

        # ----------------------------------------------------------------------
        # CUADRO 2: SOLO EGRESOS + TENDENCIA DE PROYECCIÓN
        # ----------------------------------------------------------------------
        st.markdown("#### 2. Evolución Mensual de Egresos y Gastos")
        fig_egr = go.Figure()
        fig_egr.add_trace(go.Bar(
            name="Egresos Mensuales", 
            x=core.MESES, 
            y=pivot_m["Egreso"],
            marker_color="#EF4444", 
            text=pivot_m["Egreso"].apply(lambda v: f"S/. {v:,.0f}" if v > 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_lineal(fig_egr, core.MESES, pivot_m["Egreso"].values, "Proyección / Tendencia Gastos")
        fig_egr.update_layout(
            title=f"Egresos y Gastos Mensuales ({anio_graf}) — {filtro_medio_graf}",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=390,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_egr, use_container_width=True)

        # ----------------------------------------------------------------------
        # CUADRO 3: EVOLUCIÓN DE LOS DIEZMOS + TENDENCIA DE PROYECCIÓN
        # ----------------------------------------------------------------------
        st.markdown("#### 3. Evolución Histórica de Diezmos")
        # Leer aportes directamente de diezmos
        df_diezmos_bd = core.read_db("SELECT fecha, monto FROM public.diezmos WHERE fecha IS NOT NULL")
        if not df_diezmos_bd.empty:
            df_diezmos_bd["dt"] = pd.to_datetime(df_diezmos_bd["fecha"], errors="coerce")
            df_diezmos_bd = df_diezmos_bd.dropna(subset=["dt"])
            df_dz_anio = df_diezmos_bd[df_diezmos_bd["dt"].dt.year == anio_graf].copy()
            df_dz_anio["Mes"] = df_dz_anio["dt"].dt.month.map(core.MESES_NOMBRES)
            diezmos_mes = df_dz_anio.groupby("Mes")["monto"].sum().reindex(core.MESES).fillna(0.0)
        else:
            diezmos_mes = pd.Series(0.0, index=core.MESES)

        fig_dz = go.Figure()
        fig_dz.add_trace(go.Bar(
            name="Diezmos Recaudados",
            x=core.MESES,
            y=diezmos_mes.values,
            marker_color="#6366F1",
            text=[f"S/. {v:,.0f}" if v > 0 else "" for v in diezmos_mes.values],
            textposition="auto"
        ))
        agregar_tendencia_lineal(fig_dz, core.MESES, diezmos_mes.values, "Proyección de Fidelidad / Diezmos")
        fig_dz.update_layout(
            title=f"Comportamiento de Diezmos ({anio_graf})",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=390,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_dz, use_container_width=True)

        # ----------------------------------------------------------------------
        # CUADRO 4: SALDOS QUE QUEDAN POR MES + TENDENCIA DE PROYECCIÓN
        # ----------------------------------------------------------------------
        st.markdown("#### 4. Saldos Netos Remanentes por Mes (Superávit / Déficit)")
        colores_saldo = ["#1E3A8A" if s >= 0 else "#DC2626" for s in pivot_m["Saldo"].values]
        
        fig_sal = go.Figure()
        fig_sal.add_trace(go.Bar(
            name="Saldo Neto del Mes",
            x=core.MESES,
            y=pivot_m["Saldo"],
            marker_color=colores_saldo,
            text=pivot_m["Saldo"].apply(lambda v: f"S/. {v:,.0f}" if v != 0 else ""),
            textposition="auto"
        ))
        agregar_tendencia_lineal(fig_sal, core.MESES, pivot_m["Saldo"].values, "Tendencia de Superávit / Capacidad de Ahorro")
        fig_sal.update_layout(
            title=f"Saldos Netos por Periodo ({anio_graf})",
            xaxis_title="Mes", yaxis_title="Monto (S/.)", height=390,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_sal, use_container_width=True)

# ==============================================================================
# 3. REGISTRAR MOVIMIENTO MANUAL
# ==============================================================================
elif opcion == "Registrar Movimiento":
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
# 4. MODIFICAR O ELIMINAR
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
