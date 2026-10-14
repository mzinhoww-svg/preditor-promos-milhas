# Reteste final T10a — migração/unicidade (PR #25, bfbc9f3)

Veredito: **APROVADO**. Banco próprio `qa_t10a`. Saída completa: `saida.txt`; script: `attack_api.py`.

| Verificação | Resultado |
|---|---|
| Cadeia de migrações | `0001 → 0002_observed_at → 0003_prediction_log_unique`, head único `0003`; sem aviso de revisão duplicada |
| Banco vazio: `upgrade head` | ok; índice `uq_prediction_log_logical (model_version, origin, destination, event_type, horizon_days, (logged_at AT TIME ZONE 'UTC')::date)` |
| `downgrade -1` → `upgrade` ×2 | índice 0 → 1 → 1 (idempotente) |
| Unicidade | mesmo dia UTC, horas distintas → `duplicate key`; dia UTC distinto (22:00-03 = 01:00 UTC do dia seguinte) → permitido; model_version/horizonte/par distintos → permitidos |
| Append-only | `UPDATE`/`DELETE` continuam bloqueados pelo trigger |
| `pytest` | 137 passed |
| Job: 3 rodadas (banco recriado) | run1 9 logs, run2 0; 6 jobs simultâneos → 0 duplicatas nas 3 rodadas |
| `accuracy?from=&to=` | 200 |

## Ressalvas (não bloqueiam)
1. **Colisão de revisão com T08b**: a migração `0003_calendar_seed` do PR #27 também é `0003`. Quem mesclar depois precisa renumerar (próximo livre) e ajustar `down_revision`.
2. Em base que já tenha duplicatas em `prediction_log` (criadas pelo código antigo), `upgrade` falha por completo (transação revertida, fica em `0002`) e as linhas não podem ser removidas (append-only). Não afeta bancos novos; documentar o procedimento se houver base legada.
3. Remanescentes do ciclo anterior: `from=ontem` → 500; segmentados colidem em `prediction`; `ci_low==ci_high`; sem predições → 200 (contrato 503).
