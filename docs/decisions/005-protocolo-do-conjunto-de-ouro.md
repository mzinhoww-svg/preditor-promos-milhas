# 005 Protocolo do conjunto de ouro (T06)

Data: 2026-10-13. Status: **proposta do Planejador**. As escolhas 1 e 2 aguardam o aceite de Aurimar; até lá vale a recomendação.

## 1. Uso das 50 campanhas
- A. Todas servem para ajustar e medir o extrator.
- B. Split por campanha, 20 `dev` (ajuste) e 30 `test` (só medição). **Recomendada.**
- C. Validação cruzada em k dobras.

Motivo: com A, a regex e o prompt se ajustam ao próprio ouro, e a meta de 95% passa sem garantir generalização. C é cara de manter com o ouro imutável. B é simples e honesta. O custo é medir com n=30, por isso o relatório usa IC por campanha.

## 2. Texto no repositório público
- A. Artigo integral.
- B. Trecho de até 600 caracteres, mais URL, timestamp Wayback e hash do conteúdo. **Recomendada.**
- C. Só o hash e o ID, com o texto apenas no banco local.

Motivo: A viola a decisão 002 ("nenhum HTML integral commitado"). C torna o ouro irreproduzível fora da máquina local. B basta para a extração. Pontos pra Voar fica só com o título (002, opção C).

## 3. Rótulo esperado (não é escolha, é regra)
O `expected` se baseia só no texto da mensagem e no `observed_at`. Conhecimento posterior, como outra fonte ou a data real, nunca corrige o esperado de uma mensagem. Ele entra apenas na campanha consolidada.

## 4. Imutabilidade
`gold_provisional` até a conferência de Aurimar. Linhas `gold_verified` são protegidas por `MANIFEST.sha256`, teste e CODEOWNERS; só o humano altera (decisão 004).
