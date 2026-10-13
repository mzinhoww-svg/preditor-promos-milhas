# 002 Política de coleta das fontes públicas (Livelo → Smiles)

Data: 2026-10-13. Status: **aceita**. Aurimar escolheu a opção C.

Contexto: a verificação de robots.txt e termos (2026-10-13) está em `docs/plans/coletor-livelo-smiles.md`, seção 1.

Opções:
- A. Coletar artigos completos das três fontes, via feed e página.
- B. Coletar artigos completos de Passageiro de Primeira e Melhores Cartões. De Pontos pra Voar (BoardingArea), usar só título, data e link do RSS.
- C. Igual a B, e pedir autorização por escrito à BoardingArea.

Decisão: C (aceita por Aurimar). Motivo: o robots.txt da BoardingArea proíbe uso para treino de IA, e os termos vedam uso "não autorizado". Nossa extração por LLM é inferência, não treino, mas o risco não compensa enquanto o título do feed basta como segunda fonte.

Valem para todas as opções:
- robots.txt relido a cada execução;
- no máximo 1 req a cada 10 s por domínio;
- UA identificável;
- nenhum HTML integral commitado no repositório público;
- provedores LLM sem retenção para treino.

Consequência na spec (`docs/plans/coletor-livelo-smiles.md`): no C2 (Pontos pra Voar), a Wayback é usada só como listagem CDX, sem download `id_` do corpo. Título e data vêm do RSS (vivo e arquivado). O critério de cobertura conta só C1 e C3.
