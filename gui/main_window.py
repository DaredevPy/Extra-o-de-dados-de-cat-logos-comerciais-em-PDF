import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.models import ExtractionConfig, ProductItem
from core.pdf_extractor import PDFDocumentReader
from core.parser import CatalogParser
from core.exporter import CatalogExporter
from utils.sample_generator import generate_sample_catalog

from gui.table_view import TableView
from gui.raw_text_view import RawTextView
from gui.settings_panel import SettingsPanel

class MainWindow(ctk.CTk):
    """
    Janela principal da aplicação Desktop de Extração de Catálogos em PDF.
    Integra interface gráfica moderna, seleção de arquivos, visualização de dados,
    exibição de texto bruto e ajustes com re-extração instantânea.
    """
    def __init__(self):
        super().__init__()

        # Configurações gerais da janela
        self.title("Extrator de Catálogos Comerciais em PDF")
        self.geometry("1100x750")
        self.minsize(950, 600)

        # Tema escuro elegante por padrão
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Estado da aplicação
        self.current_file_path: str = ""
        self.reader: PDFDocumentReader = None
        self.extracted_products = []
        self.is_processing = False
        self.task_queue = queue.Queue()

        self._build_ui()
        self._check_initial_sample()
        
        # Inicia loop de verificação da fila de tarefas
        self._poll_task_queue()

    def _poll_task_queue(self):
        """Verifica periodicamente a fila de mensagens enviadas por threads de processamento."""
        try:
            while True:
                msg = self.task_queue.get_nowait()
                action = msg[0]
                if action == "progress":
                    frac, text = msg[1], msg[2]
                    self._update_progress(frac, text)
                elif action == "complete":
                    reader = msg[1]
                    products = msg[2]
                    self._on_processing_complete(reader, products)
                elif action == "error":
                    err_msg = msg[1]
                    self._on_processing_error(err_msg)
        except queue.Empty:
            pass
        finally:
            self.after(50, self._poll_task_queue)

    def _build_ui(self):
        # 1. CABEÇALHO SUPERIOR
        header_frame = ctk.CTkFrame(self, fg_color="#181B26", height=70, corner_radius=0)
        header_frame.pack(fill="x", side="top")

        title_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_container.pack(side="left", padx=20, pady=12)

        lbl_app_title = ctk.CTkLabel(
            title_container,
            text="📑 Extrator de Catálogos em PDF",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#F3F4F6"
        )
        lbl_app_title.pack(anchor="w")

        lbl_app_subtitle = ctk.CTkLabel(
            title_container,
            text="Identificação automática de Código, Descrição, Preço e Página",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF"
        )
        lbl_app_subtitle.pack(anchor="w")

        # Botão de alternância de tema no cabeçalho
        self.btn_theme = ctk.CTkButton(
            header_frame,
            text="🌓 Tema",
            width=80,
            height=30,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._toggle_theme
        )
        self.btn_theme.pack(side="right", padx=20, pady=15)

        # 2. BARRA DE SELEÇÃO DE ARQUIVO
        file_bar = ctk.CTkFrame(self, fg_color="#1E2330", corner_radius=10)
        file_bar.pack(fill="x", padx=15, pady=(15, 10))

        # Botão de seleção de arquivo PDF
        self.btn_select_file = ctk.CTkButton(
            file_bar,
            text="📂 Abrir Catálogo PDF...",
            height=38,
            width=200,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._choose_pdf_file
        )
        self.btn_select_file.pack(side="left", padx=12, pady=10)

        # Botão de gerar catálogo de exemplo para teste rápido
        self.btn_sample = ctk.CTkButton(
            file_bar,
            text="✨ Usar Catálogo de Exemplo",
            height=38,
            width=190,
            fg_color="#0D9488", # Verde-azulado
            hover_color="#0F766E",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._load_sample_catalog
        )
        self.btn_sample.pack(side="left", padx=(0, 15), pady=10)

        # Card de informações do arquivo selecionado
        file_info_frame = ctk.CTkFrame(file_bar, fg_color="#111827", corner_radius=6)
        file_info_frame.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)

        self.lbl_file_status = ctk.CTkLabel(
            file_info_frame,
            text="Nenhum arquivo PDF selecionado. Clique em 'Abrir Catálogo PDF...' ou use o exemplo.",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w"
        )
        self.lbl_file_status.pack(fill="x", padx=12, pady=8)

        # 3. ÁREA PRINCIPAL COM ABAS (TABVIEW)
        self.tabview = ctk.CTkTabview(self, corner_radius=10, fg_color="#181B26")
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        tab_table = self.tabview.add("📊 Tabela de Produtos")
        tab_raw = self.tabview.add("📝 Texto Bruto Extraído")
        tab_settings = self.tabview.add("⚙️ Ajustes de Extração")

        # Aba 1: Tabela de Produtos
        self.table_view = TableView(
            tab_table,
            on_export_excel=self._export_excel,
            on_export_csv=self._export_csv
        )
        self.table_view.pack(fill="both", expand=True, padx=5, pady=5)

        # Aba 2: Texto Bruto
        self.raw_text_view = RawTextView(tab_raw)
        self.raw_text_view.pack(fill="both", expand=True, padx=5, pady=5)

        # Aba 3: Painel de Ajustes e Re-extração
        self.settings_panel = SettingsPanel(
            tab_settings,
            on_reextract=self._reextract_with_config
        )
        self.settings_panel.pack(fill="both", expand=True, padx=5, pady=5)

        # 4. BARRA DE STATUS INFERIOR
        status_bar = ctk.CTkFrame(self, fg_color="#111827", height=32, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")

        self.lbl_status = ctk.CTkLabel(
            status_bar,
            text="Pronto para iniciar.",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        self.lbl_status.pack(side="left", padx=15)

        self.progress_bar = ctk.CTkProgressBar(status_bar, width=180, height=10, mode="determinate")
        self.progress_bar.pack(side="right", padx=15, pady=6)
        self.progress_bar.set(0)

    def _check_initial_sample(self):
        """Se o catálogo de exemplo já existir na pasta, avisa na barra de status."""
        sample_path = os.path.abspath("catalogo_exemplo.pdf")
        if os.path.exists(sample_path):
            self.lbl_status.configure(text="Dica: Clique em 'Usar Catálogo de Exemplo' para um teste imediato.")

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current.lower() == "dark":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

    def _choose_pdf_file(self):
        """Abre janela de diálogo do sistema operacional para seleção do arquivo PDF."""
        file_path = filedialog.askopenfilename(
            title="Selecione um Catálogo Comercial em PDF",
            filetypes=[("Arquivos PDF (*.pdf)", "*.pdf"), ("Todos os Arquivos", "*.*")]
        )
        if file_path:
            self._load_pdf(file_path)

    def _load_sample_catalog(self):
        """Gera ou carrega o catálogo de exemplo fictício."""
        sample_path = os.path.abspath("catalogo_exemplo.pdf")
        if not os.path.exists(sample_path):
            self.lbl_status.configure(text="Gerando catálogo de exemplo...")
            generate_sample_catalog(sample_path)
        self._load_pdf(sample_path)

    def _load_pdf(self, file_path: str):
        """Inicia a leitura e extração do PDF em thread separada para não travar a interface."""
        if self.is_processing:
            return

        self.is_processing = True
        self.current_file_path = file_path
        self.btn_select_file.configure(state="disabled")
        self.btn_sample.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text=f"Carregando {os.path.basename(file_path)}...")

        # Lê a configuração de extração na thread principal (evita acesso a widgets na thread secundária)
        config = self.settings_panel.get_config()

        threading.Thread(target=self._process_pdf_worker, args=(file_path, config), daemon=True).start()

    def _process_pdf_worker(self, file_path: str, config: ExtractionConfig):
        try:
            reader = PDFDocumentReader(file_path)

            def progress_cb(current, total, msg):
                frac = current / total if total > 0 else 0
                self.task_queue.put(("progress", frac, msg))

            # Lê todas as páginas do PDF
            reader.load_document(progress_callback=progress_cb)

            # Executa o analisador inteligente de catálogo
            parser = CatalogParser(config)
            products = parser.parse_document(reader.pages_data)

            # Envia resultado completo e o reader pela fila thread-safe
            self.task_queue.put(("complete", reader, products))

        except Exception as e:
            self.task_queue.put(("error", str(e)))

    def _update_progress(self, fraction: float, message: str):
        self.progress_bar.set(fraction)
        self.lbl_status.configure(text=message)

    def _on_processing_complete(self, reader: PDFDocumentReader, products):
        self.reader = reader
        self.extracted_products = products
        self.is_processing = False
        self.btn_select_file.configure(state="normal")
        self.btn_sample.configure(state="normal")
        self.progress_bar.set(1.0)

        # Atualiza card de informações do arquivo
        fname = self.reader.file_name
        fsize = self.reader.file_size_formatted
        pages = self.reader.total_pages
        self.lbl_file_status.configure(
            text=f"📄 {fname}  |  Tamanho: {fsize}  |  Páginas: {pages}",
            text_color="#60A5FA"
        )

        # Atualiza a tabela com os produtos identificados
        self.table_view.set_data(products)

        # Atualiza a visualização do texto bruto
        self.raw_text_view.set_document(self.reader)

        # Seleciona a aba da tabela
        self.tabview.set("📊 Tabela de Produtos")

        count = len(products)
        self.lbl_status.configure(text=f"✓ Extração concluída com sucesso: {count} produtos encontrados.")

    def _on_processing_error(self, error_msg: str):
        self.is_processing = False
        self.btn_select_file.configure(state="normal")
        self.btn_sample.configure(state="normal")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Erro durante a extração do PDF.")
        messagebox.showerror("Erro de Processamento", f"Ocorreu um erro ao extrair os dados do PDF:\n\n{error_msg}")

    def _reextract_with_config(self, config: ExtractionConfig):
        """
        Requisito 6: Executa a extração novamente depois dos ajustes.
        Utiliza os dados do documento já em memória, aplicando os novos parâmetros instantaneamente.
        """
        if not self.reader or not self.reader.is_loaded:
            messagebox.showwarning("Aviso", "Por favor, selecione ou abra um arquivo PDF antes de re-executar a extração.")
            return

        self.lbl_status.configure(text="Re-executando extração com novos ajustes...")
        self.progress_bar.set(0.5)

        try:
            parser = CatalogParser(config)
            products = parser.parse_document(self.reader.pages_data)
            self.extracted_products = products

            # Atualiza tabela
            self.table_view.set_data(products)
            self.progress_bar.set(1.0)

            # Volta para a aba da tabela para o usuário conferir o resultado
            self.tabview.set("📊 Tabela de Produtos")

            count = len(products)
            self.lbl_status.configure(text=f"✓ Re-extração concluída: {count} produtos encontrados com os novos ajustes!")
            messagebox.showinfo("Sucesso", f"Extração re-executada com sucesso!\n\nForam encontrados {count} produtos com os ajustes atuais.")

        except Exception as e:
            self.lbl_status.configure(text="Erro ao re-executar a extração.")
            messagebox.showerror("Erro", f"Falha ao aplicar novos ajustes:\n\n{str(e)}")

    def _export_excel(self):
        if not self.extracted_products:
            messagebox.showwarning("Aviso", "Não há produtos extraídos para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Salvar Planilha Excel",
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel (*.xlsx)", "*.xlsx")]
        )
        if file_path:
            try:
                CatalogExporter.export_to_excel(self.extracted_products, file_path)
                messagebox.showinfo("Exportação Concluída", f"Arquivo Excel salvo com sucesso em:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Erro na Exportação", f"Erro ao salvar arquivo Excel:\n{str(e)}")

    def _export_csv(self):
        if not self.extracted_products:
            messagebox.showwarning("Aviso", "Não há produtos extraídos para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Salvar Arquivo CSV",
            defaultextension=".csv",
            filetypes=[("Arquivo CSV (*.csv)", "*.csv")]
        )
        if file_path:
            try:
                CatalogExporter.export_to_csv(self.extracted_products, file_path)
                messagebox.showinfo("Exportação Concluída", f"Arquivo CSV salvo com sucesso em:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Erro na Exportação", f"Erro ao salvar arquivo CSV:\n{str(e)}")
