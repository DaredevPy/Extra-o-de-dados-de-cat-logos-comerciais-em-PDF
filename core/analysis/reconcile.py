# -*- coding: utf-8 -*-
"""
Reconciliação de scanners (ETAPA 5).

Entrada: para um código, os candidatos de N métodos (scanners). Saída: UMA
associação reconciliada e rastreável que NUNCA escolhe silenciosamente entre
resultados divergentes — produz CONFLITO (mantendo todas as evidências) ou
NÃO_DETERMINADO (quando nada sustenta uma relação).

Regras de resolução (ordem de aplicação):
  1. Sem candidatos                     -> NÃO_DETERMINADO
  2. Nenhum candidato com preço         -> NÃO_DETERMINADO
  3. Todos os candidatos com preço têm o MESMO conjunto de valores
        -> concorda; +metodos_concordam se >=2 métodos; status por score
  4. Um conjunto é SUBCONJUNTO do outro (scanner não viu preço-2/promo)
        -> aceita a UNIÃO; nota 'scan incompleto'; status MEDIA (não ALTA)
  5. Conjuntos MATERIALMENTE diferentes -> CONFLITO (sem escolha): mantém todas
        as âncoras, nota lista método->valores, score calculado p/ transparência
  6. Descrição: divergência entre métodos é registrada em nota (sem hard CONFLITO,
        pois o preço é a autoridade); fica o candidato de maior score preliminar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.analysis.associations import (Association, PriceCondition,
                                        parse_value)
from core.analysis.confidence import ConfidenceScorer, WEIGHTS
from core.analysis.elements import Anchor, BBox
from core.analysis.evidence import Evidence, NEUTRAL


@dataclass
class Candidate:
    """Proposta de um único scanner para um código."""
    method: str
    code: str
    page: int
    prices: List[Anchor] = field(default_factory=list)      # 0..N âncoras de preço
    description: Optional[str] = None
    desc_anchor: Optional[Anchor] = None
    evidences: List[Evidence] = field(default_factory=list)
    preliminary_score: float = 0.0
    note: str = ""

    @property
    def has_price(self) -> bool:
        return any(self.prices)

    def value_set(self) -> Optional[frozenset]:
        # preço riscado (ANTIGO) não concorre com o preço atual na
        # reconciliação: ele é contexto do mesmo código, não outra proposta.
        vals = {v for a in self.prices if not a.meta.get("struck")
                for v in (parse_value(a.value),) if v is not None}
        return frozenset(vals) if vals else None

    def value_list(self) -> List[float]:
        vals = [v for v in (parse_value(a.value) for a in self.prices) if v is not None]
        return vals


class Reconciler:
    def __init__(self, scorer: Optional[ConfidenceScorer] = None):
        self.scorer = scorer or ConfidenceScorer()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _dedupe_anchors(anchors):
        seen = {}
        for a in anchors:
            v = parse_value(a.value)
            key = (v if v is not None else a.value,
                   round(a.bbox.x0, 1), round(a.bbox.y0, 1))
            if key not in seen:
                seen[key] = a
        return list(seen.values())

    @staticmethod
    def _dedupe_evidence(evidences):
        """Evidências positivas do mesmo fato ficam apenas UMA vez (regra-claim);
        negativas mantêm todas as ocorrências (cada geometria é distinta)."""
        out = []
        pos_index = {}
        for e in evidences:
            if e.polarity > 0:
                cur = pos_index.get(e.claim)
                if cur is None or abs(e.weight) > abs(cur.weight):
                    if cur is not None:
                        out.remove(cur)
                    pos_index[e.claim] = e
                    out.append(e)
            else:
                out.append(e)
        return out
    def reconcile(self, code: str, page: int,
                  candidates: List[Candidate],
                  tiers: Optional[Dict[str, int]] = None,
                  region: Optional[BBox] = None,
                  variation: str = "") -> Association:
        """Reconcilia os candidatos de todos os scanners para um código.
        `variation` é a variação do produto (ex.: 'Chase e Marshall') usada para
        ignorar divergências de descrição causadas SÓ pela variação."""
        tiers = tiers or {}
        if not candidates:
            return Association(page=page, codes=[code], status="NAO_DETERMINADO",
                               note="sem candidatos de nenhum scanner")

        # --- separa candidatos com preço ---
        priced = [c for c in candidates if c.has_price]
        if not priced:
            metodos = ", ".join(c.method for c in candidates)
            return Association(page=page, codes=[code], status="NAO_DETERMINADO",
                               note=f"nenhum scanner encontrou preço (metodos: {metodos})")

        # --- compara conjuntos de valores ---
        sets = {}
        for c in priced:
            sets[c.method] = c.value_set()

        # âncoras riscadas (PREÇO ANTIGO): context, nunca candidato a preço
        # atual. Preserva o valor sem competir com o preço vigente.
        all_anchors = self._dedupe_anchors(
            [a for c in priced for a in c.prices if a.meta.get("struck")]
            + [a for c in priced for a in c.prices if not a.meta.get("struck")])
        distinct_sets = {frozenset(s) for s in sets.values() if s is not None}
        notes: List[str] = []
        merged_evidences: List[Evidence] = [e for c in priced for e in c.evidences]

        def _agree() -> bool:
            return len(distinct_sets) == 1

        def _subset() -> Optional[str]:
            # retorna o método que tinha o conjunto menor (incompleto), se houver
            master = max(distinct_sets, key=len)
            for m, s in sets.items():
                if s is not None and s != master and s < master:
                    return m
            return None

        status_split = "NAO_DETERMINADO"
        if not distinct_sets:
            # só há preço riscado (antigo) para o código: não é conflito.
            status_split = "AGREE"
            notes.append("apenas preco riscado (antigo) encontrado")
        elif _agree():
            if len(priced) >= 2:
                merged_evidences.append(
                    Evidence("divergencia persistida inexistente; concordancia entre "
                             f"{', '.join(sorted(sets))}", "reconciliation", page,
                             weight=WEIGHTS["metodos_concordam"]))
                notes.append(f"concordancia entre {len(priced)} scanners")
            status_split = "AGREE"
        else:
            m_sub = _subset()
            if m_sub:
                # preco_painel é, POR PROJETO, um scan de UMA coluna (o tier
                # mais próximo do código): o subset dele não é ambiguidade
                # geométrica, é a delimitação da confirmação. Penalidade só
                # para scanners que deveriam ter visto o conjunto completo.
                if m_sub != "preco_painel":
                    merged_evidences.append(
                        Evidence(f"scanner {m_sub} incompleto (conjunto menor)",
                                 "reconciliation", page, NEUTRAL,
                                 WEIGHTS["estrutura_ambigua"]))
                notes.append(f"scanner {m_sub} nao viu todos os precos (subset); usou a uniao")
                status_split = "PARTIAL"
            else:
                merged_evidences.append(
                    Evidence("scanners divergem nos conjuntos de precos", "reconciliation",
                             page, weight=WEIGHTS["metodos_divergem"]))
                for m, s in sorted(sets.items()):
                    notes.append(f"{m}: {sorted(s) if s else '[]'}")
                status_split = "CONFLICT"

        # --- descrição ---
        # a descrição do scanner ESTRUTURAL (região comercial) é a autoridade:
        # ela respeita a separação da promoção e a descrição compartilhada do
        # grupo, mesmo quando outros scanners pegaram texto contíguo conturbado.
        has_structural = "regiao_comercial" in sets
        desc = None
        desc_note: List[str] = []
        ordered = sorted(priced,
                         key=lambda x: (x.method != "regiao_comercial",
                                        -x.preliminary_score))
        def _same_description(a: str, b: str) -> bool:
            """Compara ignorando os tokens da variação do produto: a divergência
            'Chase e Marshall' vs. descrição-base é RUÍDO, não conflito.
            (a descrição-base pode omitir a variação, que já vem no campo próprio.)"""
            if a == b:
                return True
            drop = {t.strip(".,|:;-") for t in variation.split() if t.strip()}
            if not drop:
                return False
            def _norm(s: str) -> str:
                return " ".join(t.strip(".,|:;-") for t in s.split()
                                if t.strip(".,|:;-") not in drop)
            return _norm(a) == _norm(b)

        for c in ordered:
            if c.description:
                if desc is None:
                    desc = c.description
                elif not _same_description(c.description, desc):
                    desc_note.append(f"desc diverge em {c.method}: '{c.description}'"[:160])
        if desc_note:
            notes.append("; ".join(desc_note))
            # divergência de descrição vinda de scanner NÃO-estrutural é texto
            # contíguo contaminado (promoção/rodapé), não conflito de produto:
            # nota preservada, mas nunca rebaixa a associação já confirmada.
            merged_evidences.append(
                Evidence("descricoes divergem entre metodos", "reconciliation",
                         page, NEUTRAL,
                         0.0 if has_structural else WEIGHTS["estrutura_ambigua"]))

        # --- política de autoridade estrutural ---
        # quando o vínculo estrutural (painel de regras por quantidade) já
        # confirma o código, penalidades geométricas de OUTROS scanners (dist.
        # 'longa', posto que o layout de painel no rodapé explica a distância)
        # não rebaixam o score. As notas continuam visíveis para rastreabilidade.
        if has_structural:
            merged_evidences = [
                e for e in merged_evidences
                if not (e.weight < 0 and e.method != "reconciliation")]

        # --- monta associação reconciliada ---
        # evidências de fatos físicos não podem ser somadas por scanner:
        # o mesmo preço visto por N scanners NÃO pesa N vezes (dedupe de positivas).
        evs = self._dedupe_evidence(merged_evidences)
        score, status = self.scorer.score_and_status(evs)
        if status_split == "CONFLICT":
            status = "CONFLITO"
        elif status_split == "PARTIAL":
            status = "MEDIA" if status not in ("REVISAR",) else status
        elif status_split == "AGREE":
            # fonte única: mesmo com score alto, não é ALTA (não confirmada)
            metodos_unicos = len({c.method for c in priced}) == 1
            if metodos_unicos:
                if status == "ALTA":
                    status = "MEDIA"
                notes.append("fonte unica (nao confirmada por outro scanner)")

        assoc = Association(
            page=page,
            codes=[code],
            description=desc,
            prices=self._to_price_conditions(all_anchors, tiers),
            region=region,
            evidences=merged_evidences,
            confidence=score,
            status=status,
            note=" | ".join(notes) or status_split,
        )
        return assoc

    def _to_price_conditions(self, anchors: List[Anchor],
                             tiers: Dict[str, int]) -> List[PriceCondition]:
        com_qty = []
        for a in sorted(anchors, key=lambda x: (x.bbox.y0, x.bbox.x0)):
            v = parse_value(a.value)
            if v is None:
                continue
            qty = tiers.get(a.value.strip())
            struck = bool(a.meta.get("struck"))
            com_qty.append(PriceCondition(
                value=v,
                quantity=qty,
                kind="previous" if struck else ("quantity" if qty else "regular"),
                raw=a.value,
                bbox=a.bbox,
            ))
        return com_qty

    # ------------------------------------------------------------------ #
    def shared_price_groups(self, associations: List[Association]) -> Dict[tuple, List[str]]:
        """Agrupa códigos que compartilham EXATAMENTE a mesma âncora de preço
        (mesmo valor e mesma posição) — o caso N códigos -> 1 preço (ex: tons)."""
        groups: Dict[tuple, List[str]] = {}
        for a in associations:
            if not a.prices:
                continue
            p = a.prices[0]
            if not p.bbox:
                continue
            key = (round(p.value, 2), round(p.bbox.x0, 1), round(p.bbox.y0, 1))
            groups.setdefault(key, []).append(a.codes[0])
        return {k: v for k, v in groups.items() if len(v) > 1}

    def stamp_shared_notes(self, associations: List[Association]) -> None:
        """Anota nas associações os agrupamentos N->1 descobertos."""
        for key, codes in self.shared_price_groups(associations).items():
            for a in associations:
                if a.codes and a.codes[0] in codes and a.prices:
                    p = a.prices[0]
                    if p.bbox and (round(p.value, 2), round(p.bbox.x0, 1),
                                   round(p.bbox.y0, 1)) == key:
                        a.note = (a.note + " | mesmos precos de: " +
                                  ", ".join(c for c in codes if c != a.codes[0])).strip(" |")