"""validated/n_sources/weight sao estado final (consolidado depois): nenhum modelo pode usa-los
como feature ou peso sem versao point-in-time (APR-008)."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "preditor"
FORBIDDEN = re.compile(r"""["'](validated|n_sources|weight)["']|\.(validated|n_sources)\b""")


def test_models_do_not_read_final_state_fields():
    offenders = []
    for name in ("model.py", "baseline.py", "walkforward.py"):
        for i, line in enumerate((SRC / name).read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if FORBIDDEN.search(line):
                offenders.append(f"{name}:{i}: {line.strip()[:100]}")
    assert not offenders, offenders
