from __future__ import annotations

from fastapi import APIRouter, Depends

from ..queries import fetch_source_health
from ..security import require_api_key

router = APIRouter()


@router.get("/source-health")
def source_health(_key: str = Depends(require_api_key)):
    return fetch_source_health()
