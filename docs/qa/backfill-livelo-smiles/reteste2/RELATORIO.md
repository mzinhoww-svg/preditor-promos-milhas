# QA — PR #36 reteste 2 (8f4c51b) — DEVOLVIDO (relatorio/dados); codigo com 1 condicao

Banco proprio `qa_bf3` (vazio → `alembic upgrade head`), venv 3.12; banco do autor `preditor_p2` so SELECT (snapshot em `p2_snapshot.txt`). Codigo intocado.

## O que passou
| Item | Resultado |
|---|---|
| alembic em banco vazio | head unico `0005` (0001→0002→0003→0004→0005); downgrade -1/upgrade ok |
| Suite | 221 passed, ruff limpo |
| start_inferred (spec 3.1) | "valida ate 20/05" sem inicio → `start_at` = dia do first_seen (SP), `start_inferred=true` na evidencia (B1); inicio explicito → false (B2); sem datas (B3), fim no passado (B4) e fim > 90 d (B5) → nenhuma oferta (nada inventado) |
| Filtro so-gap no job | oferta so com evidencia de gap NAO entra em `fetch_offers` nem gera predicao (A1/A2); oferta mista e oferta sem evidencia entram |
| Filtro so-gap na API | `GAP_ONLY_SQL` aplicado em `queries.py` |
| RSS arquivado (CDX do feed) | robots fail-closed antes de tudo (disallow do feed → 0 capturas; indisponivel → 0); `sleep(10)` imediatamente antes de cada snapshot; so titulo gravado (max 43 bytes, corpo do `<description>` nunca persistido); reexecucao 0 fetches novos; sem state 0 duplicatas; gap marcado (C1–C5) |

## Bloqueantes
1. **"Relatorio republicado" nao esta no commit.** `docs/ACTIONS.md` e o corpo do PR seguem identicos a 62f0602 ("12 campanhas, 173 raw, 64 falhas apos 2 tentativas"). Banco do autor no snapshot: **192 raw (144 PdP + 28 MC + 20 RSS vivo), 1 oferta, 0 `start_inferred`**.
2. **Dados de gap perdidos no banco do autor.** `preditor_p2`: `published_at` NULL e `published_vs_capture_gap=false` em **192/192** (na rodada anterior havia 83 com gap). A coluna foi recriada pela migracao rebaseada e `recompute_gap` nao foi reexecutado (depende de timestamps do `state.json`, ainda v1). Resultado: o filtro so-gap hoje nao exclui nada no banco real e o ouro (PR #42) depende desses flags.
3. **RSS arquivado nao esta no banco:** as 20 linhas do Pontos pra Voar sao do feed vivo de 2026-10-13; nada do arquivado foi executado/gravado, entao a afirmacao nao e verificavel contra o banco.

## Condicao (codigo)
`evaluate_c1_vs_b1` so exclui registros com o campo `gap_only` — nenhum loader do repo o preenche (so existe `GAP_ONLY_SQL`, usado em job e API). Um consumidor que leia `offer` com SELECT simples e chame `evaluate_c1_vs_b1` **inclui ofertas so-gap** (A3); `exclude_gap_only` sem o campo nao remove nada. Falta um loader unico (ex.: `load_offers(engine)` com `GAP_ONLY_SQL` + campo `gap_only`) e teste de integracao banco→evaluate.

## Observacoes
- Uma rodada completa do backfill (`--from 202301`, slug "either", >20 mil candidatas na CDX) esta em curso gravando em `preditor_p2`; o relatorio so deve ser gerado ao termino, a partir do banco.
- Oferta mista (>=1 evidencia sem gap) entra por desenho; oferta sem evidencia tambem.
