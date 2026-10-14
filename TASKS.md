# TASKS

| ID | Tarefa | Responsável | Status | Aceite / evidência |
|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | concluida | CI verde na main |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T03 | Módulo budget com ledger em Postgres | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T04 | Glossário e decisões 001 e 003 | orquestrador | concluida | docs/ |
| T05-spec | Spec do coletor Livelo → Smiles | Planejador | em_revisao | PR #2: QA aprovou com ajustes, Planejador atualizando |
| T05a | Cliente Wayback CDX e ingest idempotente | Programador | em_revisao | PR #1: B1 corrigido + R1; commit `5f35efa`; ruff limpo, 32 pytest verdes; aguardando reteste final QA |
| T07a | Extrator determinístico regex + pydantic | Programador 2 | em_revisao | PR #5: conflito com main resolvido, CI rodando (commit 82ec792) |
| T08a | Baseline B0/B1 e walk-forward | Programador 3 | concluida | PR #3 mergeado; vazamento aprovado; T08 mantém grade diária e reconstrução point-in-time |
| T08b | Modelo C1 LightGBM + grade diária + bootstrap em blocos + campeão×desafiante | Programador 3 | em_revisao | ciclo 2/3: portão (>=25 campanhas reais/par-tipo, data_source, calibração fail-closed), `evaluate_c1_vs_b1` walk-forward com purge, blocos ISO obrigatórios, p em [0,01;0,99], monotonia sobre self.horizons, sem contagem dupla de irmãos, calibração com purge, 0003 com parent 0002; fix expanding em walkforward; suíte 130 verdes, ruff limpo; relatório gerado por `scripts/t08b_report.py` (sintético, B1 permanece); ciclo 3/3: testes que matam mutacoes M1/M2/M4/M7 (`tests/test_t08b_vazamento.py`, `scripts/mutate_t08b.py`), avaliacao deterministica, migracao renumerada 0004 |
| T09a | Dashboard v0 com dados de exemplo | Designer Frontend | em_revisao | PR #9: D1–D9, N1 e N2 corrigidos; main mesclada; reteste final pedido ao QA |
| T06 | Conjunto de ouro (50 campanhas) | Planejador | gold_provisional | spec mergeada (#30); data/gold: 50 campanhas (49 livelo->smiles + 1 esfera->azul), 95 mensagens (75 positivas + 20 distratores), split 30/20, trechos <=600 chars sem HTML, schema valido; regex T07a indicativa test: par 57%, bonus 91%; aguarda conferencia de Aurimar (review.md); PR feat/t06-gold |
| T05 | Coletor RSS e backfill Wayback | Programador 2 | em_revisao | ciclo2: observed_at migracao 0002 nullable, LEAST, process fail-closed, 110 pytest verdes, 18 testes ataque; PR #19 |
| T09b | Dashboard ligado à API real (fallback simulado, explicação por item, selo B0/B1, STOP, alertas de limiar, plano de deploy) | Designer Frontend | em_revisao | branch `feat/dashboard-api-real`; lint, vitest (17) e build verdes; testado contra a API do PR #50 em Postgres descartável; `docs/deploy-vercel.md` sem deploy |
| T10 | API, job diário, deploy VPS | pendente | pendente | MVP |
| T10a | API FastAPI + job diário baseline/accuracy | Programador | em_revisao | PR #25; commit `70c0687`/`b2bfaf8`; B1-B3 corrigidos (job roda com ofertas, unicidade prediction_log, accuracy from/to); ruff/pytest verdes (99); ciclo 3: vazamento corrigido (P1 última predição na API, J1b par e J1c método point-in-time), `tests/test_t10a_leakage.py`, pytest 140 verdes |
| TP1 | Painel de progresso visual ao vivo | Programador (Painel) | em_revisao | tools/painel; docs/mvp-checklist.json; tests/test_painel.py; ruff/pytest verdes; PR pendente |
