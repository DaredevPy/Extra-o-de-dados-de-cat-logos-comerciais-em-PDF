import os
from typing import List, Callable, Optional
import pdfplumber

from core.models import PageData

class PDFDocumentReader:
    """
    Lê e armazena em cache o conteúdo bruto de texto e tabelas de um documento PDF.
    Isso permite re-executar os filtros e regras de extração instantaneamente sem reler o disco.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        self.total_pages = 0
        self.pages_data: List[PageData] = []
        self.is_loaded = False

    @property
    def file_size_formatted(self) -> str:
        size = self.file_size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def load_document(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[PageData]:
        """Extrai o texto bruto e tabelas de todas as páginas do PDF."""
        self.pages_data.clear()
        
        with pdfplumber.open(self.file_path) as pdf:
            self.total_pages = len(pdf.pages)
            for idx, page in enumerate(pdf.pages, start=1):
                if progress_callback:
                    progress_callback(idx, self.total_pages, f"Lendo página {idx} de {self.total_pages}...")
                
                # Extrai texto bruto da página
                text = page.extract_text(layout=False) or ""
                
                # Extrai tabelas se houver
                try:
                    tables = page.extract_tables()
                except Exception:
                    tables = []

                try:
                    words = page.extract_words()
                except Exception:
                    words = []

                # Anexa o tamanho médio da fonte por palavra (ajuda a identificar títulos de produto)
                try:
                    chars = page.chars
                    for w in words:
                        sizes = [c["size"] for c in chars
                                 if c["x0"] >= w["x0"] - 1 and c["x1"] <= w["x1"] + 1
                                 and c["top"] >= w["top"] - 2 and c["bottom"] <= w["bottom"] + 2]
                        w["size"] = sum(sizes) / len(sizes) if sizes else 0.0
                except Exception:
                    pass

                page_data = PageData(
                    page_number=idx,
                    raw_text=text,
                    tables=tables or [],
                    words=words or []
                )
                self.pages_data.append(page_data)

        self.is_loaded = True
        if progress_callback:
            progress_callback(self.total_pages, self.total_pages, "Carregamento concluído!")
            
        return self.pages_data

    def get_full_raw_text(self, selected_page: Optional[int] = None) -> str:
        """Retorna o texto bruto completo formatado com divisores de página ou de uma página específica."""
        if not self.pages_data:
            return "Nenhum dado extraído ainda."

        if selected_page is not None and selected_page > 0:
            for p in self.pages_data:
                if p.page_number == selected_page:
                    return f"=== PÁGINA {p.page_number} ===\n\n{p.raw_text}"
            return f"Página {selected_page} não encontrada."

        # Todas as páginas
        output_chunks = []
        for p in self.pages_data:
            separator = f"\n{'=' * 25} PÁGINA {p.page_number} de {self.total_pages} {'=' * 25}\n"
            output_chunks.append(separator)
            output_chunks.append(p.raw_text.strip() if p.raw_text else "[Página sem texto detectável]")
            output_chunks.append("\n")

        return "\n".join(output_chunks)
