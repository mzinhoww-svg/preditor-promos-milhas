import pathlib, subprocess, sys, re, os
root = pathlib.Path(sys.argv[1]); orig = pathlib.Path(sys.argv[2]).read_text()
m = root/"src/preditor/model.py"
def sub(s, a, b, count=1):
    assert a in s, f"padrao nao encontrado: {a[:60]}"
    return s.replace(a, b, count)
MUT = {}
# M0: bug original do ciclo 1: _first_seen_dt de registro sempre None
MUT["M0_first_seen_sempre_None"] = lambda s: sub(s, "def _first_seen_dt(value: Any) -> datetime | None:\n", "def _first_seen_dt(value: Any) -> datetime | None:\n    if isinstance(value, dict) or hasattr(value, 'origin'):\n        return None\n")
# M1: vazamento total: _available_offers ignora t
MUT["M1_available_offers_ignora_t"] = lambda s: sub(s, "        if fs is not None and fs <= t_dt:\n            out.append(r)", "        if fs is not None:\n            out.append(r)")
# M2: walk-forward treina com todo o train sem cutoff/purge
MUT["M2_treino_sem_cutoff"] = lambda s: sub(s, "            if (fs := _first_seen_dt(r)) is not None and fs <= cutoff_dt\n", "            if (fs := _first_seen_dt(r)) is not None\n")
# M3: pool de predicao no walk-forward ve o futuro (fs<=data_end)
MUT["M3_pool_futuro"] = lambda s: sub(s, "                    if (fs := _first_seen_dt(r)) is not None and fs <= t_dt\n", "                    if (fs := _first_seen_dt(r)) is not None\n")
# M4: engine.fit com as_of=data_end (futuro)
MUT["M4_fit_as_of_futuro"] = lambda s: sub(s, "engine.fit(train, as_of=cutoff, horizons=hs)", "engine.fit(recs, as_of=data_end, horizons=hs)")
MUT["M5_predict_trained_at_sem_filtro"] = lambda s: sub(s, "            r for r in records or [] if (fs := _first_seen_dt(r)) is not None and fs <= t_dt\n        ]\n        curve", "            r for r in records or []\n        ]\n        curve")
MUT["M6_vazamento_total_predicao"] = lambda s: MUT["M5_predict_trained_at_sem_filtro"](MUT["M3_pool_futuro"](MUT["M1_available_offers_ignora_t"](s)))
MUT["M7_grade_features_sem_filtro_t"] = lambda s: sub(s, "if (_fs := _first_seen_dt(r)) is not None and _fs <= t_dt", "if (_fs := _first_seen_dt(r)) is not None")
which = sys.argv[3:]
tests = ["tests/test_t08b_modelo.py","tests/test_t08b_portao.py","tests/test_collector_leakage.py","tests/test_walkforward.py"]
for name in which:
    m.write_text(MUT[name](orig))
    if os.environ.get("PROBE"):
        r = subprocess.run([sys.executable, os.environ["PROBE"]], cwd=root, capture_output=True, text=True)
        print(f"== {name}"); print((r.stdout.strip() or r.stderr[-300:])); continue
    r = subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","--no-header","-rf",*tests],cwd=root,capture_output=True,text=True,env=dict(os.environ))
    lines = [l for l in r.stdout.splitlines() if l.startswith(("FAILED","ERROR")) or l.strip().endswith(("s","s)")) and ("passed" in l or "failed" in l)]
    print(f"== {name}"); print("\n".join(l[:150] for l in lines[:14]) or r.stdout[-400:])
m.write_text(orig)
