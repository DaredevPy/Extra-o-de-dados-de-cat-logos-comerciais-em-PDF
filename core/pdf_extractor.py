import os
import re
from collections import Counter
from typing import List, Callable, Optional
import pdfplumber

from core.models import PageData


def _rev_norm(t: str) -> str:
    """Forma normalizada invertida do token (para detectar texto espelhado)."""
    return re.sub(r"[^a-zA-Z0-9]", "", t)[::-1].lower()


def strip_mirror_edge_words(words: List[dict], page_width: float) -> List[dict]:
    """Remove tokens espelhados das bordas da página.

    Vários catálogos Avon desenham ARTE ESPELHADA INVERTIDA nas margens X
    (ex.: 'weneR' = 'Renew', 'SIAICAF' = 'FACIAIS', 'animativ'='vitamina'),
    em tamanho pequeno, sem hierarquia de texto. Esses tokens caem na descrição
    e viram lixo. A regra é AUTO-REFERENCIAL e precisa:
      * o token está na margem X externa (x1<=72 ou x0>=largura-50);
      * tamanho pequeno (<8pt);
      * o REVERSO do token existe como palavra normal na PRÓPRIA página
        (twin), então nunca ataca conteúdo real (ex.: código/preço/página 5
        da CASA, que tem texto legítimo em x>=500 mas sem twin reverso)."""
    if not words:
        return words
    forms = Counter(_rev_norm(w["text"]) for w in words
                    if len(_rev_norm(w["text"])) >= 2)
    right_edge = max(0.0, page_width - 50) if page_width else 1e9
    out = []
    for w in words:
        t = w["text"]
        rt = _rev_norm(t)
        if len(rt) >= 2 and rt != t.lower():
            edge = w["x1"] <= 72 or w["x0"] >= right_edge
            small = (w.get("size", 0) or 0) < 8.0
            if edge and small and rt in forms:
                continue
        out.append(w)
    return out

def _is_visible_stroke_color(color) -> bool:
    """Cor de traço visível? Branco (inclusive CMYK 0,0,0,0) é invisível em
    fundo branco e não pode marcar preço como riscado."""
    if color is None:
        return True  # sem cor explícita = preto do padrão do PDF
    if isinstance(color, (int, float)):
        return float(color) < 0.98
    if isinstance(color, (list, tuple)):
        vals = [float(v) for v in color if isinstance(v, (int, float))]
        if not vals:
            return True
        if len(vals) == 4:  # CMYK
            c, m, y, k = vals
            return not (abs(c) < 0.02 and abs(m) < 0.02
                        and abs(y) < 0.02 and abs(k) < 0.02)
        return not all(abs(v - 1.0) < 0.02 for v in vals)
    return True


def extract_price_strokes(page, max_length: float = 220.0,
                          limit: int = 4000) -> List[dict]:
    """Traços diagonais curtos e visíveis — candidatos a riscar preço.

    Guarda apenas o necessário para a checagem geométrica: extremos em
    coordenadas de topo (y cresce para baixo), espessura e cor. Segmentos
    longos (swooshes/logos) são descartados na origem para não inflar a
    memória dos catálogos grandes."""
    out: List[dict] = []
    try:
        objects = list(page.lines or []) + list(page.curves or [])
    except Exception:
        return out
    for obj in objects:
        try:
            if obj.get("stroked") is False:
                continue
            pts = obj.get("pts") or []
            if len(pts) >= 2:
                x0, y0 = float(pts[0][0]), float(pts[0][1])
                x1, y1 = float(pts[-1][0]), float(pts[-1][1])
            else:
                x0, x1 = obj.get("x0"), obj.get("x1")
                y0, y1 = obj.get("top"), obj.get("bottom")
                if None in (x0, x1, y0, y1):
                    continue
                x0, x1, y0, y1 = float(x0), float(x1), float(y0), float(y1)
            dx, dy = abs(x1 - x0), abs(y1 - y0)
            if dx < 4.0 or dy < 3.0:
                continue  # riscado é diagonal; horizontal/vertical não conta
            length = (dx * dx + dy * dy) ** 0.5
            if length < 8.0 or length > max_length:
                continue
            linewidth = float(obj.get("linewidth") or 0.0)
            if linewidth <= 0.0:
                continue
            color = obj.get("stroking_color")
            if not _is_visible_stroke_color(color):
                continue
            out.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1,
                        "linewidth": round(linewidth, 2),
                        "color": list(color) if isinstance(color, (list, tuple)) else color})
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out


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

                # Imagens de produto (rects normalizados; imagens de fundo que
                # cobrem a página quase inteira são descartadas como "fundo")
                width = float(page.width or 612)
                height = float(page.height or 792)
                images = []
                try:
                    for raw in (page.images or []):
                        x0 = max(0.0, float(raw.get("x0", 0)))
                        x1 = min(width, float(raw.get("x1", 0)))
                        top = max(0.0, float(raw.get("top", 0)))
                        bottom = min(height, float(raw.get("bottom", 0)))
                        area = max(0.0, (x1 - x0) * (bottom - top))
                        if area > 0 and area / (width * height) < 0.55:
                            images.append({"x0": x0, "x1": x1, "top": top,
                                           "bottom": bottom, "area": area})
                except Exception:
                    images = []

                # Arte espelhada invertida nas bordas NÃO é texto de produto:
                # remove da análise espacial (descrição/regiões) ANTES de tudo.
                try:
                    words = strip_mirror_edge_words(words, page_width=width)
                except Exception:
                    pass

                try:
                    strokes = extract_price_strokes(page)
                except Exception:
                    strokes = []

                page_data = PageData(
                    page_number=idx,
                    raw_text=text,
                    tables=tables or [],
                    words=words or [],
                    images=images,
                    strokes=strokes
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
