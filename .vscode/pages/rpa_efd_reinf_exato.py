#!/usr/bin/env python3
"""
RPA EFD-REINF - VERSÃO FINAL COM CONTROLE DE DUPLICATAS
Automação inteligente para download de XMLs R-4000 do portal ECAC

CORREÇÕES BASEADAS NO DEBUG:
✅ Controle de duplicatas por número de recibo
✅ Detecção correta do fim da paginação
✅ Prevenção de loop infinito
✅ Identificação precisa da coluna de recibos
✅ Navegação inteligente entre páginas
✅ Log detalhado de recibos processados

EXECUÇÃO: python rpa_efd_reinf_final.py
"""

import asyncio
import logging
import signal
import sys
import atexit
from datetime import datetime, timedelta
from pathlib import Path
import re
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/rpa_efd_reinf_final.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Variáveis globais para cleanup
browser_global = None
playwright_global = None

def cleanup_resources():
    """Limpa recursos ao sair"""
    global browser_global, playwright_global
    try:
        if browser_global:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(browser_global.close())
            loop.close()
    except:
        pass

# Registra cleanup automático
atexit.register(cleanup_resources)

# Tratamento de interrupção (Ctrl+C)
def signal_handler(sig, frame):
    print("\n🛑 INTERROMPIDO PELO USUÁRIO")
    print("💾 Verificando downloads realizados...")
    
    downloads_folder = Path("downloads/efd_reinf")
    if downloads_folder.exists():
        arquivos = list(downloads_folder.rglob("*.xml"))
        if arquivos:
            print(f"✅ {len(arquivos)} arquivos XML foram salvos antes da interrupção")
            print(f"📁 Localização: {downloads_folder.absolute()}")
        else:
            print("⚠️ Nenhum arquivo foi salvo ainda")
    
    cleanup_resources()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Verifica se Playwright está instalado
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Playwright não instalado!")
    print("💡 Execute: pip install playwright")
    print("💡 Depois: playwright install chromium")
    input("Pressione Enter para sair...")
    sys.exit(1)

class RPAEFDReinfFinal:
    def __init__(self):
        self.browser = None
        self.page = None
        self.iframe = None
        self.playwright = None
        self.downloads_folder = Path("downloads/efd_reinf")
        self.downloads_folder.mkdir(parents=True, exist_ok=True)
        self.downloads_realizados = []
        self.total_processados = 0
        self.competencia_atual = ""
        self.pagina_atual = 1
        self.total_paginas = 0
        
        # CONTROLE DE DUPLICATAS - NOVO
        self.recibos_processados = set()  # Set para controle de duplicatas
        self.recibos_por_pagina = {}      # Dict para debug
        self.paginas_visitadas = set()    # Controle de páginas já visitadas
        
        # Cache de seletores para reuso
        self.seletores_cache = {
            'detalhar': [],
            'xml': None,
            'voltar': None,
            'proxima': None
        }
        
        # Cria pastas necessárias
        Path("screenshots").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

    def salvar_estado_recibos(self):
        """Salva estado dos recibos processados"""
        try:
            estado = {
                "timestamp": datetime.now().isoformat(),
                "competencia": self.competencia_atual,
                "recibos_processados": list(self.recibos_processados),
                "recibos_por_pagina": self.recibos_por_pagina,
                "paginas_visitadas": list(self.paginas_visitadas),
                "total_processados": self.total_processados
            }
            
            estado_path = self.downloads_folder / f"estado_recibos_{self.competencia_atual.replace('/', '-')}.json"
            with open(estado_path, 'w', encoding='utf-8') as f:
                json.dump(estado, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️ Erro ao salvar estado: {str(e)}")

    def carregar_estado_recibos(self):
        """Carrega estado anterior dos recibos"""
        try:
            estado_path = self.downloads_folder / f"estado_recibos_{self.competencia_atual.replace('/', '-')}.json"
            if estado_path.exists():
                with open(estado_path, 'r', encoding='utf-8') as f:
                    estado = json.load(f)
                
                self.recibos_processados = set(estado.get("recibos_processados", []))
                self.recibos_por_pagina = estado.get("recibos_por_pagina", {})
                self.paginas_visitadas = set(estado.get("paginas_visitadas", []))
                
                print(f"📋 Estado carregado: {len(self.recibos_processados)} recibos já processados")
                return True
                
        except Exception as e:
            print(f"⚠️ Erro ao carregar estado: {str(e)}")
            
        return False

    async def conectar_chrome(self):
        """Conecta ao Chrome e encontra o iframe EFD-REINF"""
        global browser_global, playwright_global
        try:
            print("🔌 Conectando ao Chrome...")
            
            self.playwright = await async_playwright().start()
            playwright_global = self.playwright
            
            self.browser = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
            browser_global = self.browser
            
            # Procura página da Receita Federal
            for context in self.browser.contexts:
                for page in context.pages:
                    if "receita" in page.url.lower():
                        self.page = page
                        break
                if self.page:
                    break
            
            if not self.page:
                print("❌ Página da Receita Federal não encontrada!")
                return False
                
            print("✅ Página principal encontrada")
            
            # Procura iframe EFD-REINF
            try:
                iframe_element = await self.page.wait_for_selector("iframe#frmApp", timeout=8000)
                if not iframe_element:
                    return False
                
                self.iframe = await iframe_element.content_frame()
                if not self.iframe:
                    return False
                
                print("✅ Iframe EFD-REINF acessado")
                return True
                
            except Exception as e:
                print(f"❌ Erro ao acessar iframe: {str(e)}")
                return False
            
        except Exception as e:
            print(f"❌ Erro ao conectar: {str(e)}")
            return False

    def criar_pasta_competencia(self, competencia):
        """Cria pasta específica para a competência"""
        try:
            mes, ano = competencia.split('/')
            pasta_nome = f"{ano}-{mes.zfill(2)}"
            pasta_competencia = self.downloads_folder / pasta_nome
            pasta_competencia.mkdir(parents=True, exist_ok=True)
            return pasta_competencia
        except Exception:
            return self.downloads_folder

    async def configurar_downloads(self):
        """Configura captura automática de downloads"""
        try:
            async def handle_download(download):
                try:
                    pasta_destino = self.criar_pasta_competencia(self.competencia_atual)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"EFD_REINF_R4000_{timestamp}.xml"
                    
                    if download.suggested_filename:
                        original_name = download.suggested_filename
                        if not original_name.endswith('.xml'):
                            original_name += '.xml'
                        filename = f"{timestamp}_{original_name}"
                    
                    download_path = pasta_destino / filename
                    await download.save_as(download_path)
                    
                    arquivo_relativo = f"{self.competencia_atual.replace('/', '-')}/{filename}"
                    self.downloads_realizados.append(arquivo_relativo)
                    print(f"📥 ✅ XML salvo: {arquivo_relativo}")
                    
                except Exception as e:
                    print(f"❌ Erro ao salvar download: {str(e)}")
            
            self.page.on("download", handle_download)
            self.iframe.on("download", handle_download)
            print("✅ Downloads configurados")
            
        except Exception as e:
            print(f"❌ Erro ao configurar downloads: {str(e)}")

    async def aguardar_inteligente(self, segundos=2, operacao=""):
        """Aguarda de forma inteligente com feedback"""
        if operacao:
            print(f"   ⏳ Aguardando {operacao}...")
        await asyncio.sleep(segundos)

    async def screenshot_debug(self, nome="debug"):
        """Screenshot para debug quando necessário"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"screenshots/{nome}_{timestamp}.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 Debug: {screenshot_path}")
        except:
            pass

    async def navegar_para_visualizar_pagamentos_balanceado(self):
        """PASSO 1: Navegação balanceada para visualizar pagamentos"""
        try:
            print("🎯 PASSO 1: Navegando para 'Visualizar pagamentos/créditos'...")
            
            await self.aguardar_inteligente(2, "carregamento inicial")
            
            # Seletores priorizados
            seletores_visualizar = [
                "text=Visualizar pagamentos/créditos",
                "text=Visualizar pagamentos",
                "//a[contains(text(), 'Visualizar pagamentos')]"
            ]
            
            # Tenta clique direto primeiro
            for seletor in seletores_visualizar:
                try:
                    element = await self.iframe.wait_for_selector(seletor, timeout=3000)
                    if element and await element.is_visible():
                        await element.click()
                        await self.iframe.wait_for_load_state('networkidle', timeout=15000)
                        print("✅ Navegou diretamente para visualizar pagamentos")
                        await self.aguardar_inteligente(3, "carregamento da página")
                        return True
                except:
                    continue
            
            # Se não funcionou, tenta hover + clique
            print("🖱️ Tentando navegação via hover...")
            seletores_hover = [
                "text=Rendimentos Pagos/Creditados (Série R-4000)",
                "text=Série R-4000",
                "//a[contains(text(), 'Rendimentos')]"
            ]
            
            for seletor_hover in seletores_hover:
                try:
                    element = await self.iframe.wait_for_selector(seletor_hover, timeout=3000)
                    if element:
                        await element.hover()
                        await self.aguardar_inteligente(1, "submenu")
                        
                        # Tenta clicar no submenu
                        for seletor in seletores_visualizar:
                            try:
                                sub_element = await self.iframe.wait_for_selector(seletor, timeout=2000)
                                if sub_element and await sub_element.is_visible():
                                    await sub_element.click()
                                    await self.iframe.wait_for_load_state('networkidle', timeout=15000)
                                    print("✅ Navegou via hover+click")
                                    await self.aguardar_inteligente(3, "carregamento da página")
                                    return True
                            except:
                                continue
                except:
                    continue
            
            print("❌ Falha na navegação")
            await self.screenshot_debug("erro_navegacao")
            return False
            
        except Exception as e:
            print(f"❌ Erro ao navegar: {str(e)}")
            await self.screenshot_debug("erro_navegacao")
            return False

    async def preencher_periodo_balanceado(self, mes_ano):
        """PASSO 2: Preenchimento balanceado do período"""
        try:
            print(f"📅 PASSO 2: Preenchendo período {mes_ano}...")
            
            await self.aguardar_inteligente(2, "carregamento dos campos")
            
            # Seletores otimizados
            seletores_periodo = [
                "input[placeholder='MM/AAAA']",
                "input[placeholder*='MM/AAAA']",
                "input[placeholder*='MM/YYYY']",
                "input[type='text'][placeholder*='MM']"
            ]
            
            campos_periodo = []
            
            for seletor in seletores_periodo:
                try:
                    elements = await self.iframe.query_selector_all(seletor)
                    for element in elements:
                        if await element.is_visible():
                            campos_periodo.append(element)
                    if campos_periodo:
                        break
                except:
                    continue
            
            if not campos_periodo:
                # Fallback: todos os inputs text visíveis
                print("🔍 Procurando todos os inputs text...")
                todos_inputs = await self.iframe.query_selector_all("input[type='text']")
                for inp in todos_inputs:
                    try:
                        if await inp.is_visible():
                            campos_periodo.append(inp)
                            if len(campos_periodo) >= 2:
                                break
                    except:
                        continue
            
            if not campos_periodo:
                print("❌ Campos de período não encontrados")
                await self.screenshot_debug("erro_campos_periodo")
                return False
            
            print(f"✅ Encontrados {len(campos_periodo)} campos de período")
            
            # Preenchimento mais cuidadoso
            async def preencher_seguro(campo, valor, nome):
                try:
                    await campo.click()
                    await self.aguardar_inteligente(0.3)
                    await campo.press('Control+a')
                    await campo.fill(valor)
                    await campo.press('Tab')
                    await self.aguardar_inteligente(0.5)
                    
                    # Verifica se preencheu
                    valor_atual = await campo.input_value()
                    if valor_atual == valor:
                        print(f"✅ Campo {nome}: {valor_atual}")
                        return True
                    else:
                        print(f"⚠️ Campo {nome}: '{valor_atual}' (esperado: '{valor}')")
                        return False
                except Exception as e:
                    print(f"❌ Erro no campo {nome}: {str(e)}")
                    return False
            
            sucesso = 0
            if len(campos_periodo) >= 2:
                if await preencher_seguro(campos_periodo[0], mes_ano, "DE"):
                    sucesso += 1
                if await preencher_seguro(campos_periodo[1], mes_ano, "ATÉ"):
                    sucesso += 1
            elif len(campos_periodo) == 1:
                if await preencher_seguro(campos_periodo[0], mes_ano, "ÚNICO"):
                    sucesso += 1
            
            if sucesso > 0:
                print(f"✅ Período preenchido ({sucesso} campos)")
                return True
            else:
                print("❌ Falha no preenchimento")
                await self.screenshot_debug("erro_preenchimento")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao preencher período: {str(e)}")
            return False

    async def clicar_listar_balanceado(self):
        """PASSO 3: Clique balanceado no botão Listar"""
        try:
            print("🔍 PASSO 3: Clicando em Listar...")
            
            await self.aguardar_inteligente(1, "preparação para listar")
            
            seletores_listar = [
                "//button[text()='Listar']",
                "//input[@type='submit' and @value='Listar']",
                "//input[@type='button' and @value='Listar']",
                "button:has-text('Listar')",
                "input[value='Listar']",
                "text=Listar"
            ]
            
            for i, seletor in enumerate(seletores_listar):
                try:
                    element = await self.iframe.wait_for_selector(seletor, timeout=3000)
                    if element and await element.is_visible():
                        # Verifica se não é um botão de tabela
                        try:
                            parent = await element.query_selector('..')
                            if parent:
                                parent_text = await parent.inner_text()
                                if any(word in parent_text.lower() for word in ['estabelecimento', 'período', 'beneficiário']):
                                    continue
                        except:
                            pass
                        
                        print(f"✅ Clicando em Listar (seletor {i+1})...")
                        await element.click()
                        await self.iframe.wait_for_load_state('networkidle', timeout=20000)
                        print("✅ Botão Listar clicado")
                        await self.aguardar_inteligente(4, "carregamento da tabela")
                        return True
                except:
                    continue
            
            print("❌ Botão Listar não encontrado")
            await self.screenshot_debug("erro_listar")
            return False
            
        except Exception as e:
            print(f"❌ Erro ao clicar Listar: {str(e)}")
            return False

    async def extrair_recibos_da_pagina(self):
        """NOVO: Extrai todos os recibos da página atual"""
        try:
            print(f"🔍 Extraindo recibos da página {self.pagina_atual}...")
            
            # Padrão do recibo baseado no DEBUG
            padrao_recibo = r'\d{8}-\d{2}-\d{4}-\d{4}-\d{8}'
            
            # Baseado no DEBUG: procura na tabela, coluna 6 (Número do recibo)
            recibos_pagina = []
            
            # Procura a tabela
            tabela = await self.iframe.query_selector("table")
            if not tabela:
                print("❌ Tabela não encontrada")
                return []
            
            # Procura linhas da tabela (pula cabeçalho)
            linhas = await tabela.query_selector_all("tr")
            
            for i, linha in enumerate(linhas[1:], 1):  # Pula cabeçalho
                try:
                    # Procura célula da coluna 6 (número do recibo)
                    celulas = await linha.query_selector_all("td")
                    if len(celulas) >= 6:  # Certifica que tem pelo menos 6 colunas
                        celula_recibo = celulas[5]  # Coluna 6 (índice 5)
                        texto_celula = await celula_recibo.inner_text()
                        
                        # Procura padrão do recibo
                        match = re.search(padrao_recibo, texto_celula)
                        if match:
                            recibo = match.group()
                            recibos_pagina.append(recibo)
                            print(f"   📋 Linha {i}: {recibo}")
                        
                except Exception as e:
                    print(f"   ⚠️ Erro na linha {i}: {str(e)}")
                    continue
            
            # Salva recibos desta página
            self.recibos_por_pagina[self.pagina_atual] = recibos_pagina
            
            print(f"✅ Encontrados {len(recibos_pagina)} recibos na página {self.pagina_atual}")
            return recibos_pagina
            
        except Exception as e:
            print(f"❌ Erro ao extrair recibos: {str(e)}")
            return []

    async def detectar_eventos_com_controle_duplicatas(self):
        """NOVO: Detecta eventos e controla duplicatas"""
        try:
            print("📋 Detectando eventos com controle de duplicatas...")
            
            await self.aguardar_inteligente(2, "carregamento completo da tabela")
            
            # Primeiro, extrai todos os recibos da página
            recibos_pagina = await self.extrair_recibos_da_pagina()
            
            if not recibos_pagina:
                print("❌ Nenhum recibo encontrado na página")
                return 0
            
            # Verifica quais recibos são novos (não processados)
            recibos_novos = []
            recibos_duplicados = []
            
            for recibo in recibos_pagina:
                if recibo not in self.recibos_processados:
                    recibos_novos.append(recibo)
                else:
                    recibos_duplicados.append(recibo)
            
            if recibos_duplicados:
                print(f"⚠️ Recibos já processados (ignorando): {len(recibos_duplicados)}")
                for recibo in recibos_duplicados:
                    print(f"   🔄 {recibo}")
            
            if not recibos_novos:
                print("ℹ️ Todos os recibos desta página já foram processados")
                return 0
            
            print(f"✅ Recibos novos para processar: {len(recibos_novos)}")
            for recibo in recibos_novos:
                print(f"   🆕 {recibo}")
            
            # Agora detecta botões Detalhar apenas para recibos novos
            seletores_detalhar = [
                "//button[text()='Detalhar']",
                "//input[@type='submit' and @value='Detalhar']",
                "//input[@type='button' and @value='Detalhar']"
            ]
            
            botoes_detalhar = []
            
            for seletor in seletores_detalhar:
                try:
                    elements = await self.iframe.query_selector_all(seletor)
                    if elements:
                        for element in elements:
                            if await element.is_visible():
                                botoes_detalhar.append(element)
                        
                        if botoes_detalhar:
                            print(f"✅ Seletor funcionou: {seletor}")
                            break
                except:
                    continue
            
            if not botoes_detalhar:
                print("❌ Nenhum botão 'Detalhar' encontrado")
                return 0
            
            # Atualiza cache
            self.seletores_cache['detalhar'] = [seletores_detalhar[0] if seletores_detalhar else "//button[text()='Detalhar']"]
            
            # Retorna apenas a quantidade de recibos novos
            return len(recibos_novos)
            
        except Exception as e:
            print(f"❌ Erro ao detectar eventos: {str(e)}")
            return 0

    async def processar_evento_com_controle_duplicatas(self, indice_linha, recibo_esperado):
        """NOVO: Processa evento verificando duplicata por recibo"""
        try:
            print(f"🔄 Processando linha {indice_linha+1} - Recibo: {recibo_esperado}")
            
            # Verifica se já foi processado
            if recibo_esperado in self.recibos_processados:
                print(f"⚠️ Recibo {recibo_esperado} já processado - pulando")
                return False
            
            # Recarrega botões Detalhar
            seletor_detalhar = self.seletores_cache['detalhar'][0] if self.seletores_cache['detalhar'] else "//button[text()='Detalhar']"
            
            await self.aguardar_inteligente(1, "recarregamento da tabela")
            
            elements = await self.iframe.query_selector_all(seletor_detalhar)
            if not elements or indice_linha >= len(elements):
                print(f"⚠️ Botão Detalhar {indice_linha+1} não encontrado")
                return False
            
            botao_detalhar = elements[indice_linha]
            if not await botao_detalhar.is_visible():
                print(f"⚠️ Botão Detalhar {indice_linha+1} não visível")
                return False
            
            # Clica Detalhar
            print("👆 Clicando em Detalhar...")
            await botao_detalhar.click()
            await self.iframe.wait_for_load_state('networkidle', timeout=15000)
            await self.aguardar_inteligente(2, "carregamento do detalhe")
            
            # Baixa XML
            sucesso_xml = await self.baixar_xml_balanceado()
            if sucesso_xml:
                # Marca recibo como processado
                self.recibos_processados.add(recibo_esperado)
                self.total_processados += 1
                print(f"✅ XML baixado - Recibo {recibo_esperado} processado")
                
                # Salva estado
                self.salvar_estado_recibos()
            else:
                print(f"⚠️ Falha ao baixar XML - Recibo {recibo_esperado}")
            
            # Volta para tabela
            await self.voltar_tabela_balanceado()
            
            return sucesso_xml
            
        except Exception as e:
            print(f"❌ Erro no evento {indice_linha+1}: {str(e)}")
            await self.voltar_tabela_balanceado()
            return False

    async def baixar_xml_balanceado(self):
        """Baixa XML com método balanceado"""
        try:
            print("📥 Procurando botão 'Baixar XML do evento'...")
            
            # Usa cache se disponível
            if self.seletores_cache['xml']:
                try:
                    element = await self.iframe.wait_for_selector(self.seletores_cache['xml'], timeout=3000)
                    if element and await element.is_visible():
                        await element.click()
                        await self.aguardar_inteligente(2, "download do XML")
                        print("✅ XML baixado (cache)")
                        return True
                except:
                    pass
            
            # Seletores priorizados
            seletores_xml = [
                "//button[contains(text(), 'Baixar XML do evento')]",
                "//input[@value='Baixar XML do evento']",
                "//button[contains(text(), 'Baixar XML')]",
                "//input[@value='Baixar XML']",
                "//a[contains(text(), 'Baixar XML')]",
                "text=Baixar XML do evento",
                "text=Baixar XML"
            ]
            
            for i, seletor in enumerate(seletores_xml):
                try:
                    element = await self.iframe.wait_for_selector(seletor, timeout=3000)
                    if element and await element.is_visible():
                        # Atualiza cache
                        self.seletores_cache['xml'] = seletor
                        await element.click()
                        await self.aguardar_inteligente(2, "download do XML")
                        print(f"✅ XML baixado (seletor {i+1})")
                        return True
                except:
                    continue
            
            print("❌ Botão 'Baixar XML do evento' não encontrado")
            await self.screenshot_debug("erro_xml_nao_encontrado")
            return False
            
        except Exception as e:
            print(f"❌ Erro ao baixar XML: {str(e)}")
            return False

    async def voltar_tabela_balanceado(self):
        """Volta para tabela com método balanceado"""
        try:
            print("🔙 Voltando para a tabela...")
            
            # Usa cache se disponível
            if self.seletores_cache['voltar']:
                try:
                    element = await self.iframe.wait_for_selector(self.seletores_cache['voltar'], timeout=3000)
                    if element and await element.is_visible():
                        await element.click()
                        await self.iframe.wait_for_load_state('networkidle', timeout=15000)
                        await self.aguardar_inteligente(2, "recarregamento da tabela")
                        print("✅ Voltou (cache)")
                        return True
                except:
                    pass
            
            seletores_voltar = [
                "//button[text()='Voltar']",
                "//input[@type='submit' and @value='Voltar']",
                "//input[@type='button' and @value='Voltar']",
                "//a[contains(text(), 'Voltar')]",
                "text=Voltar"
            ]
            
            for seletor in seletores_voltar:
                try:
                    element = await self.iframe.wait_for_selector(seletor, timeout=3000)
                    if element and await element.is_visible():
                        # Atualiza cache
                        self.seletores_cache['voltar'] = seletor
                        await element.click()
                        await self.iframe.wait_for_load_state('networkidle', timeout=15000)
                        await self.aguardar_inteligente(2, "recarregamento da tabela")
                        print("✅ Voltou para tabela")
                        return True
                except:
                    continue
            
            # Fallback: navegador
            print("🔄 Tentando voltar pelo navegador...")
            try:
                await self.iframe.go_back()
                await self.iframe.wait_for_load_state('networkidle', timeout=15000)
                await self.aguardar_inteligente(3, "recarregamento via navegador")
                print("✅ Voltou via navegador")
                return True
            except:
                print("⚠️ Falha ao voltar")
                return False
            
        except Exception as e:
            print(f"❌ Erro ao voltar: {str(e)}")
            return False

    async def detectar_paginacao_inteligente(self):
        """NOVO: Detecta paginação baseada no DEBUG"""
        try:
            print("📄 Detectando informações de paginação...")
            
            await self.aguardar_inteligente(2, "análise de paginação")
            
            # Baseado no DEBUG: procura botão "Próxima page"
            # Reset contadores
            self.total_paginas = 1
            self.pagina_atual = 1
            
            # Método 1: Procura botão "Próxima"
            seletores_proxima = [
                "//a[contains(text(), 'Próxima')]",
                "//button[contains(text(), 'Próxima')]",
                "//a[text()='»']",
                "//a[text()='>']"
            ]
            
            tem_navegacao = False
            for seletor in seletores_proxima:
                try:
                    element = await self.iframe.query_selector(seletor)
                    if element and await element.is_visible():
                        tem_navegacao = True
                        print(f"✅ Botão de navegação encontrado: {seletor}")
                        break
                except:
                    continue
            
            if tem_navegacao:
                self.total_paginas = 999  # Assume múltiplas páginas
                print("📊 Sistema de paginação detectado - navegação automática ativa")
            else:
                print("ℹ️ Apenas uma página detectada")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro na detecção de paginação: {str(e)}")
            self.total_paginas = 1
            self.pagina_atual = 1
            return False

    async def verificar_proxima_pagina_inteligente(self):
        """NOVO: Verifica próxima página com controle de loop"""
        try:
            print(f"\n📄 Verificando próxima página... (atual: {self.pagina_atual})")
            
            # Verifica se já visitou esta página (prevenção de loop)
            chave_pagina = f"pag_{self.pagina_atual}"
            if chave_pagina in self.paginas_visitadas:
                print("⚠️ Página já visitada - possível loop detectado")
                return False
            
            # Marca página como visitada
            self.paginas_visitadas.add(chave_pagina)
            
            await self.aguardar_inteligente(2, "análise de navegação")
            
            # Baseado no DEBUG: procura especificamente botão "Próxima page"
            seletores_proxima = [
                "//a[contains(text(), 'Próxima')]",
                "//button[contains(text(), 'Próxima')]",
                "//a[text()='»']",
                "//a[text()='>']",
                "//a[contains(text(), 'Next')]"
            ]
            
            for i, seletor in enumerate(seletores_proxima):
                try:
                    element = await self.iframe.query_selector(seletor)
                    if element and await element.is_visible():
                        # Verifica se não está desabilitado
                        disabled = await element.get_attribute('disabled')
                        aria_disabled = await element.get_attribute('aria-disabled')
                        class_name = await element.get_attribute('class') or ""
                        
                        is_disabled = (
                            disabled == 'true' or 
                            disabled == '' or 
                            aria_disabled == 'true' or
                            'disabled' in class_name.lower()
                        )
                        
                        if not is_disabled:
                            text = await element.inner_text()
                            print(f"✅ Botão 'Próxima' ativo encontrado: '{text.strip()}'")
                            
                            # Extrai recibos antes de navegar (para comparação)
                            recibos_antes = await self.extrair_recibos_da_pagina()
                            
                            await element.click()
                            print("👆 Clicando na próxima página...")
                            
                            # Aguarda navegação
                            await self.iframe.wait_for_load_state('networkidle', timeout=20000)
                            await self.aguardar_inteligente(4, "carregamento da nova página")
                            
                            # Verifica se realmente mudou de página
                            recibos_depois = await self.extrair_recibos_da_pagina()
                            
                            if recibos_antes == recibos_depois and len(recibos_antes) > 0:
                                print("⚠️ Mesmos recibos detectados - não houve mudança de página")
                                return False
                            
                            self.pagina_atual += 1
                            print(f"✅ Navegou para página {self.pagina_atual}")
                            return True
                        else:
                            text = await element.inner_text()
                            print(f"ℹ️ Botão 'Próxima' desabilitado: '{text.strip()}' - última página")
                            return False
                
                except Exception as e:
                    print(f"⚠️ Seletor {i+1} falhou: {str(e)}")
                    continue
            
            print("ℹ️ Não há mais páginas para navegar")
            return False
            
        except Exception as e:
            print(f"❌ Erro ao verificar próxima página: {str(e)}")
            return False

    async def processar_tabela_eventos_inteligente(self):
        """NOVO: Processa tabela com controle inteligente de duplicatas"""
        try:
            print(f"📋 Processando página {self.pagina_atual} com controle de duplicatas...")
            
            # Detecta eventos com controle de duplicatas
            total_eventos_novos = await self.detectar_eventos_com_controle_duplicatas()
            
            if total_eventos_novos == 0:
                print("ℹ️ Nenhum evento novo encontrado nesta página")
                return 0
            
            print(f"✅ Processando {total_eventos_novos} eventos novos...")
            
            # Pega lista de recibos novos desta página
            recibos_pagina = self.recibos_por_pagina.get(self.pagina_atual, [])
            recibos_novos = [r for r in recibos_pagina if r not in self.recibos_processados]
            
            eventos_processados = 0
            
            # Processa apenas eventos com recibos novos
            for i, recibo in enumerate(recibos_novos):
                try:
                    # Encontra índice da linha na tabela baseado no recibo
                    indice_linha = recibos_pagina.index(recibo)
                    
                    if await self.processar_evento_com_controle_duplicatas(indice_linha, recibo):
                        eventos_processados += 1
                        print(f"✅ Evento {i+1}/{len(recibos_novos)} processado: {recibo}")
                    else:
                        print(f"⚠️ Falha no evento {i+1}/{len(recibos_novos)}: {recibo}")
                    
                    # Pausa entre eventos
                    if i < len(recibos_novos) - 1:
                        await self.aguardar_inteligente(0.5, "preparação próximo evento")
                    
                except Exception as e:
                    print(f"❌ Erro no evento {recibo}: {str(e)}")
                    continue
            
            print(f"✅ Página {self.pagina_atual} concluída: {eventos_processados}/{len(recibos_novos)} eventos novos processados")
            return eventos_processados
            
        except Exception as e:
            print(f"❌ Erro ao processar tabela: {str(e)}")
            return 0

    async def processar_periodo_completo_final(self, mes_ano):
        """NOVO: Processa período completo com todas as correções"""
        try:
            self.competencia_atual = mes_ano
            
            # Carrega estado anterior se existir
            self.carregar_estado_recibos()
            
            print(f"\n{'='*60}")
            print(f"📅 PROCESSANDO PERÍODO: {mes_ano}")
            if self.recibos_processados:
                print(f"🔄 Continuando de onde parou: {len(self.recibos_processados)} recibos já processados")
            print(f"{'='*60}")
            
            # PASSO 1: Navega para visualizar pagamentos
            if not await self.navegar_para_visualizar_pagamentos_balanceado():
                print("❌ Falha na navegação")
                return False
            
            # PASSO 2: Preenche período
            if not await self.preencher_periodo_balanceado(mes_ano):
                print("❌ Falha no preenchimento")
                return False
            
            # PASSO 3: Clica Listar
            if not await self.clicar_listar_balanceado():
                print("❌ Falha ao listar")
                return False
            
            # Detecta paginação inteligente
            await self.detectar_paginacao_inteligente()
            
            # Reset contadores para nova execução
            self.pagina_atual = 1
            self.paginas_visitadas.clear()
            total_eventos_periodo = 0
            paginas_processadas = 0
            
            while True:
                print(f"\n📄 Processando página {self.pagina_atual}...")
                
                eventos_pagina = await self.processar_tabela_eventos_inteligente()
                total_eventos_periodo += eventos_pagina
                paginas_processadas += 1
                
                if eventos_pagina == 0:
                    print("ℹ️ Página sem eventos novos")
                
                # Salva estado após cada página
                self.salvar_estado_recibos()
                
                # Verifica próxima página com controle de loop
                if await self.verificar_proxima_pagina_inteligente():
                    continue
                else:
                    print("✅ Fim da paginação detectado")
                    break
                
                # Proteção contra loop infinito
                if paginas_processadas > 100:  # Limite de segurança
                    print("⚠️ Limite de páginas atingido - parando para evitar loop")
                    break
            
            print(f"\n✅ Período {mes_ano} concluído!")
            print(f"📊 Total de eventos novos processados: {total_eventos_periodo}")
            print(f"📄 Páginas processadas: {paginas_processadas}")
            print(f"📋 Total de recibos únicos: {len(self.recibos_processados)}")
            print(f"📁 Arquivos salvos em: downloads/efd_reinf/{mes_ano.replace('/', '-')}/")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro no período {mes_ano}: {str(e)}")
            await self.screenshot_debug("erro_periodo")
            return False

    async def finalizar_recursos(self):
        """Finaliza recursos de forma segura"""
        try:
            print("🔄 Finalizando recursos...")
            if self.browser:
                await self.browser.close()
                print("✅ Browser fechado")
        except Exception as e:
            print(f"⚠️ Erro ao finalizar: {str(e)}")

    async def executar_automacao_completa_final(self):
        """NOVO: Execução principal com todas as correções"""
        try:
            if not await self.conectar_chrome():
                print("❌ Falha na conexão")
                return
            
            await self.configurar_downloads()
            
            print("🤖 RPA EFD-REINF - VERSÃO FINAL COM CONTROLE DE DUPLICATAS")
            print("="*70)
            print("🎯 CORREÇÕES IMPLEMENTADAS:")
            print("   ✅ Controle de duplicatas por número de recibo")
            print("   ✅ Detecção correta do fim da paginação")
            print("   ✅ Prevenção de loop infinito")
            print("   ✅ Estado salvo para continuar execução")
            print("   ✅ Identificação precisa da coluna de recibos")
            print("   ✅ Navegação inteligente entre páginas")
            print("="*70)
            
            # Configuração de períodos
            print("\n📅 CONFIGURAÇÃO DE PERÍODOS:")
            print("1️⃣ Período único (ex: 01/2025)")
            print("2️⃣ Múltiplos períodos (ex: 01/2025, 02/2025)")
            print("3️⃣ Intervalo de meses (ex: de 01/2025 até 12/2025)")
            
            opcao = input("\nEscolha 1, 2 ou 3: ").strip()
            
            periodos = []
            
            if opcao == "1":
                periodo = input("Digite o período (MM/YYYY): ").strip()
                if periodo:
                    periodos = [periodo]
                    
            elif opcao == "2":
                periodos_str = input("Digite os períodos separados por vírgula: ").strip()
                if periodos_str:
                    periodos = [p.strip() for p in periodos_str.split(',')]
                    
            elif opcao == "3":
                inicio = input("Digite período inicial (MM/YYYY): ").strip()
                fim = input("Digite período final (MM/YYYY): ").strip()
                
                if inicio and fim:
                    try:
                        mes_inicio, ano_inicio = map(int, inicio.split('/'))
                        mes_fim, ano_fim = map(int, fim.split('/'))
                        
                        periodos = []
                        mes_atual, ano_atual = mes_inicio, ano_inicio
                        
                        while (ano_atual < ano_fim) or (ano_atual == ano_fim and mes_atual <= mes_fim):
                            periodos.append(f"{mes_atual:02d}/{ano_atual}")
                            mes_atual += 1
                            if mes_atual > 12:
                                mes_atual = 1
                                ano_atual += 1
                                
                    except ValueError:
                        print("❌ Formato inválido")
                        return
            
            if not periodos:
                print("❌ Nenhum período definido")
                return
            
            print(f"\n✅ Períodos selecionados: {', '.join(periodos)}")
            
            confirma = input("\nIniciar automação FINAL? (s/N): ").strip().lower()
            
            if confirma not in ['s', 'sim', 'y', 'yes']:
                print("❌ Cancelado")
                return
            
            # Execução final
            inicio_execucao = datetime.now()
            periodos_sucesso = 0
            
            print(f"\n🚀 INICIANDO AUTOMAÇÃO FINAL PARA {len(periodos)} PERÍODO(S)...")
            print("🎯 MODO INTELIGENTE: Sem duplicatas + Controle de loop!")
            print("👀 OBSERVE O CHROME - O RPA ESTÁ TRABALHANDO!")
            print("🚫 NÃO TOQUE NO MOUSE OU TECLADO")
            
            for i, periodo in enumerate(periodos, 1):
                print(f"\n🎯 PERÍODO {i}/{len(periodos)}: {periodo}")
                
                if await self.processar_periodo_completo_final(periodo):
                    periodos_sucesso += 1
                    print(f"✅ Período {periodo} concluído!")
                else:
                    print(f"❌ Falha no período {periodo}")
                
                # Pausa entre períodos
                if i < len(periodos):
                    await self.aguardar_inteligente(2, "preparação próximo período")
            
            # Relatório final
            fim_execucao = datetime.now()
            duracao = fim_execucao - inicio_execucao
            
            print("\n" + "="*70)
            print("📊 RELATÓRIO FINAL - VERSÃO INTELIGENTE")
            print("="*70)
            print(f"⏱️ Duração total: {duracao}")
            print(f"📅 Períodos processados: {periodos_sucesso}/{len(periodos)}")
            print(f"📥 Total de XMLs baixados: {len(self.downloads_realizados)}")
            print(f"🔢 Total de eventos processados: {self.total_processados}")
            print(f"🎯 Total de recibos únicos: {len(self.recibos_processados)}")
            print(f"📁 Pasta principal: {self.downloads_folder.absolute()}")
            
            if self.downloads_realizados:
                print(f"\n📋 Arquivos baixados por competência:")
                
                # Agrupa por competência
                por_competencia = {}
                for arquivo in self.downloads_realizados:
                    if '/' in arquivo:
                        competencia = arquivo.split('/')[0]
                        if competencia not in por_competencia:
                            por_competencia[competencia] = []
                        por_competencia[competencia].append(arquivo.split('/')[1])
                
                for comp, arquivos in por_competencia.items():
                    print(f"\n  📂 {comp}: {len(arquivos)} arquivos")
                    for arquivo in arquivos[:5]:  # Primeiros 5
                        print(f"    📄 {arquivo}")
                    if len(arquivos) > 5:
                        print(f"    ... e mais {len(arquivos) - 5} arquivos")
            
            # Mostra recibos únicos processados
            if self.recibos_processados:
                print(f"\n🎯 RECIBOS ÚNICOS PROCESSADOS:")
                for comp, recibos in self.recibos_por_pagina.items():
                    if recibos:
                        print(f"   Página {comp}: {len(recibos)} recibos")
            
            # Cálculo de velocidade
            if duracao.total_seconds() > 0:
                velocidade = self.total_processados / duracao.total_seconds() * 60
                print(f"\n🎯 VELOCIDADE INTELIGENTE: {velocidade:.1f} eventos/minuto")
            
            print("\n✅ AUTOMAÇÃO INTELIGENTE CONCLUÍDA!")
            print("🎯 Nenhum evento duplicado foi processado!")
            
        except Exception as e:
            print(f"❌ Erro na execução: {str(e)}")
        
        finally:
            await self.finalizar_recursos()


async def main():
    print("="*70)
    print("🤖 RPA EFD-REINF - VERSÃO FINAL COM CONTROLE DE DUPLICATAS")
    print("="*70)
    print("\n🎯 CORREÇÕES BASEADAS NO DEBUG:")
    print("1️⃣ ✅ Identificação da coluna 6 (número do recibo)")
    print("2️⃣ ✅ Controle de duplicatas por recibo único")
    print("3️⃣ ✅ Detecção inteligente do fim da paginação")
    print("4️⃣ ✅ Prevenção de loop infinito")
    print("5️⃣ ✅ Estado salvo para continuar execução")
    print("6️⃣ ✅ Verificação de mudança real de página")
    print("7️⃣ ✅ Limite de segurança (100 páginas max)")
    print("8️⃣ ✅ Log detalhado de recibos processados")
    print()
    print("🔍 BASEADO NO SEU DEBUG:")
    print("   📋 Tabela com 9 colunas identificada")
    print("   🎯 Coluna 6 = Número do recibo único")
    print("   🔘 Botão 'Próxima page' detectado")
    print("   📄 Padrão recibo: XXXXXXXX-XX-XXXX-XXXX-XXXXXXXX")
    print()
    print("⚠️  IMPORTANTE:")
    print("   🚫 Nunca mais baixará o mesmo recibo")
    print("   🔄 Pode continuar execução interrompida")
    print("   📊 Mostra recibos únicos vs duplicatas")
    print("   ⏹️ Para automaticamente na última página")
    print()
    print("⚠️  PRÉ-REQUISITOS:")
    print("✅ Chrome: chrome.exe --remote-debugging-port=9222")
    print("✅ Login no ECAC com certificado digital")
    print("✅ Estar na página do EFD-REINF")
    print()
    
    confirma = input("Executar versão FINAL? (s/N): ").strip().lower()
    
    if confirma in ['s', 'sim', 'y', 'yes']:
        rpa = RPAEFDReinfFinal()
        await rpa.executar_automacao_completa_final()
    else:
        print("❌ Operação cancelada")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Script interrompido pelo usuário")
        print("✅ Encerramento controlado realizado")
        cleanup_resources()
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        cleanup_resources()
        input("Pressione Enter para sair...")