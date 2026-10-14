# QA — T10a reteste 3 (PR #25 @ 0d55bab) — APROVADO

Banco proprio (`qa_t10a_r3`, Postgres do compose), venv Python 3.12, worktree em 0d55bab. Codigo do autor intocado.

## Resultado
| Item | Resultado |
|---|---|
| Suite completa | 140 passed (`t10a_suite.txt`) |
| Mutacao: reverter `daily_predict.py`+`queries.py` para bfbc9f3 | `tests/test_t10a_leakage.py`: 3 failed (J1b, J1c, P1) — os testes novos falham quando o vazamento volta |
| J1b par visto so apos as_of nao e previsto | ok (A1_par_tardio_ausente) |
| Backfill tardio (start<=as_of, first_seen>as_of, bonus 300) nao altera nenhuma predicao | ok (A1) |
| Anuncio futuro (first_seen<=as_of, start>as_of) nao entra em bonus/metodo | ok (A2) |
| Fronteira first_seen = as_of+1s excluida | ok (A3) |
| Reexecucao mesmo as_of: 0 linhas novas em prediction/prediction_log | ok (A4) |
| 6 jobs simultaneos: 0 erros, 0 duplicatas pela chave do indice unico, 3 linhas/par/dia | ok (probe_api_r3.out) |
| Banco vazio / as_of antes de qualquer oferta | 0 predicoes, sem excecao |
| P1: API serve a predicao mais recente por (par,tipo,horizonte) | ok (2 jobs em dias diferentes -> 1 item, made_at do ultimo) |
| append-only: DELETE e TRUNCATE em prediction_log barrados | ok |

## Remanescentes (nao bloqueiam; ja listados nos retestes anteriores)
- `GET /v1/prediction-log/accuracy?from=ontem` -> 500 INTERNAL_ERROR (deveria 422).
- `from > to` -> 200 com periodo invertido; `limit=-1`/`limit=0` e `type=zzz` -> 200.
- `0003_calendar_seed` (T08b) tambem e 0003: quem mesclar depois renumera.

## Reproduzir
`DATABASE_URL=... alembic upgrade head && pytest -q && PYTHONPATH=src python docs/qa/t10a-api/reteste3/attack_t10a_r3.py`
