# -*- coding: utf-8 -*-
"""
Pipeline de extração por evidências (ETAPAS 6/7).

Monta o fluxo completo sobre PageData existente (sem tocar no parser legado):
  inventário de palavras -> âncoras (código/preço) -> regiões -> 3 scanners
  (regional, coluna, texto-linha) -> reconciliação -> ProductItem com status.

Usado pelo CatalogParser quando mode="evidence" e pelos scripts de teste.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from core.analysis import (Anchor, BBox as ABBox, ConfidenceScorer, PageElement,
                           WEIGHTS, build_grid_regions, assign_anchors_to_regions,
                           Candidate, Reconciler, Association, Evidence)
from core.analysis.associations import parse_value
from core.analysis.commercial import analyze_commercial_region
from core.analysis.evidence import NEUTRAL, POSITIVE
from core.analysis.regions import _column_limits, detect_gaps
from core.models import ExtractionConfig, PageData, ProductItem

RE_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}[.,]\d{2}|\d{2,4})")
RE_PRICE_STRICT = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$")
RE_CODE6 = re.compile(r"^\d{4,8}$")
RE_CODE_ALPHA = re.compile(r"^[A-Z]{2,4}-?\d{3,}$")
RE_QTY = re.compile(r"^\d{1,2}$", re.IGNORECASE)
PROMO_WORDS = {"POR", "CADA", "PAR", "OFF", "ECONOMIZE", "DE", "POR R$"}

PRICE_ABOVE = 60.0     # acima disso do bottom do código não é preço dele
CAP_FAR = 280.0        # além disso fica NÃO_DETERMINADO (não-invenção)


@dataclass
class EvidenceExtractor:
    config: ExtractionConfig = field(default_factory=ExtractionConfig)
    scorer: ConfidenceScorer = field(default_factory=ConfidenceScorer)
    reconciler: Reconciler = field(default_factory=Reconciler)

    # ---------------- inventário ----------------
    def _elements(self, page: PageData) -> List[PageElement]:
        out = []
        for w in page.words or []:
            out.append(PageElement("word", w.get("text", ""),
                                   ABBox(w.get("x0", 0), w.get("top", 0),
                                         w.get("x1", 0), w.get("bottom", 0)),
                                   size=w.get("size", 0), detector="words"))
        return out

    def _page_width(self, elements) -> float:
        return max((e.bbox.x1 for e in elements), default=600.0) + 40.0

    def _has_currency_near(self, el, elements) -> bool:
        for c in elements:
            if c is el:
                continue
            if c.text != "R$":
                continue
            if abs(c.bbox.cy - el.bbox.cy) <= 16 and -6 <= c.bbox.x1 - el.bbox.x0 <= 260:
                return True
        return False

    def _promo_near(self, el, elements) -> bool:
        for c in elements:
            if c is el:
                continue
            if c.text.upper() not in PROMO_WORDS:
                continue
            if abs(c.bbox.cy - el.bbox.cy) <= 40 and abs(c.bbox.x0 - el.bbox.x0) <= 260:
                return True
        return False

    def _inventory(self, page: PageData):
        elements = self._elements(page)
        price_anchors, code_anchors, qty_by_value = [], [], {}
        r_marker = [e for e in elements if e.text.startswith("R$")]

        # ---- preços ----
        for w in elements:
            m = RE_MONEY.search(w.text)
            if not m or not re.search(r"\d", m.group(1)):
                continue
            raw = m.group(1)
            if not (RE_PRICE_STRICT.match(raw) or re.fullmatch(r"\d{2,4}", raw)):
                continue
            if "%" in w.text:
                continue
            is_code_like = bool(RE_CODE6.match(raw) or RE_CODE_ALPHA.match(raw))
            if is_code_like:
                continue  # 4+ dígitos sem centavos = código, nunca preço
            if not re.search(r"[.,]\d{2}$", raw) \
                    and not (re.fullmatch(r"\d{2,4}", raw) and w.text.upper().startswith("R$")):
                continue  # preço exige centavos OU prefixo R$ no próprio token
            if (parse_value(raw) or 0.0) < 1.0:
                continue  # restos de gramatura/desc (0,35g), nunca preço de produto
            a = Anchor("price", raw, w.bbox, page.page_number,
                       ["price"], 0.5, {"raw": w.text}, [w])
            price_anchors.append(a)
            # tier de quantidade à esquerda na mesma linha
            for c in elements:
                if c is w or RE_QTY.match(c.text) is None:
                    continue
                if abs(c.bbox.cy - w.bbox.cy) <= 6 and 0 <= w.bbox.x0 - c.bbox.x1 <= 150 \
                        and "," not in c.text and len(c.text) <= 2:
                    qty_by_value[raw] = int(c.text)

        # ---- códigos ----
        page_h = max((e.bbox.y1 for e in elements), default=0.0)
        footer_below = page_h - 96
        for e in elements:
            t = e.text
            if "__" in t or "BBEE" in t:
                continue
            if not (RE_CODE6.match(t) or RE_CODE_ALPHA.match(t)):
                continue
            if "," in t or "R$" in t:
                continue
            if e.bbox.y0 > footer_below:
                continue  # rodapé do catálogo (página/guia), nunca produto
            code_anchors.append(Anchor("code", t, e.bbox, page.page_number,
                                       ["code"], 0.5, {}, [e]))
        # dedupe por posição (mesma palavra não vira âncora dupla)
        return elements, price_anchors, code_anchors, qty_by_value

    # ---------------- scanners (retornam {código: [âncoras]}) ----------------
    def _owners(self, codes: List[Anchor], prices: List[Anchor]) -> Dict[str, List[Anchor]]:
        """Modelo 'dono': cada preço pertence ao código IMEDIATAMENTE acima
        (maior 'y1' ainda menor que o topo do preço), com afinidade de coluna."""
        owners: Dict[str, List[Anchor]] = {}
        for p in prices:
            cands = []
            for c in codes:
                if c.bbox.y1 > p.bbox.y0 + 6:
                    continue  # não está acima do preço
                dy = p.bbox.y0 - c.bbox.y1
                if dy > CAP_FAR:
                    continue  # longe demais -> NÃO_DETERMINADO (não-invenção)
                x_over = min(c.bbox.x1, p.bbox.x1) - max(c.bbox.x0, p.bbox.x0)
                if x_over < 10 and abs(c.bbox.cx - p.bbox.cx) > 200:
                    continue  # coluna distinta
                if dy < -PRICE_ABOVE:
                    continue
                cands.append((c.bbox.y1, -abs(c.bbox.cx - p.bbox.cx), c))
            if not cands:
                continue
            c = max(cands, key=lambda t: (t[0], t[1]))[2]
            owners.setdefault(c.value, []).append(p)
        return owners

    def _scanner_region(self, page, elements, codes, prices) -> Dict[str, List[Anchor]]:
        owners = self._owners(codes, prices)
        regions = build_grid_regions(page.page_number, elements, codes,
                                     page_width=self._page_width(elements))
        assign_anchors_to_regions(regions, prices + codes)
        out: Dict[str, List[Anchor]] = {}
        for c in codes:
            prices_owned = owners.get(c.value, [])
            if not prices_owned:
                continue
            reg = next((r for r in regions if any(a is c for a in r.anchors)), None)
            kept = [p for p in prices_owned
                    if reg is None or reg.bbox.overlaps(p.bbox, 10, 200)]
            if kept:
                out.setdefault(c.value, []).extend(kept)
        return out

    def _scanner_coluna(self, page, elements, codes, prices) -> Dict[str, List[Anchor]]:
        owners = self._owners(codes, prices)
        bounds = _column_limits((a.bbox.cx for a in codes), self._page_width(elements), 40)
        out: Dict[str, List[Anchor]] = {}
        for c in codes:
            prices_owned = owners.get(c.value, [])
            if not prices_owned:
                continue
            col = min(((lo, hi) for lo, hi in bounds if lo <= c.bbox.cx <= hi),
                      key=lambda b: abs((b[0] + b[1]) / 2 - c.bbox.cx), default=None)
            kept = [p for p in prices_owned
                    if col is None or (p.bbox.x1 >= col[0] - 20 and p.bbox.x0 <= col[1] + 20)]
            if kept:
                out.setdefault(c.value, []).extend(kept)
        return out

    def _scanner_linha(self, page: PageData) -> Dict[str, List[Anchor]]:
        """Scanner textual: linha com código E preço juntos (ex.: rodapé/índice)."""
        out: Dict[str, List[Anchor]] = {}
        price_re = re.compile(self.config.price_regex, re.IGNORECASE)
        for line in (page.raw_text or "").splitlines():
            price_m = price_re.search(line)
            if not price_m:
                continue
            # busca de código pelo padrão pos (dígitos ou alfanumérico)
            for tok in re.findall(r"[A-Z0-9][A-Z0-9.\-_/]{2,20}", line):
                if not (RE_CODE6.match(tok) or (RE_CODE_ALPHA.match(tok))):
                    continue
                val = RE_MONEY.search(price_m.group(0))
                if not val:
                    continue
                a = Anchor("price", val.group(1), ABBox(0, 0, 0, 0), page.page_number,
                           ["linha_texto"], 0.5, {"raw": line}, [])
                out.setdefault(tok, []).append(a)
                break  # uma linha = um produto
        return out

    # ---------------- descrição (heurística simples de bloco) ----------------
    def _description(self, code_a, elements, page_no) -> Optional[str]:
        # palavras na mesma coluna entre o código e até 320px abaixo (não-código/não-preço)
        cand = []
        for e in elements:
            if e.kind != "word" or e.text.upper().startswith("R$") or RE_CODE6.match(e.text):
                continue
            if abs(e.bbox.cx - code_a.bbox.cx) > 300:
                continue
            if 0 < e.bbox.y0 - code_a.bbox.y0 < 320 and RE_MONEY.search(e.text) is None \
                    and RE_QTY.match(e.text) is None and e.text not in PROMO_WORDS and "R$" not in e.text:
                cand.append((abs(e.bbox.cy - code_a.bbox.cy), e))
        if not cand:
            return None
        cand.sort(key=lambda t: t[0])
        seen, words = set(), []
        for _, e in cand[:14]:
            if e.text not in seen:
                seen.add(e.text)
                words.append(e.text)
        return " ".join(words) if words else None

    # ---------------- preço de seção compartilhado ----------------
    def _section_intervals(self, codes: List[Anchor]) -> List[Tuple[float, float]]:
        """Grades de colunas: mescla intervalos x de códigos separados por <=120px."""
        if not codes:
            return []
        xs = sorted((a.bbox.x0, a.bbox.x1) for a in codes)
        merged = [[xs[0][0], xs[0][1]]]
        for lo, hi in xs[1:]:
            if lo - merged[-1][1] <= 120:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        return [(lo, hi) for lo, hi in merged]

    def _assign_section_prices(self, codes, prices, priced_codes):
        """Preço de seção: modelo 'guia' das páginas Avon — uma/minhas âncoras de preço
        valem para vários códigos (grades de cores do mesmo produto). Só preenche códigos
        que NÃO receberam preço próprio; não inventa quando não há valores na seção.
        - modo GRADE: seção com <=2 valores para >=4 códigos -> espalha o conjunto.
        - modo FAIXA: vários preços -> cada código pega o preço real mais próximo abaixo."""
        for lo, hi in self._section_intervals(codes):
            center = (lo + hi) / 2.0
            scodes = [c for c in codes if lo - 45 <= c.bbox.cx <= hi + 45]
            sec_prices = [p for p in prices
                          if (parse_value(p.value) or 0.0) >= 1.0
                          and abs(p.bbox.cx - center) <= 260]
            unprice = [c for c in scodes if c.value not in priced_codes]
            if len(scodes) < 2 or not sec_prices or not unprice:
                continue
            sec_prices.sort(key=lambda p: p.bbox.y0)
            order = []
            for p in sec_prices:
                if p.value not in order:
                    order.append(p.value)
            yield unprice, order, sec_prices
        return

    # ---------------- associação + reconhecimento ----------------
    def _structure_scan(self, page: PageData, elements, codes, prices, page_h):
        """SCAN ESTRUTURAL (região comercial + promoção separada + regras por
        quantidade). Produz candidatos 'regiao_comercial' — os preços ficam
        TERRIFICADOS por quantidade (1 POR / 2 POR / 3 POR) e a oferta
        promocional nunca contamina o preço do produto."""
        region, promo_price_ids = analyze_commercial_region(
            page.page_number, elements, codes, prices, page_h)
        st = SimpleNamespace(region=region, promo_price_ids=promo_price_ids,
                             candidates={}, tiers={}, variations={})
        # UMA regra isolada ('2 POR R$6,99') é banner combinatório de página,
        # não a escada de preço do produto: exige >=2 regras para inferir o
        # ladder de quantidade (como a página 5: 1/2/3 POR).
        if len(region.price_rules) < 2:
            return st
        # liga cada regra à âncora de preço ORIGINAL do inventário
        rule_anchors = []
        for raw in region.rule_anchors_raw:
            best = None
            for a in prices:
                if a.value != raw:
                    continue
                d = a.bbox.distance_to(region.bbox)
                if best is None or d < best[0]:
                    best = (d, a)
            if best:
                rule_anchors.append(best[1])
        rule_anchors = list({id(a): a for a in rule_anchors}.values())
        if not rule_anchors:
            return st
        st.tiers = region.tier_rules
        codeset = {c.value for c in codes}
        for u in region.units:
            if u.code not in codeset:
                continue
            st.variations[u.code] = u.variation or ""
            evs = [
                Evidence("preco_valido", "regiao_comercial", page.page_number,
                         POSITIVE, WEIGHTS["preco_valido"]),
                Evidence("mesma_regiao", "regiao_comercial", page.page_number,
                         POSITIVE, WEIGHTS["mesma_regiao"]),
            ]
            if len(region.price_rules) >= 2:
                evs.append(Evidence("tier_identificado", "regiao_comercial",
                                    page.page_number, POSITIVE,
                                    WEIGHTS["tier_identificado"]))
            if len(region.units) >= 2:
                evs.append(Evidence("dominio_estrutura_grid", "regiao_comercial",
                                    page.page_number, POSITIVE,
                                    WEIGHTS["dominio_estrutura_grid"]))
            if region.promo and region.promo.is_oferta:
                evs.append(Evidence("promocao_identificada", "regiao_comercial",
                                    page.page_number, POSITIVE,
                                    WEIGHTS["promocao_identificada"]))
            note = (f"grupo comercial: {len(region.units)} códigos da mesma "
                    f"coleção compartilham {len(region.price_rules)} regras de "
                    f"preço por quantidade")
            if region.promo and region.promo.price_raw:
                note += (f"; promoção separada (R$ {region.promo.price_raw}) "
                         f"NÃO associada aos códigos")
            st.candidates[u.code] = Candidate(
                "regiao_comercial", u.code, page.page_number, list(rule_anchors),
                description=region.description,
                evidences=evs,
                preliminary_score=0.9,
                note=note,
            )
        return st

    def extract_page(self, page: PageData) -> Tuple[List[Association], dict]:
        elements, prices, codes, qty = self._inventory(page)
        page_no = page.page_number
        page_h = max((e.bbox.y1 for e in elements), default=0.0)

        # SCAN ESTRUTURAL — separa promoção e descreve o grupo comercial
        st = self._structure_scan(page, elements, codes, prices, page_h)
        self._variations = dict(st.variations)
        # preço promocional NUNCA é candidato de código (evidência da promoção)
        prices_product = [p for p in prices if id(p) not in st.promo_price_ids]

        scanners = {
            "regional_cell": self._scanner_region(page, elements, codes, prices_product),
            "coluna_banda": self._scanner_coluna(page, elements, codes, prices_product),
            "linha_texto": self._scanner_linha(page),
        }
        assocs: List[Association] = []
        reconciled = set()
        seen_codes = set()
        for c in sorted(codes, key=lambda a: (a.bbox.y0, a.bbox.x0)):
            if c.value in seen_codes:
                continue
            seen_codes.add(c.value)
            cands: List[Candidate] = []
            for method, m in scanners.items():
                for p in m.get(c.value, []):
                    ev = self._candidate_evidence(method, p, c)
                    cands.append(Candidate(method, c.value, page_no, [p],
                                           description=self._description(c, elements, page_no),
                                           evidences=ev,
                                           preliminary_score=1.0 if method != "linha_texto" else 0.6))
            # texto-linha para códigos que nenhum scanner geométrico viu (não inventa duplicata)
            if not cands:
                for p in scanners["linha_texto"].get(c.value, []):
                    cands.append(Candidate("linha_texto", c.value, page_no, [p],
                                           evidences=self._candidate_evidence("linha_texto", p, c),
                                           preliminary_score=0.6))
            s_cand = st.candidates.get(c.value)
            if s_cand is not None:
                cands.append(s_cand)
            if not cands:
                continue  # decide nos passos finais (seção compartilhada ou NÃO_DETERMINADO)
            assoc = self.reconciler.reconcile(c.value, page_no, cands, tiers=st.tiers)
            assocs.append(assoc)
            reconciled.add(c.value)
        # códigos vistos só pelo scanner textual (não mapeados acima)
        seen_geo = set(scanners["regional_cell"]) | set(scanners["coluna_banda"])
        for code, ps in scanners["linha_texto"].items():
            if code in seen_geo or code in reconciled or code in seen_codes:
                continue
            cands = [Candidate("linha_texto", code, page_no, [p],
                               evidences=self._candidate_evidence("linha_texto", p,
                                                                  Anchor("code", code, ABBox(0, 0, 0, 0), page_no, [], 0.4, {}, [])),
                               preliminary_score=0.6) for p in ps]
            assocs.append(self.reconciler.reconcile(code, page_no, cands))
            reconciled.add(code)
        # preço de seção: grades/faixas de códigos (mesmo produto, várias cores) sem preço próprio
        assigned = {a.codes[0] for a in assocs}
        for unpriced, order, sec_prices in self._assign_section_prices(codes, prices_product, assigned):
            grade_mode = len(order) <= 2 and len(unpriced) >= 4
            for c in unpriced:
                if c.value in assigned:
                    continue
                if grade_mode:
                    vals = list(order)
                else:
                    below = [p for p in sec_prices
                             if p.bbox.y0 - c.bbox.y1 >= -6 and p.bbox.y0 - c.bbox.y1 <= 380]
                    pick = None
                    if below:
                        pick = min(below, key=lambda pp: pp.bbox.y0 - c.bbox.y1)
                    else:
                        above = [p for p in sec_prices if 0 < c.bbox.y1 - p.bbox.y0 <= 90]
                        if above:
                            pick = min(above, key=lambda pp: c.bbox.y1 - pp.bbox.y0)
                    if pick is None:
                        continue
                    vals = [pick.value]
                anchors = [Anchor("price", v, c.bbox, page_no, ["preco_secao"], 0.5,
                                  {"secao": True}, []) for v in vals]
                cands = [Candidate("preco_secao", c.value, page_no, anchors,
                                   description=self._description(c, elements, page_no),
                                   preliminary_score=0.5,
                                   note="preço de seção compartilhado (grade/faixa de códigos, mesmo produto)")]
                assocs.append(self.reconciler.reconcile(c.value, page_no, cands, tiers=st.tiers))
                assigned.add(c.value)
        # código presente sem preço -> honesto NÃO_DETERMINADO
        for c in codes:
            if c.value in assigned:
                continue
            assocs.append(self.reconciler.reconcile(c.value, page_no, []))
            assigned.add(c.value)
        return assocs, {"precos": len(prices), "codigos": len(codes),
                        "grupo_comercial": bool(st.candidates),
                        "promos": 1 if (st.region.promo and st.region.promo.is_oferta) else 0}

    def _candidate_evidence(self, method, price_a: Anchor, code_a: Anchor) -> List[Evidence]:
        ev = [Evidence("preco_valido", method, code_a.page,
                       POSITIVE, WEIGHTS["preco_valido"])]
        if method in ("regional_cell", "coluna_banda") and price_a.bbox.width > 0:
            ev.append(Evidence("mesma_regiao", method, code_a.page,
                               POSITIVE, WEIGHTS["mesma_regiao"]))
            d = price_a.bbox.centroid_dist_to(code_a.bbox)
            if d <= 60:
                ev.append(Evidence("distancia_muito_curta", method, code_a.page,
                                   POSITIVE, WEIGHTS["distancia_muito_curta"]))
            elif d <= 200:
                ev.append(Evidence("distancia_curta", method, code_a.page,
                                   POSITIVE, WEIGHTS["distancia_curta"]))
            elif d <= 300:
                ev.append(Evidence("estrutura_ambigua", method, code_a.page,
                                   NEUTRAL, WEIGHTS["estrutura_ambigua"]))
            else:
                ev.append(Evidence("distancia_longa", method, code_a.page,
                                   NEUTRAL, WEIGHTS["distancia_longa"]))
        else:
            ev.append(Evidence("convencao_formatos", method, code_a.page,
                               POSITIVE, WEIGHTS["convencao_formatos"]))
        return ev

    # ---------------- saída compatível (ProductItem) ----------------
    def run(self, pages: List[PageData], include_unpriced: bool = False) -> Tuple[List[ProductItem], dict]:
        items: List[ProductItem] = []
        stats = {"paginas": 0, "associacoes": 0, "precos": 0, "codigos": 0,
                 "grupos_comerciais": 0, "promos": 0}
        counter = 1
        for page in pages:
            assocs, st = self.extract_page(page)
            stats["paginas"] += 1
            stats["precos"] += st["precos"]
            stats["codigos"] += st["codigos"]
            stats["grupos_comerciais"] += 1 if st["grupo_comercial"] else 0
            stats["promos"] += st["promos"]
            for a in assocs:
                stats["associacoes"] += 1
                if not a.prices:
                    if include_unpriced and a.codes:
                        items.append(self._product(counter, a))
                        counter += 1
                    continue
                items.append(self._product(counter, a))
                counter += 1
        return items, stats

    def _product(self, index: int, a: Association) -> ProductItem:
        code = a.codes[0] if a.codes else ""
        values = [p for p in a.prices if p.value is not None]
        if a.status == "CONFLITO":
            price = "|".join(_fmt(v.value) for v in values) if values else ""
            extra = ""
        elif values:
            price = _fmt(values[0].value)
            extra = _fmt(values[1].value) if len(values) > 1 else ""
        else:
            price, extra = "", ""
        variation = self._variations.get(code, "")
        # a descrição vinda do scanner estrutural é a do grupo inteiro (compartilhada);
        # a variação vai na coluna própria (não duplica na descrição)
        desc = a.description
        quantity_prices = []
        for p in a.prices:
            if p.quantity and p.kind == "quantity":
                quantity_prices.append([p.quantity, _fmt(p.value)])
        return ProductItem(
            index=index,
            page=a.page,
            code=code,
            description=desc,
            price=price,
            price_extra=extra,
            source_type="Evidência",
            confidence=int(round(a.confidence)),
            status=a.status,
            debug=a.note,
            variation=variation,
            quantity_prices=quantity_prices,
        )


def _fmt(v: float) -> str:
    text = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def extract_catalog(pages: List[PageData], config: Optional[ExtractionConfig] = None,
                    include_unpriced: bool = False):
    """Interface conveniente usada pelo CatalogParser (mode='evidence')."""
    ex = EvidenceExtractor(config or ExtractionConfig())
    return ex.run(pages, include_unpriced=include_unpriced)