import pathlib, subprocess, sys, os, json
root = pathlib.Path(sys.argv[1]); mp = root/"src/preditor/model.py"; orig = mp.read_text()
def rep(s, a, b, nth=1, count=1):
    idx = -1
    for _ in range(nth):
        idx = s.find(a, idx+1); assert idx >= 0, f"padrao ausente: {a[:70]}"
    return s[:idx] + b*1 + s[idx+len(a):] if count == 1 else s.replace(a, b)
A_AV = "if fs is not None and fs <= t_dt:"
M = {}
M["M0_first_seen_registro_None"] = lambda s: rep(s, "def _first_seen_dt(value: Any) -> datetime | None:\n", "def _first_seen_dt(value: Any) -> datetime | None:\n    if isinstance(value, dict) or hasattr(value, 'origin'):\n        return None\n")
M["M1_available_offers_ignora_t"] = lambda s: rep(s, A_AV, "if fs is not None:", nth=2)
M["M2_treino_sem_cutoff"] = lambda s: rep(s, "if (fs := _first_seen_dt(r)) is not None and fs <= cutoff_dt\n", "if (fs := _first_seen_dt(r)) is not None\n")
M["M4_fit_as_of_futuro"] = lambda s: rep(s, "engine.fit(train, as_of=cutoff, horizons=hs)", "engine.fit(recs, as_of=data_end, horizons=hs)")
M["M7_grade_sem_filtro_t"] = lambda s: rep(s, "if (_fs := _first_seen_dt(r)) is not None and _fs <= t_dt", "if (_fs := _first_seen_dt(r)) is not None")
M["V1_irmaos_sem_filtro_fs"] = lambda s: rep(s, A_AV, "if fs is not None:", nth=1)
M["V2_sem_purge_cutoff=test_start"] = lambda s: rep(s, "cutoff = sp.test_start - timedelta(days=purge_days)", "cutoff = sp.test_start")
M["V3_pool_walkforward_fs<=t+30d"] = lambda s: rep(s, "if (fs := _first_seen_dt(r)) is not None and fs <= t_dt\n                ]\n            pool = pool_cache[t]", "if (fs := _first_seen_dt(r)) is not None and fs <= t_dt + timedelta(days=30)\n                ]\n            pool = pool_cache[t]")
M["V4_predict_trained_at_fs<=t+30d"] = lambda s: rep(s, "r for r in records or [] if (fs := _first_seen_dt(r)) is not None and fs <= t_dt", "r for r in records or [] if (fs := _first_seen_dt(r)) is not None and fs <= t_dt + timedelta(days=30)")
M["V5_data_sem_hora_time.min"] = lambda s: rep(s, "return datetime.combine(value, time.max, tzinfo=TZ)", "return datetime.combine(value, time.min, tzinfo=TZ)")
M["V6_b1_com_todos_registros"] = lambda s: rep(s, "p_b1 = _b1_predict(\n                pool, *key,", "p_b1 = _b1_predict(\n                recs, *key,")
M["V7_sem_embargo_no_fit"] = lambda s: rep(s, "embargo_cutoff=embargo,", "embargo_cutoff=None,")
M["V8_calibracao_sem_purge"] = lambda s: rep(s, "calib_start = cut_t + timedelta(days=max_h)", "calib_start = cut_t")
M["V9_fit_filtro_as_of_removido"] = lambda s: rep(s, "if (_first_seen_dt(r) is not None and _first_seen_dt(r) <= _ao)", "if (_first_seen_dt(r) is not None)")
M["V10_predict_curve_sem_filtro_as_of"] = lambda s: rep(s, "and _first_seen_dt(r) <= _norm_dt(as_of_raw)", "and True")
M["M5_predict_trained_at_sem_filtro"] = lambda s: rep(s, "r for r in records or [] if (fs := _first_seen_dt(r)) is not None and fs <= t_dt", "r for r in records or []")
M["M3_pool_sem_filtro"] = lambda s: rep(s, "if (fs := _first_seen_dt(r)) is not None and fs <= t_dt\n                ]\n            pool = pool_cache[t]", "if (fs := _first_seen_dt(r)) is not None\n                ]\n            pool = pool_cache[t]")
tests = ["tests/test_t08b_modelo.py","tests/test_t08b_portao.py","tests/test_t08b_vazamento.py","tests/test_collector_leakage.py","tests/test_walkforward.py"]
out = {}
try:
    for name in (sys.argv[2:] or list(M)):
        mp.write_text(M[name](orig))
        r = subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","--no-header","-x" if False else "-q",*tests],cwd=root,capture_output=True,text=True)
        last = [l for l in r.stdout.splitlines() if (" passed" in l or " failed" in l or " error" in l)][-1:]
        failed = sorted({l.split("::")[1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith(("FAILED","ERROR")) and "::" in l})
        out[name] = {"resumo": last[0].strip() if last else r.stdout[-200:], "falhas": failed[:8]}
        print(name, json.dumps(out[name], ensure_ascii=False), flush=True)
finally:
    mp.write_text(orig)
