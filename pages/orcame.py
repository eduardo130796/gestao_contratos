import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
from io import BytesIO
import plotly.express as px
import math
import plotly.graph_objects as go
import re
import locale
import streamlit.components.v1 as components

#locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
# 3. Dicionário de nomes bonitos (para exibição/exportação)
NOMES_BONITOS = {
    "contrato": "contrato",
    "valor_anual_proporcional": "Valor Anual Proporcional",
    "valor_pago": "Valor Pago",
    "unidade_gestora": "Unidade Gestora",
    "mes": "Mês",
    "valor_empenhado": "Valor Empenhado",
    "valor_a_anular": "Valor a Anular",
    "objeto": "Objeto",
    "valor_mensal":"Valor Mensal",
    "valor_anual":"Valor Anual"
    # Adicione conforme sua planilha
}

# 4. Reverter nomes para visualização bonita
def aplicar_nomes_bonitos(df: pd.DataFrame, nomes_map: dict = NOMES_BONITOS) -> pd.DataFrame:
    return df.rename(columns=nomes_map)

def normalizar_colunas(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.replace(" ", "_")
    )
    return df
# Funções do cálculo
def calcular_proporcional(data_inicio, data_fim, valor_mensal):
    total = 0
    current = pd.Timestamp(data_inicio.year, data_inicio.month, 1)
    while current <= data_fim:
        _, dias_mes = calendar.monthrange(current.year, current.month)
        inicio_mes = current
        fim_mes = current.replace(day=dias_mes)

        if data_inicio > inicio_mes:
            inicio_mes = data_inicio
        if data_fim < fim_mes:
            fim_mes = data_fim

        dias_no_mes = (fim_mes - inicio_mes).days + 1
        if inicio_mes.day == 1 and fim_mes.day == dias_mes:
            valor_mes = valor_mensal
        else:
            valor_mes = (valor_mensal / dias_mes) * dias_no_mes

        total += valor_mes
        current += pd.DateOffset(months=1)
        current = current.replace(day=1)

    return round(total, 2)

def calcular_valores(df_aux, ano_referencia):
    fim_exercicio = datetime(ano_referencia, 12, 31)
    inicio_exercicio = datetime(ano_referencia, 1, 1)
    resultados = []

    df_aux["data_inicio"] = pd.to_datetime(df_aux["data_inicio"], dayfirst=True, errors="coerce")
    contratos = df_aux[["contrato", "unidade", "objeto", "tipo_de_gasto"]].drop_duplicates()

    for _, linha in contratos.iterrows():
        contrato = linha["contrato"]
        unidade = linha["unidade"]
        objeto = linha["objeto"]
        tipo_gasto = linha["tipo_de_gasto"]

        grupo = df_aux[
            (df_aux["contrato"] == contrato) &
            (df_aux["unidade"] == unidade) &
            (df_aux["objeto"] == objeto) &
            (df_aux["tipo_de_gasto"] == tipo_gasto)
        ].copy()
        grupo = grupo.sort_values(by="data_inicio").reset_index(drop=True)

        valor_anual_total = 0
        valor_mensal_ultimo = None
        tipo_alteracao_ultimo = None
        data_inicio_ultimo = None

        grupo_anteriores = grupo[grupo["data_inicio"] < inicio_exercicio]
        grupo_posteriores = grupo[grupo["data_inicio"] >= inicio_exercicio]

        # Caso haja valores anteriores ao ano de referência, considerar continuidade
        if not grupo_anteriores.empty:
            ultima_linha_antes = grupo_anteriores.sort_values(by="data_inicio").iloc[-1]
            data_inicio = inicio_exercicio
            data_fim = fim_exercicio
            valor_mensal = ultima_linha_antes["valor_mensal"]
            tipo = str(ultima_linha_antes["tipo_de_alteracao"]).lower()

            if not grupo_posteriores.empty:
                proxima_data = grupo_posteriores.iloc[0]["data_inicio"]
                proximo_tipo = str(grupo_posteriores.iloc[0]["tipo_de_alteracao"]).lower()
                if proximo_tipo == "reajuste":
                    data_fim = datetime(proxima_data.year, proxima_data.month, 1) - timedelta(days=1)
                else:
                    data_fim = proxima_data - timedelta(days=1)

            valor = calcular_proporcional(data_inicio, data_fim, valor_mensal)
            valor_anual_total += valor

            # 👉 Atualiza o valor mensal vigente e dados da última alteração (mesmo que não seja em 2025)
            valor_mensal_ultimo = valor_mensal
            tipo_alteracao_ultimo = ultima_linha_antes["tipo_de_alteracao"]
            data_inicio_ultimo = ultima_linha_antes["data_inicio"]

        # Processa alterações dentro do ano normalmente
        for i, row in grupo_posteriores.iterrows():
            data_inicio = row["data_inicio"]
            valor_mensal = row["valor_mensal"]
            tipo = str(row["tipo_de_alteracao"]).lower()

            if tipo == "rescisão":
                data_fim = data_inicio
            elif i + 1 < len(grupo_posteriores):
                proxima_data = grupo_posteriores.loc[i + 1, "data_inicio"]
                proximo_tipo = str(grupo_posteriores.loc[i + 1, "tipo_de_alteracao"]).lower()
                if proximo_tipo == "reajuste":
                    data_fim = datetime(proxima_data.year, proxima_data.month, 1) - timedelta(days=1)
                else:
                    data_fim = proxima_data - timedelta(days=1)
            else:
                data_fim = fim_exercicio

            if tipo == "reajuste":
                data_inicio = datetime(data_inicio.year, data_inicio.month, 1)

            inicio_calc = max(data_inicio, inicio_exercicio)
            fim_calc = min(data_fim, fim_exercicio)

            if inicio_calc > fim_calc:
                continue

            valor = calcular_proporcional(inicio_calc, fim_calc, valor_mensal)
            valor_anual_total += valor

            valor_mensal_ultimo = valor_mensal
            tipo_alteracao_ultimo = row["tipo_de_alteracao"]
            data_inicio_ultimo = row["data_inicio"]

        # ✅ Se houve qualquer valor válido (anterior ou durante 2025), registra no resultado
        if valor_mensal_ultimo is not None:
            resultados.append({
                "contrato": contrato,
                "unidade": unidade,
                "objeto": objeto,
                "tipo_de_gasto": tipo_gasto,
                "valor_mensal": valor_mensal_ultimo,
                "valor_anual_proporcional": round(valor_anual_total, 2),
                "tipo_de_alteracao": tipo_alteracao_ultimo,
                "data_inicio": data_inicio_ultimo
            })

    return pd.DataFrame(resultados)

def calcular_status(df_aux, ano_referencia):
    status_resultados = []
    grupos = df_aux.groupby(["contrato", "unidade", "objeto"])

    # Regex para efetivados: repactuação, repactuado, reajuste, reajustado, com ano opcional
    pattern_efetivado = re.compile(r"^(repactua[cç]ão|repactuado|reajuste|reajustado)( \d{4})?$", re.IGNORECASE)
    # Regex para solicitados: solicitado repactuação, repactuado, reajuste, reajustado, com ano opcional
    pattern_solicitado = re.compile(r"^solicitado (repactua[cç]ão|repactuado|reajuste|reajustado)( \d{4})?$", re.IGNORECASE)

    for (contrato, unidade, objeto), grupo in grupos:
        grupo = grupo.copy()
        grupo["tipo_de_alteracao"] = grupo["tipo_de_alteracao"].fillna("").str.lower()
        grupo = grupo.sort_values("data_inicio", ascending=False)

        # Filtra efetivados no ano de referência
        efetivado = grupo[
            grupo["tipo_de_alteracao"].apply(lambda x: bool(pattern_efetivado.match(x))) &
            (grupo["data_inicio"].dt.year == ano_referencia)
        ]

        # Pega último efetivado (independente do ano)
        ult_efetivado = grupo[
            grupo["tipo_de_alteracao"].apply(lambda x: bool(pattern_efetivado.match(x)))
        ]
        data_ult_efetivado = ult_efetivado.iloc[0]["data_inicio"] if not ult_efetivado.empty else None

        # Filtra solicitados no ano de referência
        solicitado = grupo[
            grupo["tipo_de_alteracao"].apply(lambda x: bool(pattern_solicitado.match(x))) &
            (grupo["data_da_ocorrencia"].dt.year == ano_referencia)
        ]

        if not efetivado.empty:
            tipo = efetivado.iloc[0]["tipo_de_alteracao"]
            if re.search(r"repactua[cç]ão|repactuado", tipo, re.IGNORECASE):
                status = "Repactuado"
            else:
                status = "Reajustado"
            data = efetivado.iloc[0]["data_inicio"]
        elif not solicitado.empty:
            status = "Em análise"
            data = data_ult_efetivado
        else:
            status = "Não solicitado"
            data = data_ult_efetivado

        status_resultados.append({
            "contrato": contrato,
            "unidade": unidade,
            "objeto": objeto,
            "Status Atualização": status,
            "Data Última Repactuação/Reajuste": data
        })

    return pd.DataFrame(status_resultados)

def consolidar_dados(df_aux, df_empenhos,df_contratos, ano_referencia):
    df_resultado = calcular_valores(df_aux, ano_referencia)
    df_status = calcular_status(df_aux, ano_referencia)

    # Confere se existe a coluna tipo_de_gasto
    if "tipo_de_gasto" not in df_empenhos.columns:
        raise ValueError("Coluna 'tipo_de_gasto' não encontrada em df_empenhos")
    if "tipo_de_gasto" not in df_resultado.columns:
        raise ValueError("Coluna 'tipo_de_gasto' não encontrada em df_resultado")

    # Faz o merge linha a linha com base em todos os campos
    df_resumo = df_empenhos.merge(
        df_resultado,
        on=["contrato", "unidade", "objeto", "tipo_de_gasto"],
        how="left"
    )

    # Preenche nulos
    df_resumo["valor_anual_proporcional"] = df_resumo["valor_anual_proporcional"].fillna(0)
    df_resumo["valor_mensal"] = df_resumo["valor_mensal"].fillna(0)

    # Diferença
    df_resumo["Diferença (Empenhado - Proporcional)"] = (
        df_resumo["valor_empenhado"] - df_resumo["valor_anual_proporcional"]
    )

    # Junta status por contrato, unidade e objeto
    df_resumo = df_resumo.merge(
        df_status,
        on=["contrato", "unidade", "objeto"],
        how="left"
    )

    def normalizar_objeto(texto):
        texto = str(texto).lower().strip()
        
        if "portaria" in texto:
            return "agente de portaria"
        elif "vigilância" in texto or "vigilancia" in texto:
            return "vigilância"
        # Adicione outras regras se precisar
        return texto

    # Aplica a normalização em uma nova coluna, sem modificar a original
    df_resumo["objeto_normalizado"] = df_resumo["objeto"].apply(normalizar_objeto)
    df_contratos["objeto_normalizado"] = df_contratos["objeto"].apply(normalizar_objeto)

    # Faz o merge usando a coluna normalizada
    df_resumo = pd.merge(
        df_resumo,
        df_contratos,
        on=["contrato", "unidade", "objeto_normalizado"],
        how="left",
        suffixes=("", "_contrato")
    )

    # Novo cálculo: valor_anual (12 meses)
    df_resumo["valor_anual"] = df_resumo["valor_mensal"] * 12


    return df_resumo, df_resultado, df_status

def gerar_excel(df1, df2, df3):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Resumo Consolidado', index=False)
        df2.to_excel(writer, sheet_name='Detalhado', index=False)
        df3.to_excel(writer, sheet_name='Status', index=False)
    output.seek(0)
    return output


def formatar_moeda_para_exibicao(df, colunas):
    df_formatado = df.copy()
    for coluna in colunas:
        df_formatado[coluna] = df_formatado[coluna].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".") if pd.notnull(x) else x
        )
    return df_formatado


def formatar_valores_grafico(fig):
    fig.update_layout(
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.2f",
        hoverlabel=dict(
            font_size=12,
            font_family="Arial"
        )
    )
    return fig

#baixaar planilha que tem a evolução do empenho
def visualizar_empenhos_unicos():
    #teste local
    df_raw = pd.read_excel('relatorio evolucao mes a mes.xlsx', skiprows=2)  # CSV convertido
    #uso no git
    url_evol = "https://raw.githubusercontent.com/eduardo130796/gestao_contratos/main/relatorio%20evolucao%20mes%20a%20mes.xlsx"
    df_raw = pd.read_excel(url_evol)
    # Define meses e tipos
    meses = ["JAN/2025", "FEV/2025", "MAR/2025", "ABR/2025","MAI/2025","JUN/2025","JUL/2025"]
    tipos = [
        "DESPESAS EMPENHADAS (CONTROLE EMPENHO)",
        "DESPESAS EMPENHADAS A LIQUIDAR (CONTROLE EMP)",
        "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)"
    ]

    dados = []
    for _, row in df_raw.iterrows():
        nota = row.get("Unnamed: 0")
        favorecido = row.get("Unnamed: 2")  # Nome pode variar conforme a planilha

        for mes in meses:
            for i, tipo in enumerate(tipos):
                col_index = 3 + meses.index(mes) * 3 + i
                if col_index < len(row):
                    valor = row.iloc[col_index]

                    if isinstance(valor, str):
                        valor = valor.replace('.', '').replace(',', '.')
                    try:
                        valor = float(valor)
                    except:
                        valor = 0.0

                    dados.append({
                        "Nota de Empenho": nota,
                        "Favorecido": favorecido,
                        "Mês": mes,
                        "Tipo de Métrica": tipo,
                        "Valor (R$)": valor
                    })

    df = pd.DataFrame(dados)
    
    #df.to_parquet("dados_empenhos_evolucao.parquet", index=False)

    return df

df_evolucao_empenho=visualizar_empenhos_unicos()
# ========================================
# STREAMLIT APP
# ========================================
#st.set_page_config(layout="wide")

#st.title("📊 Cálculo Proporcional de contratos")
#
#ano = st.number_input("Ano de Referência", min_value=2000, max_value=2100, value=2025, step=1)
#
#col1, col2, col3 = st.columns(3)
#
#with col1:
#    file_aux = st.file_uploader("📄 Planilha Auxiliar de contratos", type=["xlsx"])
#with col2:
#    file_empenhos = st.file_uploader("📄 Planilha de Valores Empenhados", type=["xlsx"])
#with col3:
#    file_contratos = st.file_uploader("📄 Planilha de contratos", type=["xlsx"])
#if file_aux and file_empenhos and file_contratos:
#    # Carregando arquivos
#    # Carregando arquivos
#    df_aux = pd.read_excel(file_aux)
#    df_aux = normalizar_colunas(df_aux)
#    df_empenhos = pd.read_excel(file_empenhos)
#    df_empenhos = normalizar_colunas(df_empenhos)
#    df_contratos = pd.read_excel(file_contratos)
#    df_contratos = normalizar_colunas(df_contratos)


def carregar_dados(file_aux,file_empenhos,file_contratos,ano=2025):
    #uso local
    #df_aux = pd.read_excel(file_aux)
    #df_aux = normalizar_colunas(df_aux)
    #df_empenhos = pd.read_excel(file_empenhos)
    #df_empenhos = normalizar_colunas(df_empenhos)
    #df_contratos = pd.read_excel(file_contratos)
    #df_contratos = normalizar_colunas(df_contratos)

    #uso no git
    url_aux = "https://raw.githubusercontent.com/eduardo130796/gestao_contratos/main/planilha_auxiliar.xlsx"
    df_aux = pd.read_excel(url_aux)
    df_aux = normalizar_colunas(df_aux)
    url_empenho = "https://raw.githubusercontent.com/eduardo130796/gestao_contratos/main/planilha_base_notas.xlsx"
    df_empenhos = pd.read_excel(url_empenho)
    df_empenhos = normalizar_colunas(df_empenhos)
    url_contrato = "https://raw.githubusercontent.com/eduardo130796/gestao_contratos/main/RELATORIO%20DE%20CONTRATOS%20VIGENTES%202025%20(1).xlsx"
    df_contratos = pd.read_excel(url_contrato)
    df_contratos = normalizar_colunas(df_contratos)
    # Faz merge da coluna "tipo_de_gasto" no df_aux, se necessário

    if "tipo_de_gasto" not in df_aux.columns:
        df_aux = df_aux.merge(
            df_empenhos[["contrato", "unidade", "objeto", "tipo_de_gasto"]],
            on=["contrato", "unidade", "objeto"],
            how="left"
        )
    # Converte datas
    # 1. Expande as linhas "TODAS" normalmente, sem mexer no valor_mensal (se não tiver, busca histórico, etc)
    df_aux["data_inicio"] = pd.to_datetime(df_aux["data_inicio"], errors="coerce")

    linhas_expandir = df_aux[df_aux["unidade"].fillna("").str.upper() == "TODAS"].copy()
    novas_linhas = []

    for _, linha in linhas_expandir.iterrows():
        contrato = linha["contrato"]
        objeto = linha["objeto"]
        data_inicio = linha["data_inicio"]
        valor_preenchido = linha["valor_mensal"] if not pd.isna(linha["valor_mensal"]) else None

        unidades_existentes = df_aux[
            (df_aux["contrato"] == contrato) &
            (df_aux["objeto"] == objeto) &
            (df_aux["unidade"].str.upper() != "TODAS")
        ]["unidade"].unique()

        for unidade in unidades_existentes:
            nova_linha = linha.copy()
            nova_linha["unidade"] = unidade

            if pd.isna(valor_preenchido):
                historico = df_aux[
                    (df_aux["contrato"] == contrato) &
                    (df_aux["objeto"] == objeto) &
                    (df_aux["unidade"] == unidade) &
                    (df_aux["data_inicio"] < data_inicio)
                ].sort_values("data_inicio", ascending=False)

                valor_ultimo = historico.iloc[0]["valor_mensal"] if not historico.empty else None
            else:
                valor_ultimo = valor_preenchido

            nova_linha["valor_mensal"] = valor_ultimo
            novas_linhas.append(nova_linha)

    df_aux = df_aux[df_aux["unidade"].fillna("").str.upper() != "TODAS"]

    if novas_linhas:
        df_aux = pd.concat([df_aux, pd.DataFrame(novas_linhas)], ignore_index=True)


    tipos_de_gasto_sem_valor = ["IPTU", "SEGURO", "TAXAS", "ENCARGOS"]

    def ajustar_valor_por_tipo_gasto(row):
        # Se tipo_de_gasto está ausente, mantém valor original
        tipo_gasto_linha = str(row.get("tipo_de_gasto", "")).strip().upper()

        # Busca empenhos relacionados para saber se tem mais de um empenho (contrato, unidade e objeto)
        contrato = row["contrato"]
        unidade = row["unidade"]
        objeto = row["objeto"]

        empenhos_relacionados = df_empenhos[
            (df_empenhos["contrato"] == contrato) &
            (df_empenhos["unidade"] == unidade) &
            (df_empenhos["objeto"] == objeto)
        ]

        if len(empenhos_relacionados) <= 1:
            return row["valor_mensal"]

        if tipo_gasto_linha in tipos_de_gasto_sem_valor:
            return None  # ou 0 se preferir

        return row["valor_mensal"]

    df_aux["valor_mensal"] = df_aux.apply(ajustar_valor_por_tipo_gasto, axis=1)

    df_final, df_detalhado, df_status = consolidar_dados(df_aux, df_empenhos,df_contratos, ano)

        # Formatar data no formato brasileiro
    df_final["Data Última Repactuação/Reajuste"] = pd.to_datetime(df_final["Data Última Repactuação/Reajuste"], errors="coerce") \
        .dt.strftime("%d/%m/%Y")

    # Formatar valores monetários em reais
    colunas_valores = [
        "valor_mensal",
        "valor_anual_proporcional",
        "valor_empenhado",
        "valor_pago",
        "Diferença (Empenhado - Proporcional)"
    ]
    df_exibicao = formatar_moeda_para_exibicao(df_final, colunas_valores)
    df_exibicao = aplicar_nomes_bonitos(df_exibicao)

    return df_final, df_aux

       

    
    #st.dataframe(df_aux)
    #st.success("Planilhas carregadas com sucesso!")
#
    #df_final, df_detalhado, df_status = consolidar_dados(df_aux, df_empenhos,df_contratos, ano)
#
    #    # Formatar data no formato brasileiro
    #df_final["Data Última Repactuação/Reajuste"] = pd.to_datetime(df_final["Data Última Repactuação/Reajuste"], errors="coerce") \
    #    .dt.strftime("%d/%m/%Y")
#
    ## Formatar valores monetários em reais
    #colunas_valores = [
    #    "valor_mensal",
    #    "valor_anual_proporcional",
    #    "valor_empenhado",
    #    "valor_pago",
    #    "Diferença (Empenhado - Proporcional)"
    #]
#
    ##for coluna in colunas_valores:
    ##    df_final[coluna] = df_final[coluna].apply(lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
#
#
    #st.subheader("✅ Resumo Consolidado")
    #
    #df_exibicao = formatar_moeda_para_exibicao(df_final, colunas_valores)
    #df_exibicao = aplicar_nomes_bonitos(df_exibicao)
    #st.dataframe(df_exibicao, use_container_width=True)
#
    #st.subheader("🔍 Detalhamento por Alteração")
    #st.dataframe(df_detalhado, use_container_width=True)
#
    #st.subheader("📌 Status de Atualizações")
    #st.dataframe(df_status, use_container_width=True)
#
    #excel_bytes = gerar_excel(df_final, df_detalhado, df_status)
    #st.download_button(
    #    label="📥 Baixar Excel Consolidado",
    #    data=excel_bytes,
    #    file_name=f"relatorio_contratos_{ano}.xlsx",
    #    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    #)

   
file_aux='planilha_auxiliar.xlsx'
file_empenhos='planilha_base_notas.xlsx'
file_contratos='RELATORIO DE CONTRATOS VIGENTES 2025 (1).xlsx'
df_final, df_aux = carregar_dados(file_aux,file_empenhos,file_contratos)


 ###########################################################

#else:
#    st.warning("Por favor, envie as duas planilhas para começar.")

def formatar_real(valor):
    if pd.isna(valor): return ""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
#############################################################
#
# INÍCIO DO APP, AJUSTES
#
#############################################################

def calcular_execucao(df):
    # Calcular execução em relação ao valor_anual
    df['Execucao Percentual (Anual)'] = (df['valor_pago'] / df['valor_anual']) * 100
    
    # Calcular execução em relação ao valor_empenhado
    df['Execucao Percentual (Empenhado)'] = (df['valor_pago'] / df['valor_empenhado']) * 100
    
    # Calcular percentual faltante de empenho para alcançar o valor_anual
    df['Percentual Faltante de Empenho'] = ((df['valor_anual'] - df['valor_empenhado']) / df['valor_anual']) * 100
    
    # Garantir que o percentual faltante não seja negativo
    df['Percentual Faltante de Empenho'] = df['Percentual Faltante de Empenho'].apply(lambda x: max(x, 0))
    
    return df
# Adicionar CSS para personalizar o layout e o botão
st.markdown(
    """
    <style>
    /* Estilizando o cabeçalho */
    .title {
        font-size: 50px;
        font-weight: bold;
        color: #4A90E2;
        text-align: center;
        padding: 0px;
    }

    /* Estilizando o botão */
    .stButton button {
        background-color: #4CAF50;  /* Verde */
        color: white;
        font-size: 16px;
        border-radius: 5px;
        padding: 12px 24px;
        border: none;
        cursor: pointer;
        transition: background-color 0.3s ease;
    }
    .stButton button:hover {
        background-color: #45a049;  /* Cor mais escura ao passar o mouse */
    }

    /* Estilizando a info da última atualização */
    .stInfo {
        font-size: 14px;
        color: #555;
        text-align: center;
        padding: 0px 0;
        margin-bottom:50px
    }
    </style>
    """, unsafe_allow_html=True
)

# Cabeçalho com título e ícone
st.markdown('<div class="title">📊 Painel de Gestão Orçamentária</div>', unsafe_allow_html=True)


df_final["regioes"] = df_final["regioes"].str.strip().str.upper()
# Sidebar para filtros
st.sidebar.header("Filtros")
regioes = st.sidebar.multiselect("Selecione a Região", df_final["regioes"].unique())
objeto = st.sidebar.multiselect("Selecione o objeto", df_final["objeto"].unique())

df_local=df_final
# Aplicar filtros
if regioes:
    df_local = df_final[df_final["regioes"].isin(regioes)]
if objeto:
    df_local = df_final[df_final["objeto"].isin(objeto)]
# Selecione o contrato com uma opção inicial "Selecione um contrato"
contrato = st.sidebar.selectbox("Selecione um contrato", options=["Selecione um contrato"] + list(df_local["contrato"].unique()))

# Filtrar os dados apenas se um contrato for selecionado
if contrato != "Selecione um contrato":
    df_local = df_local[df_local["contrato"] == contrato]
    
############################################
#
#
# POR contrato
# 
#
#############################################


def calcular_valores_mes_a_mes_ac(df_aux, ano_referencia):
    fim_exercicio = datetime(ano_referencia, 12, 31)
    inicio_exercicio = datetime(ano_referencia, 1, 1)
    resultados = []

    df_aux["data_inicio"] = pd.to_datetime(df_aux["data_inicio"], dayfirst=True, errors="coerce")
    df_aux["valor_mensal"] = df_aux["valor_mensal"].replace("R$", "", regex=True).replace(",", ".", regex=True).astype(str).str.strip()
    df_aux["valor_mensal"] = pd.to_numeric(df_aux["valor_mensal"], errors="coerce")

    contratos = df_aux[["contrato", "unidade", "objeto", "tipo_de_gasto"]].drop_duplicates()

    for _, linha in contratos.iterrows():
        contrato = linha["contrato"]
        unidade = linha["unidade"]
        objeto = linha["objeto"]
        tipo_gasto = linha["tipo_de_gasto"]

        grupo = df_aux[
            (df_aux["contrato"] == contrato) &
            (df_aux["unidade"] == unidade) &
            (df_aux["objeto"] == objeto) &
            (df_aux["tipo_de_gasto"] == tipo_gasto)
        ].copy()
        grupo = grupo.sort_values(by="data_inicio").reset_index(drop=True)

        valores_por_mes = {mes: 0.0 for mes in range(1, 13)}
        valor_mensal_ultimo = None
        tipo_alteracao_ultimo = None
        data_inicio_ultimo = None

        grupo_anteriores = grupo[grupo["data_inicio"] < inicio_exercicio]
        grupo_posteriores = grupo[grupo["data_inicio"] >= inicio_exercicio]

        # --- Processa valor vigente anterior ao exercício ---
        if not grupo_anteriores.empty:
            ultima_linha_antes = grupo_anteriores.sort_values(by="data_inicio").iloc[-1]
            data_inicio = inicio_exercicio
            data_fim = fim_exercicio
            valor_mensal = ultima_linha_antes["valor_mensal"]

            if not grupo_posteriores.empty:
                proxima_data = grupo_posteriores.iloc[0]["data_inicio"]
                proximo_tipo = str(grupo_posteriores.iloc[0]["tipo_de_alteracao"]).lower() if pd.notna(grupo_posteriores.iloc[0]["tipo_de_alteracao"]) else ""
                if proximo_tipo == "reajuste":
                    data_fim = datetime(proxima_data.year, proxima_data.month, 1) - timedelta(days=1)
                else:
                    data_fim = proxima_data - timedelta(days=1)

            current = pd.Timestamp(data_inicio.year, data_inicio.month, 1)
            while current <= data_fim:
                _, dias_mes = calendar.monthrange(current.year, current.month)
                primeiro_dia_mes = current
                ultimo_dia_mes = current.replace(day=dias_mes)

                inicio_periodo = max(primeiro_dia_mes, data_inicio)
                fim_periodo = min(ultimo_dia_mes, data_fim)
                dias_validos = (fim_periodo - inicio_periodo).days + 1

                if dias_validos > 0:
                    valor_proporcional = (valor_mensal / dias_mes) * dias_validos
                    valores_por_mes[current.month] += valor_proporcional

                current += pd.DateOffset(months=1)
                current = current.replace(day=1)

            valor_mensal_ultimo = valor_mensal
            tipo_alteracao_ultimo = ultima_linha_antes["tipo_de_alteracao"]
            data_inicio_ultimo = ultima_linha_antes["data_inicio"]

        # --- Processa alterações dentro do exercício normalmente ---
        for i, row in grupo_posteriores.iterrows():
            data_inicio = row["data_inicio"]
            valor_mensal = row["valor_mensal"]
            tipo = str(row["tipo_de_alteracao"]).lower() if pd.notna(row["tipo_de_alteracao"]) else ""

            if tipo == "rescisão":
                if data_inicio_ultimo and valor_mensal_ultimo:
                    inicio_calc = max(data_inicio_ultimo, inicio_exercicio)
                    fim_calc = min(data_inicio, fim_exercicio)

                    current = pd.Timestamp(inicio_calc.year, inicio_calc.month, 1)
                    while current <= fim_calc:
                        _, dias_mes = calendar.monthrange(current.year, current.month)
                        primeiro_dia_mes = current
                        ultimo_dia_mes = current.replace(day=dias_mes)

                        inicio_periodo = max(primeiro_dia_mes, inicio_calc)
                        fim_periodo = min(ultimo_dia_mes, fim_calc)
                        dias_validos = (fim_periodo - inicio_periodo).days + 1

                        if dias_validos > 0:
                            valor_proporcional = (valor_mensal_ultimo / dias_mes) * dias_validos
                            valores_por_mes[current.month] += valor_proporcional

                        current += pd.DateOffset(months=1)
                        current = current.replace(day=1)
                continue  # pula o restante da linha "rescisão"

            if tipo == "reajuste" and data_inicio.day != 1:
                data_inicio = datetime(data_inicio.year, data_inicio.month, 1) + pd.DateOffset(months=1)
                data_inicio = data_inicio.replace(day=1)

            if i + 1 < len(grupo_posteriores):
                proxima_data = grupo_posteriores.loc[i + 1, "data_inicio"]
                proximo_tipo = str(grupo_posteriores.loc[i + 1, "tipo_de_alteracao"]).lower() if pd.notna(grupo_posteriores.loc[i + 1, "tipo_de_alteracao"]) else ""
                if proximo_tipo == "reajuste":
                    data_fim = datetime(proxima_data.year, proxima_data.month, 1) - timedelta(days=1)
                else:
                    data_fim = proxima_data - timedelta(days=1)
            else:
                data_fim = fim_exercicio

            inicio_calc = max(data_inicio, inicio_exercicio)
            fim_calc = min(data_fim, fim_exercicio)

            if inicio_calc > fim_calc:
                continue

            current = pd.Timestamp(inicio_calc.year, inicio_calc.month, 1)
            while current <= fim_calc:
                _, dias_mes = calendar.monthrange(current.year, current.month)
                primeiro_dia_mes = current
                ultimo_dia_mes = current.replace(day=dias_mes)

                inicio_periodo = max(primeiro_dia_mes, inicio_calc)
                fim_periodo = min(ultimo_dia_mes, fim_calc)
                dias_validos = (fim_periodo - inicio_periodo).days + 1

                if dias_validos > 0:
                    valor_proporcional = (valor_mensal / dias_mes) * dias_validos
                    valores_por_mes[current.month] += valor_proporcional

                current += pd.DateOffset(months=1)
                current = current.replace(day=1)

            valor_mensal_ultimo = valor_mensal
            tipo_alteracao_ultimo = row["tipo_de_alteracao"]
            data_inicio_ultimo = data_inicio

        # --- Finaliza linha de resultado ---
        if valor_mensal_ultimo is not None:
            resultado = {
                "contrato": contrato,
                "unidade": unidade,
                "objeto": objeto,
                "tipo_de_gasto": tipo_gasto,
                "valor_mensal": valor_mensal_ultimo,
                "tipo_de_alteracao": tipo_alteracao_ultimo,
                "data_inicio": data_inicio_ultimo,
            }
            nomes_meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
            for idx, nome_mes in enumerate(nomes_meses, start=1):
                resultado[nome_mes] = round(valores_por_mes[idx], 2)
            resultados.append(resultado)
    return pd.DataFrame(resultados)


if contrato != "Selecione um contrato":
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Valor Anual", formatar_real(df_local['valor_anual'].sum()))
        col2.metric("💰 Valor Empenhado", formatar_real(df_local['valor_empenhado'].sum()))
        col3.metric("💵 Valor Pago", formatar_real(df_local['valor_pago'].sum()))
        with col4:
            # Cálculo da diferença entre o valor_anual e o valor_empenhado
            df_local['Diferença'] = df_local['valor_empenhado'] - df_local['valor_anual']

            # Calcular o total de valores a serem anulados ou reforçados
            valor_anular = df_local[df_local['Diferença'] > 0]['Diferença'].sum()
            valor_reforcar = df_local[df_local['Diferença'] < 0]['Diferença'].sum()

            # Mostrar os valores de reforço ou anulação, com as cores adequadas
            if valor_reforcar < 0:
                st.metric("⚠️ Ação Necessária - Reforçar",
                        formatar_real(abs(valor_reforcar)), "Reforçar",
                        delta_color="inverse")  # 'inverse' para destacar como algo negativo (precisa reforçar)
            else:
                st.metric("✅ Ação Necessária - Anular",
                        formatar_real(abs(valor_anular)), "Anular",
                        delta_color="normal")  # 'normal' para algo positivo (pode anular)
                

        df_contrato = df_local[df_local['contrato'] == contrato]

        # Calcular a execução e os percentuais para o contrato selecionado
        df_contrato = calcular_execucao(df_contrato)
        def dias_corridos(data_inicio, data_fim=None):
            if not pd.isna(data_inicio):
                fim = data_fim if data_fim else datetime.today()
                return (fim - data_inicio).days
            return None

        #col1, col2 = st.columns([1, 1])
        def formatar_data(data):
            if pd.isna(data):
                return '-'
            return data.strftime('%d/%m/%Y')
        
        
    
        st.markdown(f"### 📄 contrato: {contrato}")
        st.markdown("<br>", unsafe_allow_html=True)
        

        contrato_info = df_contrato

        with st.container():
            col1, col2 = st.columns(2)

            with col1:
                valores_totais = contrato_info[["valor_anual", "valor_empenhado", "valor_pago"]].sum()

                fig_valores = px.bar(
                    x=["Valor Anual", "Valor Empenhado", "Valor Pago"],
                    y=[valores_totais["valor_anual"], valores_totais["valor_empenhado"], valores_totais["valor_pago"]],
                    labels={"x": "Tipo de Valor", "y": "Valor (R$)"},
                    color=["valor_anual", "valor_empenhado", "valor_pago"],
                    color_discrete_map={
                        "valor_anual":"#ff7f0e",
                        "valor_empenhado": "#1f77b4",
                        "valor_pago": "#2ca02c",
                    },
                    text=[
                        formatar_real(valores_totais["valor_anual"]),
                        formatar_real(valores_totais["valor_empenhado"]),
                        formatar_real(valores_totais["valor_pago"])
                    ],
                    title="📊 Comparativo Anual, Empenhado e Pago"
                )
                fig_valores.update_layout(
                    height=400,
                    showlegend=False,
                    bargap=0.25,
                    plot_bgcolor="#ffffff",
                    paper_bgcolor="#ffffff",
                    margin=dict(t=50, b=30),
                    xaxis_title="Tipo de Valor",
                    yaxis_title="Valor (R$)"
                )
                st.plotly_chart(fig_valores, use_container_width=True)

            with col2:
                # Lista dos meses e seus índices para facilitar comparações
                # Mapeamento dos meses e preparação inicial
                meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
                mapa_mes_idx = {m: i for i, m in enumerate(meses)}

                df_melt = df_local.melt(
                    id_vars=["contrato", "regioes"],
                    value_vars=meses,
                    var_name="Mês",
                    value_name="valor_pago Mensal"
                )

                df_pagamento = df_melt.groupby(["contrato", "Mês"], as_index=False)["valor_pago Mensal"].sum()
                df_pagamento["Mês"] = pd.Categorical(df_pagamento["Mês"], categories=meses, ordered=True)
                df_pagamento["mes_idx"] = df_pagamento["Mês"].map(mapa_mes_idx)

                # Data de início do contrato
                df_inicio = df_aux.sort_values("data_inicio").drop_duplicates("contrato", keep="first")
                df_inicio["mes_inicio"] = df_inicio["data_inicio"].dt.month - 1
                df_pagamento = df_pagamento.merge(df_inicio[["contrato", "mes_inicio"]], on="contrato", how="left")

                # Descobre o primeiro mês com pagamento real
                df_primeiro_pago = (
                    df_pagamento[df_pagamento["valor_pago Mensal"] > 0]
                    .groupby("contrato")["mes_idx"].min()
                    .reset_index()
                    .rename(columns={"mes_idx": "primeiro_mes_pago"})
                )
                df_pagamento = df_pagamento.merge(df_primeiro_pago, on="contrato", how="left")

                # Aplica a lógica refinada:
                # - "Pago" se > 0
                # - "Projetado" se >= mes_inicio, >= primeiro_mes_pago, e valor == 0
                # - "Ignorar" nos outros casos
                df_pagamento["tipo"] = df_pagamento.apply(
                    lambda row: "Pago" if row["valor_pago Mensal"] > 0 else
                    "Projetado" if (
                        (row["mes_idx"] >= row["mes_inicio"]) and
                        ((pd.isna(row["primeiro_mes_pago"])) or row["mes_idx"] >= row["primeiro_mes_pago"])
                    ) else "Ignorar",
                    axis=1
                )
                

                # Calcula média dos meses pagos
                media_pago = df_pagamento[df_pagamento["tipo"] == "Pago"]["valor_pago Mensal"].mean()
                df_pagamento["valor_extra"] = 0.0

                # Ajuste do valor faltante
                for contrato, grupo in df_pagamento.groupby("contrato"):
                    mes_inicio = grupo["mes_inicio"].iloc[0]
                    ultimo_pago = grupo[grupo["tipo"] == "Pago"]["mes_idx"].max() if not grupo[grupo["tipo"] == "Pago"].empty else mes_inicio - 1

                    # Meses dentro do período inicial até último mês pago que não foram pagos
                    nao_pagos_anteriores = grupo[
                        (grupo["mes_idx"] >= mes_inicio) &
                        (grupo["mes_idx"] <= ultimo_pago) &
                        (grupo["valor_pago Mensal"] == 0)
                    ]
                    total_faltante = len(nao_pagos_anteriores) * media_pago

                    # Primeiro mês futuro para colocar projeção com valor extra
                    futuros_proj = grupo[
                        (grupo["mes_idx"] > ultimo_pago) &
                        (grupo["tipo"] == "Projetado")
                    ].sort_values("mes_idx")

                    if not futuros_proj.empty:
                        idx_proj = futuros_proj.index[0]
                        df_pagamento.loc[idx_proj, "valor_extra"] += total_faltante

                df_pagamento = df_pagamento[df_pagamento["tipo"] != "Ignorar"].copy()
                # Valor a ser plotado: pago real ou projetado + acumulado
                df_pagamento["valor_plotado"] = df_pagamento.apply(
                    lambda row: row["valor_pago Mensal"] if row["tipo"] == "Pago"
                    else media_pago + row["valor_extra"],
                    axis=1
                )

                # Rótulo
                def formatar_real(valor):
                    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                df_pagamento["rótulo"] = df_pagamento["valor_plotado"].apply(formatar_real)

                # Plot
                fig_pagamento = px.bar(
                    df_pagamento,
                    x="Mês",
                    y="valor_plotado",
                    color="tipo",
                    category_orders={"Mês": meses},
                    labels={"Mês": "Mês", "valor_plotado": "Valor Pago (R$)"},
                    title="📆 Pagamentos Mensais por contrato",
                    color_discrete_map={
                        "Pago": "#2ca02c",
                        "Projetado": "#d3d3d3"
                    },
                    text="rótulo"
                )

                for trace in fig_pagamento.data:
                    if trace.name == "Pago":
                        trace.opacity = 1
                        trace.textfont.color = "white"
                    else:
                        trace.opacity = 0.6
                        trace.textfont.color = "black"
                    trace.textposition = "inside"
                    trace.text = [formatar_real(val) for val in trace.y]
                    trace.textfont.size = 12

                fig_pagamento.update_layout(
                    bargap=0.05,
                    bargroupgap=0,
                    height=400,
                    xaxis_title="Mês",
                    yaxis_title="Valor Pago (R$)",
                    plot_bgcolor="#ffffff",
                    paper_bgcolor="#ffffff",
                    margin=dict(t=50, b=30)
                )

                fig_pagamento.update_traces(width=0.6)
                st.plotly_chart(fig_pagamento, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"#### 📄 Detalhes:")
        for _, row in contrato_info.iterrows():
            with st.container():
                colC, colD = st.columns(2)
                with colC:
                    
                    df_filtro = df_aux[
                            (df_aux['contrato'] == row['contrato']) &
                            (df_aux['unidade'] == row['unidade']) &
                            (df_aux['objeto'] == row['objeto'])
                        ]

                    alertas_renderizados = False  # para verificar se algo será exibido
                    for _, aux_row in df_filtro.iterrows():
                        tipo_str = aux_row['tipo_de_alteracao']
                        data_inicio = aux_row['data_da_ocorrencia']

                        match_solicitacao = re.match(r"Solicitado (Repactuação|Reajuste) (\d{4})", tipo_str, re.IGNORECASE)
                        if match_solicitacao:
                            tipo, ano = match_solicitacao.groups()
                            chave = f"{tipo.title()} {ano}"

                            concedida = df_filtro[
                                df_filtro['tipo_de_alteracao'].str.fullmatch(chave, case=False, na=False)
                            ]

                            if not concedida.empty:
                                pass
                            else:
                                dias = dias_corridos(data_inicio)
                                st.markdown(
                                    f"""
                                    <div style="background-color: #fffbe6; padding: 10px; border-left: 6px solid orange; border-radius: 6px; margin-bottom: 10px;">
                                        🕐 <strong>{chave}</strong> em aberto há <strong>{dias} dias</strong><br>
                                        <small>Desde {formatar_data(data_inicio.date())}</small>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                                alertas_renderizados = True
                    colA, colB = st.columns(2)
                    with colA:
                        ultima_data = row['Data Última Repactuação/Reajuste']

                        # converte para datetime, forçando erros a virar NaT
                        ultima_data_dt = pd.to_datetime(ultima_data, errors='coerce')

                        if pd.notna(ultima_data_dt):
                            ultima_data_formatada = ultima_data_dt.strftime("%d/%m/%Y")
                        else:
                            ultima_data_formatada = ""
                        st.markdown(
                            f"""
                            <div style="background-color: #f0f2f6; padding: 10px 12px; border-radius: 10px; font-size: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.05);">
                                <p style="margin: 2px;"><strong>📍 Região:</strong> {row['regioes']}</p>
                                <p style="margin: 2px;"><strong>🏢 Unidade:</strong> {row['unidade']}</p>
                                <p style="margin: 2px;"><strong>📦 Objeto:</strong> {row['objeto']} ({row['tipo_de_gasto']})</p>
                                <p style="margin: 2px;"><strong>📑 Nota:</strong> {row['nota_de_empenho']}</p>
                                <p style="margin: 2px;"><strong>🔄 Última Repa/Reajus:</strong> {ultima_data_formatada}</p>
                                <p style="margin: 2px;"><strong>🔄 Status atual:</strong> {row['Status Atualização']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with colB:

                        
                        st.markdown(
                            f"""
                            <div style="background-color: #e7f8f2; padding: 10px 12px; border-radius: 10px; font-size: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.05);">
                                <div style="margin-bottom: 10px;">
                                    <p style="margin: 2px;"><strong>💸 Valor Mensal:</strong> {formatar_real(row['valor_mensal'])}</p>
                                    <p style="margin: 2px;"><strong>💰 Empenhado:</strong> {formatar_real(row['valor_empenhado'])}</p>
                                    <p style="margin: 2px;"><strong>✅ Pago:</strong> {formatar_real(row['valor_pago'])}</p>
                                </div>
                                <div style="border-top: 1px solid #cdeadd; margin-top: 8px; padding-top: 8px;">
                                    <p style="margin: 2px;"><strong>📊 Exec. Anual:</strong> {row['Execucao Percentual (Anual)']:.1f}%</p>
                                    <p style="margin: 2px;"><strong>📊 Exec. Empenho:</strong> {row['Execucao Percentual (Empenhado)']:.1f}%</p>
                                    <p style="margin: 2px;"><strong>📉 Faltante:</strong> {row['Percentual Faltante de Empenho']:.1f}%</p>
                                </div>
                            </div>
                            <br>
                            """,
                            unsafe_allow_html=True
                        )
                    
                with colD:   
                        
                        # Agregar os valores para o contrato selecionado
                    # Pega os valores diretamente do row
                    valores_totais = {
                        "Valor Anual": row["valor_anual"],
                        "Valor Empenhado": row["valor_empenhado"],
                        "Valor Pago": row["valor_pago"]
                    }

                    tipos = list(valores_totais.keys())
                    valores = list(valores_totais.values())
                    # Para mostrar "R$ 0,00" quando for zero
                    valores_para_texto = [v if v > 0 else 0.00 for v in valores]

                    fig_valores = px.bar(
                        x=tipos,
                        y=valores,
                        labels={"x": "Tipo de Valor", "y": "Valor (R$)"},
                        color=tipos,
                        color_discrete_map={
                            "Valor Anual": "#ff7f0e",
                            "Valor Empenhado": "#1f77b4",
                            "Valor Pago": "#2ca02c"
                        },
                        text=[formatar_real(v) for v in valores_para_texto]
                    )

                    for i, trace in enumerate(fig_valores.data):
                        new_textposition = []
                        for val in trace.y:
                            if val == 0:
                                new_textposition.append("outside")
                            else:
                                new_textposition.append("inside")
                        trace.textposition = new_textposition
                        # Ajusta cor para texto fora da barra:
                        trace.textfont.color = ["black" if pos=="outside" else "white" for pos in new_textposition]




                    fig_valores.update_layout(
                        height=250,
                        showlegend=False,
                        bargap=0.25,
                        plot_bgcolor="#ffffff",
                        paper_bgcolor="#ffffff",
                        margin=dict(t=30, b=30),
                        xaxis_title="",
                        yaxis_title="Valor (R$)"
                    )

                    st.plotly_chart(fig_valores, use_container_width=True, key=f"grafico_totais_{row['nota_de_empenho']}")
                
                with st.expander("📊 Ver gráfico mensal de pagamentos"):
                        df_valores_previstos = calcular_valores_mes_a_mes_ac(df_aux, ano_referencia=2025)

                        # Pega os valores previstos do objeto correspondente
                        linha_prevista = df_valores_previstos[
                            (df_valores_previstos["contrato"] == row["contrato"]) &
                            (df_valores_previstos["unidade"] == row["unidade"]) &
                            (df_valores_previstos["objeto"] == row["objeto"]) &
                            (df_valores_previstos["tipo_de_gasto"] == row["tipo_de_gasto"])
                        ]

                        if not linha_prevista.empty:
                            valores_previstos = linha_prevista.iloc[0]
                            valores_previstos_por_mes = [valores_previstos[mes] for mes in ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]]
                        else:
                            valores_previstos_por_mes = [0] * 12

                        meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

                        df_plot = pd.DataFrame({
                            "Mês": meses * 2,
                            "valor": [row[mes] for mes in meses] + [valores_previstos[mes] for mes in meses],
                            "Tipo": ["Pago"] * 12 + ["Previsto"] * 12,
                            "contrato": row["contrato"],
                            "regioes": row["regioes"],
                            "nota_de_empenho": row["nota_de_empenho"]
                        })

                        # ✅ Ordena os meses
                        df_plot["Mês"] = pd.Categorical(df_plot["Mês"], categories=meses, ordered=True)

                        # ✅ Inverte a ordem das barras
                        df_plot["Tipo"] = pd.Categorical(df_plot["Tipo"], categories=["Previsto", "Pago"], ordered=True)

                        df_plot = df_plot.sort_values(["Mês", "Tipo"])

                        df_plot["label_br"] = df_plot["valor"].apply(
                            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        )

                        

                        fig = px.bar(
                            df_plot,
                            x="Mês",
                            y="valor",
                            color="Tipo",
                            barmode="group",
                            text="label_br",
                            labels={"valor": "Valor (R$)"},
                            color_discrete_map={
                                "Previsto": "#aec7e8",  # azul claro
                                "Pago": "#1f77b4"       # azul escuro
                            }
                        )

                        fig.update_traces(
                            textposition="inside",
                            textfont=dict(size=12, color="white"),
                            insidetextanchor="middle"
                        )

                        fig.update_layout(
                            height=300,
                            margin=dict(t=30, b=30),
                            xaxis_title="",
                            yaxis_title="Valor (R$)",
                            plot_bgcolor="#ffffff",
                            paper_bgcolor="#ffffff",
                            yaxis=dict(
                                tickprefix="R$ ",
                                separatethousands=True
                            ),
                            legend_title="",
                        )

                        st.markdown(f"#### 🧾 Nota de Empenho: {row['nota_de_empenho']}")
                        st.plotly_chart(fig, use_container_width=True, key=f"grafico_{row['nota_de_empenho']}")
                
                with st.expander("📊 Ver gráfico evolução mês a mês"):
                    # Filtra novamente para cada nota individualmente
                    df_filtrado = df_evolucao_empenho[
                        df_evolucao_empenho["Nota de Empenho"].astype(str).str.contains(str(row['nota_de_empenho']), na=False)
                    ]
                    
                    df_resumo = df_filtrado.groupby(["Mês", "Tipo de Métrica"])["Valor (R$)"].sum().reset_index()
                    df_pivot = df_resumo.pivot(index="Mês", columns="Tipo de Métrica", values="Valor (R$)").fillna(0)

                    # Garante a ordem correta dos meses
                    ordem_meses = ["JAN/2025", "FEV/2025", "MAR/2025", "ABR/2025", "MAI/2025"]
                    df_pivot.index = pd.Categorical(df_pivot.index, categories=ordem_meses, ordered=True)
                    df_pivot = df_pivot.sort_index()

                    legenda_dict = {
                        "DESPESAS EMPENHADAS (CONTROLE EMPENHO)": 'Empenhado',
                        "DESPESAS EMPENHADAS A LIQUIDAR (CONTROLE EMP)": 'A Liquidar',
                        "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": 'Liquidado'
                    }
                    st.subheader(f"📈 Evolução Mês a Mês - Empenho x A liquidar x Liquidado - (Nota de Empenho: {row['nota_de_empenho']})")

                    # Opção para escolher o tipo de gráfico
                    tipo_grafico_empenho = st.radio("Tipo de Gráfico", ["📊 Barras", "📈 Linha"], horizontal=True, key=f"grafico_empenho_{row['nota_de_empenho']}")
                    if tipo_grafico_empenho == "📊 Barras":
                        # Plota o gráfico de barras com a ordem correta
                        fig = go.Figure()
                        cores = {
                                
                                "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": "green",  # Cor verde para "Liquidado"
                            }
                        # Adiciona cada coluna de df_pivot como um conjunto de barras
                        for col in df_pivot.columns:
                            cor = cores.get(col)
                            fig.add_trace(go.Bar(
                                x=df_pivot.index,  # Meses como eixo X
                                y=df_pivot[col],  # Valores da métrica como eixo Y
                                name=legenda_dict.get(col, col),
                                text=[f"R$ {v:,.2f}" for v in df_pivot[col]],  # Formatação dos valores
                                textposition="outside",
                                marker_color=cor
                            ))

                            # Adicionar valores formatados nas barras
                        for trace in fig.data:
                            trace.text = [formatar_real(val) for val in trace.y]
                            trace.textposition = "outside"

                        # Atualiza o layout do gráfico de barras
                        fig.update_layout(
                            title=f"Evolução mês a mês — Nota de Empenho: {row['nota_de_empenho']}",
                            xaxis_title="Mês",
                            yaxis_title="Valor (R$)",
                            barmode="group",  # Agrupar as barras
                            xaxis=dict(tickmode="array", tickvals=df_pivot.index),
                            xaxis_tickangle=-45,  # Angulo das labels do eixo X
                            height=500,
                            plot_bgcolor="#ffffff",
                            paper_bgcolor="#ffffff",
                            legend_title="Tipo de Métrica",
                        )

                        # Exibe o gráfico de barras no Streamlit
                        st.plotly_chart(fig, use_container_width=True, key=f"grafico_empenho_plotar_{row['nota_de_empenho']}")
                    else:
                        # Plota o gráfico de linha com a ordem correta
                        fig = go.Figure()
                        cores = {
                                "DESPESAS LIQUIDADAS (CONTROLE EMPENHO)": "green",  # Cor verde para "Liquidado"
                            }
                        # Adiciona cada coluna de df_pivot como uma linha
                        for col in df_pivot.columns:
                            cor = cores.get(col)
                            fig.add_trace(go.Scatter(
                                x=df_pivot.index,  # Meses como eixo X
                                y=df_pivot[col],  # Valores da métrica como eixo Y
                                mode='lines+markers',  # Linha com marcadores
                                name=legenda_dict.get(col, col),
                                line=dict(width=3, color=cor),
                                marker=dict(size=6),
                                text=[f"R$ {v:,.2f}" for v in df_pivot[col]],  # Formatação dos valores
                                hovertemplate='<b>' + legenda_dict.get(col, col) + '</b><br>Mês: %{x}<br>R$ %{y:,.2f}<extra></extra>'  # Corrigido aqui
                            ))
                        fig.update_traces(hovertemplate='%{customdata}')
                        for trace in fig.data:
                            trace.customdata = [[
                                f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                            ] for v in trace.y]
                        fig.update_layout(hovermode="x unified")

                        # Atualiza o layout do gráfico de linha
                        fig.update_layout(
                            title=f"Evolução mês a mês — Nota de Empenho: {row['nota_de_empenho']}",
                            xaxis_title="Mês",
                            yaxis_title="Valor (R$)",
                            height=500,
                            plot_bgcolor="#ffffff",
                            paper_bgcolor="#ffffff",
                            legend_title="Tipo de Métrica",
                            xaxis=dict(tickmode="array", tickvals=df_pivot.index, showgrid=True),  # Ativa o grid no eixo X
                            yaxis=dict(showgrid=True),  # Ativa o grid no eixo Y
                            xaxis_tickangle=-45,
                        )

                        # Exibe o gráfico de linha no Streamlit
                        st.plotly_chart(fig, use_container_width=True)

                
                
                
                st.markdown("<div style='margin-bottom: 20px;'><hr></div>", unsafe_allow_html=True)
        


######################################################
        ### GRÁFICO DE EVOLUÇÃO MÊS A MÊS COM O valor_anual 
 
        st.subheader("📈 Evolução Mês a Mês - Geral")

        # 2. Valores previstos proporcionais
        df_valores_mensais = calcular_valores_mes_a_mes_ac(df_aux, ano_referencia=2025)
        meses = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]

        # 🔹 1. Obter valores previstos somando tudo para o contrato
        df_previsto = df_valores_mensais[df_valores_mensais["contrato"] == contrato]
        valores_previstos = df_previsto[meses].sum()
        #st.write(valores_previstos)

        # 🔹 2. Obter valores pagos reais para o contrato
        df_pago = df_local[df_local["contrato"] == contrato]
        df_pago_melt = df_pago.melt(id_vars=["contrato"], value_vars=meses, var_name="Mês", value_name="valor_pago_mensal")
        df_pago_agg = df_pago_melt.groupby("Mês", as_index=False)["valor_pago_mensal"].sum()
        df_pago_agg["Mês"] = pd.Categorical(df_pago_agg["Mês"], categories=meses, ordered=True)
        df_pago_agg = df_pago_agg.sort_values("Mês")
        valores_pagos = df_pago_agg["valor_pago_mensal"]

        # 🔹 3. Construir gráfico
        fig = go.Figure()

        # Barras de valores previstos
        fig.add_trace(go.Bar(
            x=meses,
            y=valores_previstos,
            name="Valor Previsto",
            marker_color="#2ca02c",
            text=[f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".") for v in valores_previstos],
            textposition="outside"
        ))

        # Barras de valores pagos
        fig.add_trace(go.Bar(
            x=meses,
            y=valores_pagos,
            name="Valor Pago",
            marker_color="#1f77b4",
            text=[f"R$ {v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".") for v in valores_pagos],
            textposition="outside"
        ))

        fig.update_layout(
            title=f"📊 Comparativo Mensal - Contrato {contrato}",
            xaxis_title="Mês",
            yaxis_title="Valor (R$)",
            barmode="group",
            height=500,
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
        )

        st.plotly_chart(fig, use_container_width=True)


        
        
        
        
#######################
#
# PARTE GERAL
#
########################

else:

    # Formatar valores monetários em reais
    colunas_valores = [
        "valor_mensal",
        "valor_anual_proporcional",
        "valor_empenhado",
        "valor_pago",
        "Diferença (Empenhado - Proporcional)"
    ]

    st.subheader("✅ Resumo Consolidado")
    df_exibicao = formatar_moeda_para_exibicao(df_final, colunas_valores)
    
    valor_anular = df_local[df_local['Diferença (Empenhado - Proporcional)'] > 0]['Diferença (Empenhado - Proporcional)'].sum()
    valor_reforcar = df_local[df_local['Diferença (Empenhado - Proporcional)'] < 0]['Diferença (Empenhado - Proporcional)'].sum()

    # Métricas principais
    col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 2, 2])
    col1.metric("Total de contratos", len(df_local))
    col2.metric("💰 Valor Anual", formatar_real(df_local['valor_anual'].sum()))
    col2.metric("💰 Valor do Exercício", formatar_real(df_local['valor_anual_proporcional'].sum()))
    col3.metric("💰 Valor Empenhado", formatar_real(df_local['valor_empenhado'].sum()))
    col4.metric("💵 Valor Pago", formatar_real(df_local['valor_pago'].sum()))

    with col5:
        if valor_reforcar < 0:
            st.metric("⚠️ Reforço Necessário",formatar_real(abs(valor_reforcar)), "Reforçar", delta_color="inverse")
        else:
            st.metric("✅ Valor a Anular", formatar_real(abs(valor_anular)), "Anular", delta_color="normal")

    # --- Tabs ---
    tab1, tab2,tab3 = st.tabs(["📌 Resumo Geral", "Situação Geral", "📉 Rescisões"])

    # ========== TAB 1 ==========
    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Comparação por Região")
            df_regioes = df_local.groupby("regioes", as_index=False)[["valor_anual", "valor_empenhado", "valor_pago"]].sum()
            df_regioes = df_regioes.sort_values(by="valor_empenhado", ascending=False)
            
            # 3. Reorganiza para gráfico com legendas personalizadas
            df_plot = df_regioes.melt(id_vars="regioes", 
                                    value_vars=["valor_anual", "valor_empenhado", "valor_pago"],
                                    var_name="tipo_valor", value_name="valor")

            # 4. Aplica nomes bonitos (somente para visualização!)
            df_plot["tipo_valor_bonito"] = df_plot["tipo_valor"].map(NOMES_BONITOS)

            # 5. Gráfico
            fig = px.bar(
                df_plot,
                x="regioes",
                y="valor",
                color="tipo_valor_bonito",
                barmode="group",
                title="💰 Comparação de Valores por Região",
                color_discrete_map={
                    NOMES_BONITOS["valor_anual"]: "#2ca02c",
                    NOMES_BONITOS["valor_empenhado"]: "#1f77b4",
                    NOMES_BONITOS["valor_pago"]: "#ff7f0e"
                },
                labels={"regioes": "Região", "valor": "Valor (R$)", "tipo_valor_bonito": "Tipo"}
            )

            fig.update_layout(
                xaxis_title="Região",
                yaxis_title="Valor (R$)",
                bargap=0.15,
                height=500
            )

            # Exibir valores em cada barra
            for trace in fig.data:
                trace.text = [formatar_real(v) for v in trace.y]

            st.plotly_chart(fig)

        with col2:
            st.subheader("📊 Comparação por objeto")
            # Renomeia colunas para nomes bonitos temporariamente
            df_objeto = df_local.groupby("objeto", as_index=False)[["valor_anual", "valor_empenhado", "valor_pago"]].sum()
            df_objeto = df_objeto.sort_values(by="valor_empenhado", ascending=False)

            # Renomear para nomes bonitos (copiar só as colunas necessárias)
            col_renomeadas = {
                "valor_anual": NOMES_BONITOS.get("valor_anual", "Valor Anual"),
                "valor_empenhado": NOMES_BONITOS.get("valor_empenhado", "Valor Empenhado"),
                "valor_pago": NOMES_BONITOS.get("valor_pago", "Valor Pago")
            }
            df_plot = df_objeto.rename(columns=col_renomeadas)

            fig_obj = px.bar(
                df_plot,
                x="objeto",
                y=list(col_renomeadas.values()),  # usa os nomes bonitos diretamente
                barmode="group",
                title="💰 Comparação de Valores por Objeto",
                color_discrete_map={
                    col_renomeadas["valor_anual"]: "#2ca02c",
                    col_renomeadas["valor_empenhado"]: "#1f77b4",
                    col_renomeadas["valor_pago"]: "#ff7f0e"
                },
                labels={"objeto": "Objeto"}
            )

            # Ajustar os textos nas barras
            limite = df_objeto[["valor_anual", "valor_empenhado", "valor_pago"]].mean().mean()

            for trace in fig_obj.data:
                trace.text = [formatar_real(val) for val in trace.y]
                trace.textposition = ["outside" if val < limite else "inside" for val in trace.y]

            fig_obj.update_layout(
                xaxis_title="Objeto",
                yaxis_title="Valor (R$)",
                bargap=0.15,
                height=500,
            )

            st.plotly_chart(fig_obj, use_container_width=True)

        # Destaque sobre contratos rescindidos
        

        
        # Filtra apenas as que são rescisão
        rescisoes_aux = df_final[
            df_final["tipo_de_alteracao"].str.lower().str.contains("rescisão", na=False)
        ]

        
        rescisoes = rescisoes_aux
        #st.dataframe(rescisoes)
        rescisoes["Valor a Anular"] = rescisoes["valor_empenhado"] - rescisoes["valor_anual"]
        valor_total_anular = rescisoes["Valor a Anular"].sum()

        st.markdown(f"""
        ### 💡 IMPORTANTE
        - **{len(rescisoes)} contratos rescindidos** foram identificados.
        - Valor total a anular: 🟢 **{formatar_real(valor_total_anular)}**
        > *Esse valor pode ser realocado ou economizado.*
        """)

    with tab2:
        def formatar_valor(valor):
            if pd.isna(valor):
                return ''
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def formatar_data(data):
            if pd.isna(data):
                return '-'
            return data.strftime('%d/%m/%Y')

        def formatar_diferenca(valor):
            try:
                valor = float(valor)
            except:
                return "-"
            if valor < 0:
                return f"<span style='color: red; font-weight: bold;'>🔻 Reforçar R$ {abs(valor):,.2f}</span>".replace(",", "#").replace(".", ",").replace("#", ".")
            elif valor > 0:
                return f"<span style='color: green; font-weight: bold;'>🔺 Anular R$ {valor:,.2f}</span>".replace(",", "#").replace(".", ",").replace("#", ".")
            else:
                return f"<span style='color: gray;'>Sem diferença</span>"

        status_prioridade = {
            "Repactuado": 3,
            "Reajustado": 2,
            "Em análise": 1,
            "Não solicitado": 0
        }
        def status_mais_relevante(statuses):
            statuses = [str(s) for s in statuses if pd.notna(s)]
            if not statuses:
                return "Não informado"
            return max(statuses, key=lambda x: status_prioridade.get(x, -1))
        
        def preparar_df_para_visualizacao(df, modo='compilado'):
            df = df.copy()
            df['Data Última Repactuação/Reajuste'] = pd.to_datetime(df['Data Última Repactuação/Reajuste'], errors='coerce')
            df['tipo_de_alteracao'] = df['tipo_de_alteracao'].fillna('').astype(str)
            df['Status Atualização'] = df['Status Atualização'].fillna('').astype(str)
            if modo == 'compilado':
                df_compilado = df.groupby(['contrato', 'processo']).agg({
                    'regioes': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'estado': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'unidade': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'objeto': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'contratada': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'cnpj/cpf': lambda x: ' / '.join(sorted(set(x.dropna()))),
                    'valor_empenhado': 'sum',
                    'valor_pago': 'sum',
                    'valor_anual_proporcional': 'sum',
                    'jan': 'sum', 'fev': 'sum', 'mar': 'sum', 'abr': 'sum', 'mai': 'sum',
                    'jun': 'sum', 'jul': 'sum', 'ago': 'sum', 'set': 'sum',
                    'out': 'sum', 'nov': 'sum', 'dez': 'sum',
                    'tipo_de_alteracao': 'max',
                    'Status Atualização': status_mais_relevante,
                    'Data Última Repactuação/Reajuste': 'max',
                    'Diferença (Empenhado - Proporcional)': 'sum'
                }).reset_index()
                return df_compilado
            
            else:
                # Detalhado, mas simulando as mesmas colunas da compilada
                df['Diferença (Empenhado - Proporcional)'] = df['valor_empenhado'] - df['valor_anual_proporcional']
                return df[[
                    'contrato', 'processo', 'regioes', 'estado', 'unidade', 'objeto', 'contratada', 'cnpj/cpf',
                    'valor_empenhado', 'valor_pago', 'valor_anual_proporcional',
                    'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez',
                    'tipo_de_alteracao', 'Status Atualização', 'Data Última Repactuação/Reajuste',
                    'Diferença (Empenhado - Proporcional)'
                ]]
        
        modo_consolidado = st.toggle("🔄 Mostrar dados consolidados", value=True)
        modo_escolhido = 'compilado' if modo_consolidado else 'detalhado'

        df_para_tabela = preparar_df_para_visualizacao(df_local, modo=modo_escolhido)
        # Usa a mesma renderização de tabela para ambos
        df_compilado=df_para_tabela
        
        import html
        

        st.markdown("## 📋 Lista de Contratos por Diferença")


        
        df = df_compilado
        def formatar_valor(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def formatar_diferenca_html(valor):
            if valor < 0:
                # ícone de “mais” verde + texto reforçar
                return f'<span style="color:#228B22; font-weight:bold;">&#43; Reforçar R$ {abs(valor):,.2f}</span>'.replace(",", "X").replace(".", ",").replace("X", ".")
            elif valor > 0:
                # ícone de “menos” vermelho + texto anular
                return f'<span style="color:#B22222; font-weight:bold;">&#8722; Anular R$ {valor:,.2f}</span>'.replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                return '<span style="color:gray;">Sem diferença</span>'
        def formatar_data(data):
            if pd.isna(data):
                return '-'
            return data.strftime('%d/%m/%Y')

        df['Valor Empenhado'] = df['valor_empenhado'].apply(formatar_valor)
        df['Valor Pago'] = df['valor_pago'].apply(formatar_valor)
        df['Anular/Reforçar'] = df['Diferença (Empenhado - Proporcional)'].apply(formatar_diferenca_html)
        df['Data Última Repactuação/Reajuste'] = df['Data Última Repactuação/Reajuste'].apply(formatar_data)

        def limpar(texto):
            return html.escape(str(texto)).replace("\n", " ").strip()

        html_tabela = """
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.4/css/jquery.dataTables.min.css">
        <link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.3.6/css/buttons.dataTables.min.css" />
        <style>
        body {
            margin:0; padding:0;
            font-family: 'Segoe UI', 'Inter', sans-serif;
            font-size: 13px;
            background: white;
        }

        /* Envolve toda a tabela, mantendo o tamanho fixo */

        /* Envolve toda a tabela, mantendo o tamanho fixo */
        .dataTables_wrapper {
            overflow-x: auto;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 10px 10px 10px;  /* espaço acima para o botão */
            box-sizing: border-box;
            position: relative;
        }

        .dataTables_filter {
            margin-bottom: 12px;
            
        }


        table.dataTable {
            width: 100% !important;
            border-collapse: separate !important;
            border-spacing: 0 !important;
            border: 1px solid #d1dce5 !important;
            border-radius: 6px !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            background-color: #fcfcfc;
        }

        thead th {
            background-color: #4a6fa5 !important;
            color: white !important;
            font-weight: 600;
            font-size: 13px;
            position: sticky !important;
            top: 0;
            z-index: 10;
        }

        .dataTables_scrollBody {
            max-height: 420px !important;
            overflow-y: auto !important;
        }

        tbody tr:hover {
            background-color: #eef3fc !important;
        }

        td, th {
            white-space: nowrap !important;
            padding: 8px 12px !important;
            vertical-align: middle !important;
        }

        td.right, th.right {
            text-align: right !important;
            font-variant-numeric: tabular-nums !important;
        }

        td span {
            font-weight: 600;
        }

        td.reforcar {
            color: #228B22;
            font-weight: 700;
        }

        td.anular {
            color: #B22222;
            font-weight: 700;
        }

        td.complementar {
            color: #555;
            font-size: 12px;
        }
        /* Estilo dos botões */
        /* Botão Exportar: discreto e acima do campo pesquisar */
        div.dt-buttons {
            position: absolute;
            top: 5px;   /* MAIS ACIMA */
            right: 10px;
            z-index: 20;
        }

        .dt-buttons .btn-sm {
            font-size: 12px !important;
            padding: 4px 8px !important;
            border-radius: 4px;
            background-color: transparent;
            border: 1px solid #4a6fa5;
            color: #4a6fa5;
        }

        .dt-buttons .btn-sm:hover {
            background-color: #4a6fa5;
            color: white;
        </style>

        <div style="overflow-x:auto;">
        <table id="contratos" class="display nowrap" style="width:100%">
        <thead>
        <tr>
            <th>📁 Contrato</th>
            <th>🔍 Processo</th>
            <th title="Resumo do objeto contratado">📌 Objeto</th>
            <th class="right">📅 Valor Empenhado</th>
            <th class="right">💰 Valor Pago</th>
            <th class="right">💸 Anular/Reforçar</th>
            <th>🏢 Unidade</th>
            <th title="Nome completo da contratada">🏢 Contratada</th>
            <th>📅 Última Repactuação</th>
            <th>📌 Situação</th>
            <th class="complementar right">Jan</th>
            <th class="complementar right">Fev</th>
            <th class="complementar right">Mar</th>
            <th class="complementar right">Abr</th>
            <th class="complementar right">Mai</th>
            <th class="complementar right">Jun</th>
            <th class="complementar right">Jul</th>
            <th class="complementar right">Ago</th>
            <th class="complementar right">Set</th>
            <th class="complementar right">Out</th>
            <th class="complementar right">Nov</th>
            <th class="complementar right">Dez</th>
        </tr>
        </thead>
        <tbody>
        """

        # Loop de preenchimento
        for _, row in df.iterrows():
            contrato = limpar(row['contrato'])
            processo = limpar(row['processo'])
            objeto = limpar(row['objeto'])
            empenhado = row['Valor Empenhado']
            pago = row['Valor Pago']
            diferenca_valor = row['Anular/Reforçar']
            unidade = limpar(row['unidade'])
            contratada = limpar(row['contratada'])
            data_repa = row['Data Última Repactuação/Reajuste']
            situacao = limpar(row['Status Atualização'])
            meses = [formatar_valor(row.get(m, 0)) for m in ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]]

            # Define a classe da diferença (para cor)
            if "Anular" in str(diferenca_valor):
                classe_dif = "anular"
            elif "Reforçar" in str(diferenca_valor):
                classe_dif = "reforcar"
            else:
                classe_dif = ""

            html_tabela += f"""
            <tr>
                <td>{contrato}</td>
                <td>{processo}</td>
                <td title="{objeto}">{objeto}</td>
                <td class="right">{empenhado}</td>
                <td class="right">{pago}</td>
                <td class="right {classe_dif}">{diferenca_valor}</td>
                <td>{unidade}</td>
                <td title="{contratada}">{contratada}</td>
                <td>{data_repa}</td>
                <td>{situacao}</td>
                {''.join(f'<td class="complementar right">{v}</td>' for v in meses)}
            </tr>
            """

        html_tabela += """
        </tbody>
        </table>
        </div>

        <script src="https://code.jquery.com/jquery-3.5.1.js"></script>
        <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/dataTables.buttons.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.html5.min.js"></script>
        <script src="https://cdn.datatables.net/buttons/2.3.6/js/buttons.print.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.0/jszip.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/pdfmake.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.7/vfs_fonts.js"></script>
        <script>
        $(document).ready(function() {
            $('#contratos').DataTable({
                dom: 'Blfrtip',
                buttons: [
                    {
                        extend: 'collection',
                        text: 'Exportar ▾',
                        className: 'btn-sm btn-outline-primary',  // botão menor e com contorno leve
                        buttons: ['copy', 'csv', 'excel', 'pdf', 'print']
                    }
                ],
                scrollX: true,
                scrollY: '420px',
                scrollCollapse: true,
                paging: true,
                pageLength: 10,
                fixedHeader: true,
                language: {
                    url: 'https://cdn.datatables.net/plug-ins/1.13.4/i18n/pt-BR.json'
                },
                columnDefs: [
                    { targets: [3,4,5], className: 'dt-body-right' }
                ]
            });
        });
        </script>
        """

        components.html(html_tabela, height=620, scrolling=True, width=1200)












    # ========== TAB 2 ==========
    with tab3:
        
        df_fmt = df_local.copy()
        df_fmt = df_fmt, ["valor_empenhado", "valor_pago", "valor_anual"]
        rescisoes["Valor a Anular"] = rescisoes["valor_empenhado"] - rescisoes["valor_anual"]

        anular = rescisoes[rescisoes["Valor a Anular"] < 0]
        reforcar = rescisoes[rescisoes["Valor a Anular"] > 0]

        total_anular = anular["Valor a Anular"].sum()
        total_reforcar = reforcar["Valor a Anular"].sum()

        # --- Cards informativos ---
        st.markdown(f"""
        <style>
        .card-container {{
            display: flex;
            gap: 1rem;
            margin-top: 10px;
            margin-bottom: 5px;
        }}
        .card {{
            flex: 1;
            padding: 1rem;
            border-radius: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            color: white;
            text-align: center;
            font-size: 1.2rem;
            font-weight: bold;
        }}
        .card.green {{
            background: linear-gradient(135deg, #2e7d32, #66bb6a);
        }}
        .card.red {{
            background: linear-gradient(135deg, #c62828, #ef5350);
        }}
        </style>
        <div class="card-container">
            <div class="card green">
                ✅ Valor Passível de Anulação<br>
                <span style="font-size: 1.6rem;">{formatar_real(total_anular)}</span>
            </div>
            <div class="card red">
                ⚠️ Valor Necessário de Reforço<br>
                <span style="font-size: 1.6rem;">{formatar_real(abs(total_reforcar))}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        
        # Função para gerar os cards lado a lado
        def mostrar_contratos_em_cards(dados, titulo):
            st.markdown(f"### {titulo}")
            num_colunas = 2  # Quantos cards por linha
            total_linhas = math.ceil(len(dados) / num_colunas)

            for i in range(total_linhas):
                cols = st.columns(num_colunas)
                for j in range(num_colunas):
                    idx = i * num_colunas + j
                    if idx < len(dados):
                        row = dados.iloc[idx]
                        with cols[j]:
                            st.markdown(f"""
                            <div style="
                                background-color: #f1f8e9;
                                border-left: 5px solid #558b2f;
                                padding: 15px;
                                border-radius: 12px;
                                box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
                                margin-bottom: 15px;
                            ">
                                <h4 style="margin-top: 0;">📄 contrato {row['contrato']}</h4>
                                <p><b>📍 Região:</b> {row['unidade']}</p>
                                <p><b>🎯 objeto:</b> {row['objeto']}</p>
                                <p><b>💰 Valor Empenhado:</b> {formatar_real(row['valor_empenhado'])}</p>
                                <p><b>📊 Valor Anual:</b> {formatar_real(row['valor_anual'])}</p>
                                <p style="color: green; font-size: 16px;"><b>🔻 Valor a Anular:</b> {formatar_real(row['Valor a Anular'])}</p>
                            </div>
                            """, unsafe_allow_html=True)

        # Exemplo de uso:
        mostrar_contratos_em_cards(anular,titulo="🔻 Contratos com valor a anular")

        st.markdown("""
        <div style='margin-top: 10px; background-color: #e8f5e9; padding: 10px; border-left: 5px solid #2e7d32'>
        💡 Esses contratos apresentam saldo a ser devolvido devido à rescisão antecipada.
        </div>
        """, unsafe_allow_html=True)

        mostrar_contratos_em_cards(reforcar,titulo="⚠️ Contratos com valor a reforçar")

        st.markdown("""
        <div style='margin-top: 10px; background-color: #ffebee; padding: 10px; border-left: 5px solid #c62828'>
        ⚠️ Estes contratos consumiram mais do que o proporcional até a data da rescisão. Avaliar possível reforço ou erro no empenho.
        </div>
        """, unsafe_allow_html=True)

        # --- Exportação ---
        st.markdown("📥 Baixar dados filtrados:")
        csv = rescisoes.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button("⬇️ Baixar CSV com todos os dados filtrados", data=csv, file_name="contratos_rescindidos.csv", mime="text/csv")


