# Extrator de Catálogos Comerciais em PDF (Aplicação Desktop)

Aplicação desktop nativa com interface gráfica moderna construída em Python (CustomTkinter) para extração automatizada de produtos, códigos, descrições, preços e números de página a partir de catálogos em formato PDF.

---

## 🌟 Principais Funcionalidades

1. **Seleção Nativa de Arquivos**:
   - Diálogo nativo do sistema operacional (`Abrir Catálogo PDF...`).
   - Detecção do tamanho do arquivo, quantidade de páginas e status.
   - Botão para **testar instantaneamente com um catálogo de exemplo** gerado sob medida.

2. **Extração Inteligente de Produtos**:
   - Identificação automática dos campos solicitados:
     - **Código do produto** (códigos alfanuméricos, referências, SKUs ou numéricos);
     - **Descrição / Nome** (especificações e detalhes completos);
     - **Preço** (preços em Reais `R$`, decimais brasileiros com vírgula ou números formatados);
     - **Número da Página** correspondente no documento.
   - Suporte a catálogos em formato de tabelas estruturadas ou blocos/linhas de texto livre.

3. **Visualização em Tabela Interativa**:
   - Grid moderno com visual escuro elegante.
   - **Busca em tempo real**: filtre instantaneamente por código, produto ou preço digitando na barra de pesquisa.
   - **Ordenação por coluna**: clique no cabeçalho de qualquer coluna (Código, Preço, Página, etc.) para ordenar de forma crescente ou decrescente.
   - **Exportação completa**: exporte os dados filtrados ou totais para **Excel (`.xlsx`)** e **CSV (`.csv`)** com 1 clique.

4. **Visualização do Texto Bruto Extraído**:
   - Aba dedicada para inspeção fiel de todo o conteúdo de texto extraído do PDF.
   - Seletor de páginas (*Todas as Páginas*, *Página 1*, *Página 2*, ...).
   - Busca com realce de palavras no texto bruto.
   - Botão para copiar texto diretamente para a área de transferência.

5. **Ajustes Customizáveis e Re-execução**:
   - Permite alterar a qualquer momento a estratégia de extração:
     - *Híbrido Inteligente (Tabelas + Texto)*;
     - *Somente Tabelas Estruturadas*;
     - *Somente Linhas de Texto (Regex)*.
   - Expressões regulares (Regex) editáveis com modelos pré-configurados prontos.
   - Filtro de intervalo de páginas (ex: `1-3, 5` ou `all`).
   - Botão **`🔄 Re-executar Extração com os Novos Ajustes`** que reprocessa os dados em milissegundos sem precisar reler o arquivo do disco.

6. **Arquitetura Assíncrona e Thread-Safe**:
   - A interface nunca trava nem congela durante o carregamento de PDFs com muitas páginas, graças ao uso de threads de trabalho em segundo plano e fila thread-safe (`queue.Queue`).

---

## 🚀 Como Executar

### 1. Pré-requisitos
Certifique-se de que o Python 3.10+ está instalado no seu computador.

### 2. Instalação das Dependências
No terminal ou PowerShell, navegue até a pasta do projeto e execute:
```bash
pip install -r requirements.txt
```

### 3. Iniciar a Aplicação
Execute o arquivo principal:
```bash
python app.py
```

---

## 📁 Estrutura do Projeto

```
Extra-o-de-dados-de-cat-logos-comerciais-em-PDF/
├── app.py                      # Ponto de entrada da aplicação desktop
├── requirements.txt            # Dependências do projeto
├── README.md                   # Documentação do sistema
├── catalogo_exemplo.pdf        # Catálogo de teste gerado automaticamente
│
├── core/                       # Lógica de extração e processamento
│   ├── models.py               # Estruturas de dados (ProductItem, ExtractionConfig, PageData)
│   ├── pdf_extractor.py        # Leitor e extrator de páginas/tabelas com pdfplumber
│   ├── parser.py               # Motor de heurísticas e regras regex para produtos
│   └── exporter.py             # Exportador para Excel (.xlsx) e CSV
│
├── gui/                        # Componentes da Interface Gráfica (CustomTkinter)
│   ├── main_window.py          # Janela principal e orquestração assíncrona
│   ├── table_view.py           # Tabela Treeview com busca, ordenação e exportação
│   ├── raw_text_view.py        # Visualizador de texto bruto e busca
│   └── settings_panel.py       # Painel de ajustes de regras e botão de re-execução
│
├── utils/                      # Utilitários auxiliares
│   └── sample_generator.py     # Gerador de catálogo PDF realista para testes
│
└── tests/                      # Bateria de testes automatizados
    └── test_app.py             # Validação automatizada de todos os 6 requisitos
```

---

## 🧪 Testes Automatizados

Para rodar a bateria de testes automatizados e validar todos os requisitos:
```bash
python tests/test_app.py
```
Resultado esperado:
```
==========================================
TODOS OS REQUISITOS FORAM TESTADOS E APROVADOS!
==========================================
```
