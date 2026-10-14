# Parada de emergência (STOP)

Para parar o job diário, o backfill e o listener sem matar o processo:

- crie o arquivo `STOP` na raiz do repositório (ou no diretório de execução), **ou**
- defina `PREDITOR_STOP_FILE=<caminho>` (arquivo qualquer), **ou**
- defina `PREDITOR_STOP=1`.

## Semântica: STOP é cooperativo

- O STOP é verificado na entrada de cada comando e **entre** unidades de trabalho (cada URL/snapshot
  do backfill, cada fonte e item do listener, cada grupo do `run_daily`, cada mensagem do
  `--reprocess`). A unidade **em curso termina**: não há interrupção no meio de uma requisição ou
  gravação.
- Efeito: nenhuma unidade nova começa depois do STOP. Por isso o parada pode demorar até o fim do
  item atual (no backfill, até a pausa de `rate_limit` + uma requisição).
- Códigos de saída: `3` nos CLIs (`preditor.jobs.daily_predict`, `preditor.backfill`,
  `preditor.jobs.feed_listener`). A exceção `preditor.stop.StopRequested` **não** é `RuntimeError`.
- `run_daily` e o coletor gravam por unidade; o que já foi gravado fica (idempotente, retomável).
- `--reprocess` é **atômico**: o `DELETE` de `offer`/`offer_evidence` e a reconstrução ocorrem numa
  única transação; STOP ou erro no meio faz rollback e mantém o estado anterior.
- Para retomar: remova o arquivo/flag e rode de novo.
