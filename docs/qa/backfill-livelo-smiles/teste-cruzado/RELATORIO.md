# QA — PR #36 backfill real Livelo→Smiles (62f0602) — DEVOLVIDO

Banco proprio (`qa_backfill`) + leitura somente-SELECT do banco do autor (`preditor_p2`) e do `state.json` dele; 3 requests a robots.txt reais (10 s entre elas). Codigo do autor intocado.

## Veredito por criterio
| Criterio | Resultado |
|---|---|
| 1 req / 10 s | OK no codigo: `sleep(10)` imediatamente antes de cada snapshot (A4: 6/6). Lacuna menor: o CDX da fonte seguinte sai logo apos o ultimo snapshot da anterior (<10 s). Sem backoff para 429: 1 falha ja conta como tentativa. |
| robots.txt | **FALHA.** (a) fail-open silencioso: `fetch_robots` falha -> `None` -> baixa tudo (A3/A3b: 6/6 baixadas). (b) causa raiz real: robots e buscado em `http://` sem `follow_redirects` -> 301 (passageirodeprimeira) e 403 (melhorescartoes) -> `robots_hash=None` no `state.json` para as **2 fontes que de fato foram baixadas**; so pontospravoar (que nao baixa corpo) tem hash. O relatorio diz "robots.txt checado". (c) so a raiz `/` e consultada: `Disallow: /p3/` nao impede baixar `/p3/` (A2). Obs.: lendo os robots.txt reais, os artigos coletados NAO sao proibidos — o problema e a verificacao, nao (ate onde vi) o conteudo coletado. |
| Idempotencia | OK: reexecucao 0 fetches novos; sem `state.json`, 0 duplicatas em raw_message/offer/offer_evidence (A5/A5b); URL duplicada baixada 1x (A10). |
| Retomada | OK: interrupcao no 4o fetch preserva `state.json`, retomada baixa so os 3 restantes (A6). Falha: `status=error` (excecao no processamento) nao tem limite de tentativas — re-baixa a cada execucao (A8: 5 execucoes, 5 fetches). |
| Nada inventado | **FALHA.** Contagens batem (12 campanhas, 9+3, 0 validadas, 173 raw, 144/28 coletadas, 32+32 falhas), mas o **conteudo** nao: ver abaixo. |
| Relatorio diz o que NAO foi coletado | Parcial: lista as lacunas de cobertura, mas (i) "64 falhas apos 2 tentativas" e falso — `state.json`: attempts=1 nas 64; (ii) nao diz que a extracao capturou numeros de menus/anuncios; (iii) "Base: 173 raw" vs 172 `done` (1 raw sem rastro no estado). |

## Campanhas nao sustentadas pela evidencia (reproduzidas com `extract()` sobre o raw guardado)
| offer | par / bonus gravado | evidencia | por que e falso |
|---|---|---|---|
| 1 | livelo→smiles **110%** (2026-09-24) | raw 14, "Smiles ... pontos + dinheiro" (corpo diz 80%) | 110% vem do card lateral "Azul Fidelidade oferece ate 110%" (outro programa) |
| 4 | smiles→livelo **58%** (2026-03-21) | raw 61, "Milhas na hora na ExpoMilhas" | 58 = "50% de desconto + 8% off" de anuncio de hoteis (regra de soma `a% + b%`); materia nao fala de bonus; direcao smiles→livelo e inventada |
| 8 | livelo→smiles **100%** (2023-11-14) | raw 144, "20% de pontos de volta" | 100% vem de CSS (`linear-gradient ... 100%`)/meta com "1000%"; campanha e pontos-de-volta |
| 7 | livelo→smiles 80% (2020-02-18) | raw 86, titulo "ate 70% de bonus" | divergente do titulo (nao confirmado no corpo) |
| 2 e 3 | livelo→smiles 80% em 2026-03-19, fim 03-20 e 03-31 | 4 materias da mesma promocao ("prorrogado") | uma campanha contada duas vezes |

Logo, de 12 campanhas, **3 sao falsas (25%), 1 divergente, 1 duplicada** — a base de campanhas reais efetiva e ~7-8, nao 12; para o gate (>=25/par-tipo) a distancia e maior que a relatada.

## Pedido ao autor
1. robots: `follow_redirects=True`, tentar https, fail-closed (sem robots verificado -> nao coleta e registra `robots_unverified`), checar `robots_allowed` por URL; registrar o hash para todas as fontes.
2. Extracao: remover chrome da pagina (nav/aside/script/style/cards laterais) antes de extrair; ignorar `%` fora do corpo do artigo; exigir bonus na mesma sentenca de livelo/smiles; deduplicar prorrogacoes.
3. Reprocessar e republicar o relatorio com contagens do banco novo; corrigir "2 tentativas"; adicionar "N campanhas descartadas como falso-positivo" e listar o que nao foi verificado.
4. Limite de tentativas tambem para `status=error`; backoff em 429.
Reexecutar: `PYTHONPATH=src python docs/qa/backfill-livelo-smiles/teste-cruzado/attack_backfill.py` (com `DATABASE_URL` proprio).
