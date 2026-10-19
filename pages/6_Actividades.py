core.verificar_acceso_pagina("Actividades")
import streamlit as st
import core
from datetime import date
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Actividades Pro-Fondos", page_icon="🍲", layout="wide")
core.aplicar_estilos_base()

st.subheader("🍲 Gestión de Actividades y Platos Pro-Fondos")
df_act = core.read_db("SELECT * FROM actividades ORDER BY date(fecha) DESC, id DESC")

def generar_pdf_acta(nom_act, fecha_corte, cod_corte, df_liq, ing_cont, ing_cred, tot_egr, saldo_neto, tot_cred_pend, resp_act, fondo_dest):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=32, bottomMargin=32)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    t_head = Table([[
        Paragraph(f"<b>IGLESIA EVANGÉLICA NAZARETH</b><br/><font size=8>ACTA DE CORTE DE ACTIVIDAD: {nom_act}</font>", ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10, textColor=c_prim)),
        Paragraph(f"<b>CÓDIGO: {cod_corte}</b><br/><font size=8>Fecha de Corte: {fecha_corte}</font>", ParagraphStyle('H2', fontName='Helvetica', fontSize=8, alignment=2))
    ]], colWidths=[340, 200])
    elem.extend([t_head, Spacer(1, 10)])

    resumen = [
        ["CONCEPTO / RUBRO", "INGRESOS", "EGRESOS"],
        ["Ventas Directas al Contado", f"S/. {ing_cont:,.2f}", ""],
        ["Cobranza de Créditos Cancelados", f"S/. {ing_cred:,.2f}", ""],
        ["Gastos e Insumos Operativos", "", f"S/. {tot_egr:,.2f}"],
        ["SALDO NETO TRASPASADO A TESORERÍA", f"S/. {saldo_neto:,.2f}", "SUPERÁVIT" if saldo_neto >= 0 else "DÉFICIT"],
        ["CRÉDITOS PENDIENTES POR COBRAR HASTA LA FECHA", f"S/. {tot_cred_pend:,.2f}", "EN CARTERA"]
    ]
    t_res = Table(resumen, colWidths=[280, 130, 130])
    t_res.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#FEF08A")),
        ('FONTNAME', (0,4), (-1,4), 'Helvetica-Bold'),
        ('BACKGROUND', (0,5), (-1,5), colors.HexColor("#FEE2E2")),
        ('FONTNAME', (0,5), (-1,5), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 5)
    ]))
    elem.extend([t_res, Spacer(1, 15)])

    filas_movs = [["FECHA", "TIPO", "CONCEPTO", "CONDICIÓN", "MONTO"]]
    for _, r in df_liq.iterrows():
        filas_movs.append([
            str(r["fecha"]), str(r["tipo"]), str(r["concepto"])[:35],
            "Contado" if r["condicion"] == "Contado" else f"Crédito ({r['cliente_deudor']})",
            f"S/. {r['monto']:,.2f}"
        ])
    t_movs = Table(filas_movs, colWidths=[65, 55, 230, 110, 80])
    t_movs.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F8FAFC")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (4,1), (4,-1), 'RIGHT'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('PADDING', (0,0), (-1,-1), 3)
    ]))
    elem.extend([t_movs, Spacer(1, 35)])

    t_firmas = Table([
        ["____________________________", "____________________________"],
        ["TESORERÍA GENERAL", f"RESPONSABLE ({resp_act})"]
    ], colWidths=[270, 270])
    t_firmas.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elem.append(t_firmas)

    doc.build(elem)
    return buf.getvalue()

def generar_pdf_creditos_pendientes(nom_act, df_creditos, total_pendiente):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=32, bottomMargin=32)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    t_head = Table([[
        Paragraph(f"<b>IGLESIA EVANGÉLICA NAZARETH</b><br/><font size=8>REPORTE DE CRÉDITOS Y DEUDAS POR COBRAR</font>", ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10, textColor=c_prim)),
        Paragraph(f"<b>ACTIVIDAD: {nom_act}</b><br/><font size=8>Fecha de Emisión: {date.today().strftime('%d/%m/%Y')}</font>", ParagraphStyle('H2', fontName='Helvetica', fontSize=8, alignment=2))
    ]], colWidths=[330, 210])
    elem.extend([t_head, Spacer(1, 12)])

    filas_cp = [["N°", "FECHA DEUDA", "DEUDOR / RESPONSABLE", "CONCEPTO / DETALLE", "MONTO ADEUDADO"]]
    idx = 1
    for _, r in df_creditos.iterrows():
        filas_cp.append([
            str(idx),
            str(r["fecha"]),
            str(r["cliente_deudor"])[:30],
            str(r["concepto"])[:40],
            f"S/. {r['monto']:,.2f}"
        ])
        idx += 1

    filas_cp.append(["", "", "", "TOTAL PENDIENTE POR COBRAR:", f"S/. {total_pendiente:,.2f}"])

    t_tabla = Table(filas_cp, colWidths=[30, 80, 180, 150, 100])
    t_tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (0,-2), 'CENTER'),
        ('ALIGN', (1,1), (1,-2), 'CENTER'),
        ('ALIGN', (4,1), (4,-1), 'RIGHT'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FEF08A")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elem.extend([t_tabla, Spacer(1, 35)])

    t_firmas = Table([
        ["____________________________", "____________________________"],
        ["CONTROL DE COBRANZAS", "TESORERÍA GENERAL"]
    ], colWidths=[270, 270])
    t_firmas.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elem.append(t_firmas)

    doc.build(elem)
    return buf.getvalue()

if df_act.empty:
    st.info("No hay actividades registradas. Cree una a continuación:")
    with st.form("form_nueva_act_init"):
        nom = st.text_input("Nombre de la Actividad:", placeholder="Ej. POLLADA PRO-TEMPLO")
        fec = st.date_input("Fecha:", value=date.today())
        df_r = core.read_db("SELECT nombre FROM responsables_catalogo")
        resp = st.selectbox("Responsable:", df_r["nombre"].tolist() if not df_r.empty else ["Encargado"])
        desc = st.text_input("Objetivo / Detalle:")
        if st.form_submit_button("Crear Actividad"):
            if nom.strip():
                core.query_db("INSERT INTO actividades (nombre, fecha, responsable, descripcion, ultima_fecha_corte) VALUES (?, ?, ?, ?, '')",
                              (nom.strip(), str(fec), resp, desc.strip()))
                st.toast("✅ Actividad creada.")
                st.rerun()
else:
    dict_act = dict(zip(df_act["nombre"] + " (" + df_act["fecha"] + ")", df_act["id"]))
    act_sel = st.selectbox("🎯 Seleccione Actividad:", list(dict_act.keys()))
    id_act = dict_act[act_sel]
    datos_act = df_act[df_act["id"] == id_act].iloc[0]

    opcion = st.radio("Sección:", ["Resumen Financiero", "Registrar Movimiento", "Créditos por Cobrar", "Corte y Acta PDF", "Administrar"], horizontal=True)
    df_mov_act = core.read_db("SELECT * FROM actividad_movimientos WHERE id_actividad=? ORDER BY id DESC", (id_act,))

    tot_cont = df_mov_act[(df_mov_act["tipo"] == "Ingreso") & (df_mov_act["condicion"] == "Contado")]["monto"].sum() if not df_mov_act.empty else 0.0
    tot_cred_cob = df_mov_act[(df_mov_act["tipo"] == "Ingreso") & (df_mov_act["condicion"] == "Credito") & (df_mov_act["estado_cobro"] == "Cobrado")]["monto"].sum() if not df_mov_act.empty else 0.0
    tot_cred_pend = df_mov_act[(df_mov_act["tipo"] == "Ingreso") & (df_mov_act["condicion"] == "Credito") & (df_mov_act["estado_cobro"] == "Pendiente")]["monto"].sum() if not df_mov_act.empty else 0.0
    tot_egr = df_mov_act[df_mov_act["tipo"] == "Egreso"]["monto"].sum() if not df_mov_act.empty else 0.0
    saldo_disp = (tot_cont + tot_cred_cob) - tot_egr

    if opcion == "Resumen Financiero":
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("1. Ventas Contado", f"S/. {tot_cont:,.2f}")
        c2.metric("2. Créditos Cobrados", f"S/. {tot_cred_cob:,.2f}")
        c3.metric("3. Créditos Pendientes", f"S/. {tot_cred_pend:,.2f}", delta="Por cobrar", delta_color="inverse")
        c4.metric("4. Gastos Insumos", f"S/. {tot_egr:,.2f}", delta=f"-S/. {tot_egr:,.2f}", delta_color="inverse")
        st.metric("🏆 Saldo Líquido Disponible en Mano", f"S/. {saldo_disp:,.2f}")

        if not df_mov_act.empty:
            st.dataframe(df_mov_act[["fecha", "tipo", "concepto", "monto", "condicion", "cliente_deudor", "estado_cobro"]], use_container_width=True)

    elif opcion == "Registrar Movimiento":
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            t_mov = st.radio("Tipo de Transacción:", ["Ingreso (Venta)", "Egreso (Gasto Insumos)"])
        es_ing = "Ingreso" in t_mov
        with c_t2:
            cond = st.radio("Condición:", ["Contado", "Crédito (Por Cobrar)"]) if es_ing else "Contado"
        es_cred = es_ing and ("Crédito" in cond)

        with st.form("form_reg_m_act", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                fec_m = st.date_input("Fecha:", value=date.today())
                concepto = st.text_input("Concepto / Plato / Insumo:", placeholder="Ej. 10 Polladas, 1 Balón de Gas")
                monto = st.number_input("Monto (S/.):", min_value=0.01, step=5.0, format="%.2f")
            with c2:
                deudor = st.text_input("Nombre de quien debe (A Crédito):") if es_cred else ""
                df_f = core.read_db("SELECT nombre FROM fondos_catalogo")
                fondo = st.selectbox("Fondo:", df_f["nombre"].tolist() if not df_f.empty else ["General"])

            if st.form_submit_button("Guardar Transacción"):
                if not concepto.strip():
                    st.error("Ingrese el concepto.")
                elif es_cred and not deudor.strip():
                    st.error("Debe ingresar el nombre del deudor.")
                else:
                    tipo_cl = "Ingreso" if es_ing else "Egreso"
                    cond_cl = "Credito" if es_cred else "Contado"
                    est_cob = "Pendiente" if es_cred else "Cobrado"
                    core.query_db("""
                        INSERT INTO actividad_movimientos (id_actividad, fecha, tipo, concepto, monto, condicion, cliente_deudor, estado_cobro, medio, fondo_destino, liquidado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Efectivo', ?, 0)
                    """, (id_act, str(fec_m), tipo_cl, concepto.strip(), monto, cond_cl, deudor.strip(), est_cob, fondo))
                    st.toast("✅ Transacción registrada.")
                    st.rerun()

    elif opcion == "Créditos por Cobrar":
        df_cp = df_mov_act[(df_mov_act["tipo"] == "Ingreso") & (df_mov_act["condicion"] == "Credito") & (df_mov_act["estado_cobro"] == "Pendiente")] if not df_mov_act.empty else df_mov_act
        if df_cp.empty:
            st.success("🎉 No hay créditos pendientes.")
        else:
            col_tot, col_pdf = st.columns([6, 3])
            with col_tot:
                st.warning(f"Total pendiente por cobrar: **S/. {df_cp['monto'].sum():,.2f}** ({len(df_cp)} deudas pendientes)")
            with col_pdf:
                pdf_cred_bytes = generar_pdf_creditos_pendientes(act_sel, df_cp, df_cp['monto'].sum())
                st.download_button(
                    "📄 Descargar Cuadro de Deudas en PDF",
                    data=pdf_cred_bytes,
                    file_name=f"Creditos_Pendientes_{id_act}.pdf",
                    mime="application/pdf",
                    type="primary"
                )

            st.markdown("---")
            for _, r in df_cp.iterrows():
                with st.container():
                    col_a, col_b = st.columns([6, 2])
                    with col_a:
                        st.markdown(f"👤 **{r['cliente_deudor']}** — Debe **S/. {r['monto']:,.2f}** (*{r['concepto']}*) | 📅 Fecha deuda: `{r['fecha']}`")
                    with col_b:
                        if st.button("✅ Marcar Pagado", key=f"cob_{r['id']}", type="primary"):
                            core.query_db("UPDATE actividad_movimientos SET estado_cobro='Cobrado' WHERE id=?", (r["id"],))
                            st.toast("✅ Crédito cobrado.")
                            st.rerun()
                st.divider()

    elif opcion == "Corte y Acta PDF":
        df_liq = df_mov_act[(df_mov_act["condicion"] == "Contado") | (df_mov_act["estado_cobro"] == "Cobrado") | (df_mov_act["tipo"] == "Egreso")] if not df_mov_act.empty else df_mov_act
        hoy_str = str(date.today())

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.info(f"💵 Saldo líquido en efectivo a transferir a Tesorería: **S/. {saldo_disp:,.2f}**")
        with col_m2:
            st.warning(f"⏳ Créditos que quedan pendientes de cobro hasta la fecha: **S/. {tot_cred_pend:,.2f}**")

        df_f = core.read_db("SELECT nombre FROM fondos_catalogo")
        fondos = df_f["nombre"].tolist() if not df_f.empty else ["General"]
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            fondo_des = st.selectbox("Fondo de Tesorería:", fondos)
        with c_f2:
            medio_des = st.selectbox("Medio de Entrega:", core.MEDIOS)

        if st.button("🚀 Ejecutar Corte y Limpiar Registros", type="primary"):
            if df_liq.empty:
                st.warning("No hay operaciones de contado para liquidar.")
            else:
                cod_corte = f"CORTE-{id_act}-{date.today().strftime('%Y%m%d%H%M')}"
                tipo_as = "Ingreso" if saldo_disp >= 0 else "Egreso"
                
                core.query_db("""
                    INSERT INTO movimientos (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito)
                    VALUES (?, ?, 'Actividades Pro-Templo', 'Liquidación Neta Actividad', ?, ?, ?, ?, ?, ?, '', 'Cobrado')
                """, (hoy_str, tipo_as, fondo_des, abs(saldo_disp), medio_des, cod_corte, f"Liquidación neta: {act_sel}", datos_act["responsable"]))

                pdf_bytes = generar_pdf_acta(act_sel, hoy_str, cod_corte, df_liq, tot_cont, tot_cred_cob, tot_egr, saldo_disp, tot_cred_pend, datos_act["responsable"], fondo_des)

                core.query_db("DELETE FROM actividad_movimientos WHERE id_actividad=? AND (condicion='Contado' OR estado_cobro='Cobrado' OR tipo='Egreso')", (id_act,))
                core.query_db("UPDATE actividades SET ultima_fecha_corte=? WHERE id=?", (hoy_str, id_act))
                
                st.session_state["pdf_corte"] = pdf_bytes
                st.session_state["cod_corte"] = cod_corte
                st.success("¡Corte completado y transferido a Tesorería!")
                st.rerun()

        if "pdf_corte" in st.session_state:
            st.download_button(f"🔴 Descargar Acta PDF ({st.session_state.get('cod_corte', '')})", st.session_state["pdf_corte"], "Acta_Corte.pdf", "application/pdf")

    elif opcion == "Administrar":
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            st.markdown("##### ➕ Crear Otra Actividad:")
            with st.form("form_nueva_act"):
                nom = st.text_input("Nombre:")
                fec = st.date_input("Fecha:", value=date.today())
                df_r = core.read_db("SELECT nombre FROM responsables_catalogo")
                resp = st.selectbox("Responsable:", df_r["nombre"].tolist() if not df_r.empty else ["Encargado"])
                desc = st.text_input("Descripción:")
                if st.form_submit_button("Crear"):
                    if nom.strip():
                        core.query_db("INSERT INTO actividades (nombre, fecha, responsable, descripcion, ultima_fecha_corte) VALUES (?, ?, ?, ?, '')", (nom.strip(), str(fec), resp, desc.strip()))
                        st.toast("✅ Creada.")
                        st.rerun()
        with c_a2:
            st.markdown("##### 🗑️ Eliminar Actividad:")
            st.warning(f"¿Eliminar actividad **{act_sel}**?")
            if st.button("Eliminar Definitivamente", type="primary"):
                core.query_db("DELETE FROM actividad_movimientos WHERE id_actividad=?", (id_act,))
                core.query_db("DELETE FROM actividades WHERE id=?", (id_act,))
                st.toast("🗑️ Actividad eliminada.")
                st.rerun()
