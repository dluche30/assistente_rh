import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

def texto_para_num(valor):
    mapa = {"Alto": 100, "Médio": 60, "Baixo": 20}
    try:
        return mapa.get(str(valor).strip().capitalize(), float(valor))
    except:
        return 0

def tabela_markdown_para_df(tabela_texto):
    linhas = [linha.strip() for linha in tabela_texto.strip().split('\n')
              if linha.strip() and not set(linha.replace('|','').replace('-','')) == set()]
    dados = [re.split(r"\s*\|\s*", linha.strip("|")) for linha in linhas]
    colunas = dados[0]
    dados_linhas = [linha for linha in dados[1:] if len(linha) == len(colunas)]
    df = pd.DataFrame(dados_linhas, columns=colunas)
    for col in colunas[1:]:
        df[col] = df[col].apply(texto_para_num)
    return df

def extrair_tabela_markdown(texto):
    tabelas = re.findall(r'((?:\|.*\n)+)', texto)
    if tabelas:
        return tabelas[0]
    else:
        return ""

def plot_radar_aderencia(df_aderencia):
    categorias = list(df_aderencia.columns[1:])
    N = len(categorias)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    for i, row in df_aderencia.iterrows():
        values = row[1:].astype(float).tolist()
        values += values[:1]
        ax.plot(angles, values, linewidth=2, label=row[0])
        ax.fill(angles, values, alpha=0.1)
    ax.set_thetagrids(np.degrees(angles[:-1]), categorias)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    plt.title("Aderência dos candidatos às vagas")
    st.pyplot(fig)

st.title("Demo - Radar de Aderência de Candidatos")

st.write("**Cole abaixo a resposta da IA (somente a tabela markdown):**")

resposta_ia = st.text_area("Resposta da IA", height=300)

if st.button("Gerar análise"):
    try:
        tabela_markdown = extrair_tabela_markdown(resposta_ia)
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
            st.warning("Tabela de aderência não encontrada no texto. Cole apenas a tabela markdown gerada pela IA, sem legenda.")
    except Exception as e:
        st.warning(f"Não foi possível gerar o gráfico de radar automaticamente: {e}")
        if 'tabela_markdown' in locals() and tabela_markdown:
            st.markdown(tabela_markdown)
        else:
            st.info("Nenhuma tabela de aderência foi retornada.")
