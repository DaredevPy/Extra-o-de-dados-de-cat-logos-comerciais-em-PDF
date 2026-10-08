from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ProductItem:
    index: int
    page: int
    code: str
    description: Optional[str]
    price: str
    price_extra: str = ""
    raw_source: str = ""
    source_type: str = "auto"  # 'tabela' ou 'texto'
    confidence: int = 0
    status: str = ""  # ALTA, MEDIA ou REVISAR
    debug: str = ""

    def to_dict(self):
        return {
            "Item": self.index,
            "Página": self.page,
            "Código": self.code,
            "Descrição": self.description,
            "Preço": self.price,
            "Preço 2": self.price_extra or "-",
            "Origem": self.source_type,
            "Confiança": self.confidence,
            "Status": self.status
        }

@dataclass
class PageData:
    page_number: int
    raw_text: str
    tables: List[List[List[Optional[str]]]] = field(default_factory=list)
    words: List[dict] = field(default_factory=list)

@dataclass
class ExtractionConfig:
    mode: str = "hybrid"  # 'hybrid', 'tables_only', 'text_only'
    code_regex: str = r"(?:(?:C[oó]d\.?|Ref\.?|Item|SKU|C[oó]digo)[:\s\.\-]*)?([A-Z0-9][A-Z0-9\.\-_/]{2,20})"
    price_regex: str = r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
    min_code_length: int = 3
    require_price: bool = True
    page_range: str = "all"
    
    code_keywords: List[str] = field(default_factory=lambda: [
        "código", "codigo", "cod", "ref", "referência", "referencia", "item", "sku"
    ])
    desc_keywords: List[str] = field(default_factory=lambda: [
        "descrição", "descricao", "desc", "produto", "especificação", "especificacao", "nome", "detalhe", "mercadoria"
    ])
    price_keywords: List[str] = field(default_factory=lambda: [
        "preço", "preco", "valor", "unitário", "unitario", "r$", "vlr", "tabela"
    ])
