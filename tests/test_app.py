import os
import sys
import time
from tkinter import messagebox

# Adiciona o diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock de caixas de diálogo para permitir testes automatizados não interativos
messagebox.showinfo = lambda title, message: None
messagebox.showwarning = lambda title, message: None
messagebox.showerror = lambda title, message: None

from gui.main_window import MainWindow
from core.models import ExtractionConfig
from core.exporter import CatalogExporter

def run_tests():
    print("Iniciando bateria de testes automatizados da aplicação Desktop...")
    
    app = MainWindow()
    app.withdraw() # Não abre a janela na tela
    
    # 1. Carrega o catálogo de exemplo
    sample_pdf = os.path.abspath("catalogo_exemplo.pdf")
    if not os.path.exists(sample_pdf):
        from utils.sample_generator import generate_sample_catalog
        generate_sample_catalog(sample_pdf)

    print("Carregando catálogo de exemplo...")
    app._load_pdf(sample_pdf)

    # Aguarda o worker terminar o processamento via fila
    start_time = time.time()
    while app.is_processing and (time.time() - start_time) < 15:
        app.update()
        app._poll_task_queue()
        time.sleep(0.05)

    assert not app.is_processing, "Processamento excedeu o tempo limite!"
    print(f"Processamento inicial finalizado com sucesso!")
    
    # Validações do Requisito 3 e 4 (Extração e Tabela)
    products = app.extracted_products
    print(f"Total de produtos extraídos: {len(products)}")
    assert len(products) == 30, f"Esperado 30 produtos, obteve {len(products)}"
    
    # Valida presença dos 4 campos solicitados pelo usuário
    for p in products:
        assert p.code, f"Item {p.index} sem código!"
        assert p.description, f"Item {p.index} sem descrição!"
        assert p.price, f"Item {p.index} sem preço!"
        assert p.page >= 1, f"Item {p.index} sem página válida!"

    print("[OK] Requisito 3 e 4: Identificacao de codigo, descricao, preco e pagina validados!")

    # Validação do Requisito 5 (Texto Bruto)
    raw_content = app.raw_text_view.txt_display.get("1.0", "end")
    assert "PÁGINA 1" in raw_content, "Texto bruto deve conter cabeçalho da Página 1"
    assert "PÁGINA 2" in raw_content, "Texto bruto deve conter cabeçalho da Página 2"
    assert "PÁGINA 3" in raw_content, "Texto bruto deve conter cabeçalho da Página 3"
    assert "SUP-3001" in raw_content, "Texto bruto deve conter produtos da página 3"
    print("[OK] Requisito 5: Exibicao do texto bruto extraido validada!")

    # Validação do Requisito 6 (Re-execução após ajustes)
    print("Testando re-execucao apos ajustes...")
    
    # Ajuste A: Somente tabelas estruturadas (deve retornar 20 itens das páginas 1 e 2)
    cfg_tables = ExtractionConfig(mode="tables_only", page_range="all")
    app._reextract_with_config(cfg_tables)
    app.update()
    print(f"Ajuste 'tables_only' retornou: {len(app.extracted_products)} produtos")
    assert len(app.extracted_products) == 20, f"Esperado 20, obteve {len(app.extracted_products)}"

    # Ajuste B: Filtro de página única (apenas página 2)
    cfg_page2 = ExtractionConfig(mode="tables_only", page_range="2")
    app._reextract_with_config(cfg_page2)
    app.update()
    print(f"Ajuste 'pagina 2' retornou: {len(app.extracted_products)} produtos")
    assert len(app.extracted_products) == 10, f"Esperado 10, obteve {len(app.extracted_products)}"
    for p in app.extracted_products:
        assert p.page == 2, f"Produto da pagina {p.page} nao deveria estar no resultado!"

    # Ajuste C: Volta para Híbrido em todas as páginas
    cfg_hybrid = ExtractionConfig(mode="hybrid", page_range="all")
    app._reextract_with_config(cfg_hybrid)
    app.update()
    assert len(app.extracted_products) == 30
    print("[OK] Requisito 6: Re-execucao da extracao apos ajustes validada com sucesso!")

    # Validação de Exportação (Excel e CSV)
    test_excel = os.path.abspath("teste_export.xlsx")
    test_csv = os.path.abspath("teste_export.csv")
    CatalogExporter.export_to_excel(app.extracted_products, test_excel)
    CatalogExporter.export_to_csv(app.extracted_products, test_csv)
    assert os.path.exists(test_excel) and os.path.getsize(test_excel) > 1000, "Erro ao gerar Excel"
    assert os.path.exists(test_csv) and os.path.getsize(test_csv) > 1000, "Erro ao gerar CSV"
    os.remove(test_excel)
    os.remove(test_csv)
    print("[OK] Exportacao para Excel e CSV validada!")

    # Validação do Filtro de Busca na Tabela
    app.table_view.entry_search.insert(0, "Nobreak")
    app.table_view._apply_filter_and_refresh()
    assert len(app.table_view.filtered_products) == 1, "Busca por 'Nobreak' deveria retornar 1 item"
    print("[OK] Busca em tempo real na tabela validada!")

    app.destroy()
    print("\n==========================================")
    print("TODOS OS REQUISITOS FORAM TESTADOS E APROVADOS!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
