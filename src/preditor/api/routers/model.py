from __future__ import annotations

from fastapi import APIRouter, Depends

from ..queries import fetch_model_metrics
from ..security import require_api_key

router = APIRouter()


@router.get("/model/metrics")
def model_metrics(_key: str = Depends(require_api_key)):
    return fetch_model_metrics()
