# STATUS final do MVP

Data: 2026-10-14. Código: `main` em `970612b` (inclui o PR #65). Escrito pelo Planejador para Aurimar. Todo número abaixo vem do banco local `preditor_p2` (lido só com SELECT) ou do relatório `docs/reports/portao-viabilidade-e-campeao.md`. Nada foi estimado.

## 1. Em uma frase

O sistema roda de ponta a ponta **em máquina local**, com dado **real** de Livelo → Smiles. Na primeira execução real do job (PR #65, cópia `preditor_e2e`), **todos os pares saíram em B0** (taxa-base). A série principal de livelo → smiles tem 23 campanhas em `as_of`, abaixo das 25 do B1, porque as campanhas de clube e outros segmentos formam séries próprias. A decisão C1 × B1 ainda **não foi tomada**: há 23 campanhas no treino, abaixo do mínimo de 25. Também **não existe acurácia de produção**, porque o `prediction_log` está vazio (n = 0). Nada foi publicado: não há VPS nem deploy na Vercel.

## 2. O que funciona de ponta a ponta (local)

| Peça | Estado | Onde |
|---|---|---|
| Coleta (RSS + robots fail-closed, 1 req/10 s, UA identificável) | funciona | `src/preditor/collector.py` |
| Backfill Wayback (retomável, idempotente, data de observação própria) | funciona; rodado no `preditor_p2` | `python -m preditor.backfill` |
| Listener recorrente de feeds (URL canônica, teto de 200 req/dia, pausa de 1 h em 429/503) | funciona; cron **documentado, não agendado** | `python -m preditor.jobs.feed_listener --once` |
| Extração (regex + pydantic; sem LLM) | funciona; medida contra o ouro provisório | `src/preditor/extract.py`, `article.py` |
| Consolidação em campanhas (dedup ±3 d, prorrogação, `start_inferred`, gap de publicação) | funciona | `campaigns.py`, `collector.py`, `backfill.py` |
| Modelos B0 / B1 (point-in-time, purge de 30 d) | funcionam | `baseline.py`, `walkforward.py` |
| C1 (LightGBM) + portão campeão × desafiante | funciona; decisão atual `keep_champion` | `model.py` |
| API FastAPI (`X-API-Key`, rate limit) | funciona | `uvicorn preditor.api.app:app` |
| Job diário (predição, `prediction_log` append-only, `model_run` com hash de dados e código) | funciona; **ainda não rodado no `preditor_p2`** | `python -m preditor.jobs.daily_predict daily` |
| Alertas por limiar + explicação por item | funcionam | `alerts.py`, `GET /v1/alerts`, `GET /v1/predictions/{o}/{d}/explanation` |
| STOP (kill switch cooperativo) | funciona nos 3 CLIs (saída 3) | `docs/stop.md` |
| Saúde das fontes | funciona | `GET /v1/source-health` |
| Dashboard Next.js (selo B0/B1 por par, "Modelo não decidido", probabilidade **estimada**, bônus **das campanhas anteriores**) | funciona em local, com fallback "Dados simulados" | `dashboard/` |

Verificação em 2026-10-14, num Postgres descartável migrado até `0008`: **303 testes Python passam**, `ruff` limpo e **38 testes do dashboard passam**. Gasto com LLM: `budget_ledger` vazio no `preditor_p2` (o pipeline não usa LLM pago).

## 3. Real × sintético

| Item | Natureza |
|---|---|
| Base de mensagens (`raw_message`) e campanhas | **real** (backfill Wayback + RSS) |
| Decisão C1 × B1 do relatório de portão | **real** (`data_source="real"`, declarado por quem chama) |
| `docs/reports/t08b-champion-decision.md` | **sintético**; só valida a mecânica, não vale como resultado |
| Números de acurácia nos PRs do QA (por exemplo, n = 9 resolvidas) | **replay em banco de teste**, não é produção |
| Dashboard sem API configurada | **simulado** (`dashboard/mock`), com aviso na tela |
| Conjunto de ouro `data/gold/` | **real, mas provisório** (`gold_provisional`, sem conferência humana) |

## 4. Portão de viabilidade (livelo → smiles, `transfer_bonus`)

| Critério | Valor | Situação |
|---|---|---|
| Campanhas no total | 55 | — |
| Validadas por 2 fontes | 7 (13%) | fraco |
| Meses distintos | 47 (campanhas de 2020-02 a 2026-03) | atende ≥ 24 |
| Utilizáveis (sem só-gap) | **27** no total; **23** na série principal (sem segmento) | **não atende o B1 no job**: a série principal tem 23 < 25 e sai em B0 |
| No treino do walk-forward (purge 30) | **23** | **não atende o C1 × B1 (< 25)** |
| Últimos 24 meses | 12 campanhas; nenhuma depois de 2026-03-11 | não atende |

Outros pares: livelo → latam_pass 5, esfera → smiles 3, esfera → azul_fidelidade 1. Nenhuma campanha de `purchase_discount` ou `boosted_accrual`.

Base: 1.239 `raw_message` (Passageiro de Primeira 314, Melhores Cartões 28, Pontos pra Voar 897 só com título), 177 com gap de publicação.

## 5. Campeão × desafiante

- **Decisão: `keep_champion` (C1 não decidido).** São 23 campanhas no treino, contra o mínimo de 25.
- **Com estes dados, o C1 perde para o B1:** Brier 0,306 contra 0,125 e log-loss 1,261 contra 0,376, com IC a favor do B1, e o C1 não está calibrado. As métricas do B1 são de validação histórica (10 dobras, 3.471 linhas avaliadas).
- **Acurácia de produção: nenhuma ainda.** O `prediction_log` do `preditor_p2` tem **0** linhas. O backtest retroativo do PR #65 (n = 221 por horizonte, só B0, janelas sobrepostas, no `preditor_e2e`) **não é acurácia de produção** e não serve de base para afirmar acerto. A primeira métrica real exige o job diário rodando e janelas de 7, 15 e 30 dias fechadas.

## 6. Limites conhecidos

- **28 das 55 campanhas dependem de data de publicação suspeita** (só-gap) e ficam fora de treino e avaliação até a revisão manual.
- **Buraco recente.** Nada depois de 2026-03-11. O backfill do PdP baixou 316 de 9.750 URLs candidatas (314 gravadas), priorizadas por slug.
- **Segunda fonte fraca.** O Pontos pra Voar (só título, decisão 002) não validou nenhuma campanha.
- **Início inferido.** 90 de 109 evidências têm início inferido (data em que a oferta foi vista).
- **Extrator.** Só regex; a camada LLM não foi feita. Contra o ouro dev: 28/28 campanhas, direção e bônus 100%, fim 79%. O ouro ainda é provisório.
- **B0 com pouco histórico:** com 1 campanha, a probabilidade explode (P(30 d) = 0,996 em esfera → azul) e gera alertas de ruído. A decisão 006 exige ≥ 3 campanhas e ≥ 180 dias para publicar e alertar, e ainda falta implementar.
- **Acurácia com n = 0** devolve zeros; pela decisão 006, deve devolver nulos (falta implementar).
- **Banco desatualizado.** O `preditor_p2` está na migração `0005`; o código está em `0008`. É preciso rodar `alembic upgrade head` antes do job diário.
- **`data_source="real"` é declarado à mão**; derivá-lo da origem dos dados continua pendente.
- **Schema `oferta-v1`** só aceita os anos 2020–2039 (decisão pendente sobre páginas de 2018–2019).

## 7. O que depende de Aurimar

0. **Banco local canônico** (decisão 006, item 4): autorizar recriar `preditor` a partir do `preditor_p2`.
1. **SSH da VPS.** A tentativa com as chaves locais foi negada (`docs/ACTIONS.md`). Sem isso não há API pública, cron nem job diário em produção.
2. **Conferência do conjunto de ouro.** Usar `data/gold/review.md` e `data/gold/duvidas.md` (13 campanhas P1). Isso libera a métrica oficial do extrator (decisão 004) e pode reduzir as só-gap.
3. **Aprovar o deploy na Vercel.** Plano em `docs/deploy-vercel.md`: primeiro deploy em `mock` e protegido.
4. **Cobertura de 24 meses recentes.** Autorizar completar o backfill do PdP (2025-07 em diante; ~26 h a 1 req/10 s) e agendar o listener.
5. Decidir o pattern de ano do schema (2018–2019) e, se quiser, novas fontes (com robots e termos verificados e nova decisão).

## 8. Como rodar em local

```
cp .env.example .env                 # senhas locais
docker compose up -d --wait
set -a; . ./.env; set +a
uv sync --python 3.12
uv run alembic upgrade head
uv run pytest                        # 303 testes
uv run python -m preditor.jobs.feed_listener --once      # coleta
uv run python -m preditor.jobs.daily_predict daily       # predições do dia
PREDITOR_API_KEY=... uv run uvicorn preditor.api.app:app --port 8055
cd dashboard && cp .env.example .env.local && npm install && npm run dev -- -p 3100
```

Para o dashboard ler a API local, use `PREDITOR_API_BASE_URL=http://127.0.0.1:8055/v1` e `PREDITOR_API_KEY` em `dashboard/.env.local` (só no servidor).

## 9. Como parar e reverter

- **Parar:** crie o arquivo `STOP` na raiz, ou use `PREDITOR_STOP=1`. Job, backfill e listener saem com código 3 antes da próxima unidade de trabalho. O `--reprocess` é atômico e não deixa ofertas parciais. Para retomar, remova o arquivo ou a flag. Detalhes em `docs/stop.md`.
- **Reverter código:** cada entrega entrou por PR. Use `git revert <merge>` do PR correspondente.
- **Reverter banco:** `uv run alembic downgrade <revisão>`. A `0008` é só de dados e não restaura quais runs eram campeões. O `prediction_log` é append-only por desenho.
- **Dashboard:** sem deploy, nada a reverter. Depois do deploy, use o rollback de deployment da Vercel.
