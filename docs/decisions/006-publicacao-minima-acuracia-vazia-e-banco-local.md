# 006 Publicação mínima do B0, acurácia sem dados e banco local canônico

Data: 2026-10-14. Status: **aceita pelo Planejador** nos itens 1 a 3. O item 4 é proposta e depende do OK de Aurimar. Origem: primeira execução real do job (PR #65, `docs/ACTIONS.md`).

## 1. B0 com histórico mínimo
Problema: o B0 é `peso / dias desde a 1ª campanha`. Com 1 campanha de 5 dias atrás, esfera→azul deu P(30 d) = 0,996 e gerou 3 alertas de ruído.

- A. Publicar sempre (como hoje).
- B. **Exigir histórico mínimo para publicar a probabilidade e o alerta: ≥ 3 campanhas e ≥ 180 dias desde a primeira campanha conhecida em `as_of`. Abaixo disso, a predição sai com `probability = null` e `status = "historico_insuficiente"` e não gera alerta.** Escolhida.
- C. Encolher o B0 para a taxa média de todos os pares (bayesiano).

Motivo: B é simples, honesto e testável. C fica como melhoria se houver pares suficientes para estimar a taxa média. O painel mostra "histórico insuficiente (N campanhas)" no lugar de um número.

## 2. Alerta
Só gera alerta a série com probabilidade publicada (item 1). Uma mudança de método entre rodadas (B0 → B1) não conta como cruzamento de limiar no primeiro dia do novo método.

## 3. Acurácia com n = 0
`/v1/prediction-log/accuracy` devolve `n = 0` e `brier`, `log_loss` e `hit_rate` **nulos**, não zero. Zero parece acerto perfeito no Brier.

## 4. Banco local canônico (proposta)
O banco `preditor` do `.env` está vazio, e o backfill está no `preditor_p2` (migração 0005).

Proposta: criar o canônico `preditor` a partir do `preditor_p2` (`CREATE DATABASE preditor TEMPLATE preditor_p2` depois de remover o `preditor` vazio), migrar até a head e passar a rodar job, listener e API só nele. `preditor_p2` e `preditor_e2e` ficam como cópias de trabalho.

Regra: execuções retroativas (`daily --as-of` passado) **nunca** rodam no canônico, porque o `prediction_log` dele só aceita predições feitas na hora. O backtest do PR #65 (672 linhas com `logged_at` retroativo) fica no `preditor_e2e` e não conta como acurácia de produção.

## Fora do escopo agora
Segmento em `prediction` e `prediction_log`. O PR #65 grava uma série por (origem, destino, tipo), a de mais campanhas, e assim respeita o glossário (não mistura segmentada com geral). As séries segmentadas não são publicadas. Guardá-las exige incluir `segment_label` na chave (migração futura).
