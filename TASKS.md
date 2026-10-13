# TASKS

| ID | Tarefa | Responsável | Terminal | Status | Aceite |
|---|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | Claude Code | em_revisao | 13 testes verdes local; CI verde |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | Claude Code | em_revisao | testes unitários verdes |
| T03 | Módulo budget com ledger em Postgres | orquestrador | Claude Code | em_revisao | testes verdes |
| T04 | Glossário e decisões | orquestrador | Claude Code | concluida | docs/glossario.md |
| T05 | Coletor Livelo → Smiles (Wayback + fontes públicas) | pendente | | pendente | fixture + contrato |
| T05a | Coletor Wayback CDX + ingest idempotente raw_message | Programador | Claude Code | devolvida | Reteste 5f6d74b: 31 passed (com DB), ruff ok; 6 dos 7 bloqueantes corrigidos; B1 rate limit de modulo burlado com rate_limit/min_interval por chamada. Ver docs/qa/t05a/RELATORIO.md |
| T06 | Conjunto de ouro (50 campanhas) | pendente | | pendente | data/gold |
| T07 | Extrator OpenRouter + regex | pendente | | pendente | metas do briefing |
| T08 | Baseline B0/B1 e walk-forward | pendente | | pendente | relatório |
| T09 | API, job diário, dashboard Vercel | pendente | | pendente | MVP |

Teste cruzado (outro agente roda e tenta quebrar) ainda não executado em T01 a T03.
