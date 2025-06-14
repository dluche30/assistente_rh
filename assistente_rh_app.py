# app_rh_assistente.py
import streamlit as st
from openai import OpenAI
import os, json, io, logging
from datetime import datetime
import pandas as pd
import fitz                             # PyMuPDF
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# ----------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ----------------------------------------------------------------------
st.set_page_config(page_title="Assistente Virtual de Recrutamento", page_icon="🤖")

# ⬇️  logging básico (aparecerá no terminal ou em Cloud Run, etc.)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# -------- OPENAI --------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------- GOOGLE --------
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

# ----------------------------------------------------------------------
# FUNÇÕES UTILITÁRIAS
# ----------------------------------------------------------------------
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

def baixar_curriculo(file_id: str) -> bytes:
    request = drive_service.files().get_media(fileId=file_id)
    file_data = io.BytesIO()
    downloader = MediaIoBaseDownload(file_data, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    file_data.seek(0)
    return file_data.read()

def ler_curriculo_drive(file_id: str, nome: str):
    pdf_bytes = baixar_curriculo(file_id)
    texto = extrair_texto_pdf(pdf_bytes)
    st.session_state.texto_curriculos += f"\n\n===== {nome} =====\n{texto}"

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
    """Reconstrói a primeira mensagem do sistema com vagas + currículos."""
    preambulo = (
        "Você é um assistente de RH. Ajude na análise de currículos.\n\n"
        f"Informações dos currículos analisados:\n{st.session_state.texto_curriculos}\n\n"
        f"As vagas disponíveis são:\n{st.session_state.texto_vagas}"
    )
    st.session_state.mensagens[0]["content"] = preambulo

def mostrar_historico():
    """Renderiza o chat do segundo elemento em diante (0 = system)."""
    for msg in st.session_state.mensagens[1:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

def processar_entrada(prompt_usuario: str):
    """Anexa a pergunta, chama a API, salva resposta e força rerun."""
    st.session_state.mensagens.append({"role": "user", "content": prompt_usuario})
    atualizar_prompt()

    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.mensagens
        )
        conteudo = resposta.choices[0].message.content
        st.session_state.mensagens.append({"role": "assistant", "content": conteudo})

        # LOG planilha Google Sheets
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.usuario_nome,
            prompt_usuario,
            conteudo,
        ])

    except Exception as e:
        logging.error("Erro na chamada ao modelo: %s", e, exc_info=True)
        st.session_state.mensagens.append({
            "role": "assistant",
            "content": "Desculpe, ocorreu um erro ao processar sua solicitação."
        })

    st.rerun()   # evita duplicação de mensagens e simplifica fluxo

# ----------------------------------------------------------------------
# ESTADO INICIAL
# ----------------------------------------------------------------------
st.session_state.setdefault("texto_curriculos", "")
st.session_state.setdefault("texto_vagas", "")
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [{"role": "system", "content": ""}]
    atualizar_prompt()


def gerar_tabela_aderencia(curriculos_texto, vagas_texto):
    prompt = f"""
Você é um assistente de recrutamento. Com base nas vagas abaixo e nos currículos fornecidos, gere uma tabela que mostre a aderência de cada candidato para cada vaga.

- Liste os nomes dos candidatos nas linhas.
- Liste as vagas nas colunas.
- Utilize critérios como: correspondência de competências, experiências, formações e requisitos da vaga.

Apresente os dados em formato de tabela, atribuindo um nível de aderência (ex.: Alto, Médio, Baixo) ou uma pontuação de 0 a 100, se possível.

Currículos analisados:
{curriculos_texto}

Vagas disponíveis:
{vagas_texto}
"""

    resposta = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": st.session_state.mensagens[0]["content"]},
            {"role": "user", "content": prompt}
        ]
    )

    return resposta.choices[0].message.content



import time
import openai

def gerar_tabela_aderencia(curriculos_texto, vagas_texto, modelo_ia):
    prompt = f"""
Você é um assistente de recrutamento. Com base nas vagas abaixo e nos currículos fornecidos, gere uma tabela que mostre a aderência de cada candidato para cada vaga.

- Liste os nomes dos candidatos nas linhas.
- Liste as vagas nas colunas.
- Utilize critérios como: correspondência de competências, experiências, formações e requisitos da vaga.

Apresente os dados em formato de tabela, atribuindo um nível de aderência (ex.: Alto, Médio, Baixo) ou uma pontuação de 0 a 100, se possível.

Currículos analisados:
{curriculos_texto}

Vagas disponíveis:
{vagas_texto}
"""

    tentativas = 5
    for tentativa in range(tentativas):
        try:
            resposta = client.chat.completions.create(
                model=modelo_ia,
                messages=[
                    {"role": "system", "content": st.session_state.mensagens[0]["content"]},
                    {"role": "user", "content": prompt}
                ]
            )
            return resposta.choices[0].message.content

        except openai.RateLimitError:
            wait_time = 2 ** tentativa
            st.warning(f"⚠️ Limite atingido. Tentando novamente em {wait_time} segundos...")
            time.sleep(wait_time)

    st.error("❌ Não foi possível gerar a tabela após várias tentativas devido ao limite da API.")
    return "Erro: Limite da API OpenAI atingido."


# ----------------------------------------------------------------------
# INTERFACE
# ----------------------------------------------------------------------
st.image("logo_unesp.png", width=300)
st.title("Assistente Virtual de Recrutamento")

# ---- Nome do usuário ----
usuario_nome = st.text_input("Digite seu nome completo:", key="nome_usuario_input")
if not usuario_nome:
    st.warning("Por favor, preencha seu nome para iniciar.")
    st.stop()
st.session_state.usuario_nome = usuario_nome

# ---- Carregar vagas ----
try:
    vagas_df = pd.read_csv("vagas_exemplo.csv")
    st.subheader("📑 Vagas disponíveis")
    st.dataframe(vagas_df)
    st.session_state.texto_vagas = vagas_df.to_string(index=False)
except Exception:
    st.warning("Arquivo de vagas não encontrado.")
    st.session_state.texto_vagas = ""


st.subheader("⚙️ Configurações do Assistente")
modelo_ia = st.selectbox(
    "Escolha o modelo de IA para análise:",
    "Escolha o modelo de IA para análise:",
        options=["gpt-4", "gpt-3.5-turbo"],
    index=1,
    key="selecao_modelo"
)


# ---- HISTÓRICO DO CHAT (antes do input) ----
st.divider()
mostrar_historico()
st.divider()

# ---- Upload de currículo ----
with st.expander("📤 Enviar novo currículo (PDF) para o Google Drive"):
    file_uploaded = st.file_uploader("Selecione o arquivo", type=["pdf"])
    if file_uploaded and st.button("🚀 Enviar"):
        upload_curriculo(file_uploaded)

# ---- Ler currículos ----
st.subheader("📄 Currículos no Google Drive")
curriculos = listar_curriculos_drive()
nomes = [c["name"] for c in curriculos]
selecionados = st.multiselect("Selecione currículos para análise:", nomes)

col_le, col_to = st.columns(2)
with col_le:
    if st.button("🔍 Ler currículos selecionados"):
        if not selecionados:
            st.warning("Selecione pelo menos um currículo.")
        else:
            for nome in selecionados:
                file_id = next(c["id"] for c in curriculos if c["name"] == nome)
                ler_curriculo_drive(file_id, nome)
            atualizar_prompt()
            st.success("Currículos lidos e armazenados na memória!")
with col_to:
    if st.button("📥 Ler TODOS os currículos"):
        for c in curriculos:
            ler_curriculo_drive(c["id"], c["name"])
        atualizar_prompt()
        st.success("Todos os currículos lidos!")


# ---- Geração de Tabela de Aderência ----
st.subheader("📊 Análise de Aderência Currículo vs Vagas")
if st.button("🔍 Gerar Tabela de Aderência", key="botao_aderencia"):

    if not st.session_state.texto_curriculos or not st.session_state.texto_vagas:
        st.warning("Por favor, carregue currículos e vagas antes de gerar a análise.")
    else:
        with st.spinner("Analisando currículos e vagas..."):
            tabela = gerar_tabela_aderencia(
                st.session_state.texto_curriculos,
                st.session_state.texto_vagas
            )
            st.subheader("🔍 Resultado da Análise de Aderência")
            st.markdown(tabela)



# ---- Geração de Tabela de Aderência ----
st.subheader("📊 Análise de Aderência Currículo vs Vagas")
if st.button("🔍 Gerar Tabela de Aderência", key="botao_aderencia"):

    if not st.session_state.texto_curriculos or not st.session_state.texto_vagas:
        st.warning("Por favor, carregue currículos e vagas antes de gerar a análise.")
    else:
        with st.spinner("Analisando currículos e vagas..."):
            tabela = gerar_tabela_aderencia(
                st.session_state.texto_curriculos,
                st.session_state.texto_vagas,
                modelo_ia
            )
            st.subheader("🔍 Resultado da Análise de Aderência")
            st.markdown(tabela)


# ---- Campo de entrada do usuário ----
prompt_usuario = st.chat_input("Digite sua mensagem para o assistente...")
if prompt_usuario:
    processar_entrada(prompt_usuario)
