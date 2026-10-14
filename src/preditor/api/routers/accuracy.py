from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..queries import fetch_prediction_accuracy
from ..security import require_api_key

router = APIRouter()


@router.get("/prediction-log/accuracy")
def prediction_accuracy(from_: str | None = Query(default=None, alias="from"),
                       to: str | None = Query(default=None),
                       horizon: int | None = Query(default=None),
                       _key: str = Depends(require_api_key)):
    data = fetch_prediction_accuracy(date_from=from_, date_to=to, horizon=horizon)
    return data
