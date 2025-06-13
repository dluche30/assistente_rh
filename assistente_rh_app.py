import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import gspread
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# ======== CONFIGURAR API OPENAI ========
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ======== AUTENTICAÇÃO GOOGLE SHEETS ========
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client_gsheet = gspread.authorize(creds)
sheet = client_gsheet.open("chat_logs_rh").sheet1

# ======== CONFIGURAR INTERFACE ========
st.set_page_config(page_title="Assistente RH + UNESP", layout="wide")
st.image("logo_unesp.png", width=160)
st.title("🤖 Assistente Virtual de Recrutamento (UNESP)")
st.markdown("Este assistente utiliza IA para comparar seu perfil com vagas disponíveis e sugerir a mais compatível.")

# ======== IDENTIFICAÇÃO DO USUÁRIO ========
if "usuario" not in st.session_state:
    st.session_state.usuario = ""

if not st.session_state.usuario:
    st.session_state.usuario = st.text_input("🔑 Digite seu nome ou RA para iniciar:", key="user_input")
    st.stop()

# ======== HISTÓRICO DE CONVERSA ========
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ======== CARREGAR ARQUIVO DE VAGAS ========
vagas_path = "vagas_exemplo.csv"
if os.path.exists(vagas_path):
    df_vagas = pd.read_csv(vagas_path)
    lista_vagas = "\n".join([f"- {row['cargo']}: {row['requisitos']}" for _, row in df_vagas.iterrows()])
else:
    lista_vagas = "Nenhuma vaga disponível no momento."

# ======== MOSTRAR CONVERSAS ANTERIORES ========
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ======== INPUT DO USUÁRIO ========
prompt = st.chat_input("🗣️ Escreva aqui sua dúvida ou descreva seu perfil profissional...")

def salvar_no_google_sheets(usuario, prompt, resposta):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, usuario, prompt, resposta])

if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    system_message = {
        "role": "system",
        "content": (
            f"Você é um assistente de RH da UNESP. Seu papel é comparar perfis com as vagas disponíveis e indicar a mais compatível.\n"
            f"As vagas atuais são:\n{lista_vagas}\n"
            "Considere sempre os requisitos de cada vaga e a descrição fornecida pelo usuário. "
            "Se não houver correspondência clara, sugira uma trilha de capacitação."
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
