import streamlit as st
import os

# Configuração da página
st.set_page_config(
    page_title="eSocial/REINF - Leitor de Eventos",
    page_icon="📋",
    layout="wide"
)

# Caminhos absolutos para as páginas
PASTA_PAGES = os.path.join(os.path.dirname(__file__), "pages")
CAMINHO_S1202 = os.path.join(PASTA_PAGES, "1_S1202.py")
CAMINHO_S5002 = os.path.join(PASTA_PAGES, "2_S5002.py")
CAMINHO_REINF4010 = os.path.join(PASTA_PAGES, "EFDREINF_4010.py")
CAMINHO_ANALISE_RUBRICAS = os.path.join(PASTA_PAGES, "analise_rubricas.py")

# Verificação se os arquivos existem
arquivos_existentes = []
arquivos_faltando = []

if os.path.exists(CAMINHO_S1202):
    arquivos_existentes.append("S-1202")
else:
    arquivos_faltando.append("1_S1202.py")

if os.path.exists(CAMINHO_S5002):
    arquivos_existentes.append("S-5002")
else:
    arquivos_faltando.append("2_S5002.py")

if os.path.exists(CAMINHO_REINF4010):
    arquivos_existentes.append("REINF-4010")
else:
    arquivos_faltando.append("EFDREINF_4010.py")

if os.path.exists(CAMINHO_ANALISE_RUBRICAS):
    arquivos_existentes.append("ANÁLISE-RUBRICAS")
else:
    arquivos_faltando.append("analise_rubricas.py")

# CSS personalizado para melhorar a aparência
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
    color: white;
    padding: 2rem;
    border-radius: 15px;
    margin-bottom: 2rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.module-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1.5rem;
    border-radius: 12px;
    margin: 1rem 0;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s ease;
}

.module-card:hover {
    transform: translateY(-5px);
}

.module-card h3 {
    margin-top: 0;
    font-size: 1.3rem;
}

.module-card p {
    margin-bottom: 1rem;
    opacity: 0.9;
}

.metric-container {
    background: rgba(255,255,255,0.1);
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
}

.status-ok {
    color: #4CAF50;
    font-weight: bold;
}

.status-error {
    color: #f44336;
    font-weight: bold;
}

.info-section {
    background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
    padding: 1.5rem;
    border-radius: 12px;
    margin: 1rem 0;
    border-left: 5px solid #ff9068;
}
</style>
""", unsafe_allow_html=True)

# Interface principal
st.markdown("""
<div class="main-header">
    <h1>📋 Sistema eSocial/REINF</h1>
    <p>Processamento automatizado de eventos fiscais e trabalhistas</p>
</div>
""", unsafe_allow_html=True)

# Cards dos módulos - Layout 2x2
col1, col2 = st.columns(2)

with col1:
    # S-1202
    st.markdown("""
    <div class="module-card">
        <h3>📄 S-1202 - Informe de Rendimentos</h3>
        <p><strong>Rendimentos do RPPS</strong></p>
        <p>• Busca por CPF e período de referência (perRef)<br>
        • Geração de comprovantes PDF personalizados<br>
        • Resumo consolidado de IR por período<br>
        • Interface moderna com cache otimizado</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "S-1202" in arquivos_existentes:
        if st.button("🚀 Acessar S-1202", use_container_width=True, type="primary"):
            st.switch_page("pages/1_S1202.py")
    else:
        st.error("❌ Arquivo 1_S1202.py não encontrado")

    # REINF 4010
    st.markdown("""
    <div class="module-card">
        <h3>💰 REINF 4010 - Pagamentos PF</h3>
        <p><strong>Pagamentos a Pessoas Físicas</strong></p>
        <p>• Análise de retenções de IRRF<br>
        • Relatórios exportáveis em CSV<br>
        • Busca avançada por beneficiário<br>
        • Consolidação por período</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "REINF-4010" in arquivos_existentes:
        if st.button("🚀 Acessar REINF 4010", use_container_width=True, type="primary"):
            st.switch_page("pages/EFDREINF_4010.py")
    else:
        st.error("❌ Arquivo EFDREINF_4010.py não encontrado")

with col2:
    # S-5002
    st.markdown("""
    <div class="module-card">
        <h3>🏛️ S-5002 - Informe de Imposto</h3>
        <p><strong>Retenção de IRRF</strong></p>
        <p>• Informações de dependentes e deduções<br>
        • Análise por código de receita<br>
        • Busca por CPF do titular<br>
        • Relatórios detalhados de retenção</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "S-5002" in arquivos_existentes:
        if st.button("🚀 Acessar S-5002", use_container_width=True, type="primary"):
            st.switch_page("pages/2_S5002.py")
    else:
        st.error("❌ Arquivo 2_S5002.py não encontrado")

    # Análise de Rubricas (NOVO)
    st.markdown("""
    <div class="module-card" style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333;">
        <h3>📊 Análise de Rubricas - NOVO!</h3>
        <p><strong>Sistema Avançado de Rubricas eSocial</strong></p>
        <p>• Dashboard interativo com 3000+ rubricas<br>
        • Classificações por incidências tributárias<br>
        • Busca avançada e filtros múltiplos<br>
        • Gráficos e estatísticas detalhadas</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "ANÁLISE-RUBRICAS" in arquivos_existentes:
        if st.button("🚀 Acessar Análise de Rubricas", use_container_width=True, type="primary"):
            st.switch_page("pages/analise_rubricas.py")
    else:
        st.error("❌ Arquivo analise_rubricas.py não encontrado")

# Status do sistema
st.markdown("---")
st.markdown("### 📊 Status do Sistema")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="metric-container">
        <h4>📁 Módulos eSocial</h4>
        <h2 style="color: #4CAF50;">3</h2>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-container">
        <h4>💰 Módulos REINF</h4>
        <h2 style="color: #2196F3;">1</h2>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-container">
        <h4>📊 Módulos Análise</h4>
        <h2 style="color: #FF9800;">1</h2>
    </div>
    """, unsafe_allow_html=True)

with col4:
    disponivel_cor = "#4CAF50" if len(arquivos_existentes) == 5 else "#FF9800"
    st.markdown(f"""
    <div class="metric-container">
        <h4>✅ Disponíveis</h4>
        <h2 style="color: {disponivel_cor};">{len(arquivos_existentes)}/5</h2>
    </div>
    """, unsafe_allow_html=True)

# Avisos se houver arquivos faltando
if arquivos_faltando:
    st.warning(f"⚠️ Arquivos não encontrados: {', '.join(arquivos_faltando)}")

# Novidades
st.markdown("---")
st.markdown("### 🆕 Últimas Atualizações")

st.markdown("""
<div class="info-section">
    <h4>🚀 Versão 2.1 - Análise de Rubricas</h4>
    <ul>
        <li><strong>📊 Dashboard Interativo:</strong> Visualização completa de mais de 3000 rubricas</li>
        <li><strong>🔍 Busca Avançada:</strong> Filtros múltiplos por código, descrição, natureza e incidências</li>
        <li><strong>📈 Análises Tributárias:</strong> Heatmaps e classificações por IRRF, Previdência, FGTS</li>
        <li><strong>📋 Exportação CSV:</strong> Download de resultados filtrados</li>
        <li><strong>🎯 Classificações Automáticas:</strong> Por categoria, status e combinações de incidências</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# Informações técnicas
st.markdown("---")
st.markdown("### 🔧 Informações Técnicas")

with st.expander("📦 Dependências e Instalação"):
    st.markdown("""
    **Para recriar esta aplicação em outro computador, instale:**
    
    ```bash
    # Dependências Python (via pip)
    pip install streamlit
    pip install pandas
    pip install fpdf2
    pip install openpyxl
    pip install plotly  # NOVO - Para análise de rubricas
    pip install lxml    # OPCIONAL - Para melhor performance XML
    
    # Ou instalar todas de uma vez:
    pip install streamlit pandas fpdf2 openpyxl plotly lxml
    ```
    
    **Bibliotecas nativas do Python utilizadas:**
    - `os` - Manipulação de arquivos e diretórios
    - `xml.etree.ElementTree` - Processamento de arquivos XML
    - `io` - Operações de entrada/saída em memória
    - `datetime` - Manipulação de datas
    - `base64` - Codificação para downloads
    - `locale` - Formatação de números/moeda
    - `sys` - Informações do sistema
    - `json` - Processamento de arquivos JSON
    - `collections.defaultdict` - Estruturas de dados
    - `pickle` - Serialização para cache
    - `hashlib` - Geração de hashes para cache
    - `pathlib` - Manipulação moderna de caminhos
    - `functools` - Decoradores e cache
    
    **Estrutura de arquivos necessária:**
    ```
    projeto/
    ├── main.py (este arquivo)
    ├── codigos_s5002.json (para S-5002)
    └── pages/
        ├── 1_S1202.py
        ├── 2_S5002.py
        ├── EFDREINF_4010.py
        └── analise_rubricas.py (NOVO)
    ```
    """)

with st.expander("⚙️ Configurações"):
    st.markdown("""
    **Caminhos configuráveis nos scripts:**
    - **Pasta de eventos XML**: `C:\\Users\\c046190\\Desktop\\Meu Python\\Eventos_eSocial`
    - **Pasta de rubricas** (S-1202 e Análise): `C:\\Users\\c046190\\Desktop\\Meu Python\\PythonTST\\.vscode\\pages\\Rubricas`
    - **Arquivo de códigos** (S-5002): `codigos_s5002.json`
    
    **Funcionalidades principais:**
    - 🔍 Busca pesquisável por CPF
    - 📊 Análise de dados com métricas interativas
    - 📄 Geração de PDFs e CSVs
    - 🎨 Interface moderna com gradientes
    - 🛡️ Tratamento robusto de erros
    - ⚡ Sistema de cache para performance
    - 📈 Gráficos interativos com Plotly
    """)

with st.expander("🚀 Como executar"):
    st.markdown("""
    **Passos para executar:**
    
    1. **Instalar Python 3.7+**
    2. **Instalar dependências** (ver aba "Dependências")
    3. **Criar estrutura de arquivos** conforme mostrado acima
    4. **Configurar caminhos** nos scripts conforme seu ambiente
    5. **Executar comando:**
       ```bash
       streamlit run main.py
       ```
    6. **Acessar** `http://localhost:8501` no navegador
    
    **Observações importantes:**
    - Certifique-se de que os arquivos XML estejam nas pastas configuradas
    - Para S-5002, crie o arquivo `codigos_s5002.json` com as descrições
    - Para S-1202 e Análise de Rubricas, configure a pasta com arquivos XML de rubricas
    - **NOVO:** Para análise de rubricas, recomenda-se instalar `lxml` para melhor performance
    
    **Estrutura das pastas XML:**
    ```
    Eventos_eSocial/
    ├── S-1202 (arquivos de rendimentos)
    ├── S-5002 (arquivos de IRRF)
    └── REINF-4010 (arquivos de pagamentos PF)
    
    Rubricas/
    └── S-1010 (arquivos de tabela de rubricas)
    ```
    """)

with st.expander("📊 Recursos da Análise de Rubricas"):
    st.markdown("""
    **O que você pode fazer no novo módulo:**
    
    **🎯 Dashboard Principal:**
    - Métricas gerais: Total, ativas, rendimentos, deduções
    - Gráficos de distribuição por categoria e status
    - Análise de incidências tributárias
    
    **🔍 Análise Detalhada:**
    - Filtros por categoria, status, IRRF, previdência
    - Top 10 naturezas mais comuns
    - Timeline de criação das rubricas
    - Tabela interativa com dados filtrados
    
    **🧠 Classificações Avançadas:**
    - Combinações de incidências (CP+IRRF+FGTS, etc.)
    - Agrupamento por faixas de natureza
    - Heatmap cruzado IRRF vs Previdência
    - Estatísticas percentuais detalhadas
    
    **🔍 Busca Avançada:**
    - Busca por código, descrição, natureza, observação
    - Até 8 filtros combinados simultaneamente
    - Exportação CSV dos resultados
    - Visualização detalhada de rubricas individuais
    
    **💡 Insights que você obterá:**
    - Quantas rubricas incidem IRRF E Previdência?
    - Quais naturezas são mais comuns por categoria?
    - Como evoluiu a criação de rubricas ao longo dos anos?
    - Quais combinações de incidências são mais frequentes?
    """)

# Rodapé
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 12px;'>"
    "Sistema de Processamento eSocial/REINF v2.1 - Agora com Análise Avançada de Rubricas"
    "</div>", 
    unsafe_allow_html=True
)