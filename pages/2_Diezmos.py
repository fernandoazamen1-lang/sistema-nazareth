import streamlit as st
import core
import reportlab
import os, io, urllib.parse, calendar
from datetime import date, datetime
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

# 1. Configuración de página (primera orden de Streamlit)
st.set_page_config(
    page_title="Módulo de Diezmos", 
    page_icon="📖", 
    layout="wide"
)

# 2. Verificación de permisos y estilos visuales
core.verificar_acceso_pagina("Diezmos")
core.aplicar_estilos_base()

# Asegurar tablas requeridas y columnas en public (PostgreSQL)
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.movimientos (
                    id SERIAL PRIMARY KEY,
                    fecha DATE NOT NULL,
                    tipo TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    subcategoria TEXT DEFAULT '',
                    fondo TEXT DEFAULT 'General',
                    monto NUMERIC(12, 2) NOT NULL,
                    medio TEXT DEFAULT 'Efectivo',
                    comprobante TEXT DEFAULT '',
                    detalle TEXT DEFAULT '',
                    responsable TEXT DEFAULT '',
                    archivo_foto TEXT DEFAULT '',
                    estado_credito TEXT DEFAULT 'Cobrado',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS public.diezmos (
                    id SERIAL PRIMARY KEY,
                    fecha DATE NOT NULL,
                    id_miembro TEXT NOT NULL,
                    nombre_miembro TEXT NOT NULL,
                    mes TEXT NOT NULL,
                    medio TEXT DEFAULT 'Efectivo',
                    monto NUMERIC(12, 2) NOT NULL,
                    detalle TEXT DEFAULT '',
                    codigo_comprobante TEXT DEFAULT '',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE public.diezmos ADD COLUMN IF NOT EXISTS codigo_comprobante TEXT DEFAULT '';
            """)
        conn.commit()
except Exception:
    pass

# Catálogos base
df_m = core.read_db("SELECT id_miembro, nombre, telefono FROM public.miembros ORDER BY nombre ASC")
d_miembros = dict(zip(df_m["nombre"], df_m["id_miembro"])) if not df_m.empty else {}
d_telefonos = dict(zip(df_m["nombre"], df_m["telefono"])) if not df_m.empty else {}

df_t = core.read_db("SELECT descripcion FROM public.auditoria WHERE modulo='Config_Tesorero' ORDER BY id DESC LIMIT 1")
tesorero_def = df_t.iloc[0]["descripcion"] if not df_t.empty else "Tesorero General"

# ==============================================================================
# MOTOR TIPOGRÁFICO UNICODE GARANTIZADO (Ñ, TILDES, SIGNOS)
# ==============================================================================
def get_font(size, bold=False):
    """
    Carga la fuente TrueType 'Bitstream Vera' incluida directamente en ReportLab.
    Garantiza soporte completo para Ñ, tildes y signos sin depender de descargas externas.
    """
    try:
        dir_rl = os.path.dirname(reportlab.__file__)
        archivo_fuente = "VeraBd.ttf" if bold else "Vera.ttf"
        ruta_fuente = os.path.join(dir_rl, "fonts", archivo_fuente)
        if os.path.exists(ruta_fuente):
            return ImageFont.truetype(ruta_fuente, int(size))
    except Exception:
        pass

    rutas_alt = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for r in rutas_alt:
        if os.path.exists(r):
            try:
                return ImageFont.truetype(r, int(size))
            except Exception:
                pass

    try:
        return ImageFont.load_default(size=int(size))
    except Exception:
        return ImageFont.load_default()

def draw_center(draw, y, text, font, fill, width=800):
    try:
        bb = draw.textbbox((0, 0), str(text), font=font)
        x = (width - (bb[2] - bb[0])) // 2
    except Exception:
        x = (width - len(str(text)) * 10) // 2
    draw.text((int(x), int(y)), str(text), font=font, fill=fill)

def render_boucher_png(serie, fecha, nombre, mes, medio, monto, detalle, tesorero):
    w, h = 800, 1140
    img = Image.new("RGB", (w, h), "#F8FAFC")
    dr = ImageDraw.Draw(img)

    # 1. Bordes exteriores
    dr.rounded_rectangle([(16, 16), (w - 16, h - 16)], 20, fill="#FFFFFF", outline="#1E3A8A", width=3)
    dr.rounded_rectangle([(24, 24), (w - 24, h - 24)], 16, outline="#CA8A04", width=1)

    # 2. Encabezado institucional azul
    dr.rounded_rectangle([(32, 32), (w - 32, 165)], 14, fill="#1E3A8A")
    draw_center(dr, 46, 'IGLESIA EVANGÉLICA "NAZARETH"', get_font(23, True), "#FFFFFF", w)
    draw_center(dr, 85, "ASAMBLEAS DE DIOS DEL PERÚ  •  DEPARTAMENTO DE TESORERÍA", get_font(13, True), "#93C5FD", w)
    draw_center(dr, 120, f"CONSTANCIA DE DIEZMO:  {serie}", get_font(17, True), "#FDE047", w)

    # 3. Datos del aportante
    dr.rounded_rectangle([(42, 185), (w - 42, 475)], 12, fill="#FFFFFF", outline="#E2E8F0", width=1)
    rows = [
        ("Hermano(a) Aportante:", str(nombre).strip().upper()[:36]),
        ("Fecha de Recepción:", str(fecha)),
        ("Mes Correspondiente:", str(mes).upper()),
        ("Medio de Entrega:", str(medio)),
        ("Detalle / Observación:", str(detalle).strip()[:40] if detalle else "Fidelidad y servicio al Señor")
    ]
    y = 205
    for lbl, val in rows:
        dr.text((65, y), lbl, font=get_font(15), fill="#64748B")
        dr.text((310, y), val, font=get_font(16, True), fill="#0F172A")
        dr.line([(65, y + 36), (w - 65, y + 36)], fill="#F1F5F9", width=1)
        y += 52

    # 4. Recuadro del monto
    dr.rounded_rectangle([(42, 495), (w - 42, 615)], 14, fill="#FEF9C3", outline="#EAB308", width=2)
    draw_center(dr, 510, "TOTAL APORTE ENTREGADO", get_font(15, True), "#854D0E", w)
    draw_center(dr, 542, f"S/. {float(monto):,.2f}", get_font(38, True), "#1E3A8A", w)

    # 5. Gratitud pastoral
    dr.rounded_rectangle([(42, 635), (w - 42, 775)], 12, fill="#F0FDF4", outline="#86EFAC", width=1)
    draw_center(dr, 650, "❤️  PALABRAS DE GRATITUD PASTORAL", get_font(15, True), "#166534", w)
    draw_center(dr, 684, "¡Muchas gracias por su fidelidad, amor y compromiso con la obra de Dios!", get_font(14), "#1F2937", w)
    draw_center(dr, 712, "Oramos para que el Señor derrame abundantes bendiciones sobre su vida,", get_font(14), "#1F2937", w)
    draw_center(dr, 738, "multiplique su siembra y guarde con paz y provisión a toda su amada familia.", get_font(14), "#1F2937", w)

    # 6. Versículo bíblico
    dr.rounded_rectangle([(42, 795), (w - 42, 945)], 12, fill="#F8FAFC", outline="#E2E8F0", width=1)
    draw_center(dr, 810, "PALABRA DE DIOS SOBRE EL DAR:", get_font(14, True), "#1E40AF", w)
    draw_center(dr, 842, "«Cada uno dé como propuso en su corazón: no con tristeza,", get_font(14), "#334155", w)
    draw_center(dr, 870, "ni por necesidad, porque Dios ama al dador alegre.»", get_font(14), "#334155", w)
    draw_center(dr, 904, "— 2 Corintios 9:7 —", get_font(14, True), "#047857", w)

    # 7. Certificación y Tesorería
    dr.rounded_rectangle([(42, 965), (w - 42, 1105)], 12, fill="#F1F5F9", outline="#CBD5E1", width=1)
    draw_center(dr, 980, "RECEPCIONADO Y CERTIFICADO FORMALMENTE POR:", get_font(13), "#64748B", w)
    draw_center(dr, 1012, str(tesorero).upper(), get_font(16, True), "#0F172A", w)
    draw_center(dr, 1048, "Tesorero(a) General  •  Iglesia Evangélica \"Nazareth\"", get_font(13), "#475569", w)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

def get_diezmos():
    df = core.read_db("SELECT * FROM public.diezmos ORDER BY id DESC")
    if not df.empty:
        df["serie_constancia"] = df.apply(
            lambda r: r["codigo_comprobante"] if r.get("codigo_comprobante") else f"D - {int(r['id']):05d}", axis=1
        )
    return df

def proximo_codigo():
    df_u = core.read_db("SELECT codigo_comprobante, id FROM public.diezmos ORDER BY id DESC LIMIT 1")
    if df_u.empty:
        return "D - 00001"
    cod = str(df_u.iloc[0].get("codigo_comprobante", ""))
    if "D -" in cod:
        try:
            return f"D - {int(cod.replace('D -', '').strip()) + 1:05d}"
        except Exception:
            pass
    cant = core.read_db("SELECT COUNT(*) as t FROM public.diezmos").iloc[0]["t"]
    return f"D - {int(cant) + 1:05d}"

# ==============================================================================
# FLUJO DE ENVÍO Y DESCARGA DE VOUCHERS
# ==============================================================================
def panel_whatsapp_descarga(d):
    img_b = render_boucher_png(d["serie"], d["fecha"], d["nombre"], d["mes"], d["medio"], d["monto"], d["detalle"], d["tesorero"])
    
    col_img, col_ws = st.columns([1, 1])
    with col_img:
        st.image(img_b, width=370, caption=f"Constancia {d['serie']}")
        
    with col_ws:
        st.markdown("#### 📤 Envío Rápido en 2 Clics")
        st.caption("Sigue estos 2 sencillos pasos para enviar el voucher digital:")
        
        st.markdown("**Paso 1:** Descarga la constancia en tu dispositivo.")
        nombre_archivo = f"Boucher_{d['serie'].replace(' ','')}_{str(d['nombre']).replace(' ', '_')}.png"
        st.download_button(
            label="📥 1. Descargar Voucher Oficial (PNG HD)",
            data=img_b,
            file_name=nombre_archivo,
            mime="image/png",
            use_container_width=True,
            type="primary"
        )
        
        st.markdown("---")
        
        st.markdown("**Paso 2:** Abre WhatsApp y adjunta la imagen con el clip 📎.")
        t_raw = "".join(filter(str.isdigit, str(d.get("telefono", ""))))
        tel = st.text_input("Número de celular (9 dígitos):", value=t_raw, placeholder="Ej. 987654321")
        
        msg = (
            f"⛪ *Iglesia Evangélica \"Nazareth\"*\n"
            f"Paz del Señor, estimado(a) hermano(a) *{d['nombre']}*.\n\n"
            f"Se confirma la recepción y registro de su aporte:\n"
            f"📌 *Constancia:* {d['serie']}\n"
            f"📅 *Fecha:* {d['fecha']}\n"
            f"🗓️ *Periodo/Mes:* {d['mes']}\n"
            f"💳 *Medio:* {d['medio']}\n"
            f"💰 *Monto:* S/. {float(d['monto']):,.2f}\n"
            f"✍️ *Receptor:* {d['tesorero']}\n\n"
            f"🖼️ _(Se adjunta la imagen de su voucher oficial formalmente certificado)._\n\n"
            f"¡Muchas gracias por su fidelidad! Que el Señor continúe bendiciendo abundantemente su vida y hogar.\n\n"
            f"_«Cada uno dé como propuso en su corazón... porque Dios ama al dador alegre.» (2 Corintios 9:7)_"
        )
        
        if tel.strip():
            num_clean = tel.strip()
            num = num_clean if num_clean.startswith("51") else f"51{num_clean}"
            link = f"https://wa.me/{num}?text={urllib.parse.quote(msg)}"
        else:
            link = f"https://api.whatsapp.com/send?text={urllib.parse.quote(msg)}"
            
        st.markdown(
            f'''<a href="{link}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#25D366;color:white;padding:12px;border-radius:10px;text-align:center;font-weight:700;font-size:15px;box-shadow:0 4px 10px rgba(37,211,102,0.3);margin-top:5px;">
                    💬 2. Abrir WhatsApp con Mensaje Listo
                </div>
            </a>''',
            unsafe_allow_html=True
        )

def generar_pdf_reporte_mensual(df_mes_rep, anio_rep, mes_rep, tot_m, efe_m, ban_m):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25)
    elem = []
    c_prim = colors.HexColor("#1E3A8A")
    c_borde = colors.HexColor("#CBD5E1")

    t_head = Table([[
        Paragraph(
            "<b>IGLESIA EVANGÉLICA \"NAZARETH\" — ASAMBLEAS DE DIOS DEL PERÚ</b><br/>"
            f"<font size=9 color='#1E3A8A'>REPORTE MENSUAL DETALLADO DE DIEZMOS — {mes_rep.upper()} {anio_rep}</font>",
            ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=11, textColor=c_prim)
        ),
        Paragraph(
            f"<b>Emisión:</b> {date.today().strftime('%d/%m/%Y')}<br/>"
            f"<font size=8>Registros: {len(df_mes_rep)}</font>",
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
        ["TOTAL GENERAL INGRESADO", "TOTAL EN EFECTIVO", "TOTAL EN BANCO / TRANSFERENCIA"],
        [f"S/. {tot_m:,.2f}", f"S/. {efe_m:,.2f}", f"S/. {ban_m:,.2f}"]
    ], colWidths=[246, 246, 248])
    t_resumen.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,1), 11),
        ('TEXTCOLOR', (0,1), (-1,1), c_prim),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elem.extend([t_resumen, Spacer(1, 12)])

    filas = [["N°", "CONSTANCIA", "FECHA", "DNI", "HERMANO(A) APORTANTE", "MES", "MEDIO", "MONTO"]]
    idx = 1
    for _, r in df_mes_rep.iterrows():
        filas.append([
            str(idx),
            str(r.get("serie_constancia", "")),
            str(r.get("fecha", "")),
            str(r.get("id_miembro", "")),
            str(r.get("nombre_miembro", ""))[:32],
            str(r.get("mes", "")),
            str(r.get("medio", "")),
            f"S/. {float(r.get('monto', 0)):,.2f}"
        ])
        idx += 1

    filas.append(["", "", "", "", "TOTAL ACUMULADO DEL MES:", "", "", f"S/. {tot_m:,.2f}"])

    t_tabla = Table(filas, colWidths=[25, 65, 65, 65, 250, 75, 105, 90])
    t_tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-2), 0.5, c_borde),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('ALIGN', (0,0), (3,-1), 'CENTER'),
        ('ALIGN', (5,0), (6,-1), 'CENTER'),
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

# --- MENÚ PRINCIPAL ---
st.subheader("📖 Módulo de Diezmos y Emisión de Constancias")
opcion = st.radio(
    "Acción:", 
    ["Registrar Nuevo Diezmo", "Ver Registros por Mes", "Ficha Individual Oficial", "⚙️ Modificar o Eliminar"], 
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# 1. REGISTRAR NUEVO DIEZMO
# ==============================================================================
if opcion == "Registrar Nuevo Diezmo":
    if not d_miembros:
        st.warning("⚠️ Registre miembros primero en el Padrón.")
    else:
        sig_cod = proximo_codigo()
        st.info(f"🔖 **Próximo Boucher por emitir:** `{sig_cod}`")
        anio, mes_s, num_m, f_def = core.selector_periodo("dz_reg")
        with st.form("form_reg_dz"):
            c1, c2 = st.columns(2)
            with c1:
                f_d = st.date_input("Fecha de Abono:", value=f_def)
                nom = st.selectbox("Hermano(a):", list(d_miembros.keys()))
                monto = st.number_input("Monto (S/.):", min_value=0.5, step=10.0, format="%.2f")
            with c2:
                mes_c = st.selectbox("Mes Correspondiente:", core.MESES, index=num_m - 1)
                medio = st.selectbox("Medio de Pago:", core.MEDIOS)
                det = st.text_input("Observación / Detalle:", placeholder="Ej. Culto Dominical")
            tes = st.text_input("Tesorero(a) Receptor(a):", value=tesorero_def)
            if st.form_submit_button(f"💾 Registrar y Emitir ({sig_cod})", type="primary"):
                if tes.strip() and tes.strip() != tesorero_def:
                    core.query_db(
                        "INSERT INTO public.auditoria (fecha_hora, modulo, accion, descripcion) VALUES (?, 'Config_Tesorero', 'Actualizar', ?)",
                        (str(date.today()), tes.strip())
                    )
                core.query_db(
                    "INSERT INTO public.diezmos (fecha, id_miembro, nombre_miembro, mes, medio, monto, detalle, codigo_comprobante) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(f_d), d_miembros[nom], nom, mes_c, medio, round(float(monto), 2), det.strip(), sig_cod)
                )
                core.registrar_log("Diezmos", "Registro", f"Diezmo {nom} S/. {monto:,.2f} ({sig_cod})")
                st.session_state["ultimo_dz"] = {
                    "serie": sig_cod, "fecha": str(f_d), "nombre": nom, "mes": mes_c,
                    "medio": medio, "monto": monto, "detalle": det.strip(), "tesorero": tes.strip(),
                    "telefono": d_telefonos.get(nom, "")
                }
                st.rerun()

        if "ultimo_dz" in st.session_state:
            st.success(f"🎉 Constancia N° **{st.session_state['ultimo_dz']['serie']}** emitida con éxito.")
            panel_whatsapp_descarga(st.session_state["ultimo_dz"])

# ==============================================================================
# 2. VER REGISTROS POR MES
# ==============================================================================
elif opcion == "Ver Registros por Mes":
    st.markdown("#### 🗓️ Control Mensual por Fecha Real de Abono")
    c1, c2, c3 = st.columns(3)
    with c1: anio_s = st.selectbox("Año de Abono:", list(range(date.today().year - 4, date.today().year + 5)), index=4)
    with c2: mes_s = st.selectbox("Mes de Abono:", core.MESES, index=date.today().month - 1)
    with c3: med_s = st.selectbox("Medio:", ["Todos", "Efectivo", "Depósito / Transferencia"])

    df_all = get_diezmos()
    if not df_all.empty:
        df_all["dt"] = pd.to_datetime(df_all["fecha"], errors="coerce")
        df_f = df_all[(df_all["dt"].dt.year == anio_s) & (df_all["dt"].dt.month == core.MESES_NUM[mes_s])].copy()
        if med_s != "Todos":
            df_f = df_f[df_f["medio"] == med_s]

        tot = float(df_f["monto"].sum()) if not df_f.empty else 0.0
        efe = float(df_f[df_f["medio"] == "Efectivo"]["monto"].sum()) if not df_f.empty else 0.0
        ban = float(df_f[df_f["medio"] != "Efectivo"]["monto"].sum()) if not df_f.empty else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Ingresado", f"S/. {tot:,.2f}")
        m2.metric("En Efectivo", f"S/. {efe:,.2f}")
        m3.metric("En Banco", f"S/. {ban:,.2f}")

        if not df_f.empty:
            pdf_mes_bytes = generar_pdf_reporte_mensual(df_f, anio_s, mes_s, tot, efe, ban)
            col_b_pdf, _ = st.columns([3, 4])
            with col_b_pdf:
                st.download_button(
                    label=f"📄 Descargar Reporte Mensual en PDF ({mes_s} {anio_s})",
                    data=pdf_mes_bytes,
                    file_name=f"Reporte_Diezmos_{mes_s}_{anio_s}.pdf",
                    mime="application/pdf",
                    type="primary"
                )

        map_c = {
            "serie_constancia": "N° Constancia", "fecha": "F. Abono", "id_miembro": "DNI",
            "nombre_miembro": "Hermano(a)", "mes": "Cuota/Mes", "medio": "Medio",
            "monto": "Importe", "detalle": "Detalle"
        }
        cols_mostrar = [c for c in map_c.keys() if c in df_f.columns]
        st.dataframe(
            df_f[cols_mostrar].rename(columns=map_c).style.format({"Importe": "S/. {:,.2f}"}),
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        u_dia = calendar.monthrange(anio_s, core.MESES_NUM[mes_s])[1]
        f_fin = f"{anio_s}-{core.MESES_NUM[mes_s]:02d}-{u_dia:02d}"
        c_efe = f"ASIENTO-DZ-EFE-{anio_s}-{core.MESES_NUM[mes_s]:02d}"
        c_ban = f"ASIENTO-DZ-BAN-{anio_s}-{core.MESES_NUM[mes_s]:02d}"
        prev = not core.read_db("SELECT id FROM public.movimientos WHERE comprobante IN (?, ?)", (c_efe, c_ban)).empty

        if st.button(
            "🔄 Actualizar Asientos en Tesorería" if prev else f"🚀 Registrar los 2 Asientos en Tesorería ({f_fin})",
            type="primary" if not prev else "secondary"
        ):
            try:
                core.query_db("DELETE FROM public.movimientos WHERE comprobante IN (?, ?)", (c_efe, c_ban))
                if efe > 0:
                    core.query_db(
                        "INSERT INTO public.movimientos (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito) VALUES (?, 'Ingreso', 'Diezmos Consolidado', 'Diezmos en Efectivo', 'General', ?, 'Efectivo', ?, ?, 'Tesorería', '', 'Cobrado')",
                        (f_fin, round(float(efe), 2), c_efe, f"Diezmos efectivo {mes_s} {anio_s}")
                    )
                if ban > 0:
                    core.query_db(
                        "INSERT INTO public.movimientos (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito) VALUES (?, 'Ingreso', 'Diezmos Consolidado', 'Diezmos en Banco / Transferencia', 'General', ?, 'Depósito / Transferencia', ?, ?, 'Tesorería', '', 'Cobrado')",
                        (f_fin, round(float(ban), 2), c_ban, f"Diezmos banco {mes_s} {anio_s}")
                    )
                core.registrar_log("Diezmos", "Tesorería", f"Asentados diezmos de {mes_s} {anio_s}")
                st.toast("✅ Asientos asentados en Tesorería con éxito.")
                st.rerun()
            except Exception as err:
                st.error(f"Error al registrar asientos: {err}")

# ==============================================================================
# 3. FICHA INDIVIDUAL OFICIAL
# ==============================================================================
elif opcion == "Ficha Individual Oficial":
    if d_miembros:
        c1, c2 = st.columns([3, 2])
        with c1: hno = st.selectbox("HERMANO:", list(d_miembros.keys()))
        with c2: st.text_input("DNI:", value=d_miembros[hno], disabled=True)
        r1, r2, r3 = st.columns(3)
        with r1: f_ini = st.date_input("Desde:", value=date(date.today().year, 1, 1))
        with r2: f_fin = st.date_input("Hasta:", value=date.today())
        with r3: f_imp = st.date_input("Fecha Emisión:", value=date.today())

        df_i = core.read_db(
            "SELECT fecha, monto, medio, mes, detalle FROM public.diezmos WHERE nombre_miembro=? AND date(fecha) >= ? AND date(fecha) <= ? ORDER BY date(fecha) ASC, id ASC",
            (hno, str(f_ini), str(f_fin))
        )
        acum, filas_tab = 0.0, []
        for i, r in df_i.iterrows():
            acum += float(r["monto"])
            filas_tab.append({"n": i + 1, "f": r["fecha"], "a": f"S/. {r['monto']:,.2f}", "m": r["medio"], "s": f"S/. {acum:,.2f}", "mes": r["mes"]})

        trs = "".join([
            f"<tr><td style='border:1px solid #000;padding:3px;'>{x['n']}</td><td style='border:1px solid #000;padding:3px;'>{x['f']}</td><td style='border:1px solid #000;padding:3px;'>{x['a']}</td><td style='border:1px solid #000;padding:3px;'>{x['m']}</td><td style='border:1px solid #000;padding:3px;'>{x['s']}</td><td style='border:1px solid #000;padding:3px;'>{x['mes']}</td></tr>"
            for x in filas_tab
        ])
        for ex in range(len(filas_tab) + 1, max(13, len(filas_tab) + 1)):
            trs += f"<tr><td style='border:1px solid #000;padding:3px;'>{ex}</td><td style='border:1px solid #000;'></td><td style='border:1px solid #000;'></td><td style='border:1px solid #000;'></td><td style='border:1px solid #000;'></td><td style='border:1px solid #000;'></td></tr>"

        st.markdown(f"""
        <div style="background:white;border:2px solid #000;padding:20px;color:black;font-family:Arial;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div style="background:#FFEE00;font-weight:bold;padding:5px 12px;border:1px solid #000;font-size:16px;">REPORTE DIEZMOS - INDIVIDUAL</div>
                <div style="text-align:center;font-weight:bold;font-size:12px;">ASAMBLEAS DE DIOS DEL PERÚ<br>IGLESIA EVANGÉLICA "NAZARETH"</div>
                <div style="border:1px solid #000;text-align:center;"><div style="background:#FFEE00;font-size:10px;padding:2px 10px;border-bottom:1px solid #000;">AÑO</div><div style="font-weight:bold;font-size:11px;">{date.today().year}</div></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;font-weight:bold;margin-bottom:8px;">
                <div>HERMANO: <u>{hno.upper()}</u></div><div>DNI: <u>{d_miembros[hno]}</u></div>
            </div>
            <div style="border:1px solid #000;padding:8px;font-size:10.5px;text-align:justify;margin-bottom:10px;">
                DECLARO HABER RECIBIDO EL PRESENTE INFORME DETALLADO DE MIS APORTES DE DIEZMOS DEL AÑO {date.today().year} HASTA LA FECHA INDICADA. TRAS HABER REVISADO LOS MONTOS Y FECHAS REGISTRADOS, MANIFIESTO MI TOTAL CONFORMIDAD. EN SEÑAL DE ACEPTACIÓN, PROCEDO A ESTAMPAR MI FIRMA.
            </div>
            <table style="width:100%;border-collapse:collapse;text-align:center;font-size:10px;">
                <tr style="background:#F1F5F9;"><th style="border:1px solid #000;">N°</th><th style="border:1px solid #000;">FECHA</th><th style="border:1px solid #000;">APORTE</th><th style="border:1px solid #000;">MEDIO</th><th style="border:1px solid #000;">SUMATORIA</th><th style="border:1px solid #000;">MES</th></tr>
                {trs}
                <tr style="background:#FFEE00;font-weight:bold;"><td colspan="4" style="border:1px solid #000;text-align:right;padding:4px;">TOTAL:</td><td colspan="2" style="border:1px solid #000;padding:4px;">S/. {acum:,.2f}</td></tr>
            </table>
            <div style="text-align:right;font-size:10px;margin-top:8px;"><b>Fecha de Emisión:</b> {f_imp.strftime('%d/%m/%Y')}</div>
            <div style="display:flex;justify-content:space-around;margin-top:25px;text-align:center;font-size:11px;font-weight:bold;">
                <div>__________________________<br>TESORERÍA GENERAL</div><div>__________________________<br>MIEMBRO CONFORME</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        def make_pdf():
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            top = Table([[
                Paragraph("<b>REPORTE DIEZMOS - INDIVIDUAL</b>", ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=12, alignment=1)),
                Paragraph("<b>ASAMBLEAS DE DIOS DEL PERÚ<br/>IGLESIA EVANGÉLICA \"NAZARETH\"</b>", ParagraphStyle('I', fontName='Helvetica-Bold', fontSize=8.5, alignment=1)),
                Table([[Paragraph("<b>AÑO</b>", ParagraphStyle('A1', fontName='Helvetica-Bold', fontSize=8, alignment=1))], [Paragraph(f"<b>{date.today().year}</b>", ParagraphStyle('A2', fontName='Helvetica-Bold', fontSize=8, alignment=1))]], colWidths=[65], style=[('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,0), colors.HexColor("#FFEE00"))])
            ]], colWidths=[240, 235, 65])
            top.setStyle(TableStyle([('BACKGROUND', (0,0), (0,0), colors.HexColor("#FFEE00")), ('BOX', (0,0), (0,0), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 4)]))
            
            id_t = Table([[Paragraph(f"<b>HERMANO:</b> {hno.upper()}", ParagraphStyle('H', fontSize=8.5)), Paragraph(f"<b>DNI:</b> {d_miembros[hno]}", ParagraphStyle('D', fontSize=8.5, alignment=2))]], colWidths=[380, 160])
            decl = Table([[Paragraph(f"DECLARO HABER RECIBIDO EL PRESENTE INFORME DETALLADO DE MIS APORTES DE DIEZMOS DEL AÑO {date.today().year} HASTA LA FECHA INDICADA. TRAS HABER REVISADO LOS MONTOS Y FECHAS, MANIFIESTO TOTAL CONFORMIDAD.", ParagraphStyle('DC', fontSize=7.5, leading=10, alignment=4))]], colWidths=[540], style=[('BOX', (0,0), (-1,-1), 1, colors.black), ('PADDING', (0,0), (-1,-1), 6)])

            grid_d = [["N°", "FECHA", "APORTE", "MEDIO", "SUMATORIA", "MES"]] + [[str(x["n"]), str(x["f"]), x["a"], str(x["m"]), x["s"], str(x["mes"])] for x in filas_tab]
            for ex in range(len(filas_tab) + 1, max(13, len(filas_tab) + 1)):
                grid_d.append([str(ex), "", "", "", "", ""])
            grid_d.append(["", "", "TOTAL:", "", f"S/. {acum:,.2f}", ""])
            
            tb_g = Table(grid_d, colWidths=[30, 80, 100, 110, 110, 110], style=[
                ('GRID', (0,0), (-1,-2), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 7.5),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FFEE00")),
                ('BOX', (0,-1), (-1,-1), 1, colors.black), ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 2.8)
            ])
            firmas = Table([
                ["__________________________________________", "__________________________________________"],
                ["TESORERO(A) GENERAL", "MIEMBRO CONFORME"],
                ["Iglesia Evangélica 'Nazareth'", f"DNI: {d_miembros[hno]}"]
            ], colWidths=[270, 270], style=[
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8), ('PADDING', (0,0), (-1,-1), 1.5)
            ])

            doc.build([top, Spacer(1, 10), id_t, Spacer(1, 6), decl, Spacer(1, 10), tb_g, Spacer(1, 6), Paragraph(f"<b>Fecha de Emisión:</b> {f_imp.strftime('%d/%m/%Y')}", ParagraphStyle('E', fontSize=7.5, alignment=2)), Spacer(1, 35), firmas])
            return buf.getvalue()

        st.download_button("📄 Descargar Ficha Oficial en PDF", make_pdf(), f"Ficha_Diezmos_{d_miembros[hno]}_{hno}.pdf", "application/pdf")

# ==============================================================================
# 4. MODIFICAR O ELIMINAR CON FILTROS
# ==============================================================================
elif opcion == "⚙️ Modificar o Eliminar":
    st.markdown("#### ⚙️ Gestión de Registros de Diezmo (Modificar o Eliminar)")
    df_all = get_diezmos()

    if df_all.empty:
        st.info("No hay registros de diezmos para gestionar.")
    else:
        df_all["dt_filtro"] = pd.to_datetime(df_all["fecha"], errors="coerce")
        df_all["anio_abono"] = df_all["dt_filtro"].dt.year
        df_all["mes_abono"] = df_all["dt_filtro"].dt.month

        with st.expander("🔎 Filtros de Búsqueda para Localizar Diezmo", expanded=True):
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                buscar_txt = st.text_input("Buscar por Hermano / DNI / N° Boucher:", placeholder="Ej. Carlos, D - 00012, 7485...")
            with col_f2:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_all["anio_abono"].dropna().unique()], reverse=True)
                filtro_anio = st.selectbox("Año de Abono:", anios_disp, index=0)
            with col_f3:
                filtro_mes = st.selectbox("Mes Correspondiente:", ["Todos"] + core.MESES, index=0)
            with col_f4:
                filtro_medio = st.selectbox("Medio de Pago:", ["Todos"] + core.MEDIOS, index=0)

        df_filtrado = df_all.copy()
        if buscar_txt.strip():
            txt = buscar_txt.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado["nombre_miembro"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["id_miembro"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["serie_constancia"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["detalle"].astype(str).str.lower().str.contains(txt)
            ]
        if filtro_anio != "Todos":
            df_filtrado = df_filtrado[df_filtrado["anio_abono"] == filtro_anio]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado["mes"] == filtro_mes]
        if filtro_medio != "Todos":
            df_filtrado = df_filtrado[df_filtrado["medio"] == filtro_medio]

        st.caption(f"Coincidencias encontradas: **{len(df_filtrado)}** de {len(df_all)} registros.")

        if df_filtrado.empty:
            st.warning("⚠️ No se encontraron diezmos con los filtros indicados.")
        else:
            opciones_item = {
                f"{r['serie_constancia']} — {r['nombre_miembro']} (S/. {r['monto']:,.2f} | {r['fecha']} | Cuota: {r['mes']})": r["id"]
                for _, r in df_filtrado.iterrows()
            }

            st.markdown("---")
            item_sel = st.selectbox("📌 Selecciona el diezmo que deseas gestionar:", list(opciones_item.keys()))
            id_sel = opciones_item[item_sel]
            reg = df_filtrado[df_filtrado["id"] == id_sel].iloc[0]

            accion_gest = st.radio("Acción a realizar sobre el diezmo seleccionado:", ["✏️ Editar Datos", "🗑️ Eliminar Registro"], horizontal=True)

            if accion_gest == "✏️ Editar Datos":
                try:
                    f_val = datetime.strptime(str(reg["fecha"]), "%Y-%m-%d").date()
                except Exception:
                    f_val = date.today()

                with st.form("form_edit_dz_unif"):
                    st.info(f"🔖 Editando **{reg['serie_constancia']}** — El número de constancia se mantiene correlativo e inalterable.")
                    c1, c2 = st.columns(2)
                    with c1:
                        e_fecha = st.date_input("Fecha de Abono:", value=f_val)
                        idx_hno = list(d_miembros.keys()).index(reg["nombre_miembro"]) if reg["nombre_miembro"] in d_miembros else 0
                        e_nom = st.selectbox("Hermano(a):", list(d_miembros.keys()), index=idx_hno)
                        e_monto = st.number_input("Monto (S/.):", min_value=0.5, value=float(reg["monto"]), step=10.0, format="%.2f")
                    with c2:
                        idx_m = core.MESES.index(reg["mes"]) if reg["mes"] in core.MESES else 0
                        e_mes = st.selectbox("Mes Correspondiente:", core.MESES, index=idx_m)
                        idx_med = core.MEDIOS.index(reg["medio"]) if reg["medio"] in core.MEDIOS else 0
                        e_medio = st.selectbox("Medio de Pago:", core.MEDIOS, index=idx_med)
                        e_det = st.text_input("Observación / Detalle:", value=str(reg.get("detalle", "")))
                    e_tes = st.text_input("Tesorero(a) Receptor(a):", value=tesorero_def)

                    btn_guardar = st.form_submit_button("💾 Guardar Cambios y Regenerar Boucher", type="primary")

                if btn_guardar:
                    core.query_db("""
                        UPDATE public.diezmos SET 
                            fecha = ?, id_miembro = ?, nombre_miembro = ?, mes = ?, 
                            medio = ?, monto = ?, detalle = ?
                        WHERE id = ?
                    """, (str(e_fecha), d_miembros[e_nom], e_nom, e_mes, e_medio, round(float(e_monto), 2), e_det.strip(), id_sel))

                    core.registrar_log("Diezmos", "Edición", f"Actualizado {reg['serie_constancia']} ({e_nom}) S/. {e_monto:,.2f}")
                    st.session_state["ultimo_dz"] = {
                        "serie": reg["serie_constancia"], "fecha": str(e_fecha), "nombre": e_nom,
                        "mes": e_mes, "medio": e_medio, "monto": e_monto, "detalle": e_det.strip(),
                        "tesorero": e_tes.strip(), "telefono": d_telefonos.get(e_nom, "")
                    }
                    st.toast("✅ Registro de diezmo actualizado correctamente.")
                    st.rerun()

                if "ultimo_dz" in st.session_state and st.session_state["ultimo_dz"]["serie"] == reg["serie_constancia"]:
                    st.success(f"Boucher **{reg['serie_constancia']}** actualizado:")
                    panel_whatsapp_descarga(st.session_state["ultimo_dz"])

            elif accion_gest == "🗑️ Eliminar Registro":
                st.warning(f"⚠️ ¿Confirma eliminar definitivamente la constancia **{reg['serie_constancia']}** de **{reg['nombre_miembro']}** por **S/. {reg['monto']:,.2f}**?")
                st.caption("Nota: Si ya se asentó el mes en Tesorería, recuerda volver a pulsar 'Actualizar Asientos en Tesorería' en el control mensual.")
                if st.button("Eliminar Definitivamente", type="primary"):
                    core.query_db("DELETE FROM public.diezmos WHERE id=?", (id_sel,))
                    core.registrar_log("Diezmos", "Eliminación", f"Eliminada constancia {reg['serie_constancia']} (#{id_sel})")
                    if "ultimo_dz" in st.session_state:
                        del st.session_state["ultimo_dz"]
                    st.toast(f"🗑️ Constancia {reg['serie_constancia']} eliminada.")
                    st.rerun()
