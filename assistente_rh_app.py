
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
import time
import openai

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import re

def extrair_tabela_markdown(texto):
    import re
    tabelas = re.findall(r'((?:\|.*\n)+)', texto)
    if tabelas:
        return tabelas[0]
    else:
        return ""


def texto_para_num(valor):
    mapa = {"Alto": 100, "Médio": 60, "Baixo": 20}
    return mapa.get(str(valor).strip().capitalize(), 0)

def tabela_markdown_para_df(tabela_texto):
    import pandas as pd
    import re

def extrair_tabela_markdown(texto):
    import re
    tabelas = re.findall(r'((?:\|.*\n)+)', texto)
    if tabelas:
        return tabelas[0]
    else:
        return ""

    linhas = [linha.strip() for linha in tabela_texto.strip().split('\n')
              if linha.strip() and not set(linha.replace('|','').replace('-','')) == set()]
    dados = [re.split(r"\s*\|\s*", linha.strip("|")) for linha in linhas]
    # Filtra linhas pelo mesmo número de colunas do cabeçalho
    colunas = dados[0]
    dados_linhas = [linha for linha in dados[1:] if len(linha) == len(colunas)]
    df = pd.DataFrame(dados_linhas, columns=colunas)
    for col in colunas[1:]:
        df[col] = df[col].apply(texto_para_num)
    return df







# ----------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ----------------------------------------------------------------------
st.set_page_config(page_title="Assistente Virtual de Recrutamento", page_icon="🤖")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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
    preambulo = (
        "Você é um assistente virtual de RH. Ajude na análise de currículos de múltiplos candidatos, gerando tabelas de aderência, cruzamento com vagas, resumos e sugestões de ocupação. \n\n"
        f"Informações dos currículos analisados:\n{st.session_state.texto_curriculos}\n\n"
        f"As vagas disponíveis são:\n{st.session_state.texto_vagas}"
    )
    st.session_state.mensagens[0]["content"] = preambulo

def mostrar_historico():
    for msg in st.session_state.mensagens[1:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

def processar_entrada(prompt_usuario: str):
    st.session_state.mensagens.append({"role": "user", "content": prompt_usuario})
    atualizar_prompt()
    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.mensagens
        )
        conteudo = resposta.choices[0].message.content
        st.session_state.mensagens.append({"role": "assistant", "content": conteudo})

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
    st.rerun()

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
# ESTADO INICIAL
# ----------------------------------------------------------------------
st.session_state.setdefault("texto_curriculos", "")
st.session_state.setdefault("texto_vagas", "")
st.session_state.setdefault("sugestoes_exibidas", False)
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [{
        "role": "system",
        "content": (
            "Você é um assistente virtual de RH. "
            "Ajude na análise de currículos de múltiplos candidatos, gerando tabelas de aderência, cruzamento com vagas, resumos e sugestões de ocupação. "
            "Sempre que gerar uma tabela de aderência para análise automática, devolva APENAS a tabela markdown, sem legenda, título, comentários ou texto extra."
        )
    }]
    atualizar_prompt()


# ----------------------------------------------------------------------
# SIDEBAR - CONFIGURAÇÕES E UPLOADS
# ----------------------------------------------------------------------
with st.sidebar:
    st.image("logo_unesp.png", width=200)
    st.header("Configurações")
    modelo_ia = st.selectbox(
        "Escolha o modelo de IA para análise:",
        options=["gpt-4", "gpt-3.5-turbo"],
        index=1,
        key="selecao_modelo_sidebar"
    )

    usuario_nome = st.text_input("Digite seu nome completo:", key="nome_usuario_input_sidebar")
    if not usuario_nome:
        st.warning("Por favor, preencha seu nome para iniciar.")
        st.stop()
    st.session_state.usuario_nome = usuario_nome

    st.subheader("📤 Enviar novo currículo (PDF) para o Google Drive")
    file_uploaded = st.file_uploader("Selecione o arquivo", type=["pdf"], key="upload_curriculo_sidebar")
    if file_uploaded and st.button("🚀 Enviar", key="enviar_curriculo_sidebar"):
        upload_curriculo(file_uploaded)

    st.subheader("📑 Vagas disponíveis (CSV local)")
    try:
        vagas_df = pd.read_csv("vagas_exemplo.csv")
        st.dataframe(vagas_df)
        st.session_state.texto_vagas = vagas_df.to_string(index=False)
    except Exception:
        st.warning("Arquivo de vagas não encontrado.")
        st.session_state.texto_vagas = ""

# ----------------------------------------------------------------------
# PAINEL PRINCIPAL
# ----------------------------------------------------------------------
st.title("Assistente Virtual de Recrutamento")

st.divider()
mostrar_historico()
st.divider()

st.subheader("📄 Currículos no Google Drive")
curriculos = listar_curriculos_drive()
nomes = [c["name"] for c in curriculos]
selecionados = st.multiselect("Selecione currículos para análise:", nomes, key="multiselect_curriculos")
col_le, col_to = st.columns(2)
with col_le:
    if st.button("🔍 Ler currículos selecionados", key="botao_ler_selecionados"):
        if not selecionados:
            st.warning("Selecione pelo menos um currículo.")
        else:
            for nome in selecionados:
                file_id = next(c["id"] for c in curriculos if c["name"] == nome)
                ler_curriculo_drive(file_id, nome)
            atualizar_prompt()
            st.success("Currículos lidos e armazenados na memória!")
with col_to:
    if st.button("📥 Ler TODOS os currículos", key="botao_ler_todos"):
        for c in curriculos:
            ler_curriculo_drive(c["id"], c["name"])
        atualizar_prompt()
        st.success("Todos os currículos lidos!")

# ---- Geração de Tabela de Aderência ----

st.subheader("📊 Análise de Aderência Currículo vs Vagas")
if st.button("🔍 Gerar Tabela de Aderência", key="botao_aderencia_principal"):
    if not st.session_state.texto_curriculos or not st.session_state.texto_vagas:
        st.warning("Por favor, carregue currículos e vagas antes de gerar a análise.")
    else:
        with st.spinner("Analisando currículos e vagas..."):
            tabela = gerar_tabela_aderencia(
                st.session_state.texto_curriculos,
                st.session_state.texto_vagas,
                modelo_ia
            )
            

try:
    tabela_markdown = extrair_tabela_markdown(tabela)
    if tabela_markdown:
        df_aderencia = tabela_markdown_para_df(tabela_markdown)
        if df_aderencia.shape[1] > 2:
            st.subheader("🔍 Resultado da Análise de Aderência")
            st.dataframe(df_aderencia)
            st.subheader("📈 Gráfico de Radar")
            plot_radar_aderencia(df_aderencia)
        else:
            st.warning("Tabela convertida tem só 1 coluna útil. Reveja a formatação da tabela de aderência.")
    else:
        st.warning("Tabela de aderência não encontrada no texto do assistente. Peça para a IA retornar apenas a tabela markdown, sem legenda ou texto extra.")
except Exception as e:
    st.warning(f"Não foi possível gerar o gráfico de radar automaticamente: {e}")
    st.markdown(tabela)




# ---- Campo de entrada do usuário (chat) ----
prompt_usuario = st.chat_input("Digite sua mensagem para o assistente...")
if prompt_usuario:
    processar_entrada(prompt_usuario)
