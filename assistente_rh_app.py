import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import csv
from datetime import datetime

# Carregar chave da OpenAI
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Assistente RH com IA", layout="wide")
st.title("🤖 Assistente Virtual de Recrutamento")

# Identificação do usuário
if "usuario" not in st.session_state:
    st.session_state.usuario = ""

if not st.session_state.usuario:
    st.session_state.usuario = st.text_input("Digite seu nome ou RA para iniciar:", key="user_input")
    st.stop()

# Inicializar histórico da conversa
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Caminho para o log CSV
LOG_FILE = "chat_logs.csv"

def salvar_log(usuario, prompt, resposta):
    with open(LOG_FILE, mode="a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now(), usuario, prompt, resposta])

# Mostrar histórico
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada do usuário
prompt = st.chat_input("Descreva seu perfil ou faça uma pergunta sobre recrutamento...")

if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Preâmbulo
    system_message = {
        "role": "system",
        "content": (
            "Você é um assistente de RH especializado em triagem de currículos e orientação profissional. "
            "Analise perfis profissionais com base em competências, experiências e alinhamento com áreas específicas. "
            "Evite julgamentos definitivos, incentive o autoconhecimento e ofereça feedback construtivo. "
            "Seja cordial e objetivo. Em caso de dados insuficientes, peça mais informações ao usuário."
        )
    }

    messages = [system_message] + st.session_state.chat_history

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        reply = response.choices[0].message.content
        st.chat_message("assistant").markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        salvar_log(st.session_state.usuario, prompt, reply)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
