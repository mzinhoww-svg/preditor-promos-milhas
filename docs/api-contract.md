# Contrato da API do dashboard (v1)

Data: 2026-10-14. Status: **implementado** pela T10a (`/predictions`, `/model/metrics`,
`/source-health`, `/prediction-log/accuracy`), **em revisão** na T10b (`/alerts`,
`/predictions/{origin}/{destination}/explanation`, PR #50) e **proposto** pelo dashboard
(`/status`, campos `method` e `n_campaigns` em `/predictions`). O dashboard consome
`dashboard/mock/*.json` com exatamente este formato e troca para a API real por variável
de ambiente, sem mudar a interface de dados.

## Transporte e autenticação

- Base: `https://<host-da-vps>/v1` (HTTPS obrigatório; Caddy termina TLS). Enquanto a VPS
  não tem host público, o dashboard fica em dados simulados (ver `docs/deploy-vercel.md`).
- Todas as rotas são `GET` e devolvem `application/json; charset=utf-8`.
- Autenticação: header `X-API-Key: <chave>`. A chave vive só em variável de ambiente
  (`PREDITOR_API_KEY` no servidor Next.js / na Vercel). Nunca no código, nunca no cliente
  (as chamadas acontecem em Server Components e na rota `/api/explanation`).
- Limite: 60 req/min por chave e 120 por IP (`RATE_LIMIT_PER_MINUTE_*` na API). O dashboard
  faz 3 a 4 chamadas por tela, sem cache, e carrega a explicação de cada item só quando o
  leitor abre o bloco.
- Erros: `401` sem chave, `403` chave inválida, `429` limite excedido, `503` API sem chave
  configurada. Corpo de erro: `{"error": {"code": "string", "message": "string"}}`.
- Datas e instantes em ISO 8601 UTC (`2026-10-13T06:00:00Z`). O dashboard exige calendário
  válido (dia existente no mês, hora/minuto/segundo na faixa); `2026-02-31` é rejeitado,
  não rolado para março. Percentuais como número inteiro ou decimal em pontos percentuais
  (`90` = 90% de bônus). Probabilidades em `[0, 1]`.
- Tolerância do dashboard: item, alerta, fonte, semana de `weekly` ou registro de `/alerts`
  malformados são descartados e contados na tela; `validation.folds` que não for inteiro
  positivo, intervalos de confiança ausentes, `bonus_pct` sem histórico, contadores de fonte
  e `period` sem dados viram `null` em vez de derrubar a tela. Endpoint opcional ausente
  (`404`) vira aviso "a API ainda não expõe".
- Fallback: com a API configurada, qualquer falha (rede, timeout de 8 s, HTTP, JSON,
  validação) faz a tela cair para os dados simulados com um aviso em destaque e o motivo.
- Sem cache de dados: cada requisição ao dashboard consulta a API (`cache: "no-store"`); a
  tela mostra "API consultada há X" e "dados gerados há Y", com selo "dado velho" acima de
  36 h. Item com janela malformada fica na lista com a janela marcada como inválida; só sai
  se as três janelas forem inválidas. `comparison` zerada com nota "sem dados suficientes"
  (ou `decision: insufficient_data`) aparece como "sem dados", não como Δ 0,000.
- Idioma dos textos (`reason`, `label`, `message`): português.

Variáveis do dashboard:

| Variável | Onde | Uso |
|---|---|---|
| `PREDITOR_API_BASE_URL` | servidor | base `https://host/v1`; ausente = modo simulado |
| `NEXT_PUBLIC_API_BASE_URL` | servidor | alternativa à anterior (também lida só no servidor; a URL base não é segredo) |
| `PREDITOR_API_KEY` | servidor | valor do header `X-API-Key`; **nunca** com prefixo `NEXT_PUBLIC_` |
| `PREDITOR_DATA_SOURCE` | servidor | `mock` força dados simulados; `api` força a API; ausente = API se houver base |

## GET /v1/predictions

Lista ranqueada das próximas promoções prováveis, já ordenada por `rank`. Uma linha por
(origem, destino, tipo); as três janelas vêm juntas na mesma linha.

`model` é o run que **gerou** estas predições (`role`: `daily` para o job diário, `champion` se o
run for o campeão decidido); `champion` é o campeão da decisão campeão × desafiante (`null` se
nunca houve decisão). Cada item traz `model_run_id` do run que o gerou.

Query opcional: `type` (`transfer_bonus|purchase_discount|boosted_accrual`), `limit` (padrão 50).

```json
{
  "generated_at": "2026-10-13T06:00:00Z",
  "model": { "run_id": "mr_41", "name": "B1", "version": "1.0.0", "role": "daily" },
  "champion": { "run_id": "mr_7", "name": "C1", "version": "0.4.2", "role": "champion" },
  "items": [
    {
      "rank": 1,
      "pair": { "origin": "Livelo", "destination": "Smiles" },
      "type": "transfer_bonus",
      "segmented": false,
      "segment_label": null,
      "windows": {
        "7":  { "probability": 0.198, "ci_low": 0.198, "ci_high": 0.198 },
        "15": { "probability": 0.376, "ci_low": 0.376, "ci_high": 0.376 },
        "30": { "probability": 0.611, "ci_low": 0.611, "ci_high": 0.611 }
      },
      "bonus_pct": { "p25": 70, "p50": 80, "p75": 100 },
      "last_offer": null,
      "reasons": [],
      "method": "b0",
      "n_campaigns": 23
    }
  ]
}
```

Campos:

| Campo | Tipo | Observação |
|---|---|---|
| `rank` | int ≥ 1 | ordem por `windows.30.probability` desc, desempate por `windows.7` |
| `pair.origin`, `pair.destination` | string | nomes canônicos do glossário |
| `type` | enum | `transfer_bonus`, `purchase_discount`, `boosted_accrual` |
| `segmented`, `segment_label` | bool, string\|null | oferta restrita (clube, cartão) tem par próprio |
| `windows.{7,15,30}.probability` | number 0–1 | probabilidade calibrada de início da oferta na janela |
| `windows.*.ci_low`, `ci_high` | number 0–1 | intervalo (bootstrap em blocos). **Hoje a API manda igual à probabilidade**: o dashboard mostra "IC indisponível" quando `ci_low == ci_high` |
| `bonus_pct.p25/p50/p75` | number\|null | faixa prevista do bônus em pontos percentuais; `null` sem histórico |
| `last_offer` | objeto\|null | última oferta e `days_since`; **a API de hoje manda `null`** (a recência está em `/explanation`) |
| `reasons[]` | lista | `kind` em `days_since_last`, `month`, `sibling_pairs`, `source_signal`, `other`; `weight` soma ≤ 1; **a API de hoje manda `[]`** |
| `method` | `b0`\|`b1`\|ausente | **proposto**: método do item (o job já grava em `prediction.explanation.method`); evita uma chamada de explicação por item só para mostrar o selo |
| `n_campaigns` | int\|ausente | **proposto**: nº de campanhas conhecidas em `as_of` (idem) |

`model` é o run que gerou as predições (com a T10b, o run diário: `role: "daily"`); `model.name`
é `B0` se nenhum par atingiu 25 campanhas, senão `B1`. `champion` (T10b) é a referência do
campeão decidido (`is_champion`) ou `null` sem decisão; com `null` o dashboard mostra
"Modelo não decidido · servindo B0/B1 por par (X em B1, Y em B0)". As contagens por método
vêm das explicações dos primeiros 12 itens (memorizadas por 5 min no servidor) até a lista
trazer `method`.
O dashboard mostra selo só para `B0` e `B1`; qualquer outro nome (ex. `C1`) aparece como
"modelo não decidido" até `comparison.decision` em `/model/metrics` ser `promote_challenger`.

## GET /v1/predictions/{origin}/{destination}/explanation (T10b)

Fatores point-in-time gravados pelo job na predição mais recente do par. Query: `type`
(padrão `transfer_bonus`). `404` quando não há predição para o item.

```json
{
  "pair": { "origin": "Livelo", "destination": "Smiles" },
  "type": "transfer_bonus",
  "as_of": "2026-10-14",
  "windows": { "7": 0.198, "15": 0.376, "30": 0.611 },
  "factors": {
    "method": "b0",
    "probability_driven_by": "base_rate",
    "n_campaigns": 23,
    "last_campaign_start": "2026-08-03",
    "days_since_last": 72,
    "median_interval_days": 27.0,
    "min_campaigns_b1": 25
  }
}
```

O dashboard mostra "Baseado em N campanhas históricas", a última campanha e a recência,
o intervalo mediano e o motivo do método (`B1` exige `min_campaigns_b1`). Qualquer fator
ausente vira "—". A chamada sai da rota interna `/api/explanation` do dashboard (proxy
server-side, chave no servidor, parâmetros validados), só quando o leitor abre o bloco.

## GET /v1/model/metrics

Métricas do modelo em produção e do desafiante. Validação histórica (walk-forward) fica
separada da precisão real em produção (`prediction_log` conferido com o que aconteceu).

```json
{
  "generated_at": "2026-10-13T06:00:00Z",
  "champion": {
    "name": "B1", "version": "1.3.0", "trained_at": "2026-10-06T03:10:00Z",
    "horizons": [7, 15, 30],
    "validation": {
      "method": "walk-forward",
      "folds": 18, "period": { "from": "2024-01-01", "to": "2026-09-30" },
      "by_horizon": { "7": { "brier": 0.142, "log_loss": 0.447, "auc": 0.78, "ci_brier": [0.131, 0.155] }, "15": { "...": 0 }, "30": { "...": 0 } }
    },
    "production": {
      "period": { "from": "2026-09-01", "to": "2026-10-12" },
      "n_predictions": 1260, "n_resolved": 840,
      "by_horizon": { "7": { "brier": 0.151, "log_loss": 0.46, "hit_rate": 0.71, "n": 280 }, "15": { "...": 0 }, "30": { "...": 0 } }
    }
  },
  "challenger": null,
  "comparison": {
    "horizon": 30,
    "delta_brier": -0.004, "delta_log_loss": 0.011,
    "ci_delta_brier": [-0.012, 0.004],
    "decision": "keep_champion",
    "note": "C1 não vence em Brier e log-loss com IC; B1 segue em produção"
  },
  "reliability": {
    "horizon": 30,
    "bins": [ { "p_mean": 0.05, "observed": 0.04, "n": 120 }, { "p_mean": 0.15, "observed": 0.17, "n": 98 } ]
  }
}
```

`serving` é o run que gerou as predições mais recentes (pode ser o job diário B0/B1, diferente do
`champion`). `champion` é o run com `is_champion`; sem decisão, cai para `serving`.

`comparison.decision` ∈ `keep_champion | promote_challenger | insufficient_data`.
`reliability.bins` são os pontos da curva de confiabilidade (previsto × observado) do campeão.
`champion` pode ser `null` (sem campeão decidido); `serving` (T10b) é o run que serve as
predições. `reliability.is_calibrated` (proposto, padrão `false`): o dashboard só escreve
"probabilidade calibrada" com `bins` não vazios e este flag verdadeiro; até lá diz
"probabilidade estimada". `comparison` com nota de falta de dados, `insufficient_data`,
Δ e IC zerados ou IC degenerado aparece como "Não decidido: dados insuficientes (N campanhas
no treino, mínimo 25)", sem Δ nem IC.
`production` é `null` quando o modelo nunca serviu predições. **A API de hoje** devolve
`validation` vazia (`folds: 0`, `period` nulo, `by_horizon: {}`), `production: null`,
`comparison` zerado com `note: "sem dados suficientes"` e `bins: []`; o dashboard mostra os
estados vazios correspondentes e preenche a precisão em produção com
`/prediction-log/accuracy`.

## GET /v1/source-health

Saúde de cada fonte coletada (tabela `source_health`).

```json
{
  "generated_at": "2026-10-13T06:00:00Z",
  "sources": [
    {
      "source": "passageirodeprimeira.com",
      "kind": "rss",
      "status": "ok",
      "last_success_at": "2026-10-13T05:40:00Z",
      "last_item_at": "2026-10-12T22:10:00Z",
      "items_new_24h": 6, "items_new_7d": 41,
      "extraction_rate_7d": 0.93,
      "error_rate_24h": 0.0,
      "robots_hash": "sha256:4f1c…", "robots_changed": false,
      "message": null
    }
  ]
}
```

`status` ∈ `ok | degraded | stale | blocked | error`. `stale` = 7 dias sem item novo.
`kind` ∈ `rss | html | wayback | official`. `items_new_*` e `extraction_rate_7d` podem ser
`null` (fonte sem checagem bem-sucedida); o dashboard mostra "—".

## GET /v1/prediction-log/accuracy

Acurácia real das predições registradas em `prediction_log` (só inserção), já resolvidas
contra o que aconteceu. Alimenta a parte "produção" da tela de métricas.

Query opcional: `from`, `to` (datas), `horizon`.

```json
{
  "generated_at": "2026-10-13T06:00:00Z",
  "period": { "from": "2026-09-01", "to": "2026-10-12" },
  "by_horizon": {
    "7":  { "n": 280, "hit_rate": 0.71, "brier": 0.151, "log_loss": 0.46 },
    "15": { "n": 280, "hit_rate": 0.77, "brier": 0.139, "log_loss": 0.43 },
    "30": { "n": 280, "hit_rate": 0.84, "brier": 0.118, "log_loss": 0.39 }
  },
  "weekly": [
    { "week": "2026-09-01", "horizon": 30, "n": 60, "hit_rate": 0.83, "brier": 0.12 }
  ],
  "alerts": [
    {
      "id": "al_000123",
      "severity": "warning",
      "kind": "drift",
      "title": "Brier de 7 dias piorou 0,02 em duas semanas",
      "detail": "0,151 em produção contra 0,142 na validação; fora do IC.",
      "since": "2026-10-10T06:00:00Z",
      "related": { "horizon": 7, "source": null, "pair": null }
    }
  ]
}
```

`period.from` é `null` sem predições resolvidas. Janelas ausentes em `by_horizon` viram
`n = 0`. `alerts[].severity` ∈ `info | warning | critical`; `kind` ∈
`drift | source | budget | pipeline | model`. **A API de hoje** devolve `weekly: []` e
`alerts: []`. O dashboard junta esses alertas com os derivados de `source-health`
(`status != ok`) e com o STOP ativo na tela de alertas.

## GET /v1/alerts (T10b)

Cruzamentos de limiar de probabilidade registrados pelo job diário (tabela `alert`), sem
canal externo. Query: `limit` (1–500, padrão 100).

```json
{
  "generated_at": "2026-10-14T06:29:24Z",
  "items": [
    {
      "made_at": "2026-10-14T00:00:00Z",
      "pair": { "origin": "Livelo", "destination": "Smiles" },
      "type": "transfer_bonus",
      "horizon_days": 30,
      "probability": 0.611,
      "previous_probability": null,
      "threshold": 0.5
    }
  ]
}
```

## GET /v1/status (proposto pelo dashboard)

Estado de operação. Hoje o STOP é um arquivo (`STOP` na raiz ou `PREDITOR_STOP_FILE`) ou a
flag `PREDITOR_STOP=1`, conhecidos só pelo job e pelos coletores; o dashboard não tem como
saber. Proposta mínima (a API já tem `stop_requested()` em `preditor.stop`):

```json
{
  "generated_at": "2026-10-14T06:29:24Z",
  "stop": { "active": false, "source": null, "since": null },
  "last_job": { "run_at": "2026-10-14T00:00:00Z", "model_run_id": "mr_3", "status": "ok" },
  "n_campaigns_total": 56
}
```

`stop.source` ∈ `file | env | null`. `last_job` vem do `model_run` mais recente.
`n_campaigns_total` é o nº de ofertas não só-gap conhecidas em `as_of`. Enquanto a rota não
existir, o dashboard mostra "STOP: desconhecido (a API não expõe /v1/status)" e usa
`generated_at` de `/predictions` como última execução.

## Versionamento

Mudança incompatível vira `/v2`; campos novos podem ser acrescentados sem quebrar. O dashboard
ignora campos desconhecidos.
