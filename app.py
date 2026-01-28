import streamlit as st
import pandas as pd
from datetime import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Calculadora PIG", page_icon="🔥", layout="centered")

# --- 1. DEFINICIÓN DE ARCHIVOS (Ajusta los nombres si es necesario) ---
FILES = {
    "dia": "tabla_dia.csv",
    "noche": "tabla_noche.csv",
    "verano_mas50": "meses_verano_mas50.csv",
    "verano_menos50": "meses_verano_menos50.csv", # Revisa si tu archivo dice 'menor' o 'menos'
    "oto_prim_mas50": "meses_otonoprim_mas50.csv",
    "oto_prim_menos50": "meses_otonoprim_menos50.csv",
    "invierno_mas50": "meses_invierno_mas50.csv",
    "invierno_menos50": "meses_invierno_menos50.csv",
    "pig": "probabilidad_ignicion.csv"
}

# --- 2. EL MOTOR DE LECTURA (TRADUCTOR DE RANGOS) ---
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
            # Manejo de números negativos (ej: -5 a 0) es complejo, asumimos positivo por ahora
            return float(parts[0]) <= value <= float(parts[1])
            
        # Valor exacto
        return float(s) == value
    except:
        return False

# --- 3. LÓGICA DE NEGOCIO ---

def get_base_hcfm(temp, rh, hour_float):
    # Definir Día (08:00 a 20:00) vs Noche (20:01 a 07:59)
    is_day = 8.0 <= hour_float <= 20.0
    
    filename = FILES["dia"] if is_day else FILES["noche"]
    try:
        df = pd.read_csv(filename, sep=';')
    except FileNotFoundError:
        return None, f"Error: No se encontró el archivo {filename}"
        
    # Buscar Fila (Temperatura) - Columna 0
    row_idx = None
    for idx, val in df.iloc[:, 0].items():
        if parse_range(temp, val):
            row_idx = idx
            break
            
    # Buscar Columna (Humedad) - Encabezados (saltando el primero)
    col_name = None
    for col in df.columns[1:]:
        if parse_range(rh, col):
            col_name = col
            break
            
    if row_idx is None: return None, "Temperatura fuera de rango"
    if col_name is None: return None, "Humedad fuera de rango"
        
    return df.loc[row_idx, col_name], "Tabla de Día" if is_day else "Tabla de Noche"

def get_correction(month, shade_pct, aspect, slope, hour_float):
    # 1. Estación
    if month in [11, 12, 1]: season = "verano"
    elif month in [5, 6, 7]: season = "invierno"
    else: season = "oto_prim"
    
    # 2. Sombra (>50 o <50)
    # Nota: Tu archivo dice "mas50" y "menor50"/"menos50"
    shade_cond = "mas50" if shade_pct > 50 else "menos50"
    
    file_key = f"{season}_{shade_cond}"
    try:
        df = pd.read_csv(FILES[file_key], sep=';')
    except KeyError:
        return 0, f"Error de configuración: falta archivo para {season}"
    except FileNotFoundError:
        return 0, f"Falta archivo: {FILES[file_key]}"

    # 3. Columna de Hora
    # Tus columnas son '8:00 a 9:59', etc.
    target_col = None
    for col in df.columns:
        if ' a ' in col.lower() or ' A ' in col: # Detectar columnas de hora
            try:
                # Extraer horas del texto. Ej: "14:00 a 15:59" -> 14 y 15
                parts = col.lower().replace(' a ', '-').split('-')
                start_h = int(parts[0].split(':')[0])
                # end_h lo tomamos simple. Si es 15:59, asumimos hasta <16
                end_h = int(parts[1].split(':')[0])
                
                if start_h <= hour_float < (end_h + 1):
                    target_col = col
                    break
            except: continue
    
    # Si la hora no cae en ningún rango (ej: noche profunda en tabla de corrección), es 0
    if target_col is None: return 0, "Hora sin corrección"

    # 4. Fila (Exposición y Pendiente)
    aspect_map = {'Norte': 'N', 'Sur': 'S', 'Este': 'E', 'Oeste': 'O'}
    aspect_code = aspect_map.get(aspect, 'N')
    
    correction = 0
    
    for idx, row in df.iterrows():
        # Columnas 0 (Exp) y 1 (Pendiente)
        r_exp = str(row.iloc[0])
        r_slope = str(row.iloc[1])
        
        # Chequear Exposición (Busca 'N' dentro de 'Norte' o 'N')
        match_exp = (aspect_code in r_exp) or ('TODAS' in r_exp.upper())
        # Chequear Pendiente
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
    
    # 1. Buscar Fila (Sombra y Temp)
    row_match = None
    for idx, row in df.iterrows():
        r_shade = row.iloc[0] # Columna Sombreado
        r_temp = row.iloc[1]  # Columna Temp
        
        if parse_range(shade_pct, r_shade) and parse_range(temp, r_temp):
            row_match = row
            break
            
    if row_match is None: return 0, "No data PIG para Temp/Sombra"
    
    # 2. Buscar Columna (Humedad calculada)
    # Las columnas son '2', '3', '4'...
    h_target = str(int(round(hcfm_final)))
    
    # Si la humedad es muy baja (0 o 1), usar columna 2 (o la mínima disponible)
    if int(h_target) < 2: h_target = "2"
    
    if h_target in df.columns:
        return row_match[h_target], "OK"
    else:
        # Si la humedad es muy alta (ej: 25) y la tabla llega a 17, es riesgo bajo (asumimos el valor min o 0)
        # Normalmente PIG disminuye con humedad alta. Tomamos el último valor (extremo derecho)
        return row_match.iloc[-1], "Humedad extrema (riesgo bajo)"

# --- 4. INTERFAZ GRÁFICA (FRONTEND) ---

st.title("🌲 Calculadora de Ignición (PIG)")
st.markdown("---")

col_izq, col_der = st.columns(2)

with col_izq:
    st.header("1. Datos Meteorológicos")
    fecha = st.date_input("Fecha")
    hora = st.time_input("Hora", value=time(14, 0))
    temp = st.number_input("Temperatura (°C)", value=25, step=1)
    hr = st.number_input("Humedad Relativa (%)", value=30, step=1)

with col_der:
    st.header("2. Datos del Terreno")
    sombra = st.slider("Sombreado (%)", 0, 100, 0)
    pendiente = st.slider("Pendiente (%)", 0, 100, 10)
    exposicion = st.selectbox("Exposición", ["Norte", "Sur", "Este", "Oeste"])

if st.button("🔥 Calcular Probabilidad", type="primary", use_container_width=True):
    # Conversión de hora a decimal (14:30 -> 14.5)
    hora_dec = hora.hour + hora.minute/60.0
    
    # --- PROCESO ---
    base, msg_base = get_base_hcfm(temp, hr, hora_dec)
    
    if base is not None:
        corr, msg_corr = get_correction(fecha.month, sombra, exposicion, pendiente, hora_dec)
        
        hcfm_final = base + corr
        
        pig, msg_pig = get_pig(hcfm_final, temp, sombra)
        
        # --- RESULTADOS ---
        st.markdown("### Resultados")
        c1, c2, c3 = st.columns(3)
        c1.metric("Humedad Base", base, help=msg_base)
        c2.metric("Corrección", corr, help=msg_corr)
        c3.metric("Humedad Final", f"{hcfm_final:.1f}")
        
        st.markdown(f"""
        <div style="padding:20px; border-radius:10px; background-color:{'#ff4b4b' if pig > 50 else '#f0f2f6'}; text-align:center">
            <h1 style="color:{'white' if pig > 50 else 'black'}; margin:0">Probabilidad: {pig}%</h1>
            <p style="color:{'white' if pig > 50 else 'black'}; margin:0">{msg_pig}</p>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        st.error(f"Error en datos base: {msg_base}")
