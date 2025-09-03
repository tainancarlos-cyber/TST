import streamlit as st
import os
import xml.etree.ElementTree as ET
import pandas as pd
import io
from datetime import datetime
import base64
import locale
import sys
from collections import defaultdict


# Configura locale para formatação de valores
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        st.warning(
            "Não foi possível configurar o locale para formatação de números.")

# Configuração da página
st.set_page_config(
    page_title="REINF 4010 - Pagamentos PF",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Funções auxiliares ---


def voltar_pagina_principal():
    st.switch_page("main.py")


def filtrar_cpfs(cpfs, termo_busca):
    """Filtra CPFs baseado no termo de busca"""
    if not termo_busca:
        return cpfs
    return [cpf for cpf in cpfs if termo_busca.replace(".", "").replace("-", "") in cpf.replace(".", "").replace("-", "")]


def filtrar_periodos(periodos, termo_busca):
    """Filtra períodos baseado no termo de busca"""
    if not termo_busca:
        return periodos
    return [periodo for periodo in periodos if termo_busca in periodo]


def criar_interface_cpf_pesquisavel(cpfs):
    """Cria uma interface pesquisável para seleção de CPF"""
    col1, col2 = st.columns([4, 1])

    with col1:
        termo_busca = st.text_input(
            "🔍 Pesquisar CPF:",
            placeholder="Digite números do CPF",
            help="Digite parte do CPF para filtrar",
            key="cpf_search"
        )

    with col2:
        if st.button("🗑️ Limpar", help="Limpar busca", key="limpar_cpf"):
            st.rerun()

    # Filtra CPFs baseado na busca
    cpfs_filtrados = filtrar_cpfs(cpfs, termo_busca)

    if termo_busca and not cpfs_filtrados:
        st.warning("❌ Nenhum CPF encontrado.")
        return None

    # Limita exibição
    max_display = 50
    cpfs_para_exibir = cpfs_filtrados[:max_display] if len(
        cpfs_filtrados) > max_display else cpfs_filtrados

    if len(cpfs_filtrados) > max_display:
        st.info(
            f"Mostrando {max_display} de {len(cpfs_filtrados)} CPFs encontrados")

    opcoes_cpf = [""] + cpfs_para_exibir

    cpf_selecionado = st.selectbox(
        "Selecionar CPF:",
        opcoes_cpf,
        index=0,
        key="cpf_select"
    )

    return cpf_selecionado if cpf_selecionado else None


def format_value(val):
    """Formata valores monetários"""
    try:
        return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)


def format_cpf_completo(cpf):
    """Formata CPF completo para exibição (sem máscara)"""
    if not cpf or cpf is None:
        return "N/A"

    # Remove formatação existente
    cpf_limpo = str(cpf).replace(".", "").replace("-", "").replace(" ", "")

    if len(cpf_limpo) == 11 and cpf_limpo.isdigit():
        return f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
    return str(cpf)


# --- Configuração inicial ---

# Namespace para REINF 4010
NS_REINF = {
    'ns': 'http://www.reinf.esocial.gov.br/schemas/evt4010PagtoBeneficiarioPF/v2_01_02'
}

# Caminho corrigido
PASTA_BASE = r"C:\Users\tst\OneDrive\Área de Trabalho\Meus Phytons\.vscode\pages\downloads\efd_reinf"

# Mapeamento de naturezas de rendimento
NATUREZAS_RENDIMENTO = {
    '10002': 'Diárias',
    '10003': 'Ajudas de custo',
    '10004': 'Jetons',
    '10005': 'Honorários',
    '10006': 'Serviços prestados por pessoa física',
    '10007': 'Comissões',
    '10008': 'Rendimentos de trabalho sem vínculo',
    '10009': 'Rendimentos de aluguéis',
    '10010': 'Royalties',
    '99999': 'Outros rendimentos'
}

# --- Funções de processamento ---


def obter_subpastas_competencias(pasta_base):
    """Obtém lista de subpastas de competências disponíveis"""
    competencias = []
    
    if not os.path.exists(pasta_base):
        return competencias
    
    for item in os.listdir(pasta_base):
        caminho_item = os.path.join(pasta_base, item)
        if os.path.isdir(caminho_item) and item.count('-') == 1:
            # Verifica se o formato é YYYY-MM
            try:
                ano, mes = item.split('-')
                if len(ano) == 4 and len(mes) == 2 and ano.isdigit() and mes.isdigit():
                    competencias.append(item)
            except:
                continue
    
    return sorted(competencias, reverse=True)


def obter_arquivos_xml_por_competencia(pasta_base, competencias_selecionadas=None):
    """Obtém lista de arquivos XML por competência"""
    arquivos_por_competencia = {}
    
    if not competencias_selecionadas:
        competencias_selecionadas = obter_subpastas_competencias(pasta_base)
    
    for competencia in competencias_selecionadas:
        pasta_competencia = os.path.join(pasta_base, competencia)
        if os.path.exists(pasta_competencia):
            arquivos = []
            for arquivo in os.listdir(pasta_competencia):
                if arquivo.lower().endswith('.xml') and 'REINF' in arquivo.upper():
                    arquivos.append(os.path.join(pasta_competencia, arquivo))
            
            if arquivos:
                arquivos_por_competencia[competencia] = arquivos
    
    return arquivos_por_competencia


def parse_reinf_4010_xml(file_path):
    """Processa um arquivo XML do REINF 4010"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Encontra o elemento evtRetPF
        evt = root.find('.//ns:evtRetPF', NS_REINF)
        if evt is None:
            return []

        # Extrai informações básicas
        ide_evento = evt.find('ns:ideEvento', NS_REINF)
        ide_contri = evt.find('ns:ideContri', NS_REINF)

        if ide_evento is None or ide_contri is None:
            return []

        per_apur = ide_evento.find('ns:perApur', NS_REINF).text if ide_evento.find(
            'ns:perApur', NS_REINF) is not None else None
        cnpj_contri = ide_contri.find('ns:nrInsc', NS_REINF).text if ide_contri.find(
            'ns:nrInsc', NS_REINF) is not None else None

        if not per_apur or not cnpj_contri:
            return []

        registros = []

        # Processa estabelecimentos
        for ide_estab in evt.findall('.//ns:ideEstab', NS_REINF):
            # Processa beneficiários
            for ide_benef in ide_estab.findall('ns:ideBenef', NS_REINF):
                cpf_benef = ide_benef.find('ns:cpfBenef', NS_REINF).text if ide_benef.find(
                    'ns:cpfBenef', NS_REINF) is not None else None

                # Processa pagamentos
                for ide_pgto in ide_benef.findall('ns:idePgto', NS_REINF):
                    nat_rend = ide_pgto.find('ns:natRend', NS_REINF).text if ide_pgto.find(
                        'ns:natRend', NS_REINF) is not None else None

                    # Processa informações de pagamento
                    for info_pgto in ide_pgto.findall('ns:infoPgto', NS_REINF):
                        dt_fg = info_pgto.find('ns:dtFG', NS_REINF).text if info_pgto.find(
                            'ns:dtFG', NS_REINF) is not None else None
                        comp_fp = info_pgto.find('ns:compFP', NS_REINF).text if info_pgto.find(
                            'ns:compFP', NS_REINF) is not None else None
                        vlr_rend_bruto = float(info_pgto.find('ns:vlrRendBruto', NS_REINF).text.replace(
                            ',', '.')) if info_pgto.find('ns:vlrRendBruto', NS_REINF) is not None else 0.0
                        observ = info_pgto.find('ns:observ', NS_REINF).text if info_pgto.find(
                            'ns:observ', NS_REINF) is not None else ''

                        # Processa rendimentos isentos
                        vlr_isento = 0.0
                        rend_isento = info_pgto.find('ns:rendIsento', NS_REINF)
                        if rend_isento is not None:
                            vlr_isento = float(rend_isento.find('ns:vlrIsento', NS_REINF).text.replace(
                                ',', '.')) if rend_isento.find('ns:vlrIsento', NS_REINF) is not None else 0.0

                        # Processa retenções (IRRF)
                        vlr_ret_ir = 0.0
                        ret_pgto = info_pgto.find('ns:retPgto', NS_REINF)
                        if ret_pgto is not None:
                            vlr_ret_ir = float(ret_pgto.find('ns:vlrRetIR', NS_REINF).text.replace(
                                ',', '.')) if ret_pgto.find('ns:vlrRetIR', NS_REINF) is not None else 0.0

                        registro = {
                            'perApur': per_apur,
                            'cpfBenef': cpf_benef or '',
                            'cpfBenefFormatado': format_cpf_completo(cpf_benef) if cpf_benef else 'N/A',
                            'natRend': nat_rend or '',
                            'natRendDesc': NATUREZAS_RENDIMENTO.get(nat_rend, f'Código {nat_rend}') if nat_rend else 'Não informado',
                            'dtFG': dt_fg or '',
                            'vlrRendBruto': vlr_rend_bruto,
                            'vlrIsento': vlr_isento,
                            'vlrRetIR': vlr_ret_ir,
                            'vlrLiquido': vlr_rend_bruto - vlr_ret_ir,
                            'observ': observ or '',
                            'arquivo': os.path.basename(file_path)  # Adiciona nome do arquivo
                        }

                        registros.append(registro)

        return registros

    except Exception as e:
        st.error(f"Erro ao processar {os.path.basename(file_path)}: {str(e)}")
        return []


def listar_cpfs_e_periodos(pasta_base, competencias_selecionadas=None):
    """Lista todos os CPFs e períodos encontrados nos arquivos REINF 4010"""
    cpfs = set()
    periodos = set()

    if not os.path.exists(pasta_base):
        st.error(f"Pasta não encontrada: {pasta_base}")
        return [], []

    arquivos_por_competencia = obter_arquivos_xml_por_competencia(pasta_base, competencias_selecionadas)
    
    for competencia, arquivos in arquivos_por_competencia.items():
        for arquivo in arquivos:
            try:
                dados = parse_reinf_4010_xml(arquivo)
                for registro in dados:
                    if registro.get('cpfBenef'):
                        cpfs.add(registro['cpfBenef'])
                    if registro.get('perApur'):
                        periodos.add(registro['perApur'])
            except Exception as e:
                continue

    return sorted(cpfs), sorted(periodos)


def processar_arquivos_xml(pasta_base, cpf_sel=None, periodos_sel=None, competencias_sel=None):
    """Processa todos os arquivos XML REINF 4010"""
    registros = []

    if not os.path.exists(pasta_base):
        st.error(f"Pasta não encontrada: {pasta_base}")
        return registros

    # Se não especificou competências, pega todas
    if not competencias_sel:
        competencias_sel = obter_subpastas_competencias(pasta_base)

    arquivos_por_competencia = obter_arquivos_xml_por_competencia(pasta_base, competencias_sel)
    
    for competencia, arquivos in arquivos_por_competencia.items():
        for arquivo in arquivos:
            dados = parse_reinf_4010_xml(arquivo)

            # Filtra por CPF se especificado
            if cpf_sel:
                dados = [r for r in dados if r.get("cpfBenef") == cpf_sel]

            # Filtra por períodos se especificado
            if periodos_sel:
                # Garante que periodos_sel seja uma lista
                if isinstance(periodos_sel, str):
                    periodos_sel = [periodos_sel]
                dados = [r for r in dados if r.get("perApur") in periodos_sel]

            registros.extend(dados)

    return registros


def create_download_link_csv(df, filename):
    """Cria um link para download do CSV"""
    csv = df.to_csv(index=False, encoding='utf-8-sig', sep=';')
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Download CSV</a>'


# --- Interface principal ---

def main_interface():
    """Interface principal do aplicativo"""
    st.title("💰 REINF 4010 - Pagamentos a Pessoa Física")

    # Verifica se a pasta existe
    if not os.path.exists(PASTA_BASE):
        st.error(f"""
        ❌ **Pasta não encontrada!**
        
        Caminho procurado: `{PASTA_BASE}`
        
        Por favor, verifique se:
        1. A pasta existe
        2. O caminho está correto
        3. Você tem permissão de acesso
        """)
        return

    # Mostra informações sobre as competências disponíveis
    competencias_disponiveis = obter_subpastas_competencias(PASTA_BASE)
    
    if not competencias_disponiveis:
        st.warning("⚠️ Nenhuma subpasta de competência encontrada.")
        st.info("Certifique-se de que existem subpastas no formato YYYY-MM (ex: 2025-01, 2025-02)")
        return

    st.success(f"✅ Encontradas {len(competencias_disponiveis)} competências: {', '.join(competencias_disponiveis)}")

    # Sidebar
    with st.sidebar:
        if st.button("🏠 Voltar"):
            voltar_pagina_principal()

        st.markdown("---")
        st.subheader("📅 Filtrar Competências")
        
        competencias_sel = st.multiselect(
            "Selecionar competências:",
            options=competencias_disponiveis,
            default=competencias_disponiveis[:3] if len(competencias_disponiveis) >= 3 else competencias_disponiveis,
            help="Selecione as competências que deseja analisar"
        )
        
        if not competencias_sel:
            st.warning("⚠️ Selecione pelo menos uma competência")
            return

        st.markdown("---")
        tipo_consulta = st.radio(
            "Tipo de Consulta:",
            ["👤 Individual", "📊 Consolidado", "📄 Relatório"],
            key="tipo_consulta"
        )

    if tipo_consulta == "👤 Individual":
        show_consulta_individual(competencias_sel)
    elif tipo_consulta == "📊 Consolidado":
        show_consulta_geral(competencias_sel)
    else:
        show_relatorio_exportavel(competencias_sel)


def show_consulta_individual(competencias_sel):
    """Consulta individual por CPF"""
    st.header("👤 Consulta Individual")

    with st.spinner("Carregando dados..."):
        cpfs, periodos = listar_cpfs_e_periodos(PASTA_BASE, competencias_sel)

    if not cpfs:
        st.warning("Nenhum dado encontrado para as competências selecionadas.")
        return

    # Seleção de CPF
    cpf_sel = criar_interface_cpf_pesquisavel(cpfs)

    if cpf_sel:
        # Seleção de períodos
        periodos_cpf_data = processar_arquivos_xml(PASTA_BASE, cpf_sel, competencias_sel=competencias_sel)
        if periodos_cpf_data:
            periodos_cpf = sorted(
                list(set([r['perApur'] for r in periodos_cpf_data])), reverse=True)
            periodo_sel = st.selectbox("Período:", ["Todos"] + periodos_cpf)

            if periodo_sel != "Todos":
                dados = [r for r in periodos_cpf_data if r['perApur']
                         == periodo_sel]
            else:
                dados = periodos_cpf_data

            mostrar_resultados_individual(dados, cpf_sel)


def mostrar_resultados_individual(registros, cpf_sel):
    """Mostra resultados da consulta individual"""
    if not registros:
        st.warning("Nenhum pagamento encontrado.")
        return

    # Métricas
    col1, col2, col3 = st.columns(3)

    total_bruto = sum(r['vlrRendBruto'] for r in registros)
    total_ir = sum(r['vlrRetIR'] for r in registros)
    total_liquido = sum(r['vlrLiquido'] for r in registros)

    with col1:
        st.metric("💰 Total Bruto", f"R$ {format_value(total_bruto)}")
    with col2:
        st.metric("🏛️ IR Retido", f"R$ {format_value(total_ir)}")
    with col3:
        st.metric("💵 Total Líquido", f"R$ {format_value(total_liquido)}")

    # Tabela
    df = pd.DataFrame(registros)
    df_display = df[['perApur', 'natRendDesc', 'dtFG',
                     'vlrRendBruto', 'vlrRetIR', 'vlrLiquido', 'arquivo']].copy()
    df_display.columns = ['Período', 'Natureza', 'Data',
                          'Valor Bruto', 'IR Retido', 'Valor Líquido', 'Arquivo']

    # Formatar valores para exibição
    for col in ['Valor Bruto', 'IR Retido', 'Valor Líquido']:
        df_display[col] = df_display[col].apply(
            lambda x: f"R$ {format_value(x)}")

    st.dataframe(df_display, use_container_width=True, hide_index=True)


def show_consulta_geral(competencias_sel):
    """Consulta geral consolidada"""
    st.header("📊 Consulta Consolidada")

    with st.spinner("Processando dados..."):
        registros = processar_arquivos_xml(PASTA_BASE, competencias_sel=competencias_sel)

    if not registros:
        st.warning("Nenhum dado encontrado para as competências selecionadas.")
        return

    # Filtros
    periodos = sorted(list(set([r['perApur']
                      for r in registros])), reverse=True)
    periodo_sel = st.selectbox("Período:", ["Todos"] + periodos)

    if periodo_sel != "Todos":
        registros = [r for r in registros if r['perApur'] == periodo_sel]

    # Métricas gerais
    col1, col2, col3, col4 = st.columns(4)

    total_beneficiarios = len(set([r['cpfBenef'] for r in registros]))
    total_pagamentos = len(registros)
    total_valor = sum(r['vlrRendBruto'] for r in registros)
    competencias_processadas = len(competencias_sel)

    with col1:
        st.metric("👥 Beneficiários", total_beneficiarios)
    with col2:
        st.metric("📄 Pagamentos", total_pagamentos)
    with col3:
        st.metric("💰 Total", f"R$ {format_value(total_valor)}")
    with col4:
        st.metric("📅 Competências", competencias_processadas)

    # Consolidado por natureza
    df = pd.DataFrame(registros)
    consolidado = df.groupby('natRendDesc').agg({
        'cpfBenef': 'nunique',
        'vlrRendBruto': ['count', 'sum']
    }).round(2)

    consolidado.columns = ['Beneficiários', 'Pagamentos', 'Total']
    consolidado['Total'] = consolidado['Total'].apply(
        lambda x: f"R$ {format_value(x)}")

    st.dataframe(consolidado, use_container_width=True)


def show_relatorio_exportavel(competencias_sel):
    """Relatório exportável"""
    st.header("📄 Relatório de Pagamentos")

    # Processa dados
    with st.spinner("Gerando relatório..."):
        registros = processar_arquivos_xml(PASTA_BASE, competencias_sel=competencias_sel)

    if not registros:
        st.warning("Nenhum pagamento encontrado para as competências selecionadas.")
        return

    # Filtros adicionais
    st.subheader("🔍 Filtros Adicionais")
    
    periodos_disponiveis = sorted(list(set([r['perApur'] for r in registros])), reverse=True)
    periodos_sel = st.multiselect(
        "Períodos específicos (opcional):",
        options=periodos_disponiveis,
        help="Deixe vazio para incluir todos os períodos das competências selecionadas"
    )

    # Aplica filtro de período se selecionado
    if periodos_sel:
        registros = [r for r in registros if r['perApur'] in periodos_sel]

    if not registros:
        st.warning("Nenhum pagamento encontrado para os filtros selecionados.")
        return

    # Prepara DataFrame do relatório
    df_relatorio = pd.DataFrame(registros)

    # Cria relatório final
    df_final = df_relatorio[['cpfBenef', 'vlrRendBruto', 'natRendDesc', 'perApur', 'arquivo']].copy()
    df_final.columns = ['CPF', 'Valor Pago', 'Natureza de Rendimento', 'Período', 'Arquivo']

    # Formata CPFs completos
    df_final['CPF'] = df_final['CPF'].apply(format_cpf_completo)

    # Ordena por valor
    df_final = df_final.sort_values('Valor Pago', ascending=False)

    # Formata valores para exibição
    df_display = df_final.copy()
    df_display['Valor Pago'] = df_display['Valor Pago'].apply(
        lambda x: f"R$ {format_value(x)}")

    # Estatísticas do relatório
    st.subheader("📊 Resumo")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("👥 CPFs", df_final['CPF'].nunique())
    with col2:
        st.metric("📄 Pagamentos", len(df_final))
    with col3:
        st.metric("💰 Total", f"R$ {format_value(df_final['Valor Pago'].sum())}")
    with col4:
        st.metric("📅 Competências", len(competencias_sel))

    # Resumo por competência
    st.subheader("📅 Por Competência")
    
    competencia_periodo = df_relatorio['perApur'].apply(lambda x: x[:7]).value_counts().sort_index(ascending=False)
    competencia_df = pd.DataFrame({
        'Competência': competencia_periodo.index,
        'Qtd Pagamentos': competencia_periodo.values,
        'Total Pago': [df_relatorio[df_relatorio['perApur'].str.startswith(comp)]['vlrRendBruto'].sum() 
                       for comp in competencia_periodo.index]
    })
    competencia_df['Total Pago'] = competencia_df['Total Pago'].apply(lambda x: f"R$ {format_value(x)}")
    
    st.dataframe(competencia_df, use_container_width=True, hide_index=True)

    # Resumo por natureza
    st.subheader("📈 Por Natureza de Rendimento")

    resumo_natureza = df_final.groupby('Natureza de Rendimento').agg({
        'CPF': 'nunique',
        'Valor Pago': ['count', 'sum']
    }).round(2)

    resumo_natureza.columns = ['CPFs Únicos', 'Qtd Pagamentos', 'Total Pago']
    resumo_natureza['Total Pago'] = resumo_natureza['Total Pago'].apply(
        lambda x: f"R$ {format_value(x)}")
    resumo_natureza = resumo_natureza.sort_values(
        'Qtd Pagamentos', ascending=False)

    st.dataframe(resumo_natureza, use_container_width=True)

    # Relatório detalhado
    st.subheader("📋 Relatório Detalhado")

    # Limita exibição na tela
    limite_exibicao = st.slider("Registros na tela:", 50, 500, 100, 50)
    st.dataframe(df_display.head(limite_exibicao),
                 use_container_width=True, hide_index=True)

    if len(df_display) > limite_exibicao:
        st.info(
            f"Mostrando {limite_exibicao} de {len(df_display)} registros. Use o download para ver todos.")

    # Downloads
    st.subheader("📥 Downloads")

    col1, col2 = st.columns(2)

    with col1:
        # Relatório completo
        df_export = df_final.copy()
        df_export['Valor Pago'] = df_export['Valor Pago'].apply(
            lambda x: f"{x:.2f}".replace('.', ','))

        filename_completo = f"REINF_4010_Detalhado_{'_'.join(competencias_sel).replace('-', '')}.csv"
        st.markdown(
            create_download_link_csv(df_export, filename_completo),
            unsafe_allow_html=True
        )
        st.caption("Relatório completo detalhado")

    with col2:
        # Resumo por natureza
        resumo_export = resumo_natureza.copy()
        resumo_export['Total Pago'] = df_final.groupby('Natureza de Rendimento')[
            'Valor Pago'].sum().apply(lambda x: f"{x:.2f}".replace('.', ','))

        filename_resumo = f"REINF_4010_Resumo_{'_'.join(competencias_sel).replace('-', '')}.csv"
        st.markdown(
            create_download_link_csv(resumo_export, filename_resumo),
            unsafe_allow_html=True
        )
        st.caption("Resumo por natureza")


# --- Ponto de entrada ---
if __name__ == "__main__":
    try:
        main_interface()
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        st.exception(e)