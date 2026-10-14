# QA — PR #50 T10b reteste 2 (ca400a2) — APROVADO

Bancos proprios `qa_pr50e` (suite/ataques/API) e `qa_pr50f` (migracao com dados). Codigo intocado.

## Resultado
| Item | Resultado |
|---|---|
| alembic | banco vazio → head unico `0008`; downgrade -1/upgrade ok |
| alembic com dados | banco em 0007 com 6 runs → 0008: runs do job (assinatura `methods` ou `daily-job`) viram `role='daily'`/`is_champion=false`; duplicata da tripla → `daily_legacy`; campeao T08b (id 5) preservado (`experiment`, `is_champion=true`); re-execucao (downgrade 0007/upgrade) idempotente |
| Suite / lint | 300 passed, ruff limpo |
| reprocess atomico: STOP no 4º de 6 raws | `StopRequested`; ofertas, evidencias, ids e flags de gap identicos ao estado anterior (rollback) |
| reprocess: erro no 3º raw | `ValueError` propagado; estado identico ao anterior |
| reprocess + `recompute_gap` na mesma transacao | `recompute_gap` falhando desfaz tambem a reextracao (conteudo alterado de um raw nao altera as 6 ofertas) |
| STOP via CLI | `--reprocess` com STOP no meio (in-process) → exit 3, ofertas inalteradas; STOP antes (subprocess) → exit 3 sem DELETE |
| Isolamento | leitor concorrente durante o reprocess ve sempre 6 ofertas (nunca 0/parcial) |
| Campeao | `model_run` T08b (C1, `is_champion`) intacto apos 2 `run_daily`; run diario `role='daily'`, `is_champion=false`; mesmo as_of/dados reutiliza o run (39, 39) |
| API | `/v1/predictions`: `model` = run que serviu (B0, `daily`, mr_39), `champion` separado (C1 2.0.0, mr_38), itens com `model_run_id=mr_39`; `/v1/model/metrics`: `champion` C1 + `serving` B0; sem campeao decidido, `champion` cai no run servido (documentado) |

## Ressalvas (nao bloqueiam)
1. Heuristica da 0008: run de T08b cujo `hyperparams` tenha a chave `methods` seria rebaixado a `daily` (caso `t08b_champ_methods` do teste); o T08b atual nao grava essa chave, mas o criterio e fragil — preferir marcar so `code_hash` do job.
2. `/v1/model/metrics.champion.run_id` vem `null` (so `serving.run_id` preenchido).
3. `comparison` segue com zeros + `note: "sem dados suficientes"` (o painel #56 precisa tratar a nota como "sem dados").
4. Mudanca de contrato: `model.role` agora e `daily` (antes `champion`); conferir consumidores (painel #56 usa `model.name`, ok).
