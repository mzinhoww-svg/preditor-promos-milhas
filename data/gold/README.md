# Conjunto de ouro T06 (provisório)

**Status: `gold_provisional` em 100% das linhas.** Ainda não há conferência humana. Métrica calculada sobre este conjunto é *provisória* e **não libera o treino** (decisão 004). Spec: `docs/plans/t06-conjunto-de-ouro.md` (§10). Protocolo: decisão 005.

## Conteúdo

| Arquivo | Linhas |
|---|---|
| `campaigns.jsonl` | 50 campanhas: 30 `test` e 20 `dev` |
| `messages.jsonl` | 95 mensagens: 75 positivas (47 `test`, 28 `dev`) e 20 distratores (12 `test`, 8 `dev`) |
| `schema/*.schema.json` | JSON Schema 2020-12. `expected` referencia o `oferta-v1` de `docs/plans/coletor-livelo-smiles.md` §3.1 |
| `review.md` | Tabela para a conferência de Aurimar |
| `MANIFEST.sha256` | Vazio até a primeira linha `gold_verified` |
| `CHANGELOG.md` | Histórico de alterações |

## Origem e texto de terceiros

- **Universo:** os 172 `raw_message` do backfill do PR #36 no banco local `preditor_p2`, lidos **só para leitura**: Passageiro de Primeira 144, Melhores Cartões 28, mais 20 títulos do RSS vivo do Pontos pra Voar.
- **`text`:** é só um **trecho** de até 600 caracteres, cortado em fronteira de frase, com as sentenças da oferta, das faixas e da validade. Sem HTML; o artigo integral fica só no banco local. No Pontos pra Voar o `text` é só o título (decisão 002).
- **Reprodução:** pelo `url` mais o `wayback_ts` (captura mais antiga) ou pelo `raw_message_id`. O `content_sha256` é o hash do HTML bruto gravado.
- **`observed_at`:** é o `observed_at` do `raw_message` (mínimo entre a publicação e a captura), em America/Sao_Paulo. `published_vs_capture_gap` copia a flag do PR #36.

## Regras de anotação (Planejador)

- **Só texto e `observed_at`.** Nada vem de outra fonte nem da data real conhecida depois. O regex T07a não define o `expected`: só ajudou a montar o quadro de candidatas.
- **`inicio`:** só quando o texto dá um início explícito ("válida de X a Y", "iniciou hoje (23)", "a partir de amanhã", "cadastre-se de 18/02 até 19/02"). "Até hoje", "somente hoje", "até amanhã (11)" preenchem **só o `fim`**, com `inicio=null`. Na campanha, `start_at = first_seen_at::date` com `start_inferred=true`.
- **Dia sem mês ou ano:** é resolvido pelo `observed_at` em SP.
- **`bonus_pct`:** é o máximo anunciado. `segmentada=true` quando o máximo exige um grupo; `segmento` é `clube` (Clube Livelo/Smiles, Diamante, plano), `cartao` ou `elegiveis`, e `null` quando o texto não nomeia o grupo.
- **Bumerangue:** os pontos de volta da Livelo vão em `bumerangue_pct` (20), **fora** do bônus (decisão 004).
- **Prorrogação:** é evidência da mesma campanha (tag `extension`). A nova oferta depois do encerramento é `relation=renewal` (c-0027: 16/11/2023 após a de 13–14/11).
- **Distratores:** `expected = {"ofertas": []}`. Também contam como distrator as ofertas com programa fora dos 5 (BB, Sicredi, Itaú, Sem Parar, ALL Accor), conforme a spec §2.

## Desvios da spec e déficits declarados (§4 e §10)

| Item | Spec | Real | Motivo |
|---|---|---|---|
| Janela | 2023+ (§4) | **2020-02 a 2026-09** | De 2023 em diante só há ~31 campanhas; ampliado para fechar 50 |
| Bloco A livelo→smiles | ~28 | **49** | O par invertido do regex escondia campanhas: as "smiles→livelo" são todas Livelo→Smiles no texto |
| Bloco B outros pares | 22 | **1** (esfera→azul_fidelidade) | O universo, filtrado por slug `livelo\|smiles`, quase não tem outros pares |
| `purchase_discount` / `boosted_accrual` | 4 / 3 | **0 / 0** | Os 3 casos de compra de pontos Livelo são de 2018–2019 (ver F1) |
| 2026 | 8 | 4 | |
| Validadas (≥ 2 fontes) | 20 | 18 | Só PdP + MC; o RSS do PPV é só o vivo |
| `titulo_rss` | 8 | 7 (distratores) | O RSS vivo não tem ofertas Livelo/Smiles |
| `virada_ano` / `decimal` / `relampago` | 2 / 2 / 2 | 0 | Sem casos no universo |

Campanhas cujas evidências são **todas** de gap: 23 de 50 (`all_evidence_gap=true`). A data delas depende de `published_time` mais de 7 dias anterior à captura e exige atenção na conferência.

## Achados para o time

- **F1, schema e extrator rejeitam anos antes de 2020.** O `pattern` de `inicio`/`fim` em `oferta-v1` e em `extract.Offer` é `^20[2-3][0-9]-…`. O backfill traz páginas publicadas entre 2018 e 2019, com 9 campanhas e 3 casos de compra de pontos, que **não têm representação válida**. É preciso decidir: ampliar para `20[1-3][0-9]` ou cortar o universo em 2020 na consolidação.
- **F2, direção.** 7 mensagens livelo→smiles saem `smiles→livelo` no regex e 22 saem sem par ("A Smiles oferece … nas transferências da Livelo"). Isso confirma o bloqueante 2 do PR #36 e a correção de direção em andamento.
- **F3, medida indicativa da regex T07a (provisória, não vale como meta):**

| split | origem | destino | tipo | início (±1 d) | bônus | distratores com FP |
|---|---|---|---|---|---|---|
| test | 57% | 57% | 96% | 2/2 | 91% | 4/12 |
| dev | 64% | 64% | 100% | 2/2 | 89% | 2/8 |

Meta da decisão 004: 95% em programa e tipo e 90% em bônus. Só 4 positivas têm `inicio` explícito; a meta de data recai sobre a consolidação (`start_inferred`) e o `fim`.

## Próximos passos

1. Aurimar confere `review.md`. As linhas aprovadas viram `gold_verified` num PR separado, `gold: verificação <data>`, com `MANIFEST.sha256`.
2. O Programador implementa `tests/test_gold.py` (schema, splits, ≤ 600 caracteres, sem HTML, `first_seen` = mínimo) e `preditor.gold.eval` (§7).
3. Quando o PR #36 corrigir `inicio=null` e trouxer o RSS arquivado, reavaliar os déficits de validadas e de `titulo_rss`.
