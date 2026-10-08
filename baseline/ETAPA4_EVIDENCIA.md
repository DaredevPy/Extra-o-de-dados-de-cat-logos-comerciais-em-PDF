# ETAPA 4 — Modelo de Evidências

**Data:** 2026-10-07 — **Status:** concluída (sem alterações em `core/parser.py`)

## O que foi analisado
- Protótipo espacial (ETAPA 3) mostrava que dados (preços/códigos) só são confiáveis se
  tiverem **origem rastreável e geometria associada**.
- Necessidade de representar multiplicidades reais: 1 código→N preços (tiers/promo),
  N códigos→1 preço (tons), sem forçar `preco: float` único.
- Necessidade de *não inventar*: ausência de contexto = `NÃO DETERMINADO`, divergência = `CONFLITO`.

## O que foi criado (pacote isolado `core/analysis/`)
| Módulo | Conteúdo |
|---|---|
| `elements.py` | `BBox` (normalizado, overlapa, contém, distância), `PageElement` (palavra/rect/line/image/table), `Anchor` (valor+tipo+bbox+página+detectors+confiança), `merge_anchors` |
| `evidence.py` | `Evidence` (claim, método, polaridade +1/-1/0, peso, bboxs), `EvidenceLog` (consultável por página/método) |
| `regions.py` | `Region` (hipótese de bloco), `detect_gaps`, `build_grid_regions` (colunas a partir de códigos), `assign_anchors_to_regions` |
| `confidence.py` | tabela central `WEIGHTS` (positivas/negativas), `ConfidenceScorer` determinístico, buckets `ALTA/MEDIA/REVISAR` |
| `associations.py` | `PriceCondition` (valor, quantidade, unidade, tipo), `Association` (códigos, descrição, preços[], status), `price_conditions_from_anchors`, `cluster_price_conditions` |

## Demonstração em PDFs reais (`scratch/etapa4_harness.py`)
Por página: inventário → âncoras → regiões → associações rastreáveis.

- **avon p65:** 11 códigos / 9 preços (incluindo `17,99` e `20,99` reconstruídos de
  `R$17,99CA`)—associações por coluna/bloco propostas com distância e bbox da região.
- **avon p7:** 28 códigos (batons) → preço único 49,99 agrupado como esperado;
  código **sem preço próximo fica sem associação** (não inventa).
- **casa p22:** preços aninhados `22,99/19,99` e `19,99/16,99` capturados como **blocos
  empilhados**; `210590` sem preço identificado → sem associacação.
- **elyssence p3:** `4093 → 96,59`; 4089-4092 `SEM_PRECO` preservado.

Detalhe importante: `detect_anchors` com `RE_VALUE.fullmatch` perdia `R$17,99CA`
(0 preços em casa p22); corrigido para `search` com posição do dígito.

## Testes
- `tests/test_analysis.py` — 8 unit tests (BBox, gaps, regiões por coluna, merge de âncoras,
  pesos centrais, tiers por quantidade, cluster empilhado, não-invenção) — **8/8 PASS**.
- Suíte existente `tests/test_app.py` (GUI + 30 produtos) — **ininterrupta** (ainda 30/30).

## Problemas residuais (encaminhados à ETAPA 5)
1. Associação dentro da região usa só proximidade (distância mínima abaixo do código);
   não distingue bloco-columnas repetidas em página inteira (ex: avon p7 com 2 bandas).
2. `Tier de quantidade` (1→8,49 / 2→6,99) ainda não mapeado automaticamente (harness
   propõe blocos, faltando `qty_by_value`).
3. STATUS/CONFLITO só existem como campos; a **reconciliação entre scanners**
   (texto vs espaço vs tabela) será a ETAPA 5.

## Decisões
- Não trocar pdfplumber; manter inventário bruto em `PageElement` (caminho para
  comparar alternativas futuras).
- Pesos finais serão calibrados na ETAPA 6/7 (aguardando testes sintéticos A–J).