from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..queries import fetch_predictions
from ..security import require_api_key

router = APIRouter()


@router.get("/predictions")
def predictions(type: str | None = Query(default=None, alias="type"),
                limit: int = Query(default=50),
                _key: str = Depends(require_api_key)):
    return fetch_predictions(type_filter=type, limit=limit)
