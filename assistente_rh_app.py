import streamlit as st
from openai import OpenAI
import os, json, io
from datetime import datetime
import pandas as pd
import fitz                   # PyMuPDF
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# ========= CONFIG GOOGLE =========
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = service_account.Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]),
    scopes=SCOPES
)
gc = gspread.authorize(creds)
sheet = gc.open("chat_logs_rh").sheet1
drive_service = build("drive", "v3", credentials=creds)
FOLDER_ID = "1oMSIeD00E3amFjTX4zUW8LfJFctxOMn4"

# ========= CONFIG OPENAI =========
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ========= FUNÇÕES UTILITÁRIAS =========
@st.cache_data(show_spinner=False)
def extrair_texto_pdf(file_bytes: bytes) -> str:
    texto = ""
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

def listar_curriculos_drive():
    res = drive_service.files().list(
        q=f"'{FOLDER_ID}' in parents and mimeType='application/pdf'",
        fields="files(id, name)"
    ).execute()
    return res.get("files", [])

def baixar_curriculo(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    file_data = io.BytesIO()
    downloader = MediaIoBaseDownload(file_data, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    file_data.seek(0)
    return file_data.read()

def ler_curriculo_drive(file_id, nome):
    pdf_bytes = baixar_curriculo(file_id)
    texto = extrair_texto_pdf(pdf_bytes)
    # ---- Persistir no estado ----
    st.session_state.texto_curriculos += f"\n\n===== {nome} =====\n{texto}"
    return texto

def upload_curriculo(file_uploaded):
    meta = {"name": file_uploaded.name, "parents": [FOLDER_ID]}
    media = MediaIoBaseUpload(file_uploaded, mimetype="application/pdf")
    uploaded = drive_service.files().create(
        body=meta, media_body=media, fields="id, webViewLink"
    ).execute()
    st.success(
        f"Currículo **{file_uploaded.name}** enviado com sucesso! "
        f"[Abrir no Drive]({uploaded['webViewLink']})"
    )

def atualizar_prompt():
    """Reconstrói a primeira mensagem 'system'."""
    preambulo = (
        "Você é um assistente de RH. Ajude na análise de currículos.\n\n"
        f"Informações dos currículos analisados:\n{st.session_state.texto_curriculos}\n\n"
        f"As vagas disponíveis são:\n{st.session_state.texto_vagas}"
    )
    st.session_state.mensagens[0]["content"] = preambulo

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

# ========= CARREGAR VAGAS =========
try:
    vagas_df = pd.read_csv("vagas_exemplo.csv")
    st.subheader("📑 Vagas disponíveis")
    st.dataframe(vagas_df)
    st.session_state.texto_vagas = vagas_df.to_string(index=False)
except Exception:
    st.session_state.texto_vagas = ""
    st.warning("Arquivo de vagas não encontrado ou com erro.")

# ========= ESTADO INICIAL =========
st.session_state.setdefault("texto_curriculos", "")
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [{"role": "system", "content": ""}]
    atualizar_prompt()  # cria o preâmbulo inicial

# ========= UPLOAD DE CURRÍCULO =========
st.subheader("📤 Enviar novo currículo para o Google Drive")
file_uploaded = st.file_uploader(
    "Selecione um currículo (PDF) para enviar", type=["pdf"]
)
if file_uploaded and st.button("🚀 Enviar currículo"):
    upload_curriculo(file_uploaded)

# ========= LER CURRÍCULOS =========
st.subheader("📄 Currículos no Google Drive")
curriculos = listar_curriculos_drive()
nomes = [c["name"] for c in curriculos]
selecionados = st.multiselect("Selecione os currículos para análise:", nomes)

if st.button("🔍 Ler currículos selecionados"):
    if not selecionados:
        st.warning("Selecione pelo menos um currículo.")
    else:
        for nome in selecionados:
            file_id = next(c["id"] for c in curriculos if c["name"] == nome)
            ler_curriculo_drive(file_id, nome)
        atualizar_prompt()
        st.success("Conteúdo lido e armazenado na memória!")
        st.text_area("📝 Currículos lidos:", st.session_state.texto_curriculos, height=400)

if st.button("📥 Ler TODOS os currículos"):
    for c in curriculos:
        ler_curriculo_drive(c["id"], c["name"])
    atualizar_prompt()
    st.success("Todos os currículos lidos!")
    st.text_area("📝 Currículos lidos:", st.session_state.texto_curriculos, height=500)

# ========= CHAT =========
prompt_usuario = st.chat_input("Digite sua mensagem para o assistente...")
if prompt_usuario:
    st.session_state.mensagens.append({"role": "user", "content": prompt_usuario})
    atualizar_prompt()               # garante prompt atualizado antes da chamada

    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.mensagens
        )
        conteudo = resposta.choices[0].message.content
        st.session_state.mensagens.append({"role": "assistant", "content": conteudo})

        with st.chat_message("assistant"):
            st.markdown(conteudo)

        # LOG
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            usuario_nome,
            prompt_usuario,
            conteudo,
            ", ".join(selecionados) if selecionados else "Todos"
        ])

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

# ========= EXIBIR HISTÓRICO =========
for msg in st.session_state.mensagens[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
