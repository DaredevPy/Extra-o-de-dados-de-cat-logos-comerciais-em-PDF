# -*- coding: utf-8 -*-
"""ETAPA 3 — Protótipo: âncoras + linhas físicas + tiers por quantidade + região.

Isolado (scratch/). Não altera core/. Propõe relações com evidências; é a semente
do modelo de ANCHOR/REGION/ASSOCIATION das etapas seguintes.
"""
import glob
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------ tokens / âncoras ------------------------------
RE_INT = re.compile(r"^(?:\d{1,3}(?:[.,]\d{3})*)[.,]?\d{0,2}$")
RE_INT_STRICT = re.compile(r"^\d{1,3}(?:[.,]\d{3})*[.,]\d{2}$")
RE_VALUE = re.compile(r"(\d{1,3}(?:[.,]\d{3})*[.,]?\d{0,2})")
RE_RSPREFIX = re.compile(r"^R\$\s?")
RE_CODISH = re.compile(r"^(?:\d{4,8}|[A-Z][A-Za-z0-9-]{2,11})$")  # 4-8 dígitos ou alfanumérico
DIM_MARKERS = ("g", "ml", "pts", "cm", "kg", "m", "mm", "|", "un", "cx", "x")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float = 0.0

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self):
        return (self.top + self.bottom) / 2.0

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.bottom - self.top


@dataclass
class Anchor:
    kind: str            # 'code' | 'price' | 'qty' | 'desc_line' | 'noise'
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    detector: str = ""
    raw_words: List[Word] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self):
        return (self.top + self.bottom) / 2.0

    def dist2(self, other) -> float:
        return ((self.cx - other.cx) ** 2 + (self.cy - other.cy) ** 2) ** 0.5


# ------------------------------ leitura de palavras ----------------------------
def load_words(pdf_path, pno) -> List[Word]:
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[pno - 1]
        words = page.extract_words()
        chars = page.chars
        for w in words:
            sizes = [c["size"] for c in chars
                     if c["x0"] >= w["x0"] - 1 and c["x1"] <= w["x1"] + 1
                     and c["top"] >= w["top"] - 2 and c["bottom"] <= w["bottom"] + 2]
            sz = sum(sizes) / len(sizes) if sizes else 0.0
            out.append(Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"], sz))
    return out


# ------------------------------ linhas físicas ---------------------------------
def physical_lines(words: List[Word], y_tol: float = 6.0) -> List[List[Word]]:
    """Agrupa palavras em linhas físicas (mesmo 'top' ± tol); dentro da linha,
    quebra segmentos com gap horizontal > 20px."""
    groups: List[List[Word]] = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        placed = False
        for g in groups:
            if any(abs(w.top - o.top) <= y_tol for o in g):
                g.append(w)
                placed = True
                break
        if not placed:
            groups.append([w])
    # ordena por topo e depois por x, e segmenta gaps horizontais em sub-grupos
    rows = []
    for g in groups:
        g.sort(key=lambda w: w.x0)
        segs = [[]]
        prev = None
        for w in g:
            if prev is not None and w.x0 - prev.x1 > 20:
                segs.append([])
            segs[-1].append(w)
            prev = w if prev is None or w.x1 > prev.x1 else prev
        for s in segs:
            if s:
                rows.append(s)
    rows.sort(key=lambda s: (s[0].top, s[0].x0))
    return rows


def row_text(row: List[Word]) -> str:
    return " ".join(w.text for w in row)


def is_dims_row(row: List[Word]) -> bool:
    low = row_text(row).lower()
    return any(m in low for m in DIM_MARKERS)


def detect_r_tokens(words: List[Word], rows: List[List[Word]]) -> List[Anchor]:
    """Tokens que contêm início 'R$' (pode ser 'R$17,99CA' num token ou 'R$' solto)."""
    out = []
    r_ws = [w for w in words if w.text.startswith("R$")]
    # índice de linhas por faixa vertical para busca rápida
    def row_of(w):
        for row in rows:
            if any(abs(o.top - w.top) <= 6 for o in row):
                return row
        return None

    for w in r_ws:
        val = None
        m = RE_VALUE.search(w.text)
        # valor no próprio token?
        if m and "," not in m.group(1).replace(".", "") or m and m.group(1):
            maybe = m.group(1)
            # 'R$17,99CA' -> val '17,99'; 'R$' -> re.search falha em números
            if re.search(r"\d", maybe):
                val = maybe
        if val is None:
            # R$ solto: procura numeral adjacente (mesma linha ou até 18px abaixo/direita)
            best = None
            for cand in words:
                if cand is w or cand.text == "R$":
                    continue
                mv = RE_VALUE.fullmatch(cand.text)
                if not mv:
                    continue
                if not re.search(r"\d", cand.text):
                    continue
                vgap = abs(cand.cy - w.cy)
                hgap = cand.x0 - w.x1
                if vgap <= 18 and -4 <= hgap <= 140:
                    if best is None or (vgap, hgap) < (best[0], best[1]):
                        # cuida do caso 0,35 vs R$ do bloco vizinho: exige alinhamento horizontal
                        best = (vgap, hgap, cand)
            if best:
                val = best[2].text
        if val is None:
            continue
        # sanidade: valor monetário reconstruído deve ter 3+ dígitos ou casas decimais
        ndig = sum(1 for c in val if c.isdigit())
        has_dec = re.search(r"[.,]\d{2}", val) is not None
        if ndig < 3 and not has_dec:
            continue
        meta = {"value": val, "has_r": True}
        out.append(Anchor("price", w.text, w.x0, w.x1, w.top, w.bottom,
                          detector="price_R$", raw_words=[w], meta=meta))
    return out


def detect_standalone_prices(words: List[Word], rows: List[List[Word]],
                             r_anchors: List[Anchor]) -> List[Anchor]:
    """Valores monetários sem 'R$' no token (ex '14,99' empilhado, '8,49' em
    'POR R$ 8,49'), exigindo: vizinho R$ OU marcador PROMO, e não ser dimensão."""
    out = []
    for w in words:
        if w.text.startswith("R$"):
            continue
        m = RE_VALUE.fullmatch(w.text)
        if not m or not re.search(r"\d", w.text):
            continue
        val = m.group(1)
        # só aceita decimais, ou inteiros com 3+ dígitos, como preço sem prefixo
        is_dec = RE_INT_STRICT.fullmatch(val) is not None
        is_int = bool(re.fullmatch(r"\d{3,5}", val))
        if not (is_dec or is_int):
            continue
        if detect_codes and _is_code_like(w):
            continue
        near_r = any(abs(a.cy - w.cy) <= 25 and a.x0 - 5 <= w.x0 <= a.x1 + 140
                     for a in r_anchors)
        row = next((r for r in rows if any(o is w for o in r)), None)
        near_prom = bool(row and any(o.text.upper() in ("POR", "CADA", "PAR", "OFF", "DE") for o in row))
        if not (near_r or near_prom):
            continue
        if row and is_dims_row(row):
            # se a linha tem marcador de dimensão, não é preço (ex '0,35 g | pts')
            if not near_prom:
                continue
        out.append(Anchor("price", w.text, w.x0, w.x1, w.top, w.bottom,
                          detector="price_standalone", raw_words=[w],
                          meta={"value": val, "has_r": False}))
    return out


def _is_code_like(w: Word) -> bool:
    return bool(RE_CODISH.fullmatch(w.text) and sum(1 for c in w.text if c.isdigit()) >= 4)


def detect_codes(words: List[Word], rows: Optional[List[List[Word]]] = None) -> List[Anchor]:
    """Âncoras de código: 4-8 dígitos ou alfanumérico curto. Filtra marcador
    de página/quantidade e watermark."""
    out = []
    for w in words:
        t = w.text
        if "__" in t or "BBEE" in t:
            continue
        if not _is_code_like(w):
            continue
        if re.fullmatch(r"\d{1,2}", t):
            continue
        # watermark/footer: linha física com marcador BBEE/__ misturado
        if rows:
            row = next((r for r in rows if any(o is w for o in r)), None)
            if row and any("__" in o.text or "BBEE" in o.text for o in row):
                continue
        out.append(Anchor("code", t, w.x0, w.x1, w.top, w.bottom,
                          detector="code_flex", raw_words=[w]))
    return out


# ------------------------------ preços (junção R$ + standalone) -----------------
def detect_prices(words: List[Word]) -> List[Anchor]:
    rows = physical_lines(words)
    r = detect_r_tokens(words, rows)
    s = detect_standalone_prices(words, rows, r)
    merged = r + s
    # dedup: mesmo valor e posição (<=15px vertical, <=60px horizontal)
    kept = []
    for a in sorted(merged, key=lambda x: (x.meta["value"], x.top, x.x0)):
        dup = next((k for k in kept
                    if k.meta["value"] == a.meta["value"]
                    and abs(k.top - a.top) <= 15 and abs(k.x0 - a.x0) <= 60), None)
        if dup:
            # junta evidência (prefere o que tem R$ próprio)
            dup.detector += "+" + a.detector
            dup.raw_words.extend(a.raw_words)
        else:
            kept.append(a)
    return kept


# ------------------------------ tiers por quantidade ---------------------------
QTY_WORDS = re.compile(r"^\d{1,2}$|un|unid|c[oó]d|cada|par|por|ml|g\b|pts")


def detect_quantity_tiers(price: Anchor, words: List[Word]) -> List[dict]:
    """Procura, em uma janela vertical perto do preço, linhas de tier:
    '1 POR R$ 8,49' | '2 POR R$ 6,99'. Retorna lista {qty, value, row}."""
    tiers = []
    rows = physical_lines([w for w in words
                           if price.top - 30 <= w.bottom <= price.bottom + 40
                           and price.x0 - 150 <= w.x0 <= price.x1 + 120])
    for row in rows:
        txt = row_text(row).upper()
        if is_dims_row(row):
            continue  # '0,35 G | 02 PTS' não é tier
        has_price = any(RE_INT_STRICT.fullmatch(x.text) for x in row)
        has_r = any(x.text.startswith("R$") for x in row)
        if not (has_price and (has_r or "POR" in txt or "CADA" in txt or "PAR" in txt)):
            continue
        vals = [x.text for x in row if RE_INT_STRICT.fullmatch(x.text)]
        mq = re.search(r"^\s*(\d{1,2})\s*(?:UN|UNID|CX|CJ|POR|X)?", txt)
        if mq and txt.split()[0].isdigit():
            qty = mq.group(1)
        else:
            qty = "?"
        tiers.append({"qty": qty, "value": vals[0] if vals else "", "row": txt})
    return tiers


def numeric_value(txt: str) -> Optional[float]:
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", txt)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


# ------------------------------ associação por vizinhança -----------------------
def associate(page_words: List[Word], codes: List[Anchor], prices: List[Anchor]) -> List[dict]:
    """Para cada code, escolhe o preço mais provável: mesmo bloco vertical e coluna.
    Registra evidências (distância, alinhamento, tier). Sem inventar."""
    # 1) agrupa preços empilhados (mesma coluna X, |Δtop| <= 45px) em blocos
    pstack = []
    used = set()
    for p in sorted(prices, key=lambda a: (a.x0, a.top)):
        if id(p) in used:
            continue
        group = [p] + [q for q in prices
                       if id(q) not in used and q is not p
                       and abs(q.cx - p.cx) <= 60 and q.top - p.top <= 45 and q.top >= p.top - 8]
        for g in group:
            used.add(id(g))
        pstack.append(group)
    price_blocks = [g for g in pstack if g]

    results = []
    for c in codes:
        cands = []
        for block in price_blocks:
            top = min(b.top for b in block)
            bot = max(b.bottom for b in block)
            cx0 = min(b.x0 for b in block)
            cx1 = max(b.x1 for b in block)
            bcx = (cx0 + cx1) / 2.0
            # preço deve estar abaixo do código (ou quase na mesma linha)
            if top < c.bottom - 60:
                continue
            if top - c.bottom > 340:
                continue
            if abs(bcx - c.cx) > 420:
                continue
            d = min(b.dist2(c) for b in block)
            aligned = abs(bcx - c.cx) <= 180
            dist_h = abs(bcx - c.cx)
            cands.append((d, -int(aligned), dist_h, block))
        if not cands:
            results.append({"code": c.text, "x": round(c.x0, 1), "top": round(c.top, 1),
                            "prices": [], "status": "SEM_PRECO", "reason": "sem_preço_próximo"})
            continue
        cands.sort(key=lambda t: (t[1], t[2], t[0]))
        best_block = cands[0][3]
        second_block = next((b for d, al, h, b in cands[1:]
                             if abs(b[0].top - best_block[0].top) > 60), None)
        closes = sorted(cands, key=lambda t: t[0])
        ambiguous = len(closes) >= 2 and closes[1][0] < closes[0][0] * 1.6 and \
            closes[0][1] == closes[1][1]
        lst = [{"value": b.meta["value"], "x": round(b.x0, 1), "top": round(b.top, 1)}
               for b in sorted(best_block, key=lambda q: q.top)]
        tiers = []
        for b in best_block:
            tiers.extend(detect_quantity_tiers(b, page_words))
        ro = {"code": c.text, "x": round(c.x0, 1), "top": round(c.top, 1),
              "prices": lst,
              "melhor_evid": f"dist={closes[0][0]:.0f}px",
              "status": "CONFLITO" if ambiguous else "OK",
              "second_block": second_block is not None}
        if tiers:
            ro["tiers"] = tiers
        results.append(ro)
    return results


# ------------------------------ driver -----------------------------------------
def run(pdf_key, pno, label):
    if not pdf_key:
        return
    path = pdf_key
    words = load_words(path, pno)
    rows = physical_lines(words)
    prices = detect_prices(words)
    codes = detect_codes(words, rows)
    print(f"== {label} p{pno} | words={len(words)} prices={len(prices)} codes={len(codes)} ==")
    print("  PRECOS:")
    for p in prices:
        print(f"    {p.text!r} val={p.meta['value']} x={(p.x0):.0f} y={(p.top):.0f} [{p.detector}]")
    print("  CODIGOS:")
    for c in codes:
        print(f"    {c.text} x={c.x0:.0f} y={c.top:.0f}")
    res = associate(words, codes, prices)
    print("  ASSOCIACOES:")
    for r in res:
        pstr = ", ".join(f"{x['value']}@{x['top']:.0f}" for x in r["prices"])
        tier = "; ".join(f"{t['qty']}->{t['value']}" for t in r.get("tiers", []))
        fl = " CONFLITO~bloco2" if r.get("second_block") else ""
        print(f"    {r['code']} -> {pstr or '-'} [{r['status']}]{fl} T:[{tier}] : {r.get('melhor_evid', r.get('reason',''))}")
    print()


if __name__ == "__main__":
    avon = os.path.join(BASE, "AVON CICLO 15.pdf")
    casa = os.path.join(BASE, "AVON CASA CICLO 15.pdf")
    oui = os.path.join(BASE, "catalogo_oui_202617 (2).pdf")
    botic = os.path.join(BASE, "catalogo_boticario_202614 (1).pdf")
    eud = os.path.join(BASE, "catalogo_eudora_202616.pdf")
    ely = next((x for x in glob.glob(os.path.join(BASE, "*.pdf"))
                if "elyssence" in os.path.basename(x).lower()), None)
    run(avon, 65, "avon_ciclo")
    run(avon, 58, "avon_ciclo")
    run(casa, 22, "avon_casa")
    run(casa, 34, "avon_casa")
    run(oui, 3, "oui")
    run(ely, 3, "elyssence")
    run(botic, 15, "boticario")
    run(eud, 4, "eudora")