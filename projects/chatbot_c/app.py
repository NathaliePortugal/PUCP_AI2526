import os
import requests
import unicodedata
import urllib.parse

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
# Cargar variables de entorno (.env)
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER")

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "data" / "procedimientos.xlsx"
#SYSTEM_PROMPT_PATH = "systemprompt.txt"
SYSTEM_PROMPT_PATH = BASE_DIR / "systemprompt.txt"



if not EXCEL_PATH.exists():
    st.error(f"No se encuentra el Excel en: {EXCEL_PATH}")
    st.stop()

# ---------- Utilidades ----------
def cargar_system_prompt():
    if not SYSTEM_PROMPT_PATH.exists():
        return (
            f"Error: no se encontró el archivo systemprompt.txt en "
            f"{SYSTEM_PROMPT_PATH}"
        )
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

def normalizar(texto: str) -> str:
    """Pasa a minúsculas y quita acentos para comparar mejor."""
    if not isinstance(texto, str):
        return ""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto


def cargar_system_prompt(path: str = SYSTEM_PROMPT_PATH) -> str:
    """Lee el prompt del sistema desde un archivo de texto."""
    if not os.path.exists(path):
        return (
            "Error: no se encontró el archivo systemprompt.txt. "
            "Por favor crea ese archivo en el mismo directorio que app.py."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = cargar_system_prompt()

@st.cache_data
def cargar_datos():
    """Lee el Excel y construye una columna de contexto textual por fila."""
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"No se encontró el archivo: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)
    # Aseguramos que algunas columnas existan aunque estén vacías
    for col in [
        "Procedimiento", "Categoria", "Descripcion", "Beneficios",
        "Indicaciones", "Contraindicaciones", "Duracion_aprox",
        "Sesiones_recomendadas", "Precio_referencial", "Cuidados_antes",
        "Cuidados_despues", "Notas", "Keywords"
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df.fillna("")

    # Creamos una columna texto_contexto con toda la info útil de la fila
    def construir_texto(row):
        return (
            f"Procedimiento: {row['Procedimiento']}\n"
            f"Categoría: {row['Categoria']}\n"
            f"Descripción: {row['Descripcion']}\n"
            f"Beneficios: {row['Beneficios']}\n"
            f"Indicaciones: {row['Indicaciones']}\n"
            f"Contraindicaciones: {row['Contraindicaciones']}\n"
            f"Duración aproximada: {row['Duracion_aprox']}\n"
            f"Sesiones recomendadas: {row['Sesiones_recomendadas']}\n"
            f"Precio referencial: {row['Precio_referencial']}\n"
            f"Cuidados antes: {row['Cuidados_antes']}\n"
            f"Cuidados después: {row['Cuidados_despues']}\n"
            f"Notas: {row['Notas']}\n"
        )

    df["texto_contexto"] = df.apply(construir_texto, axis=1)

    return df


def construir_contexto(
    df: pd.DataFrame,
    pregunta: str,
    max_filas: int = 5,
    contexto_anterior: str | None = None,
    procedimiento_anterior: str | None = None,
):
    pregunta_norm = normalizar(pregunta)

    # ✅ Si es follow-up y tenemos procedimiento anterior: NO re-buscar, reutilizar
    if es_followup(pregunta_norm) and contexto_anterior and procedimiento_anterior:
        return contexto_anterior, procedimiento_anterior, False  # False = no es match nuevo fuerte

    palabras = [p for p in pregunta_norm.split() if len(p) > 2]

    filas_puntuadas = []
    for _, row in df.iterrows():
        texto = row["texto_contexto"]
        keywords = str(row.get("Keywords", ""))
        texto_busqueda = normalizar(texto) + " " + normalizar(keywords)

        score = sum(1 for p in palabras if p in texto_busqueda)
        if score > 0:
            filas_puntuadas.append((score, texto, row.get("Procedimiento", "")))

    if not filas_puntuadas:
        # Si no hay match, pero teníamos contexto, reusarlo (sirve para "¿y riesgos?")
        if contexto_anterior and procedimiento_anterior:
            return contexto_anterior, procedimiento_anterior, False
        filas = df["texto_contexto"].tolist()
        return "\n\n---\n\n".join(filas[:max_filas]), None, False

    filas_puntuadas.sort(key=lambda x: x[0], reverse=True)
    mejores = filas_puntuadas[:max_filas]
    contexto = "\n\n---\n\n".join([t for s, t, p in mejores])
    procedimiento_actual = mejores[0][2]

    # ✅ Definimos "match fuerte" cuando score es suficientemente alto
    # (evita que "procedimiento" haga switch de tema)
    score_top = mejores[0][0]
    match_fuerte = score_top >= 2  # puedes subir a 3 si tu Excel es grande

    return contexto, procedimiento_actual, match_fuerte


def construir_user_prompt(contexto: str, pregunta: str, procedimiento_actual: str = None) -> str:
    """
    Prompt del usuario que incluye contexto del Excel
    y, si existe, el procedimiento actual.
    """

    extra = ""
    if procedimiento_actual:
        extra = f"""
Esta pregunta es un SEGUIMIENTO sobre el procedimiento llamado: "{procedimiento_actual}".

- Interpreta que el cliente sigue hablando de ese procedimiento,
  salvo que explícitamente mencione otro.
"""

    prompt = f"""
A continuación tienes información de un archivo Excel del centro de estética.
Usa EXCLUSIVAMENTE esta información para responder.

Contexto del Excel:
-------------------
{contexto}

{extra}

Pregunta del cliente:
---------------------
{pregunta}

Instrucciones:
- Si la respuesta está en el contexto, respóndela de forma clara.
- Si no ves la información exacta en el contexto, dilo explícitamente.
- Si no puedes responder con certeza, ofrece derivar al cliente a un asesor humano por WhatsApp.
"""

    return prompt


def es_followup(pregunta: str) -> bool:
    p = normalizar(pregunta)
    disparadores = [
        "ese", "esa", "eso", "ese procedimiento", "ese tratamiento",
        "sobre ese", "sobre eso", "sobre el", "sobre la",
        "dame mas info", "dame mas informacion", "mas informacion",
        "cuanto dura", "que riesgos", "riesgos", "contraindicaciones",
        "cuidados", "precio", "costo", "recuperacion", "postoperatorio"
    ]
    return any(d in p for d in disparadores)

def recortar(texto: str, max_chars: int) -> str:
    return str(texto or "")[:max_chars]


def llamar_llm_groq(system_prompt: str, user_prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": str(system_prompt or "")},
            {"role": "user", "content": str(user_prompt or "")},
        ],
        "temperature": 0.1,
        # usa max_tokens (más compatible). Si tu cuenta soporta max_completion_tokens, ok,
        # pero max_tokens suele evitar 400 por parámetro.
        "max_tokens": 600,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    if resp.status_code >= 400:
        # 🔥 Aquí está la explicación real del 400
        raise RuntimeError(f"Groq {resp.status_code} -> {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def construir_link_whatsapp(mensaje_por_defecto: str) -> str:
    numero = WHATSAPP_NUMBER or "51999999999"
    texto = urllib.parse.quote(mensaje_por_defecto)
    return f"https://wa.me/{numero}?text={texto}"


def detectar_solicitud_humano(texto: str) -> bool:
    texto = (texto or "").lower()
    disparadores = [
        "hablar con un humano",
        "hablar con una persona",
        "asesor humano",
        "asesor",
        "humano",
        "asesor por whatsapp",
        "whatsapp",
        "quiero hablar con alguien",
        "atención personalizada",
        "atencion personalizada",
    ]
    return any(d in texto for d in disparadores)

def llamar_llm_groq_debug(system_prompt: str, user_prompt: str):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": str(system_prompt or "")},
            {"role": "user", "content": str(user_prompt or "")},
        ],
        "temperature": 0.1,
        "max_tokens": 600,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    # Devuelve TODO para inspección
    return {
        "status_code": resp.status_code,
        "text": resp.text[:2000],   # recortado
    }

def main():
    st.set_page_config(page_title="Chatbot Estética", page_icon="⚕️")
    st.title("⚕️ Chatbot Centro de Estética")

    if not GROQ_API_KEY:
        st.error("Falta GROQ_API_KEY en el archivo .env")
        st.stop()

    if not os.path.exists(EXCEL_PATH):
        st.error(f"No se encuentra el Excel en: {EXCEL_PATH}")
        st.stop()

    try:
        df = cargar_datos()
    except Exception as ex:
        st.error(f"Error cargando el Excel: {ex}")
        st.stop()

    with st.expander("Ver tabla de procedimientos (Excel)", expanded=False):
        st.dataframe(df)

    with st.expander("Ver system prompt cargado", expanded=False):
        st.text(SYSTEM_PROMPT)

    # ----- Estado -----
    if "historial" not in st.session_state:
        st.session_state["historial"] = []

    if "ultimo_contexto" not in st.session_state:
        st.session_state["ultimo_contexto"] = None

    if "ultimo_procedimiento" not in st.session_state:
        st.session_state["ultimo_procedimiento"] = None

    # ----- Mostrar historial -----
    st.subheader("Chat")
    for rol, texto in st.session_state["historial"]:
        if rol == "usuario":
            with st.chat_message("user"):
                st.markdown(texto)
        else:
            with st.chat_message("assistant"):
                st.markdown(texto)

    # ----- Input chat -----
    user_message = st.chat_input("Escribe tu pregunta sobre nuestros procedimientos:")

    if user_message:
        # Guardar mensaje del usuario
        st.session_state["historial"].append(("usuario", user_message))

        contexto_anterior = st.session_state.get("ultimo_contexto")
        procedimiento_anterior = st.session_state.get("ultimo_procedimiento")

        # ✅ Construir contexto UNA sola vez (devuelve 2 valores)
        contexto, procedimiento_actual, match_fuerte = construir_contexto(
            df,
            user_message,
            contexto_anterior=contexto_anterior,
            procedimiento_anterior=procedimiento_anterior,
        )
        # Guardar estado
        st.session_state["ultimo_contexto"] = contexto
        if match_fuerte and procedimiento_actual:
            st.session_state["ultimo_procedimiento"] = procedimiento_actual


        procedimiento_para_prompt = st.session_state.get("ultimo_procedimiento")
        user_prompt = construir_user_prompt(contexto, user_message, procedimiento_para_prompt)

        with st.expander("DEBUG (prompt sizes / types)", expanded=False):
            st.write({
                "SYSTEM_PROMPT_type": type(SYSTEM_PROMPT).__name__,
                "contexto_type": type(contexto).__name__,
                "user_prompt_type": type(user_prompt).__name__,
                "SYSTEM_PROMPT_len": len(SYSTEM_PROMPT or ""),
                "contexto_len": len(contexto or ""),
                "user_prompt_len": len(user_prompt or ""),
            })
            st.write("user_message:", user_message)
            st.write("procedimiento_para_prompt:", procedimiento_para_prompt)
        

        # Llamar al modelo y mostrar respuesta
        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()
            thinking_placeholder.info("💭 El asesor está revisando tu consulta...")

            with st.spinner("El asesor está analizando tu consulta..."):
                # ✅ Incluir procedimiento para follow-up
                SYSTEM_PROMPT_CORTO = recortar(SYSTEM_PROMPT, 4000)
                contexto = recortar(contexto, 7000)
                user_prompt = construir_user_prompt(contexto, user_message, procedimiento_para_prompt)
                user_prompt = recortar(user_prompt, 12000)
                try:
                    debug_resp = llamar_llm_groq(SYSTEM_PROMPT_CORTO, user_prompt)
                    #debug_resp = llamar_llm_groq_debug(SYSTEM_PROMPT_CORTO, user_prompt)
                    
                    with st.expander("DEBUG (Groq response)", expanded=False):
                        st.write(debug_resp)

                    if debug_resp["status_code"] != 200:
                        respuesta = f"Error Groq: {debug_resp['status_code']} -> {debug_resp['text']}"
                    else:
                        # Si fue 200, parseamos JSON
                        data = requests.models.complexjson.loads(debug_resp["text"])
                        respuesta = data["choices"][0]["message"]["content"]
                except Exception as ex:
                    respuesta = f"Ocurrió un error al llamar al modelo: {ex}"

            thinking_placeholder.empty()
            st.markdown(respuesta)

        st.session_state["historial"].append(("bot", respuesta))

    # ----- WhatsApp -----
    mostrar_boton_whatsapp = any(
        rol == "usuario" and detectar_solicitud_humano(texto)
        for rol, texto in st.session_state["historial"]
    )

    if mostrar_boton_whatsapp:
        st.markdown("---")
        st.subheader("Hablar con un asesor humano")
        mensaje_defecto = "Hola, quiero más información sobre los procedimientos del centro de estética."
        link_wa = construir_link_whatsapp(mensaje_defecto)
        st.markdown(f"[💬 Abrir WhatsApp para hablar con un asesor]({link_wa})", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
