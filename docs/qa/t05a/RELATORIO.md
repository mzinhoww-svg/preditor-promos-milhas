# Reteste T05a (PR #1, commit 5f6d74b) — resultado: DEVOLVIDO (1 bloqueante)

Testador não é o autor; código do autor intocado. Banco próprio `qa_t05a_xtest` no Postgres do compose (migrações aplicadas via Alembic).

## Comandos
- `pytest -q` com `DATABASE_URL`: **31 passed** (sem skips). `ruff check .`: All checks passed.
- `attack_t05a.py` (saída em `saida_reteste.txt`).

## Corrigido (dos 7 bloqueantes originais)
Conteúdo vazio/só espaços, `source` vazio, URL sem esquema/`javascript:`/`file:`/`http://`, `collected_at` inválido, byte nulo, bytes não UTF-8
(`InvalidUTF8Error`), CDX corpo vazio/`[]`/só cabeçalho (0 capturas), 429/500/502/503/504 com retry e `Retry-After` respeitado até 60 s,
404 sem retry, erro de rede/timeout tipado, 12 threads com o mesmo conteúdo → 1 id e 0 erros, reingestão idempotente sem alterar `collected_at`.

## Bloqueante
| # | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|
| B1 | Rate limit da função de módulo é burlado quando se passa `rate_limit`, `min_interval` ou `delay` na chamada: 4 chamadas seguidas com `min_interval=2` esperam 0 s (sem argumento, esperam 1 s corretamente) | M2/M3 | `list_captures` recria `_MODULE_LIMITER = RateLimiter(...)` a cada chamada com esses kwargs, zerando `_last`. Criar o limitador só na primeira vez, ou só atualizar o intervalo e manter `_last` |

## Ressalvas
| # | Sev | Ressalva | Sugestão |
|---|---|---|---|
| R1 | MÉDIA | `CDXRateLimitError` existe mas nunca é lançada: 429 final sai como `CDXHTTPError` | lançar quando `status == 429` |
| R2 | MÉDIA | Formato inesperado vira lista vazia (indistinguível de "sem capturas"): objeto JSON sem chave conhecida, `null`, linhas não-lista são descartadas em silêncio | `CDXResponseError` |
| R3 | MÉDIA | Capturas sem `timestamp`/`original` ou com `timestamp="ontem"` passam adiante com `None`/valor inválido | validar timestamp (14 dígitos) e URL na borda |
| R4 | BAIXA | URL é validada com `strip()` mas guardada sem; `"https://x\n"` é aceita e armazenada com quebra de linha | normalizar e rejeitar caracteres de controle |
| R5 | BAIXA | `collected_at` no futuro (2999) e 1900 aceitos | rejeitar > agora + tolerância |
| R6 | BAIXA | Conteúdo lista/objeto é convertido por `str()` e gravado (`"['a', 'b']"`); surrogate solto levanta `UnicodeEncodeError` em vez de `IngestError` | aceitar só `str`/`bytes` |
| R7 | INFO | Dedup é por `(source, content_hash)`: mesmo conteúdo em outra URL da mesma fonte devolve a 1ª linha e a URL da 2ª captura se perde; BOM entra no hash | decisão de projeto; documentar |
| R8 | INFO | `Retry-After` > 60 s é limitado a 60 s (3 tentativas) | aceitável; registrar |

## Decisão
Devolvido por B1 (mesma classe do bloqueante original de rate limit, ainda aberta quando o limite é configurado por chamada). R1–R3 no mesmo ciclo.
