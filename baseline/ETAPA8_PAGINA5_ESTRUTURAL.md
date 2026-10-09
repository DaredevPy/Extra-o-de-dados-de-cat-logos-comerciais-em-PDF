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
- **Guarda `GRUPO_FAR` no vínculo regra→código**: o código só recebe a escada se a
  distância em X até o **intervalo** do painel de regras for ≤ 300 px (não ao centro);
  um banner de página inteira afastado não sequestra mais códigos.
- **Scan `preco_painel` (por coluna)**: para cada código, confirma por alinhamento a
  âncora do tier cuja **coluna de preço** está mais próxima no painel do rodapé.
  O subset por coluna é por projeto (não é "ambiguidade"), então não penaliza o score;
  eleva a confirmação estrutural de `REVISAR` (fonte única) para `MEDIA`.
- **Imagens como evidência** (`PageData.images`): a base da zona de ilustração do produto
  (imagens não-fundo) gera a evidência `painel_abaixo_ilustracao` quando o painel de
  regras cai **abaixo** da ilustração — o layout de página 5 fica reconhecível.
- **Autoridade estrutural na reconciliação**: quando `regiao_comercial` confirma o vínculo,
  penalidades geométricas de *outros* scanners (`distancia_longa`) e divergências de
  descrição vindas de scanner não-estrutural **não rebaixam** o score — as notas
  continuam visíveis para rastreabilidade.
- **Variação não é divergência**: a descrição do scanner geométrico (texto contíguo
  contaminado) é comparada ignorando os tokens da `variation` do produto.
- **Nota de preço comum do grupo (N→1)**: `stamp_shared_notes` anota
  `mesmos precos de: ...` nos itens que compartilham a mesma âncora de preço.

## 4) Testes criados

`tests/test_pagina5.py` (6 testes; os leiautes sintéticos espelham a geometria real da p5):

1. `test_estrutura_regiao_comercial_pagina5` — 5 códigos, variações, escada 1/2/3 POR,
   promo separada (9,99 / 60%), descrição compartilhada sem resíduo.
2. `test_regra_unica_banner_nao_vira_preco_estrutural` — guarda anti-regressão p65.
3. `test_regra_unica_banner_fim_a_fim` — banner único não gera produto com 6,99.
4. `test_pagina5_fim_a_fim` — pipeline completa no leiaute sintético (agora exige
   status `MEDIA` + notas `preco_painel` e `mesmos precos de`).
5. `test_pagina5_real` — PDF real com `skipif` quando o arquivo não está no repositório.
6. `test_reconcile_descricao_ignora_variacao` — variação ("Chase e Marshall") não vira
   divergência de descrição; penalidade geométrica/desc. de scanner periférico não
   rebaixa o vínculo estrutural.

Execução: `python -m pytest tests -q` → **23 passed** (17 existentes + 6 novos).

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
| **Com melhorias (painel/rodapé + GRUPO_FAR + variação)** | **102 / 119** | **36 / 119** | **1,0** | **1,0** |

A regressão intermediária estava isolada na pág. 65 (3 códigos) por um banner
combinatório com regra única; foi eliminada **sem** perda dos ganhos da página 5.
As melhorias do leiaute "códigos no topo + painel de preço no rodapé" **preservam**
os números (102/36) — o caso J não regride.

## 7) Melhorias — leiaute "códigos no topo + painel de preço no rodapé"

Página 5 real = códigos nas colunas (y≈109–181), promoção à direita (483–559) e
painel de tiers no rodapé (y≈431–453): `1 POR R$19,99` → `2 POR R$17,99` →
`3 POR R$15,99` + descrição do grupo (y≈445–461) sob a coluna mais à esquerda.

| Problema | Solução implementada | Resultado na p5 real |
|---|---|---|
| Painel a ~300 px dos códigos: só o scan estrutural via preço (status `REVISAR`, conf=69) | Scan `preco_painel` por coluna: alinhamento + `painel_abaixo_ilustracao` (imagem) | 5 itens **MEDIA** (conf 81–91) |
| Regra afastada demais poderia sequestrar códigos de outra região | Guarda `GRUPO_FAR` (distância X ao **intervalo** do painel ≤300) | combinada com a guarda ≥2 regras, o banner p65 continua NÃO_DETERMINADO |
| Ruído `desc diverge` só pela variação / texto contíguo da promoção | Comparação de descrição ignora tokens da `variation`; divergência de scanner periférico não penaliza | variações "Chase e Marshall" etc. limpas |
| Preço de grupo aparecendo como preço individual | Nota `mesmos precos de: ...` (N→1) via `stamp_shared_notes` | 5 itens anotados |
| Zona de produto não delimitada por imagem | `PageData.images` + zona de ilustração; imagem de fundo (área ≥55% da página) descartada | evidência fraca, nunca inventa preço |
| Sem teste do leiaute real | `test_pagina5_fim_a_fim` + reconciliação com variação | 6 testes verdes |

**Números**: `python -m pytest tests -q` → **23 passed**; `run_synthetic.py` →
preço_OK=102/119, desc_OK=36/119, precisão=1.0, recall=1.0 (idêntico ao baseline).

## 6) Ambiguidades / limitações remanescentes

- Produtos com embreagem **legítima** de "1 POR" isolado não ganham `quantity_prices`
  (trade-off honesto da regra de escada).
- O scan `preco_painel` confirma por coluna o tier mais próximo; em grades muito
  largas pode alinhar à coluna vizinha (a guarda X + nota de subset mitigam).
- Quando existe texto individual + painel do grupo, a descrição **do painel** vence
  (ainda sem granularidade por produto).
- A variação multi-palavra ("Skye e Rubble") depende de proximidade espacial das palavras;
  nomes muito largos podem ser cortados.
- As imagens são, em muitas páginas, arte de fundo (descartadas): quando não há imagem,
  `painel_abaixo_ilustracao` fica desarmada (sem inventar fatos).
- Linhas de benefício da oferta ("60% DE DESCONTO") ficam registradas como *benefit* da
  promoção (nota), não como preço.

---

## Reproduzir
```bash
python -m pytest tests -q              # 23 passed
python scripts/run_synthetic.py        # caso J: preço 102/119, desc 36/119, P=1.0 R=1.0
```
O teste real exige `AVON CASA CICLO 15.pdf` na raiz do repositório.