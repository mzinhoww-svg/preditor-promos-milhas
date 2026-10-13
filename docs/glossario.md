# Glossário de eventos

Todos os agentes seguem este glossário. Mudança exige decisão registrada em `docs/decisions/`.

- **Campanha**: oferta com par (origem, destino), tipo e data de início. Chave de deduplicação: (origem, destino, tipo) + janela de ±3 dias no início.
- **Tipos**: `transfer_bonus` (bônus de transferência), `purchase_discount` (compra de pontos com desconto), `boosted_accrual` (acúmulo turbinado).
- **Renovação**: nova campanha do mesmo par e tipo iniciada depois do fim da anterior. É um novo evento.
- **Prorrogação**: extensão do fim de uma campanha em curso, sem mudar o bônus. Não é novo evento; atualiza `end_at`.
- **Oferta segmentada**: restrita a clube, público ou cartão (`segmented=true` e `segment_label`). Entra com par e tipo próprios para não misturar com a oferta geral.
- **Oferta relâmpago**: duração de até 48 horas. É evento normal, marcada na evidência; a janela de ±3 dias já a cobre.
- **Fonte única**: campanha vista em uma só fonte. Entra no treino com peso 0,5 e nunca é descartada em silêncio.
- **Validada**: `validated=true` com >= 2 fontes distintas com início a no máximo 3 dias entre si.
- **Conflito de data**: fontes com datas diferentes. `date_conflict=true` e `start_at` = data mais antiga confiável.
- **first_seen_at**: instante do primeiro alerta. Features usam só o conhecido até esse instante.
