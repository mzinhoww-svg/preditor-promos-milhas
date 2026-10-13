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
