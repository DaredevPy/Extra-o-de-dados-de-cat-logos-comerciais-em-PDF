import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import List, Callable, Optional
from core.models import ProductItem

class TableView(ctk.CTkFrame):
    """
    Componente visual moderno de tabela (Treeview estilizado) com:
    - Exibição de colunas: Índice, Página, Código, Descrição, Preço, Origem.
    - Ordenação dinâmica ao clicar nos cabeçalhos.
    - Filtro de busca em tempo real.
    - Botões de exportação (Excel / CSV).
    """
    def __init__(self, master, on_export_excel: Optional[Callable] = None, on_export_csv: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.on_export_excel = on_export_excel
        self.on_export_csv = on_export_csv
        
        self.all_products: List[ProductItem] = []
        self.filtered_products: List[ProductItem] = []
        self.sort_column_name: Optional[str] = None
        self.sort_descending: bool = False

        self._init_ui()

    def _init_ui(self):
        # Barra superior de ações e busca
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(5, 10))

        # Contador de itens
        self.lbl_counter = ctk.CTkLabel(
            top_bar,
            text="0 produtos encontrados",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10B981", # Verde esmeralda
            fg_color="#064E3B",
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.lbl_counter.pack(side="left", padx=(0, 15))

        # Campo de busca
        self.entry_search = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍 Filtrar por código, descrição ou preço...",
            width=320,
            height=34
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.entry_search.bind("<KeyRelease>", self._on_search_key)

        # Botão Limpar Busca
        self.btn_clear_search = ctk.CTkButton(
            top_bar,
            text="✕",
            width=34,
            height=34,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._clear_search
        )
        self.btn_clear_search.pack(side="left", padx=(0, 15))

        # Botões de exportação
        if self.on_export_excel:
            self.btn_excel = ctk.CTkButton(
                top_bar,
                text="📊 Exportar Excel",
                width=130,
                height=34,
                fg_color="#107C41",  # Verde Excel
                hover_color="#0B5A2F",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_export_excel
            )
            self.btn_excel.pack(side="right", padx=(5, 0))

        if self.on_export_csv:
            self.btn_csv = ctk.CTkButton(
                top_bar,
                text="📄 Exportar CSV",
                width=120,
                height=34,
                fg_color="#2563EB",  # Azul
                hover_color="#1D4ED8",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_export_csv
            )
            self.btn_csv.pack(side="right", padx=(5, 5))

        # Container para a tabela Treeview com Scrollbars
        table_container = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=8)
        table_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Configura estilo do Treeview para combinar com tema escuro do CustomTkinter
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Custom.Treeview",
            background="#1F2937",
            foreground="#F9FAFB",
            fieldbackground="#1F2937",
            rowheight=30,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#374151",
            foreground="#F3F4F6",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padding=6
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[("active", "#4B5563")]
        )
        style.map(
            "Custom.Treeview",
            background=[("selected", "#2563EB")],
            foreground=[("selected", "#FFFFFF")]
        )

        # Colunas da tabela
        columns = ("index", "page", "code", "description", "price", "source")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="browse"
        )

        # Configuração das Colunas e Cabeçalhos
        self.tree.heading("index", text="#", command=lambda: self._sort_by("index"))
        self.tree.heading("page", text="Página", command=lambda: self._sort_by("page"))
        self.tree.heading("code", text="Código do Produto", command=lambda: self._sort_by("code"))
        self.tree.heading("description", text="Descrição / Nome", command=lambda: self._sort_by("description"))
        self.tree.heading("price", text="Preço", command=lambda: self._sort_by("price"))
        self.tree.heading("source", text="Origem", command=lambda: self._sort_by("source"))

        self.tree.column("index", width=50, minwidth=40, anchor="center")
        self.tree.column("page", width=70, minwidth=60, anchor="center")
        self.tree.column("code", width=140, minwidth=100, anchor="w")
        self.tree.column("description", width=420, minwidth=250, anchor="w")
        self.tree.column("price", width=120, minwidth=90, anchor="e")
        self.tree.column("source", width=80, minwidth=70, anchor="center")

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Tags para listras alternadas
        self.tree.tag_configure("oddrow", background="#1F2937")
        self.tree.tag_configure("evenrow", background="#111827")

    def set_data(self, products: List[ProductItem]):
        """Atualiza os dados exibidos na tabela."""
        self.all_products = list(products)
        self._apply_filter_and_refresh()

    def _on_search_key(self, event=None):
        self._apply_filter_and_refresh()

    def _clear_search(self):
        self.entry_search.delete(0, "end")
        self._apply_filter_and_refresh()

    def _apply_filter_and_refresh(self):
        query = self.entry_search.get().strip().lower()
        if not query:
            self.filtered_products = list(self.all_products)
        else:
            self.filtered_products = [
                p for p in self.all_products
                if query in str(p.page).lower()
                or query in p.code.lower()
                or query in p.description.lower()
                or query in p.price.lower()
            ]

        # Atualiza badge do contador
        total = len(self.all_products)
        filtered = len(self.filtered_products)
        if query:
            self.lbl_counter.configure(
                text=f"{filtered} de {total} produtos (filtrado)",
                text_color="#FBBF24",
                fg_color="#78350F"
            )
        else:
            self.lbl_counter.configure(
                text=f"{total} produtos encontrados",
                text_color="#10B981" if total > 0 else "#9CA3AF",
                fg_color="#064E3B" if total > 0 else "#374151"
            )

        self._render_rows()

    def _render_rows(self):
        # Limpa linhas antigas
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        # Insere novas linhas
        for idx, p in enumerate(self.filtered_products):
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.tree.insert(
                "",
                "end",
                values=(p.index, f"Pág {p.page}", p.code, p.description, p.price, p.source_type),
                tags=(tag,)
            )

    def _sort_by(self, col_name: str):
        """Ordena a tabela pela coluna especificada."""
        if self.sort_column_name == col_name:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column_name = col_name
            self.sort_descending = False

        def get_sort_key(p: ProductItem):
            if col_name == "index":
                return p.index
            elif col_name == "page":
                return p.page
            elif col_name == "code":
                return p.code.lower()
            elif col_name == "description":
                return p.description.lower()
            elif col_name == "price":
                # Tenta extrair float do preço para ordenação numérica
                clean = p.price.replace("R$", "").replace(".", "").replace(",", ".").strip()
                try:
                    return float(clean)
                except ValueError:
                    return 0.0
            elif col_name == "source":
                return p.source_type
            return 0

        self.filtered_products.sort(key=get_sort_key, reverse=self.sort_descending)
        self._render_rows()
