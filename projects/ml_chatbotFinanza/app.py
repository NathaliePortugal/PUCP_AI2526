import streamlit as st
import os
import requests
from dotenv import load_dotenv

# region Funciones
def consultar_groq(prompt_usuario, historial):
    url = "https://api.groq.com/openai/v1/chat/completions"
    # Mantener solo los últimos 5 mensajes del historial
    historial_reciente = historial[-5:] if len(historial) > 5 else historial

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [prompt_sistema] + historial_reciente + [{"role":"user","content":prompt_usuario}]
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error {response.status_code}: {response.text}"

# endregion

# region Configuraciones Generales

st.set_page_config(page_title="Asistente Financiero", page_icon="💵")
st.title("💵 Chatbot de Aprendizaje de Finanzas Personales")

# --- CSS personalizado ---
st.markdown("""
<style>
.user-message {
    background-color: #C2F0C2;
    color: #000000;
    padding: 10px;
    border-radius: 10px;
    margin: 5px 0;
}
.bot-message {
    background-color: #B3E5FC; 
    color: #000000;
    padding: 10px;
    border-radius: 10px;
    margin: 5px 0;
}
</style>
""", unsafe_allow_html=True)

#Cargando la clave para conectar con la AI
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# endregion

# region Prompt Sistema (Contexto Financiero)

prompt_sistema = {
    "role" : "system",
    "content" : (
        "Eres un asistente experto en educacion financiera."
        "Explica conceptos de ahorro, inversion, presupuesto, deudas y economia domestica."
        "Usa un lenguaje claro y amable. Nunca des consejos de inversion personalizada ni"
        "recomendaciones de compra o venta."
        "Se educativo y practico. Usa ejemplos simples para que las respuestas sean mas claras"
    ),
}

# endregion


# region Cargar Historial
#st.session_state es para mantener el historial
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

#Mostrando los mensajes anteriores
for msg in st.session_state.mensajes:
    #st.chat_message(msg["role"]).markdown(msg["context"])
    if msg["role"] == "user":
        st.chat_message("user", avatar="🤓").markdown(f"<div class='user-message'><b>Tú:</b> {msg['content']}</div>",
            unsafe_allow_html=True)
    else:
        st.chat_message("assistant", avatar="🧙🏻‍♂️").markdown(f"<div class='bot-message'><b>Asistente:</b> {msg['content']}</div>",
            unsafe_allow_html=True)

# endregion




# region Entrada del usuario
#:= se llama walrus operator = Guarda el valor que el usuario escribió en prompt, y si no está vacío, ejecuta el bloque
if prompt := st.chat_input("Escribe tu pregunta sobre Finanzas ..."):
    #Guardamos el msg del usuario
    st.session_state.mensajes.append({"role":"user","content":prompt})
    st.chat_message("user", avatar="🤓").markdown(
        f"<div class='user-message'><b>Tú:</b> {prompt}</div>",
        unsafe_allow_html=True
    )
    st.session_state.mensajes.append({
        "role" : "user",
        "content" : prompt
    })
    
    with st.chat_message("assistant", avatar="🧙🏻‍♂️"):
        placeholder = st.empty()
        placeholder.markdown("<div class='bot-message'>💭 Estoy pensando...</div>", unsafe_allow_html=True)

        respuesta = consultar_groq(prompt, st.session_state.mensajes)

        # Reemplazar el placeholder con la respuesta real
        placeholder.markdown(
            f"<div class='bot-message'><b>Asistente:</b> {respuesta}</div>",
            unsafe_allow_html=True
        )

    
    st.session_state.mensajes.append({"role":"assistant","content":respuesta})

# endregion