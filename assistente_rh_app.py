import streamlit as st
import openai
import os
from dotenv import load_dotenv

# Carregar chave da OpenAI
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="Assistente RH com IA", layout="wide")
st.title("🤖 Assistente Virtual de Recrutamento")

# Inicializar histórico da conversa
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Mostrar histórico
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada do usuário
prompt = st.chat_input("Descreva seu perfil ou faça uma pergunta sobre recrutamento...")

if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Preâmbulo (instruções fixas para o modelo)
    system_message = {
        "role": "system",
        "content": (
            "Você é um assistente de RH especializado em triagem de currículos e orientação profissional. "
            "Analise perfis profissionais com base em competências, experiências e alinhamento com áreas específicas. "
            "Evite julgamentos definitivos, incentive o autoconhecimento e ofereça feedback construtivo. "
            "Seja cordial e objetivo. Em caso de dados insuficientes, peça mais informações ao usuário."
        )
    }

    # Histórico para envio ao modelo
    messages = [system_message] + st.session_state.chat_history

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        reply = response["choices"][0]["message"]["content"]
        st.chat_message("assistant").markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
