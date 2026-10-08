# ETAPA 6 — Cenários Sintéticos + Calibração contra Catálogo Real (Avon)

## Objetivo
Validar o motor por evidências (`core/pipeline.py`) em cenários controlados (A–I) e calibra-lo
contra o catálogo real (J), preservando precisão sem nunca afirmar relações sem suporte.

## O que foi construído
- `scripts/generate_synthetic.py` — gera `synthetic/cenarios_AI.pdf` (9 páginas, cenários A–I)
  e `synthetic/ground_truth.json` (verdade manual por página).
- `scripts/run_synthetic.py` — roda o pipeline em A–I (PASS/FAIL) e dispara a avaliação do
  caso real J via `scripts/evaluate.py --mode evidence`.

## Cenários (todos PASS)
| Cenário | Descrição | Resultado |
|---|---|---|
| A | 1 código / 1 preço | PASS (REVISAR) |
| B | 2 códigos / 1 preço compartilhado | PASS |
| C | 1 código / 4 preços por quantidade (tiers) | PASS |
| D | 2 produtos próximos em colunas distintas | PASS |
| E | 2 linhas x 2 colunas, preço abaixo de cada código | PASS (dono do preço = código imediatamente acima) |
| F | geometria `39,90` vs texto `5,99` | PASS (CONFLITO com as duas âncoras) |
| G | código sem preço | PASS (honesto NÃO_DETERMINADO) |
| H | preço sem código | PASS (nenhum produto-fantasma) |
| I | preço empilhado + faixa promocional "ECONOMIZE" | PASS |

## Mecânicas calibradas na ETAPA 6
- **Guarda de preço**: valor exige centavos `,dd` OU prefixo `R$` no próprio token; exclusão de
  códigos 4–8 dígitos, `%`, e valores < R$1,00 ("0,35g"); zona de rodapé do catálogo ignorada.
- **Modelo "dono"** (`_owners`): cada preço pertence ao código imediatamente acima (maior `y1`
  menor que o topo do preço), com afinidade de coluna — resolve E, D e páginas reais.
- **Preço de seção** (`_assign_section_prices`): janela ±260px do centro da seção; modo GRADE
  (≤2 valores, ≥4 códigos sem preço → espalha o conjunto de preços) e modo FAIXA (vários preços →
  cada código pega o preço mais próximo abaixo). Códigos que JÁ têm preço próprio não são tocados.
- Depuração real via páginas 3/7/8/42/58/65/73 de `AVON CICLO 15.pdf`.

## Resultado no catálogo real (J) — 119 itens de referência
| Métrica | Baseline (legado) | Evidência |
|---|---|---|
| Códigos corretos | 119 / 119 | **119 / 119** |
| Preço correto | 103 / 119 | **102 / 119** |
| Descrição correta | 33 / 119 | **36 / 119** |
| Precisão | 1,0 | **1,0** (0 falsos positivos) |
| Recall | 1,0 | **1,0** |

Todos os registros evidência carregam status honesto (ALTA/MEDIA/REVISAR/CONFLITO/NÃO_DETERMINADO)
e nota/depuração. Diferença residual de 1 preço é resultado de vínculos ambíguos nessas páginas,
registrados como REVISAR (sem invenção).

## Testes
- `tests/test_analysis.py` (8) + `tests/test_reconcile.py` (9) + `test_app.py` smoke: 17 PASS.