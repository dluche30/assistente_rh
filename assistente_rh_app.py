import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# Carregar chave da OpenAI
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Autenticar com o Google Sheets via st.secrets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gsheet = gspread.authorize(creds)
sheet = client_gsheet.open("chat_logs_rh").sheet1  # Nome da planilha

# Interface Streamlit
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

# Mostrar histórico
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada do usuário
prompt = st.chat_input("Descreva seu perfil ou faça uma pergunta sobre recrutamento...")

def salvar_no_google_sheets(usuario, prompt, resposta):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, usuario, prompt, resposta])

if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

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
        salvar_no_google_sheets(st.session_state.usuario, prompt, reply)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")
