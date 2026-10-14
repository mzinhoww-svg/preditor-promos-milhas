"""Parada de emergencia: arquivo STOP na raiz (ou PREDITOR_STOP_FILE) ou flag PREDITOR_STOP=1."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_TRUTHY = {"1", "true", "yes", "on"}


class StopRequested(RuntimeError):
    """STOP presente: o job/coletor deve abortar antes de ler ou gravar qualquer coisa."""


def _stop_files() -> list[Path]:
    override = (os.environ.get("PREDITOR_STOP_FILE") or "").strip()
    if override:
        return [Path(override)]
    return [Path.cwd() / "STOP", REPO_ROOT / "STOP"]


def stop_requested() -> bool:
    if (os.environ.get("PREDITOR_STOP") or "").strip().lower() in _TRUTHY:
        return True
    return any(p.exists() for p in _stop_files())


def check_stop() -> None:
    if stop_requested():
        raise StopRequested("STOP presente: execução abortada sem gravar")
