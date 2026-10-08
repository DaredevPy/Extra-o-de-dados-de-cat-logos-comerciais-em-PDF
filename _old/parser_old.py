import re
from typing import List, Set, Tuple, Optional
from core.models import ProductItem, PageData, ExtractionConfig

class CatalogParser:
    """
    Motor inteligente e configurável para análise e extração de produtos em catálogos.
    Suporta tabelas estruturadas, expressões regulares customizadas e heurísticas textuais.
    """
    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()

    def parse_document(self, pages: List[PageData]) -> List[ProductItem]:
        """Processa a lista de páginas e extrai os itens de produto de acordo com a configuração."""
        allowed_pages = self._get_allowed_pages(len(pages))
        all_products: List[ProductItem] = []
        seen_keys: Set[Tuple[int, str, str]] = set() # (página, código, preço) para evitar duplicatas

        item_counter = 1

        for page in pages:
            if page.page_number not in allowed_pages:
                continue

            page_products: List[ProductItem] = []

            # 1. Estratégia de Tabelas
            if self.config.mode in ("hybrid", "tables_only"):
                table_items = self._extract_from_tables(page)
                for item in table_items:
                    key = (item.page, item.code.upper().strip(), item.price.strip())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        item.index = item_counter
                        item_counter += 1
                        page_products.append(item)

            # 2. Estratégia de Texto (Regex / Heurística)
            if self.config.mode in ("hybrid", "text_only"):
                # Se for híbrido e a página já teve produtos de tabela, podemos ainda verificar se há mais
                # Se for text_only, processa todas as linhas
                text_items = self._extract_from_text(page)
                for item in text_items:
                    key = (item.page, item.code.upper().strip(), item.price.strip())
                    if key not in seen_keys:
                        seen_keys.add(key)
                        item.index = item_counter
                        item_counter += 1
                        page_products.append(item)

            all_products.extend(page_products)

        return all_products

    def _get_allowed_pages(self, total_pages: int) -> Set[int]:
        """Converte a string de intervalo de páginas (ex: '1-3, 5') para um conjunto de números inteiros."""
        raw_range = (self.config.page_range or "").strip().lower()
        if not raw_range or raw_range == "all" or raw_range == "todas":
            return set(range(1, total_pages + 1))

        allowed = set()
        chunks = raw_range.split(",")
        for chunk in chunks:
            chunk = chunk.strip()
            if "-" in chunk:
                parts = chunk.split("-")
                try:
                    start = int(parts[0])
                    end = int(parts[1])
                    for p in range(start, end + 1):
                        if 1 <= p <= total_pages:
                            allowed.add(p)
                except ValueError:
                    continue
            else:
                try:
                    p = int(chunk)
                    if 1 <= p <= total_pages:
                        allowed.add(p)
                except ValueError:
                    continue

        return allowed if allowed else set(range(1, total_pages + 1))

    def _extract_from_tables(self, page: PageData) -> List[ProductItem]:
        """Extrai produtos de tabelas identificadas pelo pdfplumber."""
        items: List[ProductItem] = []
        if not page.tables:
            return items

        for table in page.tables:
            if not table or len(table) < 2:
                continue

            # Tenta localizar a linha de cabeçalho
            code_col = -1
            desc_col = -1
            price_col = -1
            header_row_idx = -1

            for row_idx, row in enumerate(table[:3]):  # Verifica as primeiras 3 linhas como cabeçalho
                clean_row = [str(cell or "").strip().lower() for cell in row]
                
                c_col = self._find_column(clean_row, self.config.code_keywords)
                d_col = self._find_column(clean_row, self.config.desc_keywords)
                p_col = self._find_column(clean_row, self.config.price_keywords)

                # Se achou pelo menos código e preço ou código e descrição
                if c_col != -1 and (p_col != -1 or d_col != -1):
                    code_col = c_col
                    desc_col = d_col
                    price_col = p_col
                    header_row_idx = row_idx
                    break

            # Se não achou por cabeçalho, tenta inferir posições se tiver 3 ou mais colunas
            if code_col == -1 or price_col == -1:
                # Heurística padrão para 3 colunas: Col 0 = Código, Col 1 = Descrição, Col 2 = Preço
                if len(table[0]) >= 3:
                    code_col = 0
                    desc_col = 1
                    price_col = 2
                    header_row_idx = 0 if self._is_header_likely(table[0]) else -1
                elif len(table[0]) == 2:
                    code_col = 0
                    desc_col = 1
                    price_col = -1
                    header_row_idx = 0 if self._is_header_likely(table[0]) else -1

            start_row = header_row_idx + 1 if header_row_idx != -1 else 0

            for r_idx in range(start_row, len(table)):
                row = table[r_idx]
                if not row:
                    continue

                code_val = self._clean_text(row[code_col]) if 0 <= code_col < len(row) else ""
                desc_val = self._clean_text(row[desc_col]) if 0 <= desc_col < len(row) else ""
                price_val = self._clean_text(row[price_col]) if 0 <= price_col < len(row) else ""

                # Validações básicas
                if not code_val or len(code_val) < self.config.min_code_length:
                    continue

                # Se o preço não foi encontrado ou estiver vazio, tenta extrair da descrição
                if not price_val and desc_val:
                    match_price = re.search(self.config.price_regex, desc_val)
                    if match_price:
                        price_val = match_price.group(0)
                        # Remove o preço da descrição
                        desc_val = desc_val.replace(price_val, "").strip()

                if self.config.require_price and not price_val:
                    continue

                # Formata preço se necessário
                price_val = self._format_price(price_val)

                item = ProductItem(
                    index=0,
                    page=page.page_number,
                    code=code_val,
                    description=desc_val,
                    price=price_val,
                    raw_source=str(row),
                    source_type="Tabela"
                )
                items.append(item)

        return items

    def _extract_from_text(self, page: PageData) -> List[ProductItem]:
        """Extrai produtos de linhas de texto usando expressões regulares."""
        items: List[ProductItem] = []
        if not page.raw_text:
            return items

        lines = page.raw_text.splitlines()
        
        # Compila os regexes do usuário com fallback de segurança
        try:
            price_re = re.compile(self.config.price_regex, re.IGNORECASE)
        except Exception:
            price_re = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})", re.IGNORECASE)

        try:
            code_re = re.compile(self.config.code_regex, re.IGNORECASE)
        except Exception:
            code_re = re.compile(r"(?:(?:C[oó]d\.?|Ref\.?|Item|SKU|C[oó]digo)[:\s\.\-]*)?([A-Z0-9][A-Z0-9\.\-_/]{2,20})", re.IGNORECASE)

        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 5:
                continue

            # 1. Procura Preço na Linha
            price_match = price_re.search(line_str)
            if self.config.require_price and not price_match:
                continue

            price_str = price_match.group(0).strip() if price_match else ""

            # 2. Procura Código na Linha
            code_match = code_re.search(line_str)
            if not code_match:
                continue

            # Pega o grupo de captura relevante ou a correspondência inteira
            if code_match.groups() and code_match.group(1):
                code_str = code_match.group(1).strip()
            else:
                code_str = code_match.group(0).strip()

            if len(code_str) < self.config.min_code_length:
                continue

            # Evita falsos positivos onde o código pegou o próprio preço
            if price_str and (code_str in price_str or price_str in code_str):
                continue

            # 3. Extrai Descrição (Texto restante da linha)
            # Remove o código e o prefixo encontrado
            full_code_span = code_match.span()
            rem = line_str[:full_code_span[0]] + " " + line_str[full_code_span[1]:]

            # Remove o preço
            if price_match:
                p_span = price_re.search(rem)
                if p_span:
                    rem = rem[:p_span.start()] + " " + rem[p_span.end():]

            # Limpa caracteres de separação e espaços extras
            desc_str = re.sub(r"^[\s\-\:\.\/\|_]+|[\s\-\:\.\/\|_]+$", "", rem)
            desc_str = re.sub(r"\s{2,}", " ", desc_str).strip()

            # Se a descrição estiver vazia ou for muito curta, descarta
            if not desc_str:
                desc_str = "Sem descrição"

            price_str = self._format_price(price_str)

            item = ProductItem(
                index=0,
                page=page.page_number,
                code=code_str,
                description=desc_str,
                price=price_str,
                raw_source=line_str,
                source_type="Texto"
            )
            items.append(item)

        return items

    def _find_column(self, row_cells: List[str], keywords: List[str]) -> int:
        """Encontra o índice da coluna que contém uma das palavras-chave."""
        for idx, cell in enumerate(row_cells):
            for kw in keywords:
                if kw in cell:
                    return idx
        return -1

    def _is_header_likely(self, row: List[Optional[str]]) -> bool:
        """Verifica se a linha se parece com um cabeçalho de tabela."""
        text = " ".join([str(c or "").lower() for c in row])
        all_kw = self.config.code_keywords + self.config.desc_keywords + self.config.price_keywords
        return any(kw in text for kw in all_kw)

    def _clean_text(self, val: Optional[str]) -> str:
        """Limpa quebras de linha e múltiplos espaços de uma célula."""
        if val is None:
            return ""
        s = str(val).replace("\r", " ").replace("\n", " ")
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def _format_price(self, price_str: str) -> str:
        """Padroniza a apresentação do preço (garante prefixo R$ se for formato numérico brasileiro)."""
        if not price_str:
            return "-"
        price_clean = price_str.strip()
        if not price_clean.upper().startswith("R$") and re.search(r"\d+,\d{2}", price_clean):
            return f"R$ {price_clean}"
        return price_clean
