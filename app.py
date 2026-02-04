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
            
    if row_idx is None:
        return None, "La temperatura está fuera de los rangos de la tabla"
    if col_name is None:
        return None, "La humedad relativa está fuera de los rangos de la tabla"
        
    hcfm = df.loc[row_idx, col_name]
    
    periodo = "día" if is_day else "noche"
    return hcfm, f"Tabla {periodo}: Temp={temp}°C, HR={rh}% → HCFM={hcfm}%"

def get_correction(month, sombra, exposicion, pendiente, hour_float):
    """
    Obtiene corrección para el HCFM según temporada, pendiente, sombreado...
    """
    # Determinar estación
    if month in [12, 1, 2]:
        estacion = "verano"
    elif month in [6, 7, 8]:
        estacion = "invierno"
    else:
        estacion = "oto_prim"
    
    # Determinar rango de pendiente
    pendiente_key = "mas50" if pendiente >= 50 else "menos50"
    
    filename = FILES[f"{estacion}_{pendiente_key}"]
    
    try:
        df_corr = pd.read_csv(filename, sep=';')
    except FileNotFoundError:
        return 0, f"No se encontró {filename}"
    
    # Paso 1: Buscar columna de exposición
    exp_map = {
        "Norte": ["N", "Norte"],
        "Sur": ["S", "Sur"],
        "Este": ["E", "Este"],
        "Oeste": ["O", "Oeste", "W", "West"]
    }
    
    col_exp = None
    for posible_col in df_corr.columns:
        for nombre in exp_map.get(exposicion, []):
            if nombre.lower() in str(posible_col).lower():
                col_exp = posible_col
                break
        if col_exp:
            break
    
    if col_exp is None:
        return 0, f"No se encontró columna para exposición '{exposicion}'"
    
    # Paso 2: Buscar fila por sombra
    sombra_idx = None
    for idx, val in df_corr.iloc[:, 0].items():
        if parse_range(sombra, val):
            sombra_idx = idx
            break
    
    if sombra_idx is None:
        return 0, f"Sombreado {sombra}% fuera de rango de la tabla"
    
    correccion = df_corr.loc[sombra_idx, col_exp]
    
    return correccion, (f"Corrección estacional ({estacion}, Pend {pendiente_key}): "
                        f"Sombra={sombra}%, Exp={exposicion} → {correccion:+.1f}%")

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

# --- ESTILOS CSS ---
st.markdown("""
<style>
html, body, .stApp { font-family: 'Segoe UI', system-ui, sans-serif; }

/* HEADER: Recuadro verde corporativo */
.app-header {
    background: linear-gradient(135deg, #F1F8F4 0%, #E3F1EA 100%);
    color: #fff; 
    padding: 1.2rem 2rem;
    border-radius: 0 0 16px 16px; 
    margin: -1rem -2rem 1.8rem;
    box-shadow: 0 4px 20px rgba(27,67,50,.35);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
}

.header-left {
    flex: 1;
    display: flex;
    justify-content: flex-start;
}

.header-center {
    flex: 2;
    text-align: center;
}
.header-center h1 { 
    margin:0; 
    font-size:1.75rem; 
    font-weight:700; 
    letter-spacing:-.3px; 
    color: #1B4332 !important; 
}
.header-center p { 
    margin:.3rem 0 0; 
    font-size:.88rem; 
    opacity:.9; 
    color: #2D6A4F; 
}

.header-right {
    flex: 1;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
}

.header-logo-img {
    height: 60px;
    width: auto;
    display: block;
}

@media (max-width: 768px) {
    .app-header { flex-direction: column; text-align: center; }
    .header-left, .header-right { justify-content: center; }
}

.footer-logo {
    text-align: center;
    margin-top: 30px;
    padding: 20px 0;
    border-top: 2px solid #2D6A4F;
}
</style>
""", unsafe_allow_html=True)

# --- HEADER CON RECUADRO VERDE ---
logo_svg = render_svg_logo("logo.svg", width="auto")
slogan_svg = render_svg_logo("Slogan.svg", width="auto")

st.markdown(f"""
<div class="app-header">
    <div class="header-left">
        {logo_svg if logo_svg else ''}
    </div>
    <div class="header-center">
        <h1>🔥 Calculadora de Probabilidad de Ignición (PIG)</h1>
        <p>CONAF</p>
    </div>
    <div class="header-right">
        {slogan_svg if slogan_svg else ''}
    </div>
</div>
""", unsafe_allow_html=True)

# --- INSTRUCTIVO ---
st.markdown("""
### 📋 Descripción del Sistema
Este sistema calcula la **Probabilidad de Ignición de combustibles forestales** mediante el cruce de variables 
meteorológicas y topográficas. Utiliza tablas de humedad del combustible fino muerto (HCFM) ajustadas por:
- **Periodo del día** (día/noche)
- **Estación del año** (verano, invierno, otoño-primavera)
- **Condiciones del terreno** (exposición, pendiente, sombreado)

El resultado es un porcentaje que indica la probabilidad de que una fuente de calor genere ignición en el combustible.
""")

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
