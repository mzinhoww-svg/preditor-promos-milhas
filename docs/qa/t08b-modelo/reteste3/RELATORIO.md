# QA — T08b reteste 3 (PR #27 @ 7cdbe91) — APROVADO (com ressalvas)

Banco proprio (`qa_t08b_r3`), venv 3.12. Codigo do autor intocado (mutacoes por `mutate27h.py`, arquivo restaurado; `git status` limpo).

## Base
- 180 passed (inclui API T10a mesclada), ruff limpo, head unico `0004` (0001→0002→0003_prediction_log_unique→0004_calendar_seed); downgrade 0003 / upgrade head ok.
- Avaliacao deterministica: mesma seed e registros em ordem invertida → mesmos p_b1/p_c1 e IC; duplicatas nao inflam campanhas (143=143); vazio/poucos → ValueError; troca B1↔C1 nao promove.

## Mutacoes (tests: modelo, portao, vazamento, collector_leakage, walkforward)
| Mutacao | Resultado |
|---|---|
| M0 `_first_seen_dt(registro)`→None (bug do ciclo 1) | MORTA (8 testes) |
| **M1** `_available_offers` ignora t | **MORTA** (`test_available_offers_drops_first_seen_after_t`, `test_feature_row_ignores_backfilled_records`) |
| **M2** treino sem cutoff/purge | **MORTA** (`test_training_filters_first_seen_even_if_splitter_leaks`) |
| **M4** `fit(recs, as_of=data_end)` | **MORTA** (`test_each_fold_fit_only_sees_cutoff`) |
| **M7** grade/features sem filtro fs<=t | **MORTA** (`test_grade_features_ignore_records_not_yet_seen`) |
| V1 irmaos sem filtro fs<=t | MORTA (3 testes) |
| V2 sem purge (cutoff=test_start) | MORTA (`test_each_fold_fit_only_sees_cutoff`) |
| V8 calibracao sem purge | MORTA (`test_calibration_purged_and_same_booster`) |
| V3+V4 (pool e predict_trained_at com fs<=t+30d), V6 B1 com todos os registros, V9 fit sem filtro as_of, V10 predict_curve sem filtro as_of, M3, M5 | sobrevivem, mas **equivalentes**: p_b1/p_c1 identicos ao base (hash `probe_equiv.out`) — guardas redundantes |
| **V5** data sem hora tratada como inicio do dia (`time.min`) em vez de fim do dia | **SOBREVIVE e muda p_c1** (Brier C1 0,0549→0,0483): first_seen so com data passa a valer a partir de 00:00 do proprio dia |
| V7 fit sem embargo de rotulos | sobrevive e muda p_c1 (0,0555); nao e vazamento do futuro (rotulos truncados), e vies de rotulo |

## Ressalvas (nao bloqueiam)
1. V5: falta teste de que `first_seen_at` date-only so e conhecido a partir do dia seguinte (fim do dia) — em producao `first_seen_at` e timestamptz, risco baixo; fixtures/CSV sao date-only.
2. V7: sem teste para o embargo de rotulos no fit.
3. `test_each_fold_fit_only_sees_cutoff` confia em metadados registrados pelo proprio `evaluate` (`fit_as_of`, `fit_max_first_seen`); a invariancia por dobra (`test_late_records...`) cobre o comportamento.
4. `data_source` continua declarado pelo chamador (mundo sintetico rotulado "real" promove C1).
