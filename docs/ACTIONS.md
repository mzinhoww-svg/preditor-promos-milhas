# Ações externas dos agentes

| Data | Responsável | Ação |
|---|---|---|
| 2026-10-13 | orquestrador | Leitura da nota de chaves e consulta de servidores na LetsCloud (somente leitura) |
| 2026-10-13 | orquestrador | Tentativa de SSH na VPS com chaves locais: negada, nada alterado |
| 2026-10-13 | orquestrador | Repositório `preditor-promos-milhas` criado na conta mzinhoww-svg (público) |
| 2026-10-14 | Programador 2 | Backfill Wayback Livelo→Smiles (branch feat/backfill-livelo-smiles, banco preditor_p2): robots.txt checado, 1 req/10 s, User-Agent identificado, sem LLM pago |

### Resultado do backfill, ciclo 3 (2026-10-14, banco `preditor_p2`, head 0005)

Base: **1.239 `raw_message`** (passageirodeprimeira.com 314, melhorescartoes.com.br 28, pontospravoar.com 897 só título/data/link). 177 com `published_vs_capture_gap`. 66 ofertas.

**Portão livelo→smiles `transfer_bonus`** (mínimo 25 por par/tipo, decisão 004):

| Critério | Meta | Medido | Status |
|---|---|---|---|
| Campanhas | ≥ 25 | **54** (27 utilizáveis sem só-gap) | atende **só para o B1 no job** (27 ≥ 25); **não** para C1×B1 |
| Campanhas no treino do walk-forward (purge 30) | ≥ 25 | **23** | **reprova**: `keep_champion` por dados insuficientes |
| Validadas (≥ 2 fontes) | relevante | **7 (13%)**; 4 delas sem gap | fraco |
| Meses distintos (2020-02 a 2026-03) | ≥ 24 | **47** | atende |
| Últimos 24 meses (desde 2024-10-14) | ≥ 24 meses | 12 campanhas em 10 meses; nenhuma depois de 2026-03 | **não atende** |
| Sem gap (utilizáveis antes da revisão manual) | — | **27 de 54** | metade |
| Início inferido (`start_inferred`) | — | 92 de 111 evidências | ver ressalva |

Outros pares/tipos: livelo→latam_pass 5, esfera→smiles 3, smiles→esfera 2, esfera→azul_fidelidade 1, livelo→esfera 1 (todos `transfer_bonus`; nenhum `purchase_discount`/`boosted_accrual`). Nenhum atinge 25.

**Cobertura contra o conjunto de ouro** (49 campanhas livelo→smiles): 47/49 encontradas (início ±3 dias) e 45/49 com bônus correto. Split dev da extração: 28/28 encontradas, direção e bônus 100%, fim 79%, 0 falso positivo; split test (só reportado): 47/47, fim 70%, 1 falso positivo em 12.

**Mudanças desde o 62f0602 (12 → 66 ofertas):** extração só do corpo do artigo, frase de validade junto do bônus, direção "A Smiles oferece … transferências da Livelo", data relativa "(DD)", `start_inferred` conforme spec §3.1, prorrogações fundidas (3). Descartadas como falso-positivo na primeira reextração: 10 das 11 ofertas do 62f0602 (card de outro programa, CSS, anúncio de hotel, direção invertida).

**Ressalvas honestas**
- `start_inferred=true` em 92 de 111 evidências: o início é a data em que vimos a oferta, não a data anunciada.
- Metade das campanhas depende de `published_time` anterior à captura em mais de 7 dias; ficam fora de treino e avaliação até revisão manual (`gap_only`).
- A 2ª fonte (Pontos pra Voar) só valida 0 campanhas hoje: o RSS arquivado `/feed/` rendeu 44 capturas (a cada 14 dias) e 880 itens, mas títulos sem data/validade não viram oferta; `/tag/livelo/feed/` não tem capturas na CDX. As 7 validadas são Passageiro de Primeira + Melhores Cartões.

**Não coletado**
- passageirodeprimeira.com: 9.750 URLs candidatas (slug `livelo` OU `smiles`); baixadas 316 por prioridade de slug (a 1 req/10 s, as demais custariam ~26 h). 21 falhas após 3 tentativas.
- melhorescartoes.com.br: 60 candidatas; 28 baixadas, 32 falhas; a ampliação do slug não foi listada (12 mil capturas na CDX, sem ganho esperado).
- Pontos pra Voar: 120 URLs só listadas; corpo nunca baixado (decisão 002).
- Buraco recente: nenhuma campanha livelo→smiles depois de 2026-03-11, nem em 2025-07 a 2026-02 além de 9.
- Fontes além das 3 configuradas e `purchase_discount`/`boosted_accrual` não foram tentados.
- Gold ainda é `gold_provisional`; revisão humana pendente.

Resíduo de teste (`raw_message` id=1) removido do `preditor_p2`; `tests/conftest.py` protege o banco.

### Listener recorrente de feeds (feat/feed-listener)

`python -m preditor.jobs.feed_listener --once` (agendar por cron, ex.: a cada 30 min): para cada fonte, robots fail-closed (indisponível ⇒ fonte pulada e `source_health.alert`), 1 req/10 s por domínio, item já conhecido (URL em `raw_message`) não é buscado de novo. Pontos pra Voar: só título/data/link; Passageiro de Primeira e Melhores Cartões: artigo integral só de URLs liberadas pelo robots. Cada item vira `raw_message` (com `published_at` e `published_vs_capture_gap` > 7 dias), passa pelo extrator e, havendo oferta nova, dispara `run_daily`. `source_health` registra a coleta; `GET /v1/source-health` agora devolve `last_success_at`, `last_item_at`, `robots_hash` e `status` (`degraded` com 1+ falha seguida, `error` com 3+, `stale` com 7 dias sem item).
### Follow-up do PR #36 (feat/backfill-followup)

- **Portão corrigido:** "atende" vale para o B1 no job (27 utilizáveis), não para a decisão C1×B1 (23 no treino com purge 30 < 25). O B1 segue em produção; o C1 só tem chance com revisão manual das campanhas só-gap ou mais coleta.
- `records.load_offer_records`: `first_seen_at` calculado só pelas evidências sem gap (11 ofertas mistas); não expõe `validated`, `n_sources` nem `weight` (estado final, sem versão point-in-time); teste garante que `model.py`, `baseline.py` e `walkforward.py` não os leem.
- `recompute_gap` não zera mais `published_at` de títulos de RSS (897 linhas do Pontos pra Voar ficaram com `published_at` nulo; `--rss-archive` reexecutado).
- Extrator: "inclusive Livelo e Esfera – para a Smiles" → livelo→smiles; "exceto Esfera" não vira origem/destino; "milhas bônus"/"pontos bônus" contam como bônus (ofertas LATAM Pass tinham bônus nulo).
- Testes de API passam também em banco populado (limpam `offer_evidence` e `source_health`).

**Reprocesso após o follow-up (preditor_p2, head 0005):** 1.239 brutas → 64 ofertas (66 antes; 8 descartadas, entre elas livelo→esfera e smiles→esfera inválidas e 6 de bônus nulo corrigidos). livelo→smiles `transfer_bonus` 55 (7 validadas, 47 meses, 27 sem só-gap, 1 sem bônus), livelo→latam_pass 5, esfera→smiles 3, esfera→azul_fidelidade 1. `published_at` preenchido em 877 de 897 títulos do Pontos pra Voar (0 com gap).

**Ajustes do listener (antes do cron):** URL do link normalizada como no backfill (sem `utm_*`/query, sem `www.`, esquema único; `canonical_url` na checagem de "já coletado", grava `https` sem query); teto de 200 req/dia por domínio e pausa de 1 h após 429/503, persistidos em `data/raw/feed_listener_state.json` (status `daily_cap_reached`/`paused`); `GET /v1/source-health` compara `robots_hash` com o anterior (`robots_changed`).

**Cron (documentado, NÃO agendado em produção):**

```
*/30 * * * * cd /caminho/preditor-promos-milhas && set -a && . ./.env && set +a && uv run python -m preditor.jobs.feed_listener --once >> logs/feed_listener.log 2>&1
```

Frequência de 30 min; sai com código 1 se alguma fonte falhar por robots/feed (alerta em `source_health`). Antes de agendar: confirmar `DATABASE_URL` da VPS e criar `logs/`.

### Fluxo ponta a ponta local (feat/run-e2e-local, 2026-10-14)

**Premissa corrigida:** o banco `preditor` (127.0.0.1:5432) estava **vazio** (sem tabelas, sem `alembic_version`); o backfill reprocessado vivia no `preditor_p2` (head 0005, 1.239 `raw_message`, 64 ofertas). Para não mexer no banco do Programador 2, criei `preditor_e2e` com `CREATE DATABASE preditor_e2e TEMPLATE preditor_p2` e migrei: `alembic upgrade head` → **0008**. Nada foi gravado em produção/VPS; o `STOP` não existe na raiz.

**Comandos exatos** (o pacote não está instalado no `.venv`; sem `PYTHONPATH=src` o `-m preditor...` dá `No module named 'preditor'`; com `uv run` funciona):

```
export DATABASE_URL=postgresql+psycopg://<usuario>:<senha>@127.0.0.1:5432/preditor_e2e
export PYTHONPATH=src
.venv/bin/alembic upgrade head
.venv/bin/python -m preditor.jobs.daily_predict daily          # as_of = hoje (2026-10-14)
.venv/bin/python -m preditor.jobs.daily_predict daily --as-of AAAA-MM-DD   # retroativo
```

Não existe comando "resolver": a resolução é feita na leitura (`GET /v1/prediction-log/accuracy`): uma linha de `prediction_log` conta quando `logged_at + horizonte ≤ hoje`; acerto = existe oferta (não só-gap) do par com início em `(logged_at, logged_at + h]`.

**Execução de hoje (as_of 2026-10-14):** 3 pares × 3 horizontes = **9 predições e 9 linhas de log, todas B0** (`n_b0=3`, `n_b1=0`). Resolvidas: **0** (nenhuma janela vencida, é a primeira execução). Alertas: 0.

| Par (transfer_bonus) | Campanhas (não só-gap, não segmentadas) | Método | P(7d) / P(15d) / P(30d) |
|---|---|---|---|
| livelo→smiles | 23 | B0 (< 25) | 0,113 / 0,227 / 0,402 |
| livelo→latam_pass | 3 | B0 | 0,029 / 0,061 / 0,119 |
| esfera→azul_fidelidade | 1 (só segmentada) | B0 | 0,021 / 0,044 / 0,087 |

**B0 × B1:** B1 **não rodou para nenhum par** — o par principal tem 23 campanhas, abaixo do mínimo de 25. Logo não há comparação B0 × B1 possível; todo o log é B0.

**Erro encontrado e corrigido (TDD, `tests/test_e2e_segment_collision.py`):** `prediction`/`prediction_log` não têm coluna de segmento; os grupos segmentados (`clube`, `segmentado`, `bonus_conflitante`) do mesmo par colidiam com o principal no `ON CONFLICT DO NOTHING` e **o primeiro a chegar ganhava**. Na 1ª execução, livelo→smiles saiu com a série `clube` (3 campanhas, P(30d)=0,081) em vez da principal (23, P(30d)=0,402). Além disso, `inserted_predictions` contava conflitos como inseridos (15 reportados, 9 gravadas). Agora o job grava **uma série por (origem, destino, tipo)**: a de mais campanhas (empate: não segmentada, depois rótulo) e conta só linhas realmente inseridas. Ressalva: pares só com ofertas segmentadas (esfera→azul) ainda geram predição com a série segmentada.

**Execuções retroativas (só para ter janelas vencidas):** `daily --as-of` semanal de 2025-01-05 a 2026-09-13 (89 execuções), point-in-time (só ofertas com `first_seen_at ≤ as_of`). Total do log: **672 linhas** (224 por horizonte), todas B0; **221 resolvidas por horizonte** (3 pares). **Atenção:** essas linhas têm `logged_at` retroativo — são backtest, não previsão prospectiva; **não** executar no banco de produção, onde o log precisa ser só de predições feitas na hora.

**Acurácia (`/v1/prediction-log/accuracy`), n = 221 por horizonte, B0 apenas:**

| Horizonte | n | Taxa de acerto (ocorreu oferta) | Brier | Log-loss |
|---|---|---|---|---|
| 7 d | 221 | 0,050 | 0,051 | 0,204 |
| 15 d | 221 | 0,113 | 0,104 | 0,353 |
| 30 d | 221 | 0,208 | 0,167 | 0,522 |

**Leitura honesta:** n é pequeno e **não independente** — são 3 pares, janelas semanais que se sobrepõem (30 d sobrepõe ~4 vezes) e 14 ofertas válidas desde 2025-01. Por par (30 d): livelo→smiles 89 linhas, 36 acertos, Brier 0,244 (constante com a taxa média dá 0,279); livelo→latam_pass 89, 10 acertos, Brier 0,111 (≈ constante 0,109); esfera→azul 43, 0 acertos, Brier 0,122 (constante 0,043: pior). **Não há base para afirmar acurácia do modelo**; o que se mede é só que o fluxo roda. O acompanhamento real começa quando o job passar a rodar todo dia.

**Outros achados (não corrigidos, decisão de modelagem — Planejador):**
1. **B0 explode com n=1:** taxa = peso / dias desde a 1ª campanha. esfera→azul (1 campanha segmentada) deu P(30d)=0,996 cinco dias após a campanha e gerou os **3 alertas** da tabela `alert` (limiar 0,5), todos ruído. Sugestão: mínimo de campanhas/dias de janela para emitir probabilidade ou alerta.
2. `/v1/prediction-log/accuracy` com n=0 devolve `hit_rate`/`brier`/`log_loss` = 0,0 (parece perfeito); o campo `n` é o único aviso. `weekly` sempre `[]`. Não alterei por causa do contrato do dashboard.
3. `GET /v1/prediction-log/accuracy` não separa B0 × B1; hoje só há B0, então não distorce.
4. `run_accuracy` no job ignora `engine` (código morto `if False`).
