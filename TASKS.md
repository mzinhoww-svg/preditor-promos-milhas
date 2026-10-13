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
| T09a | Dashboard v0 com dados de exemplo | Designer Frontend | em_revisao | PR #9: D1–D9, N1 e N2 corrigidos; main mesclada; reteste final pedido ao QA |
| T06 | Conjunto de ouro (50 campanhas) | pendente | pendente | data/gold |
| T05 | Coletor RSS e backfill Wayback | pendente | pendente | depende de T05a e PR #2 |
| T10 | API, job diário, deploy VPS | pendente | pendente | MVP |
| TP1 | Painel de progresso visual ao vivo | Programador (Painel) | em_revisao | tools/painel; docs/mvp-checklist.json; tests/test_painel.py; ruff/pytest verdes; PR pendente |
