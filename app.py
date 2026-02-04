import streamlit as st
import pandas as pd
from datetime import time
import base64
from pathlib import Path

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Calculadora PIG", page_icon="🔥", layout="wide")

# --- FUNCIONES AUXILIARES PARA LOGOS ---
def get_base64_of_svg(svg_path):
    """Convierte un archivo SVG a base64 para embeber en HTML"""
    try:
        with open(svg_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def render_svg_logo(svg_path, width="100%", height="auto"):
    """Renderiza un SVG desde archivo local"""
    svg_base64 = get_base64_of_svg(svg_path)
    if svg_base64:
        return f'<img src="data:image/svg+xml;base64,{svg_base64}" style="width:{width};height:{height};">'
    return ""

# --- 1. DEFINICIÓN DE ARCHIVOS (Ajusta los nombres si es necesario) ---
FILES = {
    "dia": "tabla_dia.csv",
    "noche": "tabla_noche.csv",
    "verano_mas50": "meses_verano_mas50.csv",
    "verano_menos50": "meses_verano_menos50.csv",
    "oto_prim_mas50": "meses_otonoprim_mas50.csv",
    "oto_prim_menos50": "meses_otonoprim_menos50.csv",
    "invierno_mas50": "meses_invierno_mas50.csv",
    "invierno_menos50": "meses_invierno_menos50.csv",
    "pig": "probabilidad_ignicion.csv"
}

# --- 2. CATEGORÍAS Y COLORES ---
def get_categoria_info(pig_value):
    """
    Retorna la categoría, color, uso técnico e interpretación según el valor PIG
    """
    categorias = [
        {
            "nombre": "Bajo",
            "rango": (0, 20),
            "color": "#2ECC71",
            "uso": "Condición segura, monitoreo básico",
            "interpretacion": "Condiciones poco favorables para que una fuente de calor genere ignición. Combustibles con mayor humedad y/o baja eficiencia de transferencia de calor."
        },
        {
            "nombre": "Moderado",
            "rango": (21, 40),
            "color": "#A9DFBF",
            "uso": "Atención preventiva",
            "interpretacion": "Existe posibilidad de ignición ante fuentes eficientes (chispas, brasas), pero no es esperable una ignición generalizada. Riesgo controlable con medidas básicas."
        },
        {
            "nombre": "Alto",
            "rango": (41, 60),
            "color": "#F4D03F",
            "uso": "Riesgo activo, medidas preventivas",
            "interpretacion": "Condiciones favorables para ignición. La mayoría de las fuentes de calor pueden generar fuego. Requiere restricciones parciales y aumento de vigilancia."
        },
        {
            "nombre": "Muy Alto",
            "rango": (61, 80),
            "color": "#E67E22",
            "uso": "Restricciones y vigilancia reforzada",
            "interpretacion": "Alta eficiencia de ignición. Combustibles finos altamente receptivos. Alta probabilidad de inicio de incendios ante actividades humanas comunes."
        },
        {
            "nombre": "Extremo",
            "rango": (81, 100),
            "color": "#C0392B",
            "uso": "Condición crítica, prohibiciones y alerta",
            "interpretacion": "Ignición casi segura ante cualquier fuente. Combustibles críticos, baja humedad y alta continuidad. Condiciones asociadas a incendios de rápida propagación."
        }
    ]
    
    for cat in categorias:
        if cat["rango"][0] <= pig_value <= cat["rango"][1]:
            return cat
    
    # Por defecto si está fuera de rango
    return categorias[0] if pig_value < 0 else categorias[-1]

def generar_interpretacion_tecnica(pig_value):
    """
    Genera una interpretación técnica personalizada según el valor exacto de PIG.
    Formato: técnico, conciso, orientado a gestión del riesgo.
    """
    # Determinar categoría base
    if pig_value <= 20:
        categoria = "riesgo bajo"
        receptividad = "receptividad limitada"
        proporcion = "una minoría de las fuentes de calor potenciales"
        actividades = "Las actividades habituales presentan bajo potencial de inicio de incendios"
        medidas = "siendo suficientes las medidas de vigilancia estándar y el monitoreo rutinario"
    elif pig_value <= 40:
        categoria = "riesgo moderado"
        receptividad = "receptividad moderada"
        proporcion = "aproximadamente un tercio de las fuentes de calor potenciales"
        actividades = "Las actividades con generación de chispas o brasas constituyen un factor de riesgo controlable"
        medidas = "siendo necesario reforzar la vigilancia preventiva y aplicar restricciones básicas en zonas sensibles"
    elif pig_value <= 60:
        categoria = "riesgo alto"
        receptividad = "receptividad significativa"
        if pig_value <= 50:
            proporcion = "aproximadamente la mitad de las fuentes de calor potenciales"
        else:
            proporcion = "la mayoría de las fuentes de calor potenciales"
        actividades = "Las actividades humanas habituales constituyen un factor relevante de inicio de incendios forestales"
        medidas = "siendo necesario reforzar las medidas preventivas, la vigilancia y el control del uso del fuego para reducir la ocurrencia de nuevos focos"
    elif pig_value <= 80:
        categoria = "riesgo muy alto"
        receptividad = "alta receptividad"
        proporcion = "la gran mayoría de las fuentes de calor comunes"
        actividades = "Las actividades humanas rutinarias presentan alta probabilidad de inicio de incendios"
        medidas = "requiriéndose la implementación de prohibiciones específicas, vigilancia reforzada y pre-posicionamiento de recursos de supresión"
    else:  # 81-100
        categoria = "riesgo extremo"
        receptividad = "receptividad crítica"
        proporcion = "prácticamente cualquier fuente de calor"
        actividades = "Las condiciones presentes garantizan la ignición ante exposiciones mínimas"
        medidas = "exigiéndose el cierre preventivo de áreas, prohibición total de actividades y máxima alerta operativa ante la inminencia de eventos de rápida propagación"
    
    interpretacion = (
        f"Una probabilidad de ignición del {pig_value:.0f}% indica una condición de {categoria}, "
        f"en la cual los combustibles finos presentan una {receptividad} y {proporcion} pueden generar ignición. "
        f"Bajo este escenario, {actividades.lower()}, {medidas}."
    )
    
    return interpretacion

# --- 3. EL MOTOR DE LECTURA (TRADUCTOR DE RANGOS) ---
def parse_range(value, range_str):
    """
    Interpreta rangos de Excel: '11 a 50', '>30', '<0', '41+', etc.
    """
    if pd.isna(range_str) or str(range_str).strip().lower() == 'nan': return False
    
    # Normalizar texto (minusculas, sin espacios extra)
    s = str(range_str).strip().lower()
    
    # Caso especial: 'TODAS'
    if 'tod' in s: return True
    
    # Limpieza: quitar % y cambiar ' a ' por '-'
    s = s.replace('%', '').replace(' a ', '-') 
    
    try:
        # Mayor que (> o +)
        if '>' in s: return value >= float(s.replace('>', ''))
        if '+' in s: return value >= float(s.replace('+', ''))
        
        # Menor que (<)
        if '<' in s: return value < float(s.replace('<', ''))
        
        # Rango (guion)
        if '-' in s:
            parts = s.split('-')
            return float(parts[0]) <= value <= float(parts[1])
            
        # Valor exacto
        return float(s) == value
    except:
        return False

# --- 4. LÓGICA DE NEGOCIO ---

def get_base_hcfm(temp, rh, hour_float):
    is_day = 8.0 <= hour_float <= 20.0
    
    filename = FILES["dia"] if is_day else FILES["noche"]
    try:
        df = pd.read_csv(filename, sep=';')
    except FileNotFoundError:
        return None, f"Error: No se encontró el archivo {filename}"
        
    row_idx = None
    for idx, val in df.iloc[:, 0].items():
        if parse_range(temp, val):
            row_idx = idx
            break
            
    col_name = None
    for col in df.columns[1:]:
        if parse_range(rh, col):
            col_name = col
            break
            
    if row_idx is None: return None, "Temperatura fuera de rango"
    if col_name is None: return None, "Humedad fuera de rango"
        
    return df.loc[row_idx, col_name], "Tabla de Día" if is_day else "Tabla de Noche"

def get_correction(month, shade_pct, aspect, slope, hour_float):
    if month in [11, 12, 1]: season = "verano"
    elif month in [5, 6, 7]: season = "invierno"
    else: season = "oto_prim"
    
    shade_cond = "mas50" if shade_pct > 50 else "menos50"
    
    file_key = f"{season}_{shade_cond}"
    try:
        df = pd.read_csv(FILES[file_key], sep=';')
    except KeyError:
        return 0, "Archivo de corrección no encontrado"
    except FileNotFoundError:
        return 0, f"Archivo {FILES[file_key]} no encontrado"
    
    aspect_code = aspect[0]
    
    target_col = None
    for col in df.columns[2:]:
        try:
            col_hour = int(col)
            if hour_float < col_hour:
                target_col = col
                break
        except:
            continue
            
    if target_col is None:
        target_col = df.columns[-1]
    
    correction = 0
    for idx, row in df.iterrows():
        r_exp = str(row.iloc[0])
        r_slope = str(row.iloc[1])
        
        match_exp = (aspect_code in r_exp) or ('TODAS' in r_exp.upper())
        match_slope = parse_range(slope, r_slope)
        
        if match_exp and match_slope:
            correction = row[target_col]
            break
            
    return correction, f"Corrección {season} ({shade_cond})"

def get_pig(hcfm_final, temp, shade_pct):
    try:
        df = pd.read_csv(FILES["pig"], sep=';')
    except FileNotFoundError:
        return 0, "Falta archivo PIG"
    
    row_match = None
    for idx, row in df.iterrows():
        r_shade = row.iloc[0]
        r_temp = row.iloc[1]
        
        if parse_range(shade_pct, r_shade) and parse_range(temp, r_temp):
            row_match = row
            break
            
    if row_match is None: return 0, "No data PIG para Temp/Sombra"
    
    h_target = str(int(round(hcfm_final)))
    
    if int(h_target) < 2: h_target = "2"
    
    if h_target in df.columns:
        return row_match[h_target], "OK"
    else:
        return row_match.iloc[-1], "Humedad extrema (riesgo bajo)"

# --- 5. INTERFAZ GRÁFICA (FRONTEND) ---

# Header con logos
st.markdown("""
<style>
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
        padding: 15px 0;
        border-bottom: 2px solid #e74c3c;
    }
    .title-section {
        flex: 1;
    }
    .logo-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        max-width: 200px;
    }
    .footer-logo {
        text-align: center;
        margin-top: 30px;
        padding: 20px 0;
        border-top: 2px solid #e74c3c;
    }
</style>
""", unsafe_allow_html=True)

# Intenta cargar los logos (si están disponibles)
logo_svg = render_svg_logo("logo.svg", width="150px")
slogan_svg = render_svg_logo("Slogan.svg", width="150px")

col_title, col_logos = st.columns([3, 1])

with col_title:
    st.title("🌲 Calculadora de Probabilidad de Ignición (PIG)")
    st.markdown("""
    ### 📋 Descripción del Sistema
    Este sistema calcula la **Probabilidad de Ignición de combustibles forestales** mediante el cruce de variables 
    meteorológicas y topográficas. Utiliza tablas de humedad del combustible fino muerto (HCFM) ajustadas por:
    - **Periodo del día** (día/noche)
    - **Estación del año** (verano, invierno, otoño-primavera)
    - **Condiciones del terreno** (exposición, pendiente, sombreado)
    
    El resultado es un porcentaje que indica la probabilidad de que una fuente de calor genere ignición en el combustible.
    """)

with col_logos:
    if logo_svg:
        st.markdown(f'<div style="margin-top: 20px;">{logo_svg}</div>', unsafe_allow_html=True)
    if slogan_svg:
        st.markdown(f'<div style="margin-top: 10px;">{slogan_svg}</div>', unsafe_allow_html=True)

st.markdown("---")

# Inputs
col_izq, col_der = st.columns(2)

with col_izq:
    st.header("1️⃣ Datos Meteorológicos")
    fecha = st.date_input("Fecha", help="Determina la estación del año para correcciones")
    hora = st.time_input("Hora", value=time(14, 0), help="Influye en tabla día/noche y corrección horaria")
    temp = st.number_input("Temperatura (°C)", value=25, step=1, help="Temperatura del aire")
    hr = st.number_input("Humedad Relativa (%)", value=30, step=1, help="Humedad relativa del aire")

with col_der:
    st.header("2️⃣ Datos del Terreno")
    sombra = st.slider("Sombreado (%)", 0, 100, 0, help="Porcentaje de sombra sobre el combustible")
    pendiente = st.slider("Pendiente (%)", 0, 100, 10, help="Inclinación del terreno")
    exposicion = st.selectbox("Exposición", ["Norte", "Sur", "Este", "Oeste"], 
                              help="Orientación de la ladera")

st.markdown("---")

if st.button("🔥 Calcular Probabilidad de Ignición", type="primary", use_container_width=True):
    # Conversión de hora a decimal (14:30 -> 14.5)
    hora_dec = hora.hour + hora.minute/60.0
    
    # --- PROCESO ---
    base, msg_base = get_base_hcfm(temp, hr, hora_dec)
    
    if base is not None:
        corr, msg_corr = get_correction(fecha.month, sombra, exposicion, pendiente, hora_dec)
        
        hcfm_final = base + corr
        
        pig, msg_pig = get_pig(hcfm_final, temp, sombra)
        
        # Obtener información de categoría
        cat_info = get_categoria_info(pig)
        
        # --- RESULTADOS ---
        st.markdown("## 📊 Resultados del Cálculo")
        
        # Métricas intermedias
        col1, col2, col3 = st.columns(3)
        col1.metric("Humedad Base HCFM", f"{base:.1f}%", help=msg_base)
        col2.metric("Corrección Aplicada", f"{corr:+.1f}%", help=msg_corr)
        col3.metric("Humedad Final HCFM", f"{hcfm_final:.1f}%")
        
        st.markdown("---")
        
        # Resultado principal con color
        st.markdown(f"""
        <div style="padding: 30px; border-radius: 15px; background-color: {cat_info['color']}; 
                    text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 20px 0;">
            <h1 style="color: white; margin: 0; font-size: 3em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                {pig:.0f}%
            </h1>
            <h2 style="color: white; margin: 10px 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">
                Riesgo {cat_info['nombre'].upper()}
            </h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Interpretación técnica personalizada
        st.markdown("### 🔍 Interpretación Técnica")
        
        interpretacion_personalizada = generar_interpretacion_tecnica(pig)
        
        # Mostrar interpretación personalizada en formato destacado
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 20px; border-left: 5px solid {cat_info['color']}; 
                    border-radius: 5px; margin: 15px 0;">
            <p style="color: #2c3e50; font-size: 1.05em; line-height: 1.6; margin: 0; text-align: justify;">
                {interpretacion_personalizada}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Botón para copiar la interpretación
        col_copy1, col_copy2, col_copy3 = st.columns([2, 1, 2])
        with col_copy2:
            if st.button("📋 Copiar interpretación", use_container_width=True):
                st.code(interpretacion_personalizada, language=None)
                st.caption("↑ Selecciona el texto de arriba para copiarlo")
        
        # Detalles complementarios
        col_a, col_b = st.columns([1, 2])
        
        with col_a:
            st.markdown(f"""
            **Categoría:** {cat_info['nombre']}  
            **Rango:** {cat_info['rango'][0]}-{cat_info['rango'][1]}%  
            """)
            
            # Indicador visual de categoría
            st.markdown(f"""
            <div style="background-color: {cat_info['color']}; padding: 15px; 
                        border-radius: 10px; text-align: center;">
                <p style="color: white; font-weight: bold; margin: 0; 
                          text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">
                    {cat_info['uso']}
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_b:
            with st.expander("📖 Ver interpretación general de la categoría"):
                st.info(cat_info['interpretacion'])
        
        # Tabla de referencia
        st.markdown("---")
        st.markdown("### 📈 Tabla de Referencia - Categorías de Riesgo")
        
        tabla_ref = pd.DataFrame([
            {"Categoría": "Bajo", "Rango (%)": "0 - 20", "Color": "🟢", "Uso Recomendado": "Condición segura, monitoreo básico"},
            {"Categoría": "Moderado", "Rango (%)": "21 - 40", "Color": "🟡", "Uso Recomendado": "Atención preventiva"},
            {"Categoría": "Alto", "Rango (%)": "41 - 60", "Color": "🟠", "Uso Recomendado": "Riesgo activo, medidas preventivas"},
            {"Categoría": "Muy Alto", "Rango (%)": "61 - 80", "Color": "🔶", "Uso Recomendado": "Restricciones y vigilancia reforzada"},
            {"Categoría": "Extremo", "Rango (%)": "81 - 100", "Color": "🔴", "Uso Recomendado": "Condición crítica, prohibiciones y alerta"}
        ])
        
        st.dataframe(tabla_ref, use_container_width=True, hide_index=True)
        
    else:
        st.error(f"❌ Error en datos base: {msg_base}")
        st.info("💡 Verifica que los valores de temperatura y humedad estén dentro de los rangos de las tablas.")

# Footer con logo inferior y texto
st.markdown("---")

inferior_svg = render_svg_logo("Inferior.svg", width="400px")

st.markdown(f"""
<div style="text-align: center; color: #7f8c8d; padding: 20px;">
    <small>
    Sistema de Cálculo de Probabilidad de Ignición en Incendios Forestales<br>
    Basado en humedad de combustibles finos muertos (HCFM) y condiciones meteorológicas/topográficas<br>
    Oficina Provincial Osorno - Producto de Alumno en Practica Francisco Vidal
    </small>
</div>
""", unsafe_allow_html=True)

if inferior_svg:
    st.markdown(f"""
    <div class="footer-logo">
        {inferior_svg}
    </div>
    """, unsafe_allow_html=True)
