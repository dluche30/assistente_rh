import streamlit as st
import requests
import csv
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime

st.set_page_config(page_title="Assistente de RH com IA", layout="centered")
st.title("👩‍💼 Assistente Virtual de Recrutamento")
st.markdown("Cole abaixo o texto de um currículo ou descrição pessoal para obter uma análise automatizada de perfil.")

API_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = os.getenv("OPENAI_API_KEY")
LOG_FILE = "rh_logs.csv"

def analisar_perfil(texto_candidato):
    preamble = (
        "Você é um assistente virtual especializado em recrutamento e seleção de profissionais na área de tecnologia. "
        "Seu papel é analisar o conteúdo enviado (currículo ou descrição pessoal), identificar habilidades técnicas e comportamentais, "
        "avaliar o alinhamento com uma vaga genérica de desenvolvedor de software e sugerir perguntas para uma entrevista. "
        "Forneça feedback construtivo e sempre estimule o desenvolvimento do candidato. Nunca forneça julgamento definitivo ou discriminatório."
    )
    messages = [
        { "role": "system", "content": preamble },
        { "role": "user",   "content": texto_candidato }
    ]
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.6
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"]
    return reply

def registrar_interacao(texto, resposta):
    with open(LOG_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), texto, resposta])

texto_candidato = st.text_area("Cole aqui o currículo ou descrição do candidato:", height=200)
if st.button("Analisar perfil") and texto_candidato.strip() != "":
    with st.spinner("Analisando perfil..."):
        try:
            resultado = analisar_perfil(texto_candidato)
            st.success("Resultado da análise:")
            st.markdown(resultado)
            registrar_interacao(texto_candidato, resultado)
        except Exception as e:
            st.error(f"Ocorreu um erro: {str(e)}")