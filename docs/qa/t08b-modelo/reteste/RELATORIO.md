# Reteste T08b (PR #27, 725f6f5)

Veredito: **APROVADO COM CONDIÇÕES** (código do modelo ok para merge após 2 ajustes pequenos; **não** habilita decisão campeão × desafiante).
Banco próprio `qa_t08b` (migração não mudou desde b46f9ff, ver relatório do ciclo 1). Saídas: `attack_output.txt`, `probe_c1_output.txt`, `mutacao_pit.md`; scripts reaplicados do PR #32.

## Corrigido (verificado)
- **Bloqueador:** `probe_c1`: C1 deixou de ser 0.0 (p7=0.339, p15=1.0, p30=0.721; `trained=True`; B1 = 0.35/0.61/0.84).
- L1 (oferta com `first_seen` futuro), L2 (backfill `first_seen>as_of`), L3 (sem `first_seen_at`): prob. idêntica **e ≠ 0** (0.604); determinismo em 3 execuções.
- `C1.fit(records, as_of=…)` chama a grade com `embargo_cutoff=as_of`: 0 linhas com `t+h > as_of`.
- Monotonicidade p7 ≤ p15 ≤ p30 (0.609 / 0.609 / 0.737).
- `pytest` 84 passed, 12 skipped; `ruff check src tests migrations` limpo.

## Condições para o merge
1. **Testes PIT ainda vacuosos para o bug original**: 725f6f5 só alterou `model.py`; com o `model.py` de b46f9ff (C1 ≡ 0.0) os 6 testes **passam**. Exigir `p0 > 0` (e ≠ `base_rate` degenerado) em `test_point_in_time_model`; adicionar caso L2 (`first_seen > as_of` com `start <= as_of`). Com vazamento total, o teste já falha (ver `mutacao_pit.md`).
2. **Relatório deixou de ser marcado sintético**: `record_decision_report` perdeu o aviso "dados sintéticos / ≥25 campanhas por (par, tipo)" (R1 do ataque agora `False`), então qualquer execução gera um relatório sem rótulo; `docs/reports/t08b-champion-decision.md` versionado continua com o texto antigo, não gerado. Reinserir o aviso condicionado a n de campanhas (< 25 ⇒ sintético/insuficiente) e gerar o `.md` por script.

## Ressalvas
- Monotonicidade é um *clamp* pós-hoc (p7 = p15), não restrição do modelo; p15 = 1.0 no probe (confiança extrema com poucos dados; horizonte 30 sem variação cai em `base_rate`).
- Ainda não existe avaliação walk-forward C1 × B1 que alimente `decide_champion`; sinal de `delta_*` oposto ao contrato da API.
- Sem embargo entre treino e janela de calibração; booster final re-treinado incluindo a janela do calibrador (ciclo 1, item 2 parcial).
- **Desempenho**: `predict_proba(c1)` levou 53 s para 4 pares × 2 anos (grade 7 s + treino); inviável no job diário com muitos pares sem cache/vetorização.
- Migração `0003_calendar_seed` colide com a `0003_prediction_log_unique` do T10a (bfbc9f3): quem mesclar depois renumera.
