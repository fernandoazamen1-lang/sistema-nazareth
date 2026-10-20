import streamlit as st
import core
import io
from datetime import date, datetime
import pandas as pd

# 1. Configuración de página
st.set_page_config(
    page_title="Sostenimiento Pastoral", 
    page_icon="✝️", 
    layout="wide"
)

# 2. Seguridad y verificación de permisos
core.requerir_login()
core.verificar_acceso_pagina("Sostenimiento Pastoral")
core.aplicar_estilos_base()

# ==============================================================================
# CARGA DE CONFIGURACIÓN PERSISTENTE EN MEMORIA (OPTIMIZADA)
# ==============================================================================
@st.cache_data(ttl=120, show_spinner=False)
def cargar_config_pastoral():
    df = core.read_db("""
        SELECT modulo, descripcion 
        FROM public.auditoria 
        WHERE modulo IN ('Config_PastorPrincipal', 'Config_PastorPrincipal_DNI', 'Config_Tesorero')
        ORDER BY id ASC
    """)
    cfg = {}
    if not df.empty:
        for _, r in df.iterrows():
            cfg[r["modulo"]] = r["descripcion"]
            
    pastor_def = cfg.get('Config_PastorPrincipal', "Pr. Titular")
    dni_def = cfg.get('Config_PastorPrincipal_DNI', "")
    tes_def = cfg.get('Config_Tesorero', "Tesorero General")
    return pastor_def, dni_def, tes_def

pastor_p_def, dni_p_def, tesorero_def = cargar_config_pastoral()

def _set_config(modulo, nuevo_val, actual_val):
    if nuevo_val.strip() and nuevo_val.strip() != actual_val:
        core.query_db(
            "INSERT INTO public.auditoria (fecha_hora, modulo, accion, descripcion) VALUES (?, ?, 'Actualizar', ?)",
            (str(date.today()), modulo, nuevo_val.strip())
        )

# Lógica correlativa y contable
def get_sig_codigo(prefijo):
    df_u = core.read_db("SELECT codigo FROM public.sostenimiento_pastoral WHERE codigo LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefijo} - %",))
    if df_u.empty:
        return f"{prefijo} - 00001"
    try:
        num = int(df_u.iloc[0]["codigo"].split("-")[-1].strip())
        return f"{prefijo} - {num + 1:05d}"
    except Exception:
        df_cant = core.read_db("SELECT COUNT(*) as t FROM public.sostenimiento_pastoral WHERE codigo LIKE ?", (f"{prefijo} - %",))
        cant = df_cant.iloc[0]["t"] if not df_cant.empty else 0
        return f"{prefijo} - {int(cant) + 1:05d}"

def _sincronizar_asiento_tesoreria(fecha, tipo_beneficiario, monto_neto, medio, codigo, motivo, pastor, tesorero, es_update=False):
    subcat = "Pastor Principal" if tipo_beneficiario == "Principal" else "Pastores Eventuales / Invitados"
    det_caja = f"Sostenimiento {motivo} - {pastor} (Neto Percibido)" if tipo_beneficiario == "Principal" else f"Ofrenda {motivo} - {pastor}"
    if es_update:
        core.query_db("""
            UPDATE public.movimientos SET fecha = ?, monto = ?, medio = ?, responsable = ?, detalle = ?
            WHERE comprobante = ?
        """, (str(fecha), monto_neto, medio, tesorero, det_caja, codigo))
    else:
        core.query_db("""
            INSERT INTO public.movimientos (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito)
            VALUES (?, 'Egreso', 'Sostenimiento Pastoral', ?, 'General', ?, ?, ?, ?, ?, '', 'Cobrado')
        """, (str(fecha), subcat, monto_neto, medio, codigo, det_caja, tesorero))

# Generador de Acta PDF Profesional (Bajo demanda)
def generar_acta_pastoral_pdf(codigo, fecha, pastor, dni, tipo, mes_actividad, bruto, desc_pension, essalud, neto, medio, motivo, tesorero, regimen):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=40, rightMargin=40, topMargin=36, bottomMargin=36)
    elements = []

    f_inst = ParagraphStyle('T2', fontName='Helvetica-Bold', fontSize=9, alignment=1, textColor=colors.HexColor("#1E3A8A"))
    f_bold = ParagraphStyle('B', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor("#0F172A"))
    f_normal = ParagraphStyle('N', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor("#1E293B"))

    titulo_doc = "ACTA OFICIAL DE SOSTENIMIENTO PASTORAL" if tipo == "Principal" else "RECIBO MINISTERIAL DE OFRENDA EVENTUAL"
    t_head = Table([
        [
            Paragraph("<b>ASAMBLEAS DE DIOS DEL PERÚ</b><br/>IGLESIA EVANGÉLICA \"NAZARETH\"<br/><font size=7.5>DEPARTAMENTO DE ADMINISTRACIÓN Y FINANZAS</font>", f_inst),
            Table([
                [Paragraph("<b>SERIE DE REGISTRO</b>", ParagraphStyle('CR', fontName='Helvetica-Bold', fontSize=7.5, alignment=1, textColor=colors.HexColor("#854D0E")))],
                [Paragraph(f"<b>{codigo}</b>", ParagraphStyle('CV', fontName='Helvetica-Bold', fontSize=10, alignment=1, textColor=colors.HexColor("#0F172A")))]
            ], colWidths=[110], style=[('GRID', (0,0), (-1,-1), 1, colors.HexColor("#CA8A04")), ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF08A")), ('PADDING', (0,0), (-1,-1), 4)])
        ]
    ], colWidths=[422, 110])
    t_head.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 2)]))
    elements.extend([t_head, Spacer(1, 10)])

    t_tit_bar = Table([[Paragraph(f"<b>{titulo_doc}</b>", ParagraphStyle('TB', fontName='Helvetica-Bold', fontSize=11, alignment=1, textColor=colors.HexColor("#000000")))]], colWidths=[532])
    t_tit_bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFEE00")),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 5)
    ]))
    elements.extend([t_tit_bar, Spacer(1, 12)])

    subt_rol = "PASTOR PRINCIPAL TITULAR" if tipo == "Principal" else "MINISTRO / PREDICADOR INVITADO"
    info_datos = [
        [Paragraph("<b>MINISTRO BENEFICIARIO:</b>", f_bold), Paragraph(str(pastor).upper(), f_bold), Paragraph("<b>FECHA ENTREGA:</b>", f_bold), Paragraph(str(fecha), f_normal)],
        [Paragraph("<b>DNI / IDENTIFICACIÓN:</b>", f_bold), Paragraph(str(dni), f_normal), Paragraph("<b>CONDICIÓN:</b>", f_bold), Paragraph(subt_rol, f_normal)],
        [Paragraph("<b>PERIODO / CONCEPTO:</b>", f_bold), Paragraph(str(mes_actividad).upper(), f_normal), Paragraph("<b>MEDIO DE PAGO:</b>", f_bold), Paragraph(str(medio), f_normal)]
    ]
    t_info = Table(info_datos, colWidths=[130, 160, 100, 142])
    t_info.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('PADDING', (0,0), (-1,-1), 4.5)
    ]))
    elements.extend([t_info, Spacer(1, 12)])

    if tipo == "Principal":
        tabla_liq = [
            ["CONCEPTO / RUBRO ECONÓMICO", "BASE / MODALIDAD", "ASIGNACIÓN", "DESCUENTOS"],
            ["Sostenimiento Mensual Fijo Asignado", "Sueldo Bruto Acordado", f"S/. {bruto:,.2f}", "-"],
            [f"Aporte Previsional / Pensión ({regimen})", "Deducción de Ley", "-", f"S/. {desc_pension:,.2f}"],
            ["Aporte Institucional de Salud - EsSalud (9%)", "Aporte Patronal (No descontable)", f"S/. {essalud:,.2f}", "Aporte Iglesia"],
            ["NETO LÍQUIDO PERCIBIDO POR EL PASTOR", f"MEDIO: {medio.upper()}", f"S/. {neto:,.2f}", "CONFORME"]
        ]
        t_liq = Table(tabla_liq, colWidths=[200, 142, 95, 95])
        t_liq.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (2,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FFEE00")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,-1), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5)
        ]))
    else:
        tabla_liq = [
            ["CONCEPTO", "MOTIVO / EVENTO", "TOTAL OFRENDA"],
            ["Ofrenda Ministerial y Viáticos", str(motivo)[:40], f"S/. {neto:,.2f}"]
        ]
        t_liq = Table(tabla_liq, colWidths=[200, 212, 120])
        t_liq.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (2,0), (-1,-1), 'CENTER'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FFEE00")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
    elements.extend([t_liq, Spacer(1, 14)])

    if tipo == "Principal":
        decl_txt = (
            f"El suscrito <b>{str(pastor).upper()}</b>, en su calidad de Pastor Principal Titular de la Iglesia Evangélica "
            f"'Nazareth', hace constar haber recibido a entera conformidad y satisfacción de la Tesorería General el sostenimiento "
            f"pastoral correspondiente al mes de <b>{str(mes_actividad).upper()}</b>, habiéndose efectuado las retenciones "
            f"previsionales correspondientes ({regimen}) y respaldando el aporte institucional de EsSalud (9%) en cumplimiento "
            f"del pacto ministerial y los estatutos eclesiásticos de las Asambleas de Dios del Perú."
        )
    else:
        decl_txt = (
            f"El suscrito <b>{str(pastor).upper()}</b> certifica haber recibido de la Tesorería General de la Iglesia Evangélica "
            f"'Nazareth' la ofrenda ministerial y viáticos consignados, en gratitud y honra por la predicación y servicio "
            f"impartido en la actividad: <i>{motivo}</i> en fecha {fecha}."
        )

    t_decl = Table([[Paragraph(decl_txt, ParagraphStyle('Dec', fontName='Helvetica', fontSize=8, leading=11.5, alignment=4))]], colWidths=[532])
    t_decl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#334155")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('PADDING', (0,0), (-1,-1), 7)
    ]))
    elements.extend([t_decl, Spacer(1, 12)])

    biblia = (
        "«Los ancianos que gobiernan bien, sean tenidos por dignos de doble honor, mayormente los que trabajan en predicar y enseñar. "
        "Porque la Escritura dice: No pondrás bozal al buey que trilla; y: Digno es el obrero de su salario.» (1 Timoteo 5:17-18)<br/>"
        "«El que es enseñado en la palabra, haga partícipe de toda cosa buena al que lo instruye.» (Gálatas 6:6)"
    )
    t_bib = Table([[Paragraph(f"<i>{biblia}</i>", ParagraphStyle('Bib', fontName='Helvetica-Oblique', fontSize=7.5, leading=10.5, alignment=1, textColor=colors.HexColor("#1E3A8A")))]], colWidths=[532])
    t_bib.setStyle(TableStyle([
        ('LINEBEFORE', (0,0), (0,0), 2, colors.HexColor("#2563EB")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    elements.extend([t_bib, Spacer(1, 35)])

    t_firmas = Table([
        ["__________________________________________", "__________________________________________"],
        [f"{str(tesorero).upper()}", f"{str(pastor).upper()}"],
        ["TESORERÍA GENERAL", "PASTOR RECEPTOR CONFORME"],
        ["Iglesia Evangélica 'Nazareth'", f"DNI: {dni}"]
    ], colWidths=[266, 266])
    t_firmas.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 1.5)
    ]))
    elements.append(t_firmas)

    doc.build(elements)
    return buf.getvalue()

# Interfaz Principal
st.subheader("✝️ Gestión de Sostenimiento y Ofrendas Ministeriales")

opcion = st.radio(
    "Sección:", 
    [
        "✍️ Registrar Sostenimiento u Ofrenda",
        "📋 Consultas y Reportes Consolidados",
        "⚙️ Gestión de Comprobantes (Editar / Eliminar)"
    ], 
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# 1. REGISTRAR SOSTENIMIENTO U OFRENDA
# ==============================================================================
if opcion == "✍️ Registrar Sostenimiento u Ofrenda":
    st.markdown("#### ✍️ Emisión de Sostenimiento y Ofrendas")
    c_rad1, c_rad2 = st.columns([1, 2])
    with c_rad1:
        tipo_pastor = st.radio("Destinatario del Sostenimiento:", ["Pastor Principal", "Pastor Invitado / Eventual"])
    
    es_principal = (tipo_pastor == "Pastor Principal")
    prefijo = "SP" if es_principal else "OM"
    codigo_asignado = get_sig_codigo(prefijo)

    with c_rad2:
        st.info(f"🔖 **Código asignado:** `{codigo_asignado}` ({'Sostenimiento Pastoral Fijo Mensual' if es_principal else 'Ofrenda Eventual'})")

    with st.form("form_reg_pastoral"):
        c1, c2 = st.columns(2)
        with c1:
            f_emision = st.date_input("Fecha de Pago:", value=date.today())
            pastor_nombre = st.text_input("Nombre del Pastor:", value=pastor_p_def if es_principal else "", placeholder="Ej. Pr. Carlos Mendoza")
            pastor_dni = st.text_input("DNI / Cédula:", value=dni_p_def if es_principal else "", placeholder="Ej. 08451236")
            monto_bruto = st.number_input("Sueldo / Asignación Bruta (S/.):" if es_principal else "Ofrenda Ministerial (S/.):", min_value=10.0, value=1500.0 if es_principal else 200.0, step=50.0 if es_principal else 20.0, format="%.2f")

        with c2:
            periodo_concepto = st.selectbox("Mes Correspondiente:", core.MESES, index=date.today().month - 1) if es_principal else core.MESES[f_emision.month - 1]
            motivo_desc = "Sostenimiento Mensual Fijo" if es_principal else st.text_input("Motivo / Evento:", placeholder="Ej. Campaña Evangelística, Aniversario")
            medio_pago = st.selectbox("Medio de Pago:", ["Efectivo", "Depósito / Transferencia"])
            tesorero_resp = st.text_input("Tesorero Responsable:", value=tesorero_def)

        desc_pension = 0.0
        essalud_aporte = 0.0
        regimen_sel = "Sin Descuento"
        neto_final = float(monto_bruto)

        if es_principal:
            st.markdown("##### 🏛️ Retenciones Previsionales y EsSalud (Pastor Principal)")
            cp1, cp2, cp3 = st.columns(3)
            with cp1:
                regimen_sel = st.selectbox("Régimen Previsional:", ["AFP (Integra / Prima / Profuturo / Hábitat)", "ONP (13.0%)", "Sin Descuento"])
            with cp2:
                if "AFP" in regimen_sel:
                    tasa_pension = st.number_input("Tasa AFP (%):", min_value=1.0, max_value=25.0, value=11.90, step=0.1)
                elif "ONP" in regimen_sel:
                    tasa_pension = 13.0
                    st.caption("Tasa ONP fija: **13.0%**")
                else:
                    tasa_pension = 0.0
                    st.caption("Sin retención previsional.")
            with cp3:
                calc_essalud = st.checkbox("Calcular EsSalud Institucional (9%)", value=True)

            desc_pension = round(monto_bruto * (tasa_pension / 100.0), 2)
            essalud_aporte = round(monto_bruto * 0.09, 2) if calc_essalud else 0.0
            neto_final = round(monto_bruto - desc_pension, 2)

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Bruto Asignado", f"S/. {monto_bruto:,.2f}")
            col_m2.metric("Retención Pensión", f"- S/. {desc_pension:,.2f}")
            col_m3.metric("EsSalud (Aporte Iglesia 9%)", f"S/. {essalud_aporte:,.2f}")
            col_m4.metric("Neto a Percibir", f"S/. {neto_final:,.2f}")

        guardar_btn = st.form_submit_button(f"💾 Registrar y Emitir Acta ({codigo_asignado})", type="primary")

    if guardar_btn:
        if not pastor_nombre.strip():
            st.error("Debe ingresar el nombre del pastor receptor.")
        elif not es_principal and not motivo_desc.strip():
            st.error("Debe especificar el motivo o actividad del pastor invitado.")
        else:
            tipo_db = "Principal" if es_principal else "Eventual"
            if es_principal:
                _set_config('Config_PastorPrincipal', pastor_nombre, pastor_p_def)
                _set_config('Config_PastorPrincipal_DNI', pastor_dni, dni_p_def)
            _set_config('Config_Tesorero', tesorero_resp, tesorero_def)

            core.query_db("""
                INSERT INTO public.sostenimiento_pastoral 
                (codigo, fecha, tipo_beneficiario, pastor_nombre, pastor_dni, mes, monto, medio, motivo_evento, tesorero, regimen_pension, descuento_pension, essalud_aporte, monto_neto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo_asignado, str(f_emision), tipo_db, pastor_nombre.strip(), pastor_dni.strip(), periodo_concepto, monto_bruto, medio_pago, motivo_desc.strip(), tesorero_resp.strip(), regimen_sel, desc_pension, essalud_aporte, neto_final))

            _sincronizar_asiento_tesoreria(f_emision, tipo_db, neto_final, medio_pago, codigo_asignado, periodo_concepto if es_principal else motivo_desc, pastor_nombre.strip(), tesorero_resp.strip(), es_update=False)
            core.registrar_log("Pastoral", "Egreso", f"{codigo_asignado} a {pastor_nombre.strip()} por S/. {neto_final:,.2f} neto")

            st.session_state["ultimo_comprobante"] = {
                "codigo": codigo_asignado, "fecha": str(f_emision), "pastor": pastor_nombre.strip(), "dni": pastor_dni.strip(),
                "tipo": tipo_db, "mes": periodo_concepto, "bruto": monto_bruto, "desc_pension": desc_pension, "essalud": essalud_aporte,
                "neto": neto_final, "medio": medio_pago, "motivo": motivo_desc.strip(), "tesorero": tesorero_resp.strip(), "regimen": regimen_sel
            }
            st.toast(f"✅ Acta registrada exitosamente ({codigo_asignado}).")
            st.rerun()

    if "ultimo_comprobante" in st.session_state:
        uc = st.session_state["ultimo_comprobante"]
        st.success(f"🎉 Acta **{uc['codigo']}** generada con éxito para {uc['pastor']}.")
        st.download_button(
            f"📄 Descargar Acta Oficial en PDF ({uc['codigo']})",
            data=lambda: generar_acta_pastoral_pdf(
                uc["codigo"], uc["fecha"], uc["pastor"], uc["dni"], uc["tipo"], uc["mes"],
                uc["bruto"], uc["desc_pension"], uc["essalud"], uc["neto"], uc["medio"], uc["motivo"], uc["tesorero"], uc.get("regimen", "Sin Descuento")
            ),
            file_name=f"Acta_Sostenimiento_{uc['codigo'].replace(' ','')}_{uc['pastor']}.pdf",
            mime="application/pdf"
        )

# ==============================================================================
# 2. CONSULTAS Y REPORTES
# ==============================================================================
elif opcion == "📋 Consultas y Reportes Consolidados":
    st.markdown("#### 📋 Consultas Consolidadas y Reporte Mensual")
    df_base = core.read_db("SELECT * FROM public.sostenimiento_pastoral ORDER BY CAST(COALESCE(NULLIF(fecha, ''), '1970-01-01') AS DATE) DESC, id DESC")

    anio_actual = date.today().year
    anios_rango = set(range(anio_actual - 4, anio_actual + 5))
    if not df_base.empty:
        df_base["dt"] = pd.to_datetime(df_base["fecha"], errors="coerce")
        anios_bd = set(df_base["dt"].dt.year.dropna().astype(int).unique())
        anios_disp = sorted(list(anios_rango.union(anios_bd)), reverse=True)
    else:
        anios_disp = sorted(list(anios_rango), reverse=True)

    idx_anio_def = anios_disp.index(anio_actual) if anio_actual in anios_disp else 0

    c_v1, c_v2, c_v3 = st.columns(3)
    with c_v1: filtro_vista = st.selectbox("Información a consultar:", ["Todos los Movimientos", "Solo Pastor Principal", "Solo Pastores Invitados / Eventuales"])
    with c_v2: anio_sel = st.selectbox("Año:", anios_disp, index=idx_anio_def)
    with c_v3: mes_sel = st.selectbox("Mes:", ["Todos"] + core.MESES, index=0)

    if df_base.empty:
        st.info(f"No hay registros de sostenimiento u ofrendas para el año {anio_sel}.")
    else:
        df_filtrado = df_base[df_base["dt"].dt.year == anio_sel].copy()
        if mes_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["mes"] == mes_sel]
        if filtro_vista == "Solo Pastor Principal":
            df_filtrado = df_filtrado[df_filtrado["tipo_beneficiario"] == "Principal"]
        elif filtro_vista == "Solo Pastores Invitados / Eventuales":
            df_filtrado = df_filtrado[df_filtrado["tipo_beneficiario"] == "Eventual"]

        tot_neto = float(df_filtrado["monto_neto"].sum()) if "monto_neto" in df_filtrado.columns and not df_filtrado.empty else (float(df_filtrado["monto"].sum()) if not df_filtrado.empty else 0.0)
        tot_desc = float(df_filtrado["descuento_pension"].sum()) if "descuento_pension" in df_filtrado.columns and not df_filtrado.empty else 0.0
        tot_essalud = float(df_filtrado["essalud_aporte"].sum()) if "essalud_aporte" in df_filtrado.columns and not df_filtrado.empty else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Neto Percibido", f"S/. {tot_neto:,.2f}")
        m2.metric("Total Retención Pensión", f"S/. {tot_desc:,.2f}")
        m3.metric("Total EsSalud (9%) Institucional", f"S/. {tot_essalud:,.2f}")

        st.markdown("---")

        if df_filtrado.empty:
            st.warning(f"No se encontraron registros en el año {anio_sel} con los filtros seleccionados.")
        else:
            mapa = {
                "codigo": "Código", "fecha": "Fecha", "tipo_beneficiario": "Condición", "pastor_nombre": "Pastor Receptor",
                "mes": "Periodo", "monto": "Bruto (S/.)", "descuento_pension": "Ret. Pensión", "essalud_aporte": "EsSalud (9%)",
                "monto_neto": "Neto (S/.)", "medio": "Medio", "tesorero": "Tesorero"
            }
            cols_disponibles = [c for c in mapa.keys() if c in df_filtrado.columns]
            df_mostrar = df_filtrado[cols_disponibles].rename(columns=mapa)
            st.dataframe(df_mostrar.style.format({
                "Bruto (S/.)": "S/. {:,.2f}", "Ret. Pensión": "S/. {:,.2f}", "EsSalud (9%)": "S/. {:,.2f}", "Neto (S/.)": "S/. {:,.2f}"
            }), use_container_width=True, hide_index=True)

            def generar_reporte_consolidado_pdf(df_datos, anio, mes, tipo_titulo):
                from reportlab.lib.pagesizes import landscape, letter
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.lib import colors

                buf = io.BytesIO()
                doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
                t_head = Table([[
                    Paragraph(f"<b>IGLESIA EVANGÉLICA \"NAZARETH\" — REPORTE DE EGRESOS MINISTERIALES</b><br/><font size=8.5>{tipo_titulo.upper()} | Periodo: {mes} {anio} | Emitido: {date.today().strftime('%d/%m/%Y')}</font>",
                              ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10.5, alignment=1))
                ]], colWidths=[732], style=[
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
                    ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1D4ED8")),
                    ('PADDING', (0,0), (-1,-1), 6)
                ])

                filas = [["CÓDIGO", "FECHA", "CONDICIÓN", "PASTOR RECEPTOR", "PERIODO", "BRUTO", "RETIRO PENSIÓN", "ESSALUD 9%", "NETO"]]
                for _, r in df_datos.iterrows():
                    filas.append([
                        r["Código"], str(r["Fecha"]), str(r["Condición"]), str(r["Pastor Receptor"])[:20], str(r["Periodo"]),
                        f"S/. {r['Bruto (S/.)']:,.2f}", f"S/. {r['Ret. Pensión']:,.2f}", f"S/. {r['EsSalud (9%)']:,.2f}", f"S/. {r['Neto (S/.)']:,.2f}"
                    ])
                filas.append(["", "", "", "", "TOTAL:", f"S/. {df_datos['Bruto (S/.)'].sum():,.2f}", f"S/. {df_datos['Ret. Pensión'].sum():,.2f}", f"S/. {df_datos['EsSalud (9%)'].sum():,.2f}", f"S/. {df_datos['Neto (S/.)'].sum():,.2f}"])

                t_tabla = Table(filas, colWidths=[65, 65, 75, 140, 65, 75, 82, 82, 83], style=[
                    ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor("#CBD5E1")),
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 7.5),
                    ('ALIGN', (5,1), (-1,-1), 'RIGHT'),
                    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FFEE00")),
                    ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                    ('PADDING', (0,0), (-1,-1), 4)
                ])
                doc.build([t_head, Spacer(1, 10), t_tabla])
                return buf.getvalue()

            st.download_button(
                f"📄 Descargar Reporte en PDF ({filtro_vista})",
                data=lambda: generar_reporte_consolidado_pdf(df_mostrar, anio_sel, mes_sel, filtro_vista),
                file_name=f"Reporte_Ministerial_{anio_sel}_{mes_sel}.pdf",
                mime="application/pdf"
            )

# ==============================================================================
# 3. GESTIÓN DE COMPROBANTES (EDITAR / ELIMINAR)
# ==============================================================================
elif opcion == "⚙️ Gestión de Comprobantes (Editar / Eliminar)":
    st.markdown("#### ⚙️ Gestión de Comprobantes (Editar / Eliminar)")
    df_gestion = core.read_db("SELECT * FROM public.sostenimiento_pastoral ORDER BY id DESC")

    if df_gestion.empty:
        st.info("No hay comprobantes disponibles para gestionar.")
    else:
        opciones_bouchers = {f"{r['codigo']} — {r['pastor_nombre']} (S/. {r['monto']:,.2f} | {r['fecha']})": r["id"] for _, r in df_gestion.iterrows()}
        boucher_seleccionado = st.selectbox("Seleccione el comprobante a gestionar:", list(opciones_bouchers.keys()))
        id_gestion = opciones_bouchers[boucher_seleccionado]
        reg = df_gestion[df_gestion["id"] == id_gestion].iloc[0]

        accion = st.radio("Acción a realizar:", ["✏️ Editar Comprobante", "🗑️ Eliminar Comprobante"], horizontal=True)

        if accion == "✏️ Editar Comprobante":
            try: f_actual = datetime.strptime(str(reg["fecha"]), "%Y-%m-%d").date()
            except Exception: f_actual = date.today()

            es_p_edit = (reg["tipo_beneficiario"] == "Principal")

            with st.form("form_editar_consolidado"):
                st.info(f"Modificando comprobante **{reg['codigo']}**")
                c1, c2 = st.columns(2)
                with c1:
                    e_fecha = st.date_input("Fecha:", value=f_actual)
                    e_nombre = st.text_input("Pastor Receptor:", value=str(reg["pastor_nombre"]))
                    e_dni = st.text_input("DNI:", value=str(reg["pastor_dni"]))
                    e_monto = st.number_input("Sueldo Bruto / Monto (S/.):", min_value=1.0, value=float(reg["monto"]), step=10.0, format="%.2f")
                with c2:
                    idx_m = core.MESES.index(reg["mes"]) if reg["mes"] in core.MESES else 0
                    e_mes = st.selectbox("Mes / Periodo:", core.MESES, index=idx_m)
                    medios = ["Efectivo", "Depósito / Transferencia"]
                    e_medio = st.selectbox("Medio de Pago:", medios, index=medios.index(reg["medio"]) if reg["medio"] in medios else 0)
                    e_motivo = st.text_input("Motivo / Detalle:", value=str(reg["motivo_evento"]))
                    e_tesorero = st.text_input("Tesorero Responsable:", value=str(reg["tesorero"]))

                if es_p_edit:
                    reg_actual_val = str(reg.get("regimen_pension", "Sin Descuento"))
                    idx_reg = ["AFP (Integra / Prima / Profuturo / Hábitat)", "ONP (13.0%)", "Sin Descuento"].index(reg_actual_val) if reg_actual_val in ["AFP (Integra / Prima / Profuturo / Hábitat)", "ONP (13.0%)", "Sin Descuento"] else 2
                    e_regimen = st.selectbox("Régimen Previsional:", ["AFP (Integra / Prima / Profuturo / Hábitat)", "ONP (13.0%)", "Sin Descuento"], index=idx_reg)
                    tasa_e = 11.90 if "AFP" in e_regimen else (13.0 if "ONP" in e_regimen else 0.0)
                    e_desc = round(e_monto * (tasa_e / 100.0), 2)
                    e_essalud = round(e_monto * 0.09, 2)
                    e_neto = round(e_monto - e_desc, 2)
                else:
                    e_regimen = "Sin Descuento"
                    e_desc = 0.0
                    e_essalud = 0.0
                    e_neto = float(e_monto)

                btn_actualizar = st.form_submit_button("💾 Guardar Cambios y Actualizar Acta", type="primary")

            if btn_actualizar:
                core.query_db("""
                    UPDATE public.sostenimiento_pastoral SET
                        fecha = ?, pastor_nombre = ?, pastor_dni = ?, mes = ?,
                        monto = ?, medio = ?, motivo_evento = ?, tesorero = ?,
                        regimen_pension = ?, descuento_pension = ?, essalud_aporte = ?, monto_neto = ?
                    WHERE id = ?
                """, (str(e_fecha), e_nombre.strip(), e_dni.strip(), e_mes, e_monto, e_medio, e_motivo.strip(), e_tesorero.strip(), e_regimen, e_desc, e_essalud, e_neto, id_gestion))

                _sincronizar_asiento_tesoreria(e_fecha, reg["tipo_beneficiario"], e_neto, e_medio, reg["codigo"], e_motivo.strip(), e_nombre.strip(), e_tesorero.strip(), es_update=True)
                core.registrar_log("Pastoral", "Edición", f"Actualizado comprobante {reg['codigo']}")

                st.session_state["ultimo_comprobante"] = {
                    "codigo": reg["codigo"], "fecha": str(e_fecha), "pastor": e_nombre.strip(), "dni": e_dni.strip(),
                    "tipo": reg["tipo_beneficiario"], "mes": e_mes, "bruto": e_monto, "desc_pension": e_desc,
                    "essalud": e_essalud, "neto": e_neto, "medio": e_medio, "motivo": e_motivo.strip(),
                    "tesorero": e_tesorero.strip(), "regimen": e_regimen
                }
                st.toast("✅ Registro y asiento en Tesorería actualizados.")
                st.rerun()

        elif accion == "🗑️ Eliminar Comprobante":
            st.warning(f"⚠️ Al eliminar **{reg['codigo']}**, se eliminará también su asiento en Tesorería.")
            if st.button("Eliminar Comprobante Definitivamente", type="primary"):
                core.query_db("DELETE FROM public.sostenimiento_pastoral WHERE id=?", (id_gestion,))
                core.query_db("DELETE FROM public.movimientos WHERE comprobante=?", (reg["codigo"],))
                core.registrar_log("Pastoral", "Eliminación", f"Eliminado comprobante {reg['codigo']}")
                if "ultimo_comprobante" in st.session_state:
                    del st.session_state["ultimo_comprobante"]
                st.toast(f"🗑️ Comprobante {reg['codigo']} eliminado.")
                st.rerun()
