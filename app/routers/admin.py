# app/routers/admin.py (snippet)
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from ..config import settings
from ..processor import run_sync, reprocess_raw


router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(authorization: str | None = Header(default=None, alias="Authorization")):
    """
    If ADMIN_BEARER_TOKEN is set on the server, require `Authorization: Bearer <token>`.
    If it's empty/None, allow access (useful for local dev).
    """
    expected = (settings.ADMIN_BEARER_TOKEN or "").strip()
    if not expected:
        return True  # no auth mode
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True

class RunParams(BaseModel):
    start_year: int | None = None
    years_ahead: int | None = None
    max_week: int | None = None

@router.post("/write-test")
def write_test(_: None = Depends(require_admin)):
    import os
    from ..config import settings
    p = os.path.join(settings.DATA_ROOT, "raw", "_health.txt")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("ok")
    return {"ok": True, "path": p}

class ReprocessParams(BaseModel):
    sport: str | None = None    # 'nfl' | 'cfb' | None (both)
    year: int | None = None
    force: bool = True

@router.post("/reprocess")
def reprocess_endpoint(body: ReprocessParams, _: None = Depends(require_admin)):
    """
    Re-run processing against existing raw files.
    """
    result = reprocess_raw(
        data_root=settings.DATA_ROOT,
        sport=body.sport,
        year=body.year,
        force=body.force,
    )
    return result


@router.post("/run-sync")
def run_sync_endpoint(body: RunParams, _: None = Depends(require_admin)):
    print(f"[admin] run-sync params: {body.dict()}")
    summary = run_sync(
        start_year=body.start_year,
        years_ahead=body.years_ahead,
        max_week=body.max_week,
        api_base=settings.API_BASE,
        data_root=settings.DATA_ROOT,
    )
    return summary