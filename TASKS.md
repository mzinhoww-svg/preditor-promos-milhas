# TASKS

| ID | Tarefa | Responsável | Terminal | Status | Aceite |
|---|---|---|---|---|---|
| T01 | Repo, Compose local, schema Alembic, CI com gitleaks | orquestrador | Claude Code | em_revisao | 13 testes verdes local; CI verde |
| T02 | Módulo campaigns (dedup, validated, peso) | orquestrador | Claude Code | em_revisao | testes unitários verdes |
| T03 | Módulo budget com ledger em Postgres | orquestrador | Claude Code | em_revisao | testes verdes |
| T04 | Glossário e decisões | orquestrador | Claude Code | concluida | docs/glossario.md |
| T05 | Coletor Livelo → Smiles (Wayback + fontes públicas) | pendente | | pendente | fixture + contrato |
| T05-spec | Spec do coletor Livelo → Smiles (robots/termos, Wayback CDX, schema do extrator, aceite) | Revisor | Claude Code | em_revisao | `docs/plans/coletor-livelo-smiles.md`; robots/termos verificados em 2026-10-13; CDX: 146 URLs únicas em 2023-2026; schema validado com jsonschema; `docs/decisions/002` |
| T06 | Conjunto de ouro (50 campanhas) | pendente | | pendente | data/gold |
| T07 | Extrator OpenRouter + regex | pendente | | pendente | metas do briefing |
| T08 | Baseline B0/B1 e walk-forward | pendente | | pendente | relatório |
| T09 | API, job diário, dashboard Vercel | pendente | | pendente | MVP |

Teste cruzado (outro agente roda e tenta quebrar) ainda não executado em T01 a T03.
