
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
    if 'tabela_markdown' in locals() and tabela_markdown:
        st.markdown(tabela_markdown)
    else:
        st.info("Nenhuma tabela de aderência foi retornada pelo assistente.")




# ---- Campo de entrada do usuário (chat) ----
prompt_usuario = st.chat_input("Digite sua mensagem para o assistente...")
if prompt_usuario:
    processar_entrada(prompt_usuario)
