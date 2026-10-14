from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..queries import fetch_alerts
from ..security import require_api_key

router = APIRouter()


@router.get("/alerts")
def alerts(limit: int = Query(default=100, ge=1, le=500), _key: str = Depends(require_api_key)):
    return fetch_alerts(limit=limit)
