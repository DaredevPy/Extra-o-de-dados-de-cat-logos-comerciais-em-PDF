# ETAPA 8 — Leitura Estrutural da Página 5 (Região Comercial Avon)

## Objetivo
Fazer o extrator interpretar ESTRUTURALMENTE uma página comercial complexa — não como
texto linear — e comprovar num caso real (AVON CASA CICLO 15, página 5): uma coleção com
**5 códigos/variantes**, **descrição compartilhada**, **preço por quantidade (1/2/3 POR)**
e uma **promoção em bloco separado** que nunca contamina o preço dos produtos.

## Arquivos alterados/novos
- `core/analysis/commercial.py` (novo) — scanner estrutural de regiões comerciais.
- `core/pipeline.py` — integração `_structure_scan` + `quantity_prices` + `variation`.
- `core/analysis/reconcile.py` — descrição estrutural como autoridade.
- `core/models.py` — campos `variation` e `quantity_prices`.
- `tests/test_pagina5.py` (novo) — bateria da missão (sintética + real com `skipif`).

---

## 1) Como o extrator leu a página 5

A página é interpretada como **composição espacial**, em 6 passos:

1. **Classificação semântica por palavra** (código / preço / quantidade / promoção /
   condição / desconto / percentual / etc.).
2. **Refinamento de linha** — encontra os pares "N POR" das regras de quantidade
   (vira `REGRA_PRECO`) e detecta frases condicionais ("Na compra de...").
3. **Bloco promocional** separado por sementes fortes (LEVE / GANHE / "60% DE DESCONTO" /
   condição reforçada por verbo) — o preço **dentro** desse bloco é marcado como
   `promo_price_ids` e **nunca** vira preço de produto.
4. **Regras por quantidade** — "1 POR 19,99 / 2 POR 17,99 / 3 POR 15,99 CADA" viram uma
   **escada de tiers** `{1: 19,99; 2: 17,99; 3: 15,99}`.
5. **Unidades comerciais** — cada código + nome/variação imediatamente abaixo.
6. **Descrição compartilhada do grupo** — coletada no painel das regras, com as palavras
   da oferta promocional e os dígitos de regra **excluídos**.

Resultado real da página 5 (`AVON CASA CICLO 15.pdf`, itens = código/variação):

| Código | Variação | Preço | Preço 2 | Preços por quantidade |
|---|---|---|---|---|
| 263406 | Marshall | 19,99 | 17,99 | 1 x 19,99; 2 x 17,99; 3 x 15,99 |
| 263656 | Chase | 19,99 | 17,99 | 1 x 19,99; 2 x 17,99; 3 x 15,99 |
| 263396 | Skye | 19,99 | 17,99 | 1 x 19,99; 2 x 17,99; 3 x 15,99 |
| 263647 | Skye e Rubble | 19,99 | 17,99 | 1 x 19,99; 2 x 17,99; 3 x 15,99 |
| 249833 | Chase e Marshall | 19,99 | 17,99 | 1 x 19,99; 2 x 17,99; 3 x 15,99 |

Descrição compartilhada (idêntica para os 5, sem resíduo de promoção/regra):
`Copo com Pingente Patrulha Canina. Plástico. 8,3 cm diâm. X 18,5 cm alt. | 03 pts`

A promoção (R$ 9,99 / "LEVE 1 CANECA DIVERTIDA POR..." / "60% DE DESCONTO") é detectada
como oferta e **não** aparece como preço de nenhum código.

## 2) Erros que a página 5 causaria (e foram eliminados)

| Sintoma antigo | Tratamento atual |
|---|---|
| Preço promocional **9,99** competindo com 19,99 (e às vezes vencendo) | `promo_price_ids` exclui do pool; `prices_product` sem promo |
| Texto "Na compra de 2 itens", "LEVE CANECA DIVERTIDA" caído na descrição | palavras do bloco promo excluídas da descrição |
| "1/2/3 POR R$ 15,99 CADA" impresso na descrição | dígitos de regra = `REGRA_PRECO` (fora); `QUANTIDADE` ("03 pts") permanece |
| 3 regras tratadas como "3 preços do produto" | escada `quantity_prices` (produto tem 1 preço + N tiers) |
| Nome da variante duplicado na descrição | `variation` é coluna própria, não duplica |
| Descrição "colada" do texto contínuo errado (painel vs. código) | descrição do grupo coletada no painel das regras |

## 3) Novos conceitos/categorias

- **Região Comercial** (`CommercialRegion`): bloco intermediário código(s) + descrição +
  regras + promoção separada, ANTES da normalização em `ProductItem`.
- **Unidade comercial**: código + **variação/nome** (evidência: proximidade abaixo do código).
- **Regra de preço por quantidade** (`QuantityRule`): "N POR R$ X CADA".
- **Escada de tiers** (`tier_rules` → `quantity_prices`): coluna "Preços por quantidade".
- **Oferta promocional separada** (`PromotionalOffer`): condição + benefício + preço + desconto.
- **Preços promocionais excluídos**: `promo_price_ids` nunca viram candidato de produto.
- **Método `regiao_comercial`** na reconciliação (autoridade de descrição + evidência tier).
- **Regra de não-invenção por escada**: só há inferência de preço por quantidade com
  **≥ 2 regras** — um banner único ("2 POR R$ 6,99 ... Combine como quiser") é oferta
  combinacional, não preço de cada produto (corrige a regressão real da pág. 65).

## 4) Testes criados

`tests/test_pagina5.py` (5 testes; os leiautes sintéticos espelham a geometria real da p5):

1. `test_estrutura_regiao_comercial_pagina5` — 5 códigos, variações, escada 1/2/3 POR,
   promo separada (9,99 / 60%), descrição compartilhada sem resíduo.
2. `test_regra_unica_banner_nao_vira_preco_estrutural` — guarda anti-regressão p65.
3. `test_regra_unica_banner_fim_a_fim` — banner único não gera produto com 6,99.
4. `test_pagina5_fim_a_fim` — pipeline completa no leiaute sintético.
5. `test_pagina5_real` — PDF real com `skipif` quando o arquivo não está no repositório.

Execução: `python -m pytest tests -q` → **22 passed** (17 existentes + 5 novos).

## 5) Antes / Depois

**Página 5 real (informação estruturada):**
- **ANTES**: preço promocional (9,99) disputava com 19,99; descrição colecionava fragmentos
  da promoção e das regras; "1/2/3 POR" aparecia como texto de produto; só 1 preço por item.
- **DEPOIS**: 19,99 + 17,99 + escada `1 x 19,99; 2 x 17,99; 3 x 15,99`; descrição exata
  compartilhada; variação na coluna própria; promo isolada (stats `promos=1`,
  `grupo_comercial=1`).

**Regressão/Variação no caso real J (AVON CICLO 15, 119 itens de referência):**
| Estado | Preço correto | Descrição correta | Precisão | Recall |
|---|---|---|---|---|
| Baseline (pré-scan estrutural) | 102 / 119 | 36 / 119 | 1,0 | 1,0 |
| Com scan estrutural (1ª integração) | 97 / 119 | 32 / 119 | 1,0 | 1,0 |
| **Final (com guarda ≥2 regras)** | **102 / 119** | **36 / 119** | **1,0** | **1,0** |

A regressão intermediária estava isolada na pág. 65 (3 códigos) por um banner
combinatório com regra única; foi eliminada **sem** perda dos ganhos da página 5.

## 6) Ambiguidades / limitações remanescentes

- Produtos com embreagem **legítima** de "1 POR" isolado não ganham `quantity_prices`
  (trade-off honesto da regra de escada).
- Itens vistos apenas pelo scanner estrutural permanecem `REVISAR` ("fonte única").
- Quando existe texto individual + painel do grupo, a descrição **do painel** vence
  (ainda sem granularidade por produto).
- A variação multi-palavra ("Skye e Rubble") depende de proximidade espacial das palavras;
  nomes muito largos podem ser cortados.
- A ligação regra→código ainda não aplica o limite `GRUPO_FAR=300 px` (candidatos cobrem
  todos os códigos da página) — melhoria futura.
- Linhas de benefício da oferta ("60% DE DESCONTO") ficam registradas como *benefit* da
  promoção (nota), não como preço.

---

## Reproduzir
```bash
python -m pytest tests -q                    # 22 passed
python scripts/run_synthetic.py              # caso J: preço 102/119, desc 36/119, P=1.0 R=1.0
```
O teste real exige `AVON CASA CICLO 15.pdf` na raiz do repositório.