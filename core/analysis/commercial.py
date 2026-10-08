# -*- coding: utf-8 -*-
"""
SCAN ESTRUTURAL — REGIÕES COMERCIAIS (missão "Página 5 Avon Casa").

A página NÃO é tratada como sequência linear de texto: é interpretada como
composição espacial. Este módulo produz uma REPRESENTAÇÃO INTERMEDIÁRIA que
preserva as relações comerciais antes da normalização final em ProductItem:

  Região Comercial
    ├── unidades comerciais (código + variação/nome do item)
    ├── descrição compartilhada do grupo
    ├── regras de preço por quantidade (1 POR 19,99 / 2 POR 17,99 / ...)
    └── oferta promocional SEPARADA (condição + benefício + preço + desconto)

Princípios:
  * proximidade espacial é EVIDÊNCIA, não prova;
  * nada é hardcoded para strings específicas ("263406", "Marshall", "2 POR",
    "Caneca") — tudo é derivado de classificação semântica + geometria;
  * quando a evidência é insuficiente, a relação NÃO é criada.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from core.analysis.elements import BBox

# --------------------------------------------------------------------------- #
# Classificação semântica (conjunto fechado de classes)
# --------------------------------------------------------------------------- #
CODIGO = "CODIGO"
VARIACAO = "VARIACAO"
DESCRICAO = "DESCRICAO"
PRECO = "PRECO"
QUANTIDADE = "QUANTIDADE"
REGRA_PRECO = "REGRA_PRECO"
QUALIFICADOR = "QUALIFICADOR"
PROMOCAO = "PROMOCAO"
CONDICAO = "CONDICAO"
DESCONTO = "DESCONTO"
BRINDE = "BRINDE"
PERCENT = "PERCENT"
INFORMATIVO = "INFORMATIVO"
NAO_CLASSIFICADO = "NAO_CLASSIFICADO"
RODAPE = "RODAPE"

ELEMENT_CLASSES = {
    CODIGO, VARIACAO, DESCRICAO, PRECO, QUANTIDADE, REGRA_PRECO,
    QUALIFICADOR, PROMOCAO, CONDICAO, DESCONTO, BRINDE, PERCENT,
    INFORMATIVO, NAO_CLASSIFICADO, RODAPE,
}

# Prefixos fortes de benefício/oferta (genéricos; NÃO dependem da página 5)
PROMO_STRONG = {"LEVE", "GANHE", "BRINDE", "GRÁTIS", "GRATIS", "OFERTA",
                "PROMO", "ECONOMIZE", "CUMPRA", "RECEBA"}
# Início de frase condicional ("Na compra de 2 itens ... / Compre 2 ...")
CONDICAO_START = {"NA", "AO", "PARA", "EM", "COM", "ACUMULE", "JUNTE",
                  "TROQUE", "COMPRE", "GASTE", "ACRESCENTE"}
CONDICAO_VERB = {"COMPRA", "COMPRE", "COMBINAR", "GASTOU", "GASTE",
                 "ACUMULAÇÃO", "ACUMULACAO", "ACÚMULO", "ACUMULO", "JUNTA",
                 "TROCA", "AQUISIÇÃO", "AQUISICAO"}

RE_CODE6 = re.compile(r"^\d{4,8}$")
RE_CODE_ALPHA = re.compile(r"^[A-Z]{2,4}-?\d{3,}$")
RE_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d{1,3}[.,]\d{2}|\d{2,4})")
RE_PRICE_STRICT = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$")
RE_PERCENT = re.compile(r"^\d{1,3}%$")
RE_QTY = re.compile(r"^\d{1,2}$")
RE_LETTERS = re.compile(r"^[A-ZÀ-Úa-zà-ú-]+$")
RE_TITLE_SENTENCE = re.compile(r"^[A-ZÀ-Ú][a-zà-ú]+")
RODAPE_JUNK = re.compile(r"(__|BBEE|BBRR|iinndddd|[0-9]{2}::|[0-9]{2}//)")

# Tolerâncias geométricas (px)
VAR_DY_MAX = 24.0          # nome/variação aparece até N px abaixo do código
VAR_DY_MIN = 4.0
VAR_MERGE_DY = 12.0        # continuação do nome em outra linha
RULE_PRICE_DY = 26.0       # preço da regra pode estar até N px abaixo do "POR"
RULE_PRICE_DX = 50.0       # ... com alinhamento horizontal N px
BAND_GAP = 26.0            # linhas do mesmo parágrafo
GRUPO_FAR = 300.0          # além disso não vinculamos código a regras (não-invenção)
PROMO_XTOL = 45.0          # margem horizontal do bloco promocional
PROMO_Y_ABOVE = 14.0       # palavras bem acima das sementes não pertencem à oferta


@dataclass
class ClassifiedWord:
    """Palavra classificada semanticamente, mantendo geometria e evidência."""
    text: str
    bbox: BBox
    cls: str = NAO_CLASSIFICADO
    size: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass
class ProductUnit:
    """Um produto/variante dentro de uma região comercial (código + nome)."""
    code: str
    code_bbox: BBox
    variation: Optional[str] = None
    var_bbox: Optional[BBox] = None
    evidence: str = ""


@dataclass
class QuantityRule:
    """Preço condicionado à quantidade (1 POR / 2 POR / 3 POR ...)."""
    quantity: int
    price: float
    price_raw: str
    rule_bbox: BBox


@dataclass
class PromotionalOffer:
    """Oferta condicional separada dos preços de produto (categoria B)."""
    bbox: BBox
    condition: List[str] = field(default_factory=list)
    benefit: List[str] = field(default_factory=list)
    price: Optional[float] = None
    price_raw: Optional[str] = None
    discount: Optional[int] = None
    terms: List[str] = field(default_factory=list)
    words: List[ClassifiedWord] = field(default_factory=list)

    @property
    def is_oferta(self) -> bool:
        return bool(self.condition or self.benefit or self.discount is not None)


@dataclass
class CommercialRegion:
    """Representação intermediária: um bloco comercial (produtos + preços +
    promoção separada), antes da normalização em ProductItem."""
    page: int
    bbox: BBox
    units: List[ProductUnit] = field(default_factory=list)
    description: Optional[str] = None
    price_rules: List[QuantityRule] = field(default_factory=list)
    promo: Optional[PromotionalOffer] = None
    words: List[ClassifiedWord] = field(default_factory=list)
    evidence_groups: Dict[str, str] = field(default_factory=dict)

    @property
    def codigos(self) -> List[str]:
        return [u.code for u in self.units]

    @property
    def tier_rules(self) -> Dict[str, int]:
        """mapeia raw do preço (ex: "19,99") -> quantidade do tier."""
        return {r.price_raw: r.quantity for r in self.price_rules}

    @property
    def rule_anchors_raw(self) -> List[str]:
        return [r.price_raw for r in self.price_rules]


# --------------------------------------------------------------------------- #
# Linhas (agrupamento físico de palavras por faixa Y)
# --------------------------------------------------------------------------- #
@dataclass
class TextLine:
    y0: float
    y1: float
    words: List[ClassifiedWord] = field(default_factory=list)
    y0_ref: Optional[float] = None

    @property
    def text(self) -> str:
        return " ".join(w.text for w in sorted(self.words, key=lambda w: w.bbox.x0))

    @property
    def x0(self) -> float:
        return min((w.bbox.x0 for w in self.words), default=0.0)

    @property
    def x1(self) -> float:
        return max((w.bbox.x1 for w in self.words), default=0.0)


def build_text_lines(words: Iterable["ClassifiedWord"], y_tol: float = 6.0) -> List[TextLine]:
    """Agrupa palavras em linhas por proximidade de TOPO (y0), com UMA referência
    fixa (a primeira palavra da linha). A referência nunca se expande, evitando
    que o 'encadeamento' junte linhas distantes (ex.: um percentual gigante acima
    da descrição). Palavras na mesma linha visual compartilham o mesmo topo."""
    lines: List[TextLine] = []
    for w in sorted(words, key=lambda x: (x.bbox.y0, x.bbox.x0)):
        y0 = w.bbox.y0
        added = False
        for ln in lines:
            if ln.y0_ref is not None and abs(y0 - ln.y0_ref) <= y_tol:
                ln.words.append(w)
                ln.y0 = min(ln.y0, w.bbox.y0)
                ln.y1 = max(ln.y1, w.bbox.y1)
                added = True
                break
        if not added:
            lines.append(TextLine(w.bbox.y0, w.bbox.y1, [w]))
            lines[-1].y0_ref = y0
    return lines


# --------------------------------------------------------------------------- #
# Passo 1: classificação individual (sem contexto)
# --------------------------------------------------------------------------- #
def classify_word(w) -> str:
    t = w.text
    if len(t) == 0:
        return NAO_CLASSIFICADO
    if RODAPE_JUNK.search(t):
        return RODAPE
    if RE_CODE6.match(t) or RE_CODE_ALPHA.match(t):
        return CODIGO
    if t.startswith("R$"):
        m = RE_MONEY.search(t)
        if m and re.search(r"[.,]\d{2}$", m.group(1)):
            return PRECO
    if RE_PERCENT.match(t):
        return PERCENT
    if RE_PRICE_STRICT.match(t):
        return PRECO
    up = t.upper()
    if up in PROMO_STRONG or t == up and up.startswith("LEVE"):
        return PROMOCAO
    if up == "DESCONTO" or up == "OFF":
        return DESCONTO
    if RE_QTY.match(t) and "," not in t:
        return QUANTIDADE
    if up in {"CADA", "PAR", "UN", "UNID", "CX"}:
        return QUALIFICADOR
    if up == "POR":
        return QUALIFICADOR  # REVISITADO no passo 2 (regra vs benefício)
    if up == "INFORME" or (up.startswith("INFO") and ",PRODUTOS" not in up):
        return INFORMATIVO
    if up in CONDICAO_VERB:
        return CONDICAO
    # {ITENS, COLEÇÃO} marcam condição; preposições comuns (com/de/na/para/em)
    # ficam NEUTRAS aqui e só viram CONDICAO contextualmente (frase "Na compra")
    if up in {"ITENS", "COLEÇÃO", "COLECAO"}:
        return CONDICAO
    if RE_LETTERS.match(t):
        return NAO_CLASSIFICADO  # aguarda contexto (variação/descrição)
    return NAO_CLASSIFICADO


# --------------------------------------------------------------------------- #
# Passo 2: refinamento por contexto de linha (regras "N POR" e frases)
# --------------------------------------------------------------------------- #
def _refine_rules_and_phrases(words: List[ClassifiedWord]) -> List[ClassifiedWord]:
    for w in words:
        raw = dict(w.raw)
        raw["cls"] = w.cls
        w.raw = raw
    lines = {round(w.bbox.cy / 6): [] for w in words}
    ll = {}
    for w in words:
        ll.setdefault(round(w.bbox.cy / 6), []).append(w)

    # --- regras "N POR" na mesma linha ---
    for key, ws in ll.items():
        ws = sorted(ws, key=lambda x: x.bbox.x0)
        for i, w in enumerate(ws):
            if w.cls not in (QUALIFICADOR,) or w.text.upper() != "POR":
                continue
            # procura quantidade imediatamente antes (mesma linha, gap curto)
            if i > 0 and ws[i - 1].cls == QUANTIDADE \
                    and w.bbox.x0 - ws[i - 1].bbox.x1 <= 40:
                for k in (i - 1, i):
                    ws[k].cls = REGRA_PRECO
        # propaga a classe REGRA_PRECO para o dígito quando "POR" já foi marcado
        for i, w in enumerate(ws):
            if w.cls == REGRA_PRECO and RE_QTY.match(w.text):
                if i > 0 and ws[i - 1].cls == REGRA_PRECO:
                    w.cls = REGRA_PRECO

    # --- frase condicional "NA COMPRA DE ..." (início de condição) ---
    keys = sorted(ll)
    for j, key in enumerate(keys):
        first = sorted(ll[key], key=lambda x: x.bbox.x0)
        if not first:
            continue
        head = first[0].text.upper()
        if head not in CONDICAO_START:
            continue
        # a próxima linha deve reforçar (verbo de compra)
        if j + 1 < len(keys):
            nxt = [w.text.upper() for w in ll[keys[j + 1]]]
            if nxt and any(v in " ".join(nxt) for v in CONDICAO_VERB):
                for w in ll[key]:
                    w.cls = CONDICAO
                for w in ll[keys[j + 1]]:
                    if w.cls == NAO_CLASSIFICADO:
                        w.cls = CONDICAO
    return words


# --------------------------------------------------------------------------- #
# Passo 3: blocos promocionais (sementes fortes + faixa X + grafia)
# --------------------------------------------------------------------------- #
def _strong_promo_seeds(words: List[ClassifiedWord]) -> List[ClassifiedWord]:
    """Sementes fortes: só considera promo quando há evidência textual clara
    (benefício tipo LEVE/GANHE/BRINDE, frase condicional ou 'X% DE DESCONTO')."""
    seeds = []
    for w in words:
        up = w.text.upper()
        if w.cls == PROMOCAO and up in {x.upper() for x in PROMO_STRONG}:
            seeds.append(w)
        elif up in CONDICAO_START and any(
                v in CONDICAO_VERB
                for v in [x.text.upper() for x in words
                          if abs(x.bbox.cy - w.bbox.cy) <= 26]):
            # palavra que INICIA frase condicional reforçada por verbo de
            # compra próxima (a classe não precisa estar feita no passo 1)
            seeds.append(w)
    # "60% DE DESCONTO": percent + palavra DESCONTO próximas
    for p in [w for w in words if w.cls == PERCENT]:
        for d in [w for w in words if w.cls == DESCONTO]:
            if p.bbox.distance_to(d.bbox) <= 60 and ('DESCONTO' in d.text.upper()
                                                     or 'OFF' in d.text.upper()):
                seeds.append(p)
                seeds.append(d)
    # dedupe
    out = []
    seen = set()
    for s in seeds:
        if id(s) not in seen:
            seen.add(id(s))
            out.append(s)
    return out


def build_promotional_offer(words: List[ClassifiedWord],
                            price_anchors: List) -> List[PromotionalOffer]:
    """Detecta ofertas promocionais separadas. O preço dentro do bloco
    promocional NUNCA é candidato a código de produto (fica aqui)."""
    seeds = _strong_promo_seeds(words)
    if not seeds:
        return []
    sx0 = min(s.bbox.x0 for s in seeds) - PROMO_XTOL
    sx1 = max(s.bbox.x1 for s in seeds) + PROMO_XTOL
    sy0 = min(s.bbox.y0 for s in seeds)
    sy1 = max(s.bbox.y1 for s in seeds)

    # palavras do bloco: mesma faixa X, abaixo até o rodapé, classificadas como
    # pertencentes à oferta (preço/percentual/benefício/condição/informativo)
    block_words: List[ClassifiedWord] = []
    for w in words:
        if w.bbox.x1 < sx0 or w.bbox.x0 > sx1:
            continue
        if w.cls in (CODIGO, REGRA_PRECO, RODAPE):
            continue
        if w.cls in (PRECO, PERCENT, PROMOCAO, CONDICAO, DESCONTO,
                     INFORMATIVO, QUALIFICADOR, QUANTIDADE, NAO_CLASSIFICADO):
            if w.bbox.y1 < sy0 - PROMO_Y_ABOVE:
                continue  # bem acima das sementes não pertence (variação/código)
            block_words.append(w)
            sy1 = max(sy1, w.bbox.y1)

    if not block_words:
        return []

    offer = PromotionalOffer(bbox=BBox(sx0, sy0, sx1, sy1), words=block_words)

    # --- separa condição / benefício / termos ---
    lines = build_text_lines(block_words)
    in_condition = False
    for ln in sorted(lines, key=lambda l: l.y0):
        txt = ln.text.upper()
        ws = sorted(ln.words, key=lambda w: w.bbox.x0)
        if any(w.cls == CONDICAO for w in ws):
            in_condition = True
            offer.condition.append(ln.text)
            continue
        if any(w.cls == PROMOCAO for w in ws) or ("LEVE" in txt and "POR" in txt):
            in_condition = False
            offer.benefit.append(ln.text)
            continue
        if any(w.cls == INFORMATIVO for w in ws):
            in_condition = False
            offer.terms.append(ln.text)
            continue
        if in_condition:
            offer.condition.append(ln.text)
        else:
            # linhas soltas que continuam o bloco (ex.: CANECA / DIVERTIDA)
            if any(w.cls in (PROMOCAO, QUALIFICADOR, NAO_CLASSIFICADO) for w in ws):
                offer.benefit.append(ln.text)

    # --- preço e desconto da oferta ---
    for a in price_anchors:
        if a.bbox.x1 < sx0 or a.bbox.x0 > sx1:
            continue
        if offer.bbox.y0 - 40 <= a.bbox.y0 <= sy1 + 40:
            offer.price = a
            offer.price_raw = a.value
            break
    for p in [w for w in block_words if w.cls == PERCENT]:
        if offer.discount is None:
            try:
                offer.discount = int(p.text.replace("%", "").strip())
            except ValueError:
                pass
    if offer.condition or offer.benefit or offer.price_raw or offer.discount is not None:
        return [offer]
    return []


# --------------------------------------------------------------------------- #
# Passo 4: regras de preço por quantidade
# --------------------------------------------------------------------------- #
def extract_quantity_rules(words: List[ClassifiedWord],
                           price_anchors: List) -> List[QuantityRule]:
    """'N POR' + preço alinhado (mesma linha ou linha seguinte <= 26px)."""
    rules: List[QuantityRule] = []
    for w in words:
        if w.cls != REGRA_PRECO or not RE_QTY.match(w.text):
            continue
        # procura o "POR" logo à direita na mesma linha
        por = None
        for o in words:
            if o is w and o is not None:
                continue
            if o.cls == REGRA_PRECO and o.text.upper() == "POR" \
                    and abs(o.bbox.cy - w.bbox.cy) <= 6 \
                    and 0 <= o.bbox.x0 - w.bbox.x1 <= 40:
                por = o
                break
        # preço: mesma linha à direita do POR ou linha seguinte alinhada
        cand_price = None
        for a in price_anchors:
            v = parse_money(a.value)
            if v is None:
                continue
            if por is not None and abs(a.bbox.cy - por.bbox.cy) <= RULE_PRICE_DY \
                    and abs(a.bbox.cx - por.bbox.cx) <= RULE_PRICE_DX:
                if cand_price is None or a.bbox.y0 < cand_price.bbox.y0:
                    cand_price = a
            elif por is None and abs(a.bbox.cy - w.bbox.cy) <= RULE_PRICE_DY \
                    and abs(a.bbox.cx - w.bbox.cx) <= RULE_PRICE_DX * 1.6:
                if cand_price is None or a.bbox.y0 < cand_price.bbox.y0:
                    cand_price = a
        if cand_price is None:
            continue
        rules.append(QuantityRule(
            quantity=int(w.text),
            price=parse_money(cand_price.value) or 0.0,
            price_raw=strip_raw(cand_price.value),
            rule_bbox=w.bbox.union(cand_price.bbox),
        ))
    # dedupe por (quantity, price_raw)
    seen = set()
    out = []
    for r in rules:
        key = (r.quantity, r.price_raw)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return sorted(out, key=lambda r: (r.rule_bbox.y0, r.quantity))


def group_rule_bands(rules: List[QuantityRule], y_gap: float = 30.0) -> List[List[QuantityRule]]:
    bands: List[List[QuantityRule]] = []
    for r in sorted(rules, key=lambda x: x.rule_bbox.y0):
        for b in bands:
            if abs(r.rule_bbox.y0 - b[-1].rule_bbox.y0) <= y_gap:
                b.append(r)
                break
        else:
            bands.append([r])
    return bands


# --------------------------------------------------------------------------- #
# Passo 5: unidades comerciais (código + variação)
# --------------------------------------------------------------------------- #
def build_units(code_anchors: List, words: List[ClassifiedWord]) -> List[ProductUnit]:
    units: List[ProductUnit] = []
    used = set()
    for c in sorted(code_anchors, key=lambda x: (x.bbox.y0, x.bbox.x0)):
        if c.value in used:
            continue
        used.add(c.value)
        text_parts, parts_bbox, cur = [], [], []
        for d in sorted(words, key=lambda x: (x.bbox.y0, x.bbox.x0)):
            if d.cls not in (NAO_CLASSIFICADO, VARIACAO):
                continue
            # deslocamento pelo TOPO (nomes de variação usam a mesma baseline do
            # código, sem lacuna vertical significativa)
            dy = d.bbox.y0 - c.bbox.y0
            if not (4.0 <= dy <= 26.0):
                continue
            if d.bbox.cy <= c.bbox.cy:
                continue  # o rótulo fica embaixo do código
            x_tol = max(16.0, c.bbox.width / 2.0 + 4.0)
            if abs(d.bbox.cx - c.bbox.cx) > x_tol and not (
                    min(d.bbox.x1, c.bbox.x1) - max(d.bbox.x0, c.bbox.x0) >= 4):
                continue
            # junta com o token anterior se for continuação vertical
            if cur and d.bbox.y0 - cur[-1].bbox.y0 > VAR_MERGE_DY:
                continue
            cur.append(d)
            text_parts.append(d.text)
            parts_bbox.append(d.bbox)
        if text_parts:
            units.append(ProductUnit(
                code=c.value,
                code_bbox=c.bbox,
                variation=" ".join(text_parts),
                var_bbox=parts_bbox[0].union(parts_bbox[-1]) if parts_bbox else None,
                evidence="nome/variação imediatamente abaixo do código",
            ))
        else:
            units.append(ProductUnit(code=c.value, code_bbox=c.bbox,
                                     evidence="sem variação próxima"))
    return units


# --------------------------------------------------------------------------- #
# Passo 6: descrição compartilhada (painel do grupo, longe do código)
# --------------------------------------------------------------------------- #
def collect_description(words: List[ClassifiedWord], rules: List[QuantityRule],
                        codes_bboxes, exclude_ids=None) -> Optional[str]:
    """A descrição do grupo é procurada no painel da regra de preço (banda da
    regra e 2 linhas seguintes), fora do bloco promocional. Nunca se assume que
    a descrição vem imediatamente depois do código."""
    if not rules:
        return None
    band_top = min(r.rule_bbox.y0 for r in rules)
    band_bottom = max(r.rule_bbox.y1 for r in rules)
    usable = []
    for ln in sorted(build_text_lines(words), key=lambda l: (l.y0, l.x0)):
        if ln.y0 < band_top - 6 or ln.y0 > band_bottom + 34:
            continue
        toks = []
        for w in sorted(ln.words, key=lambda x: x.bbox.x0):
            if exclude_ids and id(w) in exclude_ids:
                continue  # palavras da oferta promocional nunca descrevem produto
            if w.cls in (CODIGO, PRECO, REGRA_PRECO, QUALIFICADOR,
                         PROMOCAO, CONDICAO, DESCONTO, PERCENT, INFORMATIVO,
                         RODAPE):
                continue
            # QUANTIDADE passa (ex.: '03 pts') — os dígitos de regra "N POR"
            # já viraram REGRA_PRECO no refinamento e ficam de fora
            if w.text.upper().startswith("R$") or RE_CODE6.match(w.text):
                continue
            toks.append(w.text)
        if toks:
            usable.append(" ".join(toks))
    if not usable:
        return None
    return u" ".join(usable)


# --------------------------------------------------------------------------- #
# Orquestração da região comercial
# --------------------------------------------------------------------------- #
def analyze_commercial_region(page_no: int, elements, code_anchors,
                              price_anchors, page_h: float) -> CommercialRegion:
    """Classifica todas as palavras, detecta promoção, regras por quantidade,
    unidades e constrói a REGIÃO COMERCIAL intermediária."""
    words = []
    for el in elements:
        if el.text in ("", " "):
            continue
        w = ClassifiedWord(el.text, el.bbox, classify_word(el), el.size, {})
        words.append(w)

    # separa rodapé
    for w in words:
        if w.bbox.y0 > page_h - 60:
            w.cls = RODAPE

    _refine_rules_and_phrases(words)

    offers = build_promotional_offer(words, price_anchors)
    promo = offers[0] if offers else None

    # preços dentro do bloco promocional nunca servem de preço de produto
    promo_price_ids = set()
    if promo and promo.price is not None:
        for a in price_anchors:
            if a is promo.price or (
                    abs(a.bbox.x0 - promo.price.bbox.x0) < 2
                    and abs(a.bbox.y0 - promo.price.bbox.y0) < 2):
                promo_price_ids.add(id(a))

    rules = extract_quantity_rules(words, price_anchors)
    units = build_units(code_anchors, words)
    exclude_ids = {id(w) for w in promo.words} if promo else None
    desc = collect_description(words, rules, [u.code_bbox for u in units],
                               exclude_ids)

    all_bboxes = [u.code_bbox for u in units] + [r.rule_bbox for r in rules]
    if promo:
        all_bboxes.append(promo.bbox)
    if not all_bboxes:
        bbox = BBox(0, 0, 0, 0)
    else:
        b = all_bboxes[0]
        for x in all_bboxes[1:]:
            b = b.union(x)
        bbox = b

    region = CommercialRegion(
        page=page_no,
        bbox=bbox,
        units=units,
        description=desc,
        price_rules=rules,
        promo=promo,
        words=[w for w in words if w.cls != RODAPE],
        evidence_groups={
            "classificacao": "classificacao semantica por palavra",
            "promocao": "bloco promocional separado por sementes + faixa X",
            "regras": "regras de preco por quantidade (N POR)",
            "descricao": "descricao compartilhada no painel da regra",
        },
    )
    region.words = [w for w in region.words if w.cls != RODAPE]
    region.evidence_groups["promo_prices_excluidas"] = (
        f"{len(promo_price_ids)} preços promocionais não associados a códigos"
        if promo else "sem promoção detectada"
    )
    return region, promo_price_ids


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def parse_money(text: str) -> Optional[float]:
    t = text.strip().replace("R$", "").replace(" ", "")
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+)", t)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def strip_raw(text: str) -> str:
    m = RE_MONEY.search(text)
    return m.group(1) if m else text