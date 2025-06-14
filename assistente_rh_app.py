import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import pandas as pd
import json
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import fitz  # PyMuPDF para leitura de PDF

# ========= CONFIG GOOGLE =========
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

creds = service_account.Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=SCOPES
)

gc = gspread.authorize(creds)
sheet = gc.open("chat_logs_rh").sheet1

drive_service = build('drive', 'v3', credentials=creds)
FOLDER_ID = '1oMSIeD00E3amFjTX4zUW8LfJFctxOMn4'

# ========= CONFIG OPENAI =========
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ========= FUNÇÃO PARA LER PDF =========
def extrair_texto_pdf(arquivo_pdf):
    texto = ""
    try:
        with fitz.open(stream=arquivo_pdf.read(), filetype="pdf") as doc:
            for pagina in doc:
                texto += pagina.get_text()
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
    return texto

# ========= CARREGAR PREÂMBULO =========
preambulo_path = "preambulo_assistente.txt"
if os.path.exists(preambulo_path):
    with open(preambulo_path, "r", encoding="utf-8") as f:
        preambulo_base = f.read()
else:
    preambulo_base = "Preambulo não encontrado."

# ========= INTERFACE =========
st.set_page_config(page_title="Assistente RH UNESP", page_icon="🤖")
st.image("logo_unesp.png", width=400)
st.title("Assistente Virtual de Recrutamento - UNESP")
st.markdown("Preencha seus dados, envie seu currículo e converse com nosso assistente!")

# ========= NOME DO USUÁRIO =========
usuario_nome = st.text_input("Digite seu nome completo:")
if not usuario_nome:
    st.warning("Por favor, preencha seu nome para iniciar.")
    st.stop()

st.session_state.usuario_nome = usuario_nome

# ========= UPLOAD DE CURRÍCULO =========
curriculo = st.file_uploader("Envie seu currículo (PDF)", type=["pdf"])
curriculo_drive_link = ""
curriculo_texto = ""

if curriculo is not None:
    # 🔸 Ler o conteúdo do currículo
    curriculo_texto = extrair_texto_pdf(curriculo)

    # 🔸 Upload para Google Drive
    try:
        file_metadata = {'name': curriculo.name, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(curriculo, mimetype='application/pdf')
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        file_id = uploaded.get('id')
        curriculo_drive_link = uploaded.get('webViewLink')
        st.success(f"Currículo enviado com sucesso: [Abrir no Drive]({curriculo_drive_link})")

    except Exception as e:
        st.error(f"Erro ao enviar currículo: {e}")

# ========= HISTÓRICO =========
if "mensagens" not in st.session_state:
    preambulo = preambulo_base
    if curriculo_texto:
        preambulo += f"\n\nInformações do currículo de {usuario_nome}:\n{curriculo_texto}"

    st.session_state.mensagens = [
        {"role": "system", "content": preambulo}
    ]

# ========= CHAT =========
prompt_usuario = st.chat_input("Digite sua mensagem para o assistente...")

if prompt_usuario:
    st.session_state.mensagens.append({"role": "user", "content": prompt_usuario})

    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.mensagens
        )
        conteudo = resposta.choices[0].message.content
        st.session_state.mensagens.append({"role": "assistant", "content": conteudo})

        with st.chat_message("assistant"):
            st.markdown(conteudo)

        # Grava no Google Sheets
        linha_log = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.usuario_nome,
            prompt_usuario,
            conteudo,
            curriculo_drive_link
        ]
        sheet.append_row(linha_log)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

# ========= EXIBIR HISTÓRICO =========
for msg in st.session_state.mensagens[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
