# TASKS

| ID | Tarefa | Responsável | Status | Aceite / evidência |
|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | concluida | CI verde na main (1ª execução success) |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T03 | Módulo budget com ledger em Postgres | orquestrador | em_revisao | testes verdes; teste cruzado pendente |
| T04 | Glossário e decisões 001 e 003 | orquestrador | concluida | docs/ |
| T05-spec | Spec do coletor Livelo → Smiles | Planejador | em_revisao | PR #2, CI verde, decisões 002 (opção C) |
| T05a | Cliente Wayback CDX e ingest idempotente | Programador | em_correcao | PR #1; QA devolveu 7 falhas bloqueantes, corrigidas, reteste pendente |
| T07a | Extrator determinístico regex + pydantic | Programador 2 | em_correcao (ciclo 2 de 3) | PR #5; reteste QA (PR #7): N1 e N2 bloqueiam |
| T08a | Baseline B0/B1 e walk-forward | Programador 3 | em_correcao (ciclo 2 de 3) | PR #3; QA aprovou com ressalvas (PR #8), revisão de vazamento do Planejador devolveu 10 de 13 testes de ataque |
| T09a | Dashboard v0 com dados de exemplo | Designer Frontend | em_andamento | visível no portal Preview (localhost:3100) |
| T06 | Conjunto de ouro (50 campanhas) | pendente | pendente | data/gold |
| T05 | Coletor RSS e backfill Wayback | pendente | pendente | depende de T05a e PR #2 |
| T10 | API, job diário, deploy VPS | pendente | pendente | MVP |

Limite de correções: 3 por problema, depois o orquestrador simplifica ou corta.
