# QA — PR #36 reteste (b13fd97) — CODIGO APROVADO; RELATORIO BLOQUEIA O MERGE

Banco proprio (`qa_backfill2`; head 0005), venv 3.12, 171 passed + ruff limpo. Banco do autor (`preditor_p2`) lido so com SELECT. Codigo intocado.

## Ataques do PR #39, um a um
| Ataque | Antes (62f0602) | Agora (b13fd97) |
|---|---|---|
| robots 301 | `robots_hash=None`, coleta segue | segue redirect → `ok` |
| robots 403 / 500 / conexao recusada | fail-open | `robots_unavailable`, 0 downloads (R1) |
| robots 404 | — | `ok`, sem restricoes (aceitavel, RFC 9309) |
| Disallow total | aborta | 0 fetches (R2) |
| Disallow por URL (`/p3/`) | baixava | `robots_disallowed`, nao baixa (R3) |
| 110% do card da Azul (raw 14) | oferta 110% | nenhuma oferta (corpo extraido ignora aside/cards) |
| 58% de anuncio de hoteis (raw 61) | oferta smiles→livelo 58% | nenhuma oferta |
| 100% (raw 144) | 100% de "CSS" | o corpo realmente diz "ate 100% de bonus + ate 20% de pointsback" — **correcao minha:** a evidencia sustenta 100%; sem data de inicio no trecho, nao vira oferta |
| prorrogacao contada 2x (offers 2/3) | 2 ofertas | `dedupe_extensions` funde (end_at = max) (D1) |
| relatorio "2 tentativas" | falso (attempts=1) | tentativas contadas e limitadas: fetch_failed 3 em 5 execucoes (max 3); `error` 3 em 6 (T1/T2); `_retry_allowed` |
| backoff 429 | nenhum | 429,429,200 → sleeps 30 s e 60 s, devolve conteudo; 429x3 → None; 404 → None sem sleep |
| ritmo / idempotencia / retomada | ok | ok (sleep(10) antes de cada fetch; reexec 0 fetches; sem state 0 duplicatas) |
| gap publicacao x captura | — | `published_at` + `published_vs_capture_gap` gravados (83 das 172 paginas HTML com gap > 7 d no banco do autor) |
| 2a fonte RSS Pontos pra Voar | listada sem corpo | 20 `raw_message` so com titulo (44–97 bytes), robots fail-closed antes; sem corpo |

## Bloqueante
**Relatorio vs banco.** `docs/ACTIONS.md` nao foi atualizado neste commit e continua afirmando "12 campanhas (9+3), 173 raw, 64 falhas apos 2 tentativas". O banco do autor apos o reprocesso tem **192 raw (144 + 28 + 20 RSS) e 1 oferta** (livelo→smiles 100%, 2022-09-22, evidencia raw 167 sustenta; 0 validadas). O `state.json` segue v1 (robots_hash None nas 2 fontes). O relatorio precisa: contagens do banco novo; "descartadas como falso-positivo"; e declarar que a queda 12 → 1 vem do filtro de corpo + exigencia de data de inicio no trecho (nao de campanhas inexistentes).

## Ressalvas
1. **Recall**: 46 paginas com titulo "livelo+smiles+bonus" nao geram oferta (`corpus_bf_r2.out`); 81 paginas geram trecho com bonus, quase todas sem data de inicio no trecho → descartadas. Com 1 campanha o gate (>=25 por par/tipo) nao e atingivel; dizer isso na secao "nao coletado".
2. **Deteccao do corpo**: sem `<article>`/classe `entry-content`, `article_text` cai em blocos de ruido — raw 118 (campanha real "Smiles ate 80%") devolve 297 chars de cards laterais e perde a campanha; 40/192 paginas com corpo < 600 chars.
3. **Wildcards de robots**: `urllib.robotparser` nao entende `*`; `Disallow: /*?s=` e `/*/search/` nao bloqueiam (C_wildcard = false). Baixo risco aqui (URLs sem query; feed fixo), mas e lacuna de conformidade.
4. Extrator ainda atribui direcao/par errado em alguns trechos (raw 56 → esfera→azul_fidelidade 70%), contido porque sem data nao vira oferta.
5. Migracao `0005` com parent `0003`: reparentar para `0004` se T08b mesclar antes (anotado na propria migracao).
