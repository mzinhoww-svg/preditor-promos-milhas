# QA — PR #64 STATUS final (4fb3488) — APROVADO COM 1 CORRECAO OBRIGATORIA

Fontes: `preditor_p2` (so SELECT), main `edff94a`, checkout limpo com `uv sync --python 3.12`, bancos proprios (vazio para pytest; copia `TEMPLATE preditor_p2` migrada a 0008 para o job).

## (1) Correcoes do #63 em docs/reports/portao-viabilidade-e-campeao.md — OK
Contrafactual → "Com estes dados, o C1 perde… Não foi medido… (cada dobra treina com 3 a 29 registros)"; "316 baixadas (314 gravadas)"; "Período de `observed_at`¹" com nota (campanhas comecam em 2020-02).

## (2) STATUS.md contra o banco e a main
| Item | Resultado |
|---|---|
| 55 / 7 / 47 / 27 (28 so-gap) / 12 / ultima 2026-03-11, 2020-02 a 2026-03 | batem |
| outros pares 5 / 3 / 1; 0 purchase/boosted | batem |
| 1.239 raw (314 / 28 / 897), 177 gap, 90 de 109 `start_inferred` | batem |
| prediction_log 0, budget_ledger 0, model_run 0, preditor_p2 em 0005 | batem |
| 23 no treino, Brier 0,306 × 0,125, log-loss 1,261 × 0,376, 10 dobras, 3.471 linhas | batem (reexecucao ja feita no #63) |
| 300 pytest (checkout limpo, banco vazio, head 0008), ruff limpo, 38 vitest, lint ok | batem |
| caminhos citados (collector, extract, article, campaigns, baseline, walkforward, model, alerts, docs/stop.md, deploy-vercel, review/duvidas, .env.example) | todos existem |
| "Como rodar": `uv sync`, `alembic upgrade head`, `daily_predict daily`, `uvicorn … --port 8055` + `PREDITOR_API_KEY` (401 sem chave, itens com chave) | funcionam |
| STOP: arquivo `STOP` e `PREDITOR_STOP=1` | daily, `backfill --reprocess` e `feed_listener --once` saem com **3** e "STOP presente"; nada gravado |
| "Banco desatualizado: rodar alembic upgrade head antes do job" | confirmado (a copia em 0005 migrou a 0008 e o job rodou) |

## Correcao obrigatoria: "em produção está o B1 para esse par" nao e o que o job faz
Rodei `daily_predict daily` (comando do STATUS) numa copia de dados reais migrada a 0008:
`{'pairs': 5, 'inserted_predictions': 15, 'inserted_logs': 9, 'model_run_id': 1}` →
- **Todos os 5 grupos sao B0** (`model_run` = B0; `explanation.method = b0`): o job conta campanhas **por grupo** (par, tipo, segmentada, segmento) — livelo→smiles tem 23 (base) + 3 (clube) + 1 (bonus_conflitante) → 23 < 25. As 27 utilizaveis do par somam ≥ 25, mas o B1 nunca e escolhido. O STATUS (secoes 1, 2 e 4) diz "B1 em producao para esse par" e "atende o B1 no job (27 ≥ 25)": nao e verdade no codigo da main.
- **Colisao de grupos segmentados**: 5 grupos viram 3 series (9 linhas em `prediction` e `prediction_log`); `inserted_predictions` conta tentativas (15, e 15 de novo na re-execucao, com 0 novas linhas).
- **A serie publicada de livelo→smiles e a do grupo `clube`** (3 campanhas, p7 = 0,020, ultima 2024-12-19), nao a do grupo base (23 campanhas): o primeiro a inserir vence. (Correcao em andamento no PR #65.)

Sugestao de texto: "O job diario roda, mas hoje opera em B0 para todos os grupos (contagem por grupo: 23 < 25) e perde series segmentadas (PR #65); o B1 so e usado quando um grupo atinge 25 campanhas".
