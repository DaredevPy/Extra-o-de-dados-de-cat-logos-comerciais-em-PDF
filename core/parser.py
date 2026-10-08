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
        if self.config.mode == "evidence":
            from core.pipeline import extract_catalog
            allowed = self._get_allowed_pages(len(pages))
            filtered = [p for p in pages if p.page_number in allowed]
            items, _ = extract_catalog(filtered, self.config, include_unpriced=True)
            return items

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

                # Código deve conter dígito e o preço deve ter formato monetário
                if not re.search(r"\d", code_val):
                    continue
                if price_val and not re.search(r"\d+,\d{2}", price_val):
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
        """Extrai produtos de texto: primeiro parse forte linha a linha, depois associação espacial."""
        items: List[ProductItem] = []
        if not page.raw_text and not page.words:
            return items

        consumed_code_positions: Set[Tuple[int, int]] = set()

        # 1. Caminho espacial: código, descrição e preço em blocos separados
        items: List[ProductItem] = []
        page_codes: Set[str] = set()
        if page.words:
            spatial_items = self._extract_spatial(page, consumed_code_positions)
            items.extend(spatial_items)
            page_codes = {it.code for it in spatial_items}

        # 2. Caminho forte: linha única contendo código + preço (só para códigos novos)
        line_items = self._extract_from_text_lines(page)
        for it in line_items:
            if it.code not in page_codes:
                items.append(it)
                page_codes.add(it.code)

        return items

    def _extract_from_text_lines(self, page: PageData) -> List[ProductItem]:
        """Extrai produtos no formato clássico em uma única linha: código - descrição - preço."""
        items: List[ProductItem] = []
        if not page.raw_text:
            return items

        lines = page.raw_text.splitlines()

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

            price_match = price_re.search(line_str)
            if self.config.require_price and not price_match:
                continue

            price_str = price_match.group(0).strip() if price_match else ""

            code_match = code_re.search(line_str)
            if not code_match:
                continue

            if code_match.groups() and code_match.group(1):
                code_str = code_match.group(1).strip()
            else:
                code_str = code_match.group(0).strip()

            if len(code_str) < self.config.min_code_length:
                continue

            if price_str and (code_str in price_str or price_str in code_str):
                continue

            # Caminho forte só aceita código com dígito (evita pular "compra", "org", etc.)
            if not re.search(r"\d", code_str):
                continue

            # Restringe ao formato de código comercial (6 dígitos ou SKU alfanumérico)
            if not self._is_code_candidate(code_str):
                continue

            full_code_span = code_match.span()
            rem = line_str[:full_code_span[0]] + " " + line_str[full_code_span[1]:]

            if price_match:
                p_span = price_re.search(rem)
                if p_span:
                    rem = rem[:p_span.start()] + " " + rem[p_span.end():]

            desc_str = re.sub(r"^[\s\-\:\.\/\|_]+|[\s\-\:\.\/\|_]+$", "", rem)
            desc_str = re.sub(r"\s{2,}", " ", desc_str).strip()

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
                source_type="Texto",
                confidence=95,
                status="ALTA",
                debug=f"linha='{line_str}'"
            )
            items.append(item)

        return items

    # ---------------- Associação espacial por coordenadas ----------------

    def _is_code_candidate(self, token: str) -> bool:
        t = token.strip()
        if re.fullmatch(r"\d{6}", t):
            return True
        if re.fullmatch(r"[A-Za-z]{2,4}-?\d{3,}", t):
            return True
        return False

    def _is_price_token(self, token: str) -> bool:
        return bool(re.fullmatch(r"(?:R\$)?(?:\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(CA?|O)?", token.strip()))

    def _price_token_value(self, token: str) -> str:
        return re.sub(r"^R\$", "", re.sub(r"(CA?|O)$", "", token.strip()))

    def _extract_spatial(self, page: PageData, consumed: Set[Tuple[int, int]]) -> List[ProductItem]:
        """Associa código ↔ descrição ↔ preço usando proximidade espacial das palavras."""
        items: List[ProductItem] = []
        words = page.words or []
        if not words:
            return items

        def center(w):
            return ((w["x0"] + w["x1"]) / 2.0, (w["top"] + w["bottom"]) / 2.0)

        marker_tops = [w["top"] for w in words if "__" in w["text"] or "BBEE" in w["text"]]
        marker_blobs = [w["text"] for w in words if "__" in w["text"] or "BBEE" in w["text"]]
        code_words = [w for w in words if self._is_code_candidate(w["text"])]
        # Descarta falsos códigos que aparecem embutidos na marca d'água do arquivo
        code_words = [w for w in code_words
                      if not any(w["text"] in blob for blob in marker_blobs)]
        price_words = [w for w in words if self._is_price_token(w["text"])]

        # Conta quantos códigos têm preço próximo: mede estrutura de catálogo da página
        codable = 0
        for cw in code_words:
            if any(self._price_near(cw, pw) and self._has_currency_marker(pw, words)
                   for pw in price_words):
                codable += 1

        # Agrupa códigos em "runs" (bloco visual contínuo de códigos do mesmo produto)
        sorted_codes = sorted(code_words, key=lambda w: (round(w["top"] / 10), w["x0"]))
        runs: List[List[dict]] = []
        for w in sorted_codes:
            for r in runs:
                if w["top"] - r[-1]["bottom"] <= 80 and abs(w["x0"] - r[0]["x0"]) <= 400:
                    r.append(w)
                    break
            else:
                runs.append([w])

        # Pré-atribuição de preço por run: cada preço usado uma única vez por página,
        # preferindo preço logo acima do bloco (até 60px) ou dentro do bloco.
        used_prices: Set[int] = set()
        run_price: dict = {}
        for r in runs:
            r_top = min(w["top"] for w in r)
            r_bottom = max(w["bottom"] for w in r)
            r_x0 = min(w["x0"] for w in r)
            r_x1 = max(w["x1"] for w in r)
            cands = []
            for i, pw in enumerate(price_words):
                if i in used_prices:
                    continue
                if not self._has_currency_marker(pw, words):
                    continue
                px, py = center(pw)
                if not (r_x0 - 260 <= px <= r_x1 + 260):
                    continue
                if r_top - 60 <= py <= r_bottom:
                    cost = 0
                elif py < r_top:
                    cost = r_top - py
                else:
                    cost = (py - r_bottom) + 30
                cands.append((cost, abs(px - (r_x0 + r_x1)/2.0), i, pw))
            if cands:
                cands.sort(key=lambda t: (t[0], t[1]))
                run_price[id(r)] = (cands[0][2], cands[0][3])
                used_prices.add(cands[0][2])

        for cw in code_words:
            cx, cy = center(cw)

            # Rejeita candidatos na mesma faixa vertical da marca d'água do arquivo
            if any(abs(cy - mt) < 8 for mt in marker_tops):
                continue

            # Preço principal: atribuído ao run do código
            best_price = None
            best_bucket = 2
            best_pdist = 1e9
            # Tenta preço por run, mas escolhe o preço mais próximo horizontalmente ao código
            run_cands = []
            for r in runs:
                if cw in r and id(r) in run_price:
                    idx_p, rp = run_price[id(r)]
                    # considera também outros preços com mesmo 'custo' implícito? mas já temos rp; vamos buscar melhor rp para este código
                    # mas run_price já tem um; melhor buscar na faixa do run os preços ordenados por distância ao código
                    r_top = min(w["top"] for w in r); r_bottom = max(w["bottom"] for w in r); r_x0 = min(w["x0"] for w in r); r_x1 = max(w["x1"] for w in r)
                    for pw in price_words:
                        if not self._has_currency_marker(pw, words): continue
                        px,py=center(pw)
                        if not (r_x0-260<=px<=r_x1+260): continue
                        if r_top-60<=py<=r_bottom or py>r_bottom:  # aceita na faixa inferior típica
                            d = ((px-cx)**2+(py-cy)**2)**0.5
                            run_cands.append((d,pw))
                    if run_cands:
                        run_cands.sort(key=lambda t:t[0])
                        best_price = run_cands[0][1]
                        px,py=center(best_price)
                        best_pdist=((px-cx)**2+(py-cy)**2)**0.5
                        best_bucket = 0 if best_pdist<=30 else (1 if best_pdist<=150 else 2)
                        break

            if best_price is None:
                # Fallback: método antigo por proximidade individual
                for pw in price_words:
                    if pw is cw:
                        continue
                    if not self._price_near(cw, pw):
                        continue
                    if not self._has_currency_marker(pw, words):
                        continue
                    b = self._price_dist_bucket(cw, pw)
                    px, py = center(pw)
                    d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    if b < best_bucket or (b == best_bucket and d < best_pdist):
                        best_bucket = b
                        best_pdist = d
                        best_price = pw

            if best_price is None:
                # Sem evidência de preço: descarta (não gera registro)
                continue

            # Segundo quadrado de preço (mesma coluna, valor diferente)
            price_extra = self._second_price_near(cw, best_price, words)

            # Descrição: linhas próximas ao quadrado do preço (referência) na coluna do produto
            desc_text, desc_dist = self._desc_near(cw, best_price, words)

            if not desc_text:
                # Sem evidência de descrição: mantém registro para revisão, sem inventar
                score = 30 + (25 if best_bucket == 0 else (12 if best_bucket == 1 else 8))
                items.append(ProductItem(
                    index=0, page=page.page_number, code=cw["text"],
                    description=None, price=self._format_price(self._price_token_value(best_price["text"])),
                    price_extra=price_extra,
                    raw_source=cw["text"], source_type="Texto",
                    confidence=min(score, 69), status="REVISAR",
                    debug=f"p{page.page_number} code={cw['text']} dist_preco={best_pdist:.0f}px desc=ausente regras=formato_codigo,preco_proximo"
                ))
                continue

            # Pontuação determinística
            rules = ["formato_codigo"]
            score = 30
            if best_bucket == 0:
                score += 25; rules.append("preco_muito_proximo")
            elif best_bucket == 1:
                score += 15; rules.append("preco_proximo")
            else:
                score += 8; rules.append("preco_mesma_coluna_bloco")
            if desc_dist <= 50:
                score += 20; rules.append("desc_muito_proxima")
            else:
                score += 10; rules.append("desc_proxima")
            if best_bucket == 0:
                score += 15; rules.append("mesma_faixa_vertical")
            if codable >= 3:
                score += 10; rules.append("pagina_com_estrutura_grid")
            score = min(score, 100)

            status = "ALTA" if score >= 90 else ("MEDIA" if score >= 70 else "REVISAR")
            debug = (f"p{page.page_number} code={cw['text']} dist_preco={best_pdist:.0f}px "
                     f"dist_desc={desc_dist:.0f}px regras={','.join(rules)}")
            items.append(ProductItem(
                index=0, page=page.page_number, code=cw["text"],
                description=desc_text,
                price=self._format_price(self._price_token_value(best_price["text"])),
                price_extra=price_extra,
                raw_source=cw["text"], source_type="Texto",
                confidence=score, status=status, debug=debug
            ))

        # Propaga a melhor descrição do bloco (run) para códigos sem descrição
        items_by_code = {}
        for it in items:
            items_by_code.setdefault(it.code, it)
        for r in runs:
            run_items = [items_by_code.get(w["text"]) for w in r]
            run_items = [x for x in run_items if x]
            titled = [x for x in run_items
                      if x.description and not self._looks_like_marketing(x.description)
                      and not self._looks_like_badge(x.description)]
            if titled:
                best = max(titled, key=lambda x: x.confidence)
                for x in run_items:
                    if not x.description or self._looks_like_marketing(x.description) or self._looks_like_badge(x.description):
                        x.description = best.description
                        x.debug += " | desc=propagada_do_bloco"

        return items

    def _looks_like_marketing(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ("hidrat", "vitami", "cuida", "hidrata", "cuida da", "hidratai", "passa", "protege", "estimula"))

    def _looks_like_badge(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ("lançamento", "limitada", "edição", "off", "grátis", "novo", "nova", "lan�amento", "edi��o", "gr�tis"))

    def _price_near(self, cw, pw) -> bool:
        cx, cy = (cw["x0"]+cw["x1"])/2, (cw["top"]+cw["bottom"])/2
        px, py = (pw["x0"]+pw["x1"])/2, (pw["top"]+pw["bottom"])/2
        same_row = abs(py - cy) <= 30 and abs(px - cx) <= 260
        near = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 <= 150
        same_col = abs(px - cx) <= 170 and abs(py - cy) <= 500
        return same_row or near or same_col

    def _price_dist_bucket(self, cw, pw) -> int:
        cx, cy = (cw["x0"]+cw["x1"])/2, (cw["top"]+cw["bottom"])/2
        px, py = (pw["x0"]+pw["x1"])/2, (pw["top"]+pw["bottom"])/2
        if abs(py - cy) <= 30 and abs(px - cx) <= 260:
            return 0  # mesma linha
        if ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 <= 150:
            return 1  # próximo
        return 2  # mesma coluna (bloco)

    def _has_currency_marker(self, price_word, words) -> bool:
        if price_word["text"].startswith("R$"):
            return True
        px, py = (price_word["x0"]+price_word["x1"])/2, (price_word["top"]+price_word["bottom"])/2
        for w in words:
            if w["text"].startswith("R$"):
                wx, wy = (w["x0"]+w["x1"])/2, (w["top"]+w["bottom"])/2
                if abs(wy - py) <= 14 and abs(wx - px) <= 60:
                    return True
        return False

    def _desc_near(self, code_w, price_w, words) -> Tuple[Optional[str], float]:
        """Descrição ancorada no QUADRADO DO PREÇO (referência) + coluna do produto.

        O preço é a referência: recolhe as linhas mais próximas em volta do quadrado
        (acima = títulos, abaixo/ao lado = especificações), dentro da coluna do produto,
        ignorando texto da coluna vizinha e texto vertical/espelhado das imagens.
        """
        p_top, p_bot = price_w["top"], price_w["bottom"]
        p_x0, p_x1 = price_w["x0"], price_w["x1"]
        p_cy = (p_top + p_bot) / 2.0
        c_top, c_bot = code_w["top"], code_w["bottom"]
        c_cy = (c_top + c_bot) / 2.0

        col = self._column_bounds(words)
        cx = (code_w["x0"] + code_w["x1"]) / 2.0
        col_match = next(((lo, hi) for lo, hi in col if lo - 15 <= cx <= hi + 15), None)
        if col_match is None:
            col_match = (max(0, cx - 260), cx + 340)
        c_lo, c_hi = col_match

        # Exclui os rótulos do próprio quadrado de preço (ex: 'CADA PAR', 'POR')
        price_labels = self._price_labels_near(price_w, words)

        top_win = min(p_top, c_top)
        bot_win = max(p_bot, c_bot)

        lines: dict = {}
        for w in words:
            t = w["text"].strip()
            if not t:
                continue
            # Conjunções/separadores de especificações e dígitos soltos ('8', '3')
            if len(t) == 1:
                if t.isdigit():
                    pass
                elif t not in ("a", "e", "o", "x", "-", "|", "."):
                    continue
            elif t[0] in ":,.|*;":
                # Tokens de espelhamento começam com pontuação
                continue
            else:
                has_digit = any(ch.isdigit() for ch in t)
                # Ruído: texto vertical/espelhado das imagens (ex: ':setoP', 'arfinoc', 'LEVRAM',
                # '1166//0077//2266'): palavras altas e estreitas (altura >= 13px e largura < 70% da altura).
                if (w["bottom"] - w["top"]) >= 13 and (w["x1"] - w["x0"]) < (w["bottom"] - w["top"]) * 0.7:
                    continue
                # Fragmentos de letras espelhadas no limite da imagem (ex: 'tiK', 'ed' têm
                # largura < altura) - palavras reais curtas como 'de'/'da' (~1:1) passam.
                if not has_digit and (w["x1"] - w["x0"]) < (w["bottom"] - w["top"]):
                    continue
                # Caps curtas (1-3 letras) fora do quadrado de preço são ruído espelhado
                # (ex: 'C', 'A', 'R', 'DA', 'PA' na área de especificações)
                if (w["x1"] - w["x0"]) < 24 and w["text"].isupper() and len(t) <= 3:
                    continue
            if self._is_code_candidate(t) or self._is_price_token(t):
                continue
            if t in price_labels:
                continue
            # Restringe à coluna do produto (descarta a coluna vizinha)
            if not (c_lo - 10 <= w["x0"] <= c_hi + 10):
                continue
            # Janela vertical ao redor do PREÇO: até 120px acima (títulos) e 280px abaixo
            # (especificações). Não alcança faixas/banners distantes no topo da página.
            if not (p_top - 120 <= w["top"] <= bot_win + 280):
                continue
            key = round(w["top"] / 6)
            lines.setdefault(key, []).append(w)

        kept = []
        for key, lst in lines.items():
            lst = sorted(lst, key=lambda w: w["x0"])
            # Separa palavras com grande espaço horizontal: são itens vizinhos na
            # MESMA linha física (ex: dims do produto + título do próximo item).
            segs = [[]]
            prev_x1 = None
            for w in lst:
                if prev_x1 is not None and w["x0"] - prev_x1 > 20:
                    segs.append([])
                segs[-1].append(w)
                prev_x1 = w["x1"] if prev_x1 is None else max(prev_x1, w["x1"])
            for seg in segs:
                text = " ".join(x["text"] for x in seg)
                if not self._desc_line_ok(text):
                    continue
                # Linhas de tom/variação ('02 pts', 'CO BR' etc) são descartadas, mas
                # linhas de especificação com cm/%/x (composição/dimensões) são válidas.
                if self._is_tone_line(text) and not self._looks_like_spec(text):
                    continue
                if self._looks_like_badge(text) or self._looks_like_marketing(text):
                    continue
                line_top = min(x["top"] for x in seg)
                line_x0 = min(x["x0"] for x in seg)
                line_x1 = max(x["x1"] for x in seg)
                d_p = abs(line_top - p_cy)
                sizes = [x.get("size", 0.0) for x in seg]
                avg = sum(sizes) / len(sizes) if sizes else 0.0
                n_words = len(text.split())
                is_title = n_words <= 9 and not text.endswith(".") and any(
                    wd[0:1].isupper() for wd in text.split())
                rank = 0 if is_title else 2
                kept.append((text, line_top, rank, avg, d_p, line_x0, line_x1))

        if not kept:
            # Fallback: layout clássico com descrição junto ao código
            return self._desc_near_code(code_w, words)

        # Funde linhas de especificação consecutivas com sobreposição horizontal
        # (ex: '68% algodão, 27% poliamida' + 'e 5% outras fibras.' -> uma linha só),
        # mantendo o topo da primeira para a checagem da janela vertical.
        merged = []
        for t in sorted(kept, key=lambda t: t[1]):
            if t[2] == 2 and merged and merged[-1][2] == 2:
                prev = merged[-1]
                gap = t[1] - prev[1]
                if gap <= 12 and t[5] <= prev[6] and prev[5] <= t[6]:
                    merged[-1] = (
                        prev[0] + " " + t[0], prev[1], 2,
                        max(prev[3], t[3]), min(prev[4], t[4]),
                        min(prev[5], t[5]), max(prev[6], t[6]),
                    )
                    continue
            merged.append(t)
        kept = merged

        # Separa títulos (rank 0) de especificações (rank 2)
        titles = [t for t in kept if t[2] == 0]
        specs = [t for t in kept if t[2] != 0]
        cd = (code_w["top"] + code_w["bottom"]) / 2.0

        # Melhor título: o mais próximo do preço. Evita linha da faixa do código
        # (a variação 'Tamanho: 23 a 27' é anexada depois do nome).
        if titles:
            cand_titles = [t for t in titles if abs(t[1] - cd) > 12] or titles
            best = min(cand_titles, key=lambda t: t[4])
        else:
            best = min(kept, key=lambda t: t[4])

        b_x0, b_x1, b_top = best[5], best[6], best[1]

        # Junta títulos vizinhos da mesma faixa (<=14px) para montar o nome completo
        title_block = [best] + [t for t in titles
                                if t is not best
                                and abs(t[1] - b_top) <= 14
                                and t[5] < b_x1 and t[6] > b_x0]
        title_block.sort(key=lambda t: t[1])
        chosen = [t[0] for t in title_block]
        used_b = {id(t) for t in title_block}
        block_bottom = max(t[1] for t in title_block)

        # Anotação da linha do código (ex: 'Tamanho: 23 a 27') logo após o nome.
        # Restringida à faixa do próprio código (<=8px do topo) para não pegar a
        # variação de tamanho do item vizinho (2 itens a 8px de distância).
        c_top = code_w["top"]
        code_ann = [t for t in kept
                    if id(t) not in used_b and t[2] == 0
                    and abs(t[1] - c_top) <= 8
                    and t[5] < b_x1 and t[6] > b_x0]
        code_ann.sort(key=lambda t: t[1])
        for t in code_ann:
            chosen.append(t[0])
            used_b.add(id(t))

        # Especificações: linhas vizinhas logo abaixo/ao lado do título,
        # sobrepondo horizontalmente o nome do produto (mantém a coluna limpa)
        for t in sorted(kept, key=lambda t: t[1]):
            if id(t) in used_b:
                continue
            # Linhas de título (rank 0) já foram tratadas por title_block/code_ann
            if t[2] == 0:
                continue
            if t[1] < block_bottom - 45 or t[1] > block_bottom + 90:
                continue
            if t[4] > 160:
                continue
            if not (t[5] < b_x1 and t[6] > b_x0):
                continue
            chosen.append(t[0])
            used_b.add(id(t))
            if len(chosen) >= 4:
                break

        return " ".join(chosen[:4]), best[4]

    def _column_bounds(self, words) -> Tuple[tuple, ...]:
        """Divide a página em colunas usando a posição X dos códigos.

        O limite entre colunas é o ponto médio entre o código mais à direita da
        coluna esquerda e o código mais à esquerda da coluna direita.
        """
        xs = sorted({round((w["x0"] + w["x1"]) / 2.0)
                     for w in words if self._is_code_candidate(w["text"])})
        if not xs:
            return tuple()
        cols = [[xs[0], xs[0]]]
        for x in xs[1:]:
            if x - cols[-1][1] <= 60:
                cols[-1][1] = x
            else:
                cols.append([x, x])
        bounds = []
        for i, (lo, hi) in enumerate(cols):
            left = 0.0 if i == 0 else (cols[i - 1][1] + lo) / 2.0
            right = 1e9 if i == len(cols) - 1 else (hi + cols[i + 1][0]) / 2.0
            bounds.append((left, right))
        return tuple(bounds)

    def _price_labels_near(self, price_w, words) -> Set[str]:
        """Rótulos que pertencem ao próprio quadrado de preço (ex: 'CADA PAR').

        Considera apenas maiúsculas curtas e palavras muito próximas do quadrado.
        """
        labels: Set[str] = set()
        known = ("CADA", "PAR", "POR", "DE", "DO", "DA", "NA", "NO", "UN", "CX", "CJ",
                 "OFF", "COM", "DESCONTO", "SOLID", "SOLID�RIO")
        px0, px1, pt, pb = price_w["x0"], price_w["x1"], price_w["top"], price_w["bottom"]
        for w in words:
            t = w["text"].strip()
            if len(t) >= 2 and t.isupper() and t in known:
                if px0 - 40 <= w["x0"] <= px1 + 60 and pt - 18 <= w["top"] <= pb + 18:
                    labels.add(t)
        return labels

    def _second_price_near(self, code_w, best_price, words) -> str:
        """Retorna o segundo quadrado de preço (diferente do principal) na coluna do código."""
        cx = (code_w["x0"] + code_w["x1"]) / 2.0
        cy = (code_w["top"] + code_w["bottom"]) / 2.0
        best_val = self._price_token_value(best_price["text"])
        col = self._column_bounds(words)
        col_match = next(((lo, hi) for lo, hi in col if lo - 15 <= cx <= hi + 15), None)
        if col_match is None:
            col_match = (max(0, cx - 260), cx + 340)
        c_lo, c_hi = col_match
        cands = []
        for pw in words:
            if not self._is_price_token(pw["text"]):
                continue
            if self._price_token_value(pw["text"]) == best_val:
                continue
            if not self._has_currency_marker(pw, words):
                continue
            px = (pw["x0"] + pw["x1"]) / 2.0
            py = (pw["top"] + pw["bottom"]) / 2.0
            d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
            same_col = (c_lo - 40 <= px <= c_hi + 40)
            near_vert = abs(py - cy) <= 120 and abs(px - cx) <= 450
            if not (same_col or near_vert):
                continue
            cands.append((d, pw))
        if not cands:
            return ""
        cands.sort(key=lambda t: t[0])
        return self._format_price(self._price_token_value(cands[0][1]["text"]))

    def _desc_near_code(self, code_w, words) -> Tuple[Optional[str], float]:
        """Retorna descrição das linhas próximas ao código (acima ou abaixo) e a distância até a linha mais próxima."""
        cx, cy = (code_w["x0"]+code_w["x1"])/2, (code_w["top"]+code_w["bottom"])/2
        region = [w for w in words
                  if code_w["top"] - 400 <= w["top"] <= code_w["bottom"] + 400
                  and code_w["x0"] - 260 <= w["x0"] <= code_w["x0"] + 500]
        if not region:
            return None, 1e9
        # Agrupa em linhas pelo 'top'
        lines = {}
        for w in region:
            # Texto espelhado aparece como token iniciando com ',' ou '.'
            if w["text"].startswith((",", ".")):
                continue
            key = round(w["top"] / 6)
            lines.setdefault(key, []).append(w)
        kept = []
        for key in sorted(lines, key=lambda k: abs(min(w["top"] for w in lines[k]) - cy))[:20]:
            lst = sorted(lines[key], key=lambda w: w["x0"])
            text = " ".join(w["text"] for w in lst)
            if self._desc_line_ok(text) and not self._is_tone_line(text):
                # Linhas de título de produto: curtas, sem ponto final, com palavras capitalizadas
                n_words = len(text.split())
                is_title = n_words <= 8 and not text.endswith(".") and any(w[0:1].isupper() for w in text.split())
                is_badge = any(k in text.lower() for k in ("lançamento", "limitada", "edição", "off", "grátis"))
                has_product_noun = any(k in text.lower() for k in ("gloss", "batom", "base", "colônia", "máscara", "sabonete", "protetor", "paleta", "esmalte", "brilho", "lápis", "delineador", "camiseta", "nécessaire", "sérum", "creme", "kit"))
                # Peso por tamanho de fonte: textos maiores tendem a ser títulos de produto
                sizes = [w.get("size", 0.0) for w in lst]
                avg_size = sum(sizes) / len(sizes) if sizes else 0.0
                if is_badge:
                    rank = 3
                elif is_title and has_product_noun:
                    rank = 0
                elif is_title:
                    rank = 1
                else:
                    rank = 2
                kept.append((text, min(w["top"] for w in lst), rank, avg_size))
        if not kept:
            return None, 1e9
        # Ordena: títulos primeiro, depois por tamanho de fonte desc, proximidade
        kept.sort(key=lambda t: (t[2], -t[3], abs(t[1] - cy)))
        nearest_top = kept[0][1]
        dist = abs(nearest_top - cy)
        # Mantém no máximo 3 linhas próximas, em ordem vertical
        kept = sorted(kept[:3], key=lambda t: t[1])
        return " ".join(t[0] for t in kept), dist

    def _is_tone_line(self, text: str) -> bool:
        t = text.strip()
        if "|" in t:
            return True
        if re.search(r"-\s*(GC|CM|ME|CV|CE|C|M|P|F|NQ|QC|N)\b", t):
            return True
        if re.search(r"\d+\s?(pts|pt|g|ml|mg)\b", t, re.IGNORECASE):
            return True
        return False

    def _looks_like_spec(self, text: str) -> bool:
        """Identifica linhas de especificação (composição/dimensões/variação),
        que podem conter %/cm/'x'/'pts' sem serem texto de tom ou marketing."""
        t = text.lower()
        if "cm" in t or "%" in t or "tamanho" in t:
            return True
        if re.search(r"\b\d+(?:[.,]\d+)?\s?(?:x|ml|g|mg|un)\b", t):
            return True
        return False

    def _desc_line_ok(self, text: str) -> bool:
        t = text.strip()
        if len(t) < 3:
            return False
        if re.search(r"\d,\d{2}", t):
            return False
        if re.search(r"\bR\$?\b", t):
            return False
        low = t.lower()
        for bad in ("off", "pt ", "informe os", "na compra", "bbee", "qr code", "da a", " c da", "da o", " bb"):
            if bad in low:
                return False
        if sum(1 for ch in t if ch.isdigit()) > max(1, len(t) / 3):
            return False
        return True

    # ---------------- fim da associação espacial ----------------

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
