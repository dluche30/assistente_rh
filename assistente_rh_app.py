import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Inicializa o cliente OpenAI
client = OpenAI()

# Configurações para acesso ao Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("rising-precinct-252914-ed9a3a5c5944.json", scope)
client_gsheets = gspread.authorize(creds)
sheet = client_gsheets.open("chat_logs_streamlit").sheet1

# Carrega o preâmbulo a partir do arquivo externo
preambulo_path = "preambulo_assistente.txt"
if os.path.exists(preambulo_path):
    with open(preambulo_path, "r", encoding="utf-8") as f:
        preambulo = f.read()
else:
    preambulo = "Preambulo não encontrado. Por favor, verifique o arquivo 'preambulo_assistente.txt'."

# Interface
st.set_page_config(page_title="Assistente Virtual de Recrutamento UNESP", page_icon="🤖")
st.image("logo_unesp.png", width=160)
st.title("Assistente Virtual de Recrutamento UNESP")
st.markdown("Este assistente simula uma triagem inicial de candidatos com base em vagas disponíveis.")

# Campo para nome do usuário
usuario_nome = st.text_input("Digite seu nome:", value=st.session_state.get("usuario_nome", ""))
if usuario_nome:
    st.session_state.usuario_nome = usuario_nome

# Inicializa o histórico de mensagens na sessão
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [
        {"role": "system", "content": preambulo}
    ]

# Campo de entrada do usuário
prompt_usuario = st.chat_input("Digite sua mensagem...")

if prompt_usuario:
    st.session_state.mensagens.append({"role": "user", "content": prompt_usuario})

    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.mensagens
        )
        conteudo = resposta.choices[0].message.content
        st.session_state.mensagens.append({"role": "assistant", "content": conteudo})

        # Exibe a resposta
        with st.chat_message("assistant"):
            st.markdown(conteudo)

        # Registra no Google Sheets
        linha_log = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.get("usuario_nome", ""),
            prompt_usuario,
            conteudo
        ]
        sheet.append_row(linha_log)

    except Exception as e:
        st.error(f"Ocorreu um erro: {str(e)}")

# Exibe a conversa
for msg in st.session_state.mensagens[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
