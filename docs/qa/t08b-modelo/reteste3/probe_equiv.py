import sys, subprocess, pathlib, runpy, os
sys.argv=["x","<scratchpad>/wt27h"]
src=open("<scratchpad>/qa7/mutate27h.py").read().split("tests = [")[0]
ns={}; exec(src, ns)
M=ns["M"]; mp=ns["mp"]; orig=ns["orig"]
M["V3V4_pool+predict_fs<=t+30d"]=lambda s: M["V4_predict_trained_at_fs<=t+30d"](M["V3_pool_walkforward_fs<=t+30d"](s))
names=["BASE"]+["V3V4_pool+predict_fs<=t+30d","V5_data_sem_hora_time.min","V6_b1_com_todos_registros","V7_sem_embargo_no_fit","V9_fit_filtro_as_of_removido","V10_predict_curve_sem_filtro_as_of","M5_predict_trained_at_sem_filtro","M3_pool_sem_filtro"]
try:
    for n in names:
        mp.write_text(orig if n=="BASE" else M[n](orig))
        r=subprocess.run([sys.executable,"<scratchpad>/qa6/probe27.py"],cwd="<scratchpad>/wt27h",capture_output=True,text=True)
        print(n, (r.stdout.strip() or r.stderr[-200:]), flush=True)
finally: mp.write_text(orig)
