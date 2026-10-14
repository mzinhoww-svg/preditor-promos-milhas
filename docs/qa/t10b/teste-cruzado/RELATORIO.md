# QA — PR #50 T10b (6d28b5b) — DEVOLVIDO (2 bloqueantes), restante aprovado

Bancos proprios `qa_pr50` (suite) e `qa_pr50b` (ataques). Codigo intocado.

## Passou
| Item | Resultado |
|---|---|
| Suite / lint / alembic | 250 passed, ruff limpo, head unico `0006` (downgrade -1/upgrade ok); merge limpo com `main` |
| STOP no job | arquivo `STOP` no cwd, `PREDITOR_STOP=1` e `PREDITOR_STOP_FILE` abortam `run_daily` antes de qualquer leitura/escrita (contagens identicas, S1–S3); `PREDITOR_STOP=0` nao para; CLI sai com codigo 3 |
| STOP no coletor (parcial) | `collect_rss`, `collector.backfill` e `collect_titles_rss` abortam sem gravar |
| model_run | re-execucao no mesmo dia/dados reutiliza o mesmo id (2,2); registra `model_version`, `dataset_version` (hash das ofertas conhecidas em as_of), `code_hash`, `metrics` (n_offers, n_pairs, n_predictions, n_b0/n_b1) e `hyperparams`; dados novos → novo model_run e o anterior deixa de ser champion |
| Alertas | so tabela `alert` + `GET /v1/alerts` (nenhum canal externo no codigo); cruzamento ascendente certo na serie 0.30/0.55/0.60/0.40/0.70 → [0,3,0,0,3]; idempotente (reexec 0 novos; mesma chave unica); limiar invalido → 0.5; prob == limiar sem anterior alerta; retroativo nao duplica; `limit` 1–500 (0/501/x → 422), sem chave → 401 |
| Explicacao por item | gravada pelo job so com ofertas conhecidas em as_of: backfill tardio (start<=as_of, visto depois) e start futuro NAO entram (n_campaigns=4, last=2026-04-01); execucoes posteriores nao alteram a explicacao antiga; reexecucao retroativa mantem; o endpoint so le o que foi gravado (sem recalculo) |
| source-health | agregacao coerente: 24h/7d somam corretamente (3/10), media de extracao 7d (0.6), `error_rate_24h`, `last_success_at` = ultimo check sem alerta, `degraded` quando o ultimo check falhou |

## Bloqueantes
1. **STOP nao e honrado pelo coletor real.** `preditor.backfill.run_backfill` (o CLI do backfill de horas) e `collect_archived_feed` NAO chamam `check_stop()`: com `STOP` presente, executam e gravam (C3/C4). So `collect_rss`/`collector.backfill` abortam. Alem disso o STOP so e lido na entrada: criado depois do inicio, o `run_daily` termina e grava tudo (S5), e um backfill de ~26 h nao pararia. Chamar `check_stop()` em `run_backfill`, `collect_archived_feed`, e a cada item/pagina nos loops (e a cada grupo no job).
2. **model_run duplica sob concorrencia.** `record_model_run` e SELECT-then-INSERT sem UNIQUE: 8 jobs simultaneos em dados novos geraram grupos duplicados (versao, dataset, codigo) em 4 de 5 rodadas e ate **5 `is_champion=true` ao mesmo tempo** (MR_corrida). Mesmo defeito que o prediction_log teve no T10a. Adicionar UNIQUE (model_version, dataset_version, code_hash) + `ON CONFLICT`/lock e atualizar champion na mesma transacao.

## Ressalvas
3. `robots_changed` e efemero: compara so com o check anterior (h1 vs h0 com h1 repetido → false). Comparar com o hash da ultima mudanca.
4. `status` so `ok`/`degraded`; PR #49 introduz `error`/`stale` na mesma funcao: **conflito em `api/queries.py`** entre #49 e #50 (merge-tree) — decidir ordem e unificar.
5. `code_hash` cobre so `baseline.py` e `jobs/daily_predict.py` (alerts/stop/queries nao entram); aceitavel, documentar.
6. Limiar de alerta invalido cai silenciosamente em 0.5 (sem log).
