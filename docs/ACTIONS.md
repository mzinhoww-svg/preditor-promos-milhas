# Ações externas dos agentes

| Data | Responsável | Ação |
|---|---|---|
| 2026-10-13 | orquestrador | Leitura da nota de chaves e consulta de servidores na LetsCloud (somente leitura) |
| 2026-10-13 | orquestrador | Tentativa de SSH na VPS com chaves locais: negada, nada alterado |
| 2026-10-13 | orquestrador | Repositório `preditor-promos-milhas` criado na conta mzinhoww-svg (público) |
| 2026-10-14 | Programador 2 | Backfill Wayback Livelo→Smiles (branch feat/backfill-livelo-smiles, banco preditor_p2): robots.txt checado, 1 req/10 s, User-Agent identificado, sem LLM pago |

### Resultado do backfill (2026-10-14)

| Par | Tipo | Campanhas | Validadas | Meses distintos |
|---|---|---|---|---|
| livelo→smiles | transfer_bonus | 9 | 0 (0%) | 8 |
| smiles→livelo | transfer_bonus | 3 | 0 (0%) | 3 |

Total: 12 campanhas, 0% validadas (todas de fonte única, peso 0,5). Base: 173 `raw_message`.

Fontes: passageirodeprimeira.com 176 URLs candidatas (144 coletadas, 32 falhas); melhorescartoes.com.br 60 (28 coletadas, 32 falhas); pontospravoar.com 120 só listadas.

**Não coletado:** 64 capturas com falha após 2 tentativas (indisponíveis/lentas no Wayback); pontospravoar.com sem corpo (decisão 002); nenhuma campanha validada por 2ª fonte, então o gate de ≥25 campanhas por par/tipo não é atingido; extração por regex rendeu poucas ofertas por página, sem cobertura de 24 meses contínuos (campanhas em apenas 8 meses distintos para livelo→smiles); fontes além das 3 configuradas não foram tentadas.
