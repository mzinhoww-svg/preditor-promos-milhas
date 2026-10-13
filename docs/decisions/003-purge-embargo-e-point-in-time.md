# 003 Purge, embargo de rotulo e regra point-in-time no walk-forward

Data: 2026-10-13. Decisao do orquestrador, com base na revisao de vazamento do Planejador (PR #3, rodada 2).

## Opcoes
1. Purge fixo de 15 dias (briefing original). Simples, mas com horizonte de 30 dias o rotulo do ultimo dia de treino enxerga o periodo de teste.
2. Exigir purge_days >= max(horizontes). Sem logica extra, mais conservador.
3. Embargo de rotulo: manter 15 dias de purge e excluir do treino todo exemplo cujo rotulo (t+1..t+h) cruza o cutoff.

## Revisao (rodada 3 da revisao de vazamento)
O codigo do T08a implementou a opcao 2 (purge_days >= max(horizons)), mais simples e mais conservadora. O orquestrador ratifica a opcao 2 e substitui a escolha abaixo: purge efetivo de 30 dias (o horizonte maximo), em vez dos 15 do briefing, porque com horizonte de 30 dias um purge de 15 deixa o rotulo enxergar o teste. Embargo de rotulo fica como melhoria futura. Registrar na entrega final; Aurimar pode reverter.

## Escolha (original, substituida)
Opcao 3 com piso: o purge default e 15 dias (briefing), o embargo de rotulo exclui qualquer exemplo de treino cuja janela de rotulo ultrapasse `cutoff`, e `purge_days >= max(horizons)` NAO e exigido porque o embargo cobre o caso. O cutoff e contado a partir do INICIO da janela de teste: `cutoff = test_start - purge_days`.

## Regras point-in-time (valem para toda feature e para o split)
- Uma oferta so e conhecida em `t` se `first_seen_at <= cutoff`. `first_seen_at` ausente ou invalido: o registro e excluido (falha fechada), nunca tratado como conhecido.
- `as_of` do tipo `date` vira inicio do dia (`time.min`); tudo e normalizado para `America/Sao_Paulo` na entrada, evitando mistura de fuso.
- `validated`, `n_sources` e `weight` sao estado final e nao podem alimentar o treino em `t`. Ate existir reconstrucao point-in-time a partir de `offer_evidence`, o peso e 1,0 no baseline.
- `expanding=True` deve ser respeitado (janela de treino expansiva); `as_of` desconhecido em `fit`/`predict` levanta erro.
