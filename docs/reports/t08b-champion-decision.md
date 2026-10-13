# Decisão campeão × desafiante (T08b)

> **Atenção**: este resultado foi obtido com **dados SINTÉTICOS** e serve apenas para
> validar a mecânica do portão de decisão. **NÃO é resultado final de produção**.
> A decisão real de promoção de C1 a campeão só deve ser calculada quando o banco
> contiver **≥ 25 campanhas por (par, tipo)**. Enquanto isso, B1 (hazard sazonal)
> permanece em produção.

- Decisão sintética: **keep_champion**
- Nota sintética: C1 nao superou B1 em Brier/log-loss com IC excluindo zero com dados sinteticos atuais

## Critérios aplicados
- C1 vira campeão apenas se vencer B1 em Brier e log-loss, com IC (bootstrap em blocos) excluindo zero e modelo calibrado (curva de confiabilidade).
- Caso contrário (ou dados insuficientes), B1 permanece em produção e o motivo é registrado em `docs/reports`.
