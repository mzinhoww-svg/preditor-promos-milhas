# QA — revisao do PR #42 (conjunto de ouro provisorio, c9c923f) — APROVADO COMO PROVISORIO, COM RESSALVAS

Leitura de `data/gold/*` + amostra contra o texto original em `preditor_p2` (SELECT). Nada do conjunto foi alterado.

## Conformidade
| Criterio | Resultado |
|---|---|
| Sem texto integral de terceiros | OK: 95 trechos, max 597 chars (0 > 600), total 35.339 chars; 0 com HTML; nenhum campo `content/html/body`; todos com `url` + `raw_message_id` + `content_sha256` |
| `gold_provisional` | OK: 50/50 campanhas e 95/95 mensagens; `MANIFEST.sha256` vazio |
| Split decisao 005 | OK: 20 dev / 30 test (campanhas); distratores 8 / 12; todas as mensagens de uma campanha no mesmo split |
| Integridade | OK: 0 `evidence_ids` orfaos; 0 positivas sem campanha; `first_seen_at` = minimo do `observed_at` das evidencias em 50/50; `all_evidence_gap` consistente (23/50) |
| Schema | campanhas e mensagens validam (0 erros) **somente** apos extrair `oferta-v1` do markdown do plano: o `$ref` do `message.schema.json` aponta para uma URL do GitHub que nao existe e nao ha arquivo local |
| Composicao §10 | **desvio declarado, nao conforme**: A = 49 (spec ~28), B = 1 (spec 22), 19 campanhas anteriores a 2023, 2026 = 4 (cota 8), validadas 18 (cota 20), `purchase_discount`/`boosted_accrual` 0, `multi_oferta` 0, `renewal` 1 (cota 2). O README declara os deficits e motivos (nao se inventa texto) |
| Amostra de 10 (seed 20261014; 4 dev/6 test) | 10/10: `content_sha256` bate; trechos verbatim (m-0065 4/5 sentencas: 1 com emoji/formatacao); **direcao livelo→smiles correta 10/10; `bonus_pct` bate com o texto 10/10**; fins conferidos contra "(DD)", "hoje/amanha" e dia da semana (m-0015 qua 30/06/2021, m-0062 sex 14/03/2025 ok) |
| Checagem automatica | 69 `fim` verificados: 2 suspeitos (m-0037, m-0042) — falso alarme apos leitura ("vale so hoje"); `bonus_pct` ausente do trecho: m-0035 (80%+10% condicional) |

## Ressalvas
1. **Distratores com artefato de coleta (5 de 13 do PdP):** m-0081 e uma pagina de verificacao da Cloudflare ("One moment, please... "), m-0082 "Alerta de disponibilidade!" (vazio), m-0083/m-0087/m-0088 sao concatenacoes de cards laterais (contem frases tipo "Smiles oferece ate 60% de bonus...", rotuladas `ofertas: []`). Nao exercitam as categorias do §4 (noticia sem bonus, expirada, cartao, outro programa, bumerangue isolado) e podem punir/premiar o extrator por motivo errado. Substituir (ha 36 mensagens sem oferta no universo).
2. **Anotacao de bonus como soma condicional:** m-0035 = 80% + 10% "extra para quem resgatar passagem" → 90; m-0054/m-0055 = 80% + 10% do plano. Documentar a regra ou separar `bonus_pct` (transferencia) do extra condicional, pois a meta de 90% em bonus depende disso.
3. **23/50 campanhas so com evidencia de gap** e o `published_at` do banco do autor esta zerado (ver PR #36): a conferencia humana precisa dos flags reprocessados.
4. **Tags:** `ate_ddmm` 65 e `sem_ano` 31 passam as cotas, mas `multi_oferta`, `decimal`, `virada_ano`, `relampago` = 0 e `renewal` = 1; o split test nao cobre casos dificeis. Registrar como limite da metrica provisoria.
5. 49/50 sao livelo→smiles: o conjunto nao testa origem/destino em outros pares (so 1 esfera→azul).
