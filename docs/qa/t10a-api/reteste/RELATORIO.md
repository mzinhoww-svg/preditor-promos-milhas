# Reteste T10a (PR #25, b2bfaf8 / código 70c0687)

Veredito: **APROVADO COM CONDIÇÃO** — B1–B3 corrigidos; **renumerar a migração antes do merge** (colisão de revisão `0002`).
Ambiente: banco próprio `qa_t10a`, Python 3.12. Mesmo script de ataque do ciclo 1 (`attack_api.py`), **sem shim**; saída em `attack_output.txt`.

| Item | Resultado |
|---|---|
| `pytest` | 99 passed (banco recriado do zero) |
| B1 job com ofertas | ✅ 3 pares, 9 predições/9 logs; sem `TypeError`; kwargs `segmented/segment_label` aceitos por `baseline.predict_proba` |
| B2 idempotência | ✅ reexecução 9 → 0 novos logs; 6 jobs simultâneos no mesmo dia: 0 duplicatas; índice único `uq_prediction_log_logical` + `ON CONFLICT DO NOTHING`; contador de logs usa `rowcount` |
| B3 `from/to` | ✅ `from=2026-01-01` → 200; filtro com datas ok |
| Acurácia só resolvidas | ✅ logs com `logged_at + h > hoje` excluídos (n=6 em vez de 14–18) |
| Vazamento | ✅ prob. idêntica com/sem oferta futura e com `first_seen_at > as_of`; percentis de bônus agora point-in-time |
| Append-only | ✅ DELETE bloqueado |

## Condição para merge (novo)
`migrations/versions/0002_prediction_log_unique.py` usa `revision = "0002"`, mas a main já tem `0002_observed_at.py` (T05). Ao mesclar a main: `UserWarning: Revision 0002 is present more than once` e `alembic upgrade head` → **`FAILED: Multiple head revisions are present`** (reproduzido). Renumerar (ex.: `0004`/próximo livre, `down_revision` = head vigente da main; coordenar com a `0003` do T08b).

## Ressalvas remanescentes (não bloqueiam; já listadas no ciclo 1)
`from=ontem` → 500 (deveria ser 422); `segmented` sempre falso e predições segmentadas ainda colidem em `prediction` (contador do job conta 9, grava 6); `ci_low==ci_high`; sem predições → 200 (contrato: 503); `limit=-1`; `weekly/alerts` vazios; `/docs` aberto; limiter sem expurgo.
