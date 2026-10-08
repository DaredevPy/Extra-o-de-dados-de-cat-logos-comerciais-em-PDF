import customtkinter as ctk
from typing import Callable, Optional
from core.models import ExtractionConfig

class SettingsPanel(ctk.CTkScrollableFrame):
    """
    Painel de controle e ajustes de regras de extração do PDF.
    Permite ao usuário customizar expressões regulares, estratégias, filtros de página
    e re-executar a extração a qualquer momento.
    """
    def __init__(self, master, on_reextract: Optional[Callable[[ExtractionConfig], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_reextract = on_reextract
        self._init_ui()

    def _init_ui(self):
        # Título da Seção
        lbl_title = ctk.CTkLabel(
            self,
            text="Ajustes e Regras de Extração",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#60A5FA"
        )
        lbl_title.pack(anchor="w", padx=15, pady=(10, 5))

        lbl_desc = ctk.CTkLabel(
            self,
            text="Ajuste os parâmetros abaixo para refinar os dados encontrados no PDF e clique no botão 'Re-executar Extração'.",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            wraplength=700,
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=15, pady=(0, 15))

        # CARD 1: Modo de Extração
        card_mode = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        card_mode.pack(fill="x", padx=15, pady=8)

        lbl_mode = ctk.CTkLabel(
            card_mode,
            text="1. Modo e Estratégia de Extração",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_mode.pack(anchor="w", padx=15, pady=(10, 5))

        self.var_mode = ctk.StringVar(value="hybrid")
        
        radio_hybrid = ctk.CTkRadioButton(
            card_mode,
            text="Híbrido Inteligente (Detecta Tabelas Estruturadas + Linhas de Texto)",
            variable=self.var_mode,
            value="hybrid"
        )
        radio_hybrid.pack(anchor="w", padx=25, pady=4)

        radio_tables = ctk.CTkRadioButton(
            card_mode,
            text="Apenas Tabelas Estruturadas (pdfplumber table extract)",
            variable=self.var_mode,
            value="tables_only"
        )
        radio_tables.pack(anchor="w", padx=25, pady=4)

        radio_text = ctk.CTkRadioButton(
            card_mode,
            text="Apenas Padrões de Linhas de Texto (Expressões Regulares)",
            variable=self.var_mode,
            value="text_only"
        )
        radio_text.pack(anchor="w", padx=25, pady=4)

        radio_evidence = ctk.CTkRadioButton(
            card_mode,
            text="Evidência (análise espacial multi-scanner + confiança + reconciliação)",
            variable=self.var_mode,
            value="evidence"
        )
        radio_evidence.pack(anchor="w", padx=25, pady=(4, 12))

        # CARD 2: Regras para Código do Produto
        card_code = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        card_code.pack(fill="x", padx=15, pady=8)

        lbl_code = ctk.CTkLabel(
            card_code,
            text="2. Regras para Identificação do Código do Produto",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_code.pack(anchor="w", padx=15, pady=(10, 5))

        # Preset de Código
        preset_frame_code = ctk.CTkFrame(card_code, fg_color="transparent")
        preset_frame_code.pack(fill="x", padx=15, pady=4)
        
        lbl_preset_code = ctk.CTkLabel(preset_frame_code, text="Modelos Prontos:", font=ctk.CTkFont(size=12))
        lbl_preset_code.pack(side="left", padx=(0, 10))

        self.combo_code_preset = ctk.CTkComboBox(
            preset_frame_code,
            values=[
                "Padrão (Cód, Ref, SKU ou Alfanumérico)",
                "Apenas Números (ex: 100234)",
                "Alfanumérico com Hífen (ex: ABC-1001)",
                "Qualquer Código Alfanumérico (3 a 20 chars)"
            ],
            width=350,
            command=self._on_code_preset_changed
        )
        self.combo_code_preset.pack(side="left")

        # Entrada Regex de Código
        lbl_code_regex = ctk.CTkLabel(card_code, text="Expressão Regular (Regex) do Código:", font=ctk.CTkFont(size=12))
        lbl_code_regex.pack(anchor="w", padx=15, pady=(8, 2))

        self.entry_code_regex = ctk.CTkEntry(
            card_code,
            height=34,
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.entry_code_regex.pack(fill="x", padx=15, pady=(0, 8))
        self.entry_code_regex.insert(0, r"(?:(?:C[oó]d\.?|Ref\.?|Item|SKU|C[oó]digo)[:\s\.\-]*)?([A-Z0-9][A-Z0-9\.\-_/]{2,20})")

        # Tamanho mínimo do código
        min_len_frame = ctk.CTkFrame(card_code, fg_color="transparent")
        min_len_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        lbl_min_len = ctk.CTkLabel(min_len_frame, text="Tamanho mínimo de caracteres do código:", font=ctk.CTkFont(size=12))
        lbl_min_len.pack(side="left", padx=(0, 10))

        self.spin_min_code = ctk.CTkEntry(min_len_frame, width=60, height=30)
        self.spin_min_code.pack(side="left")
        self.spin_min_code.insert(0, "3")

        # CARD 3: Regras para Preço
        card_price = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        card_price.pack(fill="x", padx=15, pady=8)

        lbl_price = ctk.CTkLabel(
            card_price,
            text="3. Regras para Identificação do Preço",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_price.pack(anchor="w", padx=15, pady=(10, 5))

        # Preset de Preço
        preset_frame_price = ctk.CTkFrame(card_price, fg_color="transparent")
        preset_frame_price.pack(fill="x", padx=15, pady=4)
        
        lbl_preset_price = ctk.CTkLabel(preset_frame_price, text="Modelos Prontos:", font=ctk.CTkFont(size=12))
        lbl_preset_price.pack(side="left", padx=(0, 10))

        self.combo_price_preset = ctk.CTkComboBox(
            preset_frame_price,
            values=[
                "Padrão Brasileiro (com ou sem R$)",
                "Exigir R$ obrigatório (R$ 0,00)",
                "Apenas Decimais com Vírgula (0,00)",
                "Formato Decimal com Ponto (0.00)"
            ],
            width=350,
            command=self._on_price_preset_changed
        )
        self.combo_price_preset.pack(side="left")

        # Entrada Regex de Preço
        lbl_price_regex = ctk.CTkLabel(card_price, text="Expressão Regular (Regex) do Preço:", font=ctk.CTkFont(size=12))
        lbl_price_regex.pack(anchor="w", padx=15, pady=(8, 2))

        self.entry_price_regex = ctk.CTkEntry(
            card_price,
            height=34,
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.entry_price_regex.pack(fill="x", padx=15, pady=(0, 8))
        self.entry_price_regex.insert(0, r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")

        self.var_require_price = ctk.BooleanVar(value=True)
        self.chk_require_price = ctk.CTkCheckBox(
            card_price,
            text="Exigir preço obrigatório para validar o produto (descarta linhas sem preço)",
            variable=self.var_require_price
        )
        self.chk_require_price.pack(anchor="w", padx=15, pady=(0, 12))

        # CARD 4: Filtro de Páginas e Palavras de Tabela
        card_pages = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        card_pages.pack(fill="x", padx=15, pady=8)

        lbl_pages = ctk.CTkLabel(
            card_pages,
            text="4. Filtro de Páginas",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_pages.pack(anchor="w", padx=15, pady=(10, 5))

        lbl_page_hint = ctk.CTkLabel(
            card_pages,
            text="Digite 'all' para todas as páginas ou especifique intervalos como: '1-3, 5' para extrair apenas páginas específicas.",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF"
        )
        lbl_page_hint.pack(anchor="w", padx=15, pady=(0, 6))

        self.entry_pages = ctk.CTkEntry(card_pages, height=34, width=250)
        self.entry_pages.pack(anchor="w", padx=15, pady=(0, 12))
        self.entry_pages.insert(0, "all")

        # BOTÃO PRINCIPAL DE RE-EXECUÇÃO
        action_box = ctk.CTkFrame(self, fg_color="transparent")
        action_box.pack(fill="x", padx=15, pady=(15, 20))

        self.btn_reextract = ctk.CTkButton(
            action_box,
            text="🔄 Re-executar Extração com os Novos Ajustes",
            height=46,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._trigger_reextraction
        )
        self.btn_reextract.pack(fill="x", pady=5)

        self.btn_reset = ctk.CTkButton(
            action_box,
            text="Restaurar Ajustes Padrão",
            height=32,
            fg_color="#374151",
            hover_color="#4B5563",
            command=self._reset_defaults
        )
        self.btn_reset.pack(anchor="e", pady=5)

    def _on_code_preset_changed(self, choice: str):
        self.entry_code_regex.delete(0, "end")
        if choice == "Apenas Números (ex: 100234)":
            self.entry_code_regex.insert(0, r"\b(\d{4,14})\b")
        elif choice == "Alfanumérico com Hífen (ex: ABC-1001)":
            self.entry_code_regex.insert(0, r"\b([A-Z]{2,4}-\d{3,6})\b")
        elif choice == "Qualquer Código Alfanumérico (3 a 20 chars)":
            self.entry_code_regex.insert(0, r"\b([A-Z0-9\-_]{3,20})\b")
        else:
            self.entry_code_regex.insert(0, r"(?:(?:C[oó]d\.?|Ref\.?|Item|SKU|C[oó]digo)[:\s\.\-]*)?([A-Z0-9][A-Z0-9\.\-_/]{2,20})")

    def _on_price_preset_changed(self, choice: str):
        self.entry_price_regex.delete(0, "end")
        if choice == "Exigir R$ obrigatório (R$ 0,00)":
            self.entry_price_regex.insert(0, r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})")
        elif choice == "Apenas Decimais com Vírgula (0,00)":
            self.entry_price_regex.insert(0, r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")
        elif choice == "Formato Decimal com Ponto (0.00)":
            self.entry_price_regex.insert(0, r"(?:\$\s*)?(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})")
        else:
            self.entry_price_regex.insert(0, r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")

    def _reset_defaults(self):
        self.var_mode.set("hybrid")
        self.combo_code_preset.set("Padrão (Cód, Ref, SKU ou Alfanumérico)")
        self._on_code_preset_changed("Padrão (Cód, Ref, SKU ou Alfanumérico)")
        self.combo_price_preset.set("Padrão Brasileiro (com ou sem R$)")
        self._on_price_preset_changed("Padrão Brasileiro (com ou sem R$)")
        self.spin_min_code.delete(0, "end")
        self.spin_min_code.insert(0, "3")
        self.var_require_price.set(True)
        self.entry_pages.delete(0, "end")
        self.entry_pages.insert(0, "all")

    def get_config(self) -> ExtractionConfig:
        try:
            min_len = int(self.spin_min_code.get().strip())
        except ValueError:
            min_len = 3

        return ExtractionConfig(
            mode=self.var_mode.get(),
            code_regex=self.entry_code_regex.get().strip(),
            price_regex=self.entry_price_regex.get().strip(),
            min_code_length=min_len,
            require_price=self.var_require_price.get(),
            page_range=self.entry_pages.get().strip() or "all"
        )

    def _trigger_reextraction(self):
        if self.on_reextract:
            cfg = self.get_config()
            self.on_reextract(cfg)
