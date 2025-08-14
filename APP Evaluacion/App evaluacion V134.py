# -*- coding: utf-8 -*-
import math
from pathlib import Path
from typing import Dict, List

import streamlit as st
from datetime import date, datetime, timedelta
from PIL import Image

# ——— Autorefresh opcional (recomendado para el contador) ———
try:
    from streamlit_autorefresh import st_autorefresh
    HAVE_AUTOREFRESH = True
except Exception:
    HAVE_AUTOREFRESH = False

# =========================
# Utilidades IMC
# =========================
def _imc_categoria_y_sintomas(imc: float):
    """Devuelve (categoria, sintomas) para el IMC dado."""
    if imc is None:
        return None, ""
    if imc < 18.5:
        return "BAJO PESO", "Fatiga, fragilidad, baja masa muscular"
    elif imc < 25:
        return "PESO NORMAL", ""
    elif imc < 30:
        return "SOBREPESO", "Enfermedades digestivas, problemas de circulación en piernas, varices"
    elif imc < 35:
        return "OBESIDAD I", "Apnea del sueño, hipertensión, resistencia a la insulina"
    elif imc < 40:
        return "OBESIDAD II", "Dolor articular, hígado graso, riesgo cardiovascular"
    else:
        return "OBESIDAD III", "Riesgo cardiovascular elevado, diabetes tipo 2, problemas respiratorios"

def _imc_texto_narrativo(imc: float):
    cat, sintomas = _imc_categoria_y_sintomas(imc)
    imc_str = f"{imc:.1f}" if imc is not None else "0"
    if cat == "PESO NORMAL":
        return (f"Tu IMC es el Índice de Masa Corporal. Es la relación entre tu peso y tu tamaño. "
                f"El tuyo es de {imc_str}, eso indica que tienes PESO NORMAL y deberías sentirte con buen nivel de energía, "
                f"vitalidad y buena condición física. ¿Te sientes así?")
    else:
        return (f"Tu IMC es el Índice de Masa Corporal. Es la relación entre tu peso y tu tamaño. "
                f"El tuyo es de {imc_str}, eso indica que tienes {cat} y podrías estar sufriendo de {sintomas}.")

# =========================
# Edad desde fecha
# =========================
def edad_desde_fecha(fecha_nac):
    """Devuelve edad (int) a partir de date o str ISO; None si no válida."""
    if not fecha_nac:
        return None
    try:
        if isinstance(fecha_nac, str):
            fecha_nac = datetime.fromisoformat(fecha_nac).date()
        elif hasattr(fecha_nac, "year"):
            fecha_nac = date(fecha_nac.year, fecha_nac.month, fecha_nac.day)
        else:
            return None
        hoy = date.today()
        return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    except Exception:
        return None

# =========================
# Rango de grasa de referencia
# =========================
def _rango_grasa_referencia(genero: str, edad: int):
    gen = (genero or "").strip().lower()
    tabla_mujer = [(20, 39, 21.0, 32.9), (40, 59, 23.0, 33.9), (60, 79, 24.0, 35.9)]
    tabla_hombre = [(20, 39, 8.0, 19.9), (40, 59, 11.0, 21.9), (60, 79, 13.0, 24.9)]
    tabla = tabla_mujer if gen.startswith("muj") else tabla_hombre
    for lo, hi, rmin, rmax in tabla:
        if lo <= int(edad) <= hi:
            return rmin, rmax
    return tabla[0][2], tabla[0][3]

# -------------------------------------------------------------
# Config
# -------------------------------------------------------------
st.set_page_config(page_title="Evaluación de Bienestar", page_icon="🧭", layout="wide")
APP_DIR = Path(__file__).parent.resolve()

# -------------------------------------------------------------
# Helpers / Estado
# -------------------------------------------------------------
P3_FLAGS = [
    "p3_estrenimiento",
    "p3_colesterol_alto",
    "p3_baja_energia",
    "p3_dolor_muscular",
    "p3_gastritis",
    "p3_hemorroides",
    "p3_hipertension",
    "p3_dolor_articular",
    "p3_ansiedad_por_comer",
    "p3_jaquecas_migranas",
    "p3_diabetes_antecedentes_familiares",
]

def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "datos" not in st.session_state:
        st.session_state.datos = {}
    if "estilo_vida" not in st.session_state:
        st.session_state.estilo_vida = {}
    if "metas" not in st.session_state:
        st.session_state.metas = {
            "perder_peso": False, "tonificar": False, "masa_muscular": False,
            "energia": False, "rendimiento": False, "salud": False, "otros": ""
        }
    if "valoracion_contactos" not in st.session_state:
        st.session_state.valoracion_contactos: List[Dict] = []
    # Flags de P3
    for k in P3_FLAGS:
        st.session_state.setdefault(k, False)
    # Memoria de precios y selección
    st.session_state.setdefault("precios_recomendados", {"batido_5": None, "combo": None})
    st.session_state.setdefault("combo_elegido", None)
    # Deadline de la promoción
    st.session_state.setdefault("promo_deadline", None)

def go(prev=False, next=False, to=None):
    if to is not None:
        st.session_state.step = to
    elif next:
        st.session_state.step = min(st.session_state.step + 1, 6)
    elif prev:
        st.session_state.step = max(st.session_state.step - 1, 1)

def ir_prev(): go(prev=True)
def ir_next(): go(next=True)

def bton_nav(id_pantalla: int | None = None):
    if id_pantalla is None:
        try:
            id_pantalla = int(st.session_state.get("step", 1))
        except Exception:
            id_pantalla = 1
    c1, c2 = st.columns([1, 1])
    with c1:
        st.button("⬅️ Anterior", key=f"prev_{id_pantalla}", on_click=ir_prev)
    with c2:
        st.button("Siguiente ➡️", key=f"next_{id_pantalla}", on_click=ir_next)

def imc(peso_kg: float, altura_cm: float) -> float:
    if not peso_kg or not altura_cm:
        return 0.0
    h = altura_cm / 100.0
    return round(peso_kg / (h*h), 1)

def rango_imc_texto(imc_val: float) -> str:
    if imc_val < 5.0:
        return "Delgadez III: Postración, Astenia, Adinamia, Enfermedades Degenerativas."
    if 5.0 <= imc_val <= 9.9:
        return "Delgadez II: Anorexia, Bulimia, Osteoporosis, Autoconsumo de Masa Muscular."
    if 10.0 <= imc_val <= 18.5:
        return "Delgadez I: Transtornos Digestivos, Debilidad, Fatiga Crónica, Ansiedad, Disfunción Hormonal."
    if 18.6 <= imc_val <= 24.9:
        return "PESO NORMAL: Estado Normal, Buen nivel de Energía, Vitalidad y Buena Condición Física."
    if 25.0 <= imc_val <= 29.9:
        return "Sobrepeso: Fatiga, Enfermedades Digestivas, Problemas de Circulación en Piernas, Varices."
    if 30.0 <= imc_val <= 34.0:
        return "Obesidad I: Diabetes, Hipertensión, Enfermedades Cardiovascular, Problemas Articulares."
    if 35.0 <= imc_val <= 39.9:
        return "Obesidad II: Cáncer, Angina de Pecho, Trombeflebitis, Arteriosclerosis, Embolias."
    return "Obesidad III: Falta de Aire, Apnea, Somnolencia, Trombosis Pulmonar, Úlceras."

def rango_grasa_referencia(genero: str, edad: int) -> str:
    if genero == "MUJER":
        if 16 <= edad <= 39: return "21% – 32.9%"
        if 40 <= edad <= 59: return "23% – 33.9%"
        if 60 <= edad <= 79: return "21% – 32.9%"
    else:
        if 16 <= edad <= 39: return "8.0% – 19.9%"
        if 40 <= edad <= 59: return "11% – 21.9%"
        if 60 <= edad <= 79: return "13% – 24.9%"
    return "—"

def req_hidratacion_ml(peso_kg: float) -> int:
    if not peso_kg: return 0
    return int(round((peso_kg/7.0)*250))

def req_proteina(genero:str, metas:dict, peso_kg:float) -> int:
    if not peso_kg: return 0
    if genero == "HOMBRE":
        if metas.get("masa_muscular"): mult = 2.0
        elif metas.get("rendimiento"): mult = 2.0
        elif metas.get("perder_peso"): mult = 1.6
        elif metas.get("tonificar"): mult = 1.6
        elif metas.get("energia"): mult = 1.6
        elif metas.get("salud"): mult = 1.6
        else: mult = 1.6
    else:
        if metas.get("masa_muscular"): mult = 1.8
        elif metas.get("rendimiento"): mult = 1.8
        elif metas.get("perder_peso"): mult = 1.4
        elif metas.get("tonificar"): mult = 1.4
        elif metas.get("energia"): mult = 1.4
        elif metas.get("salud"): mult = 1.4
        else: mult = 1.4
    return int(round(peso_kg * mult))

def bmr_mifflin(genero:str, peso_kg:float, altura_cm:float, edad:int) -> int:
    if genero == "HOMBRE":
        val = (10*peso_kg) + (6.25*altura_cm) - (5*edad) + 5
    else:
        val = (10*peso_kg) + (6.25*altura_cm) - (5*edad) - 161
    return int(round(val))

def comparativos_proteina(gramos:int) -> str:
    porciones_pollo_100g = gramos / 22.5
    huevos = gramos / 5.5
    return (f"{gramos} g ≈ {round(porciones_pollo_100g*100)} g de pechuga de pollo "
            f"o ≈ {huevos:.0f} huevos.")

def load_img(filename: str):
    p = APP_DIR / filename
    if p.exists():
        try: return Image.open(p)
        except Exception: return None
    return None

# =============================================================
# PRECIOS, VISUAL Y SELECCIÓN
# =============================================================
PRECIOS = {
    "Batido": 184,
    "Té de Hierbas": 145,
    "Aloe Concentrado": 180,
    "Beverage Mix": 159,
    "Beta Heart": 231,
    "Fibra Activa": 168,
    "Golden Beverage": 154,
    "NRG": 112,
    "Herbalifeline": 180,
    "PDM": 234,
}

def _mon(v):
    return f"S/{v:,.0f}".replace(",", ".")

def _precio_sumado(items: List[str]):
    total = 0
    faltantes = []
    for it in items:
        precio = PRECIOS.get(it)
        if precio is None:
            faltantes.append(it)
        else:
            total += precio
    return total, faltantes

def _chip_desc(pct:int):
    return f"<span style='background:#e7f8ee; color:#0a7f44; padding:2px 8px; border-radius:999px; font-size:12px'>-{pct}%</span>"

def _render_card(titulo:str, items:List[str], descuento_pct:int=0, seleccionable:bool=False, key_sufijo:str=""):
    total, faltantes = _precio_sumado(items)
    if descuento_pct:
        precio_desc = round(total * (1 - descuento_pct/100))
        tachado = f"<span style='text-decoration:line-through; opacity:.6; margin-right:8px'>{_mon(total)}</span>"
        precio_html = f"{tachado}<strong style='font-size:20px'>{_mon(precio_desc)}</strong> {_chip_desc(descuento_pct)}"
    else:
        precio_desc = total
        precio_html = f"<strong style='font-size:20px'>{_mon(precio_desc)}</strong>"

    faltante_txt = ""
    if faltantes:
        faltante_txt = f"<div style='color:#b00020; font-size:12px; margin-top:6px'>Falta configurar precio: {', '.join(faltantes)}</div>"

    items_txt = " + ".join(items)
    st.markdown(
        f"""
        <div style='border:1px solid #e8e8e8; border-radius:16px; padding:14px; margin:10px 0; box-shadow:0 2px 8px rgba(0,0,0,.04)'>
          <div style='font-weight:800; font-size:17px; margin-bottom:4px'>{titulo}</div>
          <div style='font-size:13px; margin-bottom:8px'>{items_txt}</div>
          <div>{precio_html}</div>
          {faltante_txt}
        </div>
        """,
        unsafe_allow_html=True
    )

    payload = {
        "titulo": titulo,
        "items": items,
        "precio_regular": total,
        "descuento_pct": descuento_pct,
        "precio_final": precio_desc,
    }

    if seleccionable:
        btn_key = f"elegir_{key_sufijo or titulo.replace(' ', '_')}"
        if st.button("Elegir este", key=btn_key, use_container_width=True):
            st.session_state.combo_elegido = payload
            st.success(f"Elegiste: {titulo} — Total {_mon(precio_desc)}")
    return precio_desc

def _combos_por_flags() -> List[Dict]:
    """Devuelve una lista de combos (titulo, items) según TODOS los flags marcados en P3."""
    combos = []
    ss = st.session_state
    if ss.get("p3_estrenimiento"):        combos.append(("Batido + Fibra activa", ["Batido", "Fibra Activa"]))
    if ss.get("p3_colesterol_alto"):       combos.append(("Batido + Herbalifeline", ["Batido", "Herbalifeline"]))
    if ss.get("p3_baja_energia"):          combos.append(("Batido + Té de Hierbas", ["Batido", "Té de Hierbas"]))
    if ss.get("p3_dolor_muscular"):        combos.append(("Batido + Beverage Mix", ["Batido", "Beverage Mix"]))
    if ss.get("p3_gastritis"):             combos.append(("Batido + Aloe Concentrado", ["Batido", "Aloe Concentrado"]))
    if ss.get("p3_hemorroides"):           combos.append(("Batido + Aloe", ["Batido", "Aloe Concentrado"]))  # “Aloe” = concentrado
    if ss.get("p3_hipertension"):          combos.append(("Batido + Beta Heart", ["Batido", "Beta Heart"]))
    if ss.get("p3_dolor_articular"):       combos.append(("Batido + Golden Beverage", ["Batido", "Golden Beverage"]))
    if ss.get("p3_ansiedad_por_comer"):    combos.append(("Batido + PDM", ["Batido", "PDM"]))
    if ss.get("p3_jaquecas_migranas"):     combos.append(("Batido + NRG", ["Batido", "NRG"]))
    if ss.get("p3_diabetes_antecedentes_familiares"):
                                           combos.append(("Batido + Beta Heart", ["Batido", "Beta Heart"]))
    return combos

# ------------------------------
# Cuenta regresiva (48 horas)
# ------------------------------
def _init_promo_deadline():
    """Inicializa el deadline si no existe (48h desde el primer ingreso a Pantalla 6)."""
    if not st.session_state.promo_deadline:
        st.session_state.promo_deadline = (datetime.now() + timedelta(hours=48)).isoformat()

def _render_countdown():
    """Muestra 'Promoción válida por HH:MM:SS' y autorefresh cada segundo si está disponible."""
    if HAVE_AUTOREFRESH:
        st_autorefresh(interval=1000, key="promo_timer_tick")
    deadline = datetime.fromisoformat(st.session_state.promo_deadline)
    restante = max(deadline - datetime.now(), timedelta(0))
    total_seg = int(restante.total_seconds())
    h, rem = divmod(total_seg, 3600)
    m, s = divmod(rem, 60)
    if total_seg > 0:
        st.markdown(f"### ⏳ Promoción válida por **{h:02d}:{m:02d}:{s:02d}**")
    else:
        st.markdown("### ⏳ **Promoción finalizada**")

def mostrar_opciones_pantalla6():
    """Muestra Batido con 5% y TODOS los combos (10%) según los flags de P3."""
    st.markdown("### Opciones recomendadas")

    # Siempre: Batido Nutricional con 5%
    precio_batido = _render_card("Batido Nutricional", ["Batido"], 5, seleccionable=True, key_sufijo="batido")

    combos = _combos_por_flags()
    if combos:
        for i, (titulo, items) in enumerate(combos, start=1):
            _render_card(titulo, items, 10, seleccionable=True, key_sufijo=f"combo_{i}")
        precio_combo = True
    else:
        st.info("Elige una o más opciones en la Pantalla 3 para ver aquí los combos recomendados con 10% de descuento.")
        precio_combo = None

    st.session_state.precios_recomendados = {
        "batido_5": precio_batido,
        "combo": precio_combo,
    }

    if st.session_state.combo_elegido:
        e = st.session_state.combo_elegido
        st.success(
            f"Seleccionado: **{e['titulo']}** — "
            f"{_mon(e['precio_final'])} "
            f"({e['descuento_pct']}% dscto sobre {_mon(e['precio_regular'])})"
        )

# -------------------------------------------------------------
# STEP 1 - Perfil de Bienestar
# -------------------------------------------------------------
def pantalla1():
    st.header("1) Perfil de Bienestar")
    with st.form("perfil"):
        st.subheader("Información Personal")
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("¿Cuál es tu nombre completo?")
            email  = st.text_input("¿Cuál es tu correo electrónico?")
            movil  = st.text_input("¿Cuál es su número de teléfono?")
        with col2:
            fecha_nac = st.date_input("¿Cuál es tu fecha de nacimiento?",
                                      value=date(1990,1,1), min_value=date(1900,1,1), max_value=date.today())
            genero = st.selectbox("¿Cuál es tu género?", ["HOMBRE", "MUJER"])

        st.form_submit_button("Continuar")

        st.subheader("Metas físicas y de bienestar")
        st.markdown("**¿Cuáles son tus metas? Puedes elegir más de una.**")
        c1, c2, c3 = st.columns(3)
        with c1:
            perder_peso   = st.checkbox("Perder Peso")
            tonificar     = st.checkbox("Tonificar / Bajar Grasa")
            masa_muscular = st.checkbox("Aumentar Masa Muscular")
        with c2:
            energia      = st.checkbox("Aumentar Energía")
            rendimiento  = st.checkbox("Mejorar Rendimiento Físico")
            salud        = st.checkbox("Mejorar Salud")
        with c3:
            otros = st.text_input("Otros")

        st.subheader("Análisis de Nutrición y Salud")
        c1, c2 = st.columns(2)
        with c1:
            despierta     = st.text_input("A que hora despiertas?")
            dormir        = st.text_input("A que hora vas a dormir?")
            desayuna      = st.text_input("Tomas desayuno cada mañana?")
            a_que_hora    = st.text_input("A que hora desayunas?")
            que_desayunas = st.text_input("Qué desayunas?")
            agua          = st.text_input("En promedio cuánta agua bebes al día?")
        with c2:
            otras_bebidas = st.text_input("Tomas alguna otra bebida? (Jugos, refrescos, bebidas energéticas, otros)")
            meriendas     = st.text_input("Comes entre comidas?")
            porciones     = st.text_input("Cuantas porciones de frutas y verduras comes al dia?")
            baja_energia  = st.text_input("A que hora del dia sientes menos energia?")
            frecuencia    = st.text_input("Con qué frecuencia te ejercitas?")
            comer_noche   = st.text_input("Tiendes a comer de más por las noches?")
            reto          = st.text_input("Cuál es tu mayor reto respecto a la comida?")
            alcohol       = st.text_input("Cuantas bebidas alcohólicas tomas por semana?")
            gasto_comida  = st.text_input("Cuánto dinero gastas en comida diariamente?")

        enviado = st.form_submit_button("Guardar y continuar ➡️")
        if enviado:
            st.session_state.datos.update({
                "nombre": nombre, "email": email, "movil": movil,
                "fecha_nac": str(fecha_nac), "genero": genero
            })
            st.session_state.metas.update({
                "perder_peso": perder_peso, "tonificar": tonificar, "masa_muscular": masa_muscular,
                "energia": energia, "rendimiento": rendimiento, "salud": salud, "otros": otros
            })
            st.session_state.estilo_vida.update({
                "despierta": despierta, "dormir": dormir, "desayuna": desayuna, "a_que_hora": a_que_hora,
                "que_desayunas": que_desayunas, "agua": agua, "otras_bebidas": otras_bebidas,
                "meriendas": meriendas, "porciones": porciones, "baja_energia": baja_energia,
                "frecuencia": frecuencia, "comer_noche": comer_noche, "reto": reto,
                "alcohol": alcohol, "gasto_comida": gasto_comida
            })
            go(next=True)

# -------------------------------------------------------------
# STEP 2 - Evaluación de Composición Corporal
# -------------------------------------------------------------
def _calcular_edad(fecha_iso: str) -> int:
    try:
        anio = int(str(fecha_iso).split("-")[0])
    except Exception:
        return 30
    return max(16, min(79, date.today().year - anio))

def pantalla2():
    st.header("2) Evaluación de Composición Corporal")

    col = st.columns([2,1,1])
    with col[1]:
        peso_lb = st.number_input("Peso (lb)", min_value=0.0, max_value=900.0, step=0.1,
                                  value=float(st.session_state.get("peso_lb_value", 0.0)))
        if st.button("Convertir a kilogramos"):
            if peso_lb and peso_lb > 0:
                st.session_state["peso_kg_value"] = round(peso_lb * 0.45359237, 2)
                st.session_state["peso_lb_value"]  = float(peso_lb)
                st.success(f"{peso_lb} lb = {st.session_state['peso_kg_value']} kg")

    with col[0]:
        altura_cm = st.number_input("Altura (cm)", min_value=50, max_value=250, step=1,
                                    value=max(50, min(250, int(st.session_state.datos.get("altura_cm", 170)))))
        st.session_state.datos["altura_cm"] = altura_cm
        default_kg = float(st.session_state.get("peso_kg_value", st.session_state.datos.get("peso_kg", 0) or 0))
        peso_kg = st.number_input("Peso (kg)", min_value=0.0, max_value=400.0, step=0.1,
                                  value=float(min(400.0, max(0.0, default_kg))), key="peso_kg_input")
        st.caption("Tip: si tienes libras, usa el conversor para pasar a kg.")
    with col[2]:
        st.write(" ")
        grasa_pct = st.slider("¿Selecciona el % de grasa que más se parece?", 8, 45, 20)

    st.write("### ¿Cuál consideras que es tu % de grasa según la imagen?")
    img_local = load_img("imagen_grasa_corporal.png") or load_img("grasa_ref.png")
    uploaded = st.file_uploader("Sube una imagen de referencia (opcional)", type=["png","jpg","jpeg"])
    if uploaded is not None:
        try:
            img_local = Image.open(uploaded)
        except Exception:
            st.warning("No pude abrir la imagen subida.")
    if img_local:
        st.image(img_local, use_container_width=True)
    else:
        st.caption("Coloca 'imagen_grasa_corporal.png' o 'grasa_ref.png' en esta misma carpeta para mostrar una guía visual.")

    st.divider()
    st.subheader("Resultados")
    st.session_state.datos["altura_cm"] = altura_cm
    st.session_state.datos["peso_kg"]   = peso_kg
    st.session_state.datos["grasa_pct"] = grasa_pct

    edad   = _calcular_edad(st.session_state.datos.get("fecha_nac"))
    genero = st.session_state.datos.get("genero", "HOMBRE")

    imc_val = imc(peso_kg, altura_cm)
    st.metric("IMC", imc_val, help="Peso/(Altura en m)^2")
    st.write(_imc_texto_narrativo(imc_val))
    st.caption("IMC ideal 18.6 – 24.9")

    datos = st.session_state.get('datos', {})
    genero_ref = (datos.get('genero') or 'Hombre')
    fecha_nac  = (datos.get('fecha_nac'))
    edad_ref   = edad_desde_fecha(fecha_nac) or int(datos.get('edad', 30))
    rmin, rmax = _rango_grasa_referencia(genero_ref, edad_ref)
    st.markdown(f"**% GRASA de referencia** para {genero_ref.upper()} y {edad_ref} años: {rmin:.1f}% – {rmax:.1f}%.")

    agua_ml = req_hidratacion_ml(peso_kg)
    prote_g = req_proteina(genero, st.session_state.metas, peso_kg)
    bmr     = bmr_mifflin(genero, peso_kg, altura_cm, edad)

    st.metric("Requerimiento de hidratación (ml/día)", f"{agua_ml:,}")
    st.metric("Requerimiento de proteína (g/día)", f"{prote_g:,}")
    st.metric("Metabolismo en reposo (kcal/día)", f"{bmr:,}")

    st.subheader("Resultado Final")
    meta_masa = st.session_state.metas.get("masa_muscular", False)
    objetivo_kcal = bmr + 250 if meta_masa else bmr - 250
    st.success(
        f"Para alcanzar tu objetivo debes consumir **{agua_ml/1000:.2f} litros de agua**, "
        f"**{prote_g} g de proteína** y mantener tu ingesta diaria de calorías en **{objetivo_kcal:,.0f} kcal/día**."
    )

    st.write("**Referencias útiles:**")
    st.write(comparativos_proteina(prote_g))

    bton_nav()

# -------------------------------------------------------------
# STEP 3 - Estilo de Vida y Objetivos
# -------------------------------------------------------------
def pantalla3():
    st.header("3) Evaluación de Estilo de Vida")

    st.subheader("Hábitos y energía")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("¿En qué momento del día sientes menos energía?", key="ev_menos_energia")
        st.text_input("¿Tomas por lo menos 8 vasos de agua al día?", key="ev_8_vasos")
        st.text_input("¿Practicas actividad física al menos 3 veces/semana?", key="ev_actividad")
        st.text_input("¿Has intentado algo para verte/estar mejor? (Gym, Dieta, App, Otros)", key="ev_intentos")
        st.text_input("¿Qué es lo que más se te complica? (Constancia, Alimentación, Motivación, Otros)", key="ev_complica")
    with c2:
        st.write("Presentas alguna de las siguientes condiciones?")
        cols = st.columns(2)
        with cols[0]:
            estre       = st.checkbox("¿Estreñimiento?")
            colesterol  = st.checkbox("¿Colesterol Alto?")
            baja_ene    = st.checkbox("¿Baja Energía?")
            dolor_musc  = st.checkbox("¿Dolor Muscular?")
            gastritis   = st.checkbox("¿Gastritis?")
            hemorroides = st.checkbox("¿Hemorroides?")
        with cols[1]:
            hta         = st.checkbox("¿Hipertensión?")
            dolor_art   = st.checkbox("¿Dolor Articular?")
            ansiedad    = st.checkbox("¿Ansiedad por comer?")
            jaquecas    = st.checkbox("¿Jaquecas / Migrañas?")
            diabetes_fam= st.checkbox("Diabetes (antecedentes familiares)")

    # Guardar flags de P3
    st.session_state.p3_estrenimiento                      = bool(estre)
    st.session_state.p3_colesterol_alto                    = bool(colesterol)
    st.session_state.p3_baja_energia                       = bool(baja_ene)
    st.session_state.p3_dolor_muscular                     = bool(dolor_musc)
    st.session_state.p3_gastritis                          = bool(gastritis)
    st.session_state.p3_hemorroides                        = bool(hemorroides)
    st.session_state.p3_hipertension                       = bool(hta)
    st.session_state.p3_dolor_articular                    = bool(dolor_art)
    st.session_state.p3_ansiedad_por_comer                 = bool(ansiedad)
    st.session_state.p3_jaquecas_migranas                  = bool(jaquecas)
    st.session_state.p3_diabetes_antecedentes_familiares   = bool(diabetes_fam)

    st.subheader("Objetivos")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("¿Qué talla te gustaría ser?", key="obj_talla")
        st.text_input("¿Qué partes del cuerpo te gustaría mejorar?", key="obj_partes")
        st.text_input("¿Qué tienes en tu ropero para usar como meta?", key="obj_ropero")
    with c2:
        st.text_input("¿Cómo te beneficia alcanzar tu meta?", key="obj_beneficio")
        st.text_input("¿Qué eventos tienes en los próximos 3 o 6 meses?", key="obj_eventos")
        st.text_input("Del 1 al 10, ¿cuál es tu nivel de compromiso para alacanzar una mejor versión de ti?", key="obj_compromiso")

    st.subheader("Análisis de presupuesto")
    col = st.columns(4)
    with col[0]:
        g_comida  = st.number_input("Cuanto gastas diariamente en comida? (S/.)", min_value=0.0, step=0.1, key="presu_comida")
    with col[1]:
        g_cafe    = st.number_input("Cuanto gastas al dia en cafe? (S/.)", min_value=0.0, step=0.1, key="presu_cafe")
    with col[2]:
        g_alcohol = st.number_input("Cuanto gastas a la semana en alcohol? (S/.)", min_value=0.0, step=0.1, key="presu_alcohol")
    with col[3]:
        g_deliv   = st.number_input("Cuanto gastas a la semana en deliveries/salidas a comer? (S/.)", min_value=0.0, step=0.1, key="presu_deliveries")

    prom_diario = round((g_comida + g_cafe + (g_alcohol/7.0) + (g_deliv/7.0)), 2)
    st.metric("Promedio de gastos diarios (S/.)", f"{prom_diario:.2f}")

    bton_nav()

# -------------------------------------------------------------
# STEP 4 - Valoración de Servicio
# -------------------------------------------------------------
def emoji_y_texto(n):
    if n <= 0: return "😡", "PÉSIMO"
    if n == 1: return "😠", "NO ME GUSTÓ"
    if n == 2: return "😐", "ME GUSTÓ POCO"
    if n == 3: return "🙂", "ME GUSTÓ"
    if n == 4: return "😁", "ME GUSTÓ MUCHO"
    return "🤩", "ME ENCANTÓ"

def pantalla4():
    st.header("4) Valoración de Servicio")
    st.write("La empresa valora la calidad de mi servicio según la cantidad de personas a las cuales **les quieres regalar la misma evaluación**. 1 significa que no te gusto, 5 significa que te encantó.")

    if "valoracion_contactos" not in st.session_state:
        st.session_state.valoracion_contactos = []

    with st.form("add_ref"):
        cols = st.columns([2,1,1,1])
        with cols[0]:
            nombre   = st.text_input("¿A quién te gustaría regalarle esta evaluación?")
        with cols[1]:
            telefono = st.text_input("¿Cuál es su número de teléfono?")
        with cols[2]:
            distrito = st.text_input("¿Distrito?")
        with cols[3]:
            relacion = st.text_input("¿Qué relación tienen?")
        if st.form_submit_button("Agregar") and nombre:
            st.session_state.valoracion_contactos.append({
                "nombre": nombre, "telefono": telefono, "distrito": distrito, "relacion": relacion
            })

    if st.session_state.valoracion_contactos:
        st.table(st.session_state.valoracion_contactos)

    n = min(len(st.session_state.valoracion_contactos), 5)
    cara, texto = emoji_y_texto(n)
    st.markdown(f"### {cara}  {texto}")

    st.divider()
    st.write("**Finalmente ¿Te gustaría que te explique cómo, a través de la comunidad, podemos ayudarte a alcanzar los objetivos que te has propuesto?**")

    bton_nav()

# -------------------------------------------------------------
# STEP 5 - Quiénes somos (Títulos resaltados + viñetas)
# -------------------------------------------------------------
def show_img(filename: str, caption: str = ""):
    p = (APP_DIR / filename)
    if p.exists():
        try:
            img = Image.open(p)
            st.image(img, caption=caption if caption else None, use_container_width=True)
        except Exception as e:
            st.warning(f"No pude abrir '{filename}': {e}")
    else:
        st.warning(f"(Falta imagen: {filename})")

def pantalla5():
    st.header("5) Quiénes somos")
    st.write(
        "Somos **Fitclub**, una comunidad que educa a las personas en hábitos saludables de vida para que puedan alcanzar resultados "
        "de bienestar y puesta en forma, y sostenerlos para siempre.\n\n"
        "Contamos con una comunidad con más de 10,000 personas con resultados más allá de sus expectativas iniciales. "
        "A continuación te voy a mostrar algunos testimonios de nuestra comunidad."
    )
    st.subheader("Testimonios")

    st.markdown("""
        <style>
        .testi-title{
            font-weight: 800;
            font-size: 1.2rem;
            margin: 8px 0 2px 0;
        }
        .testi-box{
            margin-bottom: 18px;
        }
        </style>
    """, unsafe_allow_html=True)

    testimonios = [
        ("jessiyroi.jpg","Jessi y Roi — Padres de 3",
         ["Roi **+8 kg** de masa muscular.",
          "Jessi **−14 kg** post parto en 3 meses.",
          "Energía para jugar y disfrutar de sus hijos."]),
        ("alexisylyn.jpg","Alexis y Lyn — Recomposición corporal",
         ["Alexis **74 kg** en ambas fotos.",
          "Lyn **60 kg** en ambas fotos.",
          "Mejora notable en tono muscular y composición."]),
        ("nicolasyscarlett.jpg","Nicolás y Scarlett — 18 años",
         ["Nicolás **+20 kg** de masa muscular.",
          "Scarlett **+14 kg** de masa muscular.",
          "Acompañamiento nutricional y de entrenamiento."]),
        ("wagnerysonia.jpg","Wagner y Sonia — Tercera edad",
         ["Sonia tenia problemas de salud y dolor en las rodillas y talones.",
          "Solo le recetaban calmantes y inyecciones argumentando que eran problemas de la edad.",
          "Controlo 12kg a los 2 meses de sumarse a la comunidad",
          "Mejoro salud, se fueron los dolores y se llenó de energia."]),
        ("mayraymariaantonieta.jpg","Mayra y María Antonieta — Hipotiroidismo",
         ["Ambas pensaban que por su condición no podian tener resultados",
          "Mayra **-20kg** de grasa.",
          "Maria Antonieta **-15kg** de grasa."]),
        ("reynaldoyandreina.jpg","Reynaldo y Andreina — Padres de 4 y prediabéticos",
         ["Andreina **−15 kg** post cesárea de mellizos.",
          "Reynaldo intento todas las dietas sin tener resultado.",
          "Perdia peso temporalmente y luego lo recuperaba",
          "Controló 25kg con la comunidad los cuales sostiene hasta ahora."]),
        ("aldoycristina.jpg","Aldo y Cristina — Sin tiempo",
         ["Aldo, arquitecto se amanecia en la oficina.",
          "Controló **25kg**.",
          "Cristina es doctora y tenia turnos de 24 a 48 horas",
          "Su alimentación era muy desordenada.",
          "Controló **12 kg** de grasa."]),
    ]

    for fname, titulo, bullets in testimonios:
        st.divider()
        show_img(fname)
        st.markdown(f"<div class='testi-box'><div class='testi-title'>{titulo}</div></div>", unsafe_allow_html=True)
        for txt in bullets:
            st.markdown(f"- {txt}")
        st.write("")

    bton_nav()

# -------------------------------------------------------------
# STEP 6 - Plan Personalizado (recomendaciones + PRECIOS + SELECCIÓN + cuenta regresiva)
# -------------------------------------------------------------
def pantalla6():
    st.header("6) Plan Personalizado")

    st.write(
        "Para asegurar estos resultados nos apoyamos en la nutrición celular del Batido de Herbalife. "
        "El cual nos permite cubrir deficiencias nutricionales de nuestro día a día de manera rica, rápida y práctica."
    )

    hay = any(st.session_state.get(k, False) for k in P3_FLAGS)
    if hay:
        st.write(
            "Adicionalmente, según lo que conversamos te voy a recomendar algunos productos que pueden ayudarte "
            "a cubrir de manera específica las necesidades que me compartiste."
        )
        if st.session_state.get("p3_estrenimiento", False):
            st.write("• Para ayudarte con el estreñimiento y tengas una salud digestiva adecuada está la **fibra con sabor a manzana** para que todo te salga bien.")
        if st.session_state.get("p3_colesterol_alto", False):
            st.write("• Para mejorar tus niveles de colesterol nos apoyamos del **Herbalifeline**, unas cápsulas de concentrado de **omega 3** con sabor a menta y tomillo. Riquísimas.")
        if st.session_state.get("p3_baja_energia", False):
            st.write("• Con el **té concentrado de hierbas** y su efecto termogénico puedes disparar tus niveles de energía y de paso quemar unas calorías extra al día. Si lo combinas con el **NRG** vas a estar totalmente lúcida y enérgica en cuerpo y mente.")
        if st.session_state.get("p3_dolor_muscular", False):
            st.write("• Para el dolor muscular se recomienda una buena ingesta de **proteína**, por lo cual el **PDM** resulta ideal al sumar de 9 a 18 g adicionales según tus requerimientos.")
        if st.session_state.get("p3_gastritis", False):
            st.write("• Para la **gastritis**, el **reflujo** y similares, el **aloe** es el indicado. Desinflama, cicatriza y alivia todo el tracto digestivo y mejora la absorción de nutrientes.")
        if st.session_state.get("p3_hemorroides", False):
            st.write("• Para la gastritis, el reflujo, **hemorroides** y similares, el **aloe** es el indicado. Desinflama, cicatriza y alivia todo el tracto digestivo y mejora la absorción de nutrientes.")
        if st.session_state.get("p3_hipertension", False):
            st.write("• Para ayudarte con la **hipertensión** te recomiendo el **Beta Heart** que contiene **betaglucanos de avena** que ayudan a reducir el colesterol malo.")
        if st.session_state.get("p3_dolor_articular", False):
            st.write("• Para el **dolor articular** está el **Golden Beverage**, una bebida de **cúrcuma** ideal para desinflamar las articulaciones.")
        if st.session_state.get("p3_ansiedad_por_comer", False):
            st.write("• La **ansiedad por comer** es síntoma de un déficit en la ingesta de proteína diaria. El **PDM** y el **Beverage** son ideales para aportar de 15 a 18 g adicionales al día y generar sensación de saciedad y control de antojos.")
        if st.session_state.get("p3_jaquecas_migranas", False):
            st.write("• Para ayudarte a aliviar las **jaquecas/migranas**, el **NRG** contiene la dosis ideal de cafeína natural de la **guaraná**, además de brindarte lucidez mental.")
        if st.session_state.get("p3_diabetes_antecedentes_familiares", False):
            st.write("• Para ayudar con la **diabetes** recomendamos el **Beta Heart**, bebida **alta en fibra** que permite reducir el índice glucémico de nuestra alimentación.")
        st.write("")

    st.divider()
    st.subheader("Servicio")
    st.write(
        "**Durante los primeros 10 dias vamos a trabajar muy de cerca contigo, son dias clave para construir tus resultados y hábitos sostenibles.** "
        "Tendrás **citas diarias de coaching y seguimiento personalizado** para ayudarte a establecer los hábitos que viniste a desarrollar. "
        "Nos reuniremos cada dia para revisar tu diario de comidas, con el objetivo de ayudarte a tomar conciencia de tu alimentación y a reconocer "
        "como lo que comes impacta en como te sientes. "
        "Sabemos que en los primeros dias es cuando los hábitos antiguos presentan mayor resistencia. Por eso "
        "**el acompañamiento diario es fundamental para sostener el enfoque, aclarar dudas y ajustar lo que sea necesario en tiempo real.** "
        "No estaras solo: estamos aqui para guiarte paso a paso desde el inicio."
    )
    st.write(
        "**Además, contarás con herramientas clave para acompañar tu proceso**: "
        "Herramientas para conocer tus requerimientos diarios de **proteína** e **hidratación**. "
        "Un **tracker de alimentación diaria** para ayudarte a mantener el enfoque y medir tu progreso. "
        "**Recomendaciones de alimentos** alineadas con tus objetivos personales."
    )
    st.write(
        "También tendrás: "
        "**Acceso a nuestros grupos de soporte y compromiso**, donde compartimos motivación, aprendizajes y acompañamiento con otros miembros. "
        "**Ingreso a nuestra plataforma de entrenamientos**, tanto presenciales como virtuales, para que puedas moverte y activarte desde donde estés."
    )
    st.write(
        "Todos los productos tienen del 5 al 10% de descuento según la cantidad que elijas para empezar tu programa por las próximas 48 horas. "
        "Entonces, ¿Con qué programa te permites empezar?"
    )

    # Cuenta regresiva de 48 horas
    _init_promo_deadline()
    _render_countdown()

    # Bloque de precios + selección
    mostrar_opciones_pantalla6()

    bton_nav()

# -------------------------------------------------------------
# Side Nav
# -------------------------------------------------------------
def sidebar_nav():
    with st.sidebar:
        st.title("APP EVALUACIONES")
        for i, titulo in [
            (1, "Perfil de Bienestar"),
            (2, "Composición Corporal"),
            (3, "Estilo de Vida"),
            (4, "Valoración"),
            (5, "Quiénes somos"),
            (6, "Plan Personalizado"),
        ]:
            if st.button(f"{i}. {titulo}", use_container_width=True):
                go(to=i)

        st.markdown("---")
        st.markdown("**Selección actual (debug):**")
        st.write(st.session_state.get("combo_elegido"))

# -------------------------------------------------------------
# Main
# -------------------------------------------------------------
def main():
    init_state()
    sidebar_nav()
    s = st.session_state.step
    if s == 1: pantalla1()
    elif s == 2: pantalla2()
    elif s == 3: pantalla3()
    elif s == 4: pantalla4()
    elif s == 5: pantalla5()
    elif s == 6: pantalla6()

if __name__ == "__main__":
    main()
