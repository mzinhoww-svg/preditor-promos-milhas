# Teste cruzado T05 (PR #19, commit b78ce04) — resultado: DEVOLVIDO

Testador não é o autor; código do autor intocado. Banco próprio `qa_t05_coll`; relógio fixo (`now=`); `transport` injetado (sem rede real).
Reproduzir: `uv run python docs/qa/t05/attack_collector.py .` (saída em `saida.txt`).

## Comandos
- `pytest -q` com `DATABASE_URL`: **93 passed** (o `tests/test_collector.py` novo tem só 3 testes: `parse_feed`, `robots_allowed`, `content_hash`;
  nenhum cobre `collect_rss`, `backfill`, pipeline, idempotência ou `source_health`). `ruff check .`: All checks passed.

## Bloqueantes
| # | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|
| B1 | `backfill()` nunca funciona com o padrão: `from_="202301"` é rejeitado por `_to_cdx_timestamp` (aceita 8 ou 14 dígitos), o `ValueError` é engolido e o retorno é 0 | S14 (com `20230101` passa) | `except Exception: captures = []`. Aceitar `YYYYMM` e levantar erro de verdade |
| B2 | Vazamento temporal no backfill e no RSS: `first_seen_at` = hora da coleta (`2026-10-13`) para artigo de 2023; `raw_message.collected_at` = `now()`; não existe `observed_at` (migração 0002 ausente) nem uso de `pubDate`/`published_time` | S1b, S9, S14b, S14c | spec 2.4 e critério 4.1(4) do PR #2; `process_raw_message` usa `raw.collected_at` quando `first_seen_at is None` |
| B3 | O coletor não busca nada em produção: `fetch_url` e `fetch_snapshot` sem `transport` devolvem `None`; `collect_rss` volta `[]` e marca `alert`. Também nunca baixa `robots.txt` (sem `robots_txt` passado, não consulta) | S6, S7b | implementar GET com `httpx`, robots com cache de 24 h por domínio |
| B4 | Falhas engolidas: oferta sem direção (`Livelo e Smiles`, origem `None`) viola `NOT NULL` e some; erros de DB em `_find_offer`/`_insert_evidence`/`update_source_health`/`process_raw_message` viram `pass`; CDX 503 vira "0 itens" | S3, S15 | `except Exception: pass` em 8 pontos; registrar e propagar, ou gravar em fila de revisão |
| B5 | Dados inventados e sem validação de negócio: só data de fim (`até 20/10`) vira `start_at = first_seen` (desfaz a correção N2 do T07a); `validate_offer` nunca é chamado: `fim < inicio` e janela de 364 dias entram em `offer` | S4, S10 | usar `inicio=None` → revisão; chamar `validate_offer` antes do INSERT |
| B6 | `source_health` não mede o que a spec pede: `items_new` conta itens do feed (3ª execução sem novidade reporta 2, o alerta nunca dispara), `extraction_rate` fixo 1,0/0,0, hash do `robots.txt` não é gravado, sem alerta de 7 dias | S2b, S8 | contar linhas realmente novas (`RETURNING id` do INSERT), taxa = ofertas/itens |

## Ressalvas
- Backfill sem normalização de URL nem "captura mais antiga": `?utm_`, `/embed/` e a recaptura de 2025 viram 3 downloads e 2 linhas (S14); sem `resumeKey`, sem filtro `mimetype`.
- Corpo em bytes é descartado (`str(bytes)` → XML inválido → `[]`) (S5); XML inválido é indistinguível de "sem itens" (S8).
- Conflito de bônus vira `segment_label="bonus_conflitante"` e é gravado em `offer` (S11).
- `RateLimitState` é criado a cada chamada (limite por domínio e teto de 200/dia da spec §1 não existem); aliases em excesso (`collect_all = collect_rss`).

## Passou
Idempotência de contagem na reexecução (raw 2, offer 2, evidence 2); 2 fontes → `n_sources=2`, `validated`; PPV guarda só título (decisão 002);
robots bloqueando `/feed/` → 0 itens; XML bomb e feed de 2000 itens sem custo.

## Decisão
Devolvido. B1–B6 bloqueiam; sem B2 o backfill reintroduz o vazamento que a spec e o APR-007 proíbem.

---

# Reteste ciclo 1 (PR #19, commit ff7e1d9) — resultado: APROVADO COM RESSALVAS

Banco próprio `qa_t05_coll2` (migrações 0001 e 0002 aplicadas), relógio fixo, `transport` injetado; o fetch "real" foi substituído por stub (sem rede).
Script: `docs/qa/t05/retest_ciclo1.py` (e `attack_collector.py` da rodada anterior).

## Comandos
- `pytest -q` com `DATABASE_URL`: **93 passed** (mesmo total de antes: **nenhum teste novo** para B1–B6). `ruff check .`: All checks passed.

## B1–B6
| # | Resultado | Evidência |
|---|---|---|
| B1 | corrigido | `backfill()` com `from_` ausente, `"202301"` e `"20230101"` → 1 raw (URL normalizada, captura mais antiga) |
| B2 | corrigido | `first_seen_at` = `pubDate` (12/10 e 02/10/2023) e, no backfill, 2023-10-05; `observed_at` existe (0002) e `collected_at` fica em `now()` |
| B3 | corrigido | sem `transport`: baixa `robots.txt` e o feed (2 chamadas); `Disallow: /feed/` → 0 itens e só o robots é requisitado |
| B4 | corrigido | DB fora do ar e CDX 503 propagam (`RuntimeError`, `CDXHTTPError`) em vez de "0 itens" |
| B5 | corrigido | só data de fim → sem oferta (sem `start_at` inventado); `fim < inicio` e janela de 364 dias → 0 ofertas |
| B6 | corrigido | 3ª execução sem novidade → `items_new=0` com alerta; `extraction_rate` = ofertas/itens; `robots_hash` gravado |

## Ressalvas (não bloqueiam)
| # | Sev | Ressalva | Evidência |
|---|---|---|---|
| R1 | MÉDIA | Sem testes de regressão: `tests/test_collector.py` segue com 3 testes triviais; B1–B6 só existem como script de QA | pytest 93 = 93 |
| R2 | MÉDIA | `transport` que devolve `bytes` quebra: `robots_allowed` recebe `bytes` e levanta `TypeError` não tratado (o caminho real usa `.text`, então só afeta injeção) | S5 |
| R3 | BAIXA | Reexecutar com o mesmo `now` levanta `IntegrityError` na PK `(source, checked_at)` de `source_health`, depois de já ter ingerido | S2 |
| R4 | BAIXA | `observed_at` do backfill usa o timestamp da captura (2023-10-05) e ignora `article:published_time` (2023-10-04), contra a regra "mínimo dos dois" da spec §2.4 | `retest_ciclo1.py` |
| R5 | BAIXA | `Livelo e Smiles` sem direção continua sem oferta (raw gravado; `extraction_rate` cai); depende da decisão sobre par não direcionado | S3 |
| R6 | BAIXA | Conflito de bônus continua gravado como `segment_label="bonus_conflitante"` | S11 |

## Decisão
Aprovado para merge com R1 como condição de rastreabilidade (adicionar testes de B1–B6) e R2–R6 em ciclo posterior.
