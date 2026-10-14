# QA cruzado T10a — API FastAPI, prediction_log e job diário (PR #25, 7772323)

Veredito: **DEVOLVIDO** (3 bloqueadores). Autor não alterado; ambiente: banco próprio `qa_t10a`, Python 3.12.

## Executado
- `pytest`: 97 passed (CI verde confirmado). Os testes de API só exercitam banco **vazio**; o job diário não tem teste.
- `docs/qa/t10a-api/attack_api.py` (saídas em `attack_output_sem_shim.txt` e `attack_output_com_shim.txt`).
  O "shim" (`QA_SHIM=1`) só remove os kwargs `segmented/segment_label` na chamada ao baseline, para continuar
  explorando depois do bloqueio B1; sem shim o job para no primeiro par.

## Bloqueadores
| # | Achado | Evidência |
|---|---|---|
| B1 | **Job diário não roda com nenhuma oferta no banco**: `predict_proba(..., segmented=, segment_label=)` → `TypeError: argumentos desconhecidos: ['segment_label','segmented']` (`baseline.predict_proba` rejeita kwargs). Só passa com banco vazio (0 pares). | `attack_output_sem_shim.txt`; `daily_predict.py:96` × `baseline.py:493` |
| B2 | **prediction_log não é idempotente sob concorrência**: a unicidade é um `SELECT` seguido de `INSERT`, sem constraint única na tabela. 6 execuções simultâneas do mesmo dia → grupos duplicados (até 9 linhas B0 por horizonte para o mesmo par). Como a tabela é append-only (trigger), a duplicata não é corrigível. Em outra rodada idêntica não reproduziu → condição de corrida real, intermitente. | `A3` nos dois outputs; `\d prediction_log` sem UNIQUE |
| B3 | **`GET /v1/prediction-log/accuracy?from=…&to=…` → 500 sempre** (`TypeError: can't compare datetime.datetime to datetime.date`: `datetime` é subclasse de `date`, `_d()` devolve o datetime). `from=ontem` também → 500 (deveria ser 4xx). Sem filtro funciona. | `A4`, `B4` |

## Desvios do contrato `docs/api-contract.md` (devolver junto)
1. **Acurácia conta janela aberta como erro**: não há filtro "resolvida" (`logged_at + h <= hoje`); logs de hoje entram com y=0 (Brier/log-loss/hit_rate enviesados para "errou"). Contrato: "já resolvidas".
2. `weekly: []` e `alerts: []` sempre; `horizon=99` devolve zeros em vez de vazio/4xx.
3. `/v1/predictions`: `segmented` sempre `false`, `segment_label` sempre `null`; `ci_low == ci_high == probability` (sem IC); `last_offer: null`, `reasons: []`. Linhas de grupos segmentados e não segmentados colidem em `prediction` (UNIQUE sem segmento): `ON CONFLICT DO NOTHING` descarta e o contador do job mente (`inserted_predictions=9`, 6 linhas gravadas).
4. Sem predições o contrato manda `503`; a API devolve `200 {"items": []}` (e o teste afirma 200).
5. `type=xx` → 200 vazio (esperado 422); `limit=-1` → 200 descartando o último item; `limit=0` → todos.
6. `/v1/model/metrics`: `comparison` fixo em zeros ("sem dados suficientes"), `validation.folds=0`, `challenger` nunca preenchido; `trained_at` = hora do job (campeão "daily-job" criado pelo job com `trained_at=now`, mesmo em banco vazio — A0).
7. `/v1/source-health`: `kind` fixo `rss`; `status` só `ok|degraded`; `items_new_24h == items_new_7d`; `last_item_at`/`robots_hash` nulos.
8. `/docs` e `/openapi.json` abertos sem chave (200).
9. Rate limit: contador por **qualquer** string de chave (inclusive inválida) sem expurgo → memória cresce sem limite; limite por IP usa `request.client.host` (atrás do Caddy = IP único do proxy). Só roda quando há header `X-API-Key`.

## O que passou
- Auth: 401 sem chave, 403 inválida, comparação em tempo constante; CORS só GET; startup recusa sem `PREDITOR_API_KEY`/`DATABASE_URL`.
- Re-execução sequencial (mesmo `as_of`): `inserted_logs` 9 → 0, `prediction_log` permanece com 9.
- `DELETE` em `prediction_log` bloqueado pelo trigger.
- Sem vazamento: probabilidade idêntica com/sem oferta futura (start > as_of) e com `first_seen_at > as_of` (A5/A5b).

## Para reteste
B1–B3 corrigidos + teste do job com ofertas reais (≥1 par b0 e ≥1 b1), UNIQUE em `prediction_log (model_version, origin, destination, event_type, horizon_days, (logged_at::date))` ou `INSERT … ON CONFLICT`, e testes de `from/to`.
