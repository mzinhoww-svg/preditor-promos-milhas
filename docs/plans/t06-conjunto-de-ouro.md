# T06 — Conjunto de ouro (50 campanhas)

Data: 2026-10-13. Autor: Planejador. Decisões relacionadas: 002 (coleta), 003 (point-in-time), 004 (metas do extrator), 005 (protocolo do ouro).

## 1. Objetivo

Ter uma referência anotada à mão para medir o extrator (T07a regex, T07b LLM) contra as metas da decisão 004:

- programa origem/destino: precisão e cobertura >= 95%;
- tipo: precisão e cobertura >= 95%;
- data de início com erro <= 1 dia em >= 90%;
- `bonus_pct` exato em >= 90%.

O ouro também testa a consolidação de mensagens em campanhas (dedup ±3 dias, renovação × prorrogação, fonte única, conflito de data), como define o `docs/glossario.md`.

O treino do modelo (T08) só é liberado quando o extrator atinge as metas **no split `test` do ouro com status `gold_verified`**. Métrica calculada sobre `gold_provisional` sai rotulada como provisória e não libera nada.

## 2. Unidades

- **Mensagem** (`messages.jsonl`): uma evidência, isto é, um artigo, post ou título de RSS, com o texto a extrair e a saída esperada do extrator no esquema `oferta-v1` (seção 3 de `coletor-livelo-smiles.md`).
- **Campanha** (`campaigns.jsonl`): o evento consolidado, ligado a 1..N mensagens.
- **Distrator**: mensagem sem oferta válida, ou com oferta fora do escopo, cuja saída esperada é `{"ofertas": []}`. Serve para medir a precisão (falsos positivos). **Não conta** nas 50 campanhas.

Meta: **50 campanhas**, cerca de 90 mensagens positivas (média de 1,8 fonte por campanha) e **20 distratores**.

## 3. Arquivos em `data/gold/`

| Arquivo | Conteúdo |
|---|---|
| `README.md` | Protocolo resumido, contagens por estrato e status, e como rodar a avaliação. |
| `schema/message.schema.json` | JSON Schema 2020-12 de uma linha de `messages.jsonl`. |
| `schema/campaign.schema.json` | JSON Schema 2020-12 de uma linha de `campaigns.jsonl`. |
| `messages.jsonl` | Uma mensagem por linha, ordenada por `gold_id`. |
| `campaigns.jsonl` | Uma campanha por linha, ordenada por `campaign_id`. |
| `MANIFEST.sha256` | SHA-256 canônico de cada linha com `status=gold_verified` (seção 6). |
| `CHANGELOG.md` | Registro de cada alteração em linha verificada: data, motivo e aprovação humana. |

**Nada de HTML integral** no repositório (decisão 002, repo público). O campo `text` guarda só o **trecho necessário à extração**, com no máximo 600 caracteres e cortado em fronteira de frase. Para Pontos pra Voar, o texto é **somente o título do RSS** (decisão 002, opção C). A reprodução do original é feita por `url` + `wayback_ts` ou por `raw_message_id` no banco local.

### 3.1 Linha de `messages.jsonl`

```json
{
  "gold_id": "m-0001",
  "split": "test",
  "status": "gold_provisional",
  "kind": "positive",
  "source": "passageirodeprimeira.com",
  "url": "https://passageirodeprimeira.com/...",
  "wayback_ts": "20240312093000",
  "raw_message_id": 123,
  "content_sha256": "…",
  "observed_at": "2024-03-12T09:30:00-03:00",
  "text": "Livelo e Smiles: transfira pontos com até 90% de bônus até 15/03…",
  "expected": {"ofertas": [{"origem": "livelo", "destino": "smiles", "tipo": "transfer_bonus",
                "bonus_pct": 90, "inicio": "2024-03-12", "fim": "2024-03-15",
                "segmentada": true, "segmento": "clube", "bumerangue_pct": null}]},
  "campaign_ids": ["c-0001"],
  "tags": ["ate_ddmm", "clube"],
  "notes": "80% geral + 10% clube = 90 segmentada",
  "annotated_by": "planejador",
  "verified_by": null,
  "verified_at": null
}
```

Regras:

- `observed_at` é obrigatório e segue a regra de `coletor-livelo-smiles.md` §2.4: o mínimo entre `published_time` e a captura Wayback mais antiga. Mensagem sem `observed_at` não entra.
- `expected` é escrito **a partir do texto e de `observed_at`, e de nada mais**. O ano de uma data sem ano é o mais próximo de `observed_at` em SP (a mesma regra da T07a). É proibido "corrigir" o esperado com o que se sabe depois (por exemplo, a data real em que a campanha começou, vista em outra fonte). Isso é vazamento de rótulo para o extrator: ele só vê a mensagem.
- `inicio = null` quando o texto só diz "até DD/MM". Nesse caso a campanha usa `first_seen_at::date` com `start_inferred=true`.
- `bonus_pct` é o máximo anunciado. O bumerangue fica **fora** do bônus e vai em `bumerangue_pct` (decisão 004).
- `campaign_ids` fica vazio nos distratores. Uma mensagem com 2 ofertas aponta para 2 campanhas.

### 3.2 Linha de `campaigns.jsonl`

```json
{
  "campaign_id": "c-0001",
  "split": "test",
  "status": "gold_provisional",
  "origin": "livelo", "destination": "smiles", "event_type": "transfer_bonus",
  "segmented": true, "segment_label": "clube",
  "start_at": "2024-03-12", "start_inferred": false, "end_at": "2024-03-15",
  "bonus_pct": 90,
  "first_seen_at": "2024-03-12T09:30:00-03:00",
  "evidence_ids": ["m-0001", "m-0002"],
  "n_sources": 2, "validated": true, "date_conflict": false,
  "relation": "new",
  "tags": ["clube"],
  "notes": ""
}
```

- `first_seen_at` = menor `observed_at` entre as evidências.
- `relation`: `new`, `renewal` ou `extension`. A prorrogação **não** é campanha nova: aparece como evidência extra da campanha original com `end_at` atualizado, e conta para a cota de casos difíceis pela tag `extension` na mensagem.
- `validated` e `date_conflict` seguem o glossário.

## 4. Amostragem (estratos e cotas)

Universo: `raw_message` com `observed_at` não nulo, de 2023-01-01 até o corte da coleta T05, nas fontes C1 (Passageiro de Primeira), C2 (Pontos pra Voar, só título) e C3 (Melhores Cartões).

Cotas mínimas, sobre as 50 campanhas:

| Estrato | Mínimo |
|---|---|
| Livelo → Smiles `transfer_bonus` (alvo do PoC) | 30 |
| Outros pares dos 5 programas, para testar origem e destino | 10 |
| `purchase_discount` | 4 |
| `boosted_accrual` | 3 |
| Cada ano de 2023, 2024, 2025 e 2026 | 8 |
| Campanha com >= 2 fontes (`validated=true`) | 20 |
| Campanha de fonte única | 8 |

Casos difíceis, contados por tag na mensagem (uma mensagem pode ter várias):

| Tag | Mínimo | O que testa |
|---|---|---|
| `ate_ddmm` (início nulo) | 4 | correção N2 da T07a |
| `sem_ano` | 6 | inferência do ano por `observed_at`, incluindo a virada de ano (dez → jan) |
| `virada_ano` | 2 | mensagem de dezembro com data de janeiro |
| `clube` / `segmentada` | 5 | segmento e `bonus_pct` máximo |
| `decimal` (ex.: 37,5%) | 2 | `NUMERIC(6,2)` |
| `bumerangue` | 3 | bumerangue fora do bônus |
| `multi_oferta` | 3 | mais de uma oferta na mesma mensagem |
| `extension` | 2 | prorrogação ≠ nova campanha |
| `renewal` | 2 | renovação = nova campanha |
| `relampago` (<= 48 h) | 2 | duração curta |
| `date_conflict` | 2 | fontes com datas diferentes |
| `titulo_rss` (C2) | 8 | extração só pelo título |

Distratores (20): 6 notícias de programa sem bônus, 4 ofertas expiradas ou retrospectivas ("relembre as melhores promoções de 2023"), 4 ofertas de cartão ou cashback sem par de programas, 3 ofertas de outros programas fora dos 5, 3 bumerangues isolados.

Procedimento:

1. Script de candidatos (`scripts/gold_candidates.py`, a cargo do Programador). Pré-filtra por palavra-chave e pela saída da regex T07a, agrupa em campanhas candidatas pela chave do glossário e sorteia por estrato com `seed=20261013`. Ele **lista** candidatas; não grava ouro.
2. O anotador (agente) lê cada mensagem, escreve `expected` e as campanhas e marca `gold_provisional`.
3. Quando uma cota não fecha porque o universo não tem casos suficientes, o `README.md` registra o déficit. Não se inventa nem se adapta texto.

## 5. Split dev/test (decisão 005)

- **20 campanhas `dev`** e **30 campanhas `test`**, sorteadas dentro de cada estrato. Todas as mensagens de uma campanha ficam no mesmo split. Os distratores ficam divididos 8 `dev` / 12 `test`.
- `dev` pode ser lido por quem ajusta regex e prompt. `test` não pode ser usado para ajustar regex, prompt nem limiar; serve só para medir. O relatório sempre mostra os dois splits separados, e a meta da decisão 004 vale em `test`.
- Se uma correção do extrator for motivada por um erro visto em `test`, essa campanha passa para `dev` e é reposta em `test` por outra do mesmo estrato. A troca é registrada no `CHANGELOG.md`.

## 6. Status, conferência humana e imutabilidade

- `gold_provisional`: anotado por agente. Pode ser editado por agente em PR, com o motivo no `notes`.
- `gold_verified`: conferido por Aurimar, linha a linha, com `verified_by="aurimar"` e `verified_at`. **Só o humano altera** (decisão 004).
- Conferência: o anotador gera `data/gold/review.md`, uma tabela com o trecho, o esperado e as tags, com uma caixa por linha. Aurimar marca as aprovadas e um agente aplica só essas mudanças de status, num PR separado com o título `gold: verificação <data>`.
- Imutabilidade:
  - `MANIFEST.sha256` guarda o SHA-256 do JSON canônico (chaves ordenadas, sem espaços, UTF-8) de cada linha verificada.
  - O teste `tests/test_gold.py` falha se uma linha verificada mudar sem que a entrada correspondente no `MANIFEST` e no `CHANGELOG.md` tenha mudado no mesmo commit.
  - Mudança no `MANIFEST` exige aprovação de Aurimar no PR (CODEOWNERS em `data/gold/MANIFEST.sha256`).

## 7. Avaliação

Comando: `uv run python -m preditor.gold.eval --layer regex|llm|full --split test|dev|all [--status verified|all]`. Ele gera `docs/reports/t06-extrator-<layer>-<data>.md` e um JSON com os mesmos números.

Pareamento, por mensagem: as ofertas previstas são pareadas com as esperadas pela chave `(origem, destino, tipo, segmento)`. As que sobram viram FP (previstas) ou FN (esperadas). Com chave parcial (`origem` nula), o pareamento é guloso pelo maior número de campos iguais.

Métricas por campo, para `origem`, `destino`, `tipo`, `inicio` e `bonus_pct`:

- precisão = corretos / previstos não nulos;
- cobertura = corretos / esperados não nulos;
- `inicio`: é correto se |previsto − esperado| <= 1 dia. Quando o esperado é `null`, o acerto é prever `null`. A métrica da meta é a % de esperados não nulos com erro <= 1 dia;
- `bonus_pct`: igualdade com tolerância de 0,01;
- distratores: taxa de falso positivo = % de distratores com alguma oferta prevista;
- campanha (consolidação): % de campanhas reconstruídas com a mesma chave, `start_at` (±1 dia), `bonus_pct` e `relation`.

O relatório traz IC 95% por bootstrap **por campanha** (todas as mensagens da campanha juntas), porque as mensagens de uma mesma campanha são correlacionadas. Com n=30 campanhas, uma meta de 95% só é afirmada quando o limite inferior do IC passa de 90%. Abaixo disso, o relatório marca "meta não demonstrada".

Temporal: o extrator recebe `text` e `observed_at` como `first_seen_at`, nada além disso. A avaliação nunca passa `start_at`, `campaign_ids` ou outra fonte para o extrator.

## 8. Critérios de aceite da T06

1. `messages.jsonl` e `campaigns.jsonl` validam contra os schemas, com teste em `tests/test_gold.py`.
2. 50 campanhas e 20 distratores, com as cotas da seção 4 cumpridas ou o déficit justificado no `README.md`.
3. Split 30/20 por campanha, sem nenhuma mensagem dividida entre splits (teste).
4. Nenhum `text` com mais de 600 caracteres e nenhum HTML (teste com regex `<[a-zA-Z]`). Para C2, `text` igual ao título do RSS.
5. Para toda mensagem, `observed_at` <= o instante da captura usada, e `first_seen_at` da campanha = mínimo dos `observed_at` das evidências (teste).
6. `preditor.gold.eval` roda com a regex T07a e gera o relatório `dev`/`test` com IC.
7. Status `gold_provisional` em todas as linhas até a conferência. `review.md` gerado para Aurimar.
8. Entrega e evidência registradas em `TASKS.md`.

## 9. Divisão de trabalho sugerida

- Programador: `scripts/gold_candidates.py`, schemas, `tests/test_gold.py`, `preditor.gold.eval`.
- Anotador (agente, papel a definir pelo Maestro): seleção e anotação provisória, `review.md`.
- Planejador: revisa a amostragem, o vazamento de rótulo em `expected` e as métricas.
- Aurimar: conferência e passagem para `gold_verified`.

## 10. Composição das 50 campanhas (universo real em 2026-10-14)

Universo: os 172 `raw_message` do backfill (PR #36, banco `preditor_p2`): Passageiro de Primeira 144, Melhores Cartões 28, mais 20 títulos do RSS vivo do Pontos pra Voar. O quadro de candidatas vem das sentenças do corpo do artigo (`article.snippets`), agrupadas pela chave do glossário (±3 dias). **O extrator só gera candidatas; o `expected` é anotado a partir do texto.**

| Bloco | Campanhas | Seleção | Status das cotas da seção 4 |
|---|---|---|---|
| A. livelo→smiles `transfer_bonus` | **todas as ~28 disponíveis** (2018-02 a 2025-06) | todas, sem sorteio | cota 30: déficit de ~2 |
| B. outros pares, incluindo os ~10 smiles→livelo (suspeitos de direção invertida) e as mensagens sem direção identificada | **22** | sorteio estratificado por ano (`seed=20261013`), priorizando 2025–2026 | cota 10: OK |
| C. distratores | **20** | entre as 36 mensagens sem sentença de oferta | OK |

Déficits já conhecidos, a registrar no `data/gold/README.md` sem inventar casos:
- `purchase_discount` (cota 4) e `boosted_accrual` (cota 3): **0 no universo**, porque o filtro CDX por slug `livelo|smiles` não pega esses posts. A recoleta precisa de slugs como "compra-de-pontos" e "acumule".
- Ano de 2026 (cota 8): livelo→smiles 0, outros pares ~4.
- `titulo_rss` (cota 8): o RSS vivo só tem itens de 2026-10-13. Depende do RSS arquivado (PR #36, bloqueante 4).
- Validadas (cota 20): ~12 só com PdP + MC.
- Mensagens com `published_vs_capture_gap=true` (83 de 172) **entram** no ouro com a tag `gap`. Elas servem justamente para revisar a data, mas o `expected.inicio` delas vem só do texto.

Splits: o bloco A é dividido 17 `test` / 11 `dev` e o bloco B 13 `test` / 9 `dev`, totalizando 30/20, como manda a decisão 005. Os distratores ficam 12/8.
