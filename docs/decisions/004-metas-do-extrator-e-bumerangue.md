# 004 Metas de qualidade do extrator e tratamento do bumerangue

Data: 2026-10-13.

## Metas minimas do extrator (contra o conjunto de ouro, data/gold)
Para treinar o modelo, o extrator completo (regex + LLM) deve atingir, por campo:
- programa origem/destino: precisao e cobertura >= 95%;
- tipo do evento: precisao e cobertura >= 95%;
- erro de data de inicio <= 1 dia em >= 90% dos casos;
- bonus_pct exato em >= 90% dos casos.
Abaixo disso, corrige-se o extrator antes de avancar. A camada regex (T07a) e medida separadamente da camada LLM; o conjunto de ouro e imutavel (so o humano altera) e marcado gold_provisional ate conferencia.

## Bumerangue Livelo
Decisao de Aurimar (2026-10-13, resposta no terminal do Planejador): **ignorar**. O bonus do bumerangue nao e somado ao bonus de transferencia do par, para nao inflar a magnitude. Fica registrado como campo opcional separado `bumerangue_pct` para consulta, sem entrar no alvo do modelo.

## Segmento
Campo `segment_label` entra no esquema de saida do extrator (decisao de Aurimar), para que duas ofertas segmentadas no mesmo dia nao colidam na chave unica.
