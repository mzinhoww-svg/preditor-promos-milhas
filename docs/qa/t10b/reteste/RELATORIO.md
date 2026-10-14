# QA — PR #50 T10b reteste (7528695) — APROVADO COM 1 CONDICAO

Bancos proprios `qa_pr50c` (suite/alembic) e `qa_pr50d` (ataques). Codigo intocado.

## Passou
| Item | Resultado |
|---|---|
| alembic | banco vazio → head unico `0007`; downgrade -1/upgrade ok |
| Suite / lint | 292 passed, ruff limpo |
| STOP no meio de cada laco | `run_daily`: para antes do proximo grupo (o grupo em curso termina: 3 linhas); `run_backfill`: 2º download nao e gravado; `collect_archived_feed`: 2 capturas, 1 raw, nada depois; `collect_rss`: para no item seguinte; `feed_listener.run_once`: 0 requisicoes apos STOP, fonte seguinte nao visitada, estado do teto salvo (`finally`); `reprocess` com STOP antes: aborta antes do DELETE (ofertas intactas) |
| CLIs | `backfill`, `backfill --reprocess`, `feed_listener --once`, `daily` saem com codigo 3 e mensagem "STOP"; `StopRequested` nao e mais `RuntimeError` (nao e engolido pelos laços) |
| Campeao | `model_run` do T08b (`is_champion=true`) sobrevive a 2 `run_daily`; runs `role='daily'` nunca viram champion |
| Concorrencia | 8 threads × 5 rodadas: 1 `model_run` por rodada, 0 grupos duplicados (UNIQUE parcial + ON CONFLICT), 0 duplicatas em prediction/prediction_log/alert, 0 erros |

## Condicao (bloqueia o merge)
**`reprocess` com STOP no meio deixa o banco parcial.** O DELETE de `offer`/`offer_evidence` ocorre antes do laço; com STOP criado no 4º raw de 6, 6 ofertas viraram 4 (e 4 evidencias): `StopRequested` sai com o banco incompleto e o `run_daily`/API leem ofertas faltando. Fazer o DELETE+reconstrucao numa transacao com rollback em `StopRequested`/erro (ou reconstruir em tabela temporaria e trocar).

## Ressalvas
1. **Run legado:** runs criados pelo job antigo (is_champion=true) ficam com `role='experiment'` (default da 0007) e continuam campeoes; sem migracao de dados para marca-los `daily`/zerar `is_champion`.
2. **Atribuicao do modelo na API:** com um campeao C1 do T08b, `/v1/predictions` reporta `model.name=C1` mas os itens vem do run diario B0/B1; `/v1/model/metrics` reporta `B1` (endpoints discordam). Reportar o `model_run` que gerou cada predicao e o campeao separadamente.
3. STOP e cooperativo: o grupo/item em curso termina (ate 3 linhas de predicao por grupo).
