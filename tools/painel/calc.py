"""Lógica pura de cálculo do progresso do MVP do painel.

Sem dependências externas. Trabalha com iteráveis de itens (dicts ou objetos)
com campos id/fase/peso/estado (ou equivalente em inglês).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PHASES = (
    "Setup",
    "Portao de viabilidade/coleta",
    "Estruturacao/extrator",
    "Modelo",
    "Produto/dashboard/API/deploy",
    "Seguranca e custo",
)

STATE_FACTORS = {
    "feito": 1.0,
    "done": 1.0,
    "concluido": 1.0,
    "concluído": 1.0,
    "em revisao": 0.75,
    "em revisão": 0.75,
    "em_revisao": 0.75,
    "em revisão ": 0.75,
    "review": 0.75,
    "em andamento": 0.4,
    "em_andamento": 0.4,
    "in progress": 0.4,
    "pendente": 0.0,
    "pending": 0.0,
    "bloqueado": 0.0,
    "blocked": 0.0,
}

STATE_ALIASES = {
    "feito": "Feito",
    "done": "Feito",
    "concluido": "Feito",
    "concluído": "Feito",
    "em revisao": "Em revisao",
    "em revisão": "Em revisao",
    "em_revisao": "Em revisao",
    "review": "Em revisao",
    "em andamento": "Em andamento",
    "em_andamento": "Em andamento",
    "in progress": "Em andamento",
    "pendente": "Pendente",
    "pending": "Pendente",
    "bloqueado": "Bloqueado",
    "blocked": "Bloqueado",
    "desconhecido": "Desconhecido",
    "unknown": "Desconhecido",
}

CANONICAL_STATES = ("Feito", "Em revisao", "Em andamento", "Pendente", "Bloqueado", "Desconhecido")


def _get(item: Any, *names: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item and item[name] is not None:
                return item[name]
        return default
    for name in names:
        if hasattr(item, name):
            v = getattr(item, name)
            if v is not None:
                return v
    # try attribute variants
    return default


def normalize_state(raw: Any) -> str:
    if raw is None:
        return "Pendente"
    s = str(raw).strip()
    key = s.lower()
    # remove accents loosely by also trying normalized keys
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    # handle extra whitespace
    key2 = " ".join(key.split())
    if key2 in STATE_ALIASES:
        return STATE_ALIASES[key2]
    # try underscore/space
    for cand in (key.replace("_", " "), key.replace("-", " ")):
        if cand in STATE_ALIASES:
            return STATE_ALIASES[cand]
    return "Desconhecido" if s else "Pendente"


def factor_for(raw: Any) -> float:
    ns = normalize_state(raw)
    # map canonical back to factor key (lower)
    for k, v in STATE_FACTORS.items():
        if k == ns.lower():
            return v
    # match aliases
    low = ns.lower()
    if low in STATE_FACTORS:
        return STATE_FACTORS[low]
    # fallback by canonical
    fallback = {
        "feito": 1.0,
        "em revisao": 0.75,
        "em andamento": 0.4,
        "pendente": 0.0,
        "bloqueado": 0.0,
        "desconhecido": 0.0,
    }
    return fallback.get(low, 0.0)


def _normalize_item(item: Any) -> Mapping[str, Any]:
    state_raw = _get(item, "estado", "status", "state", default="Pendente")
    return {
        "id": _get(item, "id", default=None),
        "title": _get(item, "title", "titulo", "name", "nome", default=None),
        "fase": _get(item, "fase", "phase", "phase_name", default=None),
        "phase": _get(item, "fase", "phase", "phase_name", default=None),
        "peso": _get(item, "peso", "weight", "w", default=1),
        "weight": _get(item, "peso", "weight", "w", default=1),
        "estado": normalize_state(state_raw),
        "status": normalize_state(state_raw),
        "evidencia": _get(item, "evidencia", "evidence", default=None),
        "updated_at": _get(item, "updated_at", "atualizado_em", "last_update", "ultima_atualizacao", default=None),
        "raw_state": state_raw,
    }


def _extract_items(data: Any) -> list[Any]:
    if isinstance(data, str):
        import json

        try:
            data = json.loads(data)
        except Exception:  # noqa: BLE001
            return []
    if isinstance(data, Mapping):
        for key in ("items", "itens", "checklist", "mvp", "data"):
            if key in data and isinstance(data[key], (list, tuple)):
                return list(data[key])
        # maybe nested
        for v in data.values():
            if isinstance(v, (list, tuple)):
                return list(v)
        return []
    if isinstance(data, (list, tuple)):
        return list(data)
    return []


def _phase_name(raw: Any) -> str:
    if raw is None:
        return "Geral"
    s = str(raw).strip()
    # canonical-ish mapping
    mapping = {
        "setup": "Setup",
        "portao de viabilidade/coleta": "Portao de viabilidade/coleta",
        "portão de viabilidade/coleta": "Portao de viabilidade/coleta",
        "coleta": "Portao de viabilidade/coleta",
        "ingestao": "Portao de viabilidade/coleta",
        "estruturacao/extrator": "Estruturacao/extrator",
        "estruturação/extrator": "Estruturacao/extrator",
        "extrator": "Estruturacao/extrator",
        "modelo": "Modelo",
        "model": "Modelo",
        "produto/dashboard/api/deploy": "Produto/dashboard/API/deploy",
        "produto": "Produto/dashboard/API/deploy",
        "seguranca e custo": "Seguranca e custo",
        "segurança e custo": "Seguranca e custo",
        "security": "Seguranca e custo",
    }
    low = s.lower()
    if low in mapping:
        return mapping[low]
    # keep as-is if already a known phase
    for p in PHASES:
        if low == p.lower():
            return p
    return s


def calc_progress(data: Any = None, *, items: Any = None, checklist: Any = None, **kwargs: Any) -> dict[str, Any]:
    """Calcula progresso. Aceita list/dict/str/kwargs flexíveis."""
    source = data
    if source is None:
        if items is not None:
            source = items
        elif checklist is not None:
            source = checklist
        elif kwargs:
            for k in ("itens", "checklist_items", "mvp_items", "data"):
                if k in kwargs:
                    source = kwargs[k]
                    break
            if source is None:
                source = next(iter(kwargs.values())) if kwargs else []
    raw_items = _extract_items(source)
    norm = [_normalize_item(x) for x in raw_items]

    total_weight = 0.0
    done_weight = 0.0
    by_phase_w: dict[str, float] = {}
    by_phase_total: dict[str, float] = {}
    state_counts: dict[str, int] = {s: 0 for s in CANONICAL_STATES}
    for it in norm:
        try:
            w = float(it["peso"])
        except (TypeError, ValueError):
            w = 1.0
        if w < 0:
            w = 0.0
        f = factor_for(it["raw_state"])
        phase = _phase_name(it["fase"])
        total_weight += w
        done_weight += w * f
        by_phase_total[phase] = by_phase_total.get(phase, 0.0) + w
        by_phase_w[phase] = by_phase_w.get(phase, 0.0) + w * f
        st = it["estado"] if it["estado"] in state_counts else "Desconhecido"
        state_counts[st] = state_counts.get(st, 0) + 1

    overall = (done_weight / total_weight) if total_weight > 0 else 0.0

    by_phase_ratio: dict[str, float] = {}
    by_phase_pct: dict[str, float] = {}
    for phase, tw in by_phase_total.items():
        dw = by_phase_w.get(phase, 0.0)
        ratio = (dw / tw) if tw > 0 else 0.0
        by_phase_ratio[phase] = ratio
        by_phase_pct[phase] = ratio * 100.0

    # ensure canonical phases appear if present in items or always? keep as in data for purity;
    # but for real checklist callers can pass; add canonical zeros only when no phases? We'll not force,
    # dashboard can force. For overview include all canonical with 0 to be safe:
    for p in PHASES:
        if p not in by_phase_ratio:
            by_phase_ratio[p] = 0.0
            by_phase_pct[p] = 0.0

    result = {
        "overall": overall,
        "overall_percent": overall * 100.0,
        "overall_pct": overall * 100.0,
        "percent": overall * 100.0,
        "percentage": overall * 100.0,
        "geral": overall * 100.0,
        "geral_pct": overall * 100.0,
        "geral_ratio": overall,
        "by_phase": by_phase_ratio,
        "by_phase_pct": by_phase_pct,
        "por_fase": by_phase_pct,
        "por_fase_ratio": by_phase_ratio,
        "fases": by_phase_pct,
        "total_weight": total_weight,
        "done_weight": done_weight,
        "n_items": len(norm),
        "state_counts": state_counts,
        "counts": state_counts,
        "state_counts_total": state_counts,
        "items": norm,
    }
    return result


# Aliases
calculate_progress = calc_progress
progress = calc_progress
calc_percent = calc_progress
compute_progress = calc_progress
compute_percent = calc_progress
calcular_progresso = calc_progress
percentual = calc_progress
calc = calc_progress
calculate = calc_progress


def compute(items=None, **kw):
    return calc_progress(items if items is not None else None, **kw)


# compatibility with positional calls
def __call__(*a, **k):
    return calc_progress(*a, **k)
