import streamlit as st
import core
from datetime import date

# 1. Configuración de página
st.set_page_config(
    page_title="Foro y Recordatorios", 
    page_icon="💬", 
    layout="wide"
)

# 2. Seguridad y validación de permisos
core.requerir_login()
core.verificar_acceso_pagina("Foro / Recordatorios")
core.aplicar_estilos_base()

# 3. Asegurar estructura de tabla en esquema public (PostgreSQL)
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.foro_recordatorios (
                    id SERIAL PRIMARY KEY,
                    fecha_creacion DATE NOT NULL,
                    autor TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    contenido TEXT NOT NULL,
                    fecha_limite TEXT DEFAULT '',
                    prioridad TEXT DEFAULT 'Media',
                    leido INTEGER DEFAULT 0
                );
            """)
        conn.commit()
except Exception:
    pass

st.subheader("💬 Foro Interno y Recordatorios")

opcion = st.radio(
    "Acción:", 
    ["Tablón de Notas", "Publicar Recordatorio"], 
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# VISTA 1: TABLÓN DE NOTAS
# ==============================================================================
if opcion == "Tablón de Notas":
    df_foro = core.read_db("SELECT * FROM public.foro_recordatorios ORDER BY id DESC")
    
    if df_foro.empty:
        st.info("No hay notas ni recordatorios registrados.")
    else:
        for _, r in df_foro.iterrows():
            with st.container():
                c1, c2 = st.columns([6, 2])
                with c1:
                    prio_color = "#DC2626" if r['prioridad'] == "Alta" else ("#D97706" if r['prioridad'] == "Media" else "#2563EB")
                    st.markdown(f"**{r['titulo']}** <span style='background-color:{prio_color}20; color:{prio_color}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:12px;'>{r['prioridad'].upper()}</span>", unsafe_allow_html=True)
                    st.write(r["contenido"])
                    st.caption(f"✍️ Autor: **{r['autor']}** | 🗓️ Fecha Límite: **{r['fecha_limite'] or 'Sin fecha'}** | Publicado: {r['fecha_creacion']}")
                with c2:
                    if r["leido"] == 0:
                        if st.button("Marcar Leído", key=f"f_lei_{r['id']}"):
                            core.query_db("UPDATE public.foro_recordatorios SET leido=1 WHERE id=?", (r["id"],))
                            core.registrar_log("Foro", "Atendido", f"Marcado leído: {r['titulo']}")
                            st.rerun()
                    else:
                        st.caption("✅ Atendido / Leído")
                    
                    if st.button("🗑️ Eliminar", key=f"f_del_{r['id']}", type="secondary"):
                        core.query_db("DELETE FROM public.foro_recordatorios WHERE id=?", (r["id"],))
                        core.registrar_log("Foro", "Eliminación", f"Nota eliminada: {r['titulo']}")
                        st.toast("🗑️ Nota eliminada.")
                        st.rerun()
            st.divider()

# ==============================================================================
# VISTA 2: PUBLICAR RECORDATORIO
# ==============================================================================
elif opcion == "Publicar Recordatorio":
    df_resp = core.read_db("SELECT nombre FROM public.responsables_catalogo ORDER BY nombre ASC")
    lista_resp = df_resp["nombre"].tolist() if not df_resp.empty else ["Secretaría", "Pastor Principal", "Tesorería General"]
    
    with st.form("form_nuevo_foro", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            autor = st.selectbox("Autor:", lista_resp)
            titulo = st.text_input("Título del Recordatorio / Tarea:", placeholder="Ej. Presentar balance mensual")
        with c2:
            prioridad = st.selectbox("Nivel de Prioridad:", ["Alta", "Media", "Baja"], index=1)
            limite = st.date_input("Fecha Límite de Atención:", value=date.today())
        
        contenido = st.text_area("Detalle / Indicaciones:", placeholder="Escribe aquí las indicaciones o detalles del recordatorio...")
        
        if st.form_submit_button("📢 Publicar en el Foro", type="primary"):
            if titulo.strip() and contenido.strip():
                core.query_db("""
                    INSERT INTO public.foro_recordatorios 
                    (fecha_creacion, autor, titulo, contenido, fecha_limite, prioridad, leido) 
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (str(date.today()), autor, titulo.strip(), contenido.strip(), str(limite), prioridad))
                core.registrar_log("Foro", "Publicación", f"Publicado: {titulo.strip()} por {autor}")
                st.toast("✅ Publicado en el foro.")
                st.rerun()
            else:
                st.warning("⚠️ Debes ingresar un título y contenido para publicar.")
