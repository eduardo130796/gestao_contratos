import streamlit as st


st.title("🎯 Bem-vindo a Gestão da CCCONT!")
st.write("Explore as funcionalidades desenvolvidas para facilitar a gestão da Cordenação de Contratos.")

# Criando cards interativos
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🕵️‍♂️ Painel de Contratos")
    st.write("Verifique vigências, contratos a vencer e relátorios.")
    st.page_link("pages/app_contratos.py", label="Contratos", icon="🕵️‍♂️")

    
with col2:
    st.markdown("### 📊 Painel Orçamentário")
    st.write("Painel Gerencial Orçamentário.")
    st.page_link("pages/orcame.py", label="Relatório", icon="📊")



# Rodapé fixo com largura total
rodape = """
    <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f8f9fa;
            text-align: center;
            padding: 10px;
            font-size: 14px;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
            z-index: 100;
        }
    </style>
    <div class="footer">
        Desenvolvido por <strong>Eduardo Júnior</strong> | 2025
    </div>
"""

# Exibir o rodapé na interface
st.markdown(rodape, unsafe_allow_html=True)