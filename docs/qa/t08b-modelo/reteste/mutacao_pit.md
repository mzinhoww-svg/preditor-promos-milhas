# Mutação PIT (QA) — os testes de vazamento falham quando o futuro vaza?
Cópia isolada de `src`+`tests` (725f6f5) com mutações; `pytest tests/test_t08b_modelo.py`.

| Mutação | Resultado |
|---|---|
| `_first_seen_dt` devolve 1970 (todo registro "conhecido" desde sempre = vazamento total) | **falha** `test_point_in_time_model` (0.951 ≠ 0.679) ✅ |
| `fit`/`predict` ignoram o filtro de `first_seen` (grade ainda embargada em `as_of`) | passa (6/6) — mutante equivalente na prática: o `embargo_cutoff` do fit já impede a oferta futura de entrar; não é vazamento observável |
| **Bug original** (`model.py` de b46f9ff, C1 ≡ 0.0) com os testes atuais | **passa 6/6** ❌ — os testes não foram alterados em 725f6f5 e continuam comparando `p0 == p1` sem exigir `p0 > 0` |
