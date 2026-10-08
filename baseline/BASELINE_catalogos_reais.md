# Baseline — extrator atual em catálogos reais

Data: 2026-10-04. Parser não modificado. Métricas de cada catálogo em `baseline/*.json`.

| Catálogo | Páginas | Registros | Cód. únicos | Registros com cód+desc+preço | Sem desc |
|---|---|---|---|---|---|
| AVON CICLO 15 | 148 | 803 | 800 | 803 | 0 (mas descrição ruidosa) |
| AVON CASA CICLO 15 | 84 | 240 | 231 | 240 | 0 |
| catalogo_boticario_202614 | 184 | 19 | 19 | 13 | 6 |
| catalogo_eudora_202616 | 106 | 2 | 2 | 2 | 0 |
| Catálogo Elyssence com preço | 9 | 0 | 0 | 0 | - |
| catalogo_oui_202617 | 52 | 0 | 0 | 0 | - |

## Páginas problemáticas

- **AVON CICLO 15**: 25 páginas sem resultado (1,2,4,5,10,14,24,38,39,44,45,60,66,82,84,86,106,110,124,138,140,144,146,147,148); páginas com muitos registros: 76(32), 46(31), 7(28), 79(25)
- **AVON CASA**: 10 páginas sem resultado (capas e páginas de texto publicitário 1–4, 16, 40, 48–50, 82)
- **Boticário**: 167 de 184 páginas sem resultado; p.107 gerou 3; registros das p.15/16 com o texto inteiro da linha promovido a "código"
- **Eudora**: 105 de 106 páginas sem resultado
- **Elyssence**: 0 registros (todas as páginas)
- **O.U.i Paris**: 0 registros (todas as páginas)

## Estrutura diferente encontrada

1. **O.U.i Paris**: preços inteiros sem decimais (`R$ 389`) → nenhuma captura, pois o regex exige `,XX`
2. **Elyssence**: códigos com 4 dígitos (`4089 -`, `c�d.: 4093`) e preços `POR APENAS R$ 96,59` com dígitos separados → nenhuma captura
3. **Eudora**: códigos com 5 dígitos (`51432`, `58933`); preço de desconto `ECONOMIZE R$ 60,00` capturado como preço do produto (2 únicos registros são EAN fragments)
4. **Boticário**: códigos com 5 dígitos (`88911`, `48508`); produto e preço na mesma linha, mas o caminho de texto promove a linha inteira a código

## Amostra manual (classificação registro a registro)

### AVON CICLO 15 (medição com referência de 119 itens em 12 páginas — manual)
CORRETO: 119 (código, descrição, preço) • INCORRETO: 0 • INCOMPLETO: 0 • NÃO ENCONTRADO: 0
(preço exato em 116/119; keyword de descrição presente em 75/119 — ruído de layout)

### AVON CASA (amostra: p5, p6, p8, p9, p12)
- p5 263396 "CANECA DIVERTIDA POR" R$ 9,99 — INCOMPLETO (descrição truncada de chamada promocional)
- p6 253773 R$ 27,99 — INCOMPLETO (descrição com texto espelhado `retsaM CADA`)
- p8 204498 R$ 19,99 — INCOMPLETO (descrição começa com texto espelhado `odatcenoc OU ANGEL P`)
- p9 232000 R$ 24,99 — INCOMPLETO
- p12 248173 R$ 17,99 — INCOMPLETO (descrição "2 ITENS I 1 PREÇO..." promocional)
Padrão: descrições pegam chamada promocional em vez do nome do produto.

### Boticário (amostra: p15, p16, p17)
- p15 — INCORRETO (código = "LIMPAR CORPO E CABELO LIMPAR 88911..." linha inteira)
- p16 — INCORRETO (idem)
- p17 57882/95405... — codificado como linha inteira; preço capturado da última posição
Status: estrutura não compatível com o caminho texto.

### Eudora (p4)
- 891033 "BOLD INTENTION..." R$ 60,00 — INCORRETO (código falso = EAN, preço falso = valor de desconto)
- 977284 — INCORRETO

### Elyssence (p3, p5)
- NÃO ENCONTRADO: produtos com `4089 - Shampoo...` e `R$ 96,59` presentes no PDF

### O.U.i Paris (p3, p11)
- NÃO ENCONTRADO: `82061 MADELEINE 862, 75 ml, R$ 389` presentes no PDF

## Padrões de erro identificados

1. Bloco de códigos de 4–5 dígitos não é detectado (Elyssence, Eudora, Boticário) onde o regex espera 6 dígitos.
2. Preço sem decimais (`R$ 389`) não casa com `,(,\d{2})$` (O.U.i).
3. Texto-espelhado (`C DA A`, `:.etne...`) vira parte do código/descrição (tabela e texto).
4. Chamada promocional ("2 ITENS I 1 PREÇO", "LEVE", "POR") é usada como descrição do produto (AVON CASA).
5. Caminho de texto confundido em catálogo com tabelas/cenas (Boticário p15) e promove a linha inteira a "código".
6. Fragmentos de EAN (7 891033 977284) viram registros falsos em Eudora.
7. Preços promocionais/desconto ("ECONOMIZE R$ 60,00") vencem o preço principal em algumas páginas (Eudora).
8. Páginas de campanha/produto simples (Eudora, Elyssence, O.U.i) não geraram qualquer registro.

## Métricas da amostra (AVON CICLO 15, 12 páginas anotadas)

- Precisão: 100% (sobre os registros extraídos nas páginas anotadas)
- Recall: 100% (dos 119 produtos anotados)
- F1: 100%
- Código: 100% • Preço (exato): 97,5% • Descrição (contém o nome): 63%

Para os demais catálogos a medição é preliminar: recall 0% em Elyssence/O.U.i, poucos registros e não validáveis em Boticário/Eudora.

## Resposta

**O extrator atual NÃO é suficientemente confiável para o ajuste fino em todos os catálogos.** Ele já classifica bem o AVON CICLO 15 (catálogo Avon) e extrai parcialmente o AVON CASA, porém:
- não extrai nada em 2 catálogos (Elyssence, O.U.i), por formatos de código/preço diferentes;
- produz falsos positivos com texto promocional/EAN em Eudora e Boticário;
- descrições estão frequentemente incompletas/promocionais.

Próximos refinamentos sugeridos (sem implementar aqui):
1. Suportar códigos de 4–6 dígitos e formatos alfanuméricos;
2. Suportar preços inteiros (`R$ 389`) e valores de desconto diferenciados;
3. Filtrar texto espelhado e chamadas promocionais de descrição/código;
4. Confiar mais em coordenadas para Eudora/Boticário/O.U.i.
