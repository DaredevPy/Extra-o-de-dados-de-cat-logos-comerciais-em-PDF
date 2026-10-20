# -*- coding: utf-8 -*-
"""Detecção de preço riscado (traço diagonal) — "preço antigo".

Regra do usuário: o preço que tem um traço na diagonal é o PREÇO ANTIGO.
A marcação é feita na âncora do preço (``meta["struck"] = True``) para que a
reconciliação não trate antigo e atual como preços concorrentes.

Critérios geométricos (todos necessários):
  * traço diagonal curto e visível (já filtrado na extração do PDF);
  * cobre a maior parte da LARGURA do token de preço (~ 0.55 a 1.8x);
  * os dois extremos ficam na vizinhança do token (não é swoosh de logo);
  * o ponto médio do traço cai na FAIXA VERTICAL do token.

Isso evita os falsos positivos de curvas decorativas longas (Boticário/Eudora)
e os traços brancos (invisíveis em fundo branco).
"""
from __future__ import annotations

from typing import Iterable, List

from core.analysis.elements import Anchor


def stroke_marks_bbox(bbox, stroke: dict) -> bool:
    """O traço diagonal ``stroke`` risca a caixa ``bbox``?"""
    try:
        bx0, by0, bx1, by1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
        x0, y0 = float(stroke["x0"]), float(stroke["y0"])
        x1, y1 = float(stroke["x1"]), float(stroke["y1"])
    except (KeyError, TypeError, ValueError):
        return False
    w = max(bx1 - bx0, 1.0)
    h = max(by1 - by0, 1.0)
    slo, shi = sorted((x0, x1))
    ytop, ybot = sorted((y0, y1))
    span = shi - slo
    if span < 0.5 * w:
        return False  # traço curto demais para riscar o preço
    if span > 2.0 * w + 12.0:
        return False  # traço muito mais largo que o token (decoração)
    coverage = max(0.0, min(shi, bx1 + 2.0) - max(slo, bx0 - 2.0)) / w
    if coverage < 0.55:
        return False
    mx = 0.35 * w + 6.0
    if slo < bx0 - mx or shi > bx1 + mx:
        return False  # extremos longe do token
    my = 0.55 * h + 3.0
    if ytop < by0 - my or ybot > by1 + my:
        return False  # traço invade outra linha/produto
    if (ybot - ytop) < max(2.0, 0.18 * h):
        return False  # praticamente horizontal: não é o risco diagonal
    if not (by0 - 2.0 <= (ytop + ybot) / 2.0 <= by1 + 2.0):
        return False  # centro do traço fora da faixa do token
    return True


def mark_struck_prices(prices: Iterable[Anchor],
                       strokes: List[dict]) -> int:
    """Marca em ``prices`` as âncoras riscadas por um traço diagonal.

    Retorna a quantidade de preços marcados. Não altera valores/posições.
    """
    if not strokes:
        return 0
    marked = 0
    for a in prices:
        if a.meta.get("struck"):
            continue
        for s in strokes:
            if stroke_marks_bbox(a.bbox, s):
                a.meta["struck"] = True
                a.meta["strike"] = {"x0": round(float(s["x0"]), 1),
                                    "y0": round(float(s["y0"]), 1),
                                    "x1": round(float(s["x1"]), 1),
                                    "y1": round(float(s["y1"]), 1)}
                marked += 1
                break
    return marked
