# Decisão campeão × desafiante (T08b)

> **Atenção**: este resultado foi obtido com **dados SINTÉTICOS** (ou sem
> campanhas reais suficientes) e só valida a mecânica do portão. A decisão
> real só vale com **≥ 25 campanhas por (par, tipo)**.
> Enquanto isso, B1 permanece em produção.

- Fonte de dados: **synthetic**
- Decisão: **keep_champion**
- Nota: dados sintéticos; dados insuficientes: livelo,smiles,transfer_bonus=0 < 25. B1 permanece em producao.

## Campanhas reais no treino por (par, tipo)

| origem,destino,tipo | campanhas | mínimo |
|---|---|---|
| livelo,smiles,transfer_bonus | 0 | 25 |

## Critérios aplicados
- C1 vira campeão apenas com dados reais, ≥ 25 campanhas por (par, tipo), vencendo B1 em Brier e log-loss com IC (bootstrap em blocos de semana ISO) excluindo zero e modelo calibrado.
- Caso contrário, B1 permanece em produção e o motivo é registrado aqui.

## Motivos
- dados sintéticos
- dados insuficientes: livelo,smiles,transfer_bonus=0 < 25
