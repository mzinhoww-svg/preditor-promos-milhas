# QA — PR #49 listener de feeds (df843e0) — APROVADO COM RESSALVAS

Banco proprio `qa_pr49` / `qa_pr49b`; rede simulada (stubs) + 1 execucao real `--once --no-pipeline`. Codigo intocado.

## Verificado
| Ataque | Resultado |
|---|---|
| Suite / lint | 240 passed (banco vazio), ruff limpo, head 0005; 9 testes proprios |
| robots 403 | fonte pulada (`robots_unavailable`), feed e artigos NAO buscados, `source_health.alert=true`; as outras 2 fontes `ok` (F1) |
| robots Disallow por URL | `/p2/` nao baixado, `/p1/` sim (F2); Disallow do feed → `robots_disallowed`, feed nao buscado (F3); robots 404 → libera (F4) |
| 1 req/10 s por dominio | 9 requisicoes, 6 sleeps de 10 s = esperado (n−1 por dominio) (P1) |
| Idempotencia | 2a rodada: 0 itens novos, 0 buscas de artigo, raw/offer/health inalterados (I1) |
| Falha de fonte | feed 500 e rede caida → `feed_unavailable` sem afetar as demais (X1/X2); XML quebrado → `feed_unavailable` (X3); todos os artigos 404 → `ok` com `failures=2`, alerta no health (A1) |
| Retomada | itens que falharam nao viram "conhecidos": proxima rodada os coleta (A2) |
| PPV nunca grava corpo | `content` = titulo (max 46 B; 97 B na rodada real); `description` com marcador proibido: 0 gravados; 0 requisicoes aos artigos do PPV (N1) |
| Gap/observed | item de 01/09 → gap=true, observed=pub; item de hoje → false (N1) |
| Rodada real | 3 fontes `ok`: 20 titulos PPV, 30 PdP, 10 MC; 0 ofertas (sem campanha Livelo→Smiles no momento); health e robots_hash gravados |

## Ressalvas
1. **Excecao interna derruba o ciclo:** `run_once` nao protege cada fonte. Com `_store` levantando em PdP (simula erro de banco/extracao), `run_once` aborta com RuntimeError, nenhuma linha de `source_health` para a fonte que falhou e as fontes seguintes na lista nao rodam (X4). "Falha de fonte registrada sem derrubar as outras" vale so para falhas de rede/robots/feed. Envolver cada `run_source` em try/except que grave `alert=true` e siga.
2. **Pacing nao persiste entre execucoes:** o `_Pacer` e criado por fonte/rodada; o primeiro request de cada dominio nao espera. Cron a cada 30 min e ok; duas execucoes simultaneas ou `--once` em loop violam 1 req/10 s. Persistir o ultimo request por dominio (ou lock).
3. **Titulos repetidos:** dois itens com o mesmo titulo e URLs diferentes sao deduplicados por `content_hash`; `items_new` conta 2 mas ha 1 linha e a 2a URL nunca fica "conhecida" (e reprocessada a cada rodada) (E2).
4. Wildcards de robots (`Disallow: /*?s=`) continuam fora do `robotparser` (herdado do #36).
