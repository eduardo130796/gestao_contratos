import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import numpy as np
#import calendar
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from io import BytesIO
#from fpdf import FPDF
#from PIL import Image
import matplotlib.pyplot as plt
import plotly.express as px
import json
#import requests
#import xlsxwriter
import plotly.graph_objects as go
#import unicodedata
import re
from jinja2 import Template
import os
#import pdfkit
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
import io
import base64


#st.set_page_config(page_title="Gestão de Contratos", layout="wide", page_icon="1dd529a8-a1b8-4c15-8bae-4fbc3caacc13.png")




# Coloca uma imagem pequena e discreta na sidebar
#st.sidebar.image("1dd529a8-a1b8-4c15-8bae-4fbc3caacc13.png", width=150)
# Função para carregar e preparar os dados
@st.cache_data
def carregar_dados():
    url = "https://raw.githubusercontent.com/eduardo130796/gestao_contratos/main/RELATORIO%20DE%20CONTRATOS%20VIGENTES%202025%20(1).xlsx"
    df = pd.read_excel(url)
    #df = pd.read_excel("RELATORIO DE CONTRATOS VIGENTES 2025 (1).xlsx")  # nome do seu arquivo

    # Corrigir e converter valores monetários
    for col in ["VALOR ATUAL MENSAL", "VALOR ANUAL ATUAL", "VALOR GLOBAL"]:
        df[col] = df[col].replace("R\$", "", regex=True).replace("\.", "", regex=True).replace(",", ".", regex=True)
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Converter datas
    df["VIGÊNCIA"] = pd.to_datetime(df["VIGÊNCIA"], dayfirst=True, errors="coerce").dt.normalize()
    df["VIGÊNCIA_INDETERMINADA"] = df["VIGÊNCIA"].isna()
    df["REGIÕES"] = df["REGIÕES"].astype(str).str.strip()
    df["UNIDADE"] = df["UNIDADE"].astype(str).str.strip()
    
    # Filtrar contratos ativos ou encerrados neste mês
    hoje = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = hoje.replace(day=1)
    df = df[
        (df["VIGÊNCIA_INDETERMINADA"]) |
        (df["VIGÊNCIA"] >= hoje) |
        ((df["VIGÊNCIA"] < hoje) & (df["VIGÊNCIA"] >= inicio_mes))
    ]

    # Dias para vencer
    df["DIAS_PARA_VENCER"] = (df["VIGÊNCIA"] - hoje).dt.days

    # Novo status: Ativo ou Encerrado
    def definir_status(vigencia):
        if pd.isna(vigencia):
            return "Ativo"
        elif vigencia >= hoje:
            return "Ativo"
        else:
            return "Encerrado"

    df["STATUS"] = df["VIGÊNCIA"].apply(definir_status)

    return df

#================
#
# FILTROS
#
#================
def filtrar_contratos_unicos(
    df,
    regioes_selecionadas=None,
    unidades_selecionadas=None,
    contratos_selecionados=None,
    objetos_selecionados=None,
    modo_visao=None
):
    df_filtrado = df.copy()

    # Filtro por múltiplas regiões
    if regioes_selecionadas and "Todas" not in regioes_selecionadas:
        df_filtrado = df_filtrado[df_filtrado["REGIÕES"].isin(regioes_selecionadas)]

    # Filtro por múltiplas unidades (busca parcial)
    if unidades_selecionadas and "Todas" not in unidades_selecionadas:
        df_filtrado = df_filtrado[
            df_filtrado["UNIDADE"].apply(
                lambda unidade: any(sel.lower() in str(unidade).lower() for sel in unidades_selecionadas)
            )
        ]

    # Filtro por múltiplos contratos
    if contratos_selecionados and "Todos" not in contratos_selecionados:
        df_filtrado = df_filtrado[df_filtrado["CONTRATO"].isin(contratos_selecionados)]

    # Filtro por objetos (se houver objetos selecionados)
    if objetos_selecionados:
        regex_pattern = r'\b(' + '|'.join([re.escape(obj) for obj in objetos_selecionados]) + r')\b'
        if modo_visao == "Focar no Objeto": 
            df_filtrado = df_filtrado[df_filtrado["OBJETO"].str.contains(regex_pattern, case=False, na=False)]
        else:  # Ver Contrato Completo
            contratos_com_objeto = df_filtrado[df_filtrado['OBJETO'].str.contains(regex_pattern, case=False, na=False)]['CONTRATO'].unique()
            df_filtrado = df_filtrado[df_filtrado['CONTRATO'].isin(contratos_com_objeto)]


    return df_filtrado

# Função para destacar o objeto com a palavra-chave
def destacar_objeto(obj, objeto_busca):
    if objeto_busca:
        return obj.replace(
            objeto_busca,
            f"<mark style='background-color: yellow'>{objeto_busca}</mark>"
        )
    return obj


df = carregar_dados()

st.sidebar.header("🔎 Filtros")

# Região
regioes_disponiveis = sorted(df['REGIÕES'].dropna().unique())
regioes_selecionadas = st.sidebar.multiselect("Filtrar por Região", options=["Todas"] + regioes_disponiveis, default=[])

# Unidades dependentes da região
if "Todas" in regioes_selecionadas or not regioes_selecionadas:
    df_regiao = df
else:
    df_regiao = df[df["REGIÕES"].isin(regioes_selecionadas)]

unidades_disponiveis = sorted(df_regiao["UNIDADE"].dropna().unique())
unidades_selecionadas = st.sidebar.multiselect("Filtrar por Unidade", options=["Todas"] + unidades_disponiveis, default=[])

# Contratos dependentes da unidade e região
if "Todas" in unidades_selecionadas or not unidades_selecionadas:
    df_unidade = df_regiao
else:
    df_unidade = df_regiao[df_regiao["UNIDADE"].apply(lambda u: any(sel.lower() in str(u).lower() for sel in unidades_selecionadas))]

contratos_disponiveis = sorted(df_unidade["CONTRATO"].dropna().unique())
contratos_selecionados = st.sidebar.multiselect("Filtrar por Contrato", options=["Todos"] + contratos_disponiveis, default=[])

# Filtrando objetos de acordo com os contratos selecionados
objetos_disponiveis = sorted(df_unidade["OBJETO"].dropna().unique())

# Aplicando filtro de objetos dinâmico, dependendo dos filtros anteriores
df_filtrado_dinamico = filtrar_contratos_unicos(
    df_unidade,
    regioes_selecionadas=regioes_selecionadas,
    unidades_selecionadas=unidades_selecionadas,
    contratos_selecionados=contratos_selecionados,
    objetos_selecionados=None,
      # Não filtrar por objetos ainda
)

# Atualiza os objetos disponíveis após os filtros
objetos_filtrados = sorted(df_filtrado_dinamico["OBJETO"].dropna().unique())

# Se não houver objetos filtrados, exibe todos os objetos disponíveis
if not objetos_filtrados:
    objetos_filtrados = sorted(df["OBJETO"].dropna().unique())

# Multiselect dinâmico para objetos
objetos_selecionados = st.sidebar.multiselect(
    "Filtrar por Objeto",
    options=objetos_filtrados,
    default=[],  # Não selecionar nada por padrão
    help="Selecione os objetos que você deseja filtrar. Caso não selecione nenhum, serão mostrados todos os objetos disponíveis."
)

# Mostrar modo de visualização apenas se houver objeto selecionado
if objetos_selecionados:
    modo_visao = st.sidebar.radio(
        "🔎 Como deseja visualizar os contratos?",
        ["Focar no Objeto", "Ver Contrato Completo"],
        index=0,
        horizontal=True
    )
else:
    modo_visao = "Focar no Objeto"  # valor padrão quando não há busca

# Aplicar filtro final
df_filtrado = filtrar_contratos_unicos(
    df,
    regioes_selecionadas=regioes_selecionadas,
    unidades_selecionadas=unidades_selecionadas,
    contratos_selecionados=contratos_selecionados,
    objetos_selecionados=objetos_selecionados,
    modo_visao=modo_visao
)

# Verificação de múltiplos objetos
alerta_multiplo_objeto = False
contratos_com_objeto_diferente = []

if df_filtrado.empty:
    st.info("Nenhum contrato encontrado com os filtros selecionados.")
else:
    contratos_exibidos = df_filtrado["CONTRATO"].unique()

    for contrato in contratos_exibidos:
        df_contrato = df_filtrado[df_filtrado["CONTRATO"] == contrato]

        # Verifica objetos diferentes no contrato original
        objetos_todos = df[df["CONTRATO"] == contrato]["OBJETO"].dropna().unique()
        objetos_exibidos = df_contrato["OBJETO"].dropna().unique()

        if len(set(objetos_todos)) > 1:
            outros_objetos = set(objetos_todos) - set(objetos_exibidos)
            if outros_objetos:
                contratos_com_objeto_diferente.append(contrato)
                alerta_multiplo_objeto = True



if objetos_selecionados:
    # Mensagem de alerta para múltiplos objetos no contrato
    if alerta_multiplo_objeto:
        st.sidebar.markdown(
            f"🚨 **Alerta**: O contrato `{', '.join(contratos_com_objeto_diferente)}` possui múltiplos objetos. "
            "Considere revisar o contrato completo para análise detalhada."
        )
        st.warning(
            "⚠️ Alguns contratos podem ter múltiplos objetos. Se você precisar de uma análise mais detalhada, "
            "considere visualizar o contrato completo."
        )

if st.sidebar.button("Atualizar", type="tertiary"):
    carregar_dados.clear()
    df = carregar_dados()
#================
#
# MÉTRICAS INICIAIS
#
#================
# Datas de referência
hoje = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
inicio_mes = hoje.replace(day=1)

def compilar_contratos(df_filtrado):
        df = df_filtrado.copy()

        # Limpa espaços e uniformiza o texto
        df['CONTRATO'] = df['CONTRATO'].astype(str).str.strip()
        df['PROCESSO'] = df['PROCESSO'].astype(str).str.strip()
        df['OBJETO'] = df['OBJETO'].astype(str).str.strip()
        df['UNIDADE'] = df['UNIDADE'].astype(str).str.strip()

        # Limpeza de texto
        for col in ['CONTRATO', 'PROCESSO', 'OBJETO', 'UNIDADE', 'REGIÕES', 'ESTADO',
                    'MODALIDADE DE LICITAÇÃO', 'CONTRATADA', 'CNPJ/CPF', 'OBSERVAÇÕES']:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].str.replace('\n', ' / ', regex=False)

        # Converte valores para numérico
        for col in ['VALOR ATUAL MENSAL', 'VALOR ANUAL ATUAL', 'VALOR GLOBAL']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Converte vigência para datetime
        df['VIGÊNCIA'] = pd.to_datetime(df['VIGÊNCIA'], errors='coerce')

        # Agrupa por CONTRATO + PROCESSO
        df_compilado = df.groupby(['CONTRATO', 'PROCESSO']).agg({
            'REGIÕES': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'ESTADO': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'UNIDADE': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'OBJETO': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'MODALIDADE DE LICITAÇÃO': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'CONTRATADA': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'CNPJ/CPF': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'OBSERVAÇÕES': lambda x: ' / '.join(sorted(set(x.dropna()))),
            'VALOR ATUAL MENSAL': 'sum',
            'VALOR ANUAL ATUAL': 'sum',
            'VALOR GLOBAL': 'sum',
            'VIGÊNCIA': 'max',
            'VIGÊNCIA_INDETERMINADA': 'max',
            'DIAS_PARA_VENCER': 'max',
            'STATUS': 'max',
        }).reset_index()

        return df_compilado

df_contratos_unicos = compilar_contratos(df_filtrado)


# --- FILTROS ---
df_indeterminados = df_contratos_unicos[df_contratos_unicos["VIGÊNCIA_INDETERMINADA"]]
df_ativos = df_contratos_unicos[(df_contratos_unicos["STATUS"] == 'Ativo')]

df_vencidos_mes = df_contratos_unicos[(df_contratos_unicos["STATUS"] == 'Encerrado') & (df_contratos_unicos["VIGÊNCIA"] >= inicio_mes)]

# --- SUBCONJUNTOS IMPORTANTES ---
df_vencendo_hoje = df_ativos[df_ativos["DIAS_PARA_VENCER"] == 0]
df_vencendo_7_dias = df_ativos[(df_ativos["DIAS_PARA_VENCER"] > 0) & (df_ativos["DIAS_PARA_VENCER"] <= 7)]
df_vencendo_15_dias = df_ativos[(df_ativos["DIAS_PARA_VENCER"] >= 8) & (df_ativos["DIAS_PARA_VENCER"] <= 15)]
# --- CONTAGEM CLASSIFICAÇÃO ---
contagem_classificacao = df_ativos["STATUS"].value_counts().to_dict()

# --- TOTAL VALOR GLOBAL ATIVO ---
valor_global_total = df_ativos["VALOR GLOBAL"].sum()
valor_anual_total = df_ativos["VALOR ANUAL ATUAL"].sum()
# Contagem de status
# --- TÍTULO ---
st.title("📁 Painel Gerencial de Contratos")

aba1, aba2, aba3 = st.tabs(["📊 Visão Geral", "⏱️ Prazos", "📋 Contratos"])

with aba1:
    # --- Métricas principais ---
    st.markdown("### 📊 Visão Consolidada")
    col1, col2, col3,  col4 = st.columns(4)
    col1.metric("📄 Contratos Ativos", len(df_ativos))
    col2.metric("📆 Encerrados neste mês", len(df_vencidos_mes))
    col3.container()  # Usando container para agrupar

    # Exibindo o título com uma formatação mais suave
    col3.markdown(
        f"<h4 style='font-size: 16px; font-weight: bold;'>💰 Valor Global Ativo</h4>"
    ,unsafe_allow_html=True)

    # Exibindo o valor, mas de forma suave, sem expandir a altura
    col3.markdown(
        f"<p style='font-size: 17px; font-weight: normal; color: #333;'>"
        f"R$ {valor_global_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") +
        f"</p>"
    ,unsafe_allow_html=True)

    # Exibindo o título do valor anual
    col4.markdown(
        f"<h5 style='font-size: 16px; font-weight: bold;'>Valor Anual</h5>"
    ,unsafe_allow_html=True)

    # Exibindo o valor anual de forma suavizada
    col4.markdown(
        f"<p style='font-size: 17px; font-weight: normal; color: #333;'>"
        f"R$ {valor_anual_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") +
        f"</p>"
    ,unsafe_allow_html=True)

    # --- Classificação de vencimentos ---
    st.markdown("### ⏱️ Prazos de Encerramento")
    col4, col5, col6, col7, col8, col9 = st.columns(6)
    col4.metric("⚠️ Até 30 dias", len(df_ativos[df_ativos["DIAS_PARA_VENCER"] <=30]))
    col5.metric("🕒 Até 90 dias", len(df_ativos[(df_ativos["DIAS_PARA_VENCER"] > 30) & (df_ativos["DIAS_PARA_VENCER"] <= 90)]))
    col6.metric("Até 120 dias", len(df_ativos[(df_ativos["DIAS_PARA_VENCER"] > 90) & (df_ativos["DIAS_PARA_VENCER"] <= 120)]))
    col7.metric("Até 210 dias", len(df_ativos[(df_ativos["DIAS_PARA_VENCER"] > 120) & (df_ativos["DIAS_PARA_VENCER"] <= 210)]))
    col8.metric("✅ +7 meses", len(df_ativos[df_ativos["DIAS_PARA_VENCER"] >210]))
    col9.metric("🔒 Indeterminado", len(df_indeterminados))
    
    #st.markdown("#### 📌 <span style='font-size:18px;'>Situação Atual dos Contratos</span>", unsafe_allow_html=True)

    # Caso ambos existam: usar colunas
    if not df_vencendo_hoje.empty and not df_vencendo_7_dias.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                f"<div style='color:#cc0000; background-color:#ffe6e6; padding:8px; border-radius:8px; font-size:15px;'>"
                f"🚨 <strong>{len(df_vencendo_hoje)}</strong> contrato(s) vencem <u>hoje</u></div>",
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                f"<div style='color:#996600; background-color:#fff5cc; padding:8px; border-radius:8px; font-size:15px;'>"
                f"⚠️ <strong>{len(df_vencendo_7_dias)}</strong> contrato(s) vencem nos próximos <u>7 dias</u></div>",
                unsafe_allow_html=True
            )
            
            st.markdown(
                f"<div style='color:#996600; background-color:#fff5cc; padding:8px; border-radius:8px; font-size:15px;'>"
                f"⚠️ <strong>{len(df_vencendo_15_dias)}</strong> contrato(s) vencem nos próximos <u>15 dias</u></div>",
                unsafe_allow_html=True
            )

    # Caso só "hoje"
    elif not df_vencendo_hoje.empty:
        st.markdown(
            f"<div style='color:#cc0000; background-color:#ffe6e6; padding:8px; border-radius:8px; font-size:15px;'>"
            f"🚨 <strong>{len(df_vencendo_hoje)}</strong> contrato(s) vencem <u>hoje</u></div>",
            unsafe_allow_html=True
        )

    # Caso só "7 dias"
    elif not df_vencendo_7_dias.empty:
        st.markdown(
            f"<div style='color:#996600; background-color:#fff5cc; padding:8px; border-radius:8px; font-size:15px;'>"
            f"⚠️ <strong>{len(df_vencendo_7_dias)}</strong> contrato(s) vencem nos próximos <u>7 dias</u></div>",
            unsafe_allow_html=True
        )
    
    elif not df_vencendo_15_dias.empty:
        st.markdown(
            f"<div style='color:#997a00; background-color:#ffffcc; padding:8px; border-radius:8px; font-size:15px;'>"
            f"⏰ <strong>{len(df_vencendo_15_dias)}</strong> contrato(s) vencem nos próximos <u>15 dias</u></div>",
            unsafe_allow_html=True
        )

    # Nenhum vencendo
    else:
        st.markdown(
            "<div style='color:#006600; background-color:#e6ffe6; padding:8px; border-radius:8px; font-size:15px;'>"
            "✅ Nenhum contrato vencendo em breve</div>",
            unsafe_allow_html=True
        )

    st.markdown("<div style='font-size:13px; margin-top:8px;'>🔎 Consulte a aba 👉 <strong>'Detalhamento dos Contratos'</strong> para mais informações.</div>", unsafe_allow_html=True)
    st.markdown("---")
    
    
    col_g1, col_g2 = st.columns(2)

    def ajuste_gráficos(df_contratos_unicos):
        df_graficos = df_ativos.copy()

        # 1. Limpeza e padronização dos campos REGIONAIS e UNIDADE
        df_graficos['REGIÕES'] = df_graficos['REGIÕES'].str.strip().str.upper()
        df_graficos['UNIDADE'] = df_graficos['UNIDADE'].str.strip().str.upper()

        # Para garantir que o agrupamento considere variações de formato, podemos dividir múltiplos valores de "REGIÕES" e "UNIDADE" que estão em uma célula em valores individuais:
        df_graficos['REGIÕES'] = df_graficos['REGIÕES'].apply(lambda x: [item.strip() for item in x.split('/')])  # Dividir por '/' e limpar os espaços
        df_graficos['UNIDADE'] = df_graficos['UNIDADE'].apply(lambda x: [item.strip() for item in x.split('/')]) 

        return df_graficos


    df_graficos = ajuste_gráficos(df_contratos_unicos)
    
    with col_g1:
        st.markdown("##### 🏢 Total de Unidades por Região")

        

        # Agora, vamos explodir esses valores, criando uma linha para cada unidade ou região
        df_explodido = df_graficos.explode('REGIÕES').explode('UNIDADE')
        
        # 2. Unidades por Região (contagem única após limpeza)
        df_unidades = df_explodido.groupby("REGIÕES")["UNIDADE"].nunique().reset_index(name="UNIDADES")
        
        df_unidades = df_unidades.sort_values(by="UNIDADES", ascending=True)
        
        # Criação do gráfico
        fig2 = px.bar(df_unidades, 
                    x="UNIDADES", 
                    y="REGIÕES", 
                    orientation="h", 
                    color_discrete_sequence=["#4c78a8"],
                    text="UNIDADES")  # Adiciona rótulos dentro das barras

        # Ajuste do layout para melhorar o visual
        fig2.update_traces(texttemplate='%{text}', textposition='inside')

        # Exibe o gráfico
        st.plotly_chart(fig2, use_container_width=True)


        # ===============
        #
        # GRÁFICO DE QUANTIDADE DE ENCERRAMENTOS NO MÊS
        #
        # =================

        st.markdown("##### 📆 Encerramentos por Mês")
        # Dicionário de meses em português abreviado
        meses_pt = {
            1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
        }

        # Garante que VIGÊNCIA seja datetime
        df_graficos["VIGÊNCIA"] = pd.to_datetime(df_graficos["VIGÊNCIA"], errors='coerce')
        # FILTRA CONTRATOS COM DATA DE ENCERRAMENTO
        encerramentos_mes = df_graficos[df_graficos["VIGÊNCIA"].notna()].copy()
        

        # EXTRAI ANO E MÊS
        encerramentos_mes["Ano"] = encerramentos_mes["VIGÊNCIA"].dt.year
        encerramentos_mes["Mês"] = encerramentos_mes["VIGÊNCIA"].dt.month
        encerramentos_mes["Ano-Mês"] = encerramentos_mes["VIGÊNCIA"].dt.to_period("M").dt.to_timestamp()
        encerramentos_mes["Rótulo"] = encerramentos_mes.apply(
            lambda row: f"{meses_pt[row['Mês']]}/{row['Ano']}", axis=1
        )

        # SELEÇÃO DE ANO
        anos_disponiveis = sorted(encerramentos_mes["Ano"].unique(), reverse=False)
        col1, col2, col3 = st.columns([1, 3, 1])
        with col3:
            ano_selecionado = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(2025) if 2025 in anos_disponiveis else 0)

        # FILTRA PELO ANO ESCOLHIDO
        encerramentos_ano = encerramentos_mes[encerramentos_mes["Ano"] == ano_selecionado]

        # AGRUPAMENTO
        encerramentos_grouped = encerramentos_ano.groupby(["Ano-Mês", "Rótulo"]).size().reset_index(name="Total")
        encerramentos_grouped = encerramentos_grouped.sort_values("Ano-Mês")

        # EXIBE GRÁFICO
        if encerramentos_grouped.empty:
            st.info("Nenhum contrato com data de encerramento definida nos critérios selecionados.")
        else:
            
            fig = px.bar(encerramentos_grouped, x="Rótulo", y="Total",
                        #title=f"Contratos com Encerramento por Mês - {ano_selecionado}",
                        #labels={"Rótulo": "Mês de Encerramento", "Total": "Quantidade"},
                        text_auto=True,
                        color_discrete_sequence=["#2ECC71"] if ano_selecionado == 2025 else ["#95A5A6"])
            #fig.update_layout(xaxis_title="Mês", yaxis_title="Quantidade", title_x=0.5)
            st.plotly_chart(fig, use_container_width=True)



    with col_g2:

        # ===============
        #
        # TOTAL DOS CONTRATOS POR REGIÃO
        #
        # =================
        
        st.markdown("##### 📄 Total de Contratos por Região")

        # Corrigir a coluna 'REGIÕES' para ser string simples (não lista!)
        df_graficos["REGIÕES"] = df_graficos["REGIÕES"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else str(x)
        ).str.strip()
        # Agrupar os dados por Região
        resumo_regiao = (
            df_graficos.groupby("REGIÕES")
            .agg(
                Total_Contratos=("CONTRATO", "count"),
                Valor_Mensal=("VALOR ATUAL MENSAL", "sum"),
                Valor_Anual=("VALOR ANUAL ATUAL", "sum")
            )
            .sort_values(by="Total_Contratos", ascending=False)
            .reset_index()
        )

        # Formatando os valores para exibir nos cards (gráfico usa os numéricos mesmo)
        resumo_regiao["Valor_Mensal_Formatado"] = resumo_regiao["Valor_Mensal"].apply(lambda x: f"R$ {x:,.2f}".replace(".", "X").replace(",", ".").replace("X", ","))
        resumo_regiao["Valor_Anual_Formatado"] = resumo_regiao["Valor_Anual"].apply(lambda x: f"R$ {x:,.2f}".replace(".", "X").replace(",", ".").replace("X", ","))

        # Gráfico com quantidade de contratos por região, com rótulos nas barras
        fig = px.bar(
            resumo_regiao,
            x="REGIÕES",
            y="Total_Contratos",
            text="Total_Contratos",
            #title="Total de Contratos por Região",
            labels={"REGIÕES": "Região", "Total_Contratos": "Total de Contratos"},
            color_discrete_sequence=["#3498DB"]
        )
        fig.update_traces(textposition="outside")
        #fig.update_layout(xaxis_title="Região", yaxis_title="Total de Contratos", title_x=0.5)

        st.plotly_chart(fig, use_container_width=True)
    

        # ===============
        #
        # QUANTIDADE DE CONTRATOS QUE VÃO ENCERRAR POR MÊS E REGIÃO
        #
        # =================

        st.markdown("##### 📆 Encerramentos por Mês e Regiões")

        # Dicionário de meses em português abreviado
        meses_pt = {
            1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
        }

        # Garante que VIGÊNCIA seja datetime
        df_graficos["VIGÊNCIA"] = pd.to_datetime(df_graficos["VIGÊNCIA"], errors='coerce')
        
        # FILTRA CONTRATOS COM DATA DE ENCERRAMENTO
        encerramentos_mes = df_graficos[df_graficos["VIGÊNCIA"].notna()].copy()

        # EXTRAI ANO E MÊS
        encerramentos_mes["Ano"] = encerramentos_mes["VIGÊNCIA"].dt.year
        encerramentos_mes["Mês"] = encerramentos_mes["VIGÊNCIA"].dt.month
        encerramentos_mes["Ano-Mês"] = encerramentos_mes["VIGÊNCIA"].dt.to_period("M").dt.to_timestamp()
        encerramentos_mes["Rótulo"] = encerramentos_mes.apply(
            lambda row: f"{meses_pt[row['Mês']]}/{row['Ano']}", axis=1
        )

        # SELEÇÃO DE ANO
        anos_disponiveis = sorted(encerramentos_mes["Ano"].unique(), reverse=False)
        col1, col2, col3 = st.columns([1, 3, 1])
        with col3:
            ano_selecionado = st.selectbox("Ano",
                anos_disponiveis, 
                index=anos_disponiveis.index(2025) if 2025 in anos_disponiveis else 0, key='unico'
            )
        # FILTRA PELO ANO ESCOLHIDO
        encerramentos_ano = encerramentos_mes[encerramentos_mes["Ano"] == ano_selecionado]

        # AGRUPAMENTO
        # Supondo que a coluna "Unidade" seja a coluna que indica as unidades
        encerramentos_grouped = encerramentos_ano.groupby(["Ano-Mês", "Rótulo", "REGIÕES"]).size().reset_index(name="Total")
        encerramentos_grouped = encerramentos_grouped.sort_values("Ano-Mês")
        
        # EXIBE GRÁFICO
        if encerramentos_grouped.empty:
            st.info("Nenhum contrato com data de encerramento definida nos critérios selecionados.")
        else:
            fig = px.bar(
                encerramentos_grouped,
                x="Rótulo", 
                y="Total",
                color="REGIÕES",  # Colocando a unidade para colorir as barras
                #title=f"Contratos com Encerramento por Mês - {ano_selecionado}",
                labels={"Rótulo": "Mês de Encerramento", "Total": "Quantidade", "REGIÕES": "Região"},
                text_auto=True
            )
            #fig.update_layout(xaxis_title="Mês",yaxis_title="Quantidade",title_x=0.5)
            st.plotly_chart(fig, use_container_width=True)

        # ===============
        #
        # VALOR ANUAL GERAL
        #
        # =================


    st.markdown("##### 💰 Total de Valor Anual por Região")

    
            # --- total geral (antes do filtro) ---
    df_ativos_geral = df[(df["STATUS"] == 'Ativo')]
    resumo_total = df_ativos_geral.groupby("REGIÕES")["VALOR ANUAL ATUAL"].sum().reset_index()
    resumo_total = resumo_total.rename(columns={"VALOR ANUAL ATUAL": "Valor_Anual_Total"})

    # --- filtrado ---
    resumo_filtrado = df_graficos.groupby("REGIÕES")["VALOR ANUAL ATUAL"].sum().reset_index()
    resumo_filtrado = resumo_filtrado.rename(columns={"VALOR ANUAL ATUAL": "Valor_Anual_Filtrado"})

    # --- junta os dois ---
    resumo_comparativo = pd.merge(resumo_total, resumo_filtrado, on="REGIÕES", how="left")
    resumo_comparativo["Valor_Anual_Filtrado"] = resumo_comparativo["Valor_Anual_Filtrado"].fillna(0)

    # --- adiciona rótulos formatados ---
    resumo_comparativo["Label_Total"] = resumo_comparativo["Valor_Anual_Total"].apply(
        lambda x: f"R$ {x:,.2f} (100%)".replace(".", "X").replace(",", ".").replace("X", ",")
    )

    resumo_comparativo["Percentual_Filtrado"] = (
        resumo_comparativo["Valor_Anual_Filtrado"] / resumo_comparativo["Valor_Anual_Total"]
    ) * 100

    resumo_comparativo["Label_Filtrado"] = resumo_comparativo.apply(
        lambda row: f"R$ {row['Valor_Anual_Filtrado']:,.2f} ({row['Percentual_Filtrado']:.2f}%)"
            .replace(".", "X").replace(",", ".").replace("X", ","),
        axis=1
    )
    

    # Verifica se há filtro aplicado (ou seja, se algum valor filtrado difere do total)
    mostrar_filtrado = not resumo_comparativo["Valor_Anual_Total"].equals(resumo_comparativo["Valor_Anual_Filtrado"])

    cor_total = "#2ECC71" if not mostrar_filtrado else "#dcdcdc"

    # --- gráfico ---
    fig = go.Figure()

    # Barra do total, com cor variável
    fig.add_trace(go.Bar(
        x=resumo_comparativo["REGIÕES"],
        y=resumo_comparativo["Valor_Anual_Total"],
        name="Total Geral",
        marker_color=cor_total,
        text=resumo_comparativo["Label_Total"],
        textposition="outside"
    ))

    # Se houver filtro, adiciona a barra verde com valor filtrado
    if mostrar_filtrado:
        fig.add_trace(go.Bar(
            x=resumo_comparativo["REGIÕES"],
            y=resumo_comparativo["Valor_Anual_Filtrado"],
            name="Valor Filtrado",
            marker_color="#2ECC71",
            text=resumo_comparativo["Label_Filtrado"],
            textposition="auto"
        ))

    fig.update_layout(
        barmode="overlay",
        #title="💰 Comparativo de Valor Anual por Região (Total vs Filtrado)",
        xaxis_title="Região",
        yaxis_title="Valor Anual",
        uniformtext_minsize=8,
        uniformtext_mode="show",  # <- isso força exibição dos textos
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        #insidetextanchor="middle"
    )


    st.plotly_chart(fig, use_container_width=True)

        # ===============
        #
        # VALOR ANUAL POR REGIÃO
        #
        # =================

    if regioes_selecionadas:
        st.markdown(f"##### 🏢 Valor Anual por Unidade na Região")

        # Filtrando unidades que aparecem em qualquer uma das regiões selecionadas
        df_ativos_filtrado = df_filtrado[(df_filtrado["STATUS"] == 'Ativo')]
        df_regiao = df_ativos_filtrado[df_ativos_filtrado["REGIÕES"].apply(
            lambda x: any(regiao in x for regiao in regioes_selecionadas)
        )]

        resumo_unidades = df_regiao.groupby("UNIDADE")["VALOR ANUAL ATUAL"].sum().reset_index()
        resumo_unidades = resumo_unidades.sort_values(by="VALOR ANUAL ATUAL", ascending=True)

        # Abreviar nomes longos para exibir no gráfico
        resumo_unidades["UNIDADE_ABREVIADA"] = resumo_unidades["UNIDADE"].apply(
            lambda x: x if len(x) <= 40 else x[:37] + "..."
        )

        # Rótulo formatado
        resumo_unidades["Label"] = resumo_unidades["VALOR ANUAL ATUAL"].apply(
            lambda x: f"R$ {x:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
        )

        # Criação do gráfico com Plotly Express
        fig_unidades = px.bar(
            resumo_unidades,
            x="VALOR ANUAL ATUAL",
            y="UNIDADE_ABREVIADA",
            orientation="h",
            text="Label",
            hover_data={"UNIDADE": True, "VALOR ANUAL ATUAL": True},
            labels={"VALOR ANUAL ATUAL": "Valor Anual", "UNIDADE_ABREVIADA": "Unidade"},
            color_discrete_sequence=["#F39C12"],
        )

        fig_unidades.update_traces(textposition="auto",
             textfont_size=11)

        fig_unidades.update_layout(
            height=60 + 35 * len(resumo_unidades),  # altura ajustável conforme quantidade
            margin=dict(l=100, r=60, t=30, b=30),
            xaxis_title="Valor Anual",
            yaxis_title=None
        )

        st.plotly_chart(fig_unidades, use_container_width=True)

        # ===============
        #
        # VALOR ANUAL POR UNIDADE
        #
        # =================

        # Estilizando a página para um selectbox minimalista
        
    if unidades_selecionadas:
        st.markdown(f"##### 📦 Total de Valor Anual por Objeto nas Unidades Selecionadas")

        def unidade_bate(campo_unidade):
            campo = str(campo_unidade).upper().strip()

            # Verifica se alguma unidade selecionada está contida no campo (ou vice-versa)
            for sel in unidades_selecionadas:
                sel = sel.upper().strip()
                if sel in campo or campo in sel:
                    return True
            return False
        df_ativos_filtrado = df_filtrado[(df_filtrado["STATUS"] == 'Ativo')]
        df_unidade = df_ativos_filtrado[df_ativos_filtrado["UNIDADE"].apply(unidade_bate)]
        
        resumo_objetos = df_unidade.groupby("OBJETO")["VALOR ANUAL ATUAL"].sum().reset_index()
        resumo_objetos = resumo_objetos.sort_values(by="VALOR ANUAL ATUAL", ascending=True)
        resumo_objetos["Label"] = resumo_objetos["VALOR ANUAL ATUAL"].apply(
            lambda x: f"R$ {x:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
        )

        resumo_objetos["Objeto Abreviado"] = resumo_objetos["OBJETO"].apply(
            lambda x: x if len(x) <= 40 else x[:37] + "..."
        )

        fig_objetos = go.Figure()

        fig_objetos.add_trace(go.Bar(
            x=resumo_objetos["VALOR ANUAL ATUAL"],
            y=resumo_objetos["Objeto Abreviado"],
            text=resumo_objetos["Label"],
            hovertext=resumo_objetos["OBJETO"],
            hoverinfo="text",
            orientation="h",
            marker_color="#3498DB",
            textposition="auto"
        ))

        fig_objetos.update_layout(
            xaxis_title="Valor Anual",
            yaxis_title="Objeto",
            margin=dict(l=80, r=20, t=20, b=40),
            height=600,
        )

        st.plotly_chart(fig_objetos, use_container_width=True)

    if objetos_selecionados:
        st.markdown("##### 🏢 Comparativo de Valor Anual por Unidade para o(s) Objeto(s) Selecionado(s)")
        
        #df_objeto = df_contratos_unicos[df_contratos_unicos["OBJETO"].isin(objetos_selecionados)]
        df_ativos_filtrado = df_filtrado[(df_filtrado["STATUS"] == 'Ativo')]
        regex_pattern = r'\b(' + '|'.join([re.escape(obj) for obj in objetos_selecionados]) + r')\b'
        if modo_visao == "Focar no Objeto": 
            df_objeto = df_ativos_filtrado[df_ativos_filtrado["OBJETO"].str.contains(regex_pattern, case=False, na=False)]
        else:  # Ver Contrato Completo
            contratos_com_objeto = df_ativos_filtrado[df_ativos_filtrado['OBJETO'].str.contains(regex_pattern, case=False, na=False)]['CONTRATO'].unique()
            df_objeto = df_ativos_filtrado[df_ativos_filtrado['CONTRATO'].isin(contratos_com_objeto)]
        # Agrupa os valores por unidade
        resumo_unidades = df_objeto.groupby("UNIDADE")["VALOR ANUAL ATUAL"].sum().reset_index()
        # Ordena do maior para o menor
        resumo_unidades = resumo_unidades.sort_values(by="VALOR ANUAL ATUAL", ascending=False)

        # Formata os rótulos
        resumo_unidades["Label"] = resumo_unidades["VALOR ANUAL ATUAL"].apply(
            lambda x: f"R$ {x:,.2f}".replace(".", "X").replace(",", ".").replace("X", ",")
        )

        # Abrevia nomes longos para exibir no eixo Y
        resumo_unidades["Unidade Abreviado"] = resumo_unidades["UNIDADE"].apply(
            lambda x: x if len(x) <= 40 else x[:37] + "..."
        )

        # Filtro: Top N unidades com maior valor
        top_n = st.slider("📊 Quantas unidades deseja comparar?", min_value=5, max_value=30, value=10)
        resumo_top = resumo_unidades.head(top_n)

        # Gráfico (mantém ordem decrescente visualmente)
        fig = px.bar(
            resumo_top,
            x="VALOR ANUAL ATUAL",
            y="Unidade Abreviado",
            text="Label",
            orientation="h",
            labels={"VALOR ANUAL ATUAL": "Valor Anual", "UNIDADE": "Unidade"},
            color_discrete_sequence=["#3498DB"],
            hover_name="UNIDADE"
        )

        fig.update_traces(
            textposition="auto",
            textfont_size=11
        )
        fig.update_layout(
            xaxis_title="Valor Anual",
            yaxis_title="Unidade",
            height=60 + 40 * top_n,
            margin=dict(l=100, r=60, t=30, b=30)
        )

        st.plotly_chart(fig, use_container_width=True)

# --- Aba 2: Detalhamento dos Contratos ---
with aba2:
    st.subheader("📋 Situação de Encerramento")

    def resumir_texto(texto, limite=40):
        if pd.isna(texto):
            return ""
        return texto if len(texto) <= limite else texto[:limite] + "..."

    def format_date(date):
        if isinstance(date, pd.Timestamp):
            return date.strftime("%d/%m/%Y")
        try:
            return datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
        except Exception:
            return str(date)

    def mostrar_cards_scroll(df, cor, tag):
        df = df.copy()
        df['VIGÊNCIA'] = pd.to_datetime(df['VIGÊNCIA'], errors='coerce')
        df = df.sort_values(by='VIGÊNCIA')

        # Container com altura fixa e scroll vertical
        container_style = """
            max-height: auto; 
            overflow-y: auto; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            padding: 0 10px;
            background: #fafafa;
        """
        st.markdown(f"<div style='{container_style}'>", unsafe_allow_html=True)

        # Cabeçalho fixo
        st.markdown(f"""
            <div style="
                display: flex; 
                background-color: #f0f2f6; 
                font-weight: bold; 
                font-size: 14px; 
                color: #222;
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px; 
                padding: 12px 8px;
                border-bottom: 2px solid {cor};
                position: sticky;
                top: 0;
                z-index: 10;
                overflow-y: auto;
            ">
                <div style='flex: 1 1 14%; min-width: 140px;'>📁 Contrato</div>
                <div style='flex: 1 1 14%; min-width: 140px;'>🔍 Processo</div>
                <div style='flex: 1 1 16%; min-width: 160px;'>🏢 Unidade</div>
                <div style='flex: 1 1 22%; min-width: 220px;'>📌 Objetos</div>
                <div style='flex: 1 1 10%; min-width: 100px;'>📅 Vigência</div>
                <div style='flex: 1 1 6%; min-width: 60px;'>⏳ Restam</div>
                <div style='flex: 1 1 18%; min-width: 180px; text-align: right;'>Valores</div>
            </div>
        """, unsafe_allow_html=True)
        linhas = len(df)
        altura_linha = 115  # média estimada por linha (ajuste fino se quiser)
        altura_total = min(linhas * altura_linha, 400)

        with st.container(height=altura_total, border=False):
            for _, row in df.iterrows():
                vigencia = row['VIGÊNCIA']
                vigencia_formatada = format_date(vigencia) if pd.notna(vigencia) else "Indeterminado"
                dias_restantes = row['DIAS_PARA_VENCER']

                # Se o valor for NaN, coloca "Indeterminado"
                if pd.isna(dias_restantes):
                    dias_txt = "Indeterminado"
                else:
                    # Certifica que é inteiro e >= 0
                    dias_restantes = max(int(dias_restantes), 0)
                    dias_txt = f"{dias_restantes} dias"
                #valor_mensal = f"R$ {row['VALOR ATUAL MENSAL']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                #valor_anual = f"R$ {row['VALOR ANUAL ATUAL']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                #valor_global = f"R$ {row['VALOR GLOBAL']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                # Lista itens objeto
                itens_objeto = [item.strip() for item in str(row['OBJETO']).split('/') if item.strip()]
                objetos_html = "<ul style='margin: 0; padding-left: 18px; color: #555; font-size: 13px; list-style-type: disc;'>"
                for item in itens_objeto[:6]:
                    objetos_html += f"<li>{item}</li>"
                objetos_html += "</ul>"

                # Valores formatados em coluna à direita com mais espaço e espaçamento vertical
                valores_html = f"""
                    <div style="font-size: 13px; color: #444; line-height: 1.5; display: flex; flex-direction: column; align-items: flex-end; gap: 2px;">
                        <div>💰 <b>Mensal:</b> {row['VALOR ATUAL MENSAL']}</div>
                        <div>📈 <b>Anual:</b> {row['VALOR ANUAL ATUAL']}</div>
                        <div>💼 <b>Global:</b> {row['VALOR GLOBAL']}</div>
                        <div style="color: {cor}; font-weight: bold; margin-top: 6px;">🏷️ {tag}</div>
                    </div>
                """

                # Linha do card flexbox
                linha_html = f"""
                    <div style="
                        display: flex; 
                        padding: 12px 8px; 
                        border-bottom: 1px solid #eee; 
                        align-items: flex-start;
                        font-size: 14px; 
                        color: #222;
                        gap: 8px;
                    ">
                        <div style='flex: 1 1 14%; min-width: 140px; font-weight: 600;'>📁 {row['CONTRATO']}</div>
                        <div style='flex: 1 1 14%; min-width: 140px;'>{row['PROCESSO']}</div>
                        <div style='flex: 1 1 16%; min-width: 160px;'>{row['UNIDADE']}</div>
                        <div style='flex: 1 1 22%; min-width: 220px;'>{objetos_html}</div>
                        <div style='flex: 1 1 10%; min-width: 100px;'>{vigencia_formatada}</div>
                        <div style='flex: 1 1 6%; min-width: 60px;'>{dias_txt}</div>
                        <div style='flex: 1 1 18%; min-width: 180px; text-align: right;'>{valores_html}</div>
                    </div>
                """

                st.markdown(linha_html, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    # ===========
    # GERAR PDF
    #============

    # Função para formatar valores monetários (pt-br)
    #def formatar_valor(valor):
     #   return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def gerar_pdf_contratos(df, faixas_selecionadas, tipo_prazo):
        """
        Gera um PDF filtrando os contratos com base na faixa de dias para vencer.
        Opções de faixa_prazo_selecionada:
        - 'Tudo'
        - 'Até 30 dias'
        - 'Até 90 dias'
        - 'Até 120 dias'
        - 'Até 210 dias'
        """
        buffer = BytesIO()

        faixas_dict_vencimento = {
            '0 a 7 dias': (0, 7),
            '8 a 15 dias': (8, 15),
            '16 a 30 dias': (16, 30),
            '31 a 90 dias': (31, 90),
            '91 a 120 dias': (91, 120),
            '121 a 210 dias': (121, 210)
        }

        faixas_dict_entrada = {
            'Hoje': (0, 0),
            'Últimos 7 dias': (1, 7),
            'Últimos 15 dias': (8, 15),
            'Últimos 30 dias': (16, 30),
            'Últimos 60 dias': (31, 60),
            'Últimos 90 dias': (61, 90)
        }

        styles = getSampleStyleSheet()
        style_centered_title = ParagraphStyle(
            'TitleCentered',
            parent=styles['Heading1'],
            alignment=TA_CENTER,
            fontSize=14,
            spaceAfter=14
        )

        style_faixa = ParagraphStyle(
            'FaixaTitle',
            parent=styles['Heading3'],
            fontSize=10,
            backColor=colors.lightblue,
            textColor=colors.darkblue,
            spaceAfter=6
        )

        style_cell = ParagraphStyle('WrappedCell', fontSize=8, leading=10)

        pdf = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )

        elementos = []

        # Determina quais faixas usar
        if tipo_prazo == 'entrada':
            faixas_dict = faixas_dict_entrada
            coluna_dias = 'DIAS_DESDE_ENTRADA'
            titulo_principal = "Relatório de Contratos que entraram no período de renovação"
            texto_dias = "Dias desde entrada"
        else:
            faixas_dict = faixas_dict_vencimento
            coluna_dias = 'DIAS_PARA_VENCER'
            titulo_principal = "Relatório de Contratos a Vencer"
            texto_dias = "Dias para vencer"

        if not faixas_selecionadas or 'Tudo' in faixas_selecionadas:
            faixas_ativas = list(faixas_dict.keys())
        else:
            # Mantém a ordem do dict, mesmo filtrando
            faixas_ativas = [k for k in faixas_dict.keys() if k in faixas_selecionadas]

        for regiao in sorted(df['REGIÕES'].dropna().unique()):
            df_regiao_total = df[df['REGIÕES'] == regiao]

            if df_regiao_total.empty:
                continue

            elementos.append(Paragraph(f"{titulo_principal} - {regiao}", style_centered_title))
            elementos.append(Spacer(1, 10))

            for faixa_nome in faixas_ativas:
                faixa_limite = faixas_dict[faixa_nome]

                df_faixa = df_regiao_total[
                    (df_regiao_total[coluna_dias] >= faixa_limite[0]) &
                    (df_regiao_total[coluna_dias] <= faixa_limite[1])
                ]

                if df_faixa.empty:
                    continue

                elementos.append(Paragraph(f"Período: {faixa_nome}", style_faixa))
                df_faixa = df_faixa.sort_values(by=coluna_dias)

                tabela_dados = [[
                    'CONTRATO', 'UNIDADE', 'OBJETO', 'CONTRATADA',
                    'VALOR GLOBAL', 'VIGÊNCIA', 'DIAS'
                ]]

                dados_linha = []

                for i, (_, linha) in enumerate(df_faixa.iterrows(), start=1):
                    contrato_str = str(linha['CONTRATO'])
                    valor_formatado = linha['VALOR GLOBAL'] if not pd.isna(linha['VALOR GLOBAL']) else ''
                    dias_valor = str(int(linha['DIAS_PARA_VENCER'])) if not pd.isna(linha['DIAS_PARA_VENCER']) else 'N/A'

                    row = [
                        Paragraph(contrato_str, style_cell),
                        Paragraph(str(linha['UNIDADE']), style_cell),
                        Paragraph(str(linha['OBJETO']), style_cell),
                        Paragraph(str(linha['CONTRATADA']), style_cell),
                        valor_formatado,
                        linha['VIGÊNCIA'].strftime("%d/%m/%Y") if not pd.isna(linha['VIGÊNCIA']) else '',
                        dias_valor
                    ]
                    tabela_dados.append(row)
                    dados_linha.append(i)

                tabela = Table(tabela_dados, repeatRows=1, colWidths=[60, 100, 150, 110, 100, 70, 40])
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ])

                for i in dados_linha:
                    cor = colors.whitesmoke if i % 2 == 0 else None
                    if cor:
                        style.add('BACKGROUND', (0, i), (-1, i), cor)

                tabela.setStyle(style)
                elementos.append(tabela)
                elementos.append(Spacer(1, 10))

            elementos.append(PageBreak())

        if not elementos:
            return None

        pdf.build(elementos)
        buffer.seek(0)
        return buffer

    def mostrar_todos_cards(df, mostrar_entradas=False, selecionados_entrada=None, faixas_selecionadas=None):
        hoje = datetime.today().date()
        
        if mostrar_entradas:
            # Lista dos intervalos possíveis
            opcoes_intervalos = {
                "Hoje": 0,
                "Últimos 7 dias": 7,
                "Últimos 15 dias": 15,
                "Últimos 30 dias": 30,
                "Últimos 60 dias": 60,
                "Últimos 90 dias": 90
            }

        # Se nada for selecionado, assume que o usuário quer ver todos os períodos
            if not selecionados_entrada:
                selecionados_entrada = list(opcoes_intervalos.keys())
            # Ordenar pelos dias (do menor para o maior)
            selecionados_ordenados = sorted(selecionados_entrada, key=lambda x: opcoes_intervalos[x])

            # Para manter referência do último limite superior (ex: para "Últimos 7 dias", o anterior pode ser "Hoje", que é 0)
            limite_inferior = -1

            for intervalo in selecionados_ordenados:
                limite_superior = opcoes_intervalos[intervalo]

                # Filtrar entre os dois limites
                filtrados = df[
                    (df['DIAS_DESDE_ENTRADA'] > limite_inferior) &
                    (df['DIAS_DESDE_ENTRADA'] <= limite_superior)
                ]

                if not filtrados.empty:
                    st.markdown(f"<br>", unsafe_allow_html=True)
                    st.markdown(f"#### 🟢 {intervalo}")
                    mostrar_cards_scroll(filtrados, "#008000", f"{intervalo}")

                # Atualiza o limite inferior para a próxima faixa
                limite_inferior = limite_superior

        else:
            faixas_dict = {
            'Encerramento: 0 a 7 dias': (0, 7),
            'Encerramento: 8 a 15 dias': (8, 15),
            'Encerramento: 16 a 30 dias': (16, 30),
            'Encerramento: 31 a 90 dias': (31, 90),
            'Encerramento: 91 a 120 dias': (91, 120),
            'Encerramento: 121 a 210 dias': (121, 210)
            }

            # Cores e emojis por faixa
            cores_emojis = {
                'Encerramento: 0 a 7 dias': ("#DC143C", "🛑", "Encerrará em até 7 dias"),
                'Encerramento: 8 a 15 dias': ("#FFA500", "⚠️", "Encerrará em até 15 dias"),
                'Encerramento: 16 a 30 dias': ("#FFA500", "⚠️", "Encerrará em até 30 dias"),
                'Encerramento: 31 a 90 dias': ("#FFD700", "📅", "Encerrará em até 90 dias"),
                'Encerramento: 91 a 120 dias': ("#FFD700", "📅", "Encerrará em até 120 dias"),
                'Encerramento: 121 a 210 dias': ("#90EE90", "📅", "Encerrará em até 210 dias"),
            }

            # Loop dinâmico por faixa
            for faixa, (inicio, fim) in faixas_dict.items():
                filtrados = df.query(f"{inicio} <= DIAS_PARA_VENCER <= {fim}")
                #filtrados = df[(df["DIAS_PARA_VENCER"] >= inicio) & (df["DIAS_PARA_VENCER"] <= fim)]
                if not filtrados.empty:
                    cor, emoji, subtitulo = cores_emojis.get(faixa, ("#D3D3D3", "📌", "Prazo indefinido"))
                    st.markdown(f"<br>", unsafe_allow_html=True)
                    st.markdown(f"##### {emoji} {faixa}")
                    mostrar_cards_scroll(filtrados, cor, subtitulo)

            # Encerram hoje (exato)
            encerram_hoje = df[df["DIAS_PARA_VENCER"] == 0]
            if not encerram_hoje.empty:
                st.markdown(f"<br>", unsafe_allow_html=True)
                st.markdown("##### 🛑 Encerram Hoje")
                mostrar_cards_scroll(encerram_hoje, "#DC143C", "Encerra Hoje")

            # Indeterminados (negativos ou valores especiais)
            indeterminados = df[df["DIAS_PARA_VENCER"] < 0]
            if not indeterminados.empty:
                st.markdown(f"<br>", unsafe_allow_html=True)
                st.markdown("##### 🔄 Vigência Indeterminada")
                mostrar_cards_scroll(indeterminados, "#6495ED", "Sem data definida")

            # Encerrados no mês atual
            encerrados_mes = df[(df["STATUS"] == "Encerrado") & (df["VIGÊNCIA"] >= inicio_mes)]
            if not encerrados_mes.empty:
                st.markdown(f"<br>", unsafe_allow_html=True)
                st.markdown("##### ✅ Encerrados no Mês")
                mostrar_cards_scroll(encerrados_mes, "#8B0000", "Encerrado neste mês")

    #mostrar_todos_cards(df_contratos_unicos)   

    # Aplica o filtro
    def filtrar_contratos(df, faixas_selecionadas=None, entrada_recente=False, intervalos_entrada=None):      
        
        DURACAO_TOTAL = 210
        df['DIAS_DESDE_ENTRADA'] = DURACAO_TOTAL - df['DIAS_PARA_VENCER']

        if entrada_recente:
            # Mapeia nomes para dias
            opcoes_intervalos = {
                "Hoje": 0,
                "Últimos 7 dias": 7,
                "Últimos 15 dias": 15,
                "Últimos 30 dias": 30,
                "Últimos 60 dias": 60,
                "Últimos 90 dias": 90
            }
            if not intervalos_entrada:
                return df.copy()

            mask = pd.Series(False, index=df.index)
            for sel in intervalos_entrada:
                limite = opcoes_intervalos[sel]
                mask |= (df['DIAS_DESDE_ENTRADA'] >= 0) & (df['DIAS_DESDE_ENTRADA'] <= limite)
            filtrados = df[mask]
            return filtrados

        # Filtro por vencimento normal
        faixas_dict = {
            '0 a 7 dias': (0, 7),
            '8 a 15 dias': (8, 15),
            '16 a 30 dias': (16, 30),
            '31 a 90 dias': (31, 90),
            '91 a 120 dias': (91, 120),
            '121 a 210 dias': (121, 210)
        }

        if not faixas_selecionadas or 'Tudo' in faixas_selecionadas:
            return df.copy()

        mask = np.zeros(len(df), dtype=bool)
        for faixa in faixas_selecionadas:
            if faixa in faixas_dict:
                start, end = faixas_dict[faixa]
                mask |= (df['DIAS_PARA_VENCER'] >= start) & (df['DIAS_PARA_VENCER'] <= end)

        return df[mask]

    with st.expander("🔍 Filtro de Período e Exportação"):
        faixas_disponiveis = ['Tudo', '0 a 7 dias', '8 a 15 dias', '16 a 30 dias', '31 a 90 dias', '91 a 120 dias', '121 a 210 dias']
        mostrar_entradas = st.toggle("🔄 Ver contratos que **entraram recentemente**", value=False)

        faixas_selecionadas = []
        selecionados_entrada = []

        if mostrar_entradas:
            opcoes_intervalos = ["Hoje", "Últimos 7 dias", "Últimos 15 dias", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias"]
            selecionados_entrada = st.multiselect("Intervalos:", opcoes_intervalos, default=["Últimos 7 dias"])
        else:
            faixas_selecionadas = st.multiselect("Selecione a(s) faixa(s) de vencimento:", faixas_disponiveis, default=[])


        # Aplica o filtro correto com base no toggle
        df_filtrado = filtrar_contratos(
            df_contratos_unicos,
            faixas_selecionadas=faixas_selecionadas,
            entrada_recente=mostrar_entradas,
            intervalos_entrada=selecionados_entrada
        )

        @st.cache_data
        def preprocessar_df(df):
            df = df.copy()
            df['VIGÊNCIA'] = pd.to_datetime(df['VIGÊNCIA'], errors='coerce')
            df['DIAS_PARA_VENCER'] = df['DIAS_PARA_VENCER'].fillna(-1).astype(int)
            # Pré-formatar valores para exibição, para evitar refazer depois
            df['VALOR ATUAL MENSAL'] = df['VALOR ATUAL MENSAL'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "R$ 0,00"
            )
            df['VALOR ANUAL ATUAL'] = df['VALOR ANUAL ATUAL'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "R$ 0,00"
            )
            df['VALOR GLOBAL'] = df['VALOR GLOBAL'].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "R$ 0,00"
            )
            # Já filtra só o que importa no começo, se quiser
            return df

            
        def filtros_mudaram():
            filtros = {
                "mostrar_entradas": mostrar_entradas,
                "selecionados_entrada": tuple(selecionados_entrada),  # se ainda existir esse filtro
                "faixas_selecionadas": tuple(faixas_selecionadas),    # idem

                # Novos filtros
                "regioes_selecionadas": tuple(regioes_selecionadas),
                "unidades_selecionadas": tuple(unidades_selecionadas),
                "contratos_selecionados": tuple(contratos_selecionados),
                "objetos_selecionados": tuple(objetos_selecionados),
                "modo_visao": modo_visao
            }

            if "filtros_salvos" not in st.session_state:
                st.session_state["filtros_salvos"] = filtros
                return True
            if st.session_state["filtros_salvos"] != filtros:
                st.session_state["filtros_salvos"] = filtros
                return True
            return False

        # Se filtros mudaram, apaga df_filtrado para recalcular
        if filtros_mudaram():
            if "df_filtrado" in st.session_state:
                del st.session_state["df_filtrado"]

        # Calcula df_filtrado só se não existir no estado
        if "df_filtrado" not in st.session_state:
            # Aqui sua função que processa o dataframe
            st.session_state.df_filtrado = preprocessar_df(df_filtrado)  # seu df original

        df_filtrado = st.session_state.df_filtrado
        # CSS customizado para estilizar e alinhar os botões
        # Adiciona botão "Gerar Relatório" com o mesmo estilo
        # Seu estilo CSS para os botões e container
        st.markdown("""
            <style>
                .buttons-container {
                    display: flex;
                    justify-content: flex-end;
                    gap: 6px;
                    margin-top: 2px;
                    margin-bottom: 6px;
                    flex-wrap: wrap;
                }
                .download-btn {
                    background-color: #f5f7fa;
                    color: #555 !important;
                    border: 1.5px solid #ccc;
                    border-radius: 8px;
                    padding: 8px 10px;
                    font-weight: 500;
                    font-size: 14px;
                    cursor: pointer;
                    transition: all 0.25s ease;
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    text-decoration: none;
                }
                .download-btn:hover {
                    background-color: #e1e7ed;
                    border-color: #a9b7c6;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                    color: #000 !important;
                    transform: translateY(-1px);
                }
                .download-btn svg {
                    width: 18px;
                    height: 18px;
                }
            </style>
        """, unsafe_allow_html=True)



        # Colunas para posicionar botão totalmente à direita
        col1, col2, col3 = st.columns([10, 9, 4])
        with col3:
            gerar = st.button("🔄 Gerar Relatório", type="secondary")
        
        if gerar:      
            # Exemplo: Sua lógica para gerar pdf_buffer e df_para_excel
            # Substitua essa parte pelo seu código real para gerar os arquivos

            # Criar PDF e Excel dummy para exemplo
            if mostrar_entradas:
                pdf_buffer = gerar_pdf_contratos(df_filtrado, selecionados_entrada, tipo_prazo='entrada')
            else:
                pdf_buffer = gerar_pdf_contratos(df_filtrado, faixas_selecionadas, tipo_prazo='vencimento')
            colunas_exportar = [
                'REGIÕES', 'ESTADO', 'UNIDADE', 'OBJETO', 'MODALIDADE DE LICITAÇÃO',
                'CONTRATADA', 'CNPJ/CPF','VALOR ATUAL MENSAL','VIGÊNCIA','DIAS_PARA_VENCER'
            ]
            df_filtrado_excel = df_filtrado.copy()
            if mostrar_entradas:
                df_filtrado_excel = df_filtrado_excel[df_filtrado_excel['DIAS_DESDE_ENTRADA'] >= 0]
            else:
                df_filtrado_excel = df_filtrado_excel[df_filtrado_excel['DIAS_PARA_VENCER'] >= 0]
                if 'Tudo' in faixas_selecionadas or not faixas_selecionadas:
                    df_filtrado_excel = df_filtrado_excel[df_filtrado_excel['DIAS_PARA_VENCER'] <= 210]

            df_para_excel = df_filtrado_excel[[col for col in colunas_exportar if col in df_filtrado_excel.columns]]

            # Convertendo em base64
            pdf_bytes = pdf_buffer.getvalue() if pdf_buffer else None
            excel_bytes = None
            if not df_para_excel.empty:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df_para_excel.to_excel(writer, index=False, sheet_name="Contratos")
                excel_buffer.seek(0)
                excel_bytes = excel_buffer.getvalue()

            pdf_b64 = base64.b64encode(pdf_bytes).decode() if pdf_bytes else None
            excel_b64 = base64.b64encode(excel_bytes).decode() if excel_bytes else None

            icon_pdf = '''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                <path d="M14 2H6a2 2 0 0 0-2 2v16c0 1.1.9 2 2 2h12a2 2 0 0 0 2-2V8zm4 16H6V4h7v5h5z"/>
            </svg>'''
            icon_excel = '''
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2
                14h-2l-2-3-2 3H9l2.5-3.5L9 10h2l2 2.5L15 10h2l-2.5 3.5L17 17z"/>
            </svg>'''

            st.markdown(f'''
            <div class="buttons-container">
                <a href="data:application/pdf;base64,{pdf_b64}" download="relatorio_contratos.pdf" class="download-btn">{icon_pdf} Baixar PDF</a>
                <a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_b64}" download="relatorio.xlsx" class="download-btn">{icon_excel} Baixar Excel</a>
            </div>
            ''', unsafe_allow_html=True)

        

    mostrar_todos_cards(df_filtrado, mostrar_entradas, selecionados_entrada, faixas_selecionadas)



#========================
#
#ABA QUE MOSTRA A LISTA DOS CONTRATOS
#
#========================

# --- Aba 2: Detalhamento dos Contratos ---
with aba3:
    st.subheader("📋 Lista de Contratos")
    # Utilitários
    def hoje_formatado():
        return date.today().strftime("%Y-%m-%d")

    def formatar_valor(valor):
        if pd.isna(valor):
            return ''
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def formatar_data(data):
        if pd.isna(data):
            return 'INDETERMINADA'
        return data.strftime('%d/%m/%Y')

    def formatar_colunas_dataframe(df):
        df = df.copy()
        df['DIAS_PARA_VENCER'] = df['DIAS_PARA_VENCER'].apply(lambda x: '-' if pd.isna(x) else int(x))

        for col in df.columns:
            if col == 'VIGÊNCIA':
                df[col] = df[col].apply(formatar_data)
            elif 'VALOR' in col.upper():
                df[col] = df[col].apply(formatar_valor)
            elif df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].dt.strftime('%d/%m/%Y')
        return df

    # PDF
    def formatar_cabecalho_pdf(coluna):
        return coluna.replace("_", " ").title()

    def gerar_pdf_contratos(df, colunas):
        buffer = BytesIO()
        pdf = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)

        styles = getSampleStyleSheet()
        style_title = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=14, spaceAfter=14)
        style_header = ParagraphStyle('Header', fontSize=8, textColor=colors.white, fontName='Helvetica-Bold')
        style_cell = ParagraphStyle('Cell', fontSize=8, leading=10)

        elementos = []

        for regiao in sorted(df['REGIÕES'].dropna().unique()):
            df_regiao = df[df['REGIÕES'] == regiao][colunas]
            if df_regiao.empty:
                continue

            elementos += [
                Paragraph(f"Lista de Contratos - {regiao}", style_title),
                Spacer(1, 10)
            ]

            dados_pdf = [[Paragraph(formatar_cabecalho_pdf(col), style_header) for col in colunas]]

            for i, (_, row) in enumerate(df_regiao.iterrows(), start=1):
                linha_pdf = [Paragraph(str(row[col]), style_cell) for col in colunas]
                dados_pdf.append(linha_pdf)

            tabela = Table(dados_pdf, repeatRows=1)
            estilo_tabela = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ])

            for idx in range(1, len(dados_pdf)):
                if idx % 2 == 0:
                    estilo_tabela.add('BACKGROUND', (0, idx), (-1, idx), colors.whitesmoke)

            tabela.setStyle(estilo_tabela)
            elementos += [tabela, PageBreak()]

        if not elementos:
            return None

        pdf.build(elementos)
        buffer.seek(0)
        return buffer

    def exportar_para_excel(df, colunas):
        output = BytesIO()
        df[colunas].to_excel(output, index=False)
        output.seek(0)
        return output
    # Streamlit App
    #st.header("📋 Exportar Contratos")
    with st.expander("Exportar Contratos",icon='📥'):

        df_formatado = formatar_colunas_dataframe(df_ativos)

                # Base conforme o modo escolhido
        # 2. Selecionar colunas com base no DataFrame carregado
        colunas_permitidas = [
            'CONTRATO', 'PROCESSO', 'REGIÕES', 'ESTADO', 'UNIDADE', 'OBJETO', 
            'MODALIDADE DE LICITAÇÃO', 'CONTRATADA', 'CNPJ/CPF', 'OBSERVAÇÕES', 
            'VALOR ATUAL MENSAL', 'VALOR ANUAL ATUAL', 'VALOR GLOBAL', 'VIGÊNCIA', 
            'DIAS_PARA_VENCER', # se quiser mantê-la, com tratamento especial
            # outras colunas específicas que você deseja permitir...
        ]
        colunas_disponiveis = [col for col in df_formatado.columns if col in colunas_permitidas]
              
        colunas_selecionadas = st.multiselect(
            "Selecione as colunas que deseja exportar:",
            options=colunas_disponiveis,
            default=[col for col in colunas_disponiveis if col in ['CONTRATO', 'UNIDADE', 'OBJETO', 'VIGÊNCIA', 'VALOR ANUAL ATUAL', 'REGIÕES']]
        )
        mostrar_tabela = st.toggle("👁️ Pré Visualizar", value=False) 
        if mostrar_tabela:
            if colunas_selecionadas:
                st.markdown("### 📋 Tabela de Contratos Vigentes")
                st.data_editor(df_formatado[colunas_selecionadas], use_container_width=True, disabled=True)
        # Gerar arquivos uma única vez
        pdf_buffer = gerar_pdf_contratos(df_formatado, colunas_selecionadas)
        excel_buffer = exportar_para_excel(df_formatado, colunas_selecionadas)

        # Encode base64
        pdf_b64 = base64.b64encode(pdf_buffer.getvalue()).decode() if pdf_buffer else None
        excel_b64 = base64.b64encode(excel_buffer.getvalue()).decode() if excel_buffer else None

        # Ícones SVG
        icon_excel = '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2
        14h-2l-2-3-2 3H9l2.5-3.5L9 10h2l2 2.5L15 10h2l-2.5 3.5L17 17z"/>
        </svg>'''

        icon_pdf = '''
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="M14 2H6a2 2 0 0 0-2 2v16c0 1.1.9 2 2 2h12a2 2 0 0 0 2-2V8zm4 16H6V4h7v5h5z"/>
        </svg>'''

        # CSS customizado
        st.markdown("""
            <style>
                .buttons-container {
                    display: flex;
                    justify-content: flex-end;
                    gap: 6px;
                    margin-top: 10px;
                    margin-bottom: 12px;
                    flex-wrap: wrap;
                }
                .download-btn {
                    background-color: #f5f7fa;
                    color: #555 !important;
                    border: 1.5px solid #ccc;
                    border-radius: 8px;
                    padding: 8px 10px;
                    font-weight: 500;
                    font-size: 14px;
                    cursor: pointer;
                    transition: all 0.25s ease;
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    text-decoration: none;
                }
                .download-btn:hover {
                    background-color: #e1e7ed;
                    border-color: #a9b7c6;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
                    color: #000 !important;
                    transform: translateY(-1px);
                }
                .download-btn svg {
                    width: 18px;
                    height: 18px;
                }
            </style>
        """, unsafe_allow_html=True)

        # Renderizar os botões com base nos arquivos disponíveis
        st.markdown(f"""
            <div class="buttons-container">
                {f'<a href="data:application/pdf;base64,{pdf_b64}" download="contratos.pdf" class="download-btn">{icon_pdf} Baixar PDF</a>' if pdf_b64 else ''}
                {f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_b64}" download="contratos.xlsx" class="download-btn">{icon_excel} Baixar Excel</a>' if excel_b64 else ''}
            </div>
        """, unsafe_allow_html=True)

        if not pdf_b64 and not excel_b64:
            st.warning("Nenhum arquivo gerado para download.")

   

    


    # Agrupar por região
    regioes = df_formatado['REGIÕES'].dropna().unique()

    for regiao in sorted(regioes):
        contratos_regiao = df_formatado[df_formatado['REGIÕES'] == regiao]
        st.markdown(f"#### 🌎 Região: {regiao}")

        linhas = len(contratos_regiao)
        altura_linha = 95
        altura_total = min(linhas * altura_linha, 400)

        with st.container(height=altura_total, border=False):
            # CSS atualizado
            st.markdown("""
                <style>
                    .contract-scroll-container {
                        overflow-x: auto;
                        width: 100%;
                    }
                    .contract-header, .contract-row {
                        display: flex;
                        flex-wrap: nowrap;
                        min-width: 900px;
                        width: fit-content;
                    }
                    .contract-header {
                        padding: 10px;
                        background-color: #f0f2f6;
                        border-top-left-radius: 8px;
                        border-top-right-radius: 8px;
                        border: 1px solid #ddd;
                        font-weight: bold;
                        font-size: 13px;
                        color: #333;
                    }
                    .contract-row {
                        padding: 10px;
                        font-size: 14px;
                        color: #333;
                        border-bottom: 1px solid #eee;
                    }
                    .contract-cell {
                        flex: 0 0 150px;
                        min-width: 150px;
                        padding: 8px;
                        box-sizing: border-box;
                    }

                    /* Coluna específica de Objetos (4ª coluna) */
                    .contract-header > div:nth-child(4),
                    .contract-row > div:nth-child(4) {
                        flex: 0 0 320px;
                        min-width: 320px;
                        max-width: 450px;
                        white-space: normal;
                        word-wrap: break-word;
                    }
                    .contract-cell ul {
                        padding-left: 20px;
                        margin: 0;
                    }
                    .contract-cell li {
                        list-style-type: disc;
                        color: #555;
                    }
                </style>
            """, unsafe_allow_html=True)

            # container vertical + horizontal scroll
            container_style = """
                overflow-y: auto; 
                border: 1px solid #ddd; 
                border-radius: 8px; 
                padding: 0;
                background: #fafafa;
            """
            st.markdown(f"<div style='{container_style}'>", unsafe_allow_html=True)
            st.markdown('<div class="contract-scroll-container">', unsafe_allow_html=True)

            # cabeçalho
            st.markdown("""
                <div class="contract-header">
                    <div class="contract-cell">📁 Contrato</div>
                    <div class="contract-cell">🔍 Processo</div>
                    <div class="contract-cell">🏢 Unidade(s)</div>
                    <div class="contract-cell">📌 Objetos</div>
                    <div class="contract-cell">📅 Vigência</div>
                    <div class="contract-cell">💰 Valor Anual</div>
                </div>
            """, unsafe_allow_html=True)

            # linhas
            for _, row in contratos_regiao.iterrows():
                contrato = str(row['CONTRATO'])
                processo = str(row['PROCESSO'])
                unidades = str(row['UNIDADE']).split("/")
                objetos = str(row['OBJETO']).split("/")
                vigencia = row['VIGÊNCIA']
                valor = row['VALOR ANUAL ATUAL']

                objetos_html = "<ul>" + "".join(
                    f"<li>{objeto.strip()}</li>" for objeto in objetos) + "</ul>"
                unidades_html = "<ul>" + "".join(
                    f"<li>{unidade.strip()}</li>" for unidade in unidades) + "</ul>"

                st.markdown(f"""
                    <div class="contract-row">
                        <div class="contract-cell">{contrato}</div>
                        <div class="contract-cell">{processo}</div>
                        <div class="contract-cell">{unidades_html}</div>
                        <div class="contract-cell">{objetos_html}</div>
                        <div class="contract-cell">{vigencia}</div>
                        <div class="contract-cell">{valor}</div>
                    </div>
                """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)  # fecha contract-scroll-container
            st.markdown("</div>", unsafe_allow_html=True)  # fecha container vertical



ano_atual = datetime.now().year
versao = "v1.0"  # altere aqui quando atualizar

st.markdown(
    f"""
    <style>
        .rodape {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #f9f9f9;
            color: #6c757d;
            border-top: 1px solid #e5e5e5;
            text-align: center;
            padding: 6px 10px;
            font-size: 0.75rem;
            font-family: 'Segoe UI', sans-serif;
            z-index: 999;
        }}

        @media (max-width: 768px) {{
            .rodape {{
                font-size: 0.7rem;
                padding: 4px;
            }}
        }}
    </style>

    <div class="rodape">
        Desenvolvido por <strong> Eduardo Júnior </strong> | Gestão de Contratos &nbsp;•&nbsp; {ano_atual} &nbsp;•&nbsp; Versão {versao}
    </div>
    """,
    unsafe_allow_html=True
)