# TASKS

| ID | Tarefa | Responsável | Status | Aceite / evidência |
|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | concluida | CI verde na main |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T03 | Módulo budget com ledger em Postgres | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T04 | Glossário e decisões 001 e 003 | orquestrador | concluida | docs/ |
| T05-spec | Spec do coletor Livelo → Smiles | Planejador | em_revisao | PR #2: QA aprovou com ajustes, Planejador atualizando |
| T05a | Cliente Wayback CDX e ingest idempotente | Programador | concluida | Reteste final d2751b4: 90 passed (banco proprio), ruff ok; B1/R1 e 7 bloqueantes originais corrigidos; ressalvas R2-R6 na T05. Ver docs/qa/t05a/RELATORIO.md |
| T07a | Extrator determinístico regex + pydantic | Programador 2 | em_revisao | PR #5: conflito com main resolvido, CI rodando (commit 82ec792) |
| T08a | Baseline B0/B1 e walk-forward | Programador 3 | concluida | PR #3 mergeado; vazamento aprovado; T08 mantém grade diária e reconstrução point-in-time |
| T09a | Dashboard v0 com dados de exemplo | Designer Frontend | em_revisao | PR #9: QA aprovou com ressalvas; corrigindo N1 e N2 |
| T06 | Conjunto de ouro (50 campanhas) | pendente | pendente | data/gold |
| T05 | Coletor RSS e backfill Wayback | pendente | pendente | depende de T05a e PR #2 |
| T10 | API, job diário, deploy VPS | pendente | pendente | MVP |
