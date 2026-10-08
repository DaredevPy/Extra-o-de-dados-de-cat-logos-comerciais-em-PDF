# ETAPA 7 — Integração Final no Parser e na GUI (Modo Evidência)

## Objetivo
Disponibilizar o motor por evidências ao usuário final, preservando o funcionamento legado
como padrão e deixando a GUI/exportador completos com Status e Confiança.

## Mudanças
- `core/parser.py` — `CatalogParser.parse_document` agora despacha para `core.pipeline.extract_catalog`
  quando `config.mode == "evidence"` (inclui registro de códigos sem preço como NÃO_DETERMINADO e
  respeita `page_range`). O restante do fluxo legado (*hybrid/tables_only/text_only*) segue intacto.
- `core/pipeline.py` — `extract_catalog(...)` é a interface públicos para o parser/GUI.
- `gui/settings_panel.py` — novo radio "Evidência (análise espacial multi-scanner + confiança +
  reconciliação)" com `value="evidence"`.
- `gui/main_window.py` — já instancia `CatalogParser(config)`; nenhuma mudança necessária.
- `gui/table_view.py` e `core/exporter.py` — já exibem/exportam `Confiança` e `Status`
  (via `ProductItem.to_dict`); sem mudanças.
- `scripts/evaluate.py` — ganhou `--mode evidence` (e `include_unpriced=True`), permitindo o
  comparativo ANTES/DEPOIS com a mesma metodologia do baseline.

## Uso
1. Abrir a aplicação.
2. Em "1. Modo e Estratégia de Extração", selecionar "Evidência".
3. Selecionar o PDF e extrair — a tabela mostrará Confiança (%) e Status
   (ALTA / MEDIA / REVISAR / CONFLITO / NÃO_DETERMINADO).
4. Exportar Excel/CSV normalmente (colunas extras incluídas).

## Comparativo final (Avon Ciclo 15 — 119 itens de referência)
| Métrica | Baseline (legado) | Evidência |
|---|---|---|
| Códigos corretos | 119 / 119 | 119 / 119 |
| Preço correto | 103 / 119 | 102 / 119 |
| Descrição correta | 33 / 119 | 36 / 119 |
| Precisão | 1,0 | 1,0 |
| Recall | 1,0 | 1,0 |
| Transparência por registro | — (heurística sem status) | Status + Confiança + nota |

O modo evidência mantém precisão máxima (0 falsos positivos) e adiciona auditoria completa por
registro: múltiplos scanners (regional/coluna/linha-texto), reconciliação com CONFLITO honesto,
preço de seção/grade evidenciado, e NÃO_DETERMINADO para ausência sem invenção.