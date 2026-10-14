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
| T08b | Modelo C1 LightGBM + grade diária + bootstrap em blocos + campeão×desafiante | Programador 3 | em_revisao | ciclo 2/3: portão (>=25 campanhas reais/par-tipo, data_source, calibração fail-closed), `evaluate_c1_vs_b1` walk-forward com purge, blocos ISO obrigatórios, p em [0,01;0,99], monotonia sobre self.horizons, sem contagem dupla de irmãos, calibração com purge, 0003 com parent 0002; fix expanding em walkforward; suíte 130 verdes, ruff limpo; relatório gerado por `scripts/t08b_report.py` (sintético, B1 permanece) ; QA reteste 2 em 0b03645: APROVADA COM CONDICOES (160 passed; portao/relatorio/predict_proba ok; bug original agora falha; mas vazamentos parciais M1/M2/M4/M7 alteram p_c1 e nenhum teste falha; renumerar 0003); ver docs/qa/t08b-modelo/reteste2/RELATORIO.md |
| T09a | Dashboard v0 com dados de exemplo | Designer Frontend | em_revisao | PR #9: D1–D9, N1 e N2 corrigidos; main mesclada; reteste final pedido ao QA |
| T06 | Conjunto de ouro (50 campanhas) | pendente | pendente | data/gold |
| T05 | Coletor RSS e backfill Wayback | Programador 2 | em_revisao | ciclo2: observed_at migracao 0002 nullable, LEAST, process fail-closed, 110 pytest verdes, 18 testes ataque; PR #19 |
| T10 | API, job diário, deploy VPS | pendente | pendente | MVP |
| TP1 | Painel de progresso visual ao vivo | Programador (Painel) | em_revisao | tools/painel; docs/mvp-checklist.json; tests/test_painel.py; ruff/pytest verdes; PR pendente |
