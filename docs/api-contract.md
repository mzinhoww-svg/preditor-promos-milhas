# Contrato da API do dashboard (v1)

Data: 2026-10-13. Status: proposto pela T09a; a API ainda não existe. O dashboard consome
`dashboard/mock/*.json` com exatamente este formato e troca para a API real por variável de
ambiente, sem mudar a interface de dados.

## Transporte e autenticação

- Base: `https://<host-da-vps>/v1` (HTTPS obrigatório; Caddy termina TLS).
- Todas as rotas são `GET` e devolvem `application/json; charset=utf-8`.
- Autenticação: header `X-API-Key: <chave>`. A chave vive só em variável de ambiente
  (`PREDITOR_API_KEY` no servidor Next.js / na Vercel). Nunca no código, nunca no cliente
  (as chamadas acontecem em Server Components ou Route Handlers).
- Erros: `401` sem chave, `403` chave inválida, `429` limite excedido, `503` modelo sem
  predições publicadas. Corpo de erro: `{"error": {"code": "string", "message": "string"}}`.
- Datas e instantes em ISO 8601 UTC (`2026-10-13T06:00:00Z`). Percentuais como número
  inteiro ou decimal em pontos percentuais (`90` = 90% de bônus). Probabilidades em `[0, 1]`.
- Idioma dos textos (`reason`, `label`, `message`): português.

Variáveis do dashboard:

| Variável | Onde | Uso |
|---|---|---|
| `PREDITOR_API_BASE_URL` | servidor | base `https://host/v1`; ausente = modo mock |
| `PREDITOR_API_KEY` | servidor | valor do header `X-API-Key` |
| `PREDITOR_DATA_SOURCE` | servidor | `mock` (padrão) ou `api`; força a origem |

## GET /v1/predictions

Lista ranqueada das próximas promoções prováveis, já ordenada por `rank`. Uma linha por
(origem, destino, tipo); as três janelas vêm juntas na mesma linha.

Query opcional: `type` (`transfer_bonus|purchase_discount|boosted_accrual`), `limit` (padrão 50).

```json
{
  "generated_at": "2026-10-13T06:00:00Z",
  "model": { "run_id": "mr_2026-10-13", "name": "B1", "version": "1.3.0", "role": "champion" },
  "items": [
    {
      "rank": 1,
      "pair": { "origin": "Livelo", "destination": "Smiles" },
      "type": "transfer_bonus",
      "segmented": false,
      "segment_label": null,
      "windows": {
        "7":  { "probability": 0.62, "ci_low": 0.55, "ci_high": 0.69 },
        "15": { "probability": 0.81, "ci_low": 0.75, "ci_high": 0.86 },
        "30": { "probability": 0.94, "ci_low": 0.90, "ci_high": 0.97 }
      },
      "bonus_pct": { "p25": 70, "p50": 80, "p75": 100 },
      "last_offer": { "start_at": "2026-09-12", "end_at": "2026-09-18", "bonus_pct": 80, "days_since": 31 },
      "reasons": [
        { "kind": "days_since_last", "label": "31 dias desde a última oferta", "detail": "intervalo mediano histórico: 27 dias", "weight": 0.42 },
        { "kind": "month", "label": "Outubro concentra 11% das ofertas do par", "detail": "3º mês mais ativo", "weight": 0.21 },
        { "kind": "sibling_pairs", "label": "Livelo → LATAM Pass ativo desde 10/10", "detail": "pares irmãos costumam abrir em até 5 dias", "weight": 0.18 }
      ]
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
| `windows.*.ci_low`, `ci_high` | number 0–1 | intervalo (bootstrap em blocos) |
| `bonus_pct.p25/p50/p75` | number | faixa prevista do bônus em pontos percentuais |
| `last_offer` | objeto\|null | última oferta conhecida e `days_since` até `generated_at` |
| `reasons[]` | lista | `kind` em `days_since_last`, `month`, `sibling_pairs`, `source_signal`, `other`; `weight` soma ≤ 1 |

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
  "challenger": {
    "name": "C1", "version": "0.4.2", "trained_at": "2026-10-06T03:40:00Z",
    "horizons": [7, 15, 30],
    "validation": { "...": "mesmo formato do campeão" },
    "production": null
  },
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

`comparison.decision` ∈ `keep_champion | promote_challenger | insufficient_data`.
`reliability.bins` são os pontos da curva de confiabilidade (previsto × observado) do campeão.
`production` é `null` quando o modelo nunca serviu predições.

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
`kind` ∈ `rss | html | wayback | official`.

## GET /v1/prediction-log/accuracy

Acurácia real das predições registradas em `prediction_log` (só inserção), já resolvidas
contra o que aconteceu. Alimenta a parte "produção" da tela de métricas e os alertas de drift.

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

`alerts[].severity` ∈ `info | warning | critical`; `kind` ∈ `drift | source | budget | pipeline | model`.
O dashboard junta esses alertas com os derivados de `source-health` (`status != ok`) na tela de alertas.

## Versionamento

Mudança incompatível vira `/v2`; campos novos podem ser acrescentados sem quebrar. O dashboard
ignora campos desconhecidos.
