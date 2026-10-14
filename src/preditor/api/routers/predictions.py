from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..queries import fetch_explanation, fetch_predictions
from ..security import require_api_key

router = APIRouter()


@router.get("/predictions")
def predictions(type: str | None = Query(default=None, alias="type"),
                limit: int = Query(default=50),
                _key: str = Depends(require_api_key)):
    return fetch_predictions(type_filter=type, limit=limit)


@router.get("/predictions/{origin}/{destination}/explanation")
def explanation(origin: str, destination: str,
                type: str = Query(default="transfer_bonus", alias="type"),
                _key: str = Depends(require_api_key)):
    out = fetch_explanation(origin, destination, type)
    if out is None:
        raise HTTPException(status_code=404, detail="sem predição para o item")
    return out
