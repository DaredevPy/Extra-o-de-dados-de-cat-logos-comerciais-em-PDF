# ETAPA 5 — Reconciliação de Scanners

**Data:** 2026-10-07 — **Status:** concluída
**Princípio:** NUNCA escolher silenciosamente entre resultados divergentes. Prioriza
`CONFLITO` / `NÃO_DETERMINADO`; `ALTA` exige confirmação.

## O que foi criado — `core/analysis/reconcile.py`
- `Candidate`: proposta de UM scanner (método, código, âncoras de preço, descrição,
  evidências, score preliminar).
- `Reconciler.reconcile()`: regras documentadas, aplicadas em ordem:
  1. sem candidatos → `NÃO_DETERMINADO`
  2. nenhum candidato com preço → `NÃO_DETERMINADO`
  3. todos concordam no MESMO conjunto → junta evidências + `metodos_concordam`
  4. um conjunto é SUBCONJUNTO (scanner não viu preço-2/promo) → **união preservada**,
     nota "scan incompleto", teto `MEDIA`
  5. conjuntos MATERIALMENTE diferentes → **CONFLITO**: mantém TODAS as âncoras,
     nota lista método→valores (sem escolha)
  6. fonte única → teto `MEDIA` (mesmo com score alto)
- Correções de desenho descobertas em campo:
  - **duplicação de âncoras** do mesmo preço físico entre scanners (dedupe por valor+bbox);
  - **inflação de score**: evidências positivas de fatos físicos são deduplicadas por
    regra (o mesmo preço visto por N scanners não pesa N vezes);
  - **cap de distância** (280px) nos scanners: além disso, `NÃO_DETERMINADO`, não "peso negativo".
- `shared_price_groups()` / `stamp_shared_notes()`: detecta **N códigos → 1 preço**
  (mesma âncora física) — ex.: tons de batom.

## Demonstração em PDFs reais (2 scanners concorrentes)
- `scanner_regional` (célula de grade de colunas) vs `scanner_coluna` (faixa de coluna por X dos códigos).

| Página | Antes (ETAPA 4, sem reconciliação) | Agora (ETAPA 5) |
|---|---|---|
| avon p65 | assoc. por proximidade crua | 1× `MEDIA` (178074/177795 concordância), **CONFLITO real** `178072` (regional 18,99 vs coluna 8,49 registrado na rodada anterior; pós-cap vira REVISAR fonte única — honesto), blocos empilhados 17,99/14,99 e 20,99/18,99 preservados com nota subset |
| avon p7 | preços atribuídos por região larga | 28 batons: N→1 detectado (grupos ex.: 135511/135512/148279/152749), sem ALTA espúria; quem ficou longe do preço → `NÃO_DETERMINADO` |
| casa p22 | `210590` SEM associação | ganhou `19,99/16,99` via scanner de coluna (correto c/ referência), `262609` → `22,99/19,99`, trim: todos REVISAR (sem 2º scanner confirmando) |
| elyssence p3 | 4089–4092 ganhavam `96,59` (forçado) | 4089→`NÃO_DETERMINADO`; 4090/4091/4092→REVISAR com preço só como candidato; **4093→`96,59` MEDIA** (verdadeiro) — sem ALTA inventada |

## Phases do problema (métrica por página)
- avon p65: 10 REVISAR / 1 MEDIA (11 códigos)
- avon p7: 15 NÃO_DETERMINADO / 12 REVISAR / 1 MEDIA (28 códigos)
- casa p22: 4 REVISAR
- elyssence p3: 1 NÃO_DETERMINADO / 3 REVISAR / 1 MEDIA

## Testes
- `tests/test_reconcile.py` — 9/9 PASS (sem candidatos; sem preço; fonte única cap MEDIA;
  2 scanners concordam ALTA; divergência→CONFLITO preservando valores; conflito prevalece
  mesmo com score>70; subset mantém união; N→1; tiers reconciliados).
- Suites anteriores: `test_analysis.py` 8/8 PASS; `test_app.py` inalterado.

## Problemas residuais → ETAPA 6/7
1. Balanceamento dos pesos: com evidências mínimas (demo usa só 3 regras), saídas
   ficaram conservadoras (várias REVISAR). Calibrar com testes sintéticos A–J.
2. Preço "compartilhado" centralizado sob faixa de produtos (ex.: faixa de páginas) não
   distingue se pertence ao "row" do produto — precisa de regra de linha compartilhada.
3. `descrição` reconciliada está no nível mais simples (melhor score); nada foi alterado no
   pipeline atual de descrição.
4. Política de exportação de `REVISAR/CONFLITO` (emitir com flag vs omitir) → ETAPA 7.

## Decisões
- Hard cap de distância nos scanners (280px) é um filtro de "não-invenção", não apenas peso.
- Concordância entre scanners NÃO vira verdade: geometria fraca mantém REVISAR.
- `core/parser.py` continua intacto.