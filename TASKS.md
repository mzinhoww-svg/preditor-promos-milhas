# TASKS

| ID | Tarefa | Responsável | Terminal | Status | Aceite |
|---|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | Claude Code | em_revisao | 13 testes verdes local; CI verde |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | Claude Code | em_revisao | testes unitários verdes |
| T03 | Módulo budget com ledger em Postgres | orquestrador | Claude Code | em_revisao | testes verdes |
| T04 | Glossário e decisões | orquestrador | Claude Code | concluida | docs/glossario.md |
| T05 | Coletor Livelo → Smiles (Wayback + fontes públicas) | pendente | | pendente | fixture + contrato |
| T06 | Conjunto de ouro (50 campanhas) | pendente | | pendente | data/gold |
| T07 | Extrator OpenRouter + regex | pendente | | pendente | metas do briefing |
| T08 (T08a) | Baseline B0/B1 e walk-forward | Programador 3 | Claude Code | concluida | Reteste2 7e5310c: 36 passed, ruff ok, 0 violacoes em 8669 splits; R1/R3 corrigidos; pendencias R6 (treino vazio em 29% dos splits), R7 (fail-closed silencioso), R8 (peso 0,5 da fonte unica removido, decisao). Ver docs/qa/t08a/RELATORIO.md |
| T09 | API, job diário, dashboard Vercel | pendente | | pendente | MVP |

Teste cruzado (outro agente roda e tenta quebrar) ainda não executado em T01 a T03.
