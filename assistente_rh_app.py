import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
import pandas as pd
import json
import io
import fitz
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

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

# ========= FUNÇÕES =========
def extrair_texto_pdf(file_bytes):
    texto = ""
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for pagina in doc:
                texto += pagina.get_text()
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
    return texto

def listar_curriculos_drive():
    results = drive_service.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='application/pdf'",
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def baixar_e_ler_curriculo(file_id, file_name):
    request = drive_service.files().get_media(fileId=file_id)
    file_data = io.BytesIO()
    downloader = MediaIoBaseDownload(file_data, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    file_data.seek(0)
    texto = extrair_texto_pdf(file_data.read())
    return texto

def upload_curriculo(file_uploaded):
    try:
        file_metadata = {'name': file_uploaded.name, 'parents': [FOLDER_ID]}
        media = MediaIoBaseUpload(file_uploaded, mimetype='application/pdf')
        uploaded = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        link = uploaded.get('webViewLink')
        st.success(f"Currículo {file_uploaded.name} enviado com sucesso! [Abrir no Drive]({link})")
    except Exception as e:
        st.error(f"Erro ao enviar currículo: {e}")

# ========= INTERFACE =========
st.set_page_config(page_title="Assistente Virtual de Recrutamento", page_icon="🤖")
st.image("logo_unesp.png", width=400)
st.title("Assistente Virtual de Recrutamento")
st.markdown("Você pode analisar múltiplos currículos armazenados no Google Drive.")

usuario_nome = st.text_input("Digite seu nome completo:")
if not usuario_nome:
    st.warning("Por favor, preencha seu nome para iniciar.")
    st.stop()

st.session_state.usuario_nome = usuario_nome

# ========= LEITURA DO ARQUIVO DE VAGAS =========
try:
    vagas_df = pd.read_csv("vagas_exemplo.csv")
    texto_vagas = vagas_df.to_string(index=False)
    st.subheader("📑 Vagas disponíveis")
    st.dataframe(vagas_df)
except Exception as e:
    texto_vagas = ""
    st.warning("Arquivo vagas_exemplo.csv não encontrado ou com erro.")

# ========= UPLOAD DE CURRÍCULO =========
st.subheader("📤 Enviar novo currículo para o Google Drive")
file_uploaded = st.file_uploader("Selecione um currículo (PDF) para enviar", type=["pdf"])
if file_uploaded is not None:
    if st.button("🚀 Enviar currículo para o Drive"):
        upload_curriculo(file_uploaded)

# ========= LER CURRÍCULOS =========
st.subheader("📄 Currículos no Google Drive")
curriculos = listar_curriculos_drive()
curriculo_nomes = [c['name'] for c in curriculos]
curriculo_selecionados = st.multiselect("Selecione os currículos para análise:", curriculo_nomes)

texto_curriculos = ""

if st.button("🔍 Ler currículos selecionados"):
    if curriculo_selecionados:
        for nome in curriculo_selecionados:
            file_id = next(c['id'] for c in curriculos if c['name'] == nome)
            texto = baixar_e_ler_curriculo(file_id, nome)
            texto_curriculos += f"

===== {nome} =====
{texto}
"
        st.success("Conteúdo dos currículos lido com sucesso!")
        st.text_area("📝 Conteúdo dos currículos selecionados:", texto_curriculos, height=400)
    else:
        st.warning("Selecione pelo menos um currículo.")

if st.button("📥 Ler TODOS os currículos do Drive"):
    for c in curriculos:
        texto = baixar_e_ler_curriculo(c['id'], c['name'])
        texto_curriculos += f"

===== {c['name']} =====
{texto}
"
    st.success("Todos os currículos foram lidos com sucesso!")
    st.text_area("📝 Conteúdo de TODOS os currículos:", texto_curriculos, height=500)

# ========= HISTÓRICO =========
if "mensagens" not in st.session_state:
    preambulo = "Você é um assistente de RH. Ajude na análise de currículos.

"
    if texto_curriculos:
        preambulo += f"Informações dos currículos analisados:
{texto_curriculos}
"
    if texto_vagas:
        preambulo += f"
As vagas disponíveis são:
{texto_vagas}
"
    st.session_state.mensagens = [{"role": "system", "content": preambulo}]

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

        linha_log = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.usuario_nome,
            prompt_usuario,
            conteudo,
            ", ".join(curriculo_selecionados) if curriculo_selecionados else "Todos"
        ]
        sheet.append_row(linha_log)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

# ========= EXIBIR HISTÓRICO =========
for msg in st.session_state.mensagens[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
