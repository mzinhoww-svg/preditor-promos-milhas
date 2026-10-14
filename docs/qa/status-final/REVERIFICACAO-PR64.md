# QA — PR #64 reverificacao (2cb101f, decisao 006) — APROVADO COM 2 AJUSTES DE NUMERO

Contra a `main` atual `970612b` (com #65): checkout limpo, banco vazio e copia `TEMPLATE preditor_p2` migrada a 0008; `preditor_p2` e `preditor_e2e` so SELECT.

| Item | Resultado |
|---|---|
| Secoes 1, 2 e 4 nao dizem mais "B1 em producao" | OK: secao 1 "todos os pares saíram em B0 … série principal 23 < 25"; secao 2 so lista "Modelos B0/B1 funcionam" (capacidade); secao 4 "não atende o B1 no job"; relatorio do portao alinhado ("B1 aparece só como referência de validação histórica") |
| Tabela da secao 4 distingue par × grupo | OK: "27 no total; 23 na série principal (sem segmento)"; treino do walk-forward 23 em linha propria |
| Numeros | bate: 55/7/47/27/23/12, 1.239 raw (314/28/897), 177 gap, 90/109, `prediction_log` 0 e `preditor_p2` em 0005, 64 ofertas, `budget_ledger` 0; novo: `preditor_e2e` 672 linhas (224 por horizonte), 3 alertas, 0008, so B0 |
| Decisao 006 | itens 1–3 "aceitos" e **nao implementados**; STATUS diz isso ("falta implementar") e a API da main ainda devolve zeros com n = 0 (confirmado); item 4 e proposta |
| Comandos na main atual | `uv sync`, `alembic upgrade head` (head 0008), `daily_predict daily` em dados reais → `pairs 3, inserted_predictions 9, inserted_logs 9`, 3 series B0 (livelo→smiles 23); uvicorn com chave (401 sem chave); STOP (arquivo e `PREDITOR_STOP=1`) → exit 3 em daily, `backfill --reprocess` e `feed_listener --once` |
| Merge | branch esta antes do #65, mas `merge-tree` com a main e limpo |

## Ajustes (numeros defasados)
1. Cabecalho: "Código: `main` em `edff94a`" → a main e `970612b` (inclui #65, que o proprio STATUS cita).
2. "300 testes Python passam" (secao 2) e `uv run pytest  # 300 testes` (secao 8) → **303** na main atual (3 testes do #65). Vitest 38 e ruff continuam corretos.
