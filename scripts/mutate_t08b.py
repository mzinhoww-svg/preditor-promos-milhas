"""Aplica uma mutacao de vazamento (M1/M2/M4/M7) em model.py, roda o comando e reverte.
Uso: python scripts/mutate_t08b.py M1 pytest tests/test_t08b_vazamento.py -q"""
import os
import pathlib
import subprocess
import sys

M = pathlib.Path("src/preditor/model.py"); orig = M.read_text()
def sub(s,a,b):
    assert a in s, a[:50]; return s.replace(a,b,1)
MUT = {
 "M1": lambda s: sub(s,"        if fs is not None and fs <= t_dt:\n            out.append(r)","        if fs is not None:\n            out.append(r)"),
 "M2": lambda s: sub(s,"            if (fs := _first_seen_dt(r)) is not None and fs <= cutoff_dt\n","            if (fs := _first_seen_dt(r)) is not None\n"),
 "M4": lambda s: sub(s,"engine.fit(train, as_of=cutoff, horizons=hs)","engine.fit(recs, as_of=data_end, horizons=hs)"),
 "M7": lambda s: sub(s,"if (_fs := _first_seen_dt(r)) is not None and _fs <= t_dt","if (_fs := _first_seen_dt(r)) is not None"),
}
name = sys.argv[1]; cmd = sys.argv[2:]
try:
    M.write_text(MUT[name](orig))
    r = subprocess.run(cmd, check=False, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH="src"))
    print(f"== {name}\n" + (r.stdout[-2500:] or r.stderr[-1500:]))
finally:
    M.write_text(orig)
