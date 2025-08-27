import streamlit as st
import os
import pandas as pd
import io
from datetime import datetime
import base64
import locale
import sys
import json
import pickle
import hashlib
from pathlib import Path
from functools import lru_cache

# Importação da FPDF com tratamento de erro
try:
    from fpdf import FPDF
except ImportError:
    st.error("Biblioteca FPDF não encontrada. Instale com: pip install fpdf2")
    FPDF = None

# Configuração da página
st.set_page_config(
    page_title="S-5002 - Informe de Imposto (Otimizado)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração do parser XML
try:
    from lxml import etree
    USAR_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree
    USAR_LXML = False

# --- Configuração inicial ---
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except:
        pass

# Namespaces possíveis para S-5002
NAMESPACES_S5002 = {
    'ns1': 'http://www.esocial.gov.br/schema/evt/evtIrrfBenef/v_S_01_03_00',
    'ns2': 'http://www.esocial.gov.br/schema/evt/evtIrrfBenef/v_S_01_02_00',
    'ns3': 'http://www.esocial.gov.br/schema/evt/evtIrrfBenef/v_S_01_01_00',
    'ns4': 'http://www.esocial.gov.br/schema/evt/evtIrrfBenef/v02_05_00',
    'ns5': 'http://www.esocial.gov.br/schema/evt/evtIrrfBenef/v02_04_02'
}

# Caminhos (ajuste conforme necessário)
PASTA_BASE = r"C:\Users\tst\OneDrive\Área de Trabalho\Meus Phytons\.vscode\pages\Eventos_eSocial"
ARQUIVO_CODIGOS = r"C:\Users\tst\OneDrive\Área de Trabalho\Meus Phytons\codigos_s5002.json"
ARQUIVO_MAPEAMENTO = r"C:\Users\tst\OneDrive\Área de Trabalho\Meus Phytons\mapeamento_in2060.json"

# Arquivos de cache
CACHE_XMLS = Path("cache_s5002_xmls.pkl")
CACHE_INDICE = Path("cache_s5002_indice.pkl")
CACHE_VERSAO = "2.4"

# --- Estrutura do Comprovante IN 2060/2021 ---
CAMPOS_COMPROVANTE_IN2060 = {
    "quadro3": {
        "nome": "Quadro 3 - Rendimentos Tributáveis, Deduções e Imposto sobre a Renda Retido na Fonte (IRRF)",
        "linhas": {
            "linha1": "Total dos rendimentos tributáveis (inclusive férias e décimo terceiro salário)",
            "linha2": "Dedução: Contribuição à Previdência Oficial",
            "linha3": "Dedução: Contribuição a entidades de previdência complementar",
            "linha4": "Dedução: Pensão alimentícia",
            "linha5": "Imposto sobre a Renda Retido na Fonte (IRRF)",
            "linha6": "Rendimentos isentos de pensão, proventos de aposentadoria ou reforma por moléstia grave"
        }
    },
    "quadro4": {
        "nome": "Quadro 4 - Rendimentos Isentos e Não-Tributáveis",
        "linhas": {
            "linha1": "Parcela isenta dos proventos de aposentadoria (65 anos ou mais), exceto 13º",
            "linha2": "Parcela isenta do 13º salário (65 anos ou mais)",
            "linha3": "Diárias",
            "linha4": "Pensão e proventos por moléstia grave ou acidente em serviço",
            "linha5": "Outros rendimentos isentos e não-tributáveis"
        }
    },
    "quadro5": {
        "nome": "Quadro 5 - Rendimentos Sujeitos à Tributação Exclusiva",
        "linhas": {
            "linha1": "Décimo terceiro salário",
            "linha2": "Imposto sobre a Renda Retido na Fonte sobre 13º salário",
            "linha3": "Participação nos Lucros ou Resultados (PLR)",
            "linha4": "Imposto sobre a Renda Retido na Fonte sobre PLR",
            "linha5": "Outros rendimentos sujeitos à tributação exclusiva"
        }
    },
    "quadro6": {
        "nome": "Quadro 6 - Rendimentos Recebidos Acumuladamente (RRA)",
        "linhas": {
            "linha1": "Total dos rendimentos tributáveis (RRA)",
            "linha2": "Dedução: Contribuição à Previdência Oficial (RRA)",
            "linha3": "Dedução: Contribuição a entidades de previdência complementar (RRA)",
            "linha4": "Dedução: Pensão alimentícia (RRA)",
            "linha5": "Imposto sobre a Renda Retido na Fonte (RRA)"
        }
    },
    "quadro7": {
        "nome": "Quadro 7 - Informações Complementares",
        "linhas": {
            "linha1": "Rendimentos com exigibilidade suspensa",
            "linha2": "Depósitos judiciais",
            "linha3": "Outras informações"
        }
    }
}

# --- Mapeamento Padrão Sugerido ---
MAPEAMENTO_PADRAO_SUGERIDO = {
    # Quadro 3 - Rendimentos Tributáveis
    "11": ("quadro3", "linha1"),  # Remuneração mensal
    "31": ("quadro3", "linha1"),  # Remuneração mensal
    "91": ("quadro3", "linha1"),  # Remuneração mensal
    "12": ("quadro5", "linha1"),  # 13º salário
    "32": ("quadro5", "linha1"),  # 13º salário
    "92": ("quadro5", "linha1"),  # 13º salário
    "13": ("quadro3", "linha1"),  # Férias
    "33": ("quadro3", "linha1"),  # Férias
    "93": ("quadro3", "linha1"),  # Férias
    "14": ("quadro5", "linha3"),  # PLR
    "34": ("quadro5", "linha3"),  # PLR
    "94": ("quadro5", "linha3"),  # PLR
    
    # Deduções Previdenciárias
    "41": ("quadro3", "linha2"),  # PSO Remuneração
    "42": ("quadro5", "linha2"),  # PSO 13º
    "43": ("quadro3", "linha2"),  # PSO Férias
    "46": ("quadro3", "linha3"),  # Previdência privada mensal
    "47": ("quadro3", "linha3"),  # Previdência privada 13º
    "48": ("quadro3", "linha3"),  # Previdência privada férias
    
    # Pensão Alimentícia
    "51": ("quadro3", "linha4"),  # Pensão alimentícia mensal
    "52": ("quadro3", "linha4"),  # Pensão alimentícia 13º
    "53": ("quadro3", "linha4"),  # Pensão alimentícia férias
    "54": ("quadro3", "linha4"),  # Pensão alimentícia PLR
    
    # Isenções para maiores de 65 anos
    "70": ("quadro4", "linha1"),  # Parcela isenta 65 anos mensal
    "71": ("quadro4", "linha2"),  # Parcela isenta 65 anos 13º
    
    # Isenções diversas
    "72": ("quadro4", "linha3"),  # Diárias
    "73": ("quadro4", "linha5"),  # Ajuda de custo
    "74": ("quadro4", "linha5"),  # Indenizações
    "75": ("quadro4", "linha5"),  # Abono pecuniário
    "76": ("quadro4", "linha4"),  # Moléstia grave mensal
    "77": ("quadro4", "linha4"),  # Moléstia grave 13º
    "78": ("quadro4", "linha5"),  # MEI/EPP
    "79": ("quadro4", "linha5"),  # Outras isenções
    
    # Não tributáveis
    "0": ("quadro4", "linha5"),   # Rendimento não tributável
    "1": ("quadro4", "linha5"),   # Não tributável por acordos internacionais
    "9": ("quadro7", "linha3"),   # Verbas diversas
    
    # RRA
    "15": ("quadro6", "linha1"),  # RRA
    "35": ("quadro6", "linha1"),  # RRA
    "95": ("quadro6", "linha1"),  # RRA
    
    # Depósitos judiciais
    "81": ("quadro7", "linha2"),  # Depósito judicial
    "82": ("quadro7", "linha2"),  # Compensação judicial ano-calendário
    "83": ("quadro7", "linha2"),  # Compensação judicial anos anteriores
}

# --- Funções auxiliares ---
def voltar_pagina_principal():
    st.switch_page("main.py")

def format_value(val):
    """Formata valores monetários"""
    try:
        return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return val

def filtrar_cpfs(cpfs, termo_busca):
    """Filtra CPFs baseado no termo de busca"""
    if not termo_busca:
        return cpfs
    return [cpf for cpf in cpfs if termo_busca.replace(".", "").replace("-", "") in cpf.replace(".", "").replace("-", "")]

def mapear_codigo_corrigido(codigo):
    """Mapeia códigos inválidos conhecidos para códigos válidos"""
    mapeamento_correcoes = {
        '011': '11',   # Remove zero à esquerda
        '341': '34',   # Possível erro de digitação
        '431': '43',   # Possível erro de digitação
        '179': '79',   # Possível erro de digitação
    }
    return mapeamento_correcoes.get(codigo, codigo)

def get_descricao_codigo_melhorada(codigos_dict, codigo, tipo_codigo="Código"):
    """Versão melhorada que trata códigos inválidos conhecidos"""
    if not codigo:
        return f'{tipo_codigo} não informado'
    
    codigo_str = str(codigo).strip()
    
    # Primeiro tenta busca direta
    if codigo_str in codigos_dict:
        return codigos_dict[codigo_str]
    
    # Tenta código corrigido se não encontrou
    codigo_corrigido = mapear_codigo_corrigido(codigo_str)
    if codigo_corrigido != codigo_str and codigo_corrigido in codigos_dict:
        return f"{codigos_dict[codigo_corrigido]} (código original: {codigo_str})"
    
    # Remove zeros à esquerda
    codigo_sem_zeros = codigo_str.lstrip('0')
    if codigo_sem_zeros and codigo_sem_zeros in codigos_dict:
        return f"{codigos_dict[codigo_sem_zeros]} (código: {codigo_str})"
    
    # Se não encontrou, retorna erro informativo
    return f'Código {codigo_str} não catalogado no sistema'

@lru_cache(maxsize=1)
def carregar_codigos_s5002():
    """Carrega os códigos de descrição do arquivo JSON com cache"""
    try:
        if os.path.exists(ARQUIVO_CODIGOS):
            with open(ARQUIVO_CODIGOS, 'r', encoding='utf-8') as arquivo:
                return json.load(arquivo)
        else:
            st.warning(f"Arquivo de códigos não encontrado: {ARQUIVO_CODIGOS}")
            return {"TPInfoIR": {}, "CodCateg": {}, "TPDep": {}}
    except Exception as e:
        st.error(f"Erro ao carregar códigos: {str(e)}")
        return {"TPInfoIR": {}, "CodCateg": {}, "TPDep": {}}

def carregar_mapeamento_personalizado():
    """Carrega mapeamento personalizado salvo pelo usuário"""
    try:
        if os.path.exists(ARQUIVO_MAPEAMENTO):
            with open(ARQUIVO_MAPEAMENTO, 'r', encoding='utf-8') as arquivo:
                return json.load(arquivo)
        else:
            return MAPEAMENTO_PADRAO_SUGERIDO.copy()
    except Exception as e:
        st.warning(f"Erro ao carregar mapeamento personalizado: {e}")
        return MAPEAMENTO_PADRAO_SUGERIDO.copy()

# --- Sistema de Cache ---
def get_file_hash(file_path):
    """Gera hash do arquivo para detectar mudanças"""
    try:
        return hashlib.md5(Path(file_path).read_bytes()).hexdigest()
    except:
        return None

def carregar_cache():
    """Carrega cache existente ou cria novo"""
    if CACHE_XMLS.exists():
        try:
            with open(CACHE_XMLS, 'rb') as f:
                cache = pickle.load(f)
                if cache.get('versao') == CACHE_VERSAO:
                    return cache.get('dados', {})
        except:
            pass
    return {}

def salvar_cache(cache_dados):
    """Salva cache em disco"""
    try:
        cache = {
            'versao': CACHE_VERSAO,
            'dados': cache_dados,
            'timestamp': datetime.now()
        }
        with open(CACHE_XMLS, 'wb') as f:
            pickle.dump(cache, f)
    except Exception as e:
        st.warning(f"Erro ao salvar cache: {e}")

def carregar_indice_cpfs():
    """Carrega índice de CPFs ou cria novo"""
    if CACHE_INDICE.exists():
        try:
            with open(CACHE_INDICE, 'rb') as f:
                indice = pickle.load(f)
                if indice.get('versao') == CACHE_VERSAO:
                    return indice.get('dados', {})
        except:
            pass
    return {}

def salvar_indice_cpfs(indice_dados):
    """Salva índice de CPFs"""
    try:
        indice = {
            'versao': CACHE_VERSAO,
            'dados': indice_dados,
            'timestamp': datetime.now()
        }
        with open(CACHE_INDICE, 'wb') as f:
            pickle.dump(indice, f)
    except Exception as e:
        st.warning(f"Erro ao salvar índice: {e}")

# --- Parser XML Otimizado ---
def parse_xml_rapido(file_path):
    """Parser mais rápido e seguro usando lxml se disponível"""
    try:
        file_path = Path(file_path)
        
        if USAR_LXML:
            parser = etree.XMLParser(
                recover=True, 
                huge_tree=True,
                strip_cdata=False,
                resolve_entities=False,
                load_dtd=False,
                no_network=True
            )
            
            with open(file_path, 'rb') as f:
                xml_content = f.read()
            
            return etree.fromstring(xml_content, parser)
        else:
            import xml.etree.ElementTree as ET
            
            encodings = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    return ET.fromstring(content)
                except (UnicodeDecodeError, ET.ParseError):
                    continue
            
            tree = ET.parse(str(file_path))
            return tree.getroot()
            
    except Exception as e:
        st.warning(f"Erro no parser XML para {file_path.name}: {str(e)}")
        return None

def detectar_namespace_s5002(root):
    """Detecta o namespace correto para S-5002 no XML"""
    if root is None:
        return None, None
        
    for ns_name, ns_uri in NAMESPACES_S5002.items():
        ns_dict = {ns_name: ns_uri}
        evt = root.find(f'.//{ns_name}:evtIrrfBenef', ns_dict)
        if evt is not None:
            return ns_dict, ns_name

    for elem in root.iter():
        if elem.tag.endswith('evtIrrfBenef'):
            if '}' in elem.tag:
                namespace_uri = elem.tag.split('}')[0][1:]
                return {'ns': namespace_uri}, 'ns'

    return None, None

def verificar_arquivo_s5002_rapido(file_path):
    """Verificação rápida se o arquivo é S-5002"""
    try:
        file_path = Path(file_path)
        
        if 'S-5002' in file_path.name.upper():
            return True

        encodings = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    primeiras_linhas = f.read(2048)
                    return 'evtIrrfBenef' in primeiras_linhas or 'S-5002' in primeiras_linhas
            except UnicodeDecodeError:
                continue
                
        return False
    except Exception:
        return False

def extrair_cpf_rapido(file_path):
    """Extrai apenas o CPF do arquivo XML"""
    try:
        if not verificar_arquivo_s5002_rapido(file_path):
            return None

        root = parse_xml_rapido(file_path)
        if root is None:
            return None

        ns_dict, ns_prefix = detectar_namespace_s5002(root)
        if not ns_dict:
            return None

        ide_trab = root.find(f'.//{ns_prefix}:ideTrabalhador', ns_dict)
        if ide_trab is None:
            return None

        cpf_elem = ide_trab.find(f'{ns_prefix}:cpfBenef', ns_dict)
        if cpf_elem is None:
            return None

        return cpf_elem.text

    except Exception as e:
        st.warning(f"Erro ao extrair CPF de {Path(file_path).name}: {str(e)}")
        return None

def processar_xml_completo(file_path):
    """Processa arquivo XML completo com tratamento melhorado de códigos"""
    try:
        codigos = carregar_codigos_s5002()

        root = parse_xml_rapido(file_path)
        if root is None:
            return None

        ns_dict, ns_prefix = detectar_namespace_s5002(root)
        if not ns_dict:
            return None

        evt = root.find(f'.//{ns_prefix}:evtIrrfBenef', ns_dict)
        if evt is None:
            return None

        ide_evento = evt.find(f'{ns_prefix}:ideEvento', ns_dict)
        ide_empregador = evt.find(f'{ns_prefix}:ideEmpregador', ns_dict)
        ide_trabalhador = evt.find(f'{ns_prefix}:ideTrabalhador', ns_dict)

        dados = {
            'arquivo': Path(file_path).name,
            'nrRecArqBase': ide_evento.find(f'{ns_prefix}:nrRecArqBase', ns_dict).text if ide_evento and ide_evento.find(f'{ns_prefix}:nrRecArqBase', ns_dict) is not None else '',
            'perApur': ide_evento.find(f'{ns_prefix}:perApur', ns_dict).text if ide_evento and ide_evento.find(f'{ns_prefix}:perApur', ns_dict) is not None else '',
            'tpInsc': ide_empregador.find(f'{ns_prefix}:tpInsc', ns_dict).text if ide_empregador and ide_empregador.find(f'{ns_prefix}:tpInsc', ns_dict) is not None else '',
            'nrInsc': ide_empregador.find(f'{ns_prefix}:nrInsc', ns_dict).text if ide_empregador and ide_empregador.find(f'{ns_prefix}:nrInsc', ns_dict) is not None else '',
            'cpfBenef': ide_trabalhador.find(f'{ns_prefix}:cpfBenef', ns_dict).text if ide_trabalhador and ide_trabalhador.find(f'{ns_prefix}:cpfBenef', ns_dict) is not None else '',
            'pagamentos': [],
            'dependentes': [],
            'deducoes_dependentes': []
        }

        if ide_trabalhador is not None:
            for dm_dev in ide_trabalhador.findall(f'{ns_prefix}:dmDev', ns_dict):
                cod_categ_elem = dm_dev.find(f'{ns_prefix}:codCateg', ns_dict)
                cod_categ = cod_categ_elem.text if cod_categ_elem is not None else ''
                per_ref = dm_dev.find(f'{ns_prefix}:perRef', ns_dict).text if dm_dev.find(f'{ns_prefix}:perRef', ns_dict) is not None else ''
                
                pagamento = {
                    'perRef': per_ref,
                    'ideDmDev': dm_dev.find(f'{ns_prefix}:ideDmDev', ns_dict).text if dm_dev.find(f'{ns_prefix}:ideDmDev', ns_dict) is not None else '',
                    'tpPgto': dm_dev.find(f'{ns_prefix}:tpPgto', ns_dict).text if dm_dev.find(f'{ns_prefix}:tpPgto', ns_dict) is not None else '',
                    'dtPgto': dm_dev.find(f'{ns_prefix}:dtPgto', ns_dict).text if dm_dev.find(f'{ns_prefix}:dtPgto', ns_dict) is not None else '',
                    'codCateg': cod_categ,
                    'codCategDesc': get_descricao_codigo_melhorada(codigos['CodCateg'], cod_categ, 'CodCateg'),
                    'infoIR': [],
                    'totApurMen': {},
                    'dependentes': [],  # Dependentes específicos deste pagamento
                    'deducoes_dependentes': []  # Deduções específicas deste pagamento
                }

                # Informações de IR com tratamento melhorado
                for info_ir in dm_dev.findall(f'{ns_prefix}:infoIR', ns_dict):
                    tp_info_ir_elem = info_ir.find(f'{ns_prefix}:tpInfoIR', ns_dict)
                    tp_info_ir = tp_info_ir_elem.text if tp_info_ir_elem is not None else ''

                    pagamento['infoIR'].append({
                        'tpInfoIR': tp_info_ir,
                        'tpInfoIRDesc': get_descricao_codigo_melhorada(codigos['TPInfoIR'], tp_info_ir, 'TPInfoIR'),
                        'valor': float(info_ir.find(f'{ns_prefix}:valor', ns_dict).text) if info_ir.find(f'{ns_prefix}:valor', ns_dict) is not None else 0.0,
                        'descRendimento': info_ir.find(f'{ns_prefix}:descRendimento', ns_dict).text if info_ir.find(f'{ns_prefix}:descRendimento', ns_dict) is not None else ''
                    })

                # Totalização mensal
                tot_apur_men = dm_dev.find(f'{ns_prefix}:totApurMen', ns_dict)
                if tot_apur_men is not None:
                    pagamento['totApurMen'] = {
                        'CRMen': tot_apur_men.find(f'{ns_prefix}:CRMen', ns_dict).text if tot_apur_men.find(f'{ns_prefix}:CRMen', ns_dict) is not None else '',
                        'vlrRendTrib': float(tot_apur_men.find(f'{ns_prefix}:vlrRendTrib', ns_dict).text) if tot_apur_men.find(f'{ns_prefix}:vlrRendTrib', ns_dict) is not None else 0.0,
                        'vlrPrevOficial': float(tot_apur_men.find(f'{ns_prefix}:vlrPrevOficial', ns_dict).text) if tot_apur_men.find(f'{ns_prefix}:vlrPrevOficial', ns_dict) is not None else 0.0,
                        'vlrCRMen': float(tot_apur_men.find(f'{ns_prefix}:vlrCRMen', ns_dict).text) if tot_apur_men.find(f'{ns_prefix}:vlrCRMen', ns_dict) is not None else 0.0,
                        'vlrIsenOutros': float(tot_apur_men.find(f'{ns_prefix}:vlrIsenOutros', ns_dict).text) if tot_apur_men.find(f'{ns_prefix}:vlrIsenOutros', ns_dict) is not None else 0.0,
                        'descRendimento': tot_apur_men.find(f'{ns_prefix}:descRendimento', ns_dict).text if tot_apur_men.find(f'{ns_prefix}:descRendimento', ns_dict) is not None else ''
                    }

                # Processamento de dependentes por pagamento (dentro de dm_dev)
                info_complem = dm_dev.find(f'{ns_prefix}:infoIRComplem', ns_dict)
                if info_complem is not None:
                    for ide_dep in info_complem.findall(f'{ns_prefix}:ideDep', ns_dict):
                        tp_dep_elem = ide_dep.find(f'{ns_prefix}:tpDep', ns_dict)
                        tp_dep = tp_dep_elem.text if tp_dep_elem is not None else ''

                        pagamento['dependentes'].append({
                            'cpfDep': ide_dep.find(f'{ns_prefix}:cpfDep', ns_dict).text if ide_dep.find(f'{ns_prefix}:cpfDep', ns_dict) is not None else '',
                            'depIRRF': ide_dep.find(f'{ns_prefix}:depIRRF', ns_dict).text if ide_dep.find(f'{ns_prefix}:depIRRF', ns_dict) is not None else '',
                            'dtNascto': ide_dep.find(f'{ns_prefix}:dtNascto', ns_dict).text if ide_dep.find(f'{ns_prefix}:dtNascto', ns_dict) is not None else '',
                            'nome': ide_dep.find(f'{ns_prefix}:nome', ns_dict).text if ide_dep.find(f'{ns_prefix}:nome', ns_dict) is not None else '',
                            'tpDep': tp_dep,
                            'tpDepDesc': get_descricao_codigo_melhorada(codigos['TPDep'], tp_dep, 'TPDep'),
                            'perRef': per_ref  # Associa dependente ao período
                        })

                    # Deduções por dependente deste pagamento
                    for info_ircr in info_complem.findall(f'{ns_prefix}:infoIRCR', ns_dict):
                        for ded_depen in info_ircr.findall(f'{ns_prefix}:dedDepen', ns_dict):
                            pagamento['deducoes_dependentes'].append({
                                'tpRend': ded_depen.find(f'{ns_prefix}:tpRend', ns_dict).text if ded_depen.find(f'{ns_prefix}:tpRend', ns_dict) is not None else '',
                                'cpfDep': ded_depen.find(f'{ns_prefix}:cpfDep', ns_dict).text if ded_depen.find(f'{ns_prefix}:cpfDep', ns_dict) is not None else '',
                                'vlrDedDep': float(ded_depen.find(f'{ns_prefix}:vlrDedDep', ns_dict).text) if ded_depen.find(f'{ns_prefix}:vlrDedDep', ns_dict) is not None else 0.0,
                                'perRef': per_ref  # Associa dedução ao período
                            })

                dados['pagamentos'].append(pagamento)

            # Consolida dependentes globalmente (para compatibilidade com código anterior)
            for pagamento in dados['pagamentos']:
                dados['dependentes'].extend(pagamento['dependentes'])
                dados['deducoes_dependentes'].extend(pagamento['deducoes_dependentes'])

        return dados

    except Exception as e:
        st.warning(f"Erro ao processar {Path(file_path).name}: {str(e)}")
        return None

# --- Funções de Indexação ---
def criar_indice_cpfs_otimizado():
    """Cria índice otimizado de CPFs para arquivos"""
    indice_cache = carregar_indice_cpfs()
    if indice_cache:
        return indice_cache

    indice = {}
    
    try:
        arquivos_xml = [f for f in os.listdir(PASTA_BASE) if f.lower().endswith('.xml')]
    except Exception as e:
        st.error(f"Erro ao acessar pasta {PASTA_BASE}: {e}")
        return indice

    if not arquivos_xml:
        st.warning("Nenhum arquivo XML encontrado na pasta especificada.")
        return indice

    progress_bar = st.progress(0)
    status_text = st.empty()

    total_arquivos = len(arquivos_xml)
    processados_com_sucesso = 0
    erros = 0

    for i, arquivo in enumerate(arquivos_xml):
        file_path = os.path.join(PASTA_BASE, arquivo)

        try:
            cpf = extrair_cpf_rapido(file_path)

            if cpf:
                if cpf not in indice:
                    indice[cpf] = []
                indice[cpf].append(arquivo)
                processados_com_sucesso += 1
            else:
                erros += 1

        except Exception as e:
            erros += 1
            st.warning(f"Erro ao processar {arquivo}: {str(e)}")

        progress = (i + 1) / total_arquivos
        progress_bar.progress(progress)
        status_text.text(f"Indexando arquivos: {i + 1}/{total_arquivos} (Sucessos: {processados_com_sucesso}, Erros: {erros})")

    progress_bar.empty()
    status_text.empty()

    if indice:
        salvar_indice_cpfs(indice)

    if processados_com_sucesso > 0:
        st.success(f"Índice criado: {len(indice)} CPFs encontrados em {processados_com_sucesso} arquivos processados")
    
    if erros > 0:
        st.warning(f"{erros} arquivo(s) com erro durante o processamento")

    return indice

@st.cache_data(ttl=3600)
def listar_cpfs_otimizado():
    """Lista CPFs usando índice otimizado"""
    indice = criar_indice_cpfs_otimizado()
    return sorted(indice.keys())

def obter_periodos_referencia(dados):
    """Obtém todos os períodos de referência únicos dos pagamentos"""
    periodos = set()
    for pagamento in dados.get('pagamentos', []):
        if pagamento.get('perRef'):
            periodos.add(pagamento['perRef'])
    return sorted(list(periodos))

def filtrar_pagamentos_por_periodo(dados, periodos_selecionados):
    """Filtra pagamentos pelos períodos de referência selecionados"""
    if not periodos_selecionados:
        return dados
    
    dados_filtrados = dados.copy()
    dados_filtrados['pagamentos'] = [
        pag for pag in dados['pagamentos'] 
        if pag.get('perRef') in periodos_selecionados
    ]
    
    # Reconstrói listas de dependentes e deduções baseadas nos pagamentos filtrados
    dados_filtrados['dependentes'] = []
    dados_filtrados['deducoes_dependentes'] = []
    
    for pagamento in dados_filtrados['pagamentos']:
        dados_filtrados['dependentes'].extend(pagamento.get('dependentes', []))
        dados_filtrados['deducoes_dependentes'].extend(pagamento.get('deducoes_dependentes', []))
    
    return dados_filtrados

def agrupar_pagamentos_por_competencia(dados_filtrados):
    """Agrupa pagamentos por mês de competência"""
    pagamentos_por_mes = {}
    
    for pagamento in dados_filtrados.get('pagamentos', []):
        per_ref = pagamento.get('perRef', '')
        if per_ref:
            if per_ref not in pagamentos_por_mes:
                pagamentos_por_mes[per_ref] = []
            pagamentos_por_mes[per_ref].append(pagamento)
    
    # Ordena por data dentro de cada mês
    for mes in pagamentos_por_mes:
        pagamentos_por_mes[mes].sort(key=lambda x: x.get('dtPgto', ''))
    
    return dict(sorted(pagamentos_por_mes.items()))

# --- Processamento Principal Otimizado ---
def processar_arquivos_xml_otimizado(cpf_sel):
    """Processa arquivos XML para um CPF específico usando cache e índice"""
    indice = criar_indice_cpfs_otimizado()

    if cpf_sel not in indice:
        return {'pagamentos': [], 'dependentes': [], 'deducoes_dependentes': []}

    cache = carregar_cache()
    arquivos_relevantes = indice[cpf_sel]

    dados_consolidados = {
        'pagamentos': [],
        'dependentes': [],
        'deducoes_dependentes': [],
        'arquivos_processados': 0,
        'cache_hits': 0,
        'processados_novos': 0
    }

    if len(arquivos_relevantes) > 1:
        progress_bar = st.progress(0)
        status_text = st.empty()

    for i, arquivo in enumerate(arquivos_relevantes):
        file_path = os.path.join(PASTA_BASE, arquivo)
        file_hash = get_file_hash(file_path)
        cache_key = f"{arquivo}_{file_hash}"

        if cache_key in cache:
            dados = cache[cache_key]
            dados_consolidados['cache_hits'] += 1
        else:
            dados = processar_xml_completo(file_path)
            if dados:
                cache[cache_key] = dados
                dados_consolidados['processados_novos'] += 1

        if dados and dados.get('cpfBenef') == cpf_sel:
            dados_consolidados['pagamentos'].extend(dados.get('pagamentos', []))
            dados_consolidados['dependentes'].extend(dados.get('dependentes', []))
            dados_consolidados['deducoes_dependentes'].extend(dados.get('deducoes_dependentes', []))

            if 'perApur' not in dados_consolidados:
                dados_consolidados.update({
                    'nrRecArqBase': dados.get('nrRecArqBase'),
                    'perApur': dados.get('perApur'),
                    'tpInsc': dados.get('tpInsc'),
                    'nrInsc': dados.get('nrInsc'),
                    'cpfBenef': dados.get('cpfBenef')
                })

        dados_consolidados['arquivos_processados'] += 1

        if len(arquivos_relevantes) > 1:
            progress = (i + 1) / len(arquivos_relevantes)
            progress_bar.progress(progress)
            status_text.text(f"Processando: {i + 1}/{len(arquivos_relevantes)}")

    if len(arquivos_relevantes) > 1:
        progress_bar.empty()
        status_text.empty()

    if dados_consolidados['processados_novos'] > 0:
        salvar_cache(cache)

    return dados_consolidados

# --- Interface Otimizada ---
def criar_interface_cpf_pesquisavel(cpfs):
    """Interface pesquisável otimizada para seleção de CPF"""
    st.markdown("### Seleção de CPF")

    col1, col2 = st.columns([3, 1])

    with col1:
        termo_busca = st.text_input(
            "Digite para pesquisar CPF:",
            placeholder="Digite números do CPF (ex: 123456789 ou 123.456.789-01)",
            help="Digite parte do CPF para filtrar a lista"
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        limpar = st.button("Limpar", help="Limpar campo de busca")
        if limpar:
            st.rerun()

    cpfs_filtrados = filtrar_cpfs(cpfs, termo_busca)

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"Total de CPFs: {len(cpfs)}")
    with col2:
        if termo_busca:
            st.success(f"CPFs encontrados: {len(cpfs_filtrados)}")

    if not cpfs_filtrados:
        if termo_busca:
            st.warning("Nenhum CPF encontrado com o termo pesquisado.")
            st.info("Dica: Tente pesquisar apenas com números, sem pontos ou traços.")
        return None

    max_display = 100
    if len(cpfs_filtrados) > max_display:
        st.warning(f"Mostrando apenas os primeiros {max_display} resultados. Use a busca para refinar.")
        cpfs_para_exibir = cpfs_filtrados[:max_display]
    else:
        cpfs_para_exibir = cpfs_filtrados

    opcoes_cpf = [""] + cpfs_para_exibir

    cpf_selecionado = st.selectbox(
        "Selecione o CPF:",
        opcoes_cpf,
        index=0,
        help="Selecione o CPF desejado da lista filtrada",
        key="cpf_select"
    )

    return cpf_selecionado if cpf_selecionado else None

def criar_filtro_periodos(dados):
    """Cria interface para filtro de períodos de referência"""
    periodos_disponiveis = obter_periodos_referencia(dados)
    
    if not periodos_disponiveis:
        return []
    
    st.markdown("### Filtro por Período de Referência")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        periodos_selecionados = st.multiselect(
            "Selecione os períodos de competência:",
            periodos_disponiveis,
            default=periodos_disponiveis,  # Por padrão, todos selecionados
            help="Selecione um ou mais períodos para visualizar"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Selecionar Todos"):
            st.session_state.periodo_multiselect = periodos_disponiveis
            st.rerun()
    
    if not periodos_selecionados:
        st.info("Selecione pelo menos um período para visualizar os dados.")
    
    return periodos_selecionados

def mostrar_alertas_codigos_invalidos(dados):
    """Mostra alertas para códigos inválidos encontrados"""
    codigos_invalidos = []
    
    for pagamento in dados.get('pagamentos', []):
        for info_ir in pagamento.get('infoIR', []):
            desc = info_ir.get('tpInfoIRDesc', '')
            if 'não catalogado' in desc or 'código original:' in desc:
                codigos_invalidos.append({
                    'codigo': info_ir.get('tpInfoIR'),
                    'descricao': desc,
                    'valor': info_ir.get('valor', 0)
                })
    
    if codigos_invalidos:
        st.warning("Códigos não catalogados ou corrigidos encontrados:")
        for item in codigos_invalidos:
            st.write(f"- **{item['codigo']}**: {item['descricao']} (Valor: {format_value(item['valor'])})")
        
        st.info("Dica: Verifique se estes códigos precisam ser adicionados à tabela oficial ou se há erros nos XMLs originais.")

# --- Funções de exibição ---
def mostrar_resultados_segregados_por_competencia(dados, cpf_sel):
    """Nova versão que mostra resultados segregados por mês de competência"""
    
    # Informações básicas
    st.subheader("Informações Básicas")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("CPF do Beneficiário", dados.get('cpfBenef', ''))
        st.metric("Período de Apuração", dados.get('perApur', ''))

    with col2:
        st.metric("CNPJ do Empregador", dados.get('nrInsc', ''))

    # Filtro de períodos
    periodos_selecionados = criar_filtro_periodos(dados)
    
    if not periodos_selecionados:
        return
    
    # Filtra dados pelos períodos selecionados
    dados_filtrados = filtrar_pagamentos_por_periodo(dados, periodos_selecionados)
    
    # Mostra alertas para códigos não catalogados
    mostrar_alertas_codigos_invalidos(dados_filtrados)
    
    # Agrupa pagamentos por competência
    pagamentos_por_mes = agrupar_pagamentos_por_competencia(dados_filtrados)
    
    # Exibição segregada por mês
    st.subheader("Pagamentos por Mês de Competência")
    
    for mes, pagamentos_mes in pagamentos_por_mes.items():
        with st.expander(f"📅 Competência {mes} ({len(pagamentos_mes)} pagamento(s))", expanded=True):
            
            # Métricas do mês
            total_tributavel_mes = 0
            total_irrf_mes = 0
            total_isento_mes = 0
            
            for pagamento in pagamentos_mes:
                for info_ir in pagamento.get('infoIR', []):
                    valor = info_ir.get('valor', 0.0)
                    codigo = info_ir.get('tpInfoIR', '')
                    if codigo in ['11', '13', '31', '33', '91', '93']:  # Códigos tributáveis
                        total_tributavel_mes += valor
                    elif codigo in ['41', '43']:  # IRRF
                        total_irrf_mes += valor
                    elif codigo in ['70', '71', '72', '73', '74', '75']:  # Isentos
                        total_isento_mes += valor
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Tributável", format_value(total_tributavel_mes))
            with col2:
                st.metric("IRRF", format_value(total_irrf_mes))
            with col3:
                st.metric("Isenções", format_value(total_isento_mes))
            
            st.markdown("---")
            
            # Pagamentos do mês
            for i, pagamento in enumerate(pagamentos_mes):
                st.markdown(f"**Pagamento {i+1} - {pagamento.get('dtPgto', 'Data não informada')}**")
                mostrar_detalhes_pagamento_resumido(pagamento)
                
                # Dependentes específicos deste pagamento
                if pagamento.get('dependentes'):
                    st.markdown("**Dependentes (deste pagamento):**")
                    mostrar_dependentes_compacto(pagamento['dependentes'], pagamento.get('deducoes_dependentes', []))
                
                if i < len(pagamentos_mes) - 1:
                    st.markdown("---")

    # Seção de geração de comprovantes
    st.markdown("---")
    st.subheader("Geração de Comprovantes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Gerar Comprovante Simples (PDF)", type="secondary"):
            gerar_comprovante(dados_filtrados, cpf_sel)
    
    with col2:
        if st.button("Configurar Comprovante IN 2060/2021", type="primary"):
            st.session_state.tela_atual = "mapeamento"
            st.session_state.dados_para_comprovante = dados_filtrados
            st.rerun()

def mostrar_detalhes_pagamento_resumido(pagamento):
    """Versão resumida para exibição dentro dos meses"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Tipo de Pagamento:** {pagamento.get('tpPgto', '')}")
        cod_categ = pagamento.get('codCateg', '')
        cod_categ_desc = pagamento.get('codCategDesc', '')
        if cod_categ and cod_categ_desc:
            st.write(f"**Categoria:** {cod_categ} - {cod_categ_desc}")
        else:
            st.write(f"**Categoria:** {cod_categ}")
    
    with col2:
        if pagamento['totApurMen']:
            tot = pagamento['totApurMen']
            st.write(f"**Rendimentos Tributáveis:** {format_value(tot.get('vlrRendTrib', 0))}")
            st.write(f"**IRRF:** {format_value(tot.get('vlrCRMen', 0))}")

    if pagamento['infoIR']:
        with st.expander("Ver detalhes dos valores de IR", expanded=False):
            df_info_ir = pd.DataFrame(pagamento['infoIR'])

            if 'tpInfoIRDesc' in df_info_ir.columns:
                df_info_ir['Tipo Completo'] = df_info_ir['tpInfoIR'] + ' - ' + df_info_ir['tpInfoIRDesc']
                df_display = df_info_ir[['Tipo Completo', 'valor', 'descRendimento']].copy()
                df_display.columns = ['Tipo de Informação IR', 'Valor', 'Descrição']
            else:
                df_display = df_info_ir[['tpInfoIR', 'valor', 'descRendimento']].copy()
                df_display.columns = ['Tipo IR', 'Valor', 'Descrição']

            df_display['Valor'] = df_display['Valor'].apply(format_value)
            st.dataframe(df_display)

def mostrar_dependentes_compacto(dependentes, deducoes):
    """Versão compacta para exibição de dependentes"""
    if dependentes:
        for dep in dependentes:
            st.write(f"- **{dep.get('nome', 'Nome não informado')}** (CPF: {dep.get('cpfDep', '')}) - {dep.get('tpDepDesc', dep.get('tpDep', ''))}")
    
    if deducoes:
        st.write("**Deduções:**")
        for ded in deducoes:
            st.write(f"- CPF {ded.get('cpfDep', '')}: {format_value(ded.get('vlrDedDep', 0))}")

# --- Funções do Mapeamento IN 2060 ---
def salvar_mapeamento_personalizado(mapeamento):
    """Salva mapeamento personalizado do usuário"""
    try:
        with open(ARQUIVO_MAPEAMENTO, 'w', encoding='utf-8') as arquivo:
            json.dump(mapeamento, arquivo, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar mapeamento: {e}")
        return False

def processar_dados_para_comprovante(dados_xml):
    """Processa dados XML usando o mapeamento para gerar dados do comprovante"""
    
    mapeamento = carregar_mapeamento_personalizado()
    
    # Inicializa estrutura do comprovante
    comprovante_dados = {}
    for quadro_id, quadro_info in CAMPOS_COMPROVANTE_IN2060.items():
        comprovante_dados[quadro_id] = {}
        for linha_id in quadro_info["linhas"].keys():
            comprovante_dados[quadro_id][linha_id] = 0.0
    
    # Processa cada pagamento
    for pagamento in dados_xml.get('pagamentos', []):
        for info_ir in pagamento.get('infoIR', []):
            codigo = info_ir.get('tpInfoIR', '')
            valor = info_ir.get('valor', 0.0)
            
            if codigo in mapeamento:
                quadro, linha = mapeamento[codigo]
                if quadro in comprovante_dados and linha in comprovante_dados[quadro]:
                    comprovante_dados[quadro][linha] += valor
    
    # Adiciona dados básicos
    comprovante_dados['dados_basicos'] = {
        'exercicio': str(int(dados_xml.get('perApur', '2025-01')[:4]) + 1),
        'ano_calendario': dados_xml.get('perApur', '2025-01')[:4],
        'cnpj_fonte': dados_xml.get('nrInsc', ''),
        'cpf_beneficiario': dados_xml.get('cpfBenef', ''),
        'nome_beneficiario': 'A DEFINIR',
        'natureza_rendimento': 'RENDIMENTOS DO TRABALHO ASSALARIADO'
    }
    
    return comprovante_dados

def tela_mapeamento_comprovante(dados_xml):
    """Tela intermediária para mapear TPInfoIR aos campos do comprovante IN 2060"""
    
    st.title("Configuração do Mapeamento - Comprovante IN 2060/2021")
    
    st.markdown("""
    **Configure como os códigos TPInfoIR do S-5002 serão organizados no Comprovante de Rendimentos oficial.**
    
    Esta tela permite mapear cada código TPInfoIR encontrado nos seus XMLs S-5002 para os campos 
    corretos do Comprovante de Rendimentos conforme a Instrução Normativa RFB nº 2060/2021.
    """)
    
    # Carrega mapeamento atual
    mapeamento_atual = carregar_mapeamento_personalizado()
    
    # Extrai todos os códigos TPInfoIR únicos dos dados
    codigos_encontrados = set()
    for pagamento in dados_xml.get('pagamentos', []):
        for info_ir in pagamento.get('infoIR', []):
            codigo = info_ir.get('tpInfoIR', '')
            if codigo:
                codigos_encontrados.add(codigo)
    
    codigos_encontrados = sorted(list(codigos_encontrados))
    
    if not codigos_encontrados:
        st.warning("Nenhum código TPInfoIR encontrado nos dados XML.")
        return None
    
    # Estatísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Códigos encontrados", len(codigos_encontrados))
    with col2:
        st.metric("Códigos mapeados", len([c for c in codigos_encontrados if c in mapeamento_atual]))
    with col3:
        st.metric("Não mapeados", len([c for c in codigos_encontrados if c not in mapeamento_atual]))
    
    # Abas para organizar a interface
    tab1, tab2 = st.tabs(["Mapeamento Automático", "Visualização"])
    
    with tab1:
        st.subheader("Aplicar Mapeamento Automático Sugerido")
        st.info("Este mapeamento foi criado baseado nas regras da IN 2060/2021 e boas práticas.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Aplicar Mapeamento Padrão", type="primary"):
                mapeamento_atual.update(MAPEAMENTO_PADRAO_SUGERIDO)
                if salvar_mapeamento_personalizado(mapeamento_atual):
                    st.success("Mapeamento padrão aplicado com sucesso!")
                    st.rerun()
        
        with col2:
            if st.button("Limpar Mapeamento"):
                mapeamento_atual.clear()
                if salvar_mapeamento_personalizado(mapeamento_atual):
                    st.success("Mapeamento limpo!")
                    st.rerun()
        
        # Mostra diferenças entre atual e padrão
        st.subheader("Códigos Encontrados nos Dados")
        
        # Carrega descrições dos códigos
        codigos_dict = carregar_codigos_s5002()
        tp_info_ir_dict = codigos_dict.get('TPInfoIR', {})
        
        for codigo in codigos_encontrados:
            col1, col2, col3 = st.columns([1, 3, 2])
            
            with col1:
                st.write(f"**{codigo}**")
            
            with col2:
                descricao = tp_info_ir_dict.get(codigo, 'Descrição não encontrada')
                st.write(descricao)
            
            with col3:
                if codigo in mapeamento_atual:
                    quadro, linha = mapeamento_atual[codigo]
                    st.success(f"{quadro}.{linha}")
                elif codigo in MAPEAMENTO_PADRAO_SUGERIDO:
                    quadro, linha = MAPEAMENTO_PADRAO_SUGERIDO[codigo]
                    st.info(f"Sugerido: {quadro}.{linha}")
                else:
                    st.warning("Não mapeado")
    
    with tab2:
        st.subheader("Mapeamento Atual")
        
        # Organiza mapeamento por quadro para visualização
        mapeamento_por_quadro = {}
        for codigo, (quadro, linha) in mapeamento_atual.items():
            if codigo in codigos_encontrados:
                if quadro not in mapeamento_por_quadro:
                    mapeamento_por_quadro[quadro] = {}
                if linha not in mapeamento_por_quadro[quadro]:
                    mapeamento_por_quadro[quadro][linha] = []
                mapeamento_por_quadro[quadro][linha].append({
                    'codigo': codigo,
                    'descricao': tp_info_ir_dict.get(codigo, 'Não encontrada')
                })
        
        for quadro_id, linhas in mapeamento_por_quadro.items():
            st.markdown(f"### {CAMPOS_COMPROVANTE_IN2060[quadro_id]['nome']}")
            
            for linha_id, codigos_lista in linhas.items():
                linha_desc = CAMPOS_COMPROVANTE_IN2060[quadro_id]['linhas'][linha_id]
                st.markdown(f"**{linha_desc}:**")
                
                for item in codigos_lista:
                    st.write(f"- {item['codigo']}: {item['descricao']}")
            
            st.markdown("---")
        
        # Códigos não mapeados
        codigos_nao_mapeados = [c for c in codigos_encontrados if c not in mapeamento_atual]
        if codigos_nao_mapeados:
            st.warning("Códigos não mapeados:")
            for codigo in codigos_nao_mapeados:
                st.write(f"- {codigo}: {tp_info_ir_dict.get(codigo, 'Não encontrada')}")
    
    # Botão para prosseguir
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Voltar para Seleção de Dados"):
            return "voltar"
    
    with col2:
        codigos_mapeados = len([c for c in codigos_encontrados if c in mapeamento_atual])
        total_codigos = len(codigos_encontrados)
        
        if codigos_mapeados == total_codigos:
            if st.button("Gerar Comprovante IN 2060", type="primary"):
                return "gerar_comprovante"
        else:
            st.warning(f"{total_codigos - codigos_mapeados} código(s) ainda não mapeado(s)")
            if st.button("Gerar Comprovante (com pendências)"):
                return "gerar_comprovante"
    
    return None

class ComprovanteIN2060PDF:
    """Classe para gerar PDF do comprovante conforme IN 2060/2021"""
    
    def __init__(self):
        if FPDF is None:
            raise ImportError("FPDF não está disponível. Instale com: pip install fpdf2")
        
        self.pdf = FPDF('P', 'mm', 'A4')
        self.pdf.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.pdf.set_font('Arial', 'B', 16)
        self.pdf.cell(0, 10, 'COMPROVANTE DE RENDIMENTOS PAGOS', 0, 1, 'C')
        self.pdf.cell(0, 10, 'E DE IMPOSTO SOBRE A RENDA RETIDO NA FONTE', 0, 1, 'C')
        self.pdf.ln(5)
    
    def footer(self):
        self.pdf.set_y(-15)
        self.pdf.set_font('Arial', 'I', 8)
        self.pdf.cell(0, 10, f'Página {self.pdf.page_no()} - Conforme IN RFB nº 2060/2021', 0, 0, 'C')
    
    def add_page(self):
        self.pdf.add_page()
        self.header()
    
    def add_quadro(self, titulo, dados, linha_descricoes):
        """Adiciona um quadro ao comprovante"""
        self.pdf.set_font('Arial', 'B', 10)
        self.pdf.cell(0, 8, titulo, 1, 1, 'L')
        
        self.pdf.set_font('Arial', '', 9)
        for linha_id, descricao in linha_descricoes.items():
            valor = dados.get(linha_id, 0.0)
            if valor != 0.0 or linha_id in ['linha1', 'linha5']:
                self.pdf.cell(120, 6, descricao, 1, 0, 'L')
                self.pdf.cell(70, 6, format_value(valor), 1, 1, 'R')
        
        self.pdf.ln(3)
    
    def output(self, buffer):
        return self.pdf.output(buffer)

def gerar_comprovante_in2060(dados_xml, cpf_sel):
    """Gera o comprovante oficial conforme IN 2060/2021"""
    
    try:
        if FPDF is None:
            st.error("FPDF não está disponível. Instale com: pip install fpdf2")
            return
            
        with st.spinner("Gerando comprovante IN 2060/2021..."):
            # Processa dados usando mapeamento
            comprovante_dados = processar_dados_para_comprovante(dados_xml)
            
            # Cria PDF
            pdf = ComprovanteIN2060PDF()
            pdf.add_page()
            
            # Dados básicos
            dados_basicos = comprovante_dados['dados_basicos']
            pdf.pdf.set_font('Arial', 'B', 10)
            pdf.pdf.cell(40, 8, 'Exercício:', 1, 0, 'L')
            pdf.pdf.cell(40, 8, dados_basicos['exercicio'], 1, 0, 'C')
            pdf.pdf.cell(40, 8, 'Ano-calendário:', 1, 0, 'L')
            pdf.pdf.cell(70, 8, dados_basicos['ano_calendario'], 1, 1, 'C')
            pdf.pdf.ln(3)
            
            # Quadro 1 - Fonte Pagadora
            pdf.pdf.set_font('Arial', 'B', 10)
            pdf.pdf.cell(0, 8, 'QUADRO 1 - FONTE PAGADORA', 1, 1, 'L')
            pdf.pdf.set_font('Arial', '', 9)
            pdf.pdf.cell(30, 6, 'CNPJ:', 1, 0, 'L')
            pdf.pdf.cell(160, 6, dados_basicos['cnpj_fonte'], 1, 1, 'L')
            pdf.pdf.ln(3)
            
            # Quadro 2 - Beneficiário
            pdf.pdf.set_font('Arial', 'B', 10)
            pdf.pdf.cell(0, 8, 'QUADRO 2 - PESSOA FÍSICA BENEFICIÁRIA', 1, 1, 'L')
            pdf.pdf.set_font('Arial', '', 9)
            pdf.pdf.cell(30, 6, 'CPF:', 1, 0, 'L')
            pdf.pdf.cell(160, 6, dados_basicos['cpf_beneficiario'], 1, 1, 'L')
            pdf.pdf.cell(30, 6, 'Nome:', 1, 0, 'L')
            pdf.pdf.cell(160, 6, dados_basicos['nome_beneficiario'], 1, 1, 'L')
            pdf.pdf.ln(3)
            
            # Quadros principais
            for quadro_id, quadro_info in CAMPOS_COMPROVANTE_IN2060.items():
                if quadro_id in comprovante_dados:
                    pdf.add_quadro(
                        quadro_info["nome"].upper(),
                        comprovante_dados[quadro_id],
                        quadro_info["linhas"]
                    )
            
            # Gera arquivo
            buffer = io.BytesIO()
            pdf.output(buffer)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            # Cria link de download
            nome_arquivo = f"Comprovante_IN2060_{cpf_sel}_{dados_basicos['ano_calendario']}.pdf"
            st.markdown(create_download_link(pdf_bytes, nome_arquivo), unsafe_allow_html=True)
            st.success("Comprovante IN 2060/2021 gerado com sucesso!")
            
            # Mostra resumo
            mostrar_resumo_comprovante(comprovante_dados)

    except Exception as e:
        st.error(f"Erro ao gerar comprovante IN 2060: {str(e)}")
        st.exception(e)

def mostrar_resumo_comprovante(comprovante_dados):
    """Mostra resumo do comprovante gerado"""
    st.subheader("Resumo do Comprovante IN 2060/2021")
    
    # Métricas principais
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_tributavel = comprovante_dados.get('quadro3', {}).get('linha1', 0)
        st.metric("Total Tributável", format_value(total_tributavel))
    
    with col2:
        total_irrf = comprovante_dados.get('quadro3', {}).get('linha5', 0)
        st.metric("IRRF Total", format_value(total_irrf))
    
    with col3:
        total_isento = sum(comprovante_dados.get('quadro4', {}).values())
        st.metric("Total Isento", format_value(total_isento))

# --- Classes PDF (mantidas sem alteração) ---
class ComprovantePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'INFORME DE IMPOSTO DE RENDA RETIDO NA FONTE (S-5002)', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def create_download_link(pdf_bytes, filename):
    """Cria um link para download do PDF"""
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download do Comprovante</a>'

def gerar_comprovante(dados, cpf_sel):
    """Gera o PDF do comprovante simples"""
    try:
        with st.spinner("Gerando comprovante..."):
            pdf = ComprovantePDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)

            pdf.cell(0, 10, "INFORME DE IMPOSTO DE RENDA RETIDO NA FONTE (S-5002)", 0, 1, 'C')
            pdf.ln(5)

            pdf.cell(0, 8, "Informações Básicas:", 0, 1)
            pdf.cell(60, 8, "CPF do Beneficiário:", 1)
            pdf.cell(0, 8, dados.get('cpfBenef', ''), 1, 1)
            pdf.cell(60, 8, "Período de Apuração:", 1)
            pdf.cell(0, 8, dados.get('perApur', ''), 1, 1)
            pdf.cell(60, 8, "CNPJ do Empregador:", 1)
            pdf.cell(0, 8, dados.get('nrInsc', ''), 1, 1)
            pdf.ln(5)

            # Agrupa por competência para o PDF
            pagamentos_por_mes = agrupar_pagamentos_por_competencia(dados)
            
            for mes, pagamentos_mes in pagamentos_por_mes.items():
                pdf.cell(0, 8, f"Competência: {mes}", 0, 1)
                
                for pagamento in pagamentos_mes:
                    pdf.cell(0, 8, f"Data do Pagamento: {pagamento.get('dtPgto', '')}", 0, 1)
                    pdf.cell(60, 8, "Tipo de Pagamento:", 1)
                    pdf.cell(0, 8, pagamento.get('tpPgto', ''), 1, 1)

                    if pagamento['infoIR']:
                        pdf.cell(0, 8, "Informações de IR:", 0, 1)
                        for info in pagamento['infoIR']:
                            pdf.cell(100, 8, f"Tipo {info.get('tpInfoIR', '')}:", 1)
                            pdf.cell(0, 8, format_value(info.get('valor', 0)), 1, 1)

                    if pagamento['totApurMen']:
                        tot = pagamento['totApurMen']
                        pdf.cell(0, 8, "Totalização Mensal:", 0, 1)
                        pdf.cell(100, 8, "Rendimentos Tributáveis:", 1)
                        pdf.cell(0, 8, format_value(tot.get('vlrRendTrib', 0)), 1, 1)
                        pdf.cell(100, 8, "Valor do IRRF:", 1)
                        pdf.cell(0, 8, format_value(tot.get('vlrCRMen', 0)), 1, 1)

                    if pagamento.get('dependentes'):
                        pdf.cell(0, 8, f"Dependentes ({mes}):", 0, 1)
                        for dep in pagamento['dependentes']:
                            pdf.cell(60, 8, f"Nome: {dep.get('nome', '')}", 1)
                            pdf.cell(0, 8, f"CPF: {dep.get('cpfDep', '')}", 1, 1)

                    pdf.ln(3)
                
                pdf.ln(5)  # Espaço entre meses

            buffer = io.BytesIO()
            pdf.output(buffer)
            pdf_bytes = buffer.getvalue()
            buffer.close()

            nome_arquivo = f"Comprovante_IRRF_{cpf_sel}_{dados.get('perApur', '')}.pdf"
            st.markdown(create_download_link(pdf_bytes, nome_arquivo), unsafe_allow_html=True)
            st.success("Comprovante gerado com sucesso!")

    except Exception as e:
        st.error(f"Erro ao gerar PDF: {str(e)}")

def mostrar_estatisticas_sistema():
    """Mostra estatísticas do sistema na sidebar"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("**Estatísticas:**")

        try:
            total_xmls = len([f for f in os.listdir(PASTA_BASE) if f.lower().endswith('.xml')])
            st.metric("Total de XMLs", total_xmls)

            if CACHE_INDICE.exists():
                tamanho_indice = CACHE_INDICE.stat().st_size / 1024
                st.metric("Cache Índice", f"{tamanho_indice:.1f} KB")

            if CACHE_XMLS.exists():
                tamanho_cache = CACHE_XMLS.stat().st_size / 1024
                st.metric("Cache XMLs", f"{tamanho_cache:.1f} KB")

        except Exception as e:
            st.warning(f"Erro ao carregar estatísticas: {e}")

# --- Interface Principal ---
def main_interface_atualizada():
    """Interface principal atualizada com as melhorias solicitadas"""
    
    st.title("Informe de Imposto Retido - S-5002")

    # Sidebar
    with st.sidebar:
        if st.button("Voltar para Página Inicial"):
            voltar_pagina_principal()

        st.markdown("---")
        st.markdown("**Configurações:**")
        st.info(f"Pasta de eventos: {PASTA_BASE}")

        st.markdown("**Cache:**")
        if st.button("Recriar Índice"):
            for cache_file in [CACHE_XMLS, CACHE_INDICE]:
                if cache_file.exists():
                    cache_file.unlink()
            st.cache_data.clear()
            st.rerun()

        if CACHE_INDICE.exists():
            st.success("Índice em cache")
        if CACHE_XMLS.exists():
            st.success("XMLs em cache")

    # Carrega CPFs
    if 'cpfs_carregados' not in st.session_state:
        with st.spinner("Carregando lista de CPFs..."):
            st.session_state.cpfs_carregados = listar_cpfs_otimizado()

    cpfs = st.session_state.cpfs_carregados

    if not cpfs:
        st.warning("Nenhum CPF encontrado nos arquivos S-5002.")
        return

    cpf_sel = criar_interface_cpf_pesquisavel(cpfs)

    if cpf_sel:
        with st.spinner("Processando arquivos XML..."):
            dados_consolidados = processar_arquivos_xml_otimizado(cpf_sel)

        if dados_consolidados.get('arquivos_processados', 0) > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Arquivos processados",
                          dados_consolidados.get('arquivos_processados', 0))
            with col2:
                st.metric("Cache hits",
                          dados_consolidados.get('cache_hits', 0))
            with col3:
                st.metric("Processados agora",
                          dados_consolidados.get('processados_novos', 0))

        if dados_consolidados and dados_consolidados.get('pagamentos'):
            mostrar_resultados_segregados_por_competencia(dados_consolidados, cpf_sel)
        else:
            st.warning("Nenhum registro encontrado para este CPF.")

# --- Ponto de entrada ---
if __name__ == "__main__":
    try:
        if not os.path.exists(PASTA_BASE):
            st.error(f"Pasta não encontrada: {PASTA_BASE}")
            st.info("Verifique o caminho da pasta no código.")
        else:
            mostrar_estatisticas_sistema()
            main_interface_com_in2060()

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {str(e)}")
        st.error("Detalhes técnicos:")
        st.exception(e)

        if st.button("Limpar Cache e Reiniciar"):
            for cache_file in [CACHE_XMLS, CACHE_INDICE]:
                if cache_file.exists():
                    cache_file.unlink()
            st.cache_data.clear()
            st.rerun()estatisticas_sistema()
            main_interface_atualizada()

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {str(e)}")
        st.error("Detalhes técnicos:")
        st.exception(e)

        if st.button("Limpar Cache e Reiniciar"):
            for cache_file in [CACHE_XMLS, CACHE_INDICE]:
                if cache_file.exists():
                    cache_file.unlink()
            st.cache_data.clear()
            st.rerun()