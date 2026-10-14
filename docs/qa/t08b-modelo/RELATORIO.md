# QA cruzado T08b — modelo C1, grade diária, migração 0003 (PR #27, b46f9ff)

Veredito: **DEVOLVIDO** (1 bloqueador central + 3 maiores). Autor não alterado; banco próprio `qa_t08b`, Python 3.12.

## Executado
- `pytest`: 96 passed; `ruff check`: limpo.
- Migração `0003` em banco **vazio**: `alembic upgrade head` ok (head único `0003`), 11 linhas em `calendar_event`; `downgrade -1` → `upgrade head` ×2 idempotente (11 linhas). Em árvore mesclada com a main (que já tem `0002`): `0001 → 0002 → 0003`, head único. ✅
- Scripts: `attack_model.py` (saídas `attack_output_sem_shim.txt` / `attack_output_com_shim.txt`; `QA_SHIM=1` conserta só no script o bug abaixo para explorar o resto), `probe_c1.py`, `probe_root_cause.py`.

## Bloqueador
**C1 nunca treina nem prediz: devolve 0.0 para tudo.** `_first_seen_dt(value)` espera o *valor* de `first_seen_at`, mas `fit`, `predict`, `_available_offers` e `build_daily_grade` chamam `_first_seen_dt(r)` com o **registro inteiro** → sempre `None` → todos os registros são descartados como "não conhecidos".
- `probe_root_cause_output.txt`: `_first_seen_dt(registro) = None`; na grade `n_known_offers ∈ {0}` e `days_since_last_offer ∈ {999}` (todas as features históricas degeneradas).
- `probe_c1_output.txt`: mesmos dados — B1 = 0.35/0.61/0.84; C1 = 0.0/0.0/0.0 (`trained=False`, `base_rate=0`).
- **Consequência para o foco "vazamento temporal"**: `test_point_in_time_model` compara `0.0 == 0.0` e passa por vacuidade; o teste de embargo também não prova nada. A ausência de vazamento **não está demonstrada**. Com o shim (registro → `first_seen_at`) as invariâncias L1–L3 passam, mas isso é só diagnóstico.

## Maiores (aparecem depois de corrigir o bloqueador)
1. **Probabilidades não monótonas no horizonte** (shim): p7=0.750 > p15=0.741 > p30=0.732 — P(evento em 30 d) tem de ser ≥ P(7 d). Um modelo por horizonte sem restrição.
2. **Rótulo com censura à direita sem embargo**: grade vai até a última oferta; as 30 linhas finais têm y=1 em 29 (G1); `C1.fit` usa a grade sem `embargo_cutoff` (90 linhas com t+h > as_of, G2). Também não há embargo entre treino e a janela de calibração (últimos 20% por linha), e o booster final é re-treinado incluindo a janela com a qual o calibrador foi ajustado (calibrador descasado do modelo servido).
3. **Não existe avaliação campeão × desafiante**: nenhuma função produz Brier/log-loss/IC de C1 e B1 sobre as mesmas dobras walk-forward; `decide_champion` só consome métricas prontas. A decisão não é reproduzível por código. Convenção de sinal incompatível com `docs/api-contract.md` (`delta_brier` = champion − challenger positivo = melhor; contrato: negativo = melhor).
4. **Relatório "sintético"**: `record_decision_report` escreve sempre o mesmo texto fixo ("dados SINTÉTICOS", "B1 permanece em produção") — mesmo com `decision=promote_challenger` (R1 do ataque). O `docs/reports/t08b-champion-decision.md` versionado tem nota escrita à mão (não é a saída de `decide_champion`) e nenhum script/saída o reproduz. Está marcado sintético, mas o rótulo é incondicional e a base ("dados sintéticos atuais") não é rastreável.

## Menores
- `build_daily_grade`: 1ª lista `[... for r in recs if ...]` é descartada (código morto) e `known` é recalculado a cada (t, par, tipo) → O(dias·pares·tipos·registros): 54 s para 10 pares × 3 anos × 3 horizontes (sem shim a grade era degenerada); `C1.fit` por chamada refaz tudo (3 s por `predict_proba` em 4 pares × 2 anos).
- Seed: migração 0003 grava 11 eventos; `calendar_seed.SEED_EVENTS` tem 52 (outros nomes/anos) e é este que alimenta C1 — a tabela `calendar_event` do banco não é lida pelo modelo; `DOWNGRADE` apaga por nome (também linhas de outros seeds).
- `_rows_to_Xy` cai para "todas as linhas" quando não há linhas do horizonte (mistura horizontes).

## Reteste
Corrigir `_first_seen_dt(r)`; provar vazamento com teste não vacuoso (probabilidade ≠ 0 e invariante a oferta futura); embargo no treino/calibração; monotonia; função de avaliação walk-forward C1×B1 com IC; relatório gerado pelo script a partir da avaliação.
