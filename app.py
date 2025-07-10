import streamlit as st

st.set_page_config(page_title="CCONT", page_icon="🗂️", layout="wide")
# --- Sidebar ---


    

pages = {
    "Pagina Inícial":[
        st.Page("pages/index.py", title="Início", icon="🏠"),
    ],
    "Relatórios": [
        st.Page("pages/app_contratos.py", title="Painel Contratos", icon="📊"),
        st.Page("pages/orcame.py", title="Painel Orçamentário", icon="📊"),
    ],
    "Configurações": [
        st.Page("pages/atualizar_pagamentos_nota.py", title="Configurações", icon="⚙️"),
    ],
}
pg = st.navigation(pages)
pg.run()

with st.sidebar:
    # Configuração da página
    st.caption("© 2025 - Eduardo Júnior")