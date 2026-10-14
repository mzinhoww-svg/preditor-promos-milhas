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

### Follow-up do PR #36 (feat/backfill-followup)

- **Portão corrigido:** "atende" vale para o B1 no job (27 utilizáveis), não para a decisão C1×B1 (23 no treino com purge 30 < 25). O B1 segue em produção; o C1 só tem chance com revisão manual das campanhas só-gap ou mais coleta.
- `records.load_offer_records`: `first_seen_at` calculado só pelas evidências sem gap (11 ofertas mistas); não expõe `validated`, `n_sources` nem `weight` (estado final, sem versão point-in-time); teste garante que `model.py`, `baseline.py` e `walkforward.py` não os leem.
- `recompute_gap` não zera mais `published_at` de títulos de RSS (897 linhas do Pontos pra Voar ficaram com `published_at` nulo; `--rss-archive` reexecutado).
- Extrator: "inclusive Livelo e Esfera – para a Smiles" → livelo→smiles; "exceto Esfera" não vira origem/destino; "milhas bônus"/"pontos bônus" contam como bônus (ofertas LATAM Pass tinham bônus nulo).
- Testes de API passam também em banco populado (limpam `offer_evidence` e `source_health`).
