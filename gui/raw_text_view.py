import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable
from core.pdf_extractor import PDFDocumentReader

class RawTextView(ctk.CTkFrame):
    """
    Componente visual para visualização e busca do texto bruto extraído do PDF.
    Permite filtrar por página, buscar termos e copiar para a área de transferência.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.reader: Optional[PDFDocumentReader] = None
        self._init_ui()

    def _init_ui(self):
        # Barra de ferramentas superior
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(5, 10))

        # Seletor de Página
        lbl_page = ctk.CTkLabel(toolbar, text="Exibir:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_page.pack(side="left", padx=(0, 6))

        self.combo_page = ctk.CTkComboBox(
            toolbar,
            values=["Todas as Páginas"],
            width=180,
            height=34,
            command=self._on_page_selected
        )
        self.combo_page.pack(side="left", padx=(0, 15))
        self.combo_page.set("Todas as Páginas")

        # Campo de busca no texto bruto
        self.entry_search = ctk.CTkEntry(
            toolbar,
            placeholder_text="🔍 Localizar no texto bruto...",
            width=260,
            height=34
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_search.bind("<Return>", self._search_text)

        btn_find = ctk.CTkButton(
            toolbar,
            text="Buscar",
            width=80,
            height=34,
            command=self._search_text
        )
        btn_find.pack(side="left", padx=(0, 15))

        # Botão Copiar Tudo
        self.btn_copy = ctk.CTkButton(
            toolbar,
            text="📋 Copiar Texto",
            width=130,
            height=34,
            fg_color="#374151",
            hover_color="#4B5563",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copy_to_clipboard
        )
        self.btn_copy.pack(side="right")

        # Status do texto (número de caracteres/linhas)
        self.lbl_info = ctk.CTkLabel(
            self,
            text="Nenhum arquivo carregado",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        self.lbl_info.pack(anchor="w", padx=12, pady=(0, 4))

        # Caixa de texto rolável com fonte monospace
        self.txt_display = ctk.CTkTextbox(
            self,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
            fg_color="#111827",
            text_color="#F3F4F6",
            border_width=1,
            border_color="#374151"
        )
        self.txt_display.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def set_document(self, reader: PDFDocumentReader):
        """Atualiza a visualização com os dados do leitor de PDF."""
        self.reader = reader
        
        # Atualiza o combo de páginas
        page_options = ["Todas as Páginas"]
        for p in range(1, reader.total_pages + 1):
            page_options.append(f"Página {p}")

        self.combo_page.configure(values=page_options)
        self.combo_page.set("Todas as Páginas")

        self._refresh_content()

    def _on_page_selected(self, choice: str):
        self._refresh_content()

    def _refresh_content(self):
        if not self.reader or not self.reader.pages_data:
            self.txt_display.delete("1.0", "end")
            self.txt_display.insert("1.0", "Nenhum arquivo carregado.")
            self.lbl_info.configure(text="Nenhum arquivo carregado")
            return

        choice = self.combo_page.get()
        if choice == "Todas as Páginas":
            content = self.reader.get_full_raw_text()
            self.lbl_info.configure(
                text=f"Total: {self.reader.total_pages} páginas | {len(content):,} caracteres"
            )
        else:
            try:
                page_num = int(choice.replace("Página", "").strip())
                content = self.reader.get_full_raw_text(selected_page=page_num)
                self.lbl_info.configure(
                    text=f"Página {page_num} de {self.reader.total_pages} | {len(content):,} caracteres"
                )
            except ValueError:
                content = self.reader.get_full_raw_text()

        self.txt_display.delete("1.0", "end")
        self.txt_display.insert("1.0", content)

    def _search_text(self, event=None):
        query = self.entry_search.get().strip()
        if not query:
            return

        # Busca simples no textbox do Tkinter subjacente
        text_widget = self.txt_display._textbox
        text_widget.tag_remove("search_highlight", "1.0", "end")

        start_pos = "1.0"
        count = 0
        first_pos = None

        while True:
            pos = text_widget.search(query, start_pos, stopindex="end", nocase=True)
            if not pos:
                break
            if first_pos is None:
                first_pos = pos

            end_pos = f"{pos}+{len(query)}c"
            text_widget.tag_add("search_highlight", pos, end_pos)
            start_pos = end_pos
            count += 1

        text_widget.tag_config("search_highlight", background="#F59E0B", foreground="#000000")

        if first_pos:
            text_widget.see(first_pos)
            self.lbl_info.configure(text=f"{count} ocorrência(s) de '{query}' encontradas")
        else:
            self.lbl_info.configure(text=f"Nenhuma ocorrência de '{query}' encontrada")

    def _copy_to_clipboard(self):
        content = self.txt_display.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.btn_copy.configure(text="✓ Copiado!", fg_color="#059669")
            self.after(2000, lambda: self.btn_copy.configure(text="📋 Copiar Texto", fg_color="#374151"))
