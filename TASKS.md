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
| T08 | Baseline B0/B1 e walk-forward | pendente | | pendente | relatório |
| T09 | API, job diário, dashboard Vercel | pendente | | concluida | Reteste 400f591: D1-D9 corrigidos; lint/build ok; axe 0 violacoes; sem overflow a 195/390/1440. Ressalvas N1 (datas invalidas derrubam tela), N2 (ci_brier ausente derruba /modelo), N3. Ver docs/qa/t09a/QA-RELATORIO.md |
| T09a | Dashboard v0 (Next.js, mock + contrato da API, 4 telas) | Designer Frontend | Claude Code | em_revisao | docs/api-contract.md; build e lint verdes; QA visual desktop e 390x844 em docs/qa/t09a |

Teste cruzado (outro agente roda e tenta quebrar) ainda não executado em T01 a T03.
