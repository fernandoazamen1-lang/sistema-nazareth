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

st.subheader("💬 Foro Interno y Recordatorios")

opcion = st.radio(
    "Acción:", 
    ["Tablón de Notas", "Publicar Recordatorio"], 
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# CARGA DE DATOS OPTIMIZADA CON CACHÉ
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def cargar_notas_foro():
    """Trae las notas del foro y las guarda en memoria por 5 minutos."""
    return core.read_db("""
        SELECT id, fecha_creacion, autor, titulo, contenido, fecha_limite, prioridad, leido 
        FROM public.foro_recordatorios 
        ORDER BY id DESC
    """)

@st.cache_data(ttl=86400, show_spinner=False)
def cargar_lista_responsables():
    """Mantiene la lista de autores en memoria por 24 horas."""
    df_resp = core.read_db("SELECT nombre FROM public.responsables_catalogo ORDER BY nombre ASC")
    return df_resp["nombre"].tolist() if not df_resp.empty else ["Secretaría", "Pastor Principal", "Tesorería General"]

def limpiar_caches_foro():
    cargar_notas_foro.clear()
    st.cache_data.clear()

# ==============================================================================
# VISTA 1: TABLÓN DE NOTAS
# ==============================================================================
if opcion == "Tablón de Notas":
    df_foro = cargar_notas_foro()
    
    if df_foro.empty:
        st.info("No hay notas ni recordatorios registrados.")
    else:
        # Mostramos los últimos 50 registros para no saturar la interfaz de usuario si hay miles
        for _, r in df_foro.head(50).iterrows():
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
                            limpiar_caches_foro()
                            st.rerun()
                    else:
                        st.caption("✅ Atendido / Leído")
                    
                    if st.button("🗑️ Eliminar", key=f"f_del_{r['id']}", type="secondary"):
                        core.query_db("DELETE FROM public.foro_recordatorios WHERE id=?", (r["id"],))
                        core.registrar_log("Foro", "Eliminación", f"Nota eliminada: {r['titulo']}")
                        limpiar_caches_foro()
                        st.toast("🗑️ Nota eliminada.")
                        st.rerun()
            st.divider()

# ==============================================================================
# VISTA 2: PUBLICAR RECORDATORIO
# ==============================================================================
elif opcion == "Publicar Recordatorio":
    lista_resp = cargar_lista_responsables()
    
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
                
                limpiar_caches_foro()
                
                st.toast("✅ Publicado en el foro.")
                st.rerun()
            else:
                st.warning("⚠️ Debes ingresar un título y contenido para publicar.")

# Pie de página institucional
core.mostrar_pie_pagina()
