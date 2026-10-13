"""Testes da lógica pura do painel de progresso."""
from __future__ import annotations

import json

from preditor.painel import calc_progress


def test_empty_checklist_exposes_error():
    r = calc_progress([])
    assert r["checklist_error"]
    assert r["overall"] is None


def test_invalid_checklist_exposes_error():
    r = calc_progress("not json")
    assert r["checklist_error"]
    r2 = calc_progress({})
    assert r2["checklist_error"]



def test_all_done_is_one():
    items = [{"id": "a", "fase": "Setup", "peso": 2, "estado": "Feito"}]
    r = calc_progress(items)
    assert r["overall"] == 1.0
    assert r["by_phase"]["Setup"] == 1.0


def test_factors_weighted():
    items = [
        {"id": "a", "fase": "Setup", "peso": 1, "estado": "Feito"},        # 1
        {"id": "b", "fase": "Setup", "peso": 1, "estado": "Em revisao"},   # .75
        {"id": "c", "fase": "Setup", "peso": 1, "estado": "Em andamento"}, # .4
        {"id": "d", "fase": "Setup", "peso": 1, "estado": "Pendente"},     # 0
        {"id": "e", "fase": "Setup", "peso": 1, "estado": "Bloqueado"},    # 0
    ]
    r = calc_progress(items)
    assert abs(r["overall"] - (2.15 / 5)) < 1e-9


def test_nonfinite_weight_does_not_create_nan():
    import math
    items = [{"estado": "Feito", "peso": float("inf"), "fase": "Setup"}]
    r = calc_progress(items)
    assert r["overall"] is not None
    assert math.isfinite(r["overall"])


def test_blocked_and_pending_zero():
    items = [{"estado": "Bloqueado", "peso": 3}, {"estado": "Pendente", "peso": 2}]
    assert calc_progress(items)["overall"] == 0.0


def test_by_phase():
    items = [
        {"fase": "Setup", "peso": 1, "estado": "Feito"},
        {"fase": "Modelo", "peso": 2, "estado": "Em andamento"},
    ]
    r = calc_progress(items)
    assert r["by_phase"]["Setup"] == 1.0
    assert abs(r["by_phase"]["Modelo"] - 0.4) < 1e-9
    assert "Setup" in r["by_phase"]


def test_accepts_dict_with_items():
    data = {"items": [{"estado": "Feito", "peso": 1, "fase": "Setup"}]}
    assert calc_progress(data)["overall"] == 1.0


def test_accepts_string_json():
    s = json.dumps({"itens": [{"estado": "Feito", "peso": 1, "fase": "Setup"}]})
    assert calc_progress(s)["overall"] == 1.0


def test_accepts_checklist_kw():
    items = [{"estado": "Feito", "peso": 1, "fase": "Setup"}]
    assert calc_progress(checklist=items)["overall"] == 1.0


def test_pt_en_field_aliases():
    it = [{"estado": "Feito", "peso": 2, "fase": "Setup"}]
    it2 = [{"status": "done", "weight": 2, "phase": "Setup"}]
    assert calc_progress(it)["overall"] == calc_progress(it2)["overall"] == 1.0


def test_state_counts():
    items = [{"estado": "Feito"}, {"estado": "Pendente"}]
    r = calc_progress(items)
    assert r["state_counts"]["Feito"] == 1
    assert r["state_counts"]["Pendente"] == 1


def test_refresh_allowed_rate_limit():
    from preditor.painel import refresh_allowed

    assert refresh_allowed(100.0, 101.0, 2.0) is False
    assert refresh_allowed(100.0, 102.0, 2.0) is True


def test_ignores_non_dict_items():
    r = calc_progress([1, "x", None])
    assert r["checklist_error"]


def test_infinity_weight_is_finite_and_serializable():
    import json
    import math

    r = calc_progress([{"estado": "Feito", "peso": 1e999, "fase": "Setup"}])
    assert math.isfinite(r["overall"])
    json.dumps(r, allow_nan=False)


def test_html_script_parses_with_node():
    import re
    import shutil
    import subprocess
    from pathlib import Path

    if shutil.which("node") is None:
        return
    src = Path("tools/painel/server.py").read_text(encoding="utf-8")
    match = re.search(r"<script>\n(.*?)\n</script>", src, re.DOTALL)
    assert match is not None
    script_path = Path("/tmp/painel_script_check.js")
    script_path.write_text(match.group(1), encoding="utf-8")
    completed = subprocess.run(["node", "--check", str(script_path)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_server_does_not_execute_pytest():
    from pathlib import Path

    src = Path("tools/painel/server.py").read_text(encoding="utf-8")
    assert "uv run pytest" not in src
