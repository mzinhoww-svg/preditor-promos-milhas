# Portão de viabilidade e campeão × desafiante (relatório para o STATUS final)

Data: 2026-10-14. Autor: Planejador. Fonte dos números: banco local `preditor_p2` (backfill dos PRs #36 e #48), lido **só com SELECT**. A avaliação C1 × B1 rodou numa **cópia descartável** (`CREATE DATABASE … TEMPLATE preditor_p2`), migrada até `0008` e apagada depois. Código: `main` em `3a52046`.

## 1. Resumo

- **O dado é real, mas pouco.** O par livelo→smiles `transfer_bonus` tem 55 campanhas no total e **27 utilizáveis**. Na janela de treino do walk-forward só cabem **23**, abaixo do mínimo de **25** exigido para decidir C1 × B1.
- **Decisão: `keep_champion`.** O B1 (hazard empírico) segue em produção para o par livelo→smiles. Os demais pares ficam em B0 (taxa-base).
- **Com estes dados, o C1 perde para o B1** em Brier e em log-loss, com IC excluindo zero **a favor do B1**, e não passa no teste de calibração. Não foi medido como o C1 se sairia com mais campanhas (cada dobra treina com 3 a 29 registros).
- **Produção:** ainda não existe acurácia de produção: `prediction_log` está vazio no `preditor_p2` (n = 0).

## 2. Base coletada

| Fonte | `raw_message` | Com gap de publicação (> 7 d antes da captura) | Período de `observed_at`¹ |
|---|---|---|---|
| passageirodeprimeira.com | 314 | 169 | 2015-02 a 2026-10 |
| www.melhorescartoes.com.br | 28 | 8 | 2021-02 a 2025-03 |
| pontospravoar.com (só título, data e link; decisão 002) | 897 | 0 | 2023-08 a 2026-10 |
| **Total** | **1.239** | **177** | |

¹ `observed_at` é o mínimo entre a data de publicação e a captura Wayback, ou seja, a data das **páginas**, não a cobertura de campanhas. Algumas páginas antigas (desde 2015) não geram campanha. As campanhas extraídas começam em **2020-02** (seção 3).

## 3. Portão de viabilidade, por par e tipo

"Utilizáveis" exclui as ofertas cujas evidências são **todas** de gap (`gap_only`), que ficam fora de treino e avaliação até a revisão manual. "Últimos 24 meses" conta campanhas desde 2024-10-14.

| Par | Tipo | Campanhas | Validadas (≥ 2 fontes) | Meses distintos | Utilizáveis | Últimos 24 meses | Período |
|---|---|---|---|---|---|---|---|
| livelo→smiles | transfer_bonus | **55** | 7 (13%) | 47 | **27** | 12 | 2020-02 a 2026-03 |
| livelo→latam_pass | transfer_bonus | 5 | 0 | 5 | 3 | 4 | 2020-08 a 2025-09 |
| esfera→smiles | transfer_bonus | 3 | 0 | 3 | 0 | 1 | 2023-08 a 2025-03 |
| esfera→azul_fidelidade | transfer_bonus | 1 | 0 | 1 | 1 | 1 | 2025-11 |
| (qualquer) | purchase_discount / boosted_accrual | 0 | — | — | — | — | não coletado |

| Critério (decisão 004) | Meta | livelo→smiles | Situação |
|---|---|---|---|
| Campanhas para o B1 no job | ≥ 25 utilizáveis | 27 | **atende** (por pouco) |
| Campanhas no treino para decidir C1 × B1 | ≥ 25 | **23** | **não atende** |
| Meses distintos | ≥ 24 | 47 | atende |
| Cobertura recente (24 meses) | contínua | 12 campanhas, nenhuma depois de 2026-03-11 | **não atende** |
| Validação por 2ª fonte | relevante | 13% | fraca |

## 4. Campeão × desafiante (C1 × B1) com dado real

`run_champion_challenger(exclude_gap_only(load_offer_records(...)), data_source="real")`: walk-forward com purge de 30 dias, horizontes 7/15/30, bootstrap em blocos de semana ISO (500 reamostragens).

| Item | Valor |
|---|---|
| Dobras | 10 (cortes de 2023-09-24 a 2025-12-20; registros no treino de 3 a 29) |
| Linhas avaliadas (par, tipo, t, h) | 3.471, das quais 651 positivas |
| Campanhas reais no treino (dedup ±3 d) | livelo→smiles **23**, livelo→latam_pass 3, esfera→azul_fidelidade 1 |
| Brier B1 / C1 | **0,125** / 0,306 |
| Log-loss B1 / C1 | **0,376** / 1,261 |
| IC 95% Δ Brier (B1 − C1) | [−0,239; −0,126] (a favor do B1) |
| IC 95% Δ log-loss (B1 − C1) | [−1,146; −0,630] (a favor do B1) |
| C1 calibrado | não |
| **Decisão** | **`keep_champion`**: dados insuficientes (23 < 25); C1 não é menor em Brier nem em log-loss; IC não favorece o C1; C1 não calibrado |

Leitura: o portão de dados já impede a promoção. Mesmo sem ele, com estes dados o C1 (LightGBM) fica muito pior que o B1, coerente com poucas campanhas para um modelo global. As métricas do B1 vêm de **validação histórica**, não de produção.

## 5. Acurácia em produção

| Fonte | n resolvidas | Brier | Acerto |
|---|---|---|---|
| `prediction_log` do `preditor_p2` | **0** | — | — |

Não há predição de produção resolvida. Os números que aparecem nos testes do QA (por exemplo, Brier 0,319 com 9 resolvidas) vêm de **bancos de teste com replay** de `as_of` passado. Eles validam a mecânica, **não são acurácia de produção** e não devem ir para o STATUS como tal. A primeira métrica real exige o job diário rodando e janelas de 7, 15 e 30 dias fechadas.

## 6. Limites (para o STATUS)

- **Sintético × real.** A decisão da seção 4 é com dado **real** (`data_source="real"` declarado pelo chamador; derivá-lo da origem continua pendente desde o #27). O relatório antigo `docs/reports/t08b-champion-decision.md` foi feito com dado sintético e não vale como resultado.
- **Metade das campanhas depende de data de publicação suspeita:** 28 das 55 livelo→smiles são só-gap. Revisá-las à mão pode levar o treino a ≥ 25.
- **Buraco recente:** nenhuma campanha livelo→smiles depois de 2026-03-11, e só 12 nos últimos 24 meses. O backfill do PdP baixou 316 de 9.750 URLs candidatas (314 gravadas como `raw_message`), e o listener (#49) passa a cobrir daqui em diante.
- **Segunda fonte fraca:** o Pontos pra Voar (só título, decisão 002) validou 0 campanhas, e todas as 7 validadas são PdP + MC.
- **Tipos ausentes:** não há nenhuma campanha de `purchase_discount` nem de `boosted_accrual`.
- **Extrator e conjunto de ouro:** a medida contra o ouro é provisória (`gold_provisional`, aguarda conferência de Aurimar). No split dev, a pipeline acha 28/28 campanhas, com direção e bônus 100% e fim 79%.
- **Datas inferidas:** 90 de 109 evidências têm início inferido (`start_inferred`, data em que a oferta foi vista).

## 7. O que muda o resultado

1. Conferência humana das campanhas só-gap (o ouro tem 23 delas; a sobreposição ainda não foi cruzada).
2. Completar o backfill do PdP de 2025-07 em diante, e o listener rodando.
3. Rodar de novo este relatório; a decisão só muda com ≥ 25 campanhas no treino **e** com o C1 vencendo o B1 com IC.

Reprodução: `load_offer_records` → `exclude_gap_only` → `run_champion_challenger(..., data_source="real", n_boot=500)` sobre uma cópia de `preditor_p2`.
