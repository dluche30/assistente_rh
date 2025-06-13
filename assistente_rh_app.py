import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# ======== CONFIGURAÇÕES DE AMBIENTE ========
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ======== AUTENTICAÇÃO GOOGLE SHEETS ========
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gsheet = gspread.authorize(creds)
sheet = client_gsheet.open("chat_logs_rh").sheet1

# ======== CONFIGURAÇÕES DE PÁGINA ========
st.set_page_config(page_title="Assistente de Recrutamento IA", layout="wide")

# ======== ESTILO ========
st.markdown("""
    <style>
        .reportview-container {
            background: #f7f9fc;
        }
        .stChatInput input {
            border: 2px solid #4b8bbe;
            border-radius: 8px;
        }
        .stChatMessage {
            background-color: #ffffff;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .stButton>button {
            background-color: #4b8bbe;
            color: white;
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# ======== CABEÇALHO ========
st.title("🤖 Assistente Virtual de Recrutamento com IA")
st.markdown("Bem-vindo! Este assistente usa IA para ajudar na triagem e orientação profissional. Seja claro em suas perguntas ou descreva seu perfil para receber sugestões.")

# ======== IDENTIFICAÇÃO DO USUÁRIO ========
if "usuario" not in st.session_state:
    st.session_state.usuario = ""

if not st.session_state.usuario:
    st.session_state.usuario = st.text_input("🔑 Digite seu nome ou RA para iniciar:", key="user_input")
    st.stop()

# ======== HISTÓRICO DE CONVERSA ========
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ======== INPUT DO USUÁRIO ========
prompt = st.chat_input("🗣️ Escreva aqui sua dúvida ou apresente seu perfil...")

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
            "Analise perfis com base em competências e experiências. Incentive o autoconhecimento e ofereça feedback construtivo. "
            "Peça mais informações se necessário e evite julgamentos definitivos."
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
